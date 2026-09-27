PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-418 — Offer Config Consistency Check (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `offer-config-consistency-check`.

Read `config/clients/productive-offers.yaml` end to end and check for
internal contradictions the way TASK-382's GLM review found one (a "THE
ONLY allowed link" comment coexisting with a different link elsewhere in
the same file). Report every such contradiction found, file:line, quoting
both sides. Acceptance: a clean pass reports "none found" honestly; any
contradiction found is quoted exactly, both sides.

## RESULT BLOCK

**STATUS:** DONE
**ARTIFACT KIND:** finding (read-only audit, no code or test changes)
**COMMIT SHA:** (no code changes to commit)
**TESTS:** n/a — read-only audit
**FILES CHANGED:** none (task file only)

### Checks performed (505 lines, end to end)

| # | Check | Result |
|---|-------|--------|
| 1 | All CTA/mechanism links vs "THE ONLY allowed CTA link" comment (line 481) | All 6 links are `https://productive.io/get-started/` — consistent |
| 2 | `composes:` references resolve to existing offer IDs | OFFER-A → [OFFER-PR-001, OFFER-BU-001] ✓; OFFER-B → [OFFER-PM-001, OFFER-TT-001, OFFER-RP-001] ✓ |
| 3 | `mechanism:` references resolve to existing mechanism keys | Both offers → `ae_walkthrough_premium_trial` ✓ |
| 4 | AI page_texts match verbatim between offers and evidence.productive_ai | All 7 features match word for word |
| 5 | `traces_to:` keys resolve to existing evidence entries | All → `productive_ai` ✓ |
| 6 | Approval statuses match header claim ("Offers A v2 and B v2 stay approved") | A: approved ✓, B: approved ✓, 6 simple offers: pending ✓ |
| 7 | `approved_at_sha` matches `approval_history.v2.at_sha` | Both offers: a04574be ✓ |
| 8 | Persona consistency: composed offers match component offers | A: economic_buyer (from PR+BU) ✓; B: champion (from PM+TT+RP) ✓ |
| 9 | No-dash rule in prospect-facing fields | No dashes in any business_problem, value_proposition, concrete_deliverable or cta |
| 10 | `missing.demo_link` vs `mechanisms.demo` | Different things (self-service sandbox vs AE-led walkthrough) — not a contradiction |
| 11 | `enforced_by` vs `enforcement_status` | Tension documented inline ("ENFORCEMENT IS NOT YET BUILT") — not a hidden contradiction |
| 12 | `permitted_chains` vs offer ai_capabilities | Chains name the primary AI angle per persona; offers list all available — not contradictory |

### Finding

**None found.** `config/clients/productive-offers.yaml` is internally consistent across all checked dimensions. No two pieces of data in the file disagree.

**FINDINGS:** No contradictions. The file is clean.
**RISKS:** None from this audit.
**RECOMMENDED CLAUDE ACTION:** Accept clean pass.
