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
