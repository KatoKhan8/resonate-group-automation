# TASK-514 — Independent GLM verification: TASK-406

## Target

    task            TASK-406
    branch          origin/qwen-worker-7-r9
    nominal SHA     8acee2e8bb6a9dc447cf7ee387888f613124cdb1
    actual SHA      14c9c1660b936473230cc693ee638ab7d84f03a3
    TASK-406 commit 6154ed344f44ecff6645b9ee0b184d0275b3ea50

**Branch has moved.** The branch HEAD is now `14c9c1660b936473230cc693ee638ab7d84f03a3`, not
the `8acee2e8bb6a9dc447cf7ee387888f613124cdb1` named in the dispatch. Per protocol,
reviewing the named SHA anyway — that is the artifact this verdict is about. Worktree
created at `8acee2e8b` (detached). TASK-406's own commit (`6154ed344`) is present on
that ref and is the unit under review.

## What TASK-406 claims

TASK-406 is a GLM first-pass verification of TASK-396. TASK-396's finding: **no
training-pair capture exists in the codebase.** No module pairs prompt+output+verdict,
no `src/training.py`, no `work/training/`, no JSONL storing triples. TASK-406 confirmed
this with its own independent grep/trace and disposed: finding HOLDS, EXISTING TASK
(TASK-310) addresses the gap.

TASK-406 changed no code. Its artifact is the finding itself, recorded in its task file.

## Independent verification

### 1. Does the artifact exist on this ref?

**YES.** `docs/qwen-tasks/REVIEW/TASK-406-glm-verify-task-396.md` exists at
`8acee2e8b` (167 lines). It was moved from `TODO/` by commit `6154ed344`.

```
git show 6154ed344 --stat
 → docs/qwen-tasks/REVIEW/TASK-406-glm-verify-task-396.md  | 167 +++
 → docs/qwen-tasks/TODO/TASK-406-glm-verify-task-396.md    |  29 ---
```

### 2. Does the finding hold? — My own independent trace

I searched the worktree at `8acee2e8b` with my own terms, independent of TASK-406's
and TASK-396's search terms.

**Searches performed (all in `src/`):**

| Pattern | Matches | Assessment |
|---------|---------|------------|
| `training` | 0 | No training module, no training references |
| `fine.tun\|fine_tun\|finetun` | 0 | No fine-tuning code |
| `feedback.loop\|annotation\|human.label\|human.verdict` | 0 | No human-feedback loop |
| `prompt.*store\|store.*prompt\|save.*prompt\|prompt.*save` | 2 | `generate.py:35` (PROMPTS dir for templates, not stored outputs); `llm.py:208` (explicit comment: "not stored anywhere") |
| `output.*store\|store.*output\|save.*output\|output.*save` | 1 | `candidateexport.py:175` (exports dir, not training data) |
| `jsonl.*prompt\|prompt.*jsonl\|jsonl.*output\|output.*jsonl` | 0 | No JSONL storing prompts or outputs |
| `capture.*pair\|pair.*capture\|training.*pair\|pair.*training` | 0 | No training-pair capture |
| `prompt.*output.*verdict\|input.*output.*label` | 0 | No prompt+output+verdict chain |
| `prompt.*response\|input.*response\|prompt.*completion` | 4 | All token-counting fields (`prompt_tokens`, `completion_tokens`), not content |
| `dataset\|corpus\|examples.*jsonl\|samples.*jsonl` | 20+ | All benchmark datasets, Apify research, cohort analysis — none training pairs |
| `append.*pair\|pair.*append\|write.*pair\|pair.*write` | 15 | All duplicate detection, lead pairing, QA — none training |
| `work.*training\|training.*work` | 0 | Nothing |
| `reviewapproval.*record\|record.*reviewapproval` | 0 | No hook into reviewapproval |

**File existence checks:**

| Path | Exists? |
|------|---------|
| `src/training.py` | NO |
| `work/training/` | NO |
| `src/learning.py` | YES — cohort analysis (observational statistics), not training capture |
| `src/variants.py` | YES — `evaluate()` at line 434 ranks A/B variants by outcome rates |
| `src/reviewapproval.py` | YES — `record()` at line 99 writes metadata only (campaign, review_hash, by, source, note) |
| `src/llm.py` | YES — `record_usage_since()` at line 977 writes usage metrics only (step, model, adapter, tokens) |
| `docs/qwen-tasks/TODO/TASK-310-every-approved-file-feeds-the-training-set.md` | YES — the capture spec, still in TODO |

**Verdict: TASK-396's negative finding is CORRECT. No training-pair capture exists.**

### 3. File:line citation verification

TASK-406 cited six specific locations. I verified each:

| Citation | Verified? | What I found |
|----------|-----------|--------------|
| `src/llm.py:208` — "not stored anywhere" | **YES** | Line 208: `# raw payload carries the prompt back and is not stored anywhere.` |
| `src/llm.py:977-1005` — `record_usage_since()` | **YES** | Lines 977-1005: appends step, model, adapter, at, token counts. No prompt text, no output content. |
| `src/reviewapproval.py:97-115` — `record()` | **YES** | Lines 99-113: writes campaign, review_hash, by, source, note. No prompt text, no approved content. |
| `src/variants.py:434-480` — `evaluate()` | **YES** | Line 434: `def evaluate(node, results, config=None, progress=None, objective=None)`. Ranks variants by exposures, replies, Wilson intervals. No training capture. |
| `src/learning.py:0-50` — cohort analysis | **YES** | Module docstring: "Which cohorts are doing better, said carefully enough to act on." Observational statistics, not training data. |
| `docs/qwen-tasks/TODO/TASK-310-*` — capture spec in TODO | **YES** | File exists. Describes the capture to build. |

All six citations are accurate.

### 4. Falsification attempt

I tried to prove the finding wrong by searching for:
- Any form of model output persistence (prompt+response, input+completion) — nothing
- Any feedback loop or annotation mechanism — nothing
- Any JSONL file storing model interactions — nothing
- Any hook from reviewapproval into content capture — nothing
- Any subtle variant (dataset, corpus, examples.jsonl) — all are benchmark/research data, not training pairs

**Could not falsify.** The negative finding holds under independent search with different terms.

### 5. Would merging delete anything?

The branch diff from master: 113 files changed, +15,879 / -671.

Four files show as "deleted" from `docs/qwen-tasks/TODO/`:
- `TASK-264-every-test-module-runs-in-isolation.md` → moved to REVIEW/
- `TASK-389-contact-key-guard-cleanup.md` → moved to REVIEW/
- `TASK-406-glm-verify-task-396.md` → moved to REVIEW/
- `TASK-440-glm-verify-task-281.md` → moved to DONE/

These are all task lifecycle moves (TODO → REVIEW/DONE), not content deletions. Each
has a corresponding file in REVIEW/ or DONE/ on the branch. No source code, tests,
documentation, or configuration is deleted.

**TASK-406 itself** changed only 2 files (the task file move). Its cherry-pick is clean
and isolated.

### 6. Scope drift

The branch carries massive scope from many other tasks (TASK-396, TASK-400, TASK-425,
TASK-427, TASK-430, plus ~20 other GLM verdicts). TASK-406's own commit is clean:
2 files, both task-file lifecycle. Cherry-pick of `6154ed344` would bring only the
task file move with no collateral.

## Findings

### Finding 1: TASK-406's verification is correct

**Disposition: CONFIRMED**

TASK-406 independently verified TASK-396's negative finding with its own search terms
and reached the correct conclusion. My own independent trace with yet different search
terms reaches the same conclusion: no training-pair capture exists.

Evidence:
- 13 independent search patterns, all consistent with "nothing exists"
- 6 file:line citations verified accurate
- Falsification attempt failed
- TASK-310 (the capture specification) confirmed still in TODO

### Finding 2: No new finding emerged

**Disposition: N/A (informational)**

My independent trace found nothing TASK-406 missed. The negative finding is solid.

## Protocol dispositions

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | TASK-396's negative finding (no training-pair capture) | CONFIRMED — finding holds |
| 2 | TASK-406's verification methodology | CONFIRMED — thorough and accurate |
| 3 | TASK-310 as the address for the gap | EXISTING TASK — still in TODO |

## Recommendation

**CLOSE.** TASK-406 is a finding-only verification task. Its finding is correct, its
citations are accurate, and its disposition (EXISTING TASK → TASK-310) is appropriate.
No code was changed, no tests are needed, and the cherry-pick is clean. The finding
adds confidence that the gap is real and correctly characterised.

The branch as a whole carries significant scope from many other tasks. TASK-406's own
commit (`6154ed344`) is isolated and safe to cherry-pick if desired, but the finding
is already durable in the task file and does not require integration to be useful.

## Reproducible commands

```bash
# Create worktree at the exact SHA
git worktree add .qwen/worktrees/glm-514 8acee2e8bb6a9dc447cf7ee387888f613124cdb1 --detach

# Verify the finding
cd .qwen/worktrees/glm-514
grep -rn "training" src/                    # 0 matches
ls src/training.py                          # does not exist
ls work/training/                           # does not exist
grep -rn "prompt.*store\|store.*prompt" src/  # 2 matches, neither stores content
grep -rn "jsonl.*prompt\|prompt.*jsonl" src/  # 0 matches
grep -rn "capture.*pair\|pair.*capture" src/  # 0 matches
grep -rn "fine.tun\|fine_tun\|finetun" src/  # 0 matches
grep -rn "feedback.loop\|annotation" src/    # 0 matches

# Verify TASK-406's commit
git show 6154ed344 --stat                   # 2 files: task file move TODO→REVIEW

# Check merge safety
git diff master...8acee2e8bb6a9dc447cf7ee387888f613124cdb1 --diff-filter=D --name-only
# 4 task files, all moved to REVIEW/ or DONE/
```
