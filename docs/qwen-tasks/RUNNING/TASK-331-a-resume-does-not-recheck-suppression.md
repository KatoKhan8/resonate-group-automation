PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-331 — a resume does not re-check suppression

**SEVERITY: HIGH.** Buggie finding H5, `docs/BUGGIE-FINDINGS-2026-09-26.md`.

## The defect, stated precisely

`src/providerwrites.py` OPERATIONS declares:

    EMAIL_RESUME: ("email", False, "DECLARED AND SEALED ...")

The second field is `facing`. It is `False`. The comment three lines below says
resuming is *"the verb that puts a paused sequence back in front of people — a
sending action"*.

`_perform` branches on that flag (`channel, facing, _why = describe(operation)`
then `if facing:`), so EMAIL_RESUME takes the non-facing path and skips:

    executionguard.Authorization      not required
    per-op ledger reservation         not taken
    executionguard.revalidate()       NOT RUN — no re-check of
                                      unsubscribe / suppression state

**76 recipients are suppressed from the 2026-09-23 blank-email incident.** A
resume restarts a paused sequence without revalidating that set immediately
before sending resumes.

## Two things the first report got wrong — do not repeat them

1. **Resume is NOT ungated.** `bison.resume_campaign` calls
   `reviewapproval.require(campaign_id)` internally, and `expect_leads` still
   refuses when the provider disagrees. The gap is the missing suppression
   revalidation, not an absence of gating.
2. **EMAIL_RESUME IS in `SUPPORTED`.** It was added 2026-09-24 deliberately,
   because resumes were happening OUTSIDE `perform` and left no action-ledger
   row — the ledger's last row was 2026-09-18 while a successful resume minutes
   earlier had added nothing, and that silence was twice mistaken for evidence of
   absence. Routing it through `perform` was the fix. **Do not revert it.** The
   neighbouring comment still claims "It is NOT in SUPPORTED" and is stale —
   correct the comment.

## Build

    src/providerwrites.py   MODIFY. Either flip `facing` to True for
                            EMAIL_RESUME, or add a CONDITIONAL entry requiring
                            revalidate() for it. Choose from the code and say
                            which you chose and why.
    tests/test_a_resume_revalidates_suppression_first.py   NEW

**If flipping `facing` to True pulls in requirements the operator has not
granted** — an Authorization for every resume, a ledger reservation — then do NOT
flip it. Add the narrower fix: revalidate suppression before the resume, leave
Authorization as it is, and report which requirements flipping WOULD newly
impose, with the list, so the operator can decide the wider question from a fact.

Correct the stale "NOT in SUPPORTED" comment either way.

## Acceptance — RUN each, paste real output

1. A resume of a campaign holding a suppressed address REFUSES, naming the count:

    py -3 -m unittest tests.test_a_resume_revalidates_suppression_first -v

2. A resume of a clean campaign still proceeds. A guard that blocks every resume
   is not a fix.

3. **The guard is seen to fail:** revert, re-run, confirm the test fails on the
   old code, confirm the revert landed. Paste both runs.

4. **The action ledger still gets its row.** That is why EMAIL_RESUME was routed
   through `perform`, and this change must not cost it: assert a row is written
   for a REFUSED resume as well as a performed one.

5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- **Do not resume, activate, pause or modify any campaign.** 493 is ACTIVE and
  sending. Use a fake transport. The production freeze in
  `docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md` is in force.
- Do not remove EMAIL_RESUME from SUPPORTED.
- Do not touch the sealed `LINKEDIN_STOP_LEAD` verb.
- Do not weaken `expect_leads` or `reviewapproval`.
