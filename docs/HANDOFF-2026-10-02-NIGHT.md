# Handoff — 2026-10-02, night. For a session with none of this conversation.

Everything below is measured. Where a number came from a reader that turned out
to be blind, it says so. **Read §9 before you measure anything yourself.**

This handoff supersedes the one written at 21:05 into a session scratchpad under
`%TEMP%`, which is exactly the defect the operator fixed tonight: see §2.

---

## 1. SHAs and the machine

| | |
|---|---|
| master | **`f10cff7f`** (one docs commit past `b5ebe2a2`) |
| origin/master | `10a38310` |
| ahead by | **27 commits, NOTHING PUSHED ALL DAY** |
| lock | `work/suite.lock` in the MAIN checkout — check it, never trust this line |

Push is the operator's decision and has not been given. `git push` is refused by
the Claude Code classifier in Bash and works in PowerShell — if it is refused,
READ WHO REFUSED IT before reporting a remote problem.

## 2. THE DURABLE PATHS — new tonight, operator's order

**`C:\Users\Zvonimir\Desktop\resonate-ops`.** Everything a merge gate needs now
lives there instead of a session scratchpad: the frozen reference checkout
(moved with `git worktree move`, so git's metadata followed), both 231-name
reference logs as artefacts under `logs/`, `tools/` (`refdiff.py`,
`canarypath.py`, `copyreview.py`), `canary/` (the eleven-candidate shortlist,
the provider readback, the suppression config), `briefs/`, `glm-verdicts/`, and
a `README.md` that carries the rules for each. Read that README first.

**The move broke `refdiff.py` silently and that is the lesson in it**: the tool
derived the location of `run_suite.py` from the REFERENCE LOG's directory, which
held only while the log lived inside a checkout. It now tries
`REFDIFF_SCRIPTS`, then its own repository, then the main checkout through
`git rev-parse --path-format=absolute --git-common-dir`, then the log's own
directory, PRINTS which one it used, and refuses loudly instead of dying on
`FileNotFoundError`. Proven by positive control: from the new home with the
moved log it reproduces the pre-move verdict exactly (231 vs 231, 0 new, 0 gone).

Stable tools also go into the repository under `scripts/ops/` — **not yet done**,
deliberately: it would move master while a gate run was in flight. Do it after
the next merge lands, then re-measure the `.md` delta (§4).

## 3. The queue, as it stands tonight

| branch | head | suite vs reference | GLM | what is missing |
|---|---|---|---|---|
| `task-940-glm-verifier` | `685512cf` | **run in flight on `b3ac5c34`** | **PASS on `b3ac5c34`**; NEEDS_CLAUDE on `685512cf` | see §5 — the merge candidate is `b3ac5c34`, not the branch head |
| `task-one-os-authority` | `1728895f` | **CLEAN: 231 names, 0 new, 0 gone**, 2270.2s, one `Ran` line | **cannot run** — the branch carries no task file | §6 |
| `task-word-contract-enforced` | `109e7334` | needs a run on the current master | not yet | merge master in first |
| `task-942-token-budget` | `7a51823e` | needs a new run — code changed | FAIL on the old code | merge master in, run, GLM |
| `task-defect-map` | this branch | docs only | n/a | merge as a docs commit |
| `task-guard-regressions-rebased` | `b83f11fc` | not run | not yet | REQUIRED for the canary |
| `task-936-487-on-the-gate` | `7b732696` | not run | not yet | on the path by file, not required |
| `task-937-prior-contact-copylint` | `f71221da` | not run | not yet | conditionally required; treat as REQUIRED until asked |

Operator's merge order, unchanged: **940 → OS authority → lint contract 943 →
942 (rework)**, then guard + 936, then the five older-base branches, then phase
0, then phase 1. Phase 2 does not start.

## 4. The reference, and the one measurement to repeat

Master's reference is `resonate-ops\logs\reference-231-master-f2690f57.log`,
**231 failing names**, measured on the tree of `f2690f57`.

Master is now four commits past that: three touch `CLAUDE.md`, one adds
`docs/glm-reviews/branch-TASK-425.md`. The operator's bounded shortcut covers
that delta ONLY with a measurement, and the measurement was made tonight: `.md`
is in `test_fixture_hygiene`'s `TEXT_SUFFIXES`, that module is the only reader
of those bytes, and run alone on master it gives the **same five** failing names
the reference carries — with `test_e2e`'s eleven names as the control that the
extractor can see anything at all.

**Repeat that whenever master moves.** If the delta touches anything under
`src/` or `tests/`, the shortcut does not apply at all and master gets its own
full run — operator, 2026-10-02.

## 5. TASK-940: four GLM calls, and what each one proved

The branch fixes the verifier. Tonight it was verified four times and every call
found something real.

1. `65c88b10` — NEEDS_CLAUDE, **vacuous**: the patch slot read "(could not
   generate a diff)". `_git` captured with `text=True` and no `encoding`, so
   Python decoded git's bytes with the LOCALE codec (cp1250), the patch carried
   byte `0x90`, the reader thread died and `stdout` came back `None`.
   `--name-only` and `--stat` are ASCII and survived, so the verdict LOOKED
   considered. Fixed at `3d3d1719`: one decode policy (`CAPTURE`), three users.
2. `8a3ccb4c` first call — `GlmTimeout` after 180s. `--timeout 600` is INERT:
   `glm.complete` clamps with `min(int(timeout or GLM_TIMEOUT), GLM_TIMEOUT)`.
   The identical call on retry answered, so 180s is marginal at that size, not a
   law. The report name is keyed by SHA, so the retry OVERWROTE the timeout's
   report — the only record of it is a commit message.
3. `8a3ccb4c` retry — the first verdict ever formed from the CODE.
   NEEDS_CLAUDE on three findings: acceptance command 4 could not fail (the
   spend ledger resolves per worktree, so a fresh acceptance tree has none);
   the baseline JSON appeared to be missing (**REFUTED** — it is on master at
   `201ed39d`); and 30,596 of 79,833 patch characters unseen.
4. `685512cf` — NEEDS_CLAUDE again, on things that are NOT this branch's fault:
   it cannot see `src/providers/glm.py` to confirm `glm.complete` accepts
   `ledger_client` (**REFUTED by measurement**: the signature has it, and two
   rows under client `TASK-940` sit in the production ledger), and the
   acceptance file it checks is one the branch itself edits — **a fair point
   with no fix tonight: in this repository a task file travels with the work.**

Between 3 and 4 the branch gained the ledger escape (`905a61c2`), whole-file
patch fitting (`b3ac5c34`), and a provable banner bound (`685512cf`) after GLM
found that `BANNER_RESERVE = 400` did not bound a banner that NAMES files.

**THE MERGE CANDIDATE IS `b3ac5c34`** — the head that carries a GLM PASS, per
the operator's instruction tonight. `685512cf` stays on the branch for the next
round, together with TASK-959.

## 6. OS authority cannot be gated, and the reason is the tool

Its suite half is **clean** (231 names, 0 new, 0 gone). Its GLM half cannot run
at all: `glm_verify_branch.py` resolves the acceptance commands from a task
file, and this branch has none — its work answers to an operator decision
written up in `docs/ATTRIBUTION-AND-COLLISION-ARE-TWO-QUESTIONS-2026-10-02.md`,
not to a `TASK-xxx` file. An unreadable authority is UNKNOWN, and UNKNOWN does
not pass.

So it needs one of: a task file written by somebody who did not write the branch
(so the acceptance is not chosen because it passes), or the operator's word to
merge on suite + Claude review. **Not decided.**

## 7. TASK-959: the multi-part review, DECIDED by the operator tonight

Not a proposal any more. Written up in full in
`docs/qwen-tasks/TODO/TASK-959-...md`: split the patch by WHOLE FILES into parts
that fit the budget, code before prose; every call gets its part plus the
branch's full file list plus one sentence on what the other parts hold; the
branch is PASS only if EVERY part is PASS and any FAIL or NEEDS_CLAUDE is the
branch's verdict; the `glm-reviews` record carries the part count and the
verdict per part; spend is attributed per call to the task.

It closes exactly what blocked call 4. **Not implemented yet.** The part size
waits on the measurement TASK-959 opens with: which prompt size a 180s attempt
actually answers.

## 8. Also opened tonight

- **TASK-960 — the spend ledger is per worktree for EVERY caller.** GLM named
  two stranded rows; a sweep found **37 glm rows, 482,732 micro-USD, across six
  worktree ledgers** against 41 in the production one. Five of them are the
  TASK-903/940/942/946 verdicts this queue is gated on. All six were COPIED to
  `work\stranded-spend-2026-10-02\` in the main checkout (gitignored production
  storage, not temp) with an INDEX whose totals were read back from the copies.
  **The migration into the canonical ledger is NOT done and needs the operator**:
  appending to the money record gets a dry run, a marker naming each row's
  source so a second run cannot double-count, and a readback.
- **TASK-961 — two more verifier defects GLM found**: `_merge_commit_for` takes
  the OLDEST ancestry-path merge, so a branch merged through an integration
  branch is reviewed as that branch's range; and `_find_task_file` leaks its
  `mkstemp` copy (10 such files already in `%TEMP%`).
- **A40–A43 in `docs/DEFECT-MAP-2026-10-02.md`** on this branch carry all of it.

## 9. Where a reader was wrong tonight — read before trusting one

- **A test of mine SKIPPED and I replaced it.** It measured the banner's fixed
  prose and called `skipTest` when its fixture happened to fit whole.
- **A fixture that could not exercise the thing it tested.** It fed a
  5,000-character patch to a budget of ~57,000 and asserted a banner that
  correctly never appeared.
- **A validator that agreed with me.** An acceptance command searched source
  text for a needle containing a space, over a haystack whose spaces had been
  stripped — it could never match, and it PASSED on today's broken code.
- **An acceptance command that never entered the path it tested.** It called
  `_find_task_file('TASK-940')` without a branch, so it took the glob fallback,
  created no temporary file, and asserted that none had leaked.
- **A wrong claim in a task file's Mutation section**, caught by GLM: command 4
  does not kill the `ledger_path`→ROOT mutation; only the unit test does.
- **Two untracked `.md` verdicts sitting in a gate worktree.** They were moved
  out before the run: `test_fixture_hygiene` scans `git ls-files --others` as
  well as tracked files, so an untracked file in the tree under measurement
  changes what that test sees.
- **A stale `suite_verdict.txt` from 17:56 in the tree about to be measured.**
  Every verdict read tonight was checked by mtime against the run's start first.

## 10. Do NOT re-investigate

- Whether GLM works. It does, and it is now sharp enough to find real defects in
  the code that fixes it — four times in one evening.
- Whether the suite can run in the MAIN checkout. It cannot:
  `clientapproval.counts()` is quadratic. Every baseline is measured in a
  worktree.
- Whether `test_slack_route…test_a_get_is_refused` is a regression.
  **ATTRIBUTION IS CLOSED: it is not.** One re-run clears it. It did not appear
  in either of tonight's finished runs.
- Whether the baseline JSON is on master. It is, at `201ed39d`.
- Whether `glm.complete` accepts `ledger_client`. It does — signature and two
  billed rows under `TASK-940`.
- The clock phantom, the `task-937` rebase route, `_PUNCTUATION_MAP`, the five
  DNC writes: all settled earlier, see the previous handoff's §12 and the defect
  map.

## 11. Standing rules, unchanged tonight

One full suite at a time, machine-wide, enforced in code. One run per merge only
when `git diff <master> <branch>` is PROVEN empty, proven every time. The
shortcut applies ONLY to files no module under `src/` imports; `src/` or
`tests/` always gets a new reference. Every merge goes through GLM first and
NEEDS_CLAUDE, UNKNOWN or FAIL does not pass. No merge with a NEW NAME. No
provider write, no Slack post — **zero of each tonight**. Qwen does not run.
Nobody enters the reference. Kill a suite by PID after reading that process's
cwd. Phase 2 does not start.
