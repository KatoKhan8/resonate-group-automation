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

STATUS: DONE

COMMIT SHA: 2370abdd (verified on origin/qwen-worker-3-r9)

TESTS:
- `py -3 -m unittest tests.test_an_offer_cannot_be_invented` — 11 tests, OK
- `py -3 -m unittest tests.test_the_second_brain_returns_only_what_the_task_needs` — 10 tests, OK
- Acceptance criteria: `5 gaps listed for the operator`, NotApproved raised for campaign 503
- Pre-existing failures in test_invariants (emailbison routes, reviewapproval checklist) confirmed unrelated by running them against pre-change HEAD

FILES CHANGED:
- `src/offers.py` — NEW. Offer engine: load(), for_campaign(), missing(), all_offers(). NotApproved exception. CONFIRMED_CAPABILITIES frozenset. No LLM import.
- `config/clients/productive-offers.yaml` — NEW. Six offers (one per capability), all approval_status: pending. Five gaps in missing section.
- `src/secondbrain.py` — MODIFY. Removed "offers" from MISSING_SECTIONS. _offers() now reads from offers module. Index page updated.
- `tests/test_an_offer_cannot_be_invented.py` — NEW. 11 tests covering: no LLM import, approval refusal, no invented capability, missing non-empty, full schema.

FINDINGS:
- Caller chain: `offers` is consumed by `secondbrain._offers()` (src/secondbrain.py:27,154,162). `secondbrain` is consumed by its test (TASK-317). Production wiring of secondbrain into the copy path is TASK-321's job.
- All six offers are `approval_status: pending`. No offer can reach copy generation until the operator explicitly approves.
- Campaign 503 has two offers assigned (OFFER-PM-001, OFFER-TT-001), both pending.
- The YAML uses dict-of-dicts format (not block lists) to work with the existing clients.parse() parser.

RISKS:
- None identified. The module is additive; removing it returns secondbrain to its previous state.

RECOMMENDED CLAUDE ACTION:
- Review and integrate. The offer library is ready for the operator to approve individual offers by changing `approval_status: pending` to `approval_status: approved` in productive-offers.yaml.
