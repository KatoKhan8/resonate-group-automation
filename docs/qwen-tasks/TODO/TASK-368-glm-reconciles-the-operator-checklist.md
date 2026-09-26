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
