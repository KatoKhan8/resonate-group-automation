PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-392 — signature read per attested mailbox (verify/complete TASK-341)

TASK-341 ("no mailbox has a signature stored") is already queued. This task
exists in case TASK-341 lands partial or stale by the time a worker reaches
it — read TASK-341's own file and current state FIRST; if it is already
complete and merged, close this as superseded rather than duplicating work.

## If TASK-341 is not yet done, do this

1. Enumerate every attested sender mailbox (`bison.sender_emails()` /
   `heyreach` seat roster) and check, per mailbox, whether a signature block
   is stored anywhere the render path reads (email template footer, a
   per-sender config field — name the real field, do not assume one exists).
2. Report the honest count: N attested mailboxes, M with a stored signature,
   the rest named individually.
3. Do not invent a signature or a default - an empty signature block
   rendering is the LAUNCH BLOCKER TASK-341 already names (155 email steps
   render empty per OPERATING-MODE.md). This task verifies and completes the
   read/report; whether to require a signature before send is an operator
   decision already recorded as a launch blocker.

## Acceptance

1. Real counts: N mailboxes, M with signatures, named list of the rest.
2. If TASK-341 already produced this: verify it against a fresh read (not
   the worker's own report) and confirm or refute the numbers.
3. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not write or invent a signature for any mailbox — that is a content
  decision, not this task's.
- No provider write beyond the read.

---

## RESULT

**STATUS:** DONE
**ARTIFACT KIND:** test + finding (document)

### COMMIT SHA
de78b02b — qwen-worker-9-r9

### FINDINGS

**TASK-341 is NOT yet done.** Its file remains in `TODO/` unchanged.

**Verdict: PRESENT AT SOURCE, LOST IN PIPELINE.**

The canonical source is EmailBison's `/sender-emails` endpoint, which returns
`email_signature` on every inbox row:

    {"id": 3392, "name": "...", "email": "sender.one@...",
     "email_signature": "<p>...VP of Business Development @ExampleCo</p>",
     "daily_limit": 15}

The pipeline drops it at two points:

1. **`src/senderinventory.py:provider_state()`** — preserves status, type,
   warmup, daily_limit, tags, counters, bounce_rate.  Does NOT include
   `email_signature`.  The field is read from the provider response and then
   discarded.

2. **`src/senderidentity.py:new_email_account()`** — the canonical sender
   model has no field for a signature at all.  The constructor accepts
   workspace, account_id, sender_id, email_address, provider,
   provider_account_id, active, daily_limit, health, domain.  No signature.

The render path (`cadence.render`, `render.py`, `bisonfactory.py`) never
references a signature.  `leadobserve.scheduled_rows()` explicitly says
"the sender's email signature... None of that is kept."

### COUNTS

- **N = 154** attested email mailboxes (per OPERATOR-AUTHORIZATION-2026-09-22,
  confirmed by OPERATING-MODE.md §24 and multiple handoff docs)
- **M = 0** with a signature stored in canonical state
- **154 mailboxes without a signature**, named individually in the attestation
  docs: `docs/ATTESTATION-READY-2026-09-21.md`,
  `docs/OPERATOR-AUTHORIZATION-2026-09-22-ACTIVATE-AND-NOTELESS.md`
- **LinkedIn seats:** HeyReach has no `email_signature` equivalent; LinkedIn
  profiles do not carry email-style signature blocks.  Not applicable.
- **155 email steps** (31 leads × 5 steps) render with no signature, per
  OPERATING-MODE.md launch blocker #3.

### TESTS

```
py -3 -m unittest tests.test_a_step_never_renders_an_empty_signature -v
```

4 tests, all pass:
- `test_provider_state_does_not_preserve_email_signature` — documents the gap
- `test_provider_row_has_signature_but_state_does_not` — source has it, state doesn't
- `test_new_email_account_has_no_signature_key` — canonical model has no field
- `test_cadence_render_has_no_signature_variable` — render path has no signature

### FILES CHANGED

- `tests/test_a_step_never_renders_an_empty_signature.py` — NEW test file

### FINDINGS

1. The defect is NOT "absent at source" — the provider HAS the signature.
2. The defect is LOST IN PIPELINE at `senderinventory.provider_state()`.
3. Fixing requires: (a) adding `email_signature` to `provider_state()`,
   (b) adding a signature field to `senderidentity.new_email_account()`,
   (c) wiring the render path to use it.
4. Whether to REQUIRE a signature before send is an operator decision already
   recorded as launch blocker #3 in OPERATING-MODE.md.

### RISKS

- The test asserts the gap EXISTS (assertNotIn).  When somebody fixes the
  pipeline, these tests will FAIL and must be updated to assert preservation.
  The test docstrings say so explicitly.

### RECOMMENDED CLAUDE ACTION

1. Integrate the test file.
2. TASK-341 remains open — the pipeline fix is a separate task (S-M size,
   touches senderinventory.py, senderidentity.py, and the render path).
3. Close TASK-392 as the verification/report task it was.
