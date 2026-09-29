# TASK-514 — Independent verification of TASK-406

## Target

    task            TASK-406
    branch          origin/qwen-worker-7-r9
    branch HEAD SHA 8acee2e8bb6a9dc447cf7ee387888f613124cdb1

**Note:** The branch HEAD has moved since this task was dispatched. Current HEAD
of `origin/qwen-worker-7-r9` is `8447b1fa11cdf2960aa8c2eb2cb687204e83ca9b`. This
verdict reviews the exact SHA named in the task file: `8acee2e8`.

**Isolated worktree:** `.qwen/worktrees/task514-review`, detached at `8acee2e8`.

## What TASK-406 claims

TASK-406 is itself a GLM verification of TASK-396. TASK-396's finding: **no
training-pair capture exists in the codebase** — nothing pairs prompt + output +
human verdict. TASK-406 independently confirmed this with its own grep/trace and
cited specific file:line evidence for the three paths that might have captured
pairs but do not.

## What I verified

### 1. Does the artifact exist on this ref?

**Yes.** `docs/qwen-tasks/REVIEW/TASK-406-glm-verify-task-396.md` exists at
`8acee2e8` (167 lines). It was added by commit `6154ed34`.

### 2. Independent grep/trace — my own search terms

I used different search terms from both TASK-396 and TASK-406:

| Search term | Matches in `src/` | Interpretation |
|---|---|---|
| `training` | **0** | No training-related code at all |
| `training.?pair\|pair.?training\|fine.?tun\|rlhf\|dpo\|preference.?pair` | **150** | All false positives: "endpoint", "ThreadPoolExecutor", ctypes struct fields — none about ML training |
| `prompt.*store\|store.*prompt\|save.*prompt\|prompt.*persist` | **2** | `generate.py:35` (PROMPTS dir for templates), `llm.py:208` (explicitly says prompt is NOT stored) |
| `jsonl.*prompt\|prompt.*jsonl\|jsonl.*output\|output.*jsonl` | **0** | No JSONL storing prompts or outputs |
| `capture.*pair\|pair.*capture\|append.*pair\|write.*pair` | **7** | All about duplicate detection, lead pairing, demo pairing — not training pairs |
| `prompt.*output\|input.*output.*store` | **0** | No prompt+output pairing |

**Files/directories confirmed absent:**
- `src/training.py` — does not exist
- `work/training/` — does not exist

### 3. File:line citations verified

TASK-406 cited three specific paths. I read each one:

| Citation | Verified? | What it actually stores |
|---|---|---|
| `src/llm.py:208` | **Yes** | Comment: "The raw payload carries the prompt back and is not stored anywhere." |
| `src/llm.py:977-1005` `record_usage_since()` | **Yes** | step, model, adapter, timestamp, token counts — metrics only, no content |
| `src/reviewapproval.py:99-115` `record()` | **Yes** | campaign, review_hash, by, source, at, note — metadata only, no prompt or output |
| `src/variants.py:434-480` `evaluate()` | **Yes** | exposures, replies, Wilson intervals — ranking only, no content |
| `src/learning.py:0-50` | **Yes** | Module docstring: "Which cohorts are doing better" — observational cohort analysis |

All five citations are accurate. None of these functions store prompt text or
model output content.

### 4. TASK-310 still exists in TODO

**Confirmed.** `docs/qwen-tasks/TODO/TASK-310-every-approved-file-feeds-the-training-set.md`
exists at `8acee2e8`. It specifies the capture to build (hook
`reviewapproval.record()`, write JSONL to `work/training/`). The "EXISTING TASK"
disposition is correct — the work is queued but not done.

### 5. Falsification attempt

I tried to find something TASK-406 missed:
- Searched for any function that writes both prompt-like and output-like data to
  the same store → nothing
- Searched for any JSONL writer that includes both "prompt" and "output" fields →
  nothing
- Searched for any hook from `reviewapproval.record()` that captures content →
  none exists; `record()` takes only campaign, hash, author, source, timestamp,
  note
- Searched for any reference to "fine-tune", "RLHF", "DPO", "preference" in
  src/ → zero matches for the ML-training sense

**Result: nothing found. The negative finding holds.**

### 6. Would merging delete anything?

`git diff master...8acee2e8 --diff-filter=D` shows four deleted files, all task
queue files (TODO → REVIEW/DONE moves):
- `docs/qwen-tasks/TODO/TASK-264-*` (moved to DONE)
- `docs/qwen-tasks/TODO/TASK-389-*` (moved to REVIEW)
- `docs/qwen-tasks/TODO/TASK-406-*` (moved to REVIEW)
- `docs/qwen-tasks/TODO/TASK-440-*` (moved to DONE)

**No production code, tests, or documentation deleted.** Safe.

### 7. Scope drift

The branch carries substantial work beyond TASK-406 — many TASK-xxx commits
touching `src/`, `tests/`, and `docs/`. TASK-406 itself only changes its own
task file (TODO → REVIEW). Cherry-picking TASK-406's commit (`6154ed34`) is
clean: it moves one task file.

## Disposition

**TASK-406's finding: CONFIRMED**

The negative finding is correct. No training-pair capture exists. TASK-406's
file:line citations are accurate. TASK-406's grep/trace was thorough and used
sufficiently different search terms from TASK-396 that two independent passes
covering the same ground increases confidence.

**Disposition: EXISTING TASK (TASK-310)** — unchanged from TASK-406's own
disposition. The capture is specified but not built.

## Recommendation

**CLOSE.** TASK-406 is a verification-only task. Its finding is correct, its
citations are accurate, and its disposition is right. No new finding emerged
from independent verification. Merging is safe (only task-file moves, no
production changes).

## Evidence summary

- `src/llm.py:208` — prompt explicitly not stored
- `src/llm.py:977` — `record_usage_since()` stores metrics only
- `src/reviewapproval.py:99` — `record()` stores metadata only
- `src/variants.py:434` — `evaluate()` ranks variants, no content capture
- `src/learning.py:1-10` — cohort analysis, not training data
- `src/training.py` — does not exist
- `work/training/` — does not exist
- `docs/qwen-tasks/TODO/TASK-310-*` — the capture spec, still in TODO
