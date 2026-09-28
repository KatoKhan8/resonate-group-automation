# GLM Independent Verdict: TASK-392

**Review target:** TASK-392 — signature per attested mailbox verification
**Branch:** `origin/qwen-worker-9-r9`
**Branch HEAD SHA reviewed:** `f1b9c357c17f4b557cbdb06f68339c7343ef3e83`
**TASK-392 commits:** `de78b02b` (main work), `a48b1a64` (SHA stamp)
**Verdict date:** 2026-09-28
**Reviewer:** GLM (Qwen worktree `qwen-worker-7-r9`)

---

## 1. Artifact existence — VERIFIED

The artifact exists on the reviewed ref at the exact SHA named above.

| File | Status | Verified by |
|------|--------|-------------|
| `tests/test_a_step_never_renders_an_empty_signature.py` | NEW, 118 lines | `git show f1b9c357:...` + worktree file present |
| `docs/qwen-tasks/REVIEW/TASK-392-signature-per-attested-mailbox-verification.md` | NEW, 128 lines | `git show f1b9c357:...` + task file read |

`git log --diff-filter=A --all -- tests/test_a_step_never_renders_an_empty_signature.py` confirms first appearance on this branch.

---

## 2. Claim-by-claim verification

### Claim 1: `provider_state()` drops `email_signature` — VERIFIED

**Source code at `src/senderinventory.py` lines ~100-113:**
```python
def provider_state(row):
    return {
        "status": row.get("status"),
        "type": row.get("type"),
        "warmup_enabled": row.get("warmup_enabled"),
        "daily_limit": row.get("daily_limit"),
        "tags": [...],
        "emails_sent_count": row.get("emails_sent_count"),
        "bounced_count": row.get("bounced_count"),
        "unique_replied_count": row.get("unique_replied_count"),
        "unsubscribed_count": row.get("unsubscribed_count"),
        "bounce_rate": _rate(row),
        "read_at": store.now(),
    }
```

**Independent reproduction:**
```
row with email_signature: True
state = provider_state(row)
'email_signature' in state: False
Keys in state: ['bounce_rate', 'bounced_count', 'daily_limit', 'emails_sent_count',
                'read_at', 'status', 'tags', 'type', 'unique_replied_count',
                'unsubscribed_count', 'warmup_enabled']
```

The field is read from the provider response and discarded. **CONFIRMED.**

### Claim 2: `new_email_account()` has no signature field — VERIFIED

**Source code at `src/senderidentity.py`:** Constructor accepts `workspace, account_id, sender_id, email_address, provider, provider_account_id, active, daily_limit, health, domain`. No signature parameter.

**Independent reproduction:**
```
account = new_email_account(...)
'email_signature' in account: False
'signature' in account: False
Keys: ['account_id', 'active', 'created_at', 'daily_limit', 'domain',
       'email_address', 'health', 'kind', 'provider', 'provider_account_id',
       'sender_id', 'workspace']
```

**CONFIRMED.**

### Claim 3: Render path has no signature handling — VERIFIED

Grep for `signature` (case-insensitive) across the three named files:

| File | Result |
|------|--------|
| `src/cadence.py` | NO MATCHES |
| `src/render.py` | NO MATCHES |
| `src/bisonfactory.py` | NO MATCHES |
| `src/leadobserve.py` | Line 420: "the sender's email signature... None of that is kept." |

The leadobserve reference is a comment explicitly confirming the gap: the provider returns the signature and the module deliberately discards it. **CONFIRMED.**

### Claim 4: TASK-341 is NOT yet done — VERIFIED

`docs/qwen-tasks/TODO/TASK-341-no-mailbox-has-a-signature-stored.md` exists in TODO on the target branch. The fix task is still queued.

### Claim 5: 4 tests, all pass — VERIFIED

```
$ python -m unittest tests.test_a_step_never_renders_an_empty_signature -v
test_new_email_account_has_no_signature_key ... ok
test_provider_row_has_signature_but_state_does_not ... ok
test_provider_state_does_not_preserve_email_signature ... ok
test_cadence_render_has_no_signature_variable ... ok

Ran 4 tests in 0.130s
OK
```

---

## 3. Test falsifiability assessment

### Are the tests falsifiable? YES

Each test calls a **real production function** with **real data shapes** and asserts on the **actual return value**:

| Test | Entry point | Assertion | Falsification |
|------|-------------|-----------|---------------|
| `test_provider_state_does_not_preserve_email_signature` | `provider_state(row)` | `assertNotIn('email_signature', state)` | If `email_signature` is added to the returned dict, assertion fails ✓ |
| `test_provider_row_has_signature_but_state_does_not` | `provider_state(row)` | `assertNotIn('email_signature', state)` | Same — flips when fixed ✓ |
| `test_new_email_account_has_no_signature_key` | `new_email_account(...)` | `assertNotIn('email_signature/sig', account)` | Flips when field is added ✓ |
| `test_cadence_render_has_no_signature_variable` | `cadence.render(template, values)` | `assertNotIn('signature', result)` | Flips when render adds signature ✓ |

**Simulated fix test:** Adding `email_signature` to `provider_state()`'s return dict causes `assertNotIn` to raise — the test correctly detects the fix. These are NOT `hasattr` checks, source-text assertions, or fake cassettes.

### Tests go through real entry points? YES

- `provider_state()` IS the production function that builds stored state from provider rows.
- `new_email_account()` IS the production constructor for canonical sender accounts.
- `cadence.render()` IS the production template substitution function.

No wrapper, no indirection, no test-only path.

---

## 4. Existence-is-not-function check

TASK-392 is explicitly a **verification/reporting task**, not a fix task. Its result block says:
- "Integrate the test file."
- "TASK-341 remains open — the pipeline fix is a separate task."
- "Close TASK-392 as the verification/report task it was."

The test file has no production caller because it is a **test** — it is consumed by the test runner, which is the correct consumer for a test. The finding it documents (the gap) is real and the fix is deferred to TASK-341. This is the correct disposition for a verification task: document the gap with falsifiable tests, leave the fix for the task that owns it.

**Verdict: NOT DISCONNECTED.** The artifact is a test + finding document. Its consumer is the test suite and the human who picks up TASK-341.

---

## 5. Merge impact — would merging delete anything?

**TASK-392's own commits** (`de78b02b`, `a48b1a64`) touch exactly 3 files:
- `tests/test_a_step_never_renders_an_empty_signature.py` — NEW (+118 lines)
- `docs/qwen-tasks/REVIEW/TASK-392-...md` — NEW (+128 lines)
- `docs/qwen-tasks/TODO/TASK-392-...md` — DELETED (moved to REVIEW, normal state transition)

**The branch as a whole** (`master...f1b9c357`) changes 64 files across 235 commits and deletes 2 task files from TODO (TASK-392 and TASK-399, both moved to REVIEW). These are normal task lifecycle transitions, not production file deletions.

**TASK-392's own artifact is purely additive** — no production code changed, no lines deleted from any source file. Cherry-picking TASK-392's two commits would be clean.

---

## 6. Scope drift

The branch carries substantial work beyond TASK-392 (Groq adapter, offer v2, research freshness, GLM reviews of other tasks, task registry updates, etc.). TASK-392's own contribution is isolated to its two commits and touches no file outside its task scope.

**Cherry-pick scope:** `de78b02b` and `a48b1a64` are self-contained and can be cherry-picked without any of the other 233 commits.

---

## 7. Findings

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 1 | `provider_state()` drops `email_signature` from provider response | Confirmed gap | `src/senderinventory.py:100-113` — field absent from return dict |
| 2 | `new_email_account()` has no signature field | Confirmed gap | `src/senderidentity.py:new_email_account` — no parameter, no key in output |
| 3 | Render path has no signature variable | Confirmed gap | grep across `cadence.py`, `render.py`, `bisonfactory.py` — zero matches |
| 4 | `leadobserve.scheduled_rows()` explicitly discards signature | Confirmed by source comment | `src/leadobserve.py:420` — "None of that is kept" |
| 5 | Tests are falsifiable and go through real entry points | Verified | Simulated fix causes test failure; no test-only wrappers |
| 6 | TASK-341 (the fix task) is still in TODO | Verified | `docs/qwen-tasks/TODO/TASK-341-no-mailbox-has-a-signature-stored.md` exists |

---

## 8. Disposition

**VERIFIED.** Every claim in the result block is independently confirmed:
- The gap exists at all three pipeline points named.
- The tests pass, are falsifiable, and call real production functions.
- The artifact is purely additive and carries no scope drift.
- The fix is correctly deferred to TASK-341.
- No production code is changed; no merge would delete anything.

**Recommendation: MERGE** (cherry-pick `de78b02b` and `a48b1a64`).

The test file documents a real launch blocker (155 email steps render without signatures) with falsifiable assertions that will correctly flip when the fix lands. Integrating it gives the TASK-341 worker a safety net and a measured baseline.
