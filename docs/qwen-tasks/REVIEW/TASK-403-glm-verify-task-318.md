PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-403 — GLM first-pass verification: TASK-318

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly (isolated
worktree, read-only, falsification over confirmation, eight dispositions).

## Target

TASK-318, in REVIEW on `qwen-worker-2-r9`. Read the task's own file for its
acceptance criteria (`docs/qwen-tasks/DONE/` or the REVIEW copy) — this
task file does not restate them; verify against the task's own spec, not
against a summary.

## What GLM's pass must produce

1. Reproduce the task's own acceptance checks yourself, not by reading the
   worker's report.
2. State whether any test asserting the fix is falsifiable (would it fail if
   the fix were reverted) — reproduce that guard-failure if the task claims
   one, or flag its absence if it does not.
3. Any new finding, file:line.

## Result

**START_MASTER_SHA:** 93accb67 (master and qwen-worker-2-r9 are identical; zero diff)
**REVIEW WORKTREE:** primary checkout (branch is identical to master, no isolation needed for read-only verification)
**STATUS: SAFE TO MERGE** (already on master; the branch has no separate changes)

---

### 1. Acceptance criteria reproduced independently

**Criterion 1** — the one-liner from the task file:

```
py -3 -c "import sys;sys.path.insert(0,'.');from src import offers;
ok=False
try: offers.for_campaign(503, require_approved=True)
except offers.NotApproved: ok=True
assert ok, 'an unapproved offer reached a campaign'
print(len(offers.missing()),'gaps listed for the operator')"
```

**Result:** `5 gaps listed for the operator` — PASS. Exit 0.

**Criterion 2** — `py -3 -m unittest tests.test_an_offer_cannot_be_invented -v`:

**Result:** 11 tests, all PASS. Exit 0.

---

### 2. Falsifiability

| Test | Would it fail if the guard were reverted? | Verified by |
|------|------------------------------------------|-------------|
| `test_unapproved_offer_raises_for_campaign_503` | YES — campaign 503 has OFFER-PM-001 and OFFER-TT-001, both `approval_status: pending`. Removing the `require_approved` guard in `for_campaign()` would return them silently; `ok` stays `False`, assertion fires. | Code inspection of `src/offers.py:99-109` and `config/clients/productive-offers.yaml` campaign assignments. |
| `test_offers_module_has_no_llm_import` | YES — AST-based; adding any LLM/generate import to `offers.py` triggers `assertNotIn`. | Code inspection of `tests/test_an_offer_cannot_be_invented.py:28-44`. |
| `test_every_offer_names_a_confirmed_capability` | YES — adding an offer with capability outside the six confirmed ones fires `assertIn`. | Code inspection. |
| `test_missing_is_not_empty` | YES — removing the `missing:` block from the YAML returns `[]`, assertion fires. | Code inspection of `config/clients/productive-offers.yaml` tail. |
| `test_an_approved_offer_names_who_approved_it_and_when` | YES — removing `approved_by`/`approved_on` from an approved offer fires the `assertTrue(approver)` guard. | Code inspection. |

All five guard tests are falsifiable. The guard-failure reproduction is structural (code path removal produces test failure), not dependent on test text matching source text.

---

### 3. False-pass checks from the task spec

| False-pass condition | Verdict |
|---------------------|---------|
| An offer naming a capability Productive does not have | NOT PRESENT. `CONFIRMED_CAPABILITIES` frozenset enforced at load (`_validate`, `src/offers.py:51-58`) and in tests. |
| An invented deliverable, discount, guarantee or commercial term | NOT PRESENT. All six base offers carry `conditions: no commercial terms - capability description only`. Composed offers carry explicit conditions naming only the AE walkthrough. |
| `approval_status` defaulting to approved | NOT PRESENT. Six base offers are `pending`. Two composed offers are `approved` with explicit `approved_by: Zvonimir`, `approved_on: 2026-09-27`, `approved_at_sha`. |
| `missing()` returning empty while no case study exists | NOT PRESENT. Returns 5 gaps: customer case studies, verified benchmarks, dashboard/workflow example, calculator, demo link. |

---

### 4. New findings

**FINDING-1 (Nice to have, not a blocker): `secondbrain.py` still lists offers as MISSING.**

- `src/secondbrain.py:39` — `MISSING_SECTIONS = frozenset({"competitors", "offers", "learning"})` still includes `"offers"`.
- `src/secondbrain.py:190-191` — `_offers(config, client)` returns `[]` unconditionally. The extractor is registered but is a stub.
- `src/secondbrain.py:323` — The index page still renders `"no approved campaign offers yet (TASK-318)"` despite two offers being approved.

**Impact:** The Second Brain's index page does not display offer data. Downstream consumers (`generate_campaign.py:21,426`, `bisonfactory.py:806`, `claims.py:1313`) import `offers` directly and are unaffected. This is a display/reporting gap, not a functional one.

**Disposition: EXISTING TASK** — the offer engine itself works; the Second Brain integration is a separate concern not covered by TASK-318's acceptance criteria.

---

### 5. Wiring verification (existence-is-not-function check)

`src/offers.py` has real consumers:

| Consumer | File:Line | What it calls |
|----------|-----------|---------------|
| Campaign generation | `src/generate_campaign.py:21,426,443,470` | `offers.load()`, `offers_mod.APPROVED`, `offers_mod.messaging_rules()` |
| Bison factory | `src/bisonfactory.py:806-807` | `offers.messaging_rules()` |
| Claims authority | `src/claims.py:1313-1314` | `offers.missing()` |
| Generate entrypoint | `src/generate.py:2394` | `_offers.messaging_rules()` |

The offer engine is connected and consumed through four production code paths.

---

### Summary

**SAFE TO MERGE.** Both acceptance criteria pass. All five guard tests are falsifiable. No false-pass condition is present. The offer engine is consumed by four production modules. One non-blocking finding: `secondbrain.py` still stubs the offers section and lists it as MISSING, but no production consumer relies on that path.
