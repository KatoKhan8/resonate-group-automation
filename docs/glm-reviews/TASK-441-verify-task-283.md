# TASK-441 — GLM Independent Verification of TASK-283

**Reviewed task:** TASK-283 — S7 renders three bodies and the cadence now wants four
**Reviewed branch:** qwen-worker-7-r9
**Reviewed SHA:** 8db9271503ac965bcaa48ee4cca55356c0582d9d
**Branch HEAD has moved:** Yes — origin/qwen-worker-7-r9 now points to e6550f9216a241bdbd894225d2c8c40fad1d11c5. This verdict reviews the exact SHA named in the task file, per protocol.
**START_MASTER_SHA:** f6979300 (MERGE TASK-400)
**Review date:** 2026-09-28
**Review worktree:** .qwen/worktrees/verify-283 (detached at 8db92715)

---

## Summary

**DISPOSITION: REWORK**

The three artifacts exist, the 32 tests pass, and the verifier logic is sound. However:

1. **DISCONNECTED — zero production callers.** No pipeline script, shell script, CI step, or runbook entry invokes `verify_s7_render.py`. The result block says "Where this runs in tomorrow's sequence: After S7 re-renders, before batch1_build and push" but this is aspirational. `grep -rn "verify_s7_render" src/ scripts/` returns only the script's own docstring. Per standing rule: zero production callers means DISCONNECTED, which is a rework and not a merge.

2. **Real data never verified.** The per-variable table over 927 rows was never produced. The result block acknowledges: "The real s7-copy.jsonl is not in this worktree." The verifier was tested end-to-end against synthetic journals only.

3. **Massive scope drift.** The branch carries 121 files changed, 13,485 insertions, 541 deletions across dozens of tasks. TASK-283's three files would need cherry-picking; merging the branch would bring unrelated changes to src/, config/, scripts/, and 17 other test files.

---

## Finding 1: Artifacts exist and match claims

**VERIFIED.**

| Artifact | Claimed lines | Actual lines | Exists at SHA |
|----------|--------------|--------------|---------------|
| scripts/verify_s7_render.py | 388 | 387 | ✓ |
| tests/test_the_four_step_render_has_every_variable.py | 331 | 330 | ✓ |
| docs/S7-FOUR-STEP-RENDER-VERIFICATION-2026-09-25.md | 144 | 144 | ✓ |

Line counts differ by 1 on two files (trailing newline). All three were added by commit 4ca27d14 ("TASK-283: verifier and 52 tests, all green") and are present at the reviewed SHA.

**Evidence:**
```
git ls-tree -r --name-only 8db92715 | grep TASK-283
→ docs/qwen-tasks/REVIEW/TASK-283-s7-renders-three-bodies-and-the-cadence-wants-four.md

wc -l scripts/verify_s7_render.py tests/test_the_four_step_render_has_every_variable.py docs/S7-FOUR-STEP-RENDER-VERIFICATION-2026-09-25.md
→ 387 + 330 + 144 = 861 total
```

---

## Finding 2: Tests pass and are falsifiable

**VERIFIED.**

All 32 tests pass:
```
python -m unittest tests.test_the_four_step_render_has_every_variable -v
→ Ran 32 tests in 0.060s — OK
```

The tests are genuinely falsifiable:
- They test real logic (set operations, string matching, config parsing), not `hasattr` or source-text grep.
- The `VerifierExitCode` class calls `main()` with synthetic journals AND the real `--client productive` config, exercising the full pipeline including `bisonfactory._sequence_steps()`.
- The `SetDiffBothDirections.test_same_count_different_keys` test specifically guards against the false-pass case where equal counts mask different sets.

**Mutation tests performed:**
1. `diff_sets({'em1','em2','em3','em4'}, {'em1','em2','em4','em5'})` → correctly returns `(['em3'], ['em5'])`. A broken implementation returning `([], [])` would fail `test_cadence_has_extra`.
2. `check_row_variables` correctly distinguishes `""` → `"empty"`, `"None"` → `"literal-'None'"`, `"{FIRST_NAME}"` → `"unrendered-placeholder"`. All three labels are asserted in tests.

**What the tests do NOT cover:**
- The real `s7-copy.jsonl` with 927 rows. The verifier was never run against production data.
- Whether any pipeline orchestrator actually calls this verifier (see Finding 3).

---

## Finding 3: DISCONNECTED — zero production callers

**NOT VERIFIED — DISCONNECTED.**

```
grep -rn "verify_s7_render" src/ scripts/ --include="*.py"
→ scripts/verify_s7_render.py:4:    py -3 scripts/verify_s7_render.py --copy work/stage/s7-copy.jsonl
→ scripts/verify_s7_render.py:5:    py -3 scripts/verify_s7_render.py --copy path/to/copy.jsonl --client productive
```

Only the script's own docstring references it. No other Python module, shell script, or CI configuration imports or invokes it.

The result block claims:
> "Where this runs in tomorrow's sequence: After S7 re-renders (stage_s7_copy.py), before batch1_build and push. Step 3 in the sequence: cadence lands -> S7 renders -> THIS VERIFIER -> build -> push."

This is aspirational. There is no wiring. The verifier is a standalone script that must be run manually. The same is true of the pre-existing `scripts/verify_s7_cadence_render.py` (442 lines, added 2026-09-25) — neither verifier is called by the pipeline.

**Per standing rule:** "Existence is not function... Zero production callers means DISCONNECTED, which is a rework and not a merge."

**What would fix this:**
- Add a line to `scripts/pool.sh` or a runbook document that invokes the verifier after `stage_s7_copy.py` and before `batch1_build.py`.
- Or: document in `OPERATING-MODE.md` that this is a manual verification step with a specific trigger condition.
- At minimum: the docs file should name who runs it, when, and what "PASS" enables.

---

## Finding 4: Real data not verified

**NOT VERIFIED.**

The result block acknowledges:
> "The real s7-copy.jsonl is not in this worktree. The per-variable table over 927 rows is OWED from Claude's worktree."

The verifier was tested against synthetic journals only. The acceptance bar in TASK-283 required:
> "The verifier is run against the real s7-copy.jsonl for all 927 rows and reports a number per variable. 'All good' with no denominator is not a result."

This was not done. The per-variable table with denominators over 927 rows does not exist.

**What would fix this:**
- Run `py -3 scripts/verify_s7_render.py --copy work/stage/s7-copy.jsonl` from Claude's worktree.
- Append the output to the docs file or the result block.

---

## Finding 5: Branch would not delete production code

**VERIFIED — no production deletions.**

```
git diff master...8db92715 --diff-filter=D --name-only
→ docs/qwen-tasks/TODO/TASK-310-every-approved-file-feeds-the-training-set.md
→ docs/qwen-tasks/TODO/TASK-364-one-canonical-sequence-plan.md
→ docs/qwen-tasks/TODO/TASK-388-reconciliation-check-in-the-watcher-cycle.md
```

All three "deleted" files are task state transitions (TODO → REVIEW or TODO → DONE), verified by:
```
git ls-tree -r --name-only 8db92715 | grep "TASK-310\|TASK-364\|TASK-388"
→ docs/qwen-tasks/DONE/TASK-364-one-canonical-sequence-plan.md
→ docs/qwen-tasks/REVIEW/TASK-310-every-approved-file-feeds-the-training-set.md
→ docs/qwen-tasks/REVIEW/TASK-388-reconciliation-check-in-the-watcher-cycle.md
```

No src/, config/, or scripts/ files are deleted. The 541 deletions in the diff stat are line-level changes within modified files, not file deletions.

---

## Finding 6: Scope drift — massive

**VERIFIED — significant scope drift.**

```
git diff master...8db92715 --stat
→ 121 files changed, 13485 insertions(+), 541 deletions(-)

git log master...8db92715 --oneline | wc -l
→ 100+ commits
```

TASK-283's three files are a tiny fraction of this branch. The branch carries work from dozens of tasks including:
- 14 src/ files (bisonfactory, clientexport, enrollmenttags, generate_campaign, heyreachfactory, modelprices, nightlysourcing, notify, offers, providers/*, push, reviewapproval, sequenceplan, spendledger, store, training)
- 2 config/ files (productive-offers.yaml, model-prices.yaml)
- 8 scripts/ files (bison_watch_loop, claim_task, pool.sh, pool_watchdog, qualify_sourced_supply, refill_queue, sender_inventory_drift, stage_work_to_host)
- 17 test files beyond the TASK-283 one
- Many docs/ files (handoffs, triage reports, GLM reviews, status reports)

**Cherry-pick path:** To merge only TASK-283's work:
```
git cherry-pick 4ca27d1474028789f043cb61e0ba792dc96f168f -- scripts/verify_s7_render.py tests/test_the_four_step_render_has_every_variable.py docs/S7-FOUR-STEP-RENDER-VERIFICATION-2026-09-25.md
```
Or manually extract the three files from the SHA.

---

## Finding 7: Redundancy with existing verifier

**OBSERVATION.**

An existing `scripts/verify_s7_cadence_render.py` (442 lines) was added on 2026-09-25 by lane B. It performs comprehensive four-stage verification including lint, company name checks, and the full bisonfactory payload build.

The new `verify_s7_render.py` (387 lines) is narrower: it focuses on the set diff, per-variable table, thread_reply_pattern length, and final wait. The result block acknowledges this:
> "The existing scripts/verify_s7_cadence_render.py is the comprehensive four-stage verifier. This new script is narrower and focused on the specific questions TASK-283 names."

The two are complementary but neither is wired into the pipeline. Both are standalone scripts requiring manual invocation.

---

## Finding 8: Verifier runs correctly against real config

**VERIFIED.**

Running the verifier's logic against the real `config/clients/productive.yaml`:
```
Cadence email steps: 5
Keys: ['em1', 'em2', 'em3', 'em4', 'em5']
Sequence keys: ['em1', 'em2', 'em3', 'em4', 'em5']
Built sequence: 5 steps
  em1: thread_reply=False, wait=3
  em2: thread_reply=True, wait=4
  em3: thread_reply=True, wait=4
  em4: thread_reply=True, wait=9
  em5: thread_reply=True, wait=1
```

The config is currently correct: 5 email steps matching the cadence, thread_reply_pattern has 5 entries, final wait_in_days is 1 (non-zero). The verifier would PASS against this config if given a clean journal.

---

## Reproducible commands

All verification was performed in an isolated worktree:
```
git worktree add .qwen/worktrees/verify-283 8db9271503ac965bcaa48ee4cca55356c0582d9d --detach
cd .qwen/worktrees/verify-283

# Run the tests
python -m unittest tests.test_the_four_step_render_has_every_variable -v

# Check for production callers
grep -rn "verify_s7_render" src/ scripts/ --include="*.py"

# Run verifier logic against real config
python -c "
from scripts.verify_s7_render import cadence_steps, email_steps
from src import bisonfactory, clients
config = clients.load('productive')
email_seq = (config or {}).get('email_sequence') or {}
steps = cadence_steps()
email_steps_list = [s for s in steps if s.get('channel') == 'email' and s.get('key')]
sequence = bisonfactory._sequence_steps(email_seq, steps)
print(f'Steps: {len(sequence)}, thread_reply_pattern: {[s.get(\"thread_reply\") for s in sequence]}')
print(f'Final wait_in_days: {sequence[-1].get(\"wait_in_days\")}')
"

# Check deletions
git diff master...8db92715 --diff-filter=D --name-only

# Check scope drift
git diff master...8db92715 --stat | tail -1
```

---

## Disposition summary

| Finding | Status | Severity |
|---------|--------|----------|
| Artifacts exist | VERIFIED | — |
| Tests pass and are falsifiable | VERIFIED | — |
| Production callers | DISCONNECTED | P0 — rework required |
| Real data verified | NOT VERIFIED | P1 — owed |
| No production deletions | VERIFIED | — |
| Scope drift | SIGNIFICANT | P2 — cherry-pick required |
| Redundancy with existing verifier | OBSERVATION | P3 — document relationship |
| Verifier runs against real config | VERIFIED | — |

---

## Recommendation

**REWORK.**

The verifier is well-built and the tests are genuine, but:

1. **Wire it.** Add a caller — even if just a runbook entry in `OPERATING-MODE.md` or a line in `scripts/pool.sh` that invokes it after `stage_s7_copy.py`. A script with no caller is a file, not a gate.

2. **Run it against real data.** Produce the per-variable table over 927 rows from Claude's worktree. The acceptance bar explicitly required this.

3. **Cherry-pick only the three files.** The branch carries 121 files of unrelated work. Merging the branch would bring scope pollution.

4. **Document the relationship with `verify_s7_cadence_render.py`.** The docs file does this already; ensure both are referenced in the runbook.

A CLOSE with these three actions is a real result and is progress. The artifact is sound; the wiring is absent.

---

## What would make this a MERGE

1. A production caller (shell script, runbook entry, or CI step) that invokes `verify_s7_render.py` at the stated point in the pipeline.
2. The per-variable table over 927 real rows, appended to the docs file.
3. A cherry-pick commit that takes only the three TASK-283 files, not the 121-file branch.

---

## Boundary statement

This review was read-only. No provider calls, no production state changes, no file modifications outside the review document. The review was performed at the exact SHA named in the task file (8db9271503ac965bcaa48ee4cca55356c0582d9d), not at the branch name, per protocol.
