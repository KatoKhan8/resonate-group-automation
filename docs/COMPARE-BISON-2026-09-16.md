# COMPARE-BISON: Field-by-field analysis and fix

**Date:** 2026-09-16
**Task:** TASK-215
**Campaign:** 485 (EmailBison, CONTROL sequence, 10 leads)

## The defect

`compare_bison` compared two different quantities on four fields and could
never pass. It was the last gate before the first real EmailBison send.

## Field-by-field: what both sides mean and what is comparable

### Sequence-level fields (the template)

| Field | Approved side (OLD) | Provider side | Comparable? |
|-------|--------------------|---------------|-------------|
| subjects | RESOLVED per-contact text | `{SUBJECT_1}` placeholder | NO - different quantities |
| bodies | RESOLVED per-contact body | `<p>{BODY_1}</p>` placeholder | NO - different quantities |
| delays | Cadence DAY positions (1, 4, 8) | Provider `wait_in_days` (3, 4, 0) | NO - schedule vs graph |
| actions | Cadence step keys (em1, em2, em3) | Provider step names (step1, step2, step3) | NO - different naming |

### Stale-row fields (bookkeeping)

| Field | Row says | Provider says | Root cause |
|-------|----------|---------------|------------|
| campaign_name | Human name | Derived name with `[client/id]` suffix | Factory derives but doesn't write back |
| workspace | `""` (empty) | `10` | Factory reads from config, doesn't write back |
| sender_ids | `[]` (empty) | `['2736']` | Row may not carry senders in the field the comparator reads |
| status | `paused` | `draft` | Row's `provider_status_expected` may not match post-staging state |

### Per-lead copy (the words each prospect receives)

NOT COMPARED AT ALL by the old code. The resolved per-contact copy travels as
custom variables on the lead at the provider (`subject_1`, `body_1`, etc.).
The old code tried to compare the resolved copy against the sequence template,
which is the wrong comparison entirely.

## The fix

### Sequence-level: compare like for like

- **subjects/bodies**: Approved side now states the EXPECTED PLACEHOLDERS from
  the config (`{SUBJECT_1}`, `<p>{BODY_1}</p>`), not the resolved per-contact
  text. Built via `bisonfactory._sequence_steps` - the same function that
  writes the sequence to the provider.
- **delays**: Approved side now states the declared `wait_in_days` from the
  config, not the cadence day positions. `_sequence_steps` already verifies
  these reproduce the cadence gaps.
- **actions**: Approved side now uses `step1`, `step2`, `step3` to match
  provider naming.
- **Thread-reply normalisation**: Both sides apply `_comparable_step` to strip
  the `Re: ` prefix on thread_reply steps, so the comparison is honest.

### Stale-row: derive in the comparator

Chose to derive in the comparator rather than write back in the factory:

- **campaign_name**: `bisonfactory.provider_campaign_name(campaign)` - TASK-170
  precedent for HeyReach.
- **workspace**: Derived from config:
  `config["providers"]["emailbison"]["workspace"]`.
- **sender_ids**: Still read from the campaign row. If the row has no senders,
  that is a real mismatch.
- **status**: Still read from `provider_status_expected`. If the row says
  "paused" and the provider says "draft", that is a real mismatch.

### Per-lead copy: new comparison

- **Approved side**: For each approved contact, computes the expected custom
  variables (`subject_1`, `body_1`, etc.) from the resolved copy.
- **Provider side**: Reads custom variables per lead via `GET /leads/{id}`.
- **Comparison**: For each lead, checks that every variable matches. A mismatch
  FAILS loudly, naming the contact by hashed email (SHA-256, first 12 chars).

## What was NOT changed

- `providerwrites.SUPPORTED` / `CONDITIONAL` - untouched
- `executionguard` - untouched
- Approvals, cadence copy, the sequence, the lead set, caps - untouched
- No provider writes, no activation, no resume

## Tests

Seven tests in `tests/test_compare_bison.py`:

1. **PASS when everything matches** - sequence placeholders match, lead custom
   variables match, all fields agree.
2. **Sequence fields are placeholders** - approved subjects are `{SUBJECT_1}`
   etc., delays are `(3, 4, 0)`, actions are `("step1", "step2", "step3")`.
3. **Campaign name is derived** - approved name includes `[client/id]` suffix.
4. **Workspace derived from config** - approved workspace is `"10"`.
5. **FAIL when one lead's custom variable differs** - verdict is FAIL, failure
   names the contact by hashed email.
6. **Only the differing lead fails** - Alice passes, Bob fails, Alice's hash
   is NOT in the failures.
7. **Sequence mismatch still fails** - wrong placeholder in sequence fails on
   the `subjects` field.

All seven pass. Exit code 0.

## Real verdict for campaign 485

**Cannot be run from this worktree.** The live campaign data (`work/queue.jsonl`
and `work/campaigns.jsonl`) exists only in Claude's worktree. This worktree has
no `work/` directory.

The comparison requires:
- The campaign row with `bison_campaign_id`, `record_ids`, `senders`, etc.
- The record data with approved cadence steps
- A live EmailBison API connection with workspace pinning

**Owed from Claude's worktree:**
```
py -3 -m src.configdiff --campaign 485 --channel email --workspace 10 --json
```

Report the verdict and every field back to this document.

## Files changed

- `src/configdiff.py` - rewrote `approved_bison`, updated `provider_bison` to
  read per-lead custom variables, updated `compare_bison` to do per-lead copy
  comparison, added `_expected_lead_variables` and `_hash_email` helpers.
- `tests/test_compare_bison.py` - new file, seven tests.

## Risks

1. **The per-lead read is expensive for large campaigns.** Each lead requires
   a separate `GET /leads/{id}` call. For campaign 485 with 10 leads this is
   10 extra GETs. For a campaign with thousands it would be prohibitive. The
   comparator runs against staged campaigns that hold a handful of people, so
   this is acceptable today.

2. **The stale-row fix derives campaign_name and workspace but not sender_ids
   or status.** If the campaign row's `senders` field is empty, the comparison
   will still fail on `sender_ids`. If `provider_status_expected` doesn't match
   the post-staging status, it will still fail on `status`. These are real
   mismatches that should be fixed at the row level, not papered over in the
   comparator.

3. **The `_hash_email` function uses SHA-256 truncated to 12 chars.** This is
   enough to identify a contact in a failure message without logging PII, but
   is not collision-proof. For a campaign with millions of leads it could
   collide; for ten leads it cannot.
