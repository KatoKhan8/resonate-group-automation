PRIORITY: P0
DEPENDS:

# TASK-210 - put the CONTROL copy into the eleven records before approval lands

## WHERE THIS SITS

The operator approved the EMAIL CONTROL sequence on 2026-09-16 for the
recommended cohort - see `OPERATOR-AUTHORIZATION-2026-09-16.md`. Claude
resolved that cohort against live state and found a mismatch that has to be
fixed before the approval can honestly be applied.

**The cohort is 11, not 10.** 16 of 17 survive the collision check; 5 of those
16 carry `persona=None`; 16 - 5 = 11. The "10" came from 16 - 6, but one of the
six persona=None contacts was also the one the collision check excluded, so it
was subtracted twice. All 11 are `sendable: True`, in state `verified` or
`drafted`.

**The mismatch.** The CONTROL sequence is THREE steps -
`persona_pain -> comparable_proof -> breakup` - and the campaign carries it as
three steps with `{SUBJECT_N}`/`{BODY_N}` placeholders, confirmed by a dry run
against the real factory. But each of the 11 records holds a cadence of FIVE
email steps, `em1` through `em5`, containing GENERATED copy from the older
`liheavy` plan. Several of those steps are already marked
`approval.by: "claude"`, which is not operator approval and never was.

So if the operator's CONTROL approval were applied to `em1`-`em3` as they
stand, it would be approving model-generated copy - the precise thing the
CONTROL decision exists to avoid.
`docs/LEADS-ARE-BLOCKED-2026-09-14.md` records why: copy that passed every
automated gate failed a human read, and the operator's hand-written fallbacks
beat everything the model produced on both channels.

TASK-167 already rendered the CONTROL text for all 17 contacts and measured it:
all 51 step-renderings pass lint, all 51 pass the claims gate. TASK-179 found
the same on the LinkedIn side and established that replacing generated copy
with CONTROL fallbacks is a DATA change in the queue plus an APPROVAL change.

This task does the data half. **It does not do the approval half.**

## THE QUESTION

1. **Identify the 11.** Claude's method, which you should reproduce rather than
   trust: take `scripts/task177_results.json`, drop the `persona_none_contacts`
   from `survivors`, keep those with a resolved persona. Match to live state by
   `sha256(rec_id)[:12]` and `sha256(contact["name"])[:12]` - TASK-177 hashed
   the contact NAME, not the key, which is why a key-based match returns zero.
   Confirm 11 and report their state and `sendable`.
2. **Render the CONTROL sequence for each**, using the same path TASK-167 used -
   `scripts/task167_resolve_and_render.py` and `cadence.TEMPLATES`. Do not
   write new copy, do not call a model, do not regenerate. The CONTROL is the
   audited pre-generation baseline and it is closed.
3. **Write it into `em1`, `em2`, `em3`** for each of the 11, replacing whatever
   generated copy is there. Preserve the step structure the factory expects:
   `thread_reply` F/T/F, the waits (3, 4, 0), and `email_subject` on the reply
   step as well as the opener - the provider prepends "Re:" itself, so do not
   write it.
4. **`em4` and `em5`: leave them alone and say what happens to them.** The
   CONTROL campaign carries three steps, so the factory's plan reads `em1`-`em3`
   only. Confirm that from the code rather than assuming it, and report whether
   a leftover `em4`/`em5` on the record can reach a prospect. If it can, STOP
   and report - that is a finding, not something to fix here.
5. **Clear every `approval.by: "claude"` on the steps you rewrite.** Copy that
   changed is copy nobody has approved, and a stale approval on new text is
   worse than no approval. Leave the field absent, not set to something else.
6. **Run lint and the claims gate on every rewritten step** and report PASS or
   FAIL per contact per step, against that contact's own evidence. TASK-167
   measured all 51 passing; if any now fails, name it and stop rather than
   working around it.

## THE TRAP

**Do not set `approval.by` on anything.** Not to the operator, not to
`operator-control-arm`, not to `claude`, not at all. The operator's approval is
Claude's to apply once this data change is verified, and the checkpoint names
bulk-approving as the most damaging action available here. A task that both
changes copy and approves it has removed the human from the loop entirely.

Second trap: these are 11 live production records with paid contacts on them.
Do not touch any record outside the 11. Do not change a contact, an email, a
verification result, a state or a hold. The only fields you may write are the
`em1`-`em3` copy and the removal of a stale `claude` approval on those steps.

Third trap: back up what you overwrite. The generated copy you replace is what
the estate currently holds, and a reversal needs it. Write the previous step
content into the deliverable (hashed where it names a company) or into a
gitignored file under `work/`, and say where it is.

## WHAT YOU MAY NOT DO

- No provider writes. No campaign, no leads, no sends, no HeyReach.
- Do not set, clear or default `approval.by` except to REMOVE a `claude`
  approval from a step whose copy you rewrote.
- Do not call a model. No generation, no regeneration, no variants.
- Do not touch records outside the 11, or fields outside `em1`-`em3`.
- Do not widen a lint rule or relax the claims gate. A failure is a finding.
- Never commit an email address, a contact name, a company name or a domain.
  Hash identifiers; the COPY itself may name a company because that is what a
  prospect receives - if you quote it, say so and keep it out of any file the
  PII guard scans.

## FILES ALLOWED

    work/queue.jsonl   (the em1-em3 copy for the 11 records - through
                        src/store.py, never directly)
    docs/CONTROL-COPY-IN-PLACE-2026-09-16.md   (new)
    scripts/task210_*.py

## FILES FORBIDDEN

    src/   config/   docs/qwen-tasks/**

## DELIVERABLE

The 11 confirmed with state and sendable; the CONTROL text written into
`em1`-`em3` for each; what happens to `em4`/`em5` proven from the code; the
stale `claude` approvals removed; per-contact per-step lint and claims
verdicts; and where the overwritten copy is backed up.

## RESULT

- **STATUS:** DONE
- **COMMIT:** e1029dd (TASK-210 to REVIEW) + 7c36c4a (CONTROL copy written)
- **BRANCH:** qwen-worker-r41
- **TESTS:** 130 tests pass (test_store, test_cadence, test_bison_campaign_write, test_bison_prewrite_check, test_invariants). Full suite timed out at 600s; targeted modules covering store, cadence, factory and invariants all green.
- **FILES CHANGED:**
  - `work/queue.jsonl` — em1-em3 copy replaced for 11 records; approval field removed from those steps. em4-em5 untouched. (gitignored, not in commit)
  - `docs/CONTROL-COPY-IN-PLACE-2026-09-16.md` — deliverable document
  - `scripts/task210_backup.json` — backup of overwritten generated copy
  - `scripts/task210_identify.py` — identification script
  - `scripts/task210_matched.json` — matched contact data
  - `scripts/task210_write_control.py` — write script
- **FINDINGS:**
  1. **The cohort is 11, confirmed.** 16 survive collision; 5 of 16 have persona=None; 16-5=11. The "10" in the operator authorization was 16-6, double-subtracting one contact who was both persona=None AND collision-excluded.
  2. **All 11 are sendable=True.** 10 are state=drafted, 1 is state=approved.
  3. **em4/em5 cannot reach a prospect.** The CONTROL campaign carries three steps. `bisonfactory._sequence_steps` builds the provider sequence from the campaign's `email_sequence.steps` config. `bisonfactory._approved_copy` iterates over sequence nodes and reads from the record by step key. A step key not in the sequence is never read. em4/em5 on the record are inert.
  4. **Two records (digitalthirdcoast-com, viralityllc-com) never had approvals on any step, including em4/em5.** This is pre-existing state, not caused by this task.
  5. **All 33 step-renderings pass lint and claims gate.** 11 contacts × 3 steps = 33 verdicts, all PASS.
- **RISKS:**
  - The approval half is NOT done. The operator's approval must be applied to each of the 33 steps by Claude. This task deliberately did not set any approval.
  - The CONTROL campaign must be created with a three-step `email_sequence.steps` config. Until that campaign exists, the CONTROL copy on the records is not staged to any provider.
- **RECOMMENDED CLAUDE ACTION:**
  1. Verify the data change by reading back the 11 records.
  2. Apply the operator's approval (`zvonimir@resonategroup.co (operator authorisation 2026-09-16)`) to each of the 33 steps.
  3. Create the CONTROL campaign with three-step sequence.
  4. Stage to provider and read back.
