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

## AMENDMENT 2026-09-26 — independently confirmed by the GLM canary review

GLM finding **P0-1**, `docs/glm-reviews/canary-readiness-b333697.md`, reviewed
at `b333697`. **Claude reproduced every claim against `origin/master`
(`95ea3d36`, code identical to `b333697`) before this amendment was written.**
Confirmed current, in this exact form:

    src/providerwrites.py:406    EMAIL_RESUME: ("email", False, ...)
    src/providerwrites.py:408    prose still says "It is NOT in SUPPORTED"  <- false
    src/providerwrites.py:561    EMAIL_RESUME IS in SUPPORTED
    src/providerwrites.py:2189   if facing: executionguard.revalidate(authorization)

Three things the review adds that this task did not say, all verified by hand:

1. **`campaigns.py` never imports `eligibility`.** The 17 `CHECKS`
   (`src/campaigns.py:691-709`) that `orchestrator.resume` runs contain no
   suppression read at all. `check_recipients_sendable` delegates to
   `verification.is_sendable`, which decides address *deliverability* — whether
   the mailbox exists — not whether the person asked us to stop. So nothing
   anywhere on the resume path re-reads the stops.

2. **`orchestrator.py:660-661` passes no `expect_leads`.** The transport is
   `lambda pid: bison.resume_campaign(pid)`, so the `meta.total` reach guard at
   `src/providers/bison.py:1888-1898` — the one check whose whole job is to stop
   a campaign reaching more people than the caller believes — **is inert on
   every resume this system performs.** Pass a count. This is in scope.

3. **`orchestrator.py:617`'s docstring says "Resuming re-checks everything. A
   pause is not undone by forgetting it."** It is false, and GLM names it as
   the false confidence that hid this defect (finding T-3). Correct it.
   `orchestrator.py:648`'s "BOTH VERBS ARE SEALED TODAY" is also now stale.

Additional acceptance, on top of the five already listed:

6. **The T-3 negative control, end to end through the real path:** pause a
   campaign, persist an unsubscribe for one contact **during the pause**,
   resume through `orchestrator.resume`, and assert the resume refuses or that
   the contact is excluded. Assert the transport was **never called**. A test
   that asserts `revalidate()` was called is not this test — assert the effect.

7. **`expect_leads` refuses.** Resume a campaign whose provider-side lead count
   differs from what the caller passes, and assert `ProviderError` naming both
   numbers. Then the matching case proceeds.

**Blast radius is NOT settled and you may not settle it.** Whether a resumed
campaign would actually reach a suppressed person depends on whether the reply
loops had already pushed per-lead `EMAIL_STOP_LEAD` to EmailBison during the
pause. That is a **runtime** question, it is on the production-session
verification list, and answering it requires a provider read nobody has
authorised in this task. The skipped re-check is code-level certain; the reach
is not. Do not claim either way.
