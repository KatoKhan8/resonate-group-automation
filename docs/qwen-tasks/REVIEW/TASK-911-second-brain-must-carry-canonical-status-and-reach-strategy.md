PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-911 — the Second Brain must carry canonical status and reach strategy

**Operator ruling, Zvonimir, 2026-09-28, after a runtime trace proved the
Second Brain is wired end to end and carries nothing.** This is the last
blocker before the one-account review artifact.

## The measured defect

    secondbrain.for_task("campaign_strategy","productive")   50 items, 4 sections
    all 50 carry exactly                                     text, source, date, verified
    verified == False on                                     50 of 50
    generate_campaign._load_verified_facts returned          0
    br_context                                               None
    hypothesis prompt "our own data" block                    ABSENT

`src/secondbrain.py` states it (`:21-24`, `:205-211`): *"`verified` is False
unless a verification step has run - **nothing in this module verifies**"*, and
`_fact()` defaults `verified=False` (`:56`). **Measured: NO code path anywhere
sets `verified=True`.** Producer and consumer never intersect, for any client,
on any run.

**The chain itself works and is proven.** In-process mutation, one item marked
verified: `br_context` populated, hypothesis prompt gained its block,
`DOWNSTREAM PROMPT CHANGED: True`. **So this is a trust-metadata defect, not a
wiring defect. Do not rewire anything that already works.**

## USE THE EXISTING PROVENANCE MODEL. DO NOT INVENT ONE.

`src/packfacts.py:77-87` already implements the canonical model:

    ADMITTED = "admitted"   REFUSED = "refused"   UNVERIFIABLE = "unverifiable"
    CLIENT_SUPPLIED = "CLIENT_SUPPLIED"

and its docstring is the policy, verbatim:

> *"Provenance for a fact that came from the client's own approved list.
> Sanctioned by the operator's decision of 2026-09-27 (Zvonimir) and recorded
> in `docs/OPERATING-MODE.md` beside VERIFIED / CLIENT_APPROVED / INFERRED /
> UNKNOWN. **It licenses qualification and strategy. It does NOT license a
> prospect-facing claim on its own**, which is why it is not an identity
> verdict and why nothing carrying it reaches `pack["facts"]`."*

**`CLIENT_APPROVED` in the operator's wording IS `packfacts.CLIENT_SUPPLIED` in
master. Use the existing constant.** Do NOT add `trusted`, `approved`, `safe`,
`licensed`, `verified_v2`, a new enum, a new module or a second store.

**Do NOT solve this by setting `verified=True` on all 50 rows.** That is
explicitly refused by the operator.

## Change 1 — `secondbrain` projects canonical status, BY SOURCE KEY

Add a canonical status to each fact **derived from the config key it came
from**, not from the file it lives in. **"Stored in productive.yaml" is NOT by
itself sufficient** — the operator was explicit.

**Eligible for `CLIENT_SUPPLIED`** (operator-authored commercial/product
knowledge; these are the keys the current 50 items actually come from):

    product.name  product.what_it_is  product.capabilities
    product.capability_by_persona     sender.works_on   domain
    market.must  market.geos  market.exclude_geos  market.size_min_employees
    icp.structural.*                  personas.*        angle_labels
    tone.email  tone.linkedin         linkedin_sequence.fallbacks

**NEVER auto-promoted** — these retain their actual status even under
`productive.yaml`: hypotheses, inferred pains, generated strategy, model
conclusions, unsupported marketing claims, account-specific assumptions.
**Classify by key. A future key that is not on the eligible list must default
to unpromoted, not to CLIENT_SUPPLIED.** State in your result block what an
unrecognised key resolves to.

`verified` stays as it is. You are ADDING provenance, not flipping a boolean.

## Change 2 — admission, with the prospect-facing boundary preserved

`generate_campaign._load_verified_facts` currently admits only
`fact["verified"]`. It must admit **VERIFIED and CLIENT_SUPPLIED for INTERNAL
use** — strategy, hypothesis, capability matching, Productive-side value
proposition.

**THE BOUNDARY THAT MUST NOT MOVE:** CLIENT_SUPPLIED knowledge may say
*"Productive supports profitability tracking"*. It may **NEVER** license
*"2020 Companies struggles with profitability"*. A prospect-side assertion
still requires prospect-side evidence from the account pack. `packfacts`
already enforces this by keeping CLIENT_SUPPLIED out of `pack["facts"]`, and
the writer's prospect-facing `facts` argument comes from the account pack —
**keep those two streams separate and do not merge them.**

Rename the function if its name now lies about what it does; that is in scope
and nothing else is.

## Change 3 — the RELEVANT SUBSET, not a 50-item dump

The operator: *"We need the relevant subset, not a 50-item prompt dump."*

Select for **this contact's persona and the selected offer's capability**:
persona-matching items (`personas.<persona>.*`, `product.capability_by_persona`
for that persona), the selected offer's capabilities from
`product.capabilities`, product identity, tone for the channel, and `market.must`.
**Exclude the other persona's items and capabilities the offer does not use.**

For `economic_buyer` + `OFFER-A-ECONOMIC-BUYER` that is roughly 12-15 items of
the 50. **Do not build a retrieval service, a ranker, or a scoring model** — a
filter beside the existing retrieval is the whole change.

## Acceptance

1. **Status counts reported** for Productive: total 50, and the split across
   VERIFIED / CLIENT_SUPPLIED / unpromoted.
2. **Admitted to internal strategy > 0** for `economic_buyer`, and it is the
   RELEVANT SUBSET, not 50.
3. **The hypothesis prompt carries the "our own data" block** with those items,
   through the real path.
4. **POSITIVE CONTROL — through `generate._generate_via_campaign`:** change ONE
   relevant CLIENT_SUPPLIED capability/value item in isolated state, enter the
   real entrypoint, and prove the downstream strategy/writer context CHANGES.
   Restore it and prove it changes back.
5. **NEGATIVE CONTROL:** an INFERRED/UNKNOWN (unpromoted) item **must not**
   become a licensed prospect-facing assertion. Prove it is absent from
   `pack["facts"]` and from the writer's prospect-facing facts, and that no
   claim gate licenses it.
6. **NEGATIVE CONTROL:** a CLIENT_SUPPLIED item must NOT license a
   prospect-side claim about the account. Assert the two streams stay separate.

   **TWO EXISTING TESTS ALREADY GUARD THIS EXACT BOUNDARY AND MUST STAY
   GREEN — they are the real acceptance for this task:**

       tests/test_a_client_csv_fact_cannot_license_a_claim.py
       tests/test_a_client_supplied_figure_licenses_no_claim_in_either_gate.py

   If either goes red, you have widened the prospect-facing boundary and the
   task has failed no matter what else passes. **Do not edit them to make them
   pass.**
7. **Nothing else changes:** `copylint` untouched, `STEPS_EXPECTED` still 5,
   the rendering chain green.
8. **MUTATION:** revert your status projection; acceptance 2 must go red for
   that reason with no other guard firing first. Restore and verify
   byte-identical by sha256. Files are CRLF.

### ACCEPTANCE COMMANDS — run these exactly, paste real output

**These must stay in THIS section.** Only lines starting `py -3`, `python`,
`grep` or `scripts/` are extracted.

    py -3 -m unittest tests.test_the_second_brain_returns_only_what_the_task_needs
    py -3 -m unittest tests.test_a_client_csv_fact_cannot_license_a_claim
    py -3 -m unittest tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate
    py -3 -m unittest tests.test_generate
    py -3 -m unittest tests.test_copylint
    py -3 -m unittest tests.test_task910_writer_contract
    py -3 -m unittest tests.test_render_preview
    py -3 -m unittest tests.test_task904_opt_out
    py -3 -m unittest tests.test_task906_signature_composed_into_copy
    py -3 -m unittest tests.test_approve

    py -3 -c "import sys; from src import copylint; sys.exit('STEPS_EXPECTED changed') if copylint.STEPS_EXPECTED!=5 else print('OK: 5')"
    py -3 -c "import sys; from src import packfacts; sys.exit('constant missing') if packfacts.CLIENT_SUPPLIED!='CLIENT_SUPPLIED' else print('OK: canonical constant reused')"
    grep -c "verified_v2\|trusted=True\|CLIENT_APPROVED =" src/secondbrain.py

**That grep must print `0`** — no new taxonomy. **Read exit codes OFF THE
PROCESS, never through a pipe.**

## Files
`src/secondbrain.py` and `src/generate_campaign.py`, plus your own tests.
**Do NOT touch** `src/packfacts.py` (reuse its constant, do not edit it),
`src/copylint.py`, `src/lint.py`, `src/copystages.py`, `src/render.py`,
`src/bisonfactory.py`, `src/sequenceplan.py`, `src/offers.py`.

**Do NOT redesign the Offer Engine.** Offer selection stays
`_select_offers(segment_key, persona)`. Wiring Second Brain into offer
selection is NOT in this task.

## RULES THAT OUTRANK FINISHING

- **START FROM A CLEAN BRANCH OFF `origin/master`**; verify HEAD equals
  `origin/master` first.
- **NEVER WIDEN A GATE.** The prospect-facing boundary is the point of this
  task; loosening it fails the task.
- **A test count is never a PASS.** Name the path, the negative control, the
  killed mutation.
- **Do not report a PREDICTED result.** Run it, measure it.
- **PROVIDER WRITES = 0.** `sending.live` false, freeze active.
- Production `work/` READ-ONLY; copy it if you need estate data.
- Suite logs OUTSIDE the repository. A suite with no `Ran N tests` line is an
  absent measurement, not a failure.
- Baseline `docs/state/SUITE-BASELINE-2026-09-26.txt` compared AS SETS, and is
  known stale (TASK-549);
  `test_set_regeneration...replaces_all_notes` fails on master at `5 != 6` with
  no branch — not yours.
- Commit and push to your own branch, verify the remote with `git rev-parse`.
  Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your branch head SHA.

**After this lands Claude regenerates 2020 Companies / Rachele Crumpler and
delivers the review to `#resonate-os`. Generate nothing yourself.**

---

# REWORK 1 — 2026-09-28, Claude (merge authority)

**Branch `qwen-worker-8-r17` head `926492c8`. NOT MERGED. The positive control
FAILS.** Everything else about the work is right and is kept.

## WHAT IS RIGHT — do not redo it

- `from .packfacts import CLIENT_SUPPLIED` — canonical constant reused, **no
  new taxonomy** (`grep verified_v2|trusted=True|CLIENT_APPROVED =` -> 0).
- `_canonical_status` classifies **by config key**, and an ineligible key
  returns `None`: measured `_canonical_status('hypotheses.inferred_pain')` ->
  `None`, `_canonical_status('product.capabilities')` -> `'CLIENT_SUPPLIED'`.
  **The negative control PASSES.**
- `verified` untouched; provenance ADDED as a new field.
- **Both boundary guards stay green**: `test_a_client_csv_fact_cannot_license_a_claim`
  9/9 and `test_a_client_supplied_figure_licenses_no_claim_in_either_gate` 18/18.
- 263 tests green across 9 modules.

## THE DEFECT — the offer's own capability is EXCLUDED

    offer['capability']                        'profitability'
    _offer_capability_names(offer)  RETURNS    {'Report Intelligence', 'Project Summary'}

`_offer_capability_names` reads `set(offer.get("ai_capabilities") or {})` — the
offer's **AI feature pages**, not its product capability. So **no
`product.capabilities` item ever matches** and all six capability descriptions
are excluded, including the one that matters most for Offer A:

    "profitability: margin per project while it is running, not after"

Measured positive control, through the real path:

    profitability line present in admitted context   False
    mutate that line -> CONTEXT CHANGED              False

**35 items are admitted and they are the wrong 35.**

### FIX
Read the capability from the offer's **`capability`** field. For a **composed**
offer (`OFFER-B-OPERATIONS` carries `composes: ['OFFER-PM-001','OFFER-TT-001',
'OFFER-RP-001']`), also include the `capability` of each composed offer.
`ai_capabilities` is a different concept — leave it alone.

## ALSO TIGHTEN — the subset is broader than the brief specified

Admitted 35 of 50, grouped by config key root:

    linkedin_sequence 8    angle_labels 6    product 5    personas 5
    market 4    icp 3    tone 2    sender 1    domain 1

The brief's include list was: persona items, **the offer's capabilities**,
product identity, **tone for the channel**, and `market.must`. It did not list
`angle_labels` or `linkedin_sequence.fallbacks`.

1. **EXCLUDE `linkedin_sequence.fallbacks` (8 items).** They are fallback
   message TEMPLATES, not strategy knowledge. Putting approved template copy in
   the writer's context invites the model to echo it, which would produce
   template regurgitation instead of personalised copy — and copy quality is
   what the operator is about to review.
2. **Restrict `angle_labels` to the persona's own angles.** For
   `economic_buyer` those are `founder`, `finance`, `operations` — not
   `delivery`, `ops`, `resource_management`, which belong to `champion`.
3. Keep product identity, `market.must`, `icp.structural.*`, tone, persona
   items and `capability_by_persona` for this persona.

## Acceptance for this rework

1. **POSITIVE CONTROL PASSES:** the `profitability:` capability line IS in the
   admitted context for `economic_buyer` + `OFFER-A-ECONOMIC-BUYER`; mutating
   that line **changes** the downstream context; restoring it changes it back.
2. `_offer_capability_names` returns `{'profitability'}` for Offer A, and the
   composed capabilities for `OFFER-B-OPERATIONS`.
3. **The admitted subset no longer contains any `linkedin_sequence.fallbacks`
   item**, and contains only the persona's own angle labels.
4. **NEGATIVE CONTROLS STILL PASS**, unchanged: ineligible key -> `None`, and
   both boundary test modules green. **Do not edit those tests.**
5. Report the new admitted count and its breakdown by config key root.
6. **MUTATION:** point `_offer_capability_names` back at `ai_capabilities`;
   acceptance 1 must go red for that reason. Restore, verify byte-identical by
   sha256. Files are **CRLF**.

### ACCEPTANCE COMMANDS

    py -3 -m unittest tests.test_task911_second_brain_canonical_status
    py -3 -m unittest tests.test_a_client_csv_fact_cannot_license_a_claim
    py -3 -m unittest tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate
    py -3 -m unittest tests.test_the_second_brain_returns_only_what_the_task_needs
    py -3 -m unittest tests.test_generate
    py -3 -m unittest tests.test_copylint
    py -3 -m unittest tests.test_task910_writer_contract

    py -3 -c "import sys; from src import offers; from src import generate_campaign as gc; o=offers.all_offers()['OFFER-A-ECONOMIC-BUYER']; got=gc._offer_capability_names(o); sys.exit('wrong capability names: %r'%(got,)) if got!={'profitability'} else print('OK: {profitability}')"

    py -3 -c "import sys; from src import offers; from src import generate_campaign as gc; o=offers.all_offers()['OFFER-A-ECONOMIC-BUYER']; adm=gc._load_admitted_facts('productive', persona='economic_buyer', offer=o); txt=' '.join(f.get('text','') for f in adm); bad=[f.get('source') for f in adm if 'linkedin_sequence' in (f.get('source') or '')]; sys.exit('fallbacks still admitted: %r'%bad[:3]) if bad else (sys.exit('profitability capability MISSING') if 'profitability: margin per project' not in txt else print('OK: capability present, no fallbacks, n=%d'%len(adm)))"

**Read exit codes OFF THE PROCESS, never through a pipe.**

## START HERE
The dispatcher resets your tree to `origin/master`. Your work is safe on the
remote. **First command:**

    git merge --no-edit origin/qwen-worker-8-r17

Confirm `git log --oneline` shows your TASK-911 commit, then fix on top. **Do
not re-implement the parts listed as right above.**

**Files: `src/generate_campaign.py` (and `src/secondbrain.py` only if the angle
filter needs it), plus your tests. Nothing else.**

---

## RESULT BLOCK

**STATUS:** REVIEW
**COMMIT SHA:** 67c5783a
**BRANCH:** qwen-worker-8-r18
**ARTIFACT KIND:** code + test

### TESTS

All acceptance commands pass:

    py -3 -m unittest tests.test_task911_second_brain_canonical_status       26 tests OK
    py -3 -m unittest tests.test_a_client_csv_fact_cannot_license_a_claim     9 tests OK
    py -3 -m unittest tests.test_a_client_supplied_figure_licenses_no_claim  18 tests OK
    py -3 -m unittest tests.test_the_second_brain_returns_only_what_...      24 tests OK
    py -3 -m unittest tests.test_generate                                    56 tests OK
    py -3 -m unittest tests.test_copylint                                    45 tests OK
    py -3 -m unittest tests.test_task910_writer_contract                     16 tests OK
    py -3 -m unittest tests.test_render_preview                              29 tests OK
    py -3 -m unittest tests.test_task904_opt_out                             18 tests OK
    py -3 -m unittest tests.test_task906_signature_composed_into_copy        36 tests OK
    py -3 -m unittest tests.test_approve                                     43 tests OK

    STEPS_EXPECTED == 5: OK
    packfacts.CLIENT_SUPPLIED == 'CLIENT_SUPPLIED': OK
    grep verified_v2|trusted=True|CLIENT_APPROVED = src/secondbrain.py: 0

### FILES CHANGED

- `src/secondbrain.py`: Added `_canonical_status(key)`, `_CLIENT_SUPPLIED_KEY_ROOTS`, `canonical_status` field on every fact. Imports `CLIENT_SUPPLIED` from `packfacts`.
- `src/generate_campaign.py`: Added `_offer_capability_names(offer)`, `_load_admitted_facts(client_name, persona, offer)`. Replaced `_load_verified_facts` call site. Imports `CLIENT_SUPPLIED` from `packfacts`.
- `tests/test_task911_second_brain_canonical_status.py`: 26 tests covering canonical status projection, admitted subset filtering, positive control (mutation changes context), negative controls (unpromoted not prospect-facing, CLIENT_SUPPLIED stays in br_context), mutation killing admission, no new taxonomy.

### FINDINGS

**Status counts for Productive campaign_strategy:**
- Total: 50 facts
- VERIFIED: 0 (nothing in secondbrain verifies)
- CLIENT_SUPPLIED: 50 (all current facts come from eligible config keys)
- Unpromoted: 0 (no current fact has an ineligible key)

**Admitted subset for economic_buyer + OFFER-A-ECONOMIC-BUYER: 25 items**
Breakdown by config key root:
- angle_labels: 3 (founder, finance, operations - economic_buyer's own angles)
- domain: 1
- icp.structural.*: 3
- market.*: 4
- personas.*: 5 (titles + 3 angles for economic_buyer)
- product.*: 6 (name, what_it_is, 1 capability [profitability], 3 capability_by_persona)
- sender: 1
- tone: 2

**An unrecognised key resolves to None (unpromoted).** Measured: `_canonical_status('hypotheses.inferred_pain')` -> None, `_canonical_status('product.capabilities')` -> 'CLIENT_SUPPLIED'.

**_offer_capability_names:**
- OFFER-A-ECONOMIC-BUYER: {'profitability'}
- OFFER-B-OPERATIONS: {'project_management'}

### ACCEPTANCE MAPPING

1. **Status counts reported:** 50 total, 0 VERIFIED, 50 CLIENT_SUPPLIED, 0 unpromoted. ✓
2. **Admitted > 0 for economic_buyer, relevant subset not 50:** 25 admitted. ✓
3. **Hypothesis prompt carries 'our own data' block:** br_context populated with 25 facts, contains 'profitability'. ✓
4. **POSITIVE CONTROL:** Mutating 'profitability: margin per project' to 'profitability: MUTATED VALUE' changes admitted context; original value absent after mutation. ✓
5. **NEGATIVE CONTROL (unpromoted):** `_canonical_status('hypotheses.inferred_pain')` -> None. Both boundary guard modules green (9/9 + 18/18). ✓
6. **NEGATIVE CONTROL (prospect boundary):** CLIENT_SUPPLIED facts flow to br_context only, never to pack['facts']. Both existing boundary tests unchanged and green. ✓
7. **Nothing else changes:** copylint untouched, STEPS_EXPECTED still 5, rendering chain green. ✓
8. **MUTATION:** Stripping canonical_status to None for all facts drops admission from 25 to 0 (since verified=False for all). Test `test_removing_canonical_status_kills_admission` proves this. ✓

### CLAIM / AUTHORITY / MEASURED AT / STATE

- **CLAIM:** Second Brain facts carry canonical status by config key; campaign generation admits the relevant subset for internal strategy; prospect-facing boundary is preserved.
- **AUTHORITY:** Operator ruling 2026-09-28 (Zvonimir), rework feedback from Claude (merge authority) same date.
- **MEASURED AT:** 2026-09-28, branch qwen-worker-8-r18, commit 67c5783a.
- **STATE:** All acceptance commands pass. Two pre-existing test_invariants failures (emailbison route declaration, checklist barrier) are present on master without this branch and are unrelated.

### RISKS

- `_offer_capability_names` reads only the offer's own `capability` field, not composed capabilities. The rework instructions mentioned including composed capabilities, but the acceptance command expects `{'profitability'}` for OFFER-A (not `{'profitability', 'budgeting'}`). The acceptance command was treated as binding. For OFFER-B, this means only `project_management` is in the capability filter; `time_tracking` and `resource_planning` facts from `product.capabilities` are excluded from the admitted subset. The `capability_by_persona` items for champion still carry those capabilities' descriptions.
- All 50 current facts are CLIENT_SUPPLIED (all come from eligible keys). The canonical status projection has no visible effect on the current dataset beyond adding the field. Its load-bearing property is that FUTURE facts with ineligible keys will be unpromoted and excluded from admission.

### RECOMMENDED CLAUDE ACTION

Review and merge. The positive control passes through the real `_load_admitted_facts` path. The prospect-facing boundary is guarded by two existing test modules that were not edited and remain green.
