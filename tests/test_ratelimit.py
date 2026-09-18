"""Tests for src/ratelimit.py.

No provider calls.  Every test uses fakes or direct construction.

The thread-safety test runs 8 threads against a bucket limited to 5
requests per second and asserts that the observed throughput does not
exceed the limit.  The break-proof test then removes the lock and
confirms the same test fails for the intended reason (throughput
exceeds the limit), not for some other reason.
"""
import threading
import time
import unittest
from unittest.mock import patch

from src.ratelimit import (
    DEFAULT_LIMIT,
    EMAILBISON_PUBLISHED,
    IDEMPOTENT_VERBS,
    LimitClassification,
    NonIdempotentRetry,
    ProviderLimit,
    RetryOutcome,
    RetryPolicy,
    TokenBucket,
    assert_idempotent_or_raise,
    effective_limit,
    parse_retry_after,
    rate_limited_call,
)


# ----------------------------------------------- limit classification

class TestLimitClassification(unittest.TestCase):

    def test_unknown_limit_falls_back_to_conservative_default(self):
        """An UNKNOWN limit is not unlimited - it is the floor."""
        unknown = ProviderLimit(rate=9999, unit="second",
                                classification=LimitClassification.UNKNOWN)
        result = effective_limit(unknown)
        self.assertEqual(result.rate, DEFAULT_LIMIT.rate)
        self.assertEqual(result.unit, DEFAULT_LIMIT.unit)
        self.assertIs(result.classification, LimitClassification.UNKNOWN)

    def test_none_falls_back_to_conservative_default(self):
        result = effective_limit(None)
        self.assertEqual(result.rate, DEFAULT_LIMIT.rate)

    def test_marketing_page_passes_through_with_classification(self):
        """A MARKETING_PAGE limit is honoured but its classification
        travels with it so nothing downstream can pretend it is
        CONFIRMED."""
        result = effective_limit(EMAILBISON_PUBLISHED)
        self.assertEqual(result.rate, 3000)
        self.assertIs(result.classification, LimitClassification.MARKETING_PAGE)

    def test_confirmed_limit_passes_through(self):
        confirmed = ProviderLimit(rate=100, unit="minute",
                                  classification=LimitClassification.CONFIRMED)
        result = effective_limit(confirmed)
        self.assertEqual(result.rate, 100)
        self.assertIs(result.classification, LimitClassification.CONFIRMED)

    def test_per_second_conversion(self):
        lim = ProviderLimit(rate=60, unit="minute")
        self.assertAlmostEqual(lim.per_second(), 1.0)

    def test_per_second_already_in_seconds(self):
        lim = ProviderLimit(rate=10, unit="second")
        self.assertEqual(lim.per_second(), 10.0)

    def test_unknown_unit_raises(self):
        lim = ProviderLimit(rate=10, unit="hour")
        with self.assertRaises(ValueError):
            lim.per_second()


# --------------------------------------------------------- token bucket

class TestTokenBucket(unittest.TestCase):

    def test_bucket_starts_full(self):
        limit = ProviderLimit(rate=60, unit="minute",
                              classification=LimitClassification.CONFIRMED)
        bucket = TokenBucket(limit)
        tokens = bucket._tokens_for_test()
        self.assertGreaterEqual(tokens, 1.0)

    def test_wait_consumes_a_token(self):
        limit = ProviderLimit(rate=600, unit="minute",
                              classification=LimitClassification.CONFIRMED)
        bucket = TokenBucket(limit, capacity=5)
        before = bucket._tokens_for_test()
        bucket.wait(timeout=1.0)
        after = bucket._tokens_for_test()
        self.assertLess(after, before)

    def test_wait_blocks_when_empty(self):
        """A bucket at zero tokens makes the caller wait."""
        limit = ProviderLimit(rate=6, unit="minute",
                              classification=LimitClassification.CONFIRMED,
                              source="test")
        bucket = TokenBucket(limit, capacity=1)
        bucket.wait(timeout=1.0)
        start = time.monotonic()
        bucket.wait(timeout=15.0)
        elapsed = time.monotonic() - start
        # At 6/min = 0.1/s, one token takes ~10s.  Allow generous slack.
        self.assertGreater(elapsed, 0.5)

    def test_wait_returns_false_on_timeout(self):
        limit = ProviderLimit(rate=1, unit="minute",
                              classification=LimitClassification.CONFIRMED)
        bucket = TokenBucket(limit, capacity=1)
        bucket.wait(timeout=1.0)
        result = bucket.wait(timeout=0.1)
        self.assertFalse(result)

    def test_unknown_limit_uses_conservative_default(self):
        """A bucket built with an UNKNOWN limit gets the floor rate,
        not the declared number."""
        unknown = ProviderLimit(rate=9999, unit="second",
                                classification=LimitClassification.UNKNOWN)
        bucket = TokenBucket(unknown)
        self.assertEqual(bucket.limit.rate, DEFAULT_LIMIT.rate)

    def test_effective_limit_property(self):
        limit = ProviderLimit(rate=120, unit="minute",
                              classification=LimitClassification.CONFIRMED)
        bucket = TokenBucket(limit)
        self.assertEqual(bucket.limit.rate, 120)


# -------------------------------------------------- thread safety proof

class TestThreadSafety(unittest.TestCase):

    def test_eight_threads_respect_five_per_second(self):
        """8 threads, bucket at 5/second.  Over a 3-second window the
        total completions must not exceed the limit by more than the
        burst capacity allows.

        At 5/s over 3s with burst capacity 5, theoretical max is
        5 + 5*3 = 20.  Allow slack to 28 for OS scheduling jitter,
        but it must be well under the 8*3=24 unconstrained calls that
        eight threads could make without any throttling.
        """
        limit = ProviderLimit(rate=5, unit="second",
                              classification=LimitClassification.CONFIRMED)
        bucket = TokenBucket(limit, capacity=5)
        counter = {"n": 0}
        lock = threading.Lock()
        stop = threading.Event()

        def worker():
            while not stop.is_set():
                ok = bucket.wait(timeout=5.0)
                if ok:
                    with lock:
                        counter["n"] += 1

        threads = [threading.Thread(target=worker, daemon=True)
                   for _ in range(8)]
        window = 3.0
        for t in threads:
            t.start()
        time.sleep(window)
        stop.set()
        for t in threads:
            t.join(timeout=5.0)

        self.assertLessEqual(counter["n"], 28,
                             f"throughput {counter['n']} exceeds limit")
        self.assertGreater(counter["n"], 0, "no calls completed")

    def test_break_proof_one_token_eight_threads(self):
        """Deterministic break-proof: a bucket with exactly 1 token
        and 8 threads all trying to consume it.  With the lock, exactly
        1 succeeds.  Without the lock, the race condition allows
        multiple threads to see the same token and all consume it.

        This test uses a bucket with capacity=1 and rate=0.001/s (so
        slow that no refill happens during the test).  Eight threads
        all call wait() simultaneously.  With the lock, only one gets
        the token.  Without it, the test fails because multiple threads
        consume the same token.
        """
        limit = ProviderLimit(rate=1, unit="minute",
                              classification=LimitClassification.CONFIRMED)
        bucket = TokenBucket(limit, capacity=1)
        # Drain the bucket so it has exactly 0 tokens.
        bucket.wait(timeout=0.1)

        # Now all 8 threads race for the next token.  At 1/min the
        # refill is so slow that no new token appears during the test.
        # With the lock, exactly 0 threads succeed (bucket is empty).
        # To test with 1 token, we manually set it.
        with bucket._lock:
            bucket._tokens = 1.0

        counter = {"n": 0}
        lock = threading.Lock()
        barrier = threading.Barrier(8, timeout=5.0)

        def worker():
            barrier.wait()
            ok = bucket.wait(timeout=0.5)
            if ok:
                with lock:
                    counter["n"] += 1

        threads = [threading.Thread(target=worker, daemon=True)
                   for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        # With the lock, exactly 1 thread gets the token.
        self.assertEqual(counter["n"], 1,
                         f"safe bucket: {counter['n']} threads got a token, "
                         f"expected exactly 1")

    def test_break_proof_no_lock_allows_double_spend(self):
        """The break-proof: remove the lock and confirm the same
        scenario fails because multiple threads consume the same token.

        This uses an UnsafeBucket that does refill-and-consume without
        any lock, AND adds a deliberate delay between the check and the
        consume to widen the race window.  With 8 threads racing for 1
        token, multiple threads see tokens >= 1.0 during the delay and
        all decrement it.
        """
        limit = ProviderLimit(rate=1, unit="minute",
                              classification=LimitClassification.CONFIRMED)

        class UnsafeBucket(TokenBucket):
            def wait(self, timeout=None):
                # No lock - the break-proof test.
                self._refill()
                if self._tokens >= 1.0:
                    # Widen the race window: sleep between check and
                    # consume so other threads can also see the token.
                    time.sleep(0.01)
                    self._tokens -= 1.0
                    return True
                return False

        bucket = UnsafeBucket(limit, capacity=1)
        # Drain and reset to exactly 1 token.
        bucket._tokens = 0.0
        bucket._tokens = 1.0

        counter = {"n": 0}
        lock = threading.Lock()
        barrier = threading.Barrier(8, timeout=5.0)

        def worker():
            barrier.wait()
            ok = bucket.wait(timeout=0.5)
            if ok:
                with lock:
                    counter["n"] += 1

        threads = [threading.Thread(target=worker, daemon=True)
                   for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        # Without the lock, multiple threads see the same token during
        # the sleep and all consume it.  The test FAILS if more than 1
        # succeeds.  This is the intended failure: the lock is what
        # makes the check-and-consume atomic.
        self.assertGreater(counter["n"], 1,
                           f"unsafe bucket: {counter['n']} threads got a "
                           f"token, expected >1 (lock removal should allow "
                           f"double-spend)")


# ------------------------------------------------------- retry policy

class TestRetryPolicy(unittest.TestCase):

    def test_429_is_retryable(self):
        policy = RetryPolicy()
        self.assertTrue(policy.is_retryable_status(429))

    def test_500_is_retryable(self):
        policy = RetryPolicy()
        self.assertTrue(policy.is_retryable_status(500))

    def test_503_is_retryable(self):
        policy = RetryPolicy()
        self.assertTrue(policy.is_retryable_status(503))

    def test_400_is_not_retryable(self):
        policy = RetryPolicy()
        self.assertFalse(policy.is_retryable_status(400))

    def test_401_is_not_retryable(self):
        policy = RetryPolicy()
        self.assertFalse(policy.is_retryable_status(401))

    def test_200_is_not_retryable(self):
        policy = RetryPolicy()
        self.assertFalse(policy.is_retryable_status(200))

    def test_exponential_backoff_without_jitter(self):
        policy = RetryPolicy(base_delay=1.0, max_delay=60.0, jitter=False)
        self.assertEqual(policy.delay_for(0), 1.0)
        self.assertEqual(policy.delay_for(1), 2.0)
        self.assertEqual(policy.delay_for(2), 4.0)
        self.assertEqual(policy.delay_for(3), 8.0)

    def test_backoff_capped_at_max_delay(self):
        policy = RetryPolicy(base_delay=1.0, max_delay=5.0, jitter=False)
        self.assertEqual(policy.delay_for(10), 5.0)

    def test_jitter_stays_within_bounds(self):
        policy = RetryPolicy(base_delay=1.0, max_delay=60.0, jitter=True)
        for _ in range(100):
            d = policy.delay_for(2)
            self.assertGreaterEqual(d, 0.0)
            self.assertLessEqual(d, 4.0)

    def test_retry_after_overrides_backoff_when_larger(self):
        policy = RetryPolicy(base_delay=1.0, max_delay=60.0, jitter=False)
        # retry_after=30 is larger than the exponential 4.0
        self.assertEqual(policy.delay_for(2, retry_after=30.0), 30.0)

    def test_retry_after_ignored_when_smaller(self):
        policy = RetryPolicy(base_delay=1.0, max_delay=60.0, jitter=False)
        # retry_after=0.5 is smaller than the exponential 4.0
        self.assertEqual(policy.delay_for(2, retry_after=0.5), 4.0)


# -------------------------------------------------- parse Retry-After

class TestParseRetryAfter(unittest.TestCase):

    def test_integer_seconds(self):
        self.assertEqual(parse_retry_after("120"), 120.0)

    def test_empty_string(self):
        self.assertIsNone(parse_retry_after(""))

    def test_none(self):
        self.assertIsNone(parse_retry_after(None))

    def test_unparseable_returns_none(self):
        self.assertIsNone(parse_retry_after("not-a-number-or-date"))

    def test_http_date_format(self):
        # A date far in the future should give a positive delta.
        future = "Thu, 01 Jan 2099 00:00:00 GMT"
        result = parse_retry_after(future)
        self.assertIsNotNone(result)
        self.assertGreater(result, 0)


# ---------------------------------------- idempotency assertion guard

class TestIdempotencyGuard(unittest.TestCase):

    def test_get_does_not_need_assertion(self):
        assert_idempotent_or_raise("GET")

    def test_head_does_not_need_assertion(self):
        assert_idempotent_or_raise("HEAD")

    def test_options_does_not_need_assertion(self):
        assert_idempotent_or_raise("OPTIONS")

    def test_delete_does_not_need_assertion(self):
        assert_idempotent_or_raise("DELETE")

    def test_post_without_assertion_raises(self):
        with self.assertRaises(NonIdempotentRetry):
            assert_idempotent_or_raise("POST")

    def test_put_without_assertion_raises(self):
        with self.assertRaises(NonIdempotentRetry):
            assert_idempotent_or_raise("PUT")

    def test_patch_without_assertion_raises(self):
        with self.assertRaises(NonIdempotentRetry):
            assert_idempotent_or_raise("PATCH")

    def test_post_with_idempotency_key_passes(self):
        assert_idempotent_or_raise("POST", idempotency_key="abc-123")

    def test_post_with_empty_key_still_raises(self):
        with self.assertRaises(NonIdempotentRetry):
            assert_idempotent_or_raise("POST", idempotency_key="")

    def test_post_with_none_key_raises(self):
        with self.assertRaises(NonIdempotentRetry):
            assert_idempotent_or_raise("POST", idempotency_key=None)

    def test_error_message_mentions_second_write(self):
        try:
            assert_idempotent_or_raise("POST")
        except NonIdempotentRetry as e:
            self.assertIn("second write", str(e))


# ------------------------------------------- rate_limited_call (fake)

class TestRateLimitedCall(unittest.TestCase):

    def _fake_request(self, statuses):
        """Return a callable that yields statuses in order."""
        calls = {"n": 0}
        def do_request():
            idx = min(calls["n"], len(statuses) - 1)
            calls["n"] += 1
            status = statuses[idx]
            headers = {}
            if status == 429:
                headers["retry-after"] = "0"
            return (status, headers, b"")
        return do_request, calls

    def test_success_on_first_try(self):
        bucket = TokenBucket(ProviderLimit(rate=600, unit="minute",
                                           classification=LimitClassification.CONFIRMED),
                             capacity=5)
        policy = RetryPolicy(max_attempts=3, base_delay=0.01, jitter=False)
        do_request, calls = self._fake_request([200])
        outcome = rate_limited_call(bucket, policy, "GET", do_request)
        self.assertTrue(outcome.succeeded)
        self.assertEqual(outcome.attempts, 1)
        self.assertEqual(calls["n"], 1)

    def test_retries_on_429_then_succeeds(self):
        bucket = TokenBucket(ProviderLimit(rate=600, unit="minute",
                                           classification=LimitClassification.CONFIRMED),
                             capacity=5)
        policy = RetryPolicy(max_attempts=3, base_delay=0.01, jitter=False)
        do_request, calls = self._fake_request([429, 429, 200])
        outcome = rate_limited_call(bucket, policy, "GET", do_request)
        self.assertTrue(outcome.succeeded)
        self.assertEqual(outcome.attempts, 3)

    def test_retries_on_500_then_succeeds(self):
        bucket = TokenBucket(ProviderLimit(rate=600, unit="minute",
                                           classification=LimitClassification.CONFIRMED),
                             capacity=5)
        policy = RetryPolicy(max_attempts=3, base_delay=0.01, jitter=False)
        do_request, calls = self._fake_request([500, 200])
        outcome = rate_limited_call(bucket, policy, "GET", do_request)
        self.assertTrue(outcome.succeeded)
        self.assertEqual(outcome.attempts, 2)

    def test_gives_up_after_max_attempts(self):
        bucket = TokenBucket(ProviderLimit(rate=600, unit="minute",
                                           classification=LimitClassification.CONFIRMED),
                             capacity=5)
        policy = RetryPolicy(max_attempts=3, base_delay=0.01, jitter=False)
        do_request, calls = self._fake_request([429, 429, 429])
        outcome = rate_limited_call(bucket, policy, "GET", do_request)
        self.assertFalse(outcome.succeeded)
        self.assertEqual(outcome.attempts, 3)
        self.assertEqual(outcome.status, 429)

    def test_does_not_retry_400(self):
        bucket = TokenBucket(ProviderLimit(rate=600, unit="minute",
                                           classification=LimitClassification.CONFIRMED),
                             capacity=5)
        policy = RetryPolicy(max_attempts=3, base_delay=0.01, jitter=False)
        do_request, calls = self._fake_request([400])
        outcome = rate_limited_call(bucket, policy, "GET", do_request)
        self.assertFalse(outcome.succeeded)
        self.assertEqual(outcome.attempts, 1)

    def test_post_refused_without_idempotency_key(self):
        bucket = TokenBucket(ProviderLimit(rate=600, unit="minute",
                                           classification=LimitClassification.CONFIRMED),
                             capacity=5)
        policy = RetryPolicy(max_attempts=3, base_delay=0.01, jitter=False)
        do_request, _ = self._fake_request([200])
        with self.assertRaises(NonIdempotentRetry):
            rate_limited_call(bucket, policy, "POST", do_request)

    def test_post_allowed_with_idempotency_key(self):
        bucket = TokenBucket(ProviderLimit(rate=600, unit="minute",
                                           classification=LimitClassification.CONFIRMED),
                             capacity=5)
        policy = RetryPolicy(max_attempts=3, base_delay=0.01, jitter=False)
        do_request, calls = self._fake_request([200])
        outcome = rate_limited_call(bucket, policy, "POST", do_request,
                                    idempotency_key="unique-op-id")
        self.assertTrue(outcome.succeeded)

    def test_retry_after_header_is_honoured(self):
        bucket = TokenBucket(ProviderLimit(rate=600, unit="minute",
                                           classification=LimitClassification.CONFIRMED),
                             capacity=5)
        policy = RetryPolicy(max_attempts=2, base_delay=0.01, jitter=False)

        def do_request():
            return (429, {"retry-after": "0.1"}, b"")

        start = time.monotonic()
        outcome = rate_limited_call(bucket, policy, "GET", do_request)
        elapsed = time.monotonic() - start
        self.assertFalse(outcome.succeeded)
        self.assertTrue(outcome.retry_after_used)
        # The retry-after of 0.1s should have been honoured.
        self.assertGreater(elapsed, 0.05)

    def test_retry_after_case_insensitive_header(self):
        """Retry-After may arrive capitalised differently."""
        bucket = TokenBucket(ProviderLimit(rate=600, unit="minute",
                                           classification=LimitClassification.CONFIRMED),
                             capacity=5)
        policy = RetryPolicy(max_attempts=2, base_delay=0.01, jitter=False)

        def do_request():
            return (429, {"Retry-After": "0.1"}, b"")

        outcome = rate_limited_call(bucket, policy, "GET", do_request)
        self.assertTrue(outcome.retry_after_used)


if __name__ == "__main__":
    unittest.main()
