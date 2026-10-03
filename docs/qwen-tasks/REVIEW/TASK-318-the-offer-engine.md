PRIORITY: P0
SIZE: M
DEPENDS: TASK-317

# TASK-318 — the Offer Engine, gaps listed rather than invented

Phase 1 task 2. Read `docs/PHASE1-PLAN-2026-09-26.md` first.

`src/secondbrain.py` is on master and its `offers` section currently reports
MISSING. This task fills it.

## Files

    src/offers.py                          NEW
    config/clients/productive-offers.yaml  NEW, offers only
    src/secondbrain.py                     MODIFY, serve the offer section
    tests/test_an_offer_cannot_be_invented.py  NEW

## Build

Schema from spec 3E: offer id, segment, persona, business problem, value
proposition, **concrete deliverable**, supporting evidence, CTA, conditions,
approval status, version, campaigns using it.

**Ships with the six confirmed capabilities and nothing else**, in the
client's own words from `product.capabilities`: project_management,
time_tracking, budgeting, resource_planning, billing, profitability.

**Two offers per campaign WHERE APPROVED TERMS EXIST.** Where they do not, the
campaign carries one and the gap is listed. A campaign is not blocked for want
of a second offer; it is honest about having one.

`offers.missing()` returns what the client must supply. Seed it with what is
already known absent: no customer case studies, no verified benchmarks, no
dashboard or workflow example, no calculator, no demo link.

## The rule this task exists to enforce

**An offer whose `approval_status` is not `approved` CANNOT reach copy
generation.** A refusal, not a warning, in the same shape as `reviewapproval`:
production does not approve its own offers.

**Offers are DATA. No model creates one.** A test must assert that no code
path builds an offer from an LLM response.

## Acceptance

    py -3 -c "import sys;sys.path.insert(0,'.');from src import offers;\
    ok=False
    try: offers.for_campaign(503, require_approved=True)
    except offers.NotApproved: ok=True
    assert ok, 'an unapproved offer reached a campaign'
    print(len(offers.missing()),'gaps listed for the operator')"

plus `py -3 -m unittest tests.test_an_offer_cannot_be_invented`.

## FALSE PASS

- An offer naming a capability Productive does not have.
- An invented deliverable, discount, guarantee or commercial term.
- `approval_status` defaulting to approved.
- `missing()` returning empty while no case study exists.

Close with the section 11 report, pushed, remote SHA verified.

## RESULT

- **STATUS:** DONE
- **ARTIFACT KIND:** code (secondbrain wiring) + test (pre-existing)
- **COMMIT SHA:** 654bc355
- **TESTS:**
  - `py -3 -m unittest tests.test_an_offer_cannot_be_invented` — 11 tests, OK
  - `py -3 -m unittest tests.test_the_second_brain_returns_only_what_the_task_needs` — 24 tests, OK
  - Acceptance criterion 1: `5 gaps listed for the operator` — PASS
  - Acceptance criterion 2: `py -3 -m unittest tests.test_an_offer_cannot_be_invented` — PASS
- **FILES CHANGED:**
  - `src/secondbrain.py` — wired `_offers()` to serve offer facts from `offers.load()` and `offers.missing()`; removed `"offers"` from `MISSING_SECTIONS`; updated index page missing-item text; client-scoped so non-productive clients get `[]`
- **FINDINGS:**
  - `src/offers.py`, `config/clients/productive-offers.yaml`, and `tests/test_an_offer_cannot_be_invented.py` were already on master from prior work. This task's remaining work was wiring `secondbrain.py` to serve the offer section.
  - Callers verified: `secondbrain.py` (offers.load, offers.missing), `bisonfactory.py` (offers.messaging_rules), `claims.py` (offers.missing), `generate.py` (offers.messaging_rules), `generate_campaign.py` (offers.load referenced in comments).
  - Four false-pass guards all hold: no invented capability, no invented deliverable, approval_status never defaults to approved, missing() returns 5 gaps.
- **RISKS:** None identified. The wiring is additive; no existing behaviour changes.
- **RECOMMENDED CLAUDE ACTION:** Accept and merge.
