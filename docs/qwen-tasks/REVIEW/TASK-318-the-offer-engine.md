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

## RESULT BLOCK

**STATUS:** DONE
**ARTIFACT KIND:** code (wiring) + test (pre-existing, verified green)

**COMMIT SHA:** 80f00462
**TESTS:**
- `py -3 -m unittest tests.test_an_offer_cannot_be_invented` — 11 tests, OK
- `py -3 -m unittest tests.test_the_second_brain_returns_only_what_the_task_needs` — 24 tests, OK
- `py -3 -m unittest tests.test_task911_second_brain_canonical_status` — 41 tests, OK
- Acceptance command: `5 gaps listed for the operator` — PASS
- TASK-317 acceptance command with offers wired: PASS
- Pre-existing failures in `test_invariants` (3 tests, `providers/__init__.py:376`) confirmed on stashed baseline — NOT introduced by this change

**FILES CHANGED:**
- `src/secondbrain.py` — wired `_offers()` to serve facts from `offers.load()`, removed "offers" from `MISSING_SECTIONS`, added "offers." to `_CLIENT_SUPPLIED_KEY_ROOTS`, removed "Offer library" from index page missing items

**FILES ALREADY PRESENT (not changed by this task):**
- `src/offers.py` — the offer engine (load, for_campaign, missing, NotApproved, messaging_rules)
- `config/clients/productive-offers.yaml` — 8 offers (6 capability + 2 composed), 5 missing gaps, evidence, mechanisms
- `tests/test_an_offer_cannot_be_invented.py` — 11 tests covering all four false-pass guards

**CALLER CHAIN (verified, not just defined):**
- `secondbrain._offers()` → `_offers_engine.load()` → reads YAML
- `bisonfactory.py:806` → `offers.messaging_rules()`
- `claims.py:1314` → `offers.missing()`
- `generate.py:2394` → `offers.messaging_rules()`
- `generate_campaign.py` → `offers.load()` (via `_check_offers`)

**FINDINGS:**
- `src/offers.py`, `config/clients/productive-offers.yaml` and `tests/test_an_offer_cannot_be_invented.py` were already present on this branch from prior work. The only missing piece was wiring `secondbrain._offers()` to serve the offer section instead of returning `[]`.
- The `_offers()` function now emits 3 facts per offer (value proposition, deliverable, approval status) = 24 facts for 8 offers.
- All offer facts carry `source=config/clients/productive.yaml offers.<id>.<field>` and `canonical_status=CLIENT_SUPPLIED`.

**RISKS:** None introduced. The change is additive — `_offers()` went from returning `[]` to returning data from the already-validated offer engine.

**RECOMMENDED CLAUDE ACTION:** Review and integrate. The offer engine is now wired into the Second Brain retrieval layer.
