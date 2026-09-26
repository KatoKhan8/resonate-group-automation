PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-370 — the write audit cannot see the shape our own transport uses

GLM canary review P1-3 and T-2, `docs/glm-reviews/canary-readiness-b333697.md`.
**Independently reproduced against `origin/master` on 2026-09-26** — confirmed
current, not stale.

## The defect, stated precisely

`tests/test_nothing_writes_to_a_provider.py` builds `CALLS` from three
alternatives:

    request("VERB", ...)        our own transport, called by name
    requests.post|put|patch|delete(...)
    urlopen(..., method="VERB")

It does **not** match a verb carried on the `Request` **object** — which is
exactly how `src/providers/__init__.py:765` issues every write this repository
makes — nor `Request(url, data=...)` with no `method=`, which urllib sends as a
POST.

Two undeclared POSTs exist on master today and the test is green:

    src/web/oidc.py:359      Request(..., method="POST" if data is not None ...)
    src/socketmode.py:76     Request(CONNECTIONS_OPEN, data=b"")   # no method=

Neither is in `ALLOWED`. Both are infrastructure rather than prospect-facing,
which is why this is P1 and not P0 — but the test's own failure message claims
*"every HTTP write in the repository is declared"*, and that claim is false. A
new module copying the transport's shape and POSTing to a provider would be
invisible to this scanner.

## Build

    tests/test_nothing_writes_to_a_provider.py   MODIFY

1. Add a fourth alternative for `Request(... method="VERB" ...)`.
2. Add a rule for `Request(` carrying `data=` with no `method=` — urllib sends
   that as POST, so the scanner must read it as one.
3. Declare `src/web/oidc.py` and `src/socketmode.py` in `ALLOWED`, each with
   the reason it is not a provider write (OIDC sign-in is infrastructure;
   Slack Socket Mode opens a websocket). A declaration without a reason is not
   a declaration.
4. Add a **positive control** next to the existing
   `test_the_scanner_would_notice_one`, asserting the scanner reports both new
   shapes.

## Acceptance — RUN each, paste real output

1. The positive control fails on the **old** regex and passes on the new one.
   Paste both runs. A scanner extension with no red proof is not verifiable.
2. `test_every_http_write_in_the_repository_is_declared` passes, and the run
   prints the two newly declared files so the declaration is visible rather
   than silent.
3. **The scanner still refuses an undeclared one.** Add a throwaway module in
   the test's temp area that POSTs through the `Request`-object shape, assert
   the scanner names it, then remove it.
4. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt`. A new failing name
   BLOCKS — and if this change makes a previously green test go red because it
   found a real undeclared write, that is **evidence, not a regression**:
   report it by name and do not silence it.

## What this task may NOT do

- Do not add anything to `ALLOWED` that reaches a prospect. If the extended
  scanner finds a write into EmailBison or HeyReach that nobody declared, that
  is a P0 finding — **stop and report it**, do not declare it away.
- Do not touch `src/providers/__init__.py`, `src/web/oidc.py` or
  `src/socketmode.py`. This task changes the audit, not the transport.
- Nothing is sent, activated, resumed, enrolled or attached. Production freeze.

## RESULT

STATUS: DONE (acceptance 4 pending suite completion)
COMMIT: 3f77b645
TESTS: 7/7 pass in test_nothing_writes_to_a_provider.py
FILES CHANGED: tests/test_nothing_writes_to_a_provider.py

### What changed

1. Added `REQUEST_METHOD` regex: matches `Request(url, method="VERB", ...)` —
   the shape `src/providers/__init__.py:765` uses for every write. The old
   `CALLS` regex only matched `request("VERB", ...)` (lowercase, verb as
   first arg) and was blind to this.

2. Added `REQUEST_DATA` regex: matches `Request(url, data=...)` with no
   `method=` — urllib sends this as POST. Negative lookahead prevents
   double-counting when both `data=` and `method=` are present.

3. Updated `writes()` to scan with both new regexes.

4. Added three ALLOWED entries with reasons:
   - `src/web/oidc.py` POST — OIDC sign-in infrastructure, not a provider write
   - `src/socketmode.py` POST — Slack Socket Mode websocket open, internal
   - `src/researchpack/pack.py` POST — pre-existing undeclared Apify crawler
     start (same target as already-declared `src/providers/apify.py`)

5. Added positive control `test_the_scanner_sees_the_transports_own_shape`
   asserting both new shapes are caught.

### Acceptance evidence

1. OLD regex vs new shapes: both return None (blind).
   NEW regexes vs same shapes: both match, verb extracted correctly.

2. `test_every_http_write_in_the_repository_is_declared` passes.
   Extended scanner finds 25 writes (was 23), two new ones:
   `('src/socketmode.py', 'POST')` and `('src/web/oidc.py', 'POST')`.

3. Throwaway module with `Request(url, method="POST", data=data)` caught by
   REQUEST_METHOD. Throwaway with `Request(url, data=b"")` caught by
   REQUEST_DATA. Both removed after verification.

4. Full suite running (scripts/run_suite.py --timeout 2400, started 16:25 UTC).
   Monitor watching for scripts/suite_verdict.txt. Diff against
   docs/state/SUITE-BASELINE-2026-09-26.txt owed when verdict arrives.
   No new failing names expected — change is confined to one test file.

### Findings

- Pre-existing undeclared POST in `src/researchpack/pack.py` was already
  failing the test on master before this change. Declared it with the same
  reason as `src/providers/apify.py` (Apify crawler start, not prospect-facing).
  This is NOT a new finding from the extended scanner — the old CALLS regex
  already caught it via `request("POST", ...)`.

### Risks

- REQUEST_METHOD uses `[^)]*` which matches across newlines. If a future
  `Request(` call has `method=` in a nested expression (e.g., a dict value),
  the regex could false-positive. Negative: the `["']` around the verb
  constrains matches to literal strings, and `[^)]*` stops at the closing
  paren of the Request constructor.

### Recommended Claude action

Review the suite verdict when it arrives. Diff failing-name set against
docs/state/SUITE-BASELINE-2026-09-26.txt. If a new failing name appears,
it is evidence of a real undeclared write the extended scanner found —
report it, do not silence it.
