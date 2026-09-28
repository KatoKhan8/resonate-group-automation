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

# REWORK 2 — 2026-09-28, Claude (merge authority). NOT MERGED.

**Branch `qwen-worker-8-r18` head `e5b3f856`. The selector is CORRECT. The call
reaches it with the wrong client name, and a silent catch hides the error.**

## WHAT IS RIGHT — keep all of it

    _offer_capability_names(OfferA)            {profitability}   (was ai_capabilities)
    _load_admitted_facts('productive', ...)    25 items
    profitability capability admitted          TRUE
    linkedin_sequence.fallbacks admitted       0
    angle_labels admitted                      3  (finance, operations, founder)
    mutation of the profitability item         CONTEXT CHANGED, restores cleanly
    packfacts.CLIENT_SUPPLIED reused, no new taxonomy (grep -> 0)

**Both tightenings landed and the in-isolation positive control passes.**

## THE BLOCKER — proven through the real entrypoint

`generate._generate_via_campaign` -> `generate_campaign.generate`:

    client_name passed to _load_admitted_facts   Productive     <-- capitalised
    persona                                      economic_buyer     correct
    offer capability                             profitability      correct
    admitted                                     0                  <-- WRONG

    secondbrain.for_task(campaign_strategy, productive)  -> 50 items
    secondbrain.for_task(campaign_strategy, Productive)  -> RAISES ConfigError:
        "is not a usable client name. Lower case letters, digits ..."

    the record itself carries   rec[client] == productive

So `hypothesis_user` IS called and receives **business_context=None**: measured
`hypothesis_user CALLED: True`, `business_context is None: True`, context
length 0. **The Second Brain still reaches nothing through the real path.**

### AND THE REASON IT WAS INVISIBLE

`_load_admitted_facts` kept the old bare `except (ValueError, Exception):
return []`. **It swallows the ConfigError and reports it as "no facts".** That
breaks the "no silent fallbacks on a safety path" rule: a configuration error
is rendered indistinguishable from an empty brain, which is what let this ship
looking green.

## FIX — two small things, nothing else

1. **Resolve the client SLUG, not the display name.** `client_name` inside
   `generate()` is the config display name (capital P); `secondbrain.for_task`
   requires the slug. The record's own `client` field already holds the slug.
   Prefer an existing canonical slug accessor over blind lower-casing.
2. **Stop swallowing the error.** A ConfigError from `for_task` must not become
   `[]`. Let it surface, or catch it narrowly and record it — an unreadable
   authority is UNKNOWN, never zero. **Do not keep a bare
   `except Exception: return []` on this path.**

## Acceptance — the SAME controls, now through the entrypoint

1. **POSITIVE CONTROL via `generate._generate_via_campaign`:**
   `hypothesis_user` receives a non-None `business_context` CONTAINING
   `profitability: margin per project`. Then mutate that Second Brain item in
   isolated state, re-enter the SAME entrypoint, prove the context CHANGES,
   restore and prove it reverts. **Report measured before/after.**
2. **A wrong client name no longer silently yields zero:** prove a bad/unknown
   client name produces a visible error or a recorded UNKNOWN, not an empty
   list mistaken for "no knowledge".
3. **NEGATIVE CONTROLS unchanged and green** —
   `test_a_client_csv_fact_cannot_license_a_claim` and
   `test_a_client_supplied_figure_licenses_no_claim_in_either_gate`.
   **Do not edit them.**
4. Counts unchanged from rework 1: profitability admitted TRUE, fallbacks 0,
   only this persona's angle labels.
5. **MUTATION:** restore the capitalised name; acceptance 1 must go red for
   that reason. Restore and verify byte-identical by sha256. Files are CRLF.

### ACCEPTANCE COMMANDS

    py -3 -m unittest tests.test_task911_second_brain_canonical_status
    py -3 -m unittest tests.test_a_client_csv_fact_cannot_license_a_claim
    py -3 -m unittest tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate
    py -3 -m unittest tests.test_the_second_brain_returns_only_what_the_task_needs
    py -3 -m unittest tests.test_generate
    py -3 -m unittest tests.test_copylint
    py -3 -m unittest tests.test_task910_writer_contract

    py -3 -c "import sys; from src import generate_campaign as gc, offers; o=offers.all_offers()['OFFER-A-ECONOMIC-BUYER']; n=len(gc._load_admitted_facts('productive','economic_buyer',o)); sys.exit('slug lookup broken') if n==0 else print('OK slug: admitted', n)"

**Read exit codes OFF THE PROCESS, never through a pipe.**

## ALSO FIX — the docstring currently lies about composed offers

`_offer_capability_names` says *"For a composed offer, also includes the
capability of each composed offer"* and **does not do it**. Measured:
`OFFER-B-OPERATIONS` composes `OFFER-PM-001`, `OFFER-TT-001`, `OFFER-RP-001`
whose capabilities are `project_management`, `time_tracking`,
`resource_planning`, and the function returns only `{project_management}`.
**Either implement the composed lookup or correct the docstring** — a function
whose comment describes behaviour it lacks does not stay. Offer A is not
composed, so the current case is unaffected.

## START HERE

The dispatcher resets your tree to `origin/master`. **First command:**

    git merge --no-edit origin/qwen-worker-8-r18

Confirm your TASK-911 commits are present, then fix on top. **Commit every file
you touch — an uncommitted task-doc line blocked three dispatches.**

**Files: `src/generate_campaign.py` (and `src/secondbrain.py` only if needed),
plus your tests. Nothing else.**

---

# REWORK 3 — 2026-09-29, Claude (merge authority). NOT MERGED.

**Branch `qwen-worker-8-r19` head `74a1de4c`. ONE blocker: canonical client
identity. Everything else in rework 2 is accepted and must not change.**

## ACCEPTED — do not touch, do not regress

    Second Brain total                      50
    CLIENT_SUPPLIED                         50
    relevant admitted (economic_buyer/A)    26
    profitability capability admitted       TRUE
    linkedin_sequence.fallbacks admitted    0
    economic_buyer angle_labels             finance, operations, founder
    positive mutation                       context changes, restores cleanly
    negative claim boundary                 9/9 and 18/18 OK, unedited
    silent-fallback                         invalid identity RAISES ConfigError
    composed offers  Offer A {profitability, budgeting}  Offer B {project_management,
                                            time_tracking, resource_planning}
    no new taxonomy/store/service           confirmed

**The operator has ACCEPTED the composed-offer result.** Offer A composes
`OFFER-PR-001` + `OFFER-BU-001`, so `{profitability, budgeting}` is correct.
**Do NOT narrow it to `{profitability}`.**

## THE ONE BLOCKER — identity must not be derived from the display name

Current implementation is REFUSED by the operator:

    def _resolve_client_slug(client_name):
        if clients.valid_slug(client_name) and clients.exists(client_name):
            return client_name
        slug = client_name.lower().strip()        # <-- REFUSED
        ...

**Operator, verbatim:** *"Do NOT derive canonical identity from a display
name. Do NOT use `.lower()`, `casefold()`, `slugify()`, normalization, or
display-name lookup as the authority for client identity."*

**The record already carries the canonical identity:**

    rec["client"] == "productive"          canonical identity
    config display name == "Productive"    presentation only

Measured today through the real path: the value arriving at
`_load_admitted_facts` is `'Productive'`, the config display name.

### FIX — at the call site, not with a normaliser

Make the **canonical slug the record carries** reach `secondbrain.for_task`
directly. `_generate_via_campaign` has `rec` in hand and
`rec.get("client")` is already the slug — it is what
`clients.load(client_name)` is called with at the top of that function. Thread
that canonical value through to `_load_admitted_facts` instead of the display
name derived from the loaded config.

**DELETE `_resolve_client_slug`'s lowercasing entirely.** If a canonical slug
is absent, **do not reconstruct one from display text** — fail explicitly via
the existing fail-closed mechanism (the `ConfigError` that already surfaces is
correct; keep that behaviour).

**Keep** the rework-2 improvement that an unreadable authority RAISES rather
than returning `[]`. That control passes and must keep passing.

## Acceptance — all through the REAL entrypoint

    generate._generate_via_campaign -> generate_campaign.generate -> secondbrain

1. **value actually passed to `secondbrain.for_task` == `productive`**
   (the canonical slug), not `Productive`.
2. **derived by lowercasing a display name == FALSE.** No `.lower()`,
   `.casefold()`, `slugify` or display-name lookup anywhere on the identity
   path. `grep -n "lower()\|casefold()\|slugify" src/generate_campaign.py`
   must show nothing on the client-identity path.
3. Second Brain called TRUE, error NONE, total 50, relevant admitted 26,
   **profitability admitted TRUE**, **budgeting admitted TRUE**, downstream
   business context PRESENT with a non-zero length.
4. **Positive mutation** of the profitability item changes the downstream
   context; **restoration** returns it to baseline. Report all three lengths.
5. **Silent-fallback preserved:** a truly invalid identity
   (`no-such-client-xyz`) RAISES; a valid authority with no relevant facts
   returns a legitimate empty result. The two must stay distinguishable.
6. **Negative boundary unchanged and unedited:**
   `test_a_client_csv_fact_cannot_license_a_claim` and
   `test_a_client_supplied_figure_licenses_no_claim_in_either_gate`.
7. **MUTATION:** restore the display-name path; acceptance 1 must go red for
   that reason. Restore and verify byte-identical by sha256. Files are CRLF.

### ACCEPTANCE COMMANDS

    py -3 -m unittest tests.test_task911_second_brain_canonical_status
    py -3 -m unittest tests.test_a_client_csv_fact_cannot_license_a_claim
    py -3 -m unittest tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate
    py -3 -m unittest tests.test_the_second_brain_returns_only_what_the_task_needs
    py -3 -m unittest tests.test_copylint
    py -3 -m unittest tests.test_task910_writer_contract
    py -3 -m unittest tests.test_render_preview
    py -3 -m unittest tests.test_approve

    py -3 -c "import sys; from src import generate_campaign as gc, offers; o=offers.all_offers()['OFFER-A-ECONOMIC-BUYER']; n=len(gc._load_admitted_facts('productive','economic_buyer',o)); sys.exit('slug path broken') if n==0 else print('OK slug admitted', n)"

    grep -n "lower()\|casefold()\|slugify" src/generate_campaign.py

**The grep must show NO hit on the client-identity path.** Read exit codes OFF
THE PROCESS, never through a pipe.

## NOT YOURS — do not attempt
`tests/test_generate` has **3 long-standing failures**
(`test_a_draft_that_breaks_a_rule_is_regenerated_not_patched`,
`test_the_model_is_told_what_failed_rather_than_the_draft_being_edited`,
`test_the_retry_names_the_banned_phrase_rather_than_the_code`). **Measured by
bisect: they are red at `143f132f`, the session's starting master, and at every
commit since — they predate all of this work and are NOT a TASK-910
regression.** Do not fix them here, do not edit those tests, and do not report
them as yours. They are a separate operator decision.

## START HERE
The dispatcher resets your tree to `origin/master`. **First command:**

    git merge --no-edit origin/qwen-worker-8-r19

Confirm your TASK-911 commits are present, then make the identity fix on top.
**Commit every file you touch.**

**Files: `src/generate_campaign.py` plus your tests. Nothing else.**
