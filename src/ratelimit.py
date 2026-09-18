"""Thread-safe token-bucket rate limiter with retry policy.

Two invariants outrank everything else in this module:

1. An UNKNOWN provider limit falls back to the conservative configured
   default and is NEVER treated as unlimited.  Most enrichment providers
   in this repository have UNKNOWN limits, and EmailBison's 3000 rpm is a
   marketing page, not an API reference.  Every limit carries a
   classification that says where the number came from, and a limit whose
   classification is UNKNOWN uses the conservative floor.

2. A retried POST is a second write.  The retry path REFUSES to retry a
   non-idempotent HTTP verb unless the caller passes an explicit
   idempotency assertion.  GET and HEAD are safe by convention; everything
   else needs the caller to say so.

No provider calls live here.  Tests use fakes.
"""
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ------------------------------------------------------------------ limits

class LimitClassification(Enum):
    """Where the number came from.  UNKNOWN is the common case and the
    dangerous one: a limit nobody classified is not unlimited, it is
    the conservative floor."""
    CONFIRMED = "confirmed"
    MARKETING_PAGE = "marketing_page"
    #: A rate THIS SYSTEM has actually sustained, with the date it sustained
    #: it on. Added 2026-09-18, and it is not a softening of UNKNOWN - it is
    #: the only classification this estate has real evidence for.
    #:
    #: The UNKNOWN floor is 5/minute, on the sound reasoning that no
    #: documented provider limit is below it. Sound, and wrong here by a
    #: factor that is now measured: ContactOut `people-count` sustained
    #: 1,038/minute across K=1,4,8,12 with zero 429s, and it is 4,822 of the
    #: 8,760 provider calls in a 5,000-record pass. At 5/minute those calls
    #: alone take 16 HOURS against the ~37 minutes they take serially today.
    #: A limiter that makes the system 28x slower is an outage wearing a
    #: safety feature's clothes.
    #:
    #: OBSERVED is weaker than CONFIRMED on purpose. An unpublished limit can
    #: be changed without telling anybody, so it carries its date and it is
    #: evidence about one moment. `docs/PERF-CONCURRENCY-MEASURED-2026-09-18.md`
    OBSERVED = "observed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderLimit:
    """A rate limit with its provenance.

    `rate` is always expressed per `unit` (seconds or minutes).  The
    classification says whether the number is from an API response, a
    marketing page, or unknown.  A caller that constructs a ProviderLimit
    without thinking about the classification gets UNKNOWN, which means
    the conservative floor, not the number they wrote.
    """
    rate: int
    unit: str = "minute"
    classification: LimitClassification = LimitClassification.UNKNOWN
    source: str = ""

    def per_second(self) -> float:
        if self.unit == "second":
            return float(self.rate)
        if self.unit == "minute":
            return self.rate / 60.0
        raise ValueError(f"unknown time unit: {self.unit!r}")


# The conservative floor.  Five requests per minute is slow enough that
# no documented provider limit is below it, and fast enough that a batch
# does not stall forever.  An UNKNOWN limit uses this, not the number
# somebody guessed.
DEFAULT_LIMIT = ProviderLimit(
    rate=5,
    unit="minute",
    classification=LimitClassification.UNKNOWN,
    source="conservative default for unclassified limits",
)

# EmailBison's published number, classified honestly.  A marketing page
# is not an API reference, so this is MARKETING_PAGE, not CONFIRMED, and
# any caller that would use it for throttling has to acknowledge that.
# MEASURED 2026-09-18 and classified as what it is. Operate this route at
# K=8: scaling is 7.98x there and 8.23x at K=12, so the last four threads buy
# 3% and raise `max` from 0.516s to 0.945s. The knee is OURS - throughput
# flattens while the provider answers every request and never throttles -
# which is a local ceiling, not a server-side one.
CONTACTOUT_PEOPLE_COUNT = ProviderLimit(
    rate=1038,
    unit="minute",
    classification=LimitClassification.OBSERVED,
    source=("sustained at K=12 with zero 429s on 2026-09-18; "
            "docs/PERF-CONCURRENCY-MEASURED-2026-09-18.md"),
)

EMAILBISON_PUBLISHED = ProviderLimit(
    rate=3000,
    unit="minute",
    classification=LimitClassification.MARKETING_PAGE,
    source="EmailBison marketing page, not an API reference",
)


def effective_limit(declared: Optional[ProviderLimit]) -> ProviderLimit:
    """Return the limit to actually enforce.

    None means the caller did not declare anything - use the floor.
    A declared limit whose classification is UNKNOWN also uses the floor,
    because an unclassified number is not a limit, it is a guess.
    A MARKETING_PAGE limit is returned as-is but the classification
    travels with it so nothing downstream can pretend it is CONFIRMED.
    """
    if declared is None:
        return DEFAULT_LIMIT
    if declared.classification is LimitClassification.UNKNOWN:
        return DEFAULT_LIMIT
    return declared


# --------------------------------------------------------------- token bucket

class TokenBucket:
    """Thread-safe token bucket.

    Tokens refill at a steady rate up to the bucket capacity.  `wait()`
    blocks until a token is available, then consumes it.  The lock is
    held for the entire check-and-consume so two threads cannot both see
    a full bucket and both take a token.
    """

    def __init__(self, limit: ProviderLimit, capacity: Optional[int] = None):
        resolved = effective_limit(limit)
        self._rate_per_second = resolved.per_second()
        self._capacity = capacity if capacity is not None else max(1, int(self._rate_per_second))
        self._tokens = float(self._capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()
        self._limit = resolved

    @property
    def limit(self) -> ProviderLimit:
        return self._limit

    @property
    def capacity(self) -> int:
        return self._capacity

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            float(self._capacity),
            self._tokens + elapsed * self._rate_per_second,
        )
        self._last_refill = now

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Block until a token is available.  Returns True on success,
        False if the timeout expired before a token was available.

        The lock is held only for the check-and-consume, not during the
        sleep, so one slow thread does not block all the others from
        seeing a refill.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                # How long until one token is available?
                deficit = 1.0 - self._tokens
                wait_time = deficit / self._rate_per_second
            # Sleep outside the lock so other threads can refill too.
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                wait_time = min(wait_time, remaining)
            time.sleep(wait_time)

    def _tokens_for_test(self) -> float:
        """Read the current token count under the lock.  Test use only."""
        with self._lock:
            self._refill()
            return self._tokens


# ----------------------------------------------------------- retry policy

IDEMPOTENT_VERBS = frozenset({"GET", "HEAD", "OPTIONS", "DELETE"})


class NonIdempotentRetry(RuntimeError):
    """Raised when a retry is attempted on a non-idempotent verb without
    an explicit idempotency assertion from the caller."""


@dataclass
class RetryPolicy:
    """Exponential backoff with jitter on 429 and 5xx, honouring
    Retry-After.

    `max_attempts` is the total number of tries, including the first.
    `base_delay` and `max_delay` bound the exponential curve.  Jitter is
    uniform random in [0, delay) so that concurrent callers do not
    thundering-herd.
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True

    def is_retryable_status(self, status: int) -> bool:
        return status == 429 or status >= 500

    def delay_for(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Compute the delay before attempt `attempt` (0-indexed from the
        first retry, so attempt=0 is the delay before the second try).

        If `retry_after` is given (seconds, parsed from a Retry-After
        header), it is honoured as a floor: the backoff never sleeps for
        less than the server asked for.
        """
        exponential = self.base_delay * (2 ** attempt)
        capped = min(exponential, self.max_delay)
        if self.jitter:
            capped = random.uniform(0, capped)
        if retry_after is not None and retry_after > capped:
            return retry_after
        return capped


def parse_retry_after(value: str) -> Optional[float]:
    """Parse a Retry-After header value.

    Accepts an integer (seconds) or an HTTP-date.  Returns seconds as a
    float, or None if the value is unparseable.  An unparseable
    Retry-After is ignored, not raised: a bad header must not stop the
    retry path.
    """
    if not value:
        return None
    value = value.strip()
    try:
        return float(value)
    except ValueError:
        pass
    # HTTP-date: Fri, 31 Dec 1999 23:59:59 GMT
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %Z",
        "%A, %d-%b-%y %H:%M:%S %Z",
        "%a %b %d %H:%M:%S %Y",
    ):
        try:
            parsed = time.strptime(value, fmt)
            target = time.mktime(parsed)
            delta = target - time.time()
            return max(0.0, delta)
        except (ValueError, OverflowError):
            continue
    return None


def assert_idempotent_or_raise(method: str, idempotency_key: Optional[str] = None):
    """Refuse to sanction a retry on a non-idempotent verb unless the
    caller passed an explicit idempotency assertion.

    `idempotency_key` is any non-None, non-empty value the caller
    provides to assert that the request is safe to repeat.  The key's
    content is not validated here - the assertion is that the caller
    has thought about it.
    """
    if method.upper() in IDEMPOTENT_VERBS:
        return
    if idempotency_key:
        return
    raise NonIdempotentRetry(
        f"refusing to retry {method} without an idempotency assertion. "
        f"A retried POST is a second write.  Pass idempotency_key= to "
        f"assert the request is safe to repeat."
    )


# -------------------------------------------------------- high-level entry

@dataclass
class RetryOutcome:
    """What happened across all attempts."""
    status: Optional[int] = None
    attempts: int = 0
    succeeded: bool = False
    retry_after_used: bool = False


def rate_limited_call(
    bucket: TokenBucket,
    policy: RetryPolicy,
    method: str,
    do_request: callable,
    idempotency_key: Optional[str] = None,
):
    """Make a rate-limited, retry-aware request.

    `bucket` is waited on before each attempt.
    `policy` governs retries on 429 and 5xx.
    `method` is the HTTP verb; non-idempotent verbs require
    `idempotency_key`.
    `do_request` is a callable that performs the actual HTTP call and
    returns (status_code, headers_dict, body).  headers_dict must
    include "retry-after" if the server sent one.

    Returns a RetryOutcome.

    No provider calls live here.  The caller supplies `do_request`.
    """
    assert_idempotent_or_raise(method, idempotency_key)

    outcome = RetryOutcome()
    for attempt in range(policy.max_attempts):
        bucket.wait()
        status, headers, body = do_request()
        outcome.attempts = attempt + 1
        outcome.status = status

        if 200 <= status < 300:
            outcome.succeeded = True
            return outcome

        if not policy.is_retryable_status(status):
            return outcome

        is_last = attempt == policy.max_attempts - 1
        if is_last:
            return outcome

        retry_after_raw = (headers or {}).get("retry-after") or (headers or {}).get("Retry-After")
        retry_after = parse_retry_after(retry_after_raw) if retry_after_raw else None
        if retry_after is not None:
            outcome.retry_after_used = True
        delay = policy.delay_for(attempt, retry_after)
        time.sleep(delay)

    return outcome
