PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-416 — Research Store Freshness Check (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `research-store-freshness-check`.

For a sample of records with `rec["research"]` populated, check how old the
research is (site-crawl timestamp if one exists) against when the record
was last touched. Report the honest distribution — is stale research
silently informing current copy? Acceptance: a real sample (20+ records),
ages reported, not estimated.

---

## RESULT BLOCK

**STATUS:** PARTIAL — code path analysis complete, measurement script written,
live-data run is OWED (no queue in this worktree).

**ARTIFACT KIND:** Code (measurement script) + Finding (code path analysis).

**COMMIT SHA:** (see git log)

**TESTS:** Script parses clean. Not runnable here — no `work/queue.jsonl`.

**FILES CHANGED:**
- `scripts/measure_research_freshness.py` — new. Run against live queue.
- `docs/qwen-tasks/RUNNING/TASK-416-research-store-freshness-check.md` — this file.

**FILES FORBIDDEN:** None named.

---

### FINDINGS

#### 1. Live-data measurement is owed

This worktree has no `work/queue.jsonl` and no `work/queue.db`. The manifest
(`docs/state/QUEUE-MANIFEST.json`, generated 2026-09-20) reports 550 records
but carries no per-record research data. The measurement script
(`scripts/measure_research_freshness.py`) must be run from Claude's worktree:

    python scripts/measure_research_freshness.py

It samples up to 50 records with research, re-ages every entry against today,
and reports the full distribution.

#### 2. Code path analysis — stale research CAN silently inform copy

The freshness system has a re-aging mechanism (`evidence.recheck`) that
re-derives age, freshness bucket, and quality against today. But it is not
applied uniformly.

**Paths that DO re-age (safe):**

| Path | How |
|------|-----|
| `personalization.stored()` | `evidence.recheck(entry, today)` per entry |
| `research.for_prompt()` | → `evidence.select()` → `usable()` → `reaged()` |
| `quality.evidence_recency()` | `evidence.recheck(item, today)` per entry |

**Paths that read FROZEN quality (potentially stale):**

| Path | What it does |
|------|-------------|
| `generate.research_block()` | Filters by `e.get("quality") in ("medium","strong")` — the quality frozen at storage time. A fact that was "strong" when crawled 8 months ago still passes, even though re-aged it would be BACKGROUND/WEAK. |
| `claims._support_text()` | Reads `rec["research"]` raw for claim-checking haystack. No re-aging. |
| `eligibility.py` | Reads research entries without re-aging. |
| `dossier.py` | Counts research entries without re-aging. |
| `preview.py` | Filters research without re-aging. |
| `llm.py` | Walks research facts for token matching. No re-aging. |
| `generate._evidence_fingerprint()` | Reads `retrieved_at` for cache keying. Not a quality path. |

#### 3. The critical gap: `research_block` reaches the draft prompt

`generate.company_evidence(rec)` builds a cached block with TWO evidence
projections:

1. `public_evidence` from `research.for_prompt(rec)` → **re-aged, safe**
2. `research` from `research_block(rec)` → **frozen quality, NOT re-aged**

Both are injected into the prompt for the `draft` and `linkedin_note` steps
(the actual copy generation steps). The model receives:
- `public_evidence`: only currently-USABLE facts (re-aged)
- `research`: facts that WERE medium/strong when stored, regardless of age

If a fact was crawled 200 days ago and scored "strong" then, it is now in
the LOW bucket (91-365 days) but still passes `research_block`'s frozen
filter. The model sees it and may write from it. At 366+ days the frozen
quality still says "strong" or "medium" while re-aged quality would be
WEAK (BACKGROUND bucket caps at WEAK per `evidence.quality()`).

The freshness policy is: HIGH ≤ 30d, MEDIUM ≤ 90d, LOW ≤ 365d,
BACKGROUND > 365d. BACKGROUND caps quality at WEAK, which is not USABLE —
`evidence.select()` would exclude it, but `research_block()` does not call
`select()`.

#### 4. What `research_state.company_at` tells us

`personalization.mark_company_done()` records `company_at: store.now()` when
research completes. This timestamp says WHEN research was done, not how fresh
the underlying facts are. A record researched on 2026-05-01 has `company_at`
from May but its research entries carry their own `published_at` and
`retrieved_at` dates. The gap between `company_at` and the evidence dates
is the staleness window.

#### 5. The `recheck` function already exists

`evidence.recheck()` was clearly built to solve this problem (the docstring
says: "a draft written in March could still be sent in September describing
its supporting fact as fresh, because the number saying it was fresh was
written in March"). The fix for `research_block()` would be to route it
through `evidence.reaged()` or `evidence.select()` the same way
`research.for_prompt()` does. Three lines of change.

---

### RISKS

- **Stale copy reaching prospects.** The `research_block` path is the most
  direct: frozen-quality facts reach the model that generates the actual
  email text. A 10-month-old "strong" fact about a company event that has
  since passed could lead with "I noticed you recently..." in September
  about something from November.
- **The mitigation is partial.** `research.for_prompt()` does re-age, and
  its output (`public_evidence`) also reaches the prompt. But the model
  receives BOTH blocks and may prefer the `research` block's facts because
  they include more detail (fact text up to 400 chars vs 800 chars for
  `public_evidence`, but `research_block` has 5 entries vs 3).

### RECOMMENDED CLAUDE ACTION

1. **Run the measurement script** from Claude's worktree to get the actual
   distribution. The script is ready.
2. **Fix `generate.research_block()`** to re-age before filtering. Route
   through `evidence.reaged()` or `evidence.select()` — same as
   `research.for_prompt()`. This is the gap that lets stale research inform
   copy.
3. **Audit the other frozen-quality readers** (`claims._support_text`,
   `eligibility`, `dossier`, `preview`, `llm`) for whether they need
   re-aging too. The claims haystack is the most urgent after
   `research_block`: a claim check passing against a stale fact is a false
   positive that lets invented copy through.
