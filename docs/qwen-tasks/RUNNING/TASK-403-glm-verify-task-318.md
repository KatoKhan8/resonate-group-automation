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

**START_MASTER_SHA:** 26e68e6b (this worker's branch diverged before this
commit; verification reads master state via `git show master:<path>`)

**STATUS: ALREADY MERGED.** TASK-318 was integrated to master as TASK-333
(commit 5641e90c). The task file's reference to "REVIEW on qwen-worker-2-r9"
is stale. This verification confirms the integrated state on master.

**TASK-367 NOTE:** A follow-up (commit 9f44c4c3, two-tier capabilities/offers
restructure) exists only on `origin/qwen-worker-5-r9` and is NOT on master.
This verification covers the TASK-318/TASK-333 state as it stands on master.

---

### 1. Acceptance checks reproduced

**Acceptance command from TASK-318:**

    py -3 -c "import sys;sys.path.insert(0,'.');from src import offers;
    ok=False
    try: offers.for_campaign(503, require_approved=True)
    except offers.NotApproved: ok=True
    assert ok, 'an unapproved offer reached a campaign'
    print(len(offers.missing()),'gaps listed for the operator')"

**Result:** `5 gaps listed for the operator` — PASS

**Unit tests:** `py -3 -m unittest tests.test_an_offer_cannot_be_invented -v`

    Ran 11 tests in 0.014s — OK

All 11 tests pass:
- test_offers_module_has_no_llm_import ........................... ok
- test_load_reads_only_from_yaml ................................. ok
- test_unapproved_offer_raises_for_campaign_503 .................. ok
- test_approval_status_is_not_defaulted_to_approved .............. ok
- test_require_approved_false_returns_unapproved ................. ok
- test_every_offer_names_a_confirmed_capability .................. ok
- test_six_capabilities_shipped .................................. ok
- test_missing_is_not_empty ...................................... ok
- test_missing_includes_case_studies ............................. ok
- test_missing_includes_demo_link ................................ ok
- test_every_offer_has_all_schema_fields ......................... ok

### 2. Falsifiability

| Guard | Would it catch a regression? | Reproduced |
|-------|------------------------------|------------|
| Invented capability | `_validate()` raises ValueError for `capability` not in `CONFIRMED_CAPABILITIES` | YES — fed `ai_powered_analytics`, caught |
| Missing approval_status | `_validate()` raises ValueError when `approval_status` is None | YES — omitted field, caught |
| Unapproved offer reaching campaign | `for_campaign(503, require_approved=True)` raises `NotApproved` | YES — all 6 offers pending, raises on first |
| No LLM import | AST walk forbids generate/copyprompts/llm/etc. imports | YES — structural, would catch any LLM coupling |
| missing() empty | Asserts `len(gaps) > 0` and checks for "case stud" and "demo" | YES — would fail if gaps were cleared |
| approval_status defaulted to approved | Iterates all offers, asserts none is "approved" | YES — would catch silent approval |

**Verdict: All four false-pass guards from TASK-318 are tested and falsifiable.**

### 3. Consumption chain (the "existence is not function" check)

| Module | Has callers? | Status |
|--------|-------------|--------|
| `src/offers.py` | `campaignstrategy.py:22`, `generate_campaign.py:20` | CONSUMED |
| `src/campaignstrategy.py` | `generate_campaign.py:151` | CONSUMED (by generate_campaign) |
| `src/generate_campaign.py` | 4 test files (40 call sites), **ZERO `src/` callers** | INERT in production |
| `src/secondbrain.py _offers()` | Returns `[]` (stub), `MISSING_SECTIONS` still includes "offers" | **NOT WIRED** |

### 4. New findings

**FINDING-1 (EXISTING TASK): `secondbrain.py` offer section not served**
- File: `src/secondbrain.py:157-158`
- `_offers(config, client)` returns `[]`
- `MISSING_SECTIONS` (line 38) still includes `"offers"`
- HTML report (line 290) says "no approved campaign offers yet (TASK-318)"
- TASK-318 spec lists `src/secondbrain.py MODIFY` but the integration
  (commit 5641e90c) deliberately excluded the secondbrain.py changes from
  the cherry-pick to avoid reverting TASK-322's provenance fix (19 hardcoded
  source paths and `verified=True` defaults).
- **Disposition: EXISTING TASK** — the secondbrain wiring is a known gap,
  deferred to a task that can do it without reverting TASK-322.

**FINDING-2 (EXISTING TASK): `generate_campaign.py` has no production caller**
- `src/generate_campaign.py` is the canonical entrypoint (TASK-369) but is
  called only from tests, not from `src/generate.py` or any script.
- The offer fail-closed check (`_check_offers`) is structurally correct but
  inert in production because nothing calls `generate()`.
- **Disposition: EXISTING TASK** — this is TASK-400's target.

**FINDING-3 (OBSERVATION): All six offers are `pending`**
- No offer can currently reach copy generation. This is correct fail-closed
  behaviour, not a defect. Approving offers is an operator decision.
- **Disposition: ACCEPTED DEFERRED RISK** — operator decision required.

### 5. Verdict

**SAFE TO MERGE: N/A — already merged.** The three files taken by the
TASK-333 integration (`src/offers.py`, `config/clients/productive-offers.yaml`,
`tests/test_an_offer_cannot_be_invented.py`) are correct, tested, and
falsifiable. The `secondbrain.py` wiring gap is a known deferral, not a
regression. The production-chain inertness (`generate_campaign` has no
production caller) is TASK-400's target, not a TASK-318 defect.

### Disposition table

| Finding | Severity | Disposition |
|---------|----------|-------------|
| Acceptance checks pass | — | CONFIRMED |
| 11 tests pass and are falsifiable | — | CONFIRMED |
| `secondbrain.py _offers()` returns `[]` | P1 | EXISTING TASK (TASK-321/391) |
| `generate_campaign.py` has no production caller | P0 | EXISTING TASK (TASK-400) |
| All offers pending, no operator approval yet | P2 | ACCEPTED DEFERRED RISK |

---

## RESULT BLOCK

- **STATUS:** DONE
- **ARTIFACT KIND:** finding (verification report)
- **COMMIT SHA:** 9346363d (remote: origin/qwen-worker-9-r9)
- **TESTS:** 11/11 pass in `tests.test_an_offer_cannot_be_invented`; acceptance command passes (5 gaps)
- **FILES CHANGED:** `docs/qwen-tasks/RUNNING/TASK-403-glm-verify-task-318.md` (this file)
- **FINDINGS:**
  - TASK-318 integrated state on master is correct
  - `secondbrain.py` offer section not wired (known deferral, not regression)
  - `generate_campaign.py` production-chain inert (TASK-400's target)
  - All 6 offers pending — operator approval needed to activate
- **RISKS:** None new. Known gaps have existing tasks.
- **RECOMMENDED CLAUDE ACTION:** Close TASK-403. The two existing-task
  findings (TASK-400, TASK-321/391) are already tracked.
