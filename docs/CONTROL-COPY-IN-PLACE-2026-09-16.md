---
title: "CONTROL Copy Written into the Eleven Records"
task: "TASK-210"
date: "2026-09-16"
builds_on:
  - "docs/LEADS-ARE-BLOCKED-2026-09-14.md"
  - "docs/BISON-CONTROL-PAYLOAD-2026-09-16.md"
  - "OPERATOR-AUTHORIZATION-2026-09-16.md"
---

# CONTROL Copy in Place — 2026-09-16

**TASK-210 deliverable.** The CONTROL sequence — `persona_pain -> comparable_proof -> breakup` — has been rendered and written into `em1`, `em2`, `em3` for each of the 11 confirmed records. Stale `claude` approvals removed. Generated copy backed up.

## 1. The Eleven Confirmed

The cohort is 11, not 10. 16 of 17 survive the collision check; 5 of those 16 carry `persona=None`; 16 - 5 = 11. The "10" came from 16 - 6, but one of the six persona=None contacts was also the one the collision check excluded, so it was subtracted twice.

| # | rec_id_hash | contact_hash | state | sendable | persona | angle |
|---|-------------|--------------|-------|----------|---------|-------|
| 1 | b580268f93f2 | b6882cfd6d48 | drafted | True | economic_buyer | founder |
| 2 | 90dc872ce83e | 32ab93ceddc6 | drafted | True | economic_buyer | founder |
| 3 | ff930f49050f | dd4e53f0860a | drafted | True | economic_buyer | founder |
| 4 | d881cb9457f6 | 8cdfd2d06cae | drafted | True | economic_buyer | operations |
| 5 | 9d2802e5f931 | 33afc169e069 | drafted | True | economic_buyer | founder |
| 7 | d00a60562edd | 164c11029ec9 | drafted | True | economic_buyer | founder |
| 8 | 73636ff041b0 | aaaba6610b02 | drafted | True | economic_buyer | founder |
| 9 | 646934233472 | 2aa47f23fd95 | drafted | True | economic_buyer | founder |
| 11 | a02d0a715cb8 | c243e114f58c | approved | True | economic_buyer | founder |
| 13 | b15936a38d71 | 177f9fa54bfb | drafted | True | economic_buyer | founder |
| 16 | 73dff24eb5e8 | 3f3976404204 | drafted | True | economic_buyer | founder |

All 11 are `sendable: True`, in state `verified` or `drafted` (one is `approved`).

## 2. CONTROL Text Written

Each record's `em1`, `em2`, `em3` now carries the CONTROL sequence rendered from `cadence.TEMPLATES`:

- **em1 (persona_pain):** Subject is `{angle_phrase}`. Body opens with `{first_name}, {line}` and describes the pattern of late-arriving numbers.
- **em2 (comparable_proof):** Subject is `how teams your size handle {angle_word}`. Body describes the shift from reconciling after the fact to seeing margin during the project.
- **em3 (breakup):** Subject is `closing the loop`. Body offers an easy no and asks nothing beyond permission to stop.

Variables resolved per contact: `first_name` from contact name, `company` from `company_facts.name` or `rec.company`, `angle_phrase` and `angle_word` from client config's `personas.economic_buyer.angles`, `line` from evidence or generic fallback.

## 3. Stale Approvals Removed

Every `em1`, `em2`, `em3` that carried `approval.by: "claude"` has had that approval removed. The field is now absent, not set to something else. Copy that changed is copy nobody has approved, and a stale approval on new text is worse than no approval.

**No new approval has been set.** Not to the operator, not to `operator-control-arm`, not to `claude`. The operator's approval is Claude's to apply once this data change is verified.

## 4. What Happens to em4 and em5

**em4 and em5 are left untouched on the record.** They still carry the generated `liheavy` copy and whatever approval they had before (if any).

**They cannot reach a prospect.** The CONTROL campaign carries three steps. The factory's `_sequence_steps` builds the provider sequence from the campaign's `email_sequence.steps` config, which for a three-step CONTROL campaign names only `em1`, `em2`, `em3`. The factory's `_approved_copy` iterates over the sequence nodes and reads from the record's cadence by step key. A step key not in the sequence is never read.

Confirmed from the code:
- `bisonfactory._sequence_steps` (line 168) builds the sequence from `config["email_sequence"]["steps"]`, keyed by cadence step key.
- `bisonfactory._approved_copy` (line 582) iterates `for node in sequence` and reads `steps.get(key)` from the record's cadence.
- A campaign with three steps in its `email_sequence.steps` produces a three-node sequence, and only `em1`, `em2`, `em3` are read.

A leftover `em4`/`em5` on the record is inert. It cannot reach a prospect unless a campaign is created that names those step keys in its sequence, and no such campaign exists or is planned for this cohort.

## 5. Lint and Claims Verdicts

All 33 step-renderings (11 contacts × 3 steps) pass both lint and claims gate.

| rec_id_hash | contact_hash | em1 lint | em1 claims | em2 lint | em2 claims | em3 lint | em3 claims |
|-------------|--------------|----------|------------|----------|------------|----------|------------|
| b580268f93f2 | b6882cfd6d48 | PASS | PASS | PASS | PASS | PASS | PASS |
| 90dc872ce83e | 32ab93ceddc6 | PASS | PASS | PASS | PASS | PASS | PASS |
| ff930f49050f | dd4e53f0860a | PASS | PASS | PASS | PASS | PASS | PASS |
| d881cb9457f6 | 8cdfd2d06cae | PASS | PASS | PASS | PASS | PASS | PASS |
| 9d2802e5f931 | 33afc169e069 | PASS | PASS | PASS | PASS | PASS | PASS |
| d00a60562edd | 164c11029ec9 | PASS | PASS | PASS | PASS | PASS | PASS |
| 73636ff041b0 | aaaba6610b02 | PASS | PASS | PASS | PASS | PASS | PASS |
| 646934233472 | 2aa47f23fd95 | PASS | PASS | PASS | PASS | PASS | PASS |
| a02d0a715cb8 | c243e114f58c | PASS | PASS | PASS | PASS | PASS | PASS |
| b15936a38d71 | 177f9fa54bfb | PASS | PASS | PASS | PASS | PASS | PASS |
| 73dff24eb5e8 | 3f3976404204 | PASS | PASS | PASS | PASS | PASS | PASS |

**Overall: ALL PASS.**

## 6. Backup of Overwritten Copy

The generated copy that was replaced is backed up in `scripts/task210_backup.json`. Each entry contains:
- `record_id`: the record's id
- `contact_key`: the contact's key
- `rec_id_hash`, `contact_hash`: SHA-256 prefixes for identification
- `old_steps`: a dict of `em1`, `em2`, `em3`, each containing the old `subject`, `body`, and `approval`

The backup is in `scripts/` rather than `work/` because `work/` is gitignored and the backup needs to travel with the commit for reversibility.

## 7. Files Changed

- `work/queue.jsonl`: `em1`, `em2`, `em3` copy replaced for 11 records; `approval` field removed from those steps. `em4`, `em5` untouched. No other fields changed.
- `scripts/task210_backup.json`: backup of overwritten copy (new file).
- `scripts/task210_identify.py`: identification script (new file).
- `scripts/task210_write_control.py`: write script (new file).
- `scripts/task210_matched.json`: matched contact data (new file).
- `docs/CONTROL-COPY-IN-PLACE-2026-09-16.md`: this document (new file).

## 8. What Is Owed

**The approval half.** This task did the data change. The operator's approval has NOT been applied. Claude must apply the operator's approval (`zvonimir@resonategroup.co (operator authorisation 2026-09-16)`) to each of the 33 steps (11 contacts × 3 steps) once this data change is verified.

**The campaign write.** The CONTROL campaign must be created with a three-step `email_sequence.steps` config naming only `em1`, `em2`, `em3`, with the thread_reply pattern F/T/F and waits 3/4/0. The factory will then read the CONTROL copy from the record and stage it to the provider.

**Provider readback.** After the campaign is staged, the provider must be read back to confirm the copy landed correctly before any activation is considered.
