#!/usr/bin/env python3
"""A bounded-concurrency gather primitive and its first caller.

## The measurement this rests on

`docs/PERF-CONCURRENCY-MEASURED-2026-09-18.md`, against live ContactOut:

    K=1   2.10 req/s   p50 0.461s
    K=4   8.19 req/s   p50 0.477s   3.89x
    K=8  16.78 req/s   p50 0.454s   7.98x     <- operate here
    K=12 17.29 req/s   p50 0.432s   8.23x     <- the knee, and it is ours

Zero 429s at every level. Latency did not degrade under concurrency; p95
improved. `people-count` is 4,822 of the 8,760 provider calls in a modelled
5,000-record pass; at K=8 the serial ~37-minute wait becomes ~5.

## What this module is

Two things, landed together because the primitive without a caller is the
mistake TASK-029 / TASK-028 / TASK-019 all made:

    1. `gather`             the concurrency primitive: decide-serially,
                            fetch-concurrently, apply-serially. Step 2 only.
    2. `prefetch_headcount` the first caller: prefetches
                            `company_facts.headcount_signal` across records
                            before `enrich.run` walks them one at a time.

The shape is decide-serially, fetch-concurrently, apply-serially IN INPUT
ORDER. Input order is what keeps the waterfall ledger byte-identical to a
serial run, and that is the acceptance test.

## Why THIS call and not a more important one

Because it costs nothing. `enrich.COSTS["people-count"]` is 0. The gather
docstring names the trap that makes concurrency dangerous here: a timed-out
call STILL REACHED THE PROVIDER AND STILL COST A CREDIT. On a paid route,
fifty timeouts under-count the ledger by fifty credits and
`costs.reconcile()` then reports clean against a wrong number. On a route
that costs zero, that entire failure mode has no value to be wrong about.

So the call that dominates the count is also the only one where the first
wiring cannot corrupt the spend audit. That is the whole argument for
starting here, and it is why this module does NOT touch
`decision-makers`, `email-verifier` or any other paid route.

## What stays serial

EVERY call still goes through `spend()`, which writes the waterfall ledger.
`spend()` is the DECIDE phase. It runs serially. The shared `Budget` cap,
the ledger append order, the `new_accounts_per_day` reservation lock, and
checkpoint ordering all stay serial - see section 7 of
`docs/PRODUCTION-HANDOFF-2026-09-18.md`. Two concurrent charges read the
same `spent` and both pass, so a 260-credit cap silently spends 262.

## Why ThreadPoolExecutor and not asyncio

The calls are I/O-bound HTTP against provider modules written as blocking
functions. asyncio would mean rewriting every provider module. Threads are
the right abstraction for wrapping existing blocking I/O.

## A TIMED-OUT CALL STILL REACHED THE PROVIDER, AND STILL COST A CREDIT

**FIXED (TASK-231).** The timeout is now enforced at the HTTP layer:
`src/providers._urllib_transport` passes `timeout` to
`urllib.request.urlopen`, which aborts the socket when the deadline
expires. `gather` no longer has its own `timeout` parameter - that was
the defect, two timeouts with the same name and different guarantees.

A callable that raises `TimeoutError` (including `HttpTimeout` from the
HTTP transport) is classified as `timed_out` in the Outcome. This proves
WE stopped waiting; it does NOT prove the SERVER stopped working. For a
GET that distinction costs nothing; for a paid POST it is the whole
question, and the report must state which of the two was achieved.

**That is why no paid route is wired into `gather` yet.** The people-count
call costs zero, so the honesty caveat has no value to be wrong about.
Wiring a paid route needs the idempotency contract from
`src/ratelimit.py` as a separate task.

## Rate limits: K is a ceiling, not a target

The enrichment providers that dominate the call count have UNKNOWN rate
limits, and EmailBison's 3,000 rpm is MARKETING, not in the API reference.
So `k` defaults to 4, the conservative recommendation. An optional
`min_interval` lets a caller throttle without changing `k`. There are no
retries: a 429 is a result the caller classifies, not something this
primitive hides.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class GatherIncomplete(RuntimeError):
    """The pool stopped accepting work. Carries the partial results.

    Raised rather than returned so a caller cannot mistake a truncated run
    for a complete one, and carrying `outcomes` so the work already done -
    which has already cost credits at a paid provider - is not thrown away.
    """

    def __init__(self, cause, outcomes):
        super().__init__(
            f"the pool stopped accepting work after "
            f"{sum(1 for o in outcomes if not o.is_not_attempted)} of "
            f"{len(outcomes)} items ({type(cause).__name__}: {cause})")
        self.cause = cause
        self.outcomes = outcomes


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
    min_interval: Optional[float] = None,
) -> List[Outcome]:
    """Execute `call` for each item with bounded concurrency.

    Returns exactly one Outcome per input item, in input order, regardless of
    completion order. The callable is executed exactly once per item. No
    retries, no shared mutable state, no state mutation of any kind.

    **Timeout enforcement lives at the HTTP layer**, not here. The transport
    in `src/providers/__init__.py` passes `timeout` to `urllib.request.urlopen`,
    which aborts the socket when the deadline expires. A callable that raises
    `TimeoutError` (including `HttpTimeout` from the transport) is classified
    as `timed_out`. There is no second, weaker timeout here with the same
    name and different guarantees - that was the defect.

    A `TimeoutError` from the callable proves WE stopped waiting. It does NOT
    prove the SERVER stopped working: for a paid POST the request may have
    been processed before the socket closed. See `HttpTimeout` in
    `src/providers/__init__.py`.

    Args:
        items: The inputs, processed in order.
        call: A callable taking one item and returning a result. It must not
              retry - a retry hidden inside the pool would double-spend at a
              paid provider. If the callable raises `TimeoutError` (including
              `HttpTimeout` from the HTTP transport), the outcome is
              `timed_out`; any other exception is `failed`.
        k: Maximum concurrent calls. Defaults to 4.
        min_interval: Minimum seconds between dispatches. None means no
                      throttling. K is still the concurrency ceiling.

    Returns:
        A list of Outcome, one per item, in input order.
    """
    if not items:
        return []

    outcomes: List[Outcome] = [Outcome.not_attempted()] * len(items)
    executor = ThreadPoolExecutor(max_workers=k)
    futures = [None] * len(items)

    try:
        last_submit = time.monotonic()
        submit_failure = None
        for i, item in enumerate(items):
            if min_interval is not None and i > 0:
                elapsed = time.monotonic() - last_submit
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
            last_submit = time.monotonic()
            try:
                futures[i] = executor.submit(call, item)
            except BaseException as exc:          # noqa: BLE001 - classified
                # THE POOL REFUSED TO TAKE MORE WORK - interpreter shutdown,
                # a thread that cannot be created, memory. Raising here would
                # discard every result already in flight: at item 3,000 of
                # 5,000 the caller would lose 2,999 completed calls that had
                # already cost credits. The remaining items stay
                # `not_attempted`, which is what that outcome is FOR, and the
                # ones that were submitted are still collected below.
                submit_failure = exc
                break

        for i, fut in enumerate(futures):
            if fut is None:
                continue                          # never submitted
            try:
                result = fut.result()
                outcomes[i] = Outcome.ok(result)
            except TimeoutError:
                # The callable raised TimeoutError (including HttpTimeout
                # from the HTTP transport). The request was ABORTED at the
                # socket layer. This is NOT the same as a future-level
                # timeout (which no longer exists here); it is the HTTP
                # layer's timeout firing, which is the enforcement point.
                outcomes[i] = Outcome.timed_out()
            except BaseException as exc:
                outcomes[i] = Outcome.failed(exc)
    finally:
        executor.shutdown(wait=False)

    if submit_failure is not None:
        # Reported, never swallowed. The caller gets its partial results AND
        # is told the pool stopped taking work, because "some items are
        # not_attempted" and "the pool died" are different situations and only
        # one of them is worth retrying.
        outcomes = list(outcomes)
        raise GatherIncomplete(submit_failure, outcomes)

    return outcomes


# Default K. Measured against live ContactOut on 2026-09-18:
#
#     K=1   2.10 req/s   p50 0.461s
#     K=4   8.19 req/s   p50 0.477s   3.89x
#     K=8  16.78 req/s   p50 0.454s   7.98x     <- here
#     K=12 17.29 req/s   p50 0.432s   8.23x     <- the knee
#
# K=12 buys 3% and raises max from 0.516s to 0.945s. Do not default higher.
DEFAULT_HEADCOUNT_K = 8


def prefetch_headcount(records, people_count, spend, k=DEFAULT_HEADCOUNT_K,
                       on_applied=None):
    """Prefetch `company_facts.headcount_signal` across records concurrently.

    THE FIRST CALLER of `gather`. The shape is decide-serially,
    fetch-concurrently, apply-serially IN INPUT ORDER:

        1. DECIDE   which records still need the call, serially, in record
                    order. No I/O. Records that already carry
                    `headcount_signal` are skipped - the same guard
                    `enrich_record` uses, so a prefetch and a serial run
                    make the same decisions.

        2. GATHER   call `people_count(domain=rec["domain"])` for each
                    chosen record, bounded at K. No decisions, no spending,
                    no state mutation - just round trips.

        3. APPLY    walk the results in INPUT ORDER. For each:
                      - ok:        call `spend` (which writes the waterfall
                                   step and charges the budget), then write
                                   `headcount_signal` onto the record.
                      - timed_out: treat as a provider failure; do not
                                   call `spend`, do not write; the record
                                   keeps its chance to buy the call in
                                   `enrich_record`.
                      - failed:    same as timed_out.

    The apply order is what keeps the waterfall ledger byte-identical to a
    serial run. `spend()` is the DECIDE phase and runs serially; the shared
    `Budget` cap is NOT made concurrent (two concurrent charges read the
    same `spent` and both pass, so a 260-credit cap silently spends 262).

    Timeout enforcement lives at the HTTP layer (`src/providers.TIMEOUT`),
    not here. A callable that raises `TimeoutError` (including `HttpTimeout`
    from the transport) produces a `timed_out` outcome.

    Args:
        records:       the records, in input order. Each must carry
                       `rec["domain"]` and `rec.get("company_facts")`.
        people_count:  callable taking `domain=` and returning a dict with
                       a `"profiles"` key. The free ContactOut call in
                       production; a fake in tests.
        spend:         callable accepting at least
                       `spend(call, why, provider="contactout")`. Returns
                       truthy on approval (and writes the waterfall step),
                       falsy on refusal. The record is passed as a keyword
                       argument `rec=rec` so a bridge that needs it can
                       accept it via `**kw`; a bridge that does not need
                       it ignores the keyword.
        k:             max concurrent calls. Defaults to 8.

    Returns:
        `{"attempted": N, "ok": N, "failed": N, "timed_out": N,
          "skipped_already_present": N, "skipped_budget_refused": N}`
    """
    # --- DECIDE: serially, in record order. No I/O. ---------------------
    need = []
    skipped_already = 0
    for rec in records:
        facts = rec.get("company_facts") or {}
        if "headcount_signal" in facts:
            skipped_already += 1
            continue
        need.append(rec)

    if not need:
        return {"attempted": 0, "ok": 0, "failed": 0, "timed_out": 0,
                "skipped_already_present": skipped_already,
                "skipped_budget_refused": 0}

    # --- GATHER: bounded concurrent I/O. No decisions, no mutation. -----
    outcomes = gather(
        need,
        lambda rec: people_count(domain=rec["domain"]),
        k=k,
    )

    # --- APPLY: serially, IN INPUT ORDER. -------------------------------
    # Input order is what keeps the waterfall byte-identical to a serial
    # run, and that is the acceptance test. The Budget cap stays in this
    # serial lane: `spend` is called once at a time, so two concurrent
    # charges cannot read the same `spent` and both pass.
    ok = failed = timed_out = budget_refused = 0
    for rec, outcome in zip(need, outcomes):
        if outcome.is_ok:
            # `spend` is the DECIDE phase. It runs serially, writes the
            # waterfall step, and only then is the prefetched value written
            # onto the record. A `spend` that returns falsy (cap reached)
            # leaves the record untouched so `enrich_record` can surface
            # the refusal through its own path.
            #
            # The record is passed as `rec=` so a bridge that needs it -
            # to charge the right budget key or write the right ledger -
            # can accept it via `**kw`. A bridge that does not need it
            # (the test fake, a pure budget gate) ignores the keyword and
            # keeps the simple `(call, why, provider)` signature.
            approved = spend(
                "people-count",
                "confirm the domain is staffed",
                "contactout",
                rec=rec,
            )
            if not approved:
                budget_refused += 1
                continue
            count = outcome.value or {}
            facts = dict(rec.get("company_facts") or {})
            facts["headcount_signal"] = count.get("profiles")
            rec["company_facts"] = facts
            # EVERY PROVIDER CALL IS LOGGED ON THE RECORD, AND A TEST
            # CAUGHT THIS BEING TRUE ONLY OF THE SERIAL PATH.
            #
            # `tests/test_enrich.py::test_every_provider_call_is_logged_on
            # _the_record` failed when the prefetch landed, because the
            # prefetched branch wrote `headcount_signal` and the serial
            # branch's `store.log(rec, "enrich", ...)` line then never
            # ran. Moving the call did not change what the record owes a
            # reader: a provider was asked about this company and the
            # record has to say so.
            #
            # The callback keeps `store` out of this primitive - the
            # caller already owns its own logging vocabulary - and it
            # runs HERE, inside the serial apply loop and in input order,
            # so the log lines land in the same order a serial pass
            # would have written them.
            if on_applied is not None:
                on_applied(rec, count)
            ok += 1
        elif outcome.is_timed_out:
            # A timed-out call still reached the provider and may yet
            # succeed there. On a paid route that is a ledger hole; on
            # people-count it costs zero and the record keeps its chance
            # to buy the call in `enrich_record`.
            timed_out += 1
        else:
            failed += 1
            # Per-record failure does not fail the pass. Append to the
            # record's `failures` list so `enrich_record`'s existing
            # failure-tracking picks it up.
            rec.setdefault("failures", []).append("people-count")

    return {"attempted": len(need), "ok": ok, "failed": failed,
            "timed_out": timed_out,
            "skipped_already_present": skipped_already,
            "skipped_budget_refused": budget_refused}
