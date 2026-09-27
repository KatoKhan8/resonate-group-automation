# BRIEF — TASK-427: `_check_offers` validates the SELECTED offer

**NOT A POOL TASK. CLAUDE ONLY, critical path.** It lives here rather than in
`docs/qwen-tasks/TODO/` because a header line naming an owner is not an access
control — learned three times in one night. The pool copy is `STATUS: BLOCKED`.

**Dispatch the moment `TASK-400` merges**, because the fix is in
`src/generate_campaign.py`, the file `task400-rework3` owns until then.

## WHY THIS IS THE LAST THING BETWEEN US AND THE ARTIFACT

**Measured 2026-09-28 01:30 by running it, not by reading it:**

    generate_campaign.generate("productive", acct, [], live=False)
      -> NotApproved: offer OFFER-PM-001 has approval_status='pending',
                      not 'approved'
      provider requests: []

`_check_offers(client_name)` is **step 1 of `generate()` and does NOT gate on
`live`**, so a DRY RUN refuses too. **`TASK-425` therefore cannot run at all until
this lands** — the one-account artifact is blocked on it, and approving Offers A
and B did not unblock it, contrary to reasonable expectation.

The operator's decision 5, 2026-09-27, reaffirmed the same evening: **only the
offer selected for that prospect is validated, not every offer in the system.**

Measured, so the record carries the number rather than the belief: `offers.load()`
returns **8 offers, 2 approved** (`OFFER-A-ECONOMIC-BUYER`, `OFFER-B-OPERATIONS`)
and **6 pending** — the capability offers A and B compose. Read through the real
entrypoint, never by parsing the YAML a second way; a validator that accepts more
than production proves nothing, which is how `offers.load()` was broken once this
week.

**The six pending offers are CORRECT.** They are composed by A and B, nobody
selected them, and approving them to clear this gate would be approving six
offers nobody reviewed. That is the pressure this defect creates and the reason
the scope is what is wrong, not the approvals.

## WHAT TO BUILD

`_check_offers` validates the offer or offers the run has **SELECTED**, and
refuses if any of those is not approved.

Answer these in the result rather than papering over them:

1. **Where does selection happen, and is it before this check?** If selection
   happens after `_check_offers` today, the check moves or the selection is passed
   in. Trace it; do not guess.
2. **Composed offers.** A and B each compose several capability offers. State and
   justify which reading you implement. The conservative one: the composed offer
   is what the operator reviewed and approved, and its constituents are provenance
   rather than separately shippable offers.
3. **No offer selected must REFUSE.** An empty selection passing silently is
   exactly how a fail-closed check becomes fail-open, and it is the likeliest way
   to get this wrong.

## ACCEPTANCE — BY EFFECT

1. A run selecting an APPROVED offer proceeds through `src/generate.py`.
2. A run selecting a PENDING offer raises `NotApproved` **naming that offer**.
3. **A pending offer elsewhere in the library that the run does not select does
   NOT block the run.** This is the behaviour change — assert it directly.
4. A run with NO offer selected REFUSES.
5. MUTATION: make the check pass unconditionally; a test must fail. If the suite
   stays green with the gate disabled, the tests are not testing the gate.
6. MUTATION: restore the whole-library iteration; the test for item 3 must fail.
7. **Then prove the point of the whole task:** `generate(..., live=False)` for
   `productive` no longer refuses at `OFFER-PM-001`. That is the measurement above,
   inverted, and it is what unblocks `TASK-425`.

## WHAT THIS MAY NOT DO

- **Do not approve, retire or alter any offer.** Approval is the operator's;
  `approval_status` values are not yours to change, and
  `config/clients/productive-offers.yaml` is the canonical record of an operator
  decision.
- **Do not weaken the gate for a non-live caller, a test, or a dry run.** An
  earlier TASK-400 attempt keyed an offer bypass on `not live`, which weakened the
  gate for every non-live caller. Any bypass is explicit, named, and never
  inferred from an unrelated flag — and a dry run must still refuse an unapproved
  SELECTED offer, because a dry run executes the real decision path.
- No send, activate, resume, enrol or attach. Provider writes ZERO. Freeze stands.
  `sending.live` stays off for productive.

PROTECTED PROOFS, all must still pass: `test_a_client_supplied_figure_licenses_no_claim_in_either_gate`
(18) · `test_a_client_csv_fact_cannot_license_a_claim` (9) · `test_compliance_gate`
(34) · `test_one_plan_decides_both_providers` (11) ·
`test_lead_writes_respect_the_killswitch` (5) ·
`test_staging_hands_the_sequence_gate_its_inputs` (12) ·
`test_sending_live_off_blocks_only_our_new_writes` (6) · `test_generate` (51).

SUITE: the baseline is a LIST of 128 NAMED failures. Diff NAMES with
`scripts/suite_baseline.py`, normalising both sides (`normalise_test_name` in
`scripts/glm_verify_branch.py`). **Eight names are known to be master's, not
yours**: the four baseline gaps (`test_an_offer_cannot_be_invented`, two
`test_fixture_hygiene`, one `test_the_cadence_reacts_to_what_the_prospect_did`),
the three order-dependent ones, and — if TASK-400 has landed —
`test_changing_an_approved_fact_changes_the_output`. Report; never adopt a new
baseline; do not edit that file. 228 is not a baseline and neither is 197.
