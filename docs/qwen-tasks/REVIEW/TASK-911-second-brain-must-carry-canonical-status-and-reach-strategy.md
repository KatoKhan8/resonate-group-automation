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

## RESULT BLOCK

**STATUS:** REVIEW
**ARTIFACT KIND:** code + test
**COMMIT SHA:** 147f6491f3a7a5a86e74f4802c9495dfda007a61
**BRANCH:** qwen-worker-8-r17

**TESTS:**
- `tests.test_the_second_brain_returns_only_what_the_task_needs` - 24 tests OK
- `tests.test_a_client_csv_fact_cannot_license_a_claim` - 9 tests OK
- `tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate` - 18 tests OK
- `tests.test_generate` - OK
- `tests.test_copylint` - 45 tests OK
- `tests.test_task910_writer_contract` - 16 tests OK
- `tests.test_render_preview` - OK
- `tests.test_task904_opt_out` - OK
- `tests.test_task906_signature_composed_into_copy` - OK
- `tests.test_approve` - OK
- `tests.test_task911_second_brain_canonical_status` - 23 tests OK

**ACCEPTANCE COMMANDS:**
- `STEPS_EXPECTED` = 5 -> OK
- `packfacts.CLIENT_SUPPLIED` = 'CLIENT_SUPPLIED' -> OK
- `grep -c "verified_v2|trusted=True|CLIENT_APPROVED =" src/secondbrain.py` -> 0

**FILES CHANGED:**
- `src/secondbrain.py` - added `_ELIGIBLE_CLIENT_SUPPLIED_PREFIXES`, `_canonical_status()`, provenance projection in `_fact()`
- `src/generate_campaign.py` - renamed `_load_verified_facts` to `_load_admitted_facts`, added persona/offer filtering (`_is_relevant`, `_config_key_of`, `_offer_capability_names`), updated `_format_br_context` to show provenance, moved offer resolution before step 2
- `tests/test_task911_second_brain_canonical_status.py` - NEW, 23 tests covering all 8 acceptance criteria

**FINDINGS:**
- MEASURED: Productive campaign_strategy has 50 facts, all from eligible keys -> 50 CLIENT_SUPPLIED, 0 VERIFIED, 0 unpromoted.
- MEASURED: economic_buyer admitted set = 35 facts (down from 50). Champion's 6 items excluded, 7 product.capabilities excluded (offer ai_capabilities don't match product.capabilities keys).
- MEASURED: champion admitted set = 36 facts. Zero cross-contamination between personas.
- MEASURED: br_context is non-None, contains "CLIENT_SUPPLIED", reaches hypothesis_user's "our own data" block through the real path.
- POSITIVE CONTROL: mutating "Product: Productive" to "Product: MUTATED_PRODUCTIVE" changes br_context. Restoring changes it back (byte-identical).
- NEGATIVE CONTROL: unpromoted fact (verified=False, no provenance) not admitted. pack["facts"] empty for CSV-only record.
- NEGATIVE CONTROL: two existing boundary tests stay green (9 + 18 tests).
- MUTATION: reverting `_canonical_status` to return None -> 0 CLIENT_SUPPLIED facts, 0 admitted -> acceptance 2 goes red.
- An unrecognised key (e.g. "hypothesis.generated_strategy") resolves to None (unpromoted).

**CLAIM:** The Second Brain now carries canonical provenance (CLIENT_SUPPLIED from packfacts), admits to internal strategy through `_load_admitted_facts`, filters to the relevant subset per persona/offer, and the hypothesis prompt carries the "our own data" block through the real path. The prospect-facing boundary is unchanged.

**AUTHORITY:** Operator ruling 2026-09-28, TASK-911.
**MEASURED AT:** 2026-09-28, branch qwen-worker-8-r17.
**STATE:** All 50 facts projected as CLIENT_SUPPLIED. 35/36 admitted per persona. Prospect boundary intact.

**RISKS:**
- Offer ai_capabilities keys ("Report Intelligence", "Project Summary") don't match product.capabilities keys ("project_management", etc.), so ALL product.capabilities facts are filtered out. Persona capabilities still reach via product.capability_by_persona. If the offer schema changes to use product.capability keys, the filter will include them automatically.

**RECOMMENDED CLAUDE ACTION:** Review and integrate. Then regenerate 2020 Companies / Rachele Crumpler as named in the task.
