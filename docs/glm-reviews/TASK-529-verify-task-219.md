# TASK-529 — GLM Independent Verification of TASK-423

**Verdict date:** 2026-09-29
**Reviewer:** GLM (independent, read-only)
**Target task:** TASK-423 — failure taxonomy of the fifty's 37 non-passing leads
**Target branch:** `origin/qwen-worker-6-r9`
**Branch HEAD SHA reviewed:** `6aa450938b035e4486a8e13096da83d0c2f0d067`
**Worktree:** `.qwen/worktrees/glm-529` (detached at exact SHA)

---

## SCOPE OF REVIEW

TASK-423 is a **read-only analysis task** producing a failure taxonomy document. It claims to:
1. Assign exactly one primary reason code and stage to each of 37 non-passing leads
2. Produce a Pareto table accounting for all 37
3. Identify the mechanism behind the 13 `unrendered_variable` failures
4. Name 6 fixes ordered by impact

No code changes. No test changes. No gate modifications.

---

## FINDING 1 — Artifact existence

**Status:** VERIFIED

`docs/TASK-423-FAILURE-TAXONOMY.md` exists at `6aa45093` (352 lines). Created by commit `f933ec7a`, updated by `46327108`. The task file is at `docs/qwen-tasks/REVIEW/TASK-423-failure-taxonomy-of-the-fifty.md`.

The artifact is referenced in:
- `docs/INTEGRATION-QUEUE-2026-09-27.md` (line 516, 925)
- `docs/OPERATING-MODE.md` (line 208, 221)
- `docs/PRODUCTION-HANDOFF-2026-09-28-NIGHT.md` (line 206)
- `docs/state/TASK-REGISTRY.json` (line 2085)

**Consumption:** This is a document/analysis task. Its consumers are human decision-makers (Claude, integration queue). No code consumption is expected or claimed. The document is consumed by the integration/handoff process.

---

## FINDING 2 — Pareto table arithmetic

**Status:** VERIFIED

Claimed: 13 + 13 + 4 + 3 + 2 + 2 = 37

| Rank | Reason code            | Count | Cumulative |
|------|------------------------|-------|------------|
| 1    | `not_an_agency`        | 13    | 13         |
| 2    | `unrendered_variable`  | 13    | 26         |
| 3    | `no_pack_facts`        | 4     | 30         |
| 4    | `channels_complement`  | 3     | 33         |
| 5    | `claims_supported`     | 2     | 35         |
| 6    | `missing_company_data` | 2     | 37         |

**Sum: 37.** Each lead appears exactly once in the per-lead table. The largest buckets are specific and actionable, not "other" or "unknown".

---

## FINDING 3 — `{firstName}` mechanism claim

**Status:** VERIFIED

The taxonomy claims: writer prompts use `{firstName}` (camelCase), email templates use `{first_name}` (snake_case), and LinkedIn steps bypass `render()`.

**Verification at cited lines:**

| Claim | Evidence |
|-------|----------|
| `copystages.py:332` contains `{firstName}` | `voice as the emails, \`{firstName}\` opening every message after the connect` — CONFIRMED |
| `copyprompts.py:343` contains `{firstName}` | `**\`{firstName}\` opens every message after the connect.**` — CONFIRMED |
| `cadence.py` uses `{first_name}` | Lines 359, 362, 366, 389, 399, 436, 455, 506, 521, 543, 552, 569 all use `{first_name}` — CONFIRMED |
| LinkedIn steps bypass `render()` | `generate_campaign.py:477`: `li_text = (w.get("linkedin") or {}).get(key, "")` — model output stored directly, no render/format call. No `render()` or `.format()` call exists for LinkedIn text in `generate_campaign.py` — CONFIRMED |
| `UNRENDERED_RE` catches `{...}` | `copylint.py:481`: `UNRENDERED_RE = re.compile(r"\{\{?\s*[A-Za-z_][A-Za-z0-9_]*\s*\}?\}|%\([A-Za-z_]+\)s")` — matches `{firstName}` — CONFIRMED |

**The naming mismatch is real.** Prompts instruct the model to write `{firstName}` (camelCase, EmailBison merge-field convention). Email templates use `{first_name}` (snake_case, Python `str.format()` convention). LinkedIn output bypasses `render()` entirely, so the token survives verbatim.

---

## FINDING 4 — Per-lead classification integrity

**Status:** VERIFIED WITH CAVEAT

Each of the 37 leads appears exactly once in the per-lead table. Classifications use earliest-pipeline-stage rule (e.g., 5 leads that also failed sequencegate are classified at RENDER because unrendered variable is earlier).

**Caveat:** The taxonomy acknowledges `fifty-data.json` is missing from all worktrees. Analysis was reconstructed from posted HTML/XLSX review files and `sample50-built.json`. The 8 "copylint-only" leads (R12, R13, R14, R19, R20, R37, R41, R43) are classified from TASK-342's re-lint numbers, not from direct measurement of the source data.

This is a data-provenance limitation, not a logic error. The task was transparent about it.

---

## FINDING 5 — Fix list quality

**Status:** VERIFIED

Each of the 6 fixes names:
- A file (or upstream location)
- An upstream cause
- A count of leads unblocked
- Specific lead IDs

Fix 1 (`{firstName}` substitution, 13 leads) correctly identifies both parts: (a) change prompts to use actual names, (b) add post-generation substitution as safety net. This is the right fix shape — addressing the prompt/render mismatch rather than loosening the gate.

Fix 2 (list pre-filtering, 13 leads) correctly identifies this as upstream of the pipeline — the list sourcing problem, not a pipeline defect.

No fix proposes loosening a gate. This complies with the task's "rule that outranks finishing."

---

## FINDING 6 — Deletion check

**Status:** NO PRODUCTION DELETIONS

`git diff master...6aa45093 --diff-filter=D --name-only -- src/ tests/` returns empty. No source or test files would be deleted.

Three task files are deleted from `docs/qwen-tasks/TODO/` (TASK-391, TASK-419, TASK-439) — these are task lifecycle moves (TODO → REVIEW/DONE), not production deletions.

---

## FINDING 7 — Scope drift

**Status:** SIGNIFICANT BRANCH-LEVEL DRIFT, TASK-423 ISOLATED

The branch `qwen-worker-6-r9` carries 40 commits not in master, spanning TASK-400, TASK-246, TASK-439, TASK-445, TASK-455, TASK-461, and others. The full branch diff is 43 files, +5887/-413 lines.

**TASK-423's own work is cleanly separable:** 3 commits (`f933ec7a`, `46327108`, `d76f860d`) touching only 2 files:
- `docs/TASK-423-FAILURE-TAXONOMY.md` (NEW, 352 lines)
- `docs/qwen-tasks/REVIEW/TASK-423-failure-taxonomy-of-the-fifty.md` (task file)

Cherry-pick of TASK-423 alone is straightforward and carries no risk of pulling in other tasks' work.

---

## FINDING 8 — Falsification attempts

### Attempt 1: Could the math be wrong?
Counted each row in the per-lead table: 19 (QUALIFICATION) + 13 (RENDER) + 3 (SEQUENCEGATE/channels) + 2 (SEQUENCEGATE/claims) = 37. Math is correct.

### Attempt 2: Could the `{firstName}` mechanism be wrong?
Checked every cited line. The naming mismatch (`firstName` vs `first_name`) and the render bypass are both real. The regex in copylint matches `{firstName}`. The mechanism is correct.

### Attempt 3: Could a gate have been loosened?
No src/ or test files were modified by TASK-423's commits. No gate changes.

### Attempt 4: Could PII have been committed?
The taxonomy uses `R##` identifiers (row numbers). No email addresses, personal names, or domains appear in the committed file. Confirmed by inspection.

---

## DISPOSITION

| Finding | Status |
|---------|--------|
| Artifact exists | VERIFIED |
| Pareto math | VERIFIED (37 = 37) |
| `{firstName}` mechanism | VERIFIED at cited lines |
| Per-lead classification | VERIFIED WITH CAVEAT (source data missing, task was transparent) |
| Fix list quality | VERIFIED (no gate loosening, correct fix shape) |
| No production deletions | VERIFIED |
| Scope drift | Branch-level drift present, TASK-423 isolated and cherry-pickable |
| No PII committed | VERIFIED |

---

## RECOMMENDATION

**MERGE** (TASK-423's own commits via cherry-pick)

The analysis is sound, the mechanism claim is verified against the actual code at the cited lines, the math adds up, and the artifact is consumed by the integration/handoff process. The task respected all boundaries: no critical-path edits, no gate loosening, no PII.

The missing `fifty-data.json` is a data-provenance concern, not a defect in the taxonomy. The task was transparent about reconstructing from posted artifacts.

**Cherry-pick the 3 TASK-423 commits** (`f933ec7a`, `46327108`, `d76f860d`) rather than merging the full branch, which carries 37 other commits from multiple tasks.

---

## BOUNDARIES OBSERVED

- Read-only review. No production files modified.
- No provider calls. No campaign mutations.
- Worktree isolated at exact SHA `6aa450938b035e4486a8e13096da83d0c2f0d067`.
- Verdict is the deliverable. Claude merges.
