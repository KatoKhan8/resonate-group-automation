#!/usr/bin/env python3
"""A bounded-concurrency gather primitive that cannot break the spend audit.

## The measurement this exists to answer

`docs/PERF-LATENCY-MODEL-2026-09-18.md`: provider wait is 98-99% of a real
5,000-record pass in every latency band, against ~15s of our own CPU. K=4
would take a pass from ~33 minutes of waiting to ~8.

## What this module is, and what it is not

This is a concurrency primitive for I/O-bound HTTP calls. It is NOT wired
into `enrich.run` - that is a separate reviewable decision, the same way
`queuejournal` was landed before `store.save` was touched.

The shape is decide-serially, fetch-concurrently, apply-serially:

    1. DECIDE   which calls to make, serially, in record order. No I/O.
    2. GATHER   execute those calls concurrently, bounded at K. No decisions,
                no spending, no state mutation - just round trips.
    3. APPLY    consume the results serially, IN THE ORIGINAL ORDER, charging
                the budget and appending to the ledger exactly as today.

This module is step 2 only. It does not touch the store, the budget, the
ledger or any record. Step 3 in the original order is what makes the ledger
byte-identical to a serial run, which is the property that keeps the spend
audit working.

## Why ThreadPoolExecutor and not asyncio

The calls are I/O-bound HTTP against provider modules written as blocking
functions. asyncio would mean rewriting every provider module. Threads are
the right abstraction for wrapping existing blocking I/O.

## Rate limits: K is a ceiling, not a target

The enrichment providers that dominate the call count have UNKNOWN rate
limits, and EmailBison's 3,000 rpm is MARKETING, not in the API reference.
So `k` defaults to 4, the conservative recommendation. An optional
`min_interval` lets a caller throttle without changing `k`. There are no
retries: a 429 is a result the caller classifies, not something this
primitive hides.
"""
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class _CallableTimeoutError(BaseException):
    """Wraps a TimeoutError raised BY the callable, so gather can tell it
    apart from a TimeoutError raised by the future's own deadline.

    Both surface as `TimeoutError` from `Future.result(timeout=...)`. Without
    this wrapper, a callable that raises TimeoutError (e.g. a socket timeout)
    would be misclassified as `timed_out` instead of `failed`.
    """


@dataclass(frozen=True, slots=True)
class Outcome:
    """The result of one gathered call.

    Four kinds, each distinguishable without ambiguity:

        ok            the call returned a value
        failed        it raised; the exception is CARRIED, not swallowed
        timed_out     it exceeded the per-item timeout
        not_attempted the pool shut down before reaching it

    A bare `False` or an empty dict never stands in for confusion: the `kind`
    field says what happened, and `value` carries the payload or the reason.
    """
    kind: str
    value: Any = None

    __match_args__ = ("kind", "value")

    @staticmethod
    def ok(value: Any) -> "Outcome":
        return Outcome(kind="ok", value=value)

    @staticmethod
    def failed(exc: BaseException) -> "Outcome":
        return Outcome(kind="failed", value=exc)

    @staticmethod
    def timed_out() -> "Outcome":
        return Outcome(kind="timed_out")

    @staticmethod
    def not_attempted() -> "Outcome":
        return Outcome(kind="not_attempted")

    @property
    def is_ok(self) -> bool:
        return self.kind == "ok"

    @property
    def is_failed(self) -> bool:
        return self.kind == "failed"

    @property
    def is_timed_out(self) -> bool:
        return self.kind == "timed_out"

    @property
    def is_not_attempted(self) -> bool:
        return self.kind == "not_attempted"

    def __repr__(self) -> str:
        if self.kind == "ok":
            return f"Outcome(ok={self.value!r})"
        if self.kind == "failed":
            return f"Outcome(failed={type(self.value).__name__}: {self.value})"
        return f"Outcome({self.kind})"


def gather(
    items: Sequence[T],
    call: Callable[[T], R],
    k: int = 4,
    timeout: Optional[float] = None,
    min_interval: Optional[float] = None,
) -> List[Outcome]:
    """Execute `call` for each item with bounded concurrency.

    Returns exactly one Outcome per input item, in input order, regardless of
    completion order. The callable is executed exactly once per item. No
    retries, no shared mutable state, no state mutation of any kind.

    Args:
        items: The inputs, processed in order.
        call: A callable taking one item and returning a result. It must not
              retry - a retry hidden inside the pool would double-spend at a
              paid provider.
        k: Maximum concurrent calls. Defaults to 4.
        timeout: Per-item timeout in seconds. None means no timeout.
        min_interval: Minimum seconds between dispatches. None means no
                      throttling. K is still the concurrency ceiling.

    Returns:
        A list of Outcome, one per item, in input order.
    """
    if not items:
        return []

    def _wrapped(item):
        try:
            return call(item)
        except TimeoutError as exc:
            raise _CallableTimeoutError(exc) from exc

    outcomes: List[Outcome] = [Outcome.not_attempted()] * len(items)
    executor = ThreadPoolExecutor(max_workers=k)
    futures = [None] * len(items)

    try:
        last_submit = time.monotonic()
        for i, item in enumerate(items):
            if min_interval is not None and i > 0:
                elapsed = time.monotonic() - last_submit
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
            last_submit = time.monotonic()
            futures[i] = executor.submit(_wrapped, item)

        for i, fut in enumerate(futures):
            try:
                result = fut.result(timeout=timeout)
                outcomes[i] = Outcome.ok(result)
            except TimeoutError:
                outcomes[i] = Outcome.timed_out()
            except _CallableTimeoutError as exc:
                outcomes[i] = Outcome.failed(exc.__cause__)
            except BaseException as exc:
                outcomes[i] = Outcome.failed(exc)
    finally:
        executor.shutdown(wait=False)

    return outcomes
