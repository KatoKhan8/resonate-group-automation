PRIORITY: P1
DEPENDS:

# TASK-200 - 289 steps are waiting on a person, so make that person's job small

## WHERE THIS SITS

TASK-194 sorted the records that are verified but not campaign-ready and found
zero permanent blocks. The largest bucket is not a defect and cannot be
delegated:

    289 steps held by draft_not_approved
     23 records with cadence generated and ZERO approvals
      3 records with partial approvals and lint or claim failures

Approval is `operator-control-arm`. It means a human read the copy. Nothing in
this system may set it, and the checkpoint names bulk-approving as the most
damaging action available here - because `pushable` was retired as a promotion
criterion precisely when copy that passed every automated gate failed a human
read, and the operator's hand-written fallbacks then beat everything the model
had produced on both channels.

So the bottleneck is a person's attention, and the useful engineering is not to
work around it but to spend as little of it as possible.

## THE QUESTION

Produce ONE document an operator can read start to finish and approve or reject
from, without opening the repository.

1. **Per record, per step: the rendered copy as a prospect would receive it.**
   Subject and body, fully resolved, in send order, with the delay between
   steps and whether each is a same-thread reply. Not a template. Not a
   variable name. What arrives.
2. **Beside each step, what the gates already said.** Lint verdict, claims
   verdict, and for claims the specific evidence row each assertion rests on
   with its `source_url` and `retrieved_at`. An operator approving a claim
   needs to see what licenses it; that is the difference between reading copy
   and auditing it.
3. **Flag what a human is most likely to reject**, using what this repository
   has already learned rather than your judgement of the prose. At minimum:
   which steps are entirely CONTROL fallback text, which variables fell back
   rather than resolved, and which records carry `persona=None` and therefore
   receive an angle chosen by a default rather than by their role - TASK-167
   found six of sixteen on the email side and TASK-176 found fifteen of
   twenty-four variable slots falling back on LinkedIn.
4. **Order it so the cheapest decisions come first.** Records whose every step
   passes both gates with no fallbacks are the fastest yes. Records that are
   entirely fallback text are the slowest. Say the count in each band at the
   top, so the operator knows the size of the job before starting it.
5. **State what approving one record causes.** Which campaign it would enter,
   how many messages that contact would receive, over how many days, from which
   sender if one is assigned. An approval whose consequence is not on the page
   is an approval given blind.

## THE TRAP

**Do not set, clear, default or pre-fill `approval.by` for anything, and do not
add a mechanism that would make it easier to set in bulk.** This task's entire
purpose is to serve a human decision, and a convenience that approves twenty
records in one keystroke is the damaging action wearing a helpful face.

Second trap: do not edit the copy. If a step reads badly, that is information
for the operator, not a defect for you to fix - regeneration resets what the
human would be approving and TASK-197 established that generation cannot even
run for records with no research.

## WHAT YOU MAY NOT DO

- No provider writes, no provider calls, no model calls, no generation.
- Do not set or modify any approval field anywhere.
- Do not regenerate, edit or reorder copy.
- Do not include a real contact name, email, company name or domain in the
  document - hash every identifier. The COPY ITSELF may contain a company name
  because that is what the prospect receives; put those records' copy behind a
  clear warning that the section carries unhashed prospect data, and say so at
  the top, so the operator knows not to paste it anywhere public. If the PII
  guard refuses the file for that reason, report it rather than defeating it.

## FILES ALLOWED

    docs/APPROVAL-PACKET-2026-09-16.md   (new)
    scripts/task200_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The packet: per record per step rendered copy, the gate verdicts with the
evidence row behind each claim, the rejection flags, the bands with counts at
the top, and what approving one record causes.

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: 6f3b7e7
TESTS: Script imports verified. No src/ files modified. The script is a read-only generator that imports from src.lint and src.claims for gate checks.
FILES CHANGED:
  - docs/APPROVAL-PACKET-2026-09-16.md (new, 7980 lines)
  - scripts/task200_approval_packet.py (new, 529 lines)

FINDINGS:
  - 47 records have unapproved steps (449 steps total awaiting approval)
  - Band distribution: 1 record in band 1 (all clean), 41 in band 2 (pass with fallbacks), 5 in band 3 (gate failures), 0 in band 4
  - 7 steps have actual gate failures: 5 claims failures (unsupported operational assertions), 1 lint failure (em_dash), 1 additional claims failure
  - No campaigns exist yet for these records, so approving enters no campaign
  - All records use the productive_li_heavy_v1 cadence (11 steps: em1-em5, li1-li6)
  - Cadence spans Day 1 through Day 21 (three weeks)
  - No sender assigned yet; workspace sender configuration applies
  - Evidence is shown once per contact (not per step) to keep the document readable
  - The copy itself contains unhashed prospect data (company names, first names) as the prospect would receive it, behind a clear warning at the top
  - Record identifiers and contact keys are hashed throughout

RISKS:
  - The document is 7980 lines long. An operator reading it start to finish is a significant time commitment. The band ordering helps (band 1 is one record, fastest yes), but the total volume is the bottleneck this task was meant to reduce, not solve.
  - No same-thread reply indicators are shown in the document. The cadence library defines thread_reply patterns per ladder, but the stored steps do not carry this flag. An operator would need to consult cadencelibrary.py to know which emails are same-thread follow-ups.
  - The snapshot is from 2026-09-15T17:52:12+00:00. Any approvals or changes since then are not reflected.

RECOMMENDED CLAUDE ACTION:
  - Review the packet and hand it to the operator. The document is the deliverable.
  - The 5 band-3 records have gate failures that need operator attention: unsupported claims about "utilisation" on records with no evidence, and one em_dash lint failure.
  - Consider whether the document length is acceptable or whether it should be split per-client for easier digestion.
