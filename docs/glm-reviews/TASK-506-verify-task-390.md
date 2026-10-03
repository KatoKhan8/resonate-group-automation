# TASK-506 — Independent GLM Verification of TASK-390

**Target task:** TASK-390 (GLM Checkpoint B: offers, persona list, campaign strategy)
**Branch:** origin/qwen-worker-10-r9
**Named HEAD SHA:** d3b76e3e172b59d86fd9541f15f47fcbf049c857
**Actual HEAD at review time:** c77460d66ccfa61b6f82c8347d597c1faa9b43b7 (branch has moved)
**Reviewed SHA:** d3b76e3e172b59d86fd9541f15f47fcbf049c857 (the named artifact)
**Worktree:** .qwen/worktrees/glm-506 (detached at d3b76e3e1)
**Review date:** 2026-10-03

## Branch movement notice

The branch `origin/qwen-worker-10-r9` has moved from `d3b76e3e1` to `c77460d66`.
Per TASK-506 instructions, the verdict reviews the named SHA `d3b76e3e1` regardless.

## Summary

TASK-390's result block is **SUBSTANTIALLY CORRECT**. All seven negative controls
were independently reproduced. The overall assessment — chain NOT safe, dependency
not met — is the right call. One additional finding not in the result block is
reported below (generate_campaign.py has zero production callers).

## Negative control dispositions

### Control 1: cta_link allowlist — VERIFIED PASS

**TASK-390 claim:** PARTIALLY VERIFIED / NOT APPLICABLE TO CURRENT STATE.

**Independent reproduction:** `src/copylint.py:633-635` contains exactly one URL:
```python
CTA_LINK_ALLOWLIST = frozenset({
    "https://productive.io/get-started/",
```
Line 733 enforces it: `if url not in CTA_LINK_ALLOWLIST:`. No offer in
`productive-offers.yaml` has a `cta_link` field (all six confirmed absent).
The `mechanisms:` block carries the link correctly for both `demo` and
`free_trial`. The allowlist is fail-closed.

**Disposition:** FIXED + VERIFIED. The allowlist is correct. The test
`test_a_dead_cta_link_is_refused` (22 tests) passes.

### Control 2: Neither offer approved — VERIFIED PASS

**TASK-390 claim:** VERIFIED PASS.

**Independent reproduction:** All six offers have `approval_status: pending`.
Grep of `config/` for `approval_status:\s*approved` returns zero matches.
`src/offers.py:99-103` raises `NotApproved` for non-approved offers.

**Disposition:** FIXED + VERIFIED.

### Control 3: capability_by_persona order changes only angle — VERIFIED PASS

**TASK-390 claim:** VERIFIED PASS.

**Independent reproduction:** `_offers_for_segment('agencies', 'champion')`
and `_offers_for_segment('agencies', 'economic_buyer')` both return EMPTY
dicts. This is because `campaignstrategy.py:72` filters by
`approval_status != offers_mod.APPROVED`, and all six offers are pending.
Offer assignment is by `offer.persona` field, NOT by `capability_by_persona`
order. The `capability_by_persona` list in `productive.yaml:359-361` controls
angle ordering for `cadence.product_words` only.

**Disposition:** FIXED + VERIFIED. The separation is correct. Note: the
empty return is the approval gate working as designed — no approved offers
means no strategy can plan around them.

### Control 4: Campaign strategy decided ONCE — VERIFIED PASS

**TASK-390 claim:** VERIFIED PASS.

**Independent reproduction:** 5 calls to `for_segment('agencies', 'champion')`
with a counting model → exactly 1 model call, 4 cache hits. Cache keyed by
`(segment_key, persona)` in `_strategy_cache` (`campaignstrategy.py:30`).
Test `test_model_called_once_for_fifty_leads_in_one_segment` passes.

**Disposition:** FIXED + VERIFIED.

### Control 5: No capability deleted — VERIFIED PASS

**TASK-390 claim:** VERIFIED PASS.

**Independent reproduction:** `productive.yaml` `product.capabilities` has
all six: project_management, time_tracking, budgeting, resource_planning,
billing, profitability. `src/offers.py:CONFIRMED_CAPABILITIES` matches
exactly (frozenset of 6). All six have corresponding offer records. Billing
is present as `OFFER-BI-001` (persona: economic_buyer).

**Disposition:** FIXED + VERIFIED.

### Control 6: Offer never restates value proposition — VIOLATION CONFIRMED

**TASK-390 claim:** VIOLATION FOUND.

**Independent reproduction:** All six offers have `value_proposition` text
that is VERBATIM identical to the corresponding `product.capabilities` text:

| Offer | Capability | Verbatim Match |
|-------|-----------|----------------|
| OFFER-PM-001 | project_management | TRUE |
| OFFER-TT-001 | time_tracking | TRUE |
| OFFER-BU-001 | budgeting | TRUE |
| OFFER-RP-001 | resource_planning | TRUE |
| OFFER-BI-001 | billing | TRUE |
| OFFER-PR-001 | profitability | TRUE |

Example: `OFFER-PM-001.value_proposition` = `'projects, tasks and delivery in one place'`
= `capabilities.project_management` exactly.

**Disposition:** EXISTING TASK (TASK-367). The two-offer rework was designed
to fix this. Until TASK-367 lands, the dual truth persists: updating a
capability's wording would silently desynchronise the offer's copy.

### Control 7: NotApproved raises at offer layer — VERIFIED PASS

**TASK-390 claim:** VERIFIED PASS.

**Independent reproduction:** `src/offers.py:40` defines `class NotApproved(Exception)`.
`for_campaign(503, require_approved=True)` raises:
```
NotApproved: offer OFFER-PM-001 has approval_status='pending', not 'approved'.
Production does not approve its own offers.
```
The exception names the offer and its status. Test
`test_unapproved_offer_raises_for_campaign_503` passes.

**Disposition:** FIXED + VERIFIED.

## Additional finding: generate_campaign.py has zero production callers

`src/generate_campaign.py` (420 lines, added by this branch) imports
`campaignstrategy` and `offers` and is the intended production entrypoint
for the checkpoint B chain. However:

- `grep -rn "generate_campaign" src/` returns ZERO matches.
- `grep -rn "generate_campaign" scripts/` returns ZERO matches.
- It is consumed ONLY by test files (4 test modules import it).

This is the "existence is not function" defect documented in QWEN.md and
CLAUDE.md. The module compiles, has tests, and is correctly structured —
but no production code path reaches it. The chain from capability_by_persona
through offers through campaign strategy to copy generation is DISCONNECTED
at the final step.

**Disposition:** NEW TASK (or EXISTING TASK if TASK-369 or equivalent covers
this). Not a defect in TASK-390's own claims, which did not assert that
generate_campaign was wired — but material to the "is the chain safe"
question.

## Deletion risk

`git diff master...d3b76e3e1 --diff-filter=D` returns exactly one file:
`docs/qwen-tasks/TODO/TASK-216-find-the-supported-list-to-campaign-bind.md`

This is a task file being moved/consumed, not production code. **No
production files would be deleted by merging this branch.** Safe.

## Scope drift

The branch diff is 205 files, ~31k lines added. This is far larger than a
checkpoint review — it carries the accumulated work of many tasks (TASK-320
through TASK-380+). The checkpoint B artifacts (offers, campaignstrategy,
capability_by_persona changes) are a small subset. Cherry-picking would
require extracting:

- `config/clients/productive-offers.yaml` (new)
- `config/clients/productive.yaml` (modified: capabilities, capability_by_persona)
- `src/offers.py` (new)
- `src/campaignstrategy.py` (new)
- `src/copylint.py` (new, CTA allowlist)
- Related tests

The rest is other tasks' work. Not pollution per se — the branch is a
integration branch carrying many merged tasks — but merging the whole
branch to get checkpoint B would bring everything.

## Overall verdict

**REWORK.** The result block's findings are accurate and well-evidenced.
The chain is correctly assessed as NOT safe:

1. TASK-367 (two-offer design) is not merged — the six-offer state persists.
2. Control 6 (value proposition restatement) is violated for all six offers.
3. No offer carries a `cta_link` field.
4. `generate_campaign.py` has zero production callers (additional finding).

The result block's recommended action is correct: complete TASK-367, resolve
control 6, re-run the checkpoint.

**MERGE / REWORK / CLOSE:** CLOSE. The verdict confirms TASK-390's findings
are correct. The chain is not safe. The closure reason is the unmet
dependency (TASK-367) and the control 6 violation, both correctly identified
by the worker. No rework of TASK-390 itself is needed — its analysis is
sound. The open items belong to TASK-367 and to the entrypoint wiring
(TASK-369 or successor).
