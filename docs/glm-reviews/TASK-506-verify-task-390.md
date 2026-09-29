# TASK-506 — GLM Independent Verification of TASK-390

## Review metadata

| Field | Value |
|-------|-------|
| Reviewing task | TASK-506 |
| Target task | TASK-390 |
| Target branch | origin/qwen-worker-10-r9 |
| Target SHA | d3b76e3e172b59d86fd9541f15f47fcbf049c857 |
| Branch HEAD at review time | 3f7f8f14 (branch has moved; reviewed SHA is frozen) |
| Worktree | .qwen/worktrees/task506-review (detached at d3b76e3e) |
| START_MASTER_SHA | 53dc50c8 |
| Artifact kind | finding (read-only verification checkpoint) |
| Verdict date | 2026-09-29 |

## Scope of TASK-390

TASK-390 is a GLM Checkpoint B review covering three linked pieces:
1. `capability_by_persona` (TASK-366) — ordered angle list per persona
2. `offers:` block (TASK-367) — persona-to-offer mapping (dependency NOT met)
3. Campaign strategy (TASK-320) — decided once per segment+persona, cached

TASK-390's own commit (`d3b76e3e`) changes exactly two files:
- `docs/qwen-tasks/REVIEW/TASK-390-glm-checkpoint-b.md` (+175 lines, the result block)
- `docs/qwen-tasks/TODO/TASK-390-glm-checkpoint-b.md` (-57 lines, moved to REVIEW)

The artifact is the result block. No production code was changed.

## Independent verification of each negative control

### Control 1: cta_link allowlist is the sole URL

**TASK-390 claim:** PARTIALLY VERIFIED / NOT APPLICABLE TO CURRENT STATE. Allowlist has one URL (`https://productive.io/get-started/`). Six offers have no `cta_link` field.

**Independent verdict: CONFIRMED.**

`src/copylint.py:633-635`:
```python
CTA_LINK_ALLOWLIST = frozenset({
    "https://productive.io/get-started/",
})
```

`check_cta_links` at line 733 refuses any URL not in this frozenset. The allowlist is fail-closed: a non-allowlisted URL is classified as `not_allowlisted` before resolution is even attempted.

The six offers in `productive-offers.yaml` carry no `cta_link` field. The `mechanisms:` block at lines ~200-210 carries the link for `demo` and `free_trial`. TASK-390 correctly identified this as "not applicable to current state" — the allowlist is correct but has no offer-level cta_link to validate yet.

**Disposition: EXISTING TASK (TASK-367 must land before this control becomes fully testable at the offer level).**

### Control 2: Neither offer's approval_status is approved

**TASK-390 claim:** VERIFIED PASS. All six offers have `approval_status: pending`.

**Independent verdict: CONFIRMED.**

Reproduced programmatically at SHA d3b76e3e:
```
OFFER-PM-001: approval_status='pending'
OFFER-TT-001: approval_status='pending'
OFFER-BU-001: approval_status='pending'
OFFER-RP-001: approval_status='pending'
OFFER-BI-001: approval_status='pending'
OFFER-PR-001: approval_status='pending'
```

Grep of `config/` for `approval_status.*approved` returns only the comment lines in the YAML header (lines 8-9), not any data field. No offer is approved.

**Disposition: FIXED + VERIFIED (the gate works as intended; no offer can reach copy generation).**

### Control 3: capability_by_persona order changes only the angle, not offer assignment

**TASK-390 claim:** VERIFIED PASS. Offer assignment is by `offer.persona` field, not by `capability_by_persona` order.

**Independent verdict: CONFIRMED with nuance.**

`src/campaignstrategy.py:56-73` (`_offers_for_segment`) filters offers by `offer.get("persona")` match, not by `capability_by_persona`. The `capability_by_persona` list is consumed by `cadence.product_words` (`src/cadence.py:775`) which resolves `{capability}` to the first entry's sentence for rung 3.

Current state:
```yaml
capability_by_persona:
  economic_buyer: [profitability, budgeting, billing]
  champion: [resource_planning, project_management, time_tracking]
```

Reordering the list changes the primary angle (first entry → `cadence.product_words` output) but NOT which offers a persona gets. Offer assignment is by `persona` field match in the offer YAML.

**Nuance:** Since all offers are `pending`, `_offers_for_segment` returns empty for both personas (it filters by `approval_status == 'approved'` at line 72). The separation of concerns is correct in design but untestable with live data until an offer is approved.

**Disposition: FIXED + VERIFIED.**

### Control 4: Campaign strategy decided ONCE per segment+persona

**TASK-390 claim:** VERIFIED PASS. 5 calls → 1 model call, 4 cache hits.

**Independent verdict: CONFIRMED.**

Reproduced at SHA d3b76e3e:
```python
campaignstrategy.clear_cache()
model = CountingModel()
for i in range(5):
    result = campaignstrategy.for_segment('agencies', 'champion', model=model)
# Result: model.calls == 1, campaignstrategy.model_call_count() == 1
```

Cache key is `(segment_key, persona)` at `src/campaignstrategy.py:30`. The existing test `test_model_called_once_for_fifty_leads_in_one_segment` passes (50 calls → 1 model invocation).

**Falsification check:** Could this pass while the implementation is wrong? The cache is a plain dict lookup — if the key matched, the cached value is returned without calling the model. A wrong implementation would need to both (a) hash the key correctly and (b) return the wrong value. The test asserts on `model.calls` (side effect), not on source text, so it is falsifiable.

**Disposition: FIXED + VERIFIED.**

### Control 5: No capability deleted

**TASK-390 claim:** VERIFIED PASS. All six capabilities present.

**Independent verdict: CONFIRMED.**

`src/offers.py:24-31`:
```python
CONFIRMED_CAPABILITIES = frozenset({
    "project_management", "time_tracking", "budgeting",
    "resource_planning", "billing", "profitability",
})
```

`config/clients/productive.yaml:337-343` has all six under `product.capabilities`. Each offer maps to exactly one confirmed capability. Billing is present as `OFFER-BI-001`.

Test `test_six_capabilities_shipped` passes.

**Disposition: FIXED + VERIFIED.**

### Control 6: Offer never restates a value proposition

**TASK-390 claim:** VIOLATION FOUND. All six offers restate their capability's value_proposition verbatim.

**Independent verdict: CONFIRMED — VIOLATION REPRODUCED.**

Programmatic comparison at SHA d3b76e3e:

| Offer | capability | offer.value_proposition | capabilities.<id> | VERBATIM MATCH |
|-------|-----------|------------------------|-------------------|----------------|
| OFFER-PM-001 | project_management | "projects, tasks and delivery in one place" | "projects, tasks and delivery in one place" | **True** |
| OFFER-TT-001 | time_tracking | "time booked against the project and the budget it belongs to" | "time booked against the project and the budget it belongs to" | **True** |
| OFFER-BU-001 | budgeting | "what a project was quoted at and what it has burned so far" | "what a project was quoted at and what it has burned so far" | **True** |
| OFFER-RP-001 | resource_planning | "who is booked on what next week, and where the next hire goes" | "who is booked on what next week, and where the next hire goes" | **True** |
| OFFER-BI-001 | billing | "invoices raised from the time and the budget rather than retyped" | "invoices raised from the time and the budget rather than retyped" | **True** |
| OFFER-PR-001 | profitability | "margin per project while it is running, not after it closes" | "margin per project while it is running, not after it closes" | **True** |

All six are verbatim copies. TASK-367's spec says: "Value propositions are referenced, never restated. An offer names capability ids; the sentences stay in `capabilities:` where they are CLIENT_APPROVED verbatim. Copying a sentence into the offer creates a second truth."

This is a genuine design violation. If a capability's wording is updated in `productive.yaml`, the offer's `value_proposition` becomes stale without any mechanism to detect the drift.

**Disposition: EXISTING TASK (TASK-367 rework was meant to fix this; the two-offer design does not carry verbatim value_proposition text).**

### Control 7: NotApproved still raises at the offer layer

**TASK-390 claim:** VERIFIED PASS.

**Independent verdict: CONFIRMED.**

Reproduced at SHA d3b76e3e:
```python
offers.for_campaign(503, require_approved=True)
# Raises: NotApproved: offer OFFER-PM-001 has approval_status='pending', not 'approved'. Production does not approve its own offers.
```

`src/offers.py:40` defines `class NotApproved(Exception)`. `for_campaign` at lines 99-103 raises it naming the offer ID and its actual status. The exception message is specific and actionable.

Test `test_unapproved_offer_raises_for_campaign_503` passes.

**Disposition: FIXED + VERIFIED.**

## Additional findings

### F1: generate_campaign.py has zero production callers

`src/generate_campaign.py` exists on master and on this branch. It imports `offers`, `campaignstrategy`, and the five skills. But NO module in `src/` or `scripts/` imports or calls `generate_campaign`. Its only consumers are four test files.

The CLI entrypoint `src/generate.py` does NOT import `generate_campaign`. The old generation path is still the live path.

This is NOT a finding about TASK-390 specifically — TASK-390 is a review checkpoint, not an implementation task. But it is load-bearing context: the chain TASK-390 reviewed (offers → strategy → entrypoint) terminates at `generate_campaign.generate()`, which nothing production calls. TASK-380 already documented this.

**Disposition: EXISTING TASK (acknowledged by TASK-380, not in scope for Checkpoint B).**

### F2: Branch carries substantial scope beyond TASK-390

The diff `master...d3b76e3e` is 205 files changed, +30,881 / -477 lines. TASK-390's own commit changes 2 files (task file move). The branch is an operational accumulation branch carrying dozens of tasks, operator directives, handoff docs, case study JSON, provider answer docs, and the full implementation of TASK-346/369/373/etc.

Merging this branch would bring all of that. Only one file is deleted: `docs/qwen-tasks/TODO/TASK-216-find-the-supported-list-to-campaign-bind.md`, which was moved to REVIEW (normal lifecycle).

**This verdict is about TASK-390's artifact (the result block), not about merging the branch.** The branch merge is Claude's decision and is out of scope.

## Deletion check

`git diff master...d3b76e3e --diff-filter=D --name-only`:
- `docs/qwen-tasks/TODO/TASK-216-find-the-supported-list-to-campaign-bind.md` — moved to REVIEW, not destroyed.

No source files, config files, or test files are deleted.

## Test falsifiability assessment

| Test | Falsifiable? | How it could pass while wrong |
|------|-------------|-------------------------------|
| `test_unapproved_offer_raises_for_campaign_503` | Yes | Asserts on exception type and message content; would fail if gate were removed |
| `test_model_called_once_for_fifty_leads_in_one_segment` | Yes | Asserts on side effect (model call count), not source text |
| `test_six_capabilities_shipped` | Yes | Asserts on frozenset equality; would fail if a capability were removed |
| `test_every_offer_names_a_confirmed_capability` | Yes | Asserts on load-time validation; would fail if an invented capability were added |
| `test_no_model_call_when_cached` | Yes | Asserts on side effect; would fail if cache were bypassed |

None of the tests rely on `hasattr`, source text search, or token matching. They assert on observable behavior (exception raised, counter value, set equality).

## Summary disposition table

| Control | TASK-390 claim | Independent verdict | Disposition |
|---------|---------------|--------------------|-------------|
| 1. cta_link allowlist | PARTIALLY VERIFIED | CONFIRMED | EXISTING TASK |
| 2. No approved offer | VERIFIED PASS | CONFIRMED | FIXED + VERIFIED |
| 3. Order → angle only | VERIFIED PASS | CONFIRMED (with nuance) | FIXED + VERIFIED |
| 4. Strategy cached | VERIFIED PASS | CONFIRMED | FIXED + VERIFIED |
| 5. No capability deleted | VERIFIED PASS | CONFIRMED | FIXED + VERIFIED |
| 6. No VP restatement | VIOLATION FOUND | CONFIRMED VIOLATION | EXISTING TASK |
| 7. NotApproved raises | VERIFIED PASS | CONFIRMED | FIXED + VERIFIED |

## Recommendation

**CLOSE.**

TASK-390 is a read-only verification checkpoint. Its artifact is the result block, and every claim in that result block is accurate:

1. All five passing controls (2, 3, 4, 5, 7) are independently reproduced and confirmed.
2. The blocking finding (TASK-367 dependency not met) is accurate — the two-offer design was never merged; `99de48df` on master explicitly blocks it.
3. The control 6 violation (verbatim value_proposition restatement) is real and reproduced for all six offers.
4. The chain safety assessment ("NOT safe to build copy generation against") is correct given the current state.

TASK-390 did what a checkpoint should: it found the dependency was not met, identified a design violation, and refused to declare the chain safe. The result block is honest, specific, and actionable. No rework is needed.

The branch `qwen-worker-10-r9` carries substantial accumulated work beyond TASK-390. Merging that branch is a separate decision and is not recommended or discouraged by this verdict.
