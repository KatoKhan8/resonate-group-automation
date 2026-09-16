PRIORITY: P0
DEPENDS:

# TASK-209 - run the complete activation gate against the one-lead canary

## WHERE THIS SITS

Production is the overriding priority and this is the last analysis standing
between approved inventory and a first real send. Claude measured the approved
inventory directly from live state on 2026-09-16:

    steps approved by operator-control-arm      30   ALL LinkedIn (li1-li5)
    steps approved by the operator directly      2
    steps approved by "claude"                  95   NOT operator approval
    steps unapproved                           590

    contacts with FULL li1-li5 operator approval:  6
    every one of them has a LinkedIn profile

**Zero email steps have ever carried operator approval.** So EmailBison cannot
reach a send inside existing gates - `_ensure_leads` refuses without approved
steps, and approval is a human act nobody here may perform. HeyReach is the
channel with approved copy.

Everything else HeyReach needs exists: campaign 599020, a sender that resolves
and is active, the sequence with merge variables, the list schema proven
(TASK-158), the staging path designed (TASK-165), rehearsed (TASK-186), and its
permission deliberately OFF (TASK-172).

What nobody has produced is a single document saying: for ONE named lead, here
is every gate and what it says RIGHT NOW.

## THE QUESTION

Pick the canary candidate and run every gate against it. Read-only.

1. **Name the candidate.** From the 6 contacts with full li1-li5 operator
   approval, pick the one that passes the most gates, and say why the others
   were not chosen. Two of them sit on one record in state `held` with
   `sendable: True`; one is on a `drafted` record; one is `verified`. Hash the
   identifiers. Say which record and contact, and what state each is in.
2. **Then every gate, each with PASS or FAIL and the value it read.** Do not
   summarise - one line per gate:

       tenancy / workspace ownership
       campaign ownership and identity (by id, from the provider)
       campaign state, read from the provider now
       list ownership and whether it is attached to any campaign
       sender resolves, is active, authorization currently valid
       killswitch: global, workspace, campaign
       collision: account-level and contact-level
       prior contact, on any channel, from the provider
       historical contact
       fatigue
       caps and daily volume
       approval: which steps, by whom, and whether the fingerprint is current
       copy: lint and claims, against this contact's own evidence
       sequence / copy fingerprint matches what was approved
       campaign binding

   A gate whose input cannot be read is a FAIL, not a PASS. Say which values
   came from the provider and which from local state.
3. **State the blocking set.** Which gates FAIL, and for each: is it a
   permission, a data gap, a human act, or a defect. That list is the answer
   the operator needs.
4. **Is the hold a blocker?** Five of the seven approved contacts sit on
   records in state `held`, and all five have `hold_reason: None` despite
   TASK-168 wiring that field - so either the backfill did not reach them or
   the reason lives elsewhere. Establish whether `held` prevents staging at
   all, or whether it is orthogonal to a LinkedIn add.
5. **The exact command sequence** an operator would run to stage this one lead
   once the permission exists, in order, with the readback after each step. Do
   not run it.

## THE TRAP

Do not create a new gate, and do not reopen a decision already proven. The
reseal of `LINKEDIN_ADD_LEAD`, the `CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False`
finding, the list schema, the CONTROL copy - all settled. This task reports
the state of existing gates and adds nothing.

Second trap, and it is the one to be careful about: **a gate that passes today
may not pass at the moment of the write.** Fatigue, collision, prior contact
and campaign state are all time-dependent and two of them are provider facts.
Mark every time-dependent gate as such, so nobody reads this document tomorrow
as a licence. The pre-write check is what must run at the write; this is a
readiness report, not a substitute for it.

## WHAT YOU MAY NOT DO

- **No provider writes.** No lead add to any list or campaign, no sequence
  write, no activation. Provider READS are required and expected.
- Do not add anything to `SUPPORTED` or `CONDITIONAL`.
- Do not set, clear or default any approval field.
- Do not clear a hold, raise a cap, or resolve a collision.
- Do not weaken or reorder a gate. If a gate cannot be evaluated, that is a
  FAIL and a finding.
- Never commit a profile URL, a prospect name, a company name or a domain.
  Hash every identifier and say what you hashed.

## FILES ALLOWED

    docs/CANARY-GATE-REPORT-2026-09-16.md   (new, PII hashed)
    scripts/task209_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The named candidate with the reason it was chosen over the other five; every
gate with PASS/FAIL, the value read, and provider-or-local; the blocking set
classified into permission, data, human act or defect; whether `held` blocks a
LinkedIn add; and the exact operator command sequence with its readbacks.
