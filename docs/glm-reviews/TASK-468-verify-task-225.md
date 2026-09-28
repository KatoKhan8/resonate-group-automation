# TASK-468 — Independent Verification of TASK-225

## Review metadata

| Field | Value |
|-------|-------|
| Target task | TASK-225 |
| Target branch | origin/qwen-worker-7-r28 |
| Branch HEAD SHA | `b80d3631532b831a64e10bfa3459c1734b7634e1` |
| SHA verified by | `git rev-parse FETCH_HEAD` → `b80d3631532b831a64e10bfa3459c1734b7634e1` ✓ |
| Merge base with master | `bd940e58c660c6465fde9a1c19fc9345c8c9985c` |
| Review worktree | `.qwen/worktrees/glm-468` (detached at target SHA, now removed) |
| Review date | 2026-09-28 |
| Reviewer | Qwen (independent GLM verdict) |

Note: the task file names the output `TASK-468-verify-task-219.md` — this is a typo in the dispatch file; the target is TASK-225.

---

## 1. Does the artifact exist, and does it do what the result block claims?

**VERDICT: Artifacts exist. Claims are accurate within scope.**

Three files changed on the branch vs master:

```
docs/qwen-tasks/DONE/TASK-225-a-rate-limiter-the-gather-can-be-given.md  (NEW)
src/ratelimit.py                                                          (NEW, 324 lines)
tests/test_ratelimit.py                                                   (NEW, 530 lines)
```

The result block claims:
- **52/52 tests pass** → VERIFIED. `python -m unittest tests.test_ratelimit -v` → `Ran 52 tests in 15.499s OK`
- **80/80 test_invariants pass** → PARTIALLY VERIFIED. 79/80 pass; the one failure (`test_nothing_was_written_by_that`) is environmental — it expects `work/` to exist, which it does not in a detached worktree. This test passes on the main worktree. NOT caused by TASK-225.
- **UNKNOWN limits fall back to DEFAULT_LIMIT (5/min)** → VERIFIED by code inspection and `test_unknown_limit_falls_back_to_conservative_default`.
- **EmailBison 3000rpm classified as MARKETING_PAGE** → VERIFIED at `src/ratelimit.py:58-62`.
- **POST/PUT/PATCH refused without idempotency_key** → VERIFIED. `assert_idempotent_or_raise()` raises `NonIdempotentRetry` with "second write" in the message.
- **Thread safety: 8 threads vs 5/s** → VERIFIED by `test_eight_threads_respect_five_per_second`.
- **Break-proof** → VERIFIED with caveat (see Finding 3 below).
- **Retry-After parsed (integer and HTTP-date)** → VERIFIED by `TestParseRetryAfter`.

---

## 2. Existence is not function — production callers

**VERDICT: ZERO PRODUCTION CALLERS. DISCONNECTED.**

```
git grep -n "ratelimit\|TokenBucket\|RetryPolicy\|rate_limited_call" FETCH_HEAD -- src/ | grep -v "src/ratelimit.py"
→ (empty)

git grep -n "from src.ratelimit\|import src.ratelimit" FETCH_HEAD -- src/ tests/ | grep -v "test_ratelimit.py"
→ (empty)
```

No module in `src/` imports or references anything from `src/ratelimit.py`. The only consumer is `tests/test_ratelimit.py`, which tests the module in isolation.

The task file's FILES FORBIDDEN section explicitly excluded `src/gather.py`, `src/enrich.py`, and any provider module. The result block acknowledges: "No wiring to gather.py or any provider module (per task instructions). Claude must wire the bucket into the gather loop."

This is honest and the task scope was deliberate. But the protocol is unambiguous: **zero production callers = DISCONNECTED = rework, not merge.** The module is correct code that nothing downstream reads — the exact recurring defect this repository has been bitten by.

Additionally, `src/gather.py` does not exist on this branch (it was added to master after the merge base at `bd940e58`). The wiring target the task names is absent from the branch entirely.

---

## 3. Falsification of the result's own claims

### 3a. Break-proof: lock removal

The result claims: "Unsafe bucket (no lock, widened race window) allows >1 to succeed."

**My independent falsification attempt:** I replaced `TokenBucket._lock` with a no-op context manager (removing the lock without adding the deliberate `time.sleep(0.01)` between check and consume). With 8 threads racing for 1 token, only 1 succeeded.

**Why:** CPython's GIL serialises the check-and-consume when there is no I/O or sleep between them. The `if self._tokens >= 1.0: self._tokens -= 1.0` sequence runs atomically under the GIL.

**The branch's UnsafeBucket test** adds `time.sleep(0.01)` between check and consume, which releases the GIL and widens the race window. With this artificial widening, >1 thread succeeds. This is a valid demonstration that the lock matters, but it proves a weaker claim than stated: it proves the lock matters *when there is a sleep between check and consume*, not that the lock matters in general under CPython.

**Assessment:** The break-proof is directionally correct — the lock DOES protect against real concurrency issues (non-CPython runtimes, future code changes, memory visibility). But the test as written demonstrates an artificial scenario. A stronger break-proof would use `ctypes.pythonapi.PyThreadState_SetAsyncExc` or `sys.setswitchinterval(0)` to force thread switches without explicit sleeps. This is a test quality concern, not a code defect — the production code's lock is correct.

### 3b. Idempotency guard

The result claims "POST/PUT/PATCH refused on retry without explicit idempotency_key." The code actually refuses BEFORE the first attempt, not just on retry. `rate_limited_call` calls `assert_idempotent_or_raise(method, idempotency_key)` before entering the attempt loop. This is stricter than the claim — it refuses non-idempotent calls entirely without a key, not just retries. This is a safer design choice.

### 3c. UNKNOWN limit fallback

VERIFIED. `effective_limit()` returns `DEFAULT_LIMIT` for both `None` and `LimitClassification.UNKNOWN`. A `ProviderLimit(rate=9999, unit="second", classification=UNKNOWN)` is correctly replaced by the 5/min floor.

---

## 4. Are the tests falsifiable?

**VERDICT: Mostly yes, with one caveat.**

**Strong tests:**
- `test_unknown_limit_falls_back_to_conservative_default` — asserts on behaviour (the returned limit's rate), not source text. ✓
- `test_post_without_assertion_raises` — asserts on raised exception. ✓
- `test_retries_on_429_then_succeeds` — drives through `rate_limited_call`, the real entry point. ✓
- `test_eight_threads_respect_five_per_second` — measures throughput, not source. ✓

**Caveat — break-proof test:**
- `test_break_proof_no_lock_allows_double_spend` uses an `UnsafeBucket` subclass with a deliberate `time.sleep(0.01)`. This is a valid negative control but the race window is artificial. On a fast machine without the sleep, the GIL would serialize the check-and-consume. The test passes because of the sleep, not purely because of lock absence.
- A test that could pass while the implementation is wrong: if someone removed the lock AND the sleep from `UnsafeBucket.wait()`, the test would fail (asserting `>1` but getting `1`). This is the correct direction — the test fails when the vulnerability is removed — but the mechanism is the sleep, not the lock absence alone.

**Not-a-concern tests:**
- No `hasattr` checks.
- No assertions on source text.
- No fake cassettes returning fake data — the fakes are callables returning status codes, which is appropriate for a module that takes a `do_request` callable.

---

## 5. Would merging delete anything?

**VERDICT: No. Purely additive.**

```
git diff master...FETCH_HEAD --shortstat
→ 3 files changed, 914 insertions(+), 0 deletions(-)
```

All three files are NEW. No existing files are modified. Merging would add 914 lines and delete nothing.

---

## 6. Scope drift

**VERDICT: No scope drift.**

The branch carries exactly three files beyond master: the task file, `src/ratelimit.py`, and `tests/test_ratelimit.py`. No unrelated changes, no junk, no configuration modifications. Cherry-picking would be trivial — in fact, the entire diff is clean enough to merge without cherry-pick.

---

## Findings

### Finding 1 — DISCONNECTED: zero production callers [CRITICAL]

- **Severity:** Critical
- **Evidence:** `git grep` for `ratelimit|TokenBucket|RetryPolicy|rate_limited_call` in `src/` (excluding `src/ratelimit.py`) returns zero hits. No import, no reference, no caller.
- **Failure scenario:** Merging this branch adds a correct, well-tested module that nothing uses. The wiring step the result block recommends is the entire point of the module. Without it, the rate limiter is dead code — the exact "existence is not function" defect this repository's review protocol exists to catch.
- **Category:** correctness/wiring
- **Context:** The task scope deliberately excluded wiring (FILES FORBIDDEN). The result block honestly discloses this. The protocol nonetheless requires production callers for merge.

### Finding 2 — test_invariants claim slightly overstated [LOW]

- **Severity:** Low
- **Evidence:** Result block claims "80/80 pass in tests.test_invariants". In a detached worktree (the review environment), 79/80 pass — one test fails because `work/` does not exist. This is environmental, not a code defect. The test passes on the main worktree.
- **Failure scenario:** A reviewer running tests in a clean checkout might see 79/80 and flag it. The result block's "80/80" claim is accurate only in an environment where `work/` already exists.
- **Category:** test-coverage/accuracy

### Finding 3 — Break-proof demonstrates artificial scenario [LOW]

- **Severity:** Low
- **Evidence:** The `UnsafeBucket` in `test_break_proof_no_lock_allows_double_spend` adds `time.sleep(0.01)` between check and consume. Without this sleep, CPython's GIL serializes the check-and-consume even without the lock (verified: my independent mutation with a no-op lock got `counter["n"] == 1`, not `>1`).
- **Failure scenario:** The test proves the lock matters when there is a sleep between check and consume, which is an artificial scenario. The lock IS correct and necessary (for non-CPython runtimes, future code changes, and memory visibility), but the test does not demonstrate this directly.
- **Category:** test-quality

---

## Disposition

| Finding | Disposition |
|---------|-------------|
| 1. Zero production callers | DISCONNECTED — rework required |
| 2. test_invariants claim | FALSE POSITIVE — environmental, not a defect |
| 3. Break-proof scenario | ACCEPTED DEFERRED RISK — code is correct, test is weaker than stated |

---

## Recommendation: **REWORK**

**Reason:** The module is well-written, the tests are mostly sound, and the code is merge-safe (purely additive). But it has zero production callers — nothing in `src/` imports or uses `ratelimit.py`. The protocol is explicit: "Zero production callers means DISCONNECTED, which is a rework and not a merge."

The task scope deliberately excluded wiring, and the result block honestly discloses this. The wiring is the recommended Claude action. Until `gather.py` (or another production entry point) consumes the `TokenBucket`, the module is correct code that nothing reads — the recurring defect.

**What rework looks like:** Wire `TokenBucket` into `src/gather.py`'s provider call loop (as the result block recommends), with each provider getting its own bucket constructed from its declared limit. Then re-verify with the production caller in place. The code in `src/ratelimit.py` itself does not need to change.

**What does NOT need rework:** The module code, the limit classification design, the idempotency guard, the retry policy, and the majority of the tests. These are solid.

---

## Commands reproduced

```bash
# Verify SHA
git rev-parse FETCH_HEAD
# → b80d3631532b831a64e10bfa3459c1734b7634e1

# Run ratelimit tests
cd .qwen/worktrees/glm-468 && python -m unittest tests.test_ratelimit -v
# → Ran 52 tests in 15.499s OK

# Run invariants
cd .qwen/worktrees/glm-468 && python -m unittest tests.test_invariants -v
# → Ran 80 tests, FAILED (errors=1) — environmental, work/ missing

# Check for production callers
git grep -n "ratelimit\|TokenBucket\|RetryPolicy\|rate_limited_call" FETCH_HEAD -- src/ | grep -v "src/ratelimit.py"
# → (empty)

# Check merge safety
git diff master...FETCH_HEAD --shortstat
# → 3 files changed, 914 insertions(+), 0 deletions(-)

# Break-proof mutation (lock replaced with no-op, no sleep added)
# → counter["n"] == 1 (falsification of the break-proof claim did NOT succeed)
```
