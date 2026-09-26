PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-333 - integrate the Offer Engine from its branch, by cherry-pick

TASK-318 is **complete on `origin/qwen-worker-3-r9`** and in REVIEW there. The
2026-09-26 handoff says it is "WRITTEN, NOT STARTED". The handoff is wrong -
verified 2026-09-26: the branch carries `src/offers.py` (4229 bytes),
`config/clients/productive-offers.yaml` (4719 bytes) and
`tests/test_an_offer_cannot_be_invented.py` (6123 bytes).

**CHERRY-PICK. DO NOT MERGE THE BRANCH.** Standing operator rule from the
handoff section 4: the r9 branches carry more than their task, and a wholesale
merge brings the extra with it. That branch also carries `docs/AUDIT-2026-09-26.md`
and other work that belongs to different tasks.

## What to do

1. Identify the commits on `origin/qwen-worker-3-r9` that touch ONLY the three
   TASK-318 files above. Report their SHAs.
2. Cherry-pick those onto a fresh branch from master.
3. **Diff every picked file against master before and after.** Report the exact
   line count that lands, and confirm nothing outside the three files changed.
4. Run the task's own acceptance, from `docs/PHASE1-PLAN-2026-09-26.md` TASK-318,
   and paste the real output.

## The rule that must hold after the pick

**An offer with `approval_status != "approved"` cannot reach copy generation.**
Not a warning - a refusal, in the same shape as `reviewapproval`. Production does
not approve its own offers.

Prove it fires:

    py -3 -m unittest tests.test_an_offer_cannot_be_invented -v

and separately prove the refusal is REAL by constructing an unapproved offer and
confirming `offers.for_campaign(503, require_approved=True)` raises. Paste it.

## Also verify, because the branch predates two directives

`docs/OPERATIVE-DIRECTIVES` note: `docs/OPERATOR-DIRECTIVES-2026-09-26-PHASE1.md`
section 1 requires every producer to name a **production consumer**. `src/offers.py`
as written may have none. Do NOT wire it here - that is TASK-321's - but report
under FINDINGS whether it has a caller, so it is not silently another
DISCONNECTED module.

`offers.missing()` must list what the client has not supplied: no case studies,
no verified benchmarks, no dashboard or workflow example, no calculator, no demo
link. Report the count it returns.

## Acceptance

1. The three files exist on your branch and are byte-identical to the r9 versions
   unless you changed something - if you changed anything, say exactly what and
   why.
2. `py -3 -m unittest tests.test_an_offer_cannot_be_invented` passes, output
   pasted.
3. The refusal is seen to FIRE, not merely asserted present.
4. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against the baseline. Not a count.
5. Section 11 completion report with the REMOTE SHA verified.

## What this task may NOT do

- Do not merge `qwen-worker-3-r9` wholesale.
- Do not bring `docs/AUDIT-2026-09-26.md` in with it (that is TASK-335).
- Do not invent an offer, a commercial term, a discount, a pilot, a guarantee or
  a customer result. Offers are DATA, never generated.
- Nothing sent, nothing activated.
