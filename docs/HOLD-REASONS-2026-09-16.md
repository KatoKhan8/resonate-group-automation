# Hold Reasons — 2026-09-16

**TASK-168:** Every hold carries a machine-readable reason.

## Taxonomy

Five classes decide what happens next:

| Class | Meaning | Next action |
|-------|---------|-------------|
| ACTIONABLE | Something we can do now moves it | Re-enrichment, re-run |
| WAITING | A dependency outside us, time will move it | Wait for provider, clearing |
| RETRYABLE | Transient, retrying is correct | Model re-run with different config |
| HUMAN_REVIEW | A person must decide | Manual review queue |
| PERMANENT | It is never moving | Drop with reason |

## Reason codes

### Enrichment holds (src/enrich.py)

| Code | Class | Trigger |
|------|-------|---------|
| `enrich:unresolved_verdict` | WAITING | Contact verdict is None or "unknown" |
| `enrich:accept_all_uncleared` | WAITING | Contact verdict is "accept_all", no clearing provider |
| `enrich:no_contacts_found` | PERMANENT | Enrichment found no contacts at domain |
| `enrich:verifiers_disagree` | HUMAN_REVIEW | Verifiers give contradictory results |

### Generation holds (src/generate.py)

| Code | Class | Trigger |
|------|-------|---------|
| `generation:evidence_not_traceable` | RETRYABLE | Model invented evidence not in record |
| `generation:evidence_empty` | RETRYABLE | Model returned empty evidence list |
| `generation:json_parse_failure` | RETRYABLE | Model output was not valid JSON |
| `generation:lint_failure` | HUMAN_REVIEW | Draft did not pass lint, needs manual copy |

### Un-drop holds

| Code | Class | Trigger |
|------|-------|---------|
| `undrop:pending_reenrichment` | ACTIONABLE | Record reinstated after drop, needs re-enrichment |

## Fields written

When a record is held, three fields are written:

- `hold_reason` — the reason code (e.g. `enrich:accept_all_uncleared`)
- `hold_class` — the taxonomy class (e.g. `WAITING`)
- `hold_at` — ISO 8601 timestamp of when the hold was set
- `hold_detail` — (optional) the raw error message or detail string

## Return-to-queue predicate

`holdreasons.can_return_to_queue(rec)` returns `(safe, reason)`.

Safe means ALL three conditions are provably met:

1. **The condition that caused the hold is measurably gone.** A WAITING record
   with all contacts resolved is safe; one with unresolved contacts is not.
2. **The record still passes every gate it passed before.** The record's state
   and verdicts are checked.
3. **Returning it costs nothing.** No provider call, no credit spend.

Records that are RETRYABLE require a model re-run (which costs credits), so
they are NOT safe to return automatically. They need a deliberate regeneration
pass.

Records that are PERMANENT or HUMAN_REVIEW are never returned automatically.

## Call sites

### src/enrich.py — `outcome()` and `enrich_record()`

`outcome()` returns `("held", reason_code)` instead of `("held", None)`.
The reason code distinguishes accept_all from unresolved verdicts.

`enrich_record()` calls `holdreasons.set_hold_reason()` when the outcome is
"held" and a reason is available.

### src/generate.py — `generate_record()` exception handler

The `llm.ModelError` handler classifies the error message:

- "not traceable" → `generation:evidence_not_traceable`
- "non-empty list" or "evidence...empty" → `generation:evidence_empty`
- "not JSON" or "JSON" → `generation:json_parse_failure`
- "lint" → `generation:lint_failure`
- Other → `generation:{step}:{message[:60]}`

## Backfill

`scripts/task168_backfill.py` reconstructs hold reasons from log entries for
the 36 records held before this change. It classifies using:

1. Log entries with step "un-dropped" → undrop
2. Log entries with "held:" notes on generation steps → generation errors
3. Contact verdicts → enrichment holds
4. Verifier disagreement notes → human review

Run with `--apply` to write changes to the queue.

## Distribution (from TASK-161 classification)

| Class | Count | Records |
|-------|-------|---------|
| RETRYABLE | 12 | Generation model errors |
| WAITING | 9 | Verification unresolved |
| ACTIONABLE | 9 | Un-drop pending re-enrichment |
| HUMAN_REVIEW | 3 | Verifier disagreement, lint failures |
| PERMANENT | 3 | No contacts, should drop |

## What is NOT returned

No record is returned to a queue unless the cause is measured as gone:

- **RETRYABLE (12):** Require model re-run. Not free. Stay held.
- **WAITING (9):** Contacts still unresolved. Stay held.
- **HUMAN_REVIEW (3):** Person must decide. Stay held.
- **PERMANENT (3):** No contacts, no path. Stay held (should be dropped
  separately with proper authority).
- **ACTIONABLE (9):** Contacts exist but may still need enrichment. Each one
  must be individually verified before return.

The trap: a record that cycles held → queued → held burns the stage that
holds it, every pass, forever. Better to leave it held than to loop.
