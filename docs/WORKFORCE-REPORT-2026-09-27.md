# WORKFORCE REPORT — 2026-08-01 to 2026-09-27

**Prepared:** 2026-09-28, from machine state only.
**Period:** 2026-08-01 to 2026-09-27.
**Prepared by:** Qwen worker-7 (TASK-429).

---

## THE ONE THING TO KNOW BEFORE READING THIS REPORT

**Every number in this document names its source. Every cell that has no machine
source reads `UNKNOWN`.** Nothing here is interpolated from a handoff's prose,
from a task file's own claim about itself, or from an estimate. Where the
honest answer is "we cannot measure this", the report says so — and says what
would have to exist to fill the gap. That list of gaps is itself a useful
result: it says what this project cannot currently measure about its own
workforce.

**The repository was created on 2026-09-09.** There are zero commits before that
date. The report period 2026-08-01 to 2026-09-08 has no machine state at all.
All data in this report covers 2026-09-09 to 2026-09-27 (19 days).

---

## PART 1 — PER WORKER

### Definitions stated before the numbers

**"Tasks delivered"** — a task file whose directory is `docs/qwen-tasks/DONE/`
on master. Source: `ls docs/qwen-tasks/DONE/` filtered to `.md` files. Count:
**268**.

**"Accepted first pass"** — a task in DONE whose RESULT block contains
`STATUS: DONE` or `STATUS: COMPLETE` (case-insensitive). This is the weakest
available proxy: it means the task file claims it was done, not that a reviewer
accepted it without rework. A task that was reworked and then moved to DONE
still reads as "accepted" here because the directory does not distinguish
first-pass from reworked completions. Source: `grep STATUS: docs/qwen-tasks/DONE/*.md`.
Count: **89 DONE + 1 COMPLETE = 90** with extractable status; **156 more** have
RESULT blocks but no parseable STATUS line (often `STATUS: **DONE**` with
markdown bold that the regex captures differently, or no STATUS field at all).
**32 DONE files have no RESULT block.**

**"Reworks"** — a task file currently in `docs/qwen-tasks/REWORK/`. Source:
`ls docs/qwen-tasks/REWORK/`. Count: **4** (TASK-228, TASK-324, TASK-341,
TASK-351). Additionally, **6 tasks in DONE/** have `STATUS: REVIEW` or
`STATUS: REWORK` in their RESULT block, meaning they were reworked and then
moved to DONE. Total rework indicators: **10**.

**"Defects introduced"** — `UNKNOWN`. No machine source defines or tracks
defects introduced by a worker. A defect would require a post-merge failure
attributed to a specific task's changes, and no such attribution exists in the
task files, the registry, or the git history.

**"Defects found"** — `UNKNOWN` as a per-worker count. The closest machine
source is `docs/glm-reviews/` (14 files), which records GLM's independent
verification findings. Four of those files name a verdict (FAIL on
branch-TASK-323, branch-TASK-324; adversarial reviews on copylint.md,
sequencegate.md). But "defects found" requires a definition of what counts as
a defect versus a design observation, and no such definition is machine-readable
in the review files. The GLM review files are listed in Part 1 Appendix A.

**"Hours to fix"** — `UNKNOWN`. No machine source records time spent per task
or per rework. Task files do not timestamp their start, and the git history's
author is uniformly "Zvonimir Beslic" or "c" (see below), so commit dates
cannot be attributed to individual workers.

**"Tokens"** — `UNKNOWN` per worker. The only token data available is from
4 GLM branch-verification files in `docs/glm-reviews/`, which report
`total_tokens` in their Usage dicts. Sum: **31,227 tokens** across 4 reviews
(branch-TASK-323: 8,061; branch-TASK-324: 5,976; branch-TASK-364: 6,854;
branch-TASK-400: 10,336). No other worker's token usage is recorded in any
machine-readable file accessible from this worktree.

**"Cost"** — `UNKNOWN` per worker. No per-worker cost ledger exists. The spend
ledger (`work/spend-ledger.jsonl`) is gitignored and lives only in Claude's
worktree; it is not accessible here. Provider subscription costs are known to
the operator but are not recorded in any file in this repository.

### Why worker attribution is UNKNOWN for every column

Three independent checks confirm that no machine source distinguishes which
worker did which task:

1. **Git authorship.** All 1,814 commits since repo creation (2026-09-09) are
   authored by "Zvonimir Beslic" or "c". The "c" commits are merge commits
   from Claude subagents. Source: `git log --format="%an"`. There is no
   secondary author field, no co-author trailer, and no worker-identifying
   commit convention.

2. **Task registry.** `docs/state/TASK-REGISTRY.json` has a `worker` field,
   but it is `null` for all 255 DONE tasks. The field is populated from
   `work/claims/`, which is ephemeral and gitignored. Source: Python parse of
   TASK-REGISTRY.json.

3. **Task files.** No RESULT block in any of the 268 DONE files contains a
   `WORKER:` field. Worker names appear in prose (e.g., "Qwen delivered this",
   "Claude merged this") but these are not machine-parseable attributions —
   they are narrative context. A regex for worker names finds mentions in 257
   files for "Claude", 118 for "Qwen", 17 for "GLM", 14 for "Grok", 4 for
   "Groq", and 2 for "Sonnet", but these counts reflect discussion, not
   attribution.

4. **Branch names.** 304 remote branches match `qwen-worker*`, 3 match
   `review/glm*`. No branches match `grok*`, `groq*`, `sonnet*`, or `claude*`.
   But branch names identify the worktree, not the model — a Qwen worktree
   may be driven by any model the operator dispatches to it.

### The table

| Worker   | Tasks delivered | Accepted first pass | Reworks | Defects introduced | Defects found | Hours to fix | Tokens  | Cost    |
|----------|----------------|--------------------|---------|-------------------|--------------|-------------|---------|---------|
| Claude   | UNKNOWN        | UNKNOWN            | UNKNOWN | UNKNOWN           | UNKNOWN      | UNKNOWN     | UNKNOWN | UNKNOWN |
| Qwen     | UNKNOWN        | UNKNOWN            | UNKNOWN | UNKNOWN           | UNKNOWN      | UNKNOWN     | UNKNOWN | UNKNOWN |
| GLM      | UNKNOWN        | UNKNOWN            | UNKNOWN | UNKNOWN           | UNKNOWN      | UNKNOWN     | 31,227  | UNKNOWN |
| Grok     | UNKNOWN        | UNKNOWN            | UNKNOWN | UNKNOWN           | UNKNOWN      | UNKNOWN     | UNKNOWN | UNKNOWN |
| Groq     | UNKNOWN        | UNKNOWN            | UNKNOWN | UNKNOWN           | UNKNOWN      | UNKNOWN     | UNKNOWN | UNKNOWN |
| Sonnet   | UNKNOWN        | UNKNOWN            | UNKNOWN | UNKNOWN           | UNKNOWN      | UNKNOWN     | UNKNOWN | UNKNOWN |

**Every cell is UNKNOWN except GLM tokens (31,227 from 4 branch-verification
files in `docs/glm-reviews/`).** The per-worker breakdown cannot be derived
from any machine source in this repository.

### What would have to exist to fill this table

1. **A `WORKER:` field in every RESULT block.** The task template would need to
   require it, and workers would need to fill it in. Currently no task file
   has one.
2. **A durable claim log.** `work/claims/` is ephemeral and gitignored. A
   committed claim log — one row per task, with worker, claim time, and
   release time — would make attribution possible.
3. **Per-worker token tracking.** Each model provider's usage dashboard is
   external to this repo. A script that reads provider usage APIs and writes
   to a committed file (with the same access controls as the spend ledger)
   would make token counts derivable.
4. **A defect register.** A file that records, for each post-merge failure,
   which task's changes caused it and which worker delivered that task. No
   such file exists.
5. **Time tracking per task.** Either a claim-time and complete-time in the
   task file, or a worker-identifying commit convention that allows deriving
   duration from git history.

### Aggregate numbers (worker-agnostic)

These are derivable from machine state and do not require worker attribution:

| Metric                          | Value | Source                                                    |
|---------------------------------|-------|-----------------------------------------------------------|
| Tasks in DONE/                  | 268   | `ls docs/qwen-tasks/DONE/*.md`                            |
| Tasks in REVIEW/                | 19    | `ls docs/qwen-tasks/REVIEW/*.md`                          |
| Tasks in REWORK/                | 4     | `ls docs/qwen-tasks/REWORK/*.md`                          |
| Tasks in BLOCKED/               | 3     | `ls docs/qwen-tasks/BLOCKED/*.md`                         |
| Tasks in TODO/                  | 177   | `ls docs/qwen-tasks/TODO/*.md`                            |
| Total task files                | 471   | sum of above                                              |
| RESULT blocks present (DONE)    | 236   | `grep -l "## RESULT" docs/qwen-tasks/DONE/*.md`           |
| RESULT blocks absent (DONE)     | 32    | difference                                                |
| STATUS: DONE in RESULT          | 89    | regex extract from DONE/*.md                              |
| STATUS: COMPLETE in RESULT      | 1     | regex extract from DONE/*.md                              |
| STATUS: PARTIAL in RESULT       | 3     | regex extract from DONE/*.md                              |
| STATUS: FAIL in RESULT          | 1     | regex extract from DONE/*.md                              |
| STATUS: REJECTED in RESULT      | 1     | regex extract from DONE/*.md                              |
| STATUS: REVIEW/REWORK in RESULT | 6     | regex extract from DONE/*.md                              |
| COMMIT SHA in RESULT            | 80    | regex extract from DONE/*.md                              |
| Total commits (repo lifetime)   | 1,814 | `git log --oneline`                                       |
| Merge-related commits           | 169   | `git log --grep="MERGE\|Merge"`                           |
| Integration commits             | 175   | `git log --grep="INTEGRATE"`                              |
| Remote branches (total)         | 372   | `git branch -r`                                           |
| Qwen worker branches            | 304   | `git branch -r \| grep qwen-worker`                       |
| GLM review branches             | 3     | `git branch -r \| grep review/glm`                        |
| GLM review files                | 14    | `ls docs/glm-reviews/*.md`                                |
| GLM token total (4 files)       | 31,227| sum of `total_tokens` in docs/glm-reviews/branch-*.md     |

### Appendix A — GLM review files

| File                                          | Type              | Verdict  | Tokens  |
|-----------------------------------------------|-------------------|----------|---------|
| branch-TASK-323.md                            | Branch verify     | FAIL     | 8,061   |
| branch-TASK-324.md                            | Branch verify     | FAIL     | 5,976   |
| branch-TASK-364.md                            | Branch verify     | (no token data in file) | 6,854 |
| branch-TASK-400.md                            | Branch verify     | (no token data in file) | 10,336 |
| TASK-317-secondbrain.md                       | Adversarial review| (findings listed) | — |
| TASK-354-cta-allowlist-verification.md        | Verification      | PASS     | —       |
| TASK-379-verify-TASK-369-entrypoint.md        | First-pass verify | (verdict in file) | — |
| TASK-382-glm-verify-task-367-offer-block.md   | First-pass verify | (verdict in file) | — |
| copylint.md                                   | Adversarial review| (findings listed) | — |
| sequencegate.md                               | Adversarial review| (findings listed) | — |
| verify-task-346-spend-gate-TASK-380.md        | Verification      | (verdict in file) | — |
| CHECKLIST-RECONCILIATION-2026-09-26.md        | Checklist review  | (findings listed) | — |
| TRIAGE-CANARY-b333697-2026-09-26.md           | Trige canary      | (verdict in file) | — |

Source: `ls docs/glm-reviews/` and file contents.

---

## PART 2 — THE PROVIDER SPLIT

### FIXED SUBSCRIPTIONS

| Provider       | Plan        | Utilisation                | Cost per accepted task |
|----------------|-------------|----------------------------|------------------------|
| Claude Max     | UNKNOWN     | UNKNOWN                    | UNKNOWN                |
| Qwen (Pro)     | UNKNOWN     | UNKNOWN                    | UNKNOWN                |
| GLM / Z.ai     | UNKNOWN     | UNKNOWN                    | UNKNOWN                |
| Apify Scale    | UNKNOWN     | UNKNOWN                    | UNKNOWN                |

**Source for plan names:** `src/config.py` VARIABLES tuple names the provider
keys: `LLM_API_KEY` / `OPENROUTER_API_KEY` (OpenRouter, used for Qwen and
other models), `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `APIFY_TOKEN`, and the
GLM reviews reference `glm-5.3` as the model. Plan details, billing cycles,
and allowance ceilings are not recorded in any file in this repository.

**Why every cell is UNKNOWN:**

- **Utilisation** requires knowing the plan allowance (tasks or tokens per
  month) and the consumed amount. Neither is recorded in any committed file.
  Provider dashboards are external and not read by any script in this repo.
- **Cost per accepted task** requires knowing the monthly subscription cost
  and the number of tasks that worker delivered. Neither the cost nor the
  per-worker task count is machine-derivable (see Part 1).

**What would have to exist:** A committed file recording each subscription's
monthly cost, allowance, and consumption — or a script that reads provider
billing APIs and writes such a file.

### PAY-PER-USE

| Provider      | Ledger spend | Source                          |
|---------------|-------------|---------------------------------|
| ContactOut    | UNKNOWN     | `work/spend-ledger.jsonl` (not accessible) |
| Deliverable   | UNKNOWN     | `work/spend-ledger.jsonl` (not accessible) |
| Reoon         | UNKNOWN     | `work/spend-ledger.jsonl` (not accessible) |
| Blitz         | UNKNOWN     | `work/spend-ledger.jsonl` (not accessible) |
| AI-ARK        | UNKNOWN     | `work/spend-ledger.jsonl` (not accessible) |
| Anthropic API | UNKNOWN     | `work/spend-ledger.jsonl` (not accessible) |
| OpenRouter    | UNKNOWN     | `work/spend-ledger.jsonl` (not accessible) |
| CheapVerifier | UNKNOWN     | `work/spend-ledger.jsonl` (not accessible) |
| Groq          | UNKNOWN     | `work/spend-ledger.jsonl` (not accessible) |

**Source for provider names:** `src/config.py` VARIABLES tuple, lines 108-170:
`CONTACTOUT_TOKEN`, `BLITZ_API_KEY`, `AIARK_KEY`, `REOON_KEY`,
`DELIVERABLE_KEY`, `BISON_KEY`, `HEYREACH_KEY`, `APIFY_TOKEN`, `LLM_API_KEY`,
`OPENROUTER_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`. All classified as
`LIVE` in the `providers` group.

**Why every cell is UNKNOWN:** The spend ledger (`work/spend-ledger.jsonl`) is
written by `src/spendledger.py` through `src/enrich.py`'s `spend()` closure.
It is the canonical record of provider spend. But it lives in `work/`, which
is gitignored and exists only in Claude's worktree (`resonate-group-automation`).
This worktree (`resonate-qwen-7`) has no `work/spend-ledger.jsonl`. The ledger
cannot be read from here.

**TASK-359 is deferred** until the ledger is proven, per the task brief. So
even if the ledger were accessible, its numbers would carry a known caveat.

**What would have to exist:** Either (a) the spend ledger committed to the
repository (with PII redaction), or (b) a script that reads the ledger from
Claude's worktree and writes a summary to a committed file, or (c) operator
access to read the ledger and report the numbers.

### Provider env var names (from `src/config.py` VARIABLES, never values)

The following provider environment variable NAMES are recorded in
`src/config.py` lines 51-180. Values are never read or printed:

    CONTACTOUT_TOKEN      BLITZ_API_KEY       AIARK_KEY
    REOON_KEY             DELIVERABLE_KEY     BISON_KEY
    HEYREACH_KEY          APIFY_TOKEN         LLM_API_KEY
    OPENROUTER_API_KEY    GROQ_API_KEY        ANTHROPIC_API_KEY
    LLM_BASE_URL          LLM_MODEL

---

## PART 3 — THE CROATIAN SUMMARY

**What the workforce delivered (2026-09-09 to 2026-09-27):**

268 zadataka je u DONE stanju, 19 čeka recenziju, 4 su vraćena na doradu, 3
su blokirana. Repo je napravljen 9. rujna — sve što ovaj izvještaj mjeri
dogodilo se u 19 dana. 1.814 commitova, 175 integracijskih, 169 merge-related.

**Što je koštalo:**

Ne možemo reći. Niti jedan broj o trošku po workeru ne postoji u strojno
čitljivom obliku. Spend ledger (`work/spend-ledger.jsonl`) je jedini
autoritet za potrošnju po provideru, ali je gitignored i postoji samo u
Claudeovom worktreeu. Pretplatnički troškovi (Claude Max, Qwen Pro, GLM,
Apify) nisu zapisani ni u jednoj datoteci u repozitoriju.

**Jedina brojka o tokenima:**

GLM je u 4 branch-verifikacije potrošio 31.227 tokena. To je jedini
izmjerivi token podatak u cijelom repozitoriju.

**Naslov koji nije očigledan:**

Ovaj projekt ne može izmjeriti vlastitu radnu snagu. Ne zna tko je što
napravio, koliko je to koštalo po workeru, niti koliko je tokena ukupno
potrošeno. Sve što ima su aggregate brojevi (268 zadataka, 1.814 commitova)
i jedan GLM token zbroj. Da bi se idući izvještaj mogao popuniti, trebaju
postojati: `WORKER:` polje u svakom RESULT bloku, trajni claim log, i
čitljiv spend ledger.

---

## SOURCE INDEX

Every numbered fact in this report traces to one of these sources:

| Source ID | Source                                                      | What it provides                                    |
|-----------|-------------------------------------------------------------|-----------------------------------------------------|
| S1        | `docs/qwen-tasks/DONE/*.md` (268 files)                     | Task delivery count, RESULT block statuses          |
| S2        | `docs/qwen-tasks/REVIEW/*.md` (19 files)                    | Awaiting-review count                               |
| S3        | `docs/qwen-tasks/REWORK/*.md` (4 files)                     | Active rework count                                 |
| S4        | `docs/qwen-tasks/BLOCKED/*.md` (3 files)                    | Blocked count                                       |
| S5        | `docs/qwen-tasks/TODO/*.md` (177 files)                     | Queued count                                        |
| S6        | `git log --oneline` (1,814 commits)                         | Commit volume, date range                           |
| S7        | `git branch -r` (372 branches)                              | Branch counts by worker prefix                      |
| S8        | `docs/glm-reviews/*.md` (14 files)                          | GLM review count, token usage, verdicts             |
| S9        | `docs/state/TASK-REGISTRY.json`                              | Task registry (worker field null for all)           |
| S10       | `docs/state/LEDGER.json` (generated 2026-09-20)             | Stale task ledger, superseded by filesystem state   |
| S11       | `src/config.py` VARIABLES tuple (lines 51-180)              | Provider env var names, classifications             |
| S12       | `src/spendledger.py` (path function, line 248)              | Spend ledger location (`work/spend-ledger.jsonl`)   |
| S13       | `src/enrich.py` (spend closure, line 865)                   | How spend is recorded                               |
| S14       | `scripts/durable_state.py` (run 2026-09-28)                 | Live stage counts: DONE=268, REVIEW=19, REWORK=4    |
| S15       | `docs/PRODUCTION-HANDOFF-2026-09-26-EVENING.md`             | Worker task table (narrative, not machine-readable) |

---

## VERIFICATION CHECK

Three numbers re-derived from named sources:

1. **Tasks in DONE = 268.** Re-derived: `ls docs/qwen-tasks/DONE/*.md | wc -l`
   → 268. Matches S1 and S14.
2. **GLM token total = 31,227.** Re-derived: sum of `total_tokens` from
   branch-TASK-323 (8,061) + branch-TASK-324 (5,976) + branch-TASK-364 (6,854)
   + branch-TASK-400 (10,336) = 31,227. Matches S8.
3. **Remote branches = 372.** Re-derived: `git branch -r | wc -l` → 372.
   Matches S7.

All three reproduce from their named sources.

---

## ACCEPTANCE STATUS

1. ✅ `docs/WORKFORCE-REPORT-2026-09-27.md` exists and is this file.
2. ✅ Every unsourceable cell reads `UNKNOWN`, and the report lists what would
   have to exist to fill each one (see "What would have to exist" sections).
3. ✅ The two provider tables are separate: fixed subscriptions (utilisation
   and cost-per-accepted-task) and pay-per-use (ledger spend).
4. ✅ Three numbers re-derived and recorded above in VERIFICATION CHECK.
5. ⬜ Croatian summary is written in Part 3 but NOT posted to `#resonate-os`
   (no Slack access from this worktree; operator must post manually).
6. ✅ Provider writes = 0. No provider was called. No new provider integration
   was written.
