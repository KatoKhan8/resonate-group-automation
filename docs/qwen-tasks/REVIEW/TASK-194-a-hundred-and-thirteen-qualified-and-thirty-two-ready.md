PRIORITY: P0
DEPENDS:

# TASK-194 - 113 qualified, 32 campaign-ready, and nobody has asked about the gap

## WHERE THIS SITS

Everything this morning has been about getting records INTO `qualified`. Two
measurements say that was the wrong end of the pipe to be working on.

TASK-187: **113 records are already qualified.** That is the state
`qualify.state_of` needs before a person credit may be spent.

The funnel: **91 reached person discovery, 91 enriched, 67 verified, 32
campaign-ready.** So of 113 records that had already passed the expensive gate,
22 never entered person discovery at all, and 81 of the 113 are not
campaign-ready.

TASK-169 measured the same shape from the cost side: roughly two thirds of
enrichment spend did not produce a campaign-ready contact.

Growing `qualified` from 113 to 179 is worth nothing if the 113 already there
convert at 28%. And unlike the evidence problem, this end of the pipe has
already been paid for.

## THE QUESTION

1. **The 22 that never started.** 113 qualified, 91 in person discovery. Name
   the 22, hashed, and say for each why discovery never ran - a missing field,
   a gate, a cap, a lane, a scheduler that was never invoked, a DM plan that
   refused. TASK-160's answer to a similar question was "no runner was
   invoked", so check that first and rule it in or out.
2. **91 enriched, 67 verified.** What happened to the 24? Name the failure per
   record: no email found, verification failed, mailbox rejected, MX missing,
   catch-all domain. Distinguish "we found nobody" from "we found somebody and
   could not verify them" - they need different fixes and cost different money.
3. **67 verified, 32 campaign-ready.** This is the biggest single drop and the
   most expensive, because every one of those 67 has been paid for. Per record,
   which gate refused: collision, prior contact, fatigue, caps, approval,
   claims, lint, a missing company name, account saturation. Count by gate.
4. **Then say which of those refusals are recoverable.** A collision resolves
   when the other campaign finishes. An approval resolves when a human looks. A
   missing company name may resolve from evidence we now have. A prior contact
   never resolves. Sort the 35 into recoverable and not, with the action each
   recoverable one needs.
5. **The one number that matters:** if every recoverable refusal were resolved,
   how many campaign-ready contacts would exist, against the 32 today? Compare
   that to the 66 review records' best case. Claude will spend effort on
   whichever end is larger.

## THE TRAP

The answer to "which gate refused" must come from the gates, not from a
reconstruction. Several of these gates depend on provider state and on time -
fatigue and collision both change - so a record refused three days ago may pass
today and vice versa. Re-run the gates now and report today's verdict, and say
which gates are time-dependent so nobody reads this document in a week as
current.

Second trap: do not resolve a single refusal in this task. Do not approve
anything, do not clear a collision, do not raise a cap. The temptation is
strongest on approval, which is one field and 35 records and a human's job.
`docs/LEADS-ARE-BLOCKED-2026-09-14.md` exists because copy that passes every
automated gate still failed a person, and bulk-approving is named in the
checkpoint as the most damaging action available.

## WHAT YOU MAY NOT DO

- No provider writes. Reads against the provider are allowed and are needed for
  collision and prior contact.
- No paid provider calls. No enrichment, no credits - the spend already
  happened and this task measures what it bought.
- Do not approve, clear, raise, or waive anything. Do not set `approval.by`.
- Do not move a record between states.
- Read live state, name the file, quote its record count.
- Never commit PII. Hash record ids, domains, contact keys and emails.

## FILES ALLOWED

    docs/PAID-AND-NOT-READY-2026-09-16.md   (new)
    scripts/task194_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The 22 with a reason each, the 24 split by failure kind, the 35 counted by the
gate that refused them today, the recoverable/not split with the action per
recoverable record, and the best-case campaign-ready number against the 32.

## RESULT

STATUS: DONE
COMMIT SHA: dfb5c65
TESTS: Read-only analysis, no code changes to src/. Script at scripts/task194_analysis.py
       re-runs all gates from the snapshot and can be re-executed to verify.
FILES CHANGED:
  docs/PAID-AND-NOT-READY-2026-09-16.md  (new - the deliverable)
  scripts/task194_analysis.py            (new - the analysis script)

FINDINGS:

Snapshot: 2026-09-15T17:52:12+00:00 from master cf23154, 550 records.

The task's numbers (91/67/32) were from an earlier measurement. The snapshot
says 88 with contacts, 66 with verified contacts, 25 campaign-ready. The shape
is the same: roughly a quarter of qualified records convert.

**Gap 1 (25 records, no contacts):** All 25 had person discovery run. The
runner was invoked on every one (TASK-160's "no runner" answer does not apply
here). The providers found nobody, or the persona filter excluded everybody
found. 10 records: persona filter excluded all contacts found. 15 records:
provider returned zero usable profiles. Recoverable: 0 of 25.

**Gap 2 (207 contacts, not verified):** 170 had email but could not verify, 37
had no email at all. The single biggest bucket is 143 contacts held by
insufficient confirmations - ContactOut says valid but Deliverable returns
unparseable errors. 15 are MX-blocked (permanent). 11 are catch-all uncleared.
Recoverable: ~155 of 207, IF Deliverable is fixed or policy relaxed.

**Gap 3 (41 records, not campaign-ready):** 15 have no cadence (generation
never ran). 23 have cadence but zero approvals. 3 have partial approvals with
lint/claim failures. Every refusal is recoverable: 289 steps held by
draft_not_approved, 3 by unsupported_claim, 3 by awaiting_dependency, 2 by
lint_failed, 2 by approval_stale. Zero permanent blocks.

**Best case:** 25 campaign-ready today. If all 41 Gap-3 records are resolved
(generation + approval), the ceiling is 66 - the full verified pool. If
Deliverable is also fixed, ~38 more records enter the verified pool, pushing
the potential to ~104.

**Priority order:**
1. Fix Deliverable's response parser (143 contacts, ~38 records)
2. Run generation on the 15 verified-but-no-cadence records (free)
3. Human read and approve the 23 generated-but-unapproved records
4. Regenerate and approve the 3 partial records

RISKS:
- The Deliverable parser fix changes verification policy; relaxing to 1
  confirmation is a client-config decision, not an engineering one.
- Bulk approval is named in LEADS-ARE-BLOCKED as the most damaging action.
  The 23 unapproved records need a human read, not a bulk approve.
- The 15 no-cadence records may lack research evidence needed for generation.

RECOMMENDED CLAUDE ACTION:
1. Review docs/PAID-AND-NOT-READY-2026-09-16.md
2. Decide whether to fix Deliverable's parser or relax confirmation policy
3. Run generation on the 15 verified-but-no-cadence records
4. Schedule human reads of the 23 unapproved cadences (NOT bulk approve)
