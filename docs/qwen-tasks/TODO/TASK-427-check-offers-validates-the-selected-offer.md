PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-427 — `_check_offers` validates the SELECTED offer, not the whole library

**APPROVED AND UNBLOCKED by the operator, 2026-09-27:** "provjerava se samo ponuda
odabrana za tog prospecta, ne svaka ponuda u sustavu" — only the offer selected for
that prospect is validated, not every offer in the system.

**REAFFIRMED — Zvonimir, 2026-09-27 evening.** Recorded again here because the
operator restated it in the evening decision set (decision 5) and instructed that
it is not to be asked about again. **MEASURED THE SAME EVENING**, so the record
carries the number rather than the belief: `offers.load()` returns **8 offers, 2
approved** (`OFFER-A-ECONOMIC-BUYER`, `OFFER-B-OPERATIONS`) **and 6 pending**
(`OFFER-PM-001`, `OFFER-TT-001`, `OFFER-BU-001`, `OFFER-RP-001`, `OFFER-BI-001`,
`OFFER-PR-001`). Read through the real entrypoint `offers.load()`, not by parsing
the YAML a second way — a validator that accepts more than production proves
nothing, which is how `offers.load()` was broken once already on 2026-09-27.
So the gate as written refuses every live run for productive at the first pending
capability offer, and the six pending offers are CORRECT: they are composed by A
and B, they are not selected for anybody, and approving them to clear this gate
would be approving six offers nobody chose.

So question 2 below is answered by the decision itself: the gate checks the offer
chosen for this prospect. Answer questions 1 and 3 in the result block as written,
because the decision does not settle where selection happens or what an empty
selection means, and an empty selection passing silently would turn a fail-closed
gate into a fail-open one.

## THE SITUATION, confirmed independently twice

`src/generate_campaign.py:191-198`:

    def _check_offers(client_name):
        all_offers = offers_mod.load()
        for oid, offer in all_offers.items():
            if offer.get("approval_status") != offers_mod.APPROVED:
                raise NotApproved(...)

It iterates the ENTIRE offer library and raises on the first unapproved offer.

Offers A and B were approved by the operator on 2026-09-27 at version 2. The six
capability offers they compose (`OFFER-PM-001`, `OFFER-TT-001`, `OFFER-BU-001`,
`OFFER-RP-001`, `OFFER-BI-001`, `OFFER-PR-001`) are still `pending`. So
**every live run for `productive` now refuses** with:

    NotApproved: offer OFFER-PM-001 has approval_status='pending', not 'approved'

This was invisible until 2026-09-27 because `offers.load()` itself was raising
`ConfigError` (my regression, fixed at `603afbba`). Fixing the parse made the gate
functional for the first time, and the gate then refused everything. Two agents
found this separately without seeing each other's work.

**Consequence: TASK-425, the one-account dry run, cannot run at all.** Approving A
and B did not unblock it, contrary to the reasonable expectation.

## WHY THE CURRENT BEHAVIOUR IS WRONG, and why that is not obvious

It is genuinely fail-closed, which is the right instinct and why this needs care.
But the scope is wrong in a way that has two bad effects:

1. **Adding any draft offer to the library halts all production.** A library is
   where drafts live. Making the presence of a draft a production outage means the
   library cannot be used for its purpose.
2. **It creates pressure to approve offers nobody intends to use**, purely to clear
   the gate. That is the opposite of what an approval gate is for, and it would put
   six unreviewed capability offers into the approved set to unblock a dry run.

The property actually worth having is: **the offer a run USES must be approved.**
Nothing is gained by validating offers the run never touches.

## WHAT TO BUILD

`_check_offers` validates the offer or offers the run has SELECTED, and refuses if
any of those is not approved.

Design questions to answer explicitly in the result block, not to paper over:

1. **Where does selection happen, and is it before this check?** If selection
   happens after `_check_offers` today, the check has to move or the selection has
   to be passed in. Do not guess: trace it.
2. **Composed offers.** A and B each `composes` several capability offers. Decide
   and justify: does approving a composed offer implicitly approve what it
   composes, or must each composed offer also be approved? The conservative reading
   is that the composed offer is the thing the operator reviewed and approved, and
   its constituents are provenance rather than separately-shippable offers. State
   which reading you implement.
3. **What if NO offer is selected?** That must refuse, not pass. An empty selection
   silently passing the gate is exactly how a fail-closed check becomes fail-open.

## ACCEPTANCE — BY EFFECT

1. A run selecting an APPROVED offer proceeds through `src/generate.py`.
2. A run selecting a PENDING offer raises `NotApproved` naming that offer.
3. **A pending offer elsewhere in the library that the run does not select does NOT
   block the run.** This is the behaviour change; assert it directly.
4. A run with NO offer selected REFUSES.
5. MUTATION: make the check pass unconditionally, and a test must fail. If the
   suite stays green with the gate disabled, the tests are not testing the gate.
6. MUTATION: restore the whole-library iteration, and the test for acceptance 3
   must fail.
7. Suite: diff the failing-name SET against
   `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 named failures). The 228-failure
   09-27 file is NOT a baseline; the operator refused it. A new failure in any
   safety module BLOCKS.

## WHAT THIS TASK MAY NOT DO

- **Do not approve, retire or alter any offer.** Approval is the operator's, and
  Claude has approved nothing. `approval_status` values are not yours to change.
- Do not weaken the gate for a non-live caller, for a test, or for a dry run. An
  earlier attempt on TASK-400 keyed an offer bypass on `not live`, which weakened
  the gate for every non-live caller; it was corrected to an explicit
  `allow_pending_offers` parameter. Learn from it: any bypass is explicit, named,
  and never inferred from an unrelated flag.
- No send, activate, resume, enrol or attach. Provider writes ZERO. Freeze stands.
- Do not edit `src/generate.py` beyond what the call site requires — TASK-400 is
  active there and its branch is `worktree-agent-a88cf873fc4570da2`.

## THE ALTERNATIVE THE OPERATOR MAY CHOOSE INSTEAD

Approve or retire the six capability offers. If that is the decision, this task is
not needed and should be closed rather than implemented. Claude's recommendation is
this task, because it fixes the scope rather than changing what is licensed for
prospect-facing copy.
