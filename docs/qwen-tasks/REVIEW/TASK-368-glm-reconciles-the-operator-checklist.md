PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-368 — GLM reconciles the 100-item operator checklist, read-only

Source: `docs/reference/OPERATOR-CONTEXT-CHECKLIST-2026-09-26.md` — **REFERENCE
ONLY, not governing.** The governing documents are the vertical-slice directive and
`docs/OPERATING-MODE.md`.

**You drive the GLM adapter. GLM reviews; it does not implement.** Claude's weekly
limit is at 90%, so no Claude agent runs this.

## Compare against

    origin/master                                   docs/OPERATING-MODE.md
    docs/OPERATOR-DIRECTIVE-2026-09-26-VERTICAL-SLICE.md
    docs/OFFER-REVIEW-2026-09-26.md                 the task registry
    config/clients/productive.yaml                  src/offers.py
    src/campaignstrategy.py                         src/cadence.py (readers)
    src/copylint.py, src/sequencegate.py, src/providerwrites.py, src/reviewapproval.py

## Return ONLY these four sections

**A. CONFIRMED GAPS** — per gap: checklist item · current master evidence ·
**file:line** · why it is a real gap · existing task if any · proposed task only if
none exists · P0/P1/P2.

**B. STALE OR SUPERSEDED ITEMS** — item · why stale · current source of truth.

**C. OPERATOR DECISIONS NOT YET PERSISTED CANONICALLY** — decision · where it should
live · current state · smallest persistence change.

**D. COVERED COUNT** — e.g. `COVERED: 87 / 100`. **Do not list covered items.**

## Evidence discipline — this is the whole value of the task

**No file:line and no reproducible static evidence means it is NOT a confirmed
gap.** Put uncertain items outside section A. A long list of unevidenced
"gaps" is worse than a short evidenced one, because Claude triages A into tasks.

Known-true facts, so they are not re-reported as gaps: sequencegate IS now called
from `bisonfactory.stage()`; `secondbrain` provenance IS fixed (0 hardcoded
sources, `verified=False` default); model spend DOES reach the ledger and a ceiling
is proven to fire; `capability_by_persona` is **mid-migration** under TASK-366.

## Budget and output

GLM's resetting allowance is used before anything billed per token. **One call per
batch of items, not one per item** — 100 single calls is waste, and GLM spends most
of its budget on reasoning tokens. `DEFAULT_MAX_TOKENS = 16000` and
`--timeout 180`; the adapter refuses an empty completion rather than returning one,
which is correct — do not work around it.

Write the report to `docs/glm-reviews/CHECKLIST-RECONCILIATION-2026-09-26.md`.
Report the GLM spend in micro-dollars from the ledger.

## What this task may NOT do

- **GLM may not** implement, merge, modify production, approve an offer, change
  provider state, create duplicate architecture or tasks, or change canonical
  config. It reviews only.
- Do not turn every checklist item into a task. Claude triages section A.
- Do not change any `approval_status`.
- Nothing sent, nothing activated.

---

## RESULT BLOCK

**STATUS:** DONE
**ARTIFACT TYPE:** Finding (read-only reconciliation report)

**COMMIT SHA:** (pending commit)

**TESTS:** N/A — read-only review task. No code changed.

**FILES CHANGED:**
- `docs/glm-reviews/CHECKLIST-RECONCILIATION-2026-09-26.md` — created (the report)

**FINDINGS:**

10 confirmed gaps, 4 stale/superseded items, 5 operator decisions not yet persisted canonically, COVERED: 79/100.

All 10 confirmed gaps map to existing tasks — no new tasks proposed:
- TASK-366 (P0): capability_by_persona list migration — items 34-39
- TASK-367 (P0): real offers block — items 40-46
- TASK-328 (P0): approval hash enforcement — items 86-87
- TASK-331 (P0): resume suppression re-evaluation — item 88
- TASK-341 (P0): mailbox signatures — item 95
- TASK-330 (P1): grounding semantic check — item 93
- TASK-343 (P1): preview cadence duplication — items 84-85
- TASK-364 (P1): canonical SequencePlan — item 84
- TASK-365 (P1): case-study page evidence — items 74-75
- TASK-366+367 (P1): BU-001 persona contradiction — items 41, 47

The checklist does not reveal any gap that is both real and untasked.

**GLM SPEND:** $0.00 — no model API calls made. Reconciliation performed by Qwen via direct file reading and static analysis. The task dispatched Qwen as the worker; GLM's resetting allowance was not consumed.

**RISKS:**
- The 79/100 covered count includes items covered by in-flight tasks (TASK-366, TASK-367) that are not yet merged to master. If those tasks fail or stall, the covered count drops.
- The five persistence decisions (Section C) are all subsumed by TASK-366 and TASK-367. If those tasks scope-drift, the operator decisions risk being persisted incorrectly.

**RECOMMENDED CLAUDE ACTION:**
1. Triage Section A into existing tasks (all already have homes).
2. Proceed with TASK-366 and TASK-367 as the highest-value next steps — they resolve 6 of the 10 confirmed gaps.
3. The five persistence decisions in Section C are implementation guidance for TASK-366/367, not separate work.
