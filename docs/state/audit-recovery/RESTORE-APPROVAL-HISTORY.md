# Restoring 72 deleted approval records - procedure, not yet run

**Status: QUEUED as a controlled audit migration. NOT a production blocker.**
Do not run this on the production-critical path; it is bookkeeping about the
past, and the HeyReach cohort does not depend on it.

## What was lost, and how

Regeneration replaced the cadence step dict wholesale at three call sites in
`src/generate.py`, discarding the outgoing `approval` rather than retaining it.
Measured 2026-09-15 by diffing a pre-regeneration backup against the estate:

    steps approved before regeneration   169
    approval record still present         97
    approval record GONE                  72

The 72 are audit evidence, not live permissions. **None of them approved
anything that is still in the estate** - the copy they were given to has been
replaced, and `approval.is_approved` would have refused them anyway because it
binds to a content fingerprint. Nothing is unsafe because they are missing;
the record of who looked, and when, is simply absent.

Fixed forward in `generate.store_step`, which now moves a superseded approval
into `approval_history`. The loss cannot recur.

## Where the evidence is

**Deliberately NOT committed.** The mapping needs real record ids, contact
keys and an approver's email address to be usable, and tracked files may not
carry those - `test_fixture_hygiene` enforces it. Keeping a restoration
mapping in the repository would trade one audit problem for a PII one.

    pre-regeneration truth   the earliest queue backup taken 2026-09-15,
                             before any --live regeneration ran. It holds all
                             169 records intact, including BOTH operator
                             approvals.
    exported mapping         approval_history.json in the session scratchpad:
                             record, contact, step, by, at, fingerprint

Both are outside the repository and outside `work/`. **Before this migration
is attempted, confirm the backup still exists** - if it does not, the 72 are
gone and that is the honest outcome to record rather than reconstruct.

## The procedure

1. Confirm the backup and export are present and readable.
2. Take a fresh backup of `work/queue.jsonl` first.
3. For each exported record, locate `cadence[contact][step]` in the live queue.
   - If it carries a LIVE `approval`, SKIP it. That approval is current and
     must not be touched.
   - If `approval_history` already contains an entry whose
     `approved_content_fingerprint` matches, SKIP it. Idempotent.
   - Otherwise append to `approval_history`, marked
     `superseded_by: regeneration`, `restored_from: <backup name>`.
4. **Write through `src/store.py`, never by rewriting the file.** A raw
   rewrite was attempted on 2026-09-15 and the sandbox refused it, correctly -
   `store.save` carries the snapshot merge and the evidence-loss guards, and a
   direct write bypasses both. That refusal is the reason this is a procedure
   rather than a completed action.
5. Re-run the diff from step 1 and confirm 0 records still missing.
6. Confirm no live `approval` changed: the count of binding approvals must be
   identical before and after.

## What must not happen

- Do not restore a record as a LIVE `approval`. Every one of these is
  superseded; reinstating one would approve copy no human has read.
- Do not touch the 97 that survived.
- Do not commit the mapping to the repository.
- Do not let this block a production cohort. It is history, and history keeps.
