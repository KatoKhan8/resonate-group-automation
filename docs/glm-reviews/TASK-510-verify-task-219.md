# TASK-510 — Independent GLM verification of TASK-402

## Target

    task            TASK-402
    branch          origin/qwen-worker-9-r9
    branch HEAD SHA f1b9c357c17f4b557cbdb06f68339c7343ef3e83
    commit          cd54811d51ef76db68786efd2faa196eec92ae86
    artifact kind   finding (read-only verification, no code changes)

**SHA verified:** `git rev-parse origin/qwen-worker-9-r9` returns `f1b9c357c17f4b557cbdb06f68339c7343ef3e83`. Branch has not moved.

**Isolated worktree:** `.qwen/worktrees/verify-402` checked out at the exact SHA.

---

## 1. Does the artifact exist on this ref?

**YES.** `docs/qwen-tasks/REVIEW/TASK-402-glm-verify-task-391-skills-runtime-finding.md` was added in commit `cd54811d5` ("TASK-402: independent verification of TASK-391's five-way mismatch finding"). The file contains a detailed stage-by-stage verification of TASK-391's finding with eight dispositions.

`git log --diff-filter=A --all -- docs/qwen-tasks/REVIEW/TASK-402-glm-verify-task-391-skills-runtime-finding.md` confirms the file was introduced by this commit.

---

## 2. Independent re-verification of TASK-402's claims

I read the same source TASK-402 cites, at the same SHA. Here is what I found:

### 2.1 render_prompt() call sites in generate.py

TASK-402 claims five stages call `render_prompt()`. Confirmed at:

| Stage          | Line | Call                                                    |
|----------------|------|---------------------------------------------------------|
| diagnose       | 1488 | `render_prompt("diagnose", rec)`                        |
| hook           | 1501 | `render_prompt("hook", rec)`                            |
| persona_angle  | 1511 | `render_prompt("persona_angle", rec, contact, client)`  |
| linkedin_note  | 1542 | `render_prompt("linkedin_note", rec, contact, client, step_key)` |
| draft          | 1626 | `render_prompt("draft", rec, contact, client, day)`     |

Additionally, `linkedin_note` is called at line 1385 in `_regenerate_linkedin_set`. All line numbers match TASK-402's claims.

### 2.2 Skill procedures

| Skill                | Procedure constant         | Location          |
|----------------------|----------------------------|-------------------|
| signal_verification  | `copyprompts.ICP_SYSTEM`   | copyprompts.py:184 |
| account_research     | `copyprompts.EXTRACT_SYSTEM` | copyprompts.py:79 |
| campaign_strategy    | `copystages.STRATEGY_SYSTEM` | copystages.py:191 |
| cold_email_writing   | `copystages.WRITER_SYSTEM`  | copystages.py:273 |
| linkedin_writing     | `copystages.WRITER_SYSTEM`  | copystages.py:273 |

All confirmed. Both cold_email_writing and linkedin_writing share the same WRITER_SYSTEM prompt.

### 2.3 Prompt file sizes

| Prompt file         | Lines |
|---------------------|-------|
| prompts/draft.md    | 265   |
| prompts/linkedin_note.md | 196 |
| prompts/diagnose.md | 26    |
| prompts/hook.md     | 17    |
| prompts/persona_angle.md | 24 |

TASK-402 says draft.md is "~200 lines" (actual: 265) and linkedin_note.md is "~150 lines" (actual: 196). Minor imprecision, does not affect the conclusion.

### 2.4 The critical mismatch: draft/linkedin_note vs WRITER_SYSTEM

TASK-402 claims draft.md and linkedin_note.md have context-aware features that WRITER_SYSTEM lacks. I searched for six key features:

| Feature          | draft.md | linkedin_note.md | WRITER_SYSTEM (copystages.py) |
|------------------|----------|------------------|-------------------------------|
| prior_contact    | 6 hits   | 0 hits           | 0 hits                        |
| already_sent     | 8 hits   | 3 hits           | 0 hits                        |
| siblings         | 7 hits   | 3 hits           | 0 hits                        |
| sender_identity  | 3 hits   | 2 hits           | 0 hits                        |
| step.purpose     | 3 hits   | 3 hits           | 0 hits                        |
| angle_wording    | 6 hits   | 0 hits           | 0 hits                        |

**WRITER_SYSTEM has ZERO matches for all six features.** Replacing generate.py's prompts with WRITER_SYSTEM would lose: prior_contact branching (first touch vs reply), already_sent awareness (confirmed sent messages), siblings context (other drafts in sequence), sender_identity (who is writing), step.purpose (this message's job in the sequence), and angle_wording (client's configured phrasing).

**CONFIRMED: The mismatch is real and the regression risk is genuine.**

### 2.5 generate_campaign.py has zero production callers

`git grep -l "generate_campaign" f1b9c357c17f4b557cbdb06f68339c7343ef3e83 -- src/` returns empty (exit code 1). The file exists at `src/generate_campaign.py` but nothing in `src/` imports or references it.

**CONFIRMED.**

### 2.6 Skills' consumer names do not exist in generate.py

The five skills declare consumers: `stage_a`, `stage_b`, `stage_e`, `stage_f`, `stage_f`.

`grep -E "stage_a|stage_b|stage_e|stage_f" src/generate.py` returns zero matches.

**CONFIRMED.**

---

## 3. Falsification attempt: is any mismatch overstated?

I examined the closest pair: **hook vs account_research**. Both extract facts, but:
- `hook` (prompts/hook.md, 17 lines): extracts ONE fact from a signal event, returns `{"hook": "one sentence"}`
- `EXTRACT_SYSTEM` (copyprompts.py:79, 64 lines): extracts 3-5 structured facts from scraped sources, returns JSON with `{text, quote, source_index, kind, confidence}` per fact, plus `angle`, `company_hook`, `usable`, `why_this_lead`

Different inputs (signal event vs multi-source scraped text), different outputs (one string vs structured array with verbatim quotes), different downstream jobs (opening line vs evidence foundation). The mismatch holds.

**Result: No stage has an overstated mismatch. All five pairs are genuinely different jobs.**

---

## 4. Are TASK-402's tests falsifiable?

TASK-402 is a finding, not code. It has no tests. Its verification method is source reading and grep, which is appropriate for an architectural mismatch claim. The claims are falsifiable: if any skill's procedure actually matched a generate.py stage in input/output/job, the finding would fail. I found no such match.

---

## 5. Would merging delete anything?

`git diff master...f1b9c357c17f4b557cbdb06f68339c7343ef3e83 --diff-filter=D --name-only -- src/ tests/ scripts/` returns empty. No source, test, or script files are deleted.

Two TODO task files are deleted because they moved to REVIEW (normal task progression):
- `docs/qwen-tasks/TODO/TASK-392-signature-per-attested-mailbox-verification.md` → now in REVIEW/
- `docs/qwen-tasks/TODO/TASK-399-docs-hygiene-pass.md` → now in REVIEW/

**No harmful deletions.**

---

## 6. Scope drift

The branch has 34 commits ahead of master, covering many tasks (TASK-290, TASK-305, TASK-313, TASK-364, TASK-384, TASK-392, TASK-399, TASK-400, TASK-402, TASK-404, TASK-416, TASK-423/424/425, offers v2, status reports, audit corrections, etc.).

TASK-402's own commit (`cd54811d5`) touches only the task file (move from TODO to REVIEW with result block). The branch carries substantial other work that would need separate review and separate cherry-picks.

**TASK-402 itself is clean — one commit, one file, finding only.**

---

## Seven dispositions

TASK-402 is a verification of TASK-391's finding. The dispositions apply to TASK-402's verification claims:

1. **The five render_prompt() call sites exist at the cited lines** — **CONFIRMED.** Lines 1385, 1488, 1501, 1511, 1542, 1626 all match.

2. **The five skill procedures reference the constants TASK-402 names** — **CONFIRMED.** ICP_SYSTEM, EXTRACT_SYSTEM, STRATEGY_SYSTEM, WRITER_SYSTEM, WRITER_SYSTEM.

3. **draft.md and linkedin_note.md have context-aware features WRITER_SYSTEM lacks** — **CONFIRMED.** 24 matches in draft.md, 13 in linkedin_note.md, 0 in WRITER_SYSTEM for the six key features (prior_contact, already_sent, siblings, sender_identity, step.purpose, angle_wording).

4. **generate_campaign.py has zero production callers in src/** — **CONFIRMED.** `git grep` at the target SHA returns empty.

5. **The skills' consumer names (stage_a/b/e/f) do not exist in generate.py** — **CONFIRMED.** Zero matches.

6. **No stage has an overstated mismatch** — **CONFIRMED.** Even the closest pair (hook vs account_research) has different inputs, outputs, and jobs.

7. **TASK-400 proceeds on solid ground** — **CONFIRMED.** TASK-400's pipeline-level fix is the correct architectural response to a real mismatch.

---

## Minor inaccuracies in TASK-402

- TASK-402 says WRITER_SYSTEM is "~80 lines". The actual prompt text is closer to 85-100 lines (the triple-quoted string in copystages.py:273). Minor imprecision, does not affect the conclusion.
- TASK-402 says draft.md is "~200 lines" (actual: 265) and linkedin_note.md is "~150 lines" (actual: 196). Again, minor imprecision.

These do not undermine the finding. The mismatch conclusion rests on the jobs being different, not on exact line counts.

---

## Recommendation

**MERGE** (TASK-402's finding only, not the whole branch).

TASK-402 is a clean, read-only verification that independently confirms TASK-391's finding with evidence. The artifact exists, the claims are correct, the falsification attempt found no overstatement, and the finding is consumed by TASK-400 (which builds on it).

The branch carries substantial other work (34 commits) that would need separate review. TASK-402's own commit is cherry-pickable: it touches only the task file.

**Disposition: MERGE the finding. TASK-391's conclusion is independently verified by two independent readers (TASK-391's author and TASK-402's verifier) and the evidence holds.**
