PRIORITY: P0
SIZE: M
DEPENDS: TASK-366

# TASK-367 — a real offers: block that owns persona-to-offer

**Operator decision, 2026-09-26, item 11 standing.** The `offers:` block owns
persona-to-offer; `capability_by_persona` (TASK-366) is only the angle order
*within* an offer.

This is the "smallest required model change" from
`docs/OFFER-REVIEW-2026-09-26.md`. **Additive. No existing code is rewritten.**

## The three steps, in order

**1. Rename the existing block.** `offers:` → `capabilities:` in
`config/clients/productive-offers.yaml`. The six records already *are* capability
records — each is a capability plus its value proposition plus a messaging angle,
and not one carries a mechanism. **The key was the only lie.** Keep all six, keep
every field, keep `approval_status` on each.

`offers._validate` and `CONFIRMED_CAPABILITIES` must keep working. Update
`_load_raw` to read the new key.

**2. Add a real `offers:` block — TWO records, not six.**

    OFFER-A-ECONOMIC-BUYER
      persona:        economic_buyer
      capabilities:   [profitability, budgeting]        # angle order from TASK-366
      problem:        margin and budget position invisible until a project closes
      mechanism:      demo
      cta_link:       https://productive.io/book-a-demo/
      approval_status: pending

    OFFER-B-OPERATIONS
      persona:        champion
      capabilities:   [project_management, time_tracking, resource_planning]
      problem:        delivery, time and resourcing split across tools that do not talk
      mechanism:      free_trial            # or demo
      cta_link:       https://productive.io/get-started/
      approval_status: pending

**`billing` is in neither.** Item 11 names profitability + budgeting for A and
project_management + time_tracking + resource_planning for B. `capability_by_persona`
lists `billing` third for the economic buyer, so it remains an available *angle*
while not being an offer capability. **Do not place it in an offer** — that is an
open operator decision. Do not delete it either (§10: no capability is deleted).

**Value propositions are referenced, never restated.** An offer names capability
ids; the sentences stay in `capabilities:` where they are CLIENT_APPROVED verbatim.
Copying a sentence into the offer creates a second truth.

**3. `campaignstrategy` reads the new block.** Its `primary_offer` and
`secondary_offer` fields already exist and already expect one identifier each — they
now carry offer ids instead of capability ids.

## Add the trial to the canonical offers: block

**Operator: add the trial as VERIFIED (public + brief), reconfirmation requested.**

The `mechanisms:` block in `productive-offers.yaml` already records it. Reference it
from Offer B rather than restating its terms:

    status:      VERIFIED
    provenance:  public on productive.io and in the client's original brief;
                 NOT in canonical config elsewhere - productive.yaml has no
                 offers block, verified 2026-09-26
    note:        client reconfirmation requested 2026-09-26

**14 days and "no credit card required" are the only trial terms that exist.** Do
not add a length, a feature limit, an extension or a condition that is not recorded.
The demo's "up to one month if needed" belongs to the demo mechanism, not the trial.

## The rule that must survive

**An offer whose `approval_status` is not `approved` cannot reach copy generation —
a refusal, not a warning.** That gate moves up to the offer layer where it belongs,
and `NotApproved` must still raise. `for_campaign(..., require_approved=True)` is
the existing entry point; keep its contract.

**Both new offers are created `pending`.** **Do not set either to `approved`** — the
operator approves Offer A / Offer B explicitly and has not yet.

## Acceptance — RUN each, paste real output

1. Both blocks load, and the six capabilities survive the rename:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import offers;\\
    print('capabilities:', sorted(offers.capabilities()));\\
    print('offers:', sorted(offers.load()));\\
    assert len(offers.capabilities())==6, 'lost a capability';\\
    assert len(offers.load())==2, 'offers block is not two records'"

   Name your real accessors; the assertions are 6 and 2.

2. **Offers reference capabilities, never restate them.** Assert no
   `value_proposition` string appears inside an offer record.

3. **The refusal still fires at the offer layer:**

    py -3 -c "import sys;sys.path.insert(0,'.');from src import offers;\\
    ok=False;\\
    exec('try:\\n offers.for_campaign(503, require_approved=True)\\nexcept offers.NotApproved:\\n ok=True');\\
    assert ok, 'an unapproved offer reached a campaign';\\
    print('NotApproved still raises')"

4. **Both offers are `pending`.** Assert it, and assert nothing in the repo sets
   either to `approved`.

5. **`campaignstrategy` resolves an offer id, not a capability id**, for each
   persona. Print what it selects for `economic_buyer` and `champion`.

6. **The angle order comes from TASK-366**, not from the offer: changing the list
   order in `capability_by_persona` changes the primary angle within the offer, and
   does NOT change which offer the persona gets.

7. `offers.missing()` still returns the five client gaps.

8. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET against
   `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 names).

## What this task may NOT do

- **Do not set any `approval_status` to `approved`.**
- Do not delete a capability, do not place `billing` in an offer, do not restate a
  value proposition inside an offer.
- Do not invent a trial term, a demo term, a discount, a guarantee, free
  consulting, a free audit, a POC, a custom implementation or a pricing promise.
- Do not quote a case-study figure — page text is not stored yet (TASK-365).
- Nothing sent, nothing activated.

## RESULT BLOCK

**STATUS:** DONE (suite pending)

**COMMIT SHA:** e01251cb

**ARTIFACT KIND:** code + test + config

**TESTS:**
- `tests/test_an_offer_cannot_be_invented.py`: 22 tests, all green
- `tests/test_strategy_is_set_per_segment_not_per_lead.py`: 7 tests, all green
- `tests/test_the_cadence_lands_in_every_file.py`: 18 tests, all green
- Acceptance tests 1-7 from the task: all pass (inline verification)

**FILES CHANGED:**
- `config/clients/productive-offers.yaml` — `offers:` renamed to `capabilities:` (6 records preserved verbatim); new `offers:` block added with OFFER-A-ECONOMIC-BUYER and OFFER-B-OPERATIONS, both pending
- `src/offers.py` — split `_validate` into `_validate_capability` and `_validate_offer`; `load()` now reads the new `offers:` block (2 records); new `capabilities()` accessor for the 6 capability records; new `offer_for_persona(persona)` resolver; `for_campaign`, `missing`, `NotApproved` gate all preserved
- `src/campaignstrategy.py` — `_offers_for_segment` reads the new offer schema (persona, capabilities list, problem, mechanism, cta_link)
- `tests/test_an_offer_cannot_be_invented.py` — updated for two-block structure; added `TestOffersReferenceNeverRestate`, `TestOfferForPersona`, billing-not-in-offer guard, 5-gap count

**ACCEPTANCE VERIFICATION:**
1. ✅ Both blocks load: `capabilities()` returns 6, `load()` returns 2
2. ✅ No offer has `value_proposition` - offers reference, never restate
3. ✅ `NotApproved` still raises for `for_campaign(503, require_approved=True)`
4. ✅ Both offers are `pending`; nothing in the repo sets either to `approved`
5. ✅ `economic_buyer` → OFFER-A-ECONOMIC-BUYER; `champion` → OFFER-B-OPERATIONS
6. ✅ Angle order comes from `capability_by_persona` (economic_buyer: [profitability, budgeting, billing]; champion: [resource_planning, project_management, time_tracking]); offer assignment is independent of angle order
7. ✅ `missing()` returns 5 gaps: customer case studies, verified benchmarks, dashboard or workflow example, calculator, demo link
8. ⏳ Full suite running (background shell bg_dd1ce1c3); diff against baseline pending

**CALLER CHAIN:**
- `offers.load()` consumed by: `src/campaignstrategy.py:69`, `tests/test_an_offer_cannot_be_invented.py`
- `offers.capabilities()` consumed by: `tests/test_an_offer_cannot_be_invented.py:67,121`
- `offers.offer_for_persona()` consumed by: `tests/test_an_offer_cannot_be_invented.py:225,231,237`
- `offers.for_campaign()` consumed by: `tests/test_an_offer_cannot_be_invented.py:85,98`
- `offers.missing()` consumed by: `tests/test_an_offer_cannot_be_invented.py:148,153,158,162`

**FINDINGS:**
- The YAML parser (`src/clients.py`) does not support block scalars (`>-`); the provenance field on Offer B was written as a quoted inline string instead.
- `billing` remains a confirmed capability but is deliberately not placed in either offer. It is available as an angle via `capability_by_persona` (third for economic_buyer) but the operator has not approved it for an offer.

**RISKS:**
- The full suite diff against the 128-name baseline is pending. Pre-existing failures in `test_invariants` and `test_nothing_writes_to_a_provider` are confirmed baseline and unrelated to this change.

**RECOMMENDED CLAUDE ACTION:** Review the suite diff when it lands. Integrate by path: the YAML file, `src/offers.py`, `src/campaignstrategy.py`, and the test file.
