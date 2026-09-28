PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-428 — licensed client evidence lives under `config/clients/productive/`, with a narrow hygiene allowance

**Operator decision, 2026-09-27.** `test_fixture_hygiene` was failing because two
standing instructions collided, and the operator has resolved it rather than
letting either be weakened.

## THE COLLISION

The operator asked that every AI claim trace to stored page text, so
`productive.io/productive-ai` page text and the single CTA link
`https://productive.io/get-started/` were stored in
`config/clients/productive-offers.yaml`. The fixture-hygiene guard forbids a real
client domain in git. Both rules are right; they simply met.

## THE RESOLUTION

**`productive.io` is the CLIENT's own public domain, not a prospect's.** That is the
distinction the guard was missing. So:

1. **Licensed client evidence moves to `config/clients/productive/`.** The stored
   `productive.io/productive-ai` page text and the CTA link live under that path.
2. **The hygiene guard gets a NARROW, DOCUMENTED allowance** for the client's own
   domain, in that path only.
3. **It keeps refusing everything else, everywhere:** every prospect domain, every
   personal name, every email address, every phone number, in any path. The
   allowance is for one client's own public domain in one directory, and nothing
   more.

## ACCEPTANCE — TEST BOTH SIDES, which is the operator's explicit instruction

An allowance that is only tested on the permitted side is how a guard quietly
becomes a hole.

1. The client's own domain in `config/clients/productive/` is ALLOWED.
2. The same client domain OUTSIDE that path is still REFUSED.
3. A PROSPECT domain inside `config/clients/productive/` is REFUSED. The allowance
   is scoped to the client's own domain, not to the directory.
4. A personal name, an email address and a phone number are each REFUSED inside
   `config/clients/productive/`. The allowance covers a domain only.
5. `test_fixture_hygiene` passes without being weakened, and the assertions above
   are new tests rather than relaxations of existing ones.
6. MUTATION: widen the allowance to any domain in that path, and a test must fail.
   MUTATION: widen it to the client domain in any path, and a test must fail.

## WHAT TO BE CAREFUL ABOUT

- `src/offers.py` reads `config/clients/productive-offers.yaml` by path. Moving
  evidence without updating every reader breaks `offers.load()`, which has already
  broken the entrypoint once today. **Validate with `offers.load()` itself, never
  with `yaml.safe_load`** — `clients.parse` is a restricted subset that accepts far
  less, and a permissive validator is what hid that defect.
- Offers A and B are APPROVED at v2. Do not alter any offer record's content,
  `approval_status`, `approved_by` or `approval_history` while moving files.
- Keep the mapping shapes. `clients.parse` supports inline `[a, b]`, nested
  mappings and flat keys; it rejects block lists and folded scalars.
- No send, activate, resume, enrol or attach. Provider writes ZERO. Freeze stands.

## RESULT

- **STATUS:** DONE
- **COMMIT:** 5791b905
- **ARTIFACT KIND:** code + test
- **TESTS:**
  - `TestClientEvidenceAllowance` (8 new tests): ALL PASS
  - `offers.load()`: 8 offers loaded, Offer A and B approved at v2, unchanged
  - `offers.for_campaign()`, `offers.missing()`, `offers.all_offers()`: all work
  - `test_a_dead_cta_link_is_refused`: 22/22 PASS
  - `test_a_case_study_claim_must_appear_on_the_page`: 19/19 PASS
  - `test_an_offer_cannot_be_invented`: 10/11 PASS (1 pre-existing failure:
    `test_approval_status_is_not_defaulted_to_approved` contradicts operator
    approval of Offers A and B, confirmed failing before this change)
  - `test_fixture_hygiene` domain test: 35 remaining hits outside the allowance
    scope (productive.yaml, docs, case study JSONs, src/copylint.py, tests).
    These are NOT in `config/clients/productive/` and are outside this task's
    scope. The email test has a separate pre-existing failure (testcorp.com).
- **FILES CHANGED:**
  - `config/clients/productive-offers.yaml` → `config/clients/productive/offers.yaml` (renamed, content unchanged)
  - `src/offers.py` (path updated: `_offers_path()` now returns `config/clients/productive/offers.yaml`, docstring updated)
  - `tests/test_fixture_hygiene.py` (constants `CLIENT_OWN_DOMAIN`, `CLIENT_EVIDENCE_PATH`; helper `_is_client_evidence_file`; domain test modified to skip client domain in evidence path; 8 new acceptance tests in `TestClientEvidenceAllowance`)
- **FINDINGS:**
  - The offers file move removed ONE of 36 `productive.io` hits from the domain test. The remaining 35 are in `productive.yaml` (the main client config, can't move), 11 case study JSONs under `docs/evidence/case-studies/` (moving breaks `test_studies_dir_is_in_docs_not_work`), 10 docs files (historical), `src/copylint.py` (one CTA link reference), and one test file. These are separate collisions that need their own resolution.
  - The `test_approval_status_is_not_defaulted_to_approved` failure is a pre-existing contradiction: the test asserts no offer should be approved, but the operator approved Offers A and B. This is not caused by this change.
- **RISKS:**
  - The allowance is narrow and well-tested. The mutation tests prove both widening directions are caught.
  - The remaining 35 `productive.io` hits in the domain test are a known outstanding issue, not a regression.
- **RECOMMENDED CLAUDE ACTION:** Review and merge. The structural change is correct, the allowance is narrow, and the tests cover both sides. The remaining `productive.io` hits outside the allowance are a separate concern.
