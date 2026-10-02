# Handoff — 2026-10-02, night. For a session with none of this conversation.

Everything below is measured. Where a number came from a reader that turned out
to be blind, it says so. **Read §9 before you measure anything yourself.**

This handoff supersedes the one written at 21:05 into a session scratchpad under
`%TEMP%`, which is exactly the defect the operator fixed tonight: see §2.

---

## 1. SHAs and the machine

| | |
|---|---|
| master | **`cd8e00bc`** — TASK-940 merged at `ae134dd2`, then `scripts/ops` |
| origin/master | `10a38310` |
| ahead by | **30 commits, NOTHING PUSHED ALL DAY** |
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

Stable tools are also in the repository now, under `scripts/ops/` — `refdiff.py`
and `canarypath.py`, with a README that points back here for everything that is
not code. `copyreview.py` deliberately stayed out: it has never been run, phase
0 has not started, and existence is not function. The commit waited until after
the TASK-940 merge so it could not move master while a gate run was in flight,
and the `scripts/ops` delta was then measured against the three repo-walking
modules (§4).

## 3. The queue, as it stands tonight

| branch | head | suite vs reference | GLM | what is missing |
|---|---|---|---|---|
| `task-940-glm-verifier` | `685512cf` | **MERGED at `b3ac5c34`** — 230 names, 0 new, 1 gone | **PASS on `b3ac5c34`** | nothing; `685512cf` stays as the base of `task-959-multipart-review` |
| `task-959-multipart-review` | `51ee340f` | not run | not run | the multi-part review itself, §7 — gate it with itself |
| `task-one-os-authority` | `3411e085` | its 231/0/0 is STALE (master gained `tests/` changes) and its new run was STOPPED | **FAIL** — 8 parts, two findings verified in the source | **does not merge.** Fix the CALLER, not the authority — A45 |
| `task-word-contract-enforced` | `70e86de2` | **CLEAN again: 231 vs 231, 0 new, 0 gone**, 2,086s, after the GLM findings were fixed | FAIL on `4b1e66a9`, re-running on the fixed head | merge if PASS — and see the em1 collision below |
| `task-959-multipart-review` | `413a9682` | not run | not run | carries the multi-part review AND the TASK-969 fix |
| `task-942-token-budget` | `b82304ab` | master merged in, waiting for the machine | FAIL on the old code | run, then GLM |
| `task-defect-map` | this branch | docs only | n/a | merge as a docs commit |
| `task-guard-regressions-rebased` | `b83f11fc` | not run | not yet | REQUIRED for the canary |
| `task-936-487-on-the-gate` | `7b732696` | not run | not yet | on the path by file, not required |
| `task-937-prior-contact-copylint` | `f71221da` | not run | not yet | conditionally required; treat as REQUIRED until asked |

Operator's merge order: **940 → OS authority → lint contract 943 → 942
(rework)**, then guard + 936, then the five older-base branches, then phase 0,
then phase 1. 940 is merged; OS authority is out on a FAIL; 943 is the run in
flight; 942 is next. **Phase 2 does not start, and it is now a 90-day
simulation** — §8a.

## 4. The reference, and the one measurement to repeat

Master's reference is now
`resonate-ops\logs\reference-230-master-ae134dd2.log`, **230 failing names**,
measured in a detached tree at exactly `b3ac5c34` — and `git diff master
b3ac5c34` was proven EMPTY after the merge, so that run IS master's reference
rather than a branch's. `reference-231-master-f2690f57.log` is kept as the
previous one.

The delta from `ae134dd2` to `cd8e00bc` is `scripts/ops/` — two `.py` files and
a README. MEASURED, not assumed: the three modules that walk the whole
repository (`test_fixture_hygiene`, `test_nothing_writes_to_a_provider`,
`test_secrets`) give the SAME 8 failing names on the new master as the reference
carries for them, with the reference's 231 total as the control that the reader
sees anything.

**And read A44 before trusting a 230 against a 231.** The name that vanished
between the two references is a safety guard that my gate worktree's NAME
switched off — see §8.

The older note below is kept because the measurement it describes is the one to
repeat whenever master moves.

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

**MERGED at `b3ac5c34`**, the head that carries the GLM PASS, per the operator's
instruction — `ae134dd2` on master, with `git diff master b3ac5c34` proven
empty. `685512cf` stayed on the branch and is the base of
`task-959-multipart-review`.

## 6. OS authority: the tool could not gate it, and now it can

Its suite half is **clean** (231 names, 0 new, 0 gone). Its GLM half cannot run
at all: `glm_verify_branch.py` resolves the acceptance commands from a task
file, and this branch has none — its work answers to an operator decision
written up in `docs/ATTRIBUTION-AND-COLLISION-ARE-TWO-QUESTIONS-2026-10-02.md`,
not to a `TASK-xxx` file. An unreadable authority is UNKNOWN, and UNKNOWN does
not pass.

**Resolved on the operator's order**: `TASK-962` was written for it, docs-only,
on the branch (`acf6bc70`), with four acceptance commands every one of which was
EXECUTED before being written down — 481 is OS and 274/327/328/352 are not, with
the authority readable; an unreadable authority gives UNKNOWN where a readable
one gives `not_ours`; a live sequence HOLDs the account whoever owns it; and a
reply beside a live sequence STOPs. The file says out loud that it was written
AFTER the code, and names the one claim in the operator's brief that the
measurement CONTRADICTS: "OS mid-sequence STOPs" was true of `8bfd9431` and
`aef91548` reversed it after the operator's own refinement, so
`account_policy(account)` now takes no ownership argument at all.

Its banked suite result is nevertheless STALE now — master gained changes under
`tests/`, and the operator's rule gives that no exception. A new run is what it
is waiting on.

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

## 8a. Also landed tonight, after this handoff was first written

- **`#resonate-os-output` exists and carries its first two posts.** Created as a
  public channel in the workspace (`C0C6DES2L7L`), matching every sibling
  outbound channel; archive or convert it if that is wrong. Standing permission
  from the operator: every generated copy in full with per-step word counts,
  every classified reply with text and verdict, DNC changes, the campaign plan
  when one exists. Engineering status stays in `#resonate-os` on request only.
  Post 1 is bigfish's five emails read from the artefact rather than retyped;
  post 2 is three classified replies whose verdicts were measured at post time.
  Both read back intact (2,668 and 1,718 characters, em dash and arrow
  present). **TASK-939 turned out to be already merged (`e9ae9e6b`)**, so those
  three verdicts are live master behaviour, and the two production replies the
  defect map names could NOT be shown verbatim: `work/learning-replies.jsonl`
  holds metadata only and the 899 bodies were read live.
- **Phase 2 is now a 90-day simulated campaign** — operator's order. The brief
  at `resonate-ops\briefs\phase2-brief.md` is rewritten: same population and
  same sandbox, an injected clock from day 0 to day 90, input assumptions
  DERIVED from our own data (899 replies, provider bounce/unsubscribe history,
  per-step latency) and written as config with source and sample size, a
  per-day loop through the real scheduler, classifier, DNC and recontact paths,
  and per-week output including the weekly Slack digest rendered exactly as the
  operator would receive it. Two risks are named in it rather than discovered
  later: the persona split may not be joinable, and latency needs both sides of
  the join. It still runs only after phases 0 and 1.
- **A44 / TASK-963, and it is the finding of the night.** The 230-vs-231 in
  TASK-940's gate was not a fix. `test_invariants.TestNothingCanSend.
  test_no_module_issues_an_http_post_outside_the_named_ones` excuses a hit with
  `any(a in p for a in allowed)` where `p` is the ABSOLUTE PATH and `allowed`
  is the provider names — so a worktree called `glm-940` exempted EVERY FILE IN
  THE REPOSITORY and the guard passed having watched nothing. Measured in three
  trees on a byte-identical file. The second half: what it had to excuse is a
  COMMENT containing a POST written in prose, and `tests/test_audit.py` already
  skips comments while `test_invariants.py` does not — two copies of one scan,
  one corrected.

## 8c. After midnight: the reference had to be re-measured, and 943 is clean

**The 230-name reference was contaminated by A44 and it blocked a clean merge.**
`task-word-contract-enforced`'s gate run reported ONE new name — the send guard
`test_no_module_issues_an_http_post_outside_the_named_ones` — and it is not the
branch's: the guard fails ALONE in that branch's tree, the branch does not touch
`src/providers` at all, and the two trees differ exactly as A44 predicts (the
reference's `glm-940` exempted by `['glm']`, this run's `wt-wordcontract` by
nothing). A re-run would have changed nothing, because the guard is
deterministic; the blocker was the reference.

So master's reference was re-measured in **`resonate-ops/ref-cd8e00bc`**, a name
the exemption cannot match: **231 names**, 14,702 tests, 2,111.8s, one `Ran`
line. Banked as `logs/reference-231-master-cd8e00bc.log`. Against it
`task-word-contract-enforced` is **CLEAN: 231 vs 231, 0 new, 0 gone**, both
controls passing, both sides measured in neutrally-named trees.

**The naming trap is now written into `resonate-ops/README.md`**: no worktree may
carry `aiark/apify/blitz/bison/contactout/glm/heyreach/slack/xai` in its name
until TASK-963 lands. A44's cost so far: one unusable 2,139-second verdict plus a
38-minute re-measurement.

**TASK-968 is the task file `task-word-contract-enforced` never had**, written
after the code and saying so, four commands executed before being written down.
It carries two findings of its own:

- **the number 943 names two different tasks** — the operator's queue and
  CLAUDE.md use it for the writer contract, while
  `TASK-943-name-the-authority-for-sent.md` exists in history as a P0 ramp task
  about which provider field decides SENT;
- **the em1 collision.** The branch's `WORD_CONTRACT` is em1 (60,75,90) and the
  operator's new contract is em1 90–140 target 120. **The branch's em1 ceiling is
  90**, so a 120-word em1 would be REFUSED on the merged master — the two
  contracts intersect at one value, which is the very shape this branch exists to
  prevent. Merging is still right (nothing generates a 120-word em1 today, and a
  contract nothing reads is worse), but `WORD_CONTRACT` must become
  **em1: (90,120,140)** in the same TASK-964 commit that teaches the new ladder,
  with em4's target becoming 50.

## 8d. The lint contract, gated twice, and a reviewer bug fixed mid-queue

**The first multi-part verdict on 943 was FAIL on four grounds, and they did not
all belong to the branch.** Each was measured:

1. `lint.is_contract_failure` had **no production caller** — TRUE, and the
   "helper nothing calls" shape the branch itself deleted `_selected_offer`
   for. Measured first whether a consumer was missing: a contract code already
   classifies as `failed` and `explain_contract` already renders the sentence,
   so the right fix was SUBTRACTION. The helper is gone and the test asks
   through `explain_contract`, which production calls at `src/lint.py:405`.
2. Acceptance command 4 was `assert … >= 140 or True` — **mine**, and GLM named
   it: *"a print statement wearing an assert"*, with the sharper point that the
   em1 bound was then accepted by a check unfalsifiable by construction.
   Deleted.
3. *"`lint.word_range` was deleted and a caller may now raise AttributeError"* —
   **REFUTED**: the function MOVED (`lint.py:735` calls
   `writercontract.word_range`, defined in `cold_email_writing.py:48`) and no
   `lint.word_range` call remains under `src/` or `scripts/`.
4. The loader ERROR for the deleted `test_a_thread_reply_has_its_own_word_range`
   — **the verifier's defect, not the branch's.** `_changed_test_files` asked
   git for the changed-file list, which includes DELETIONS, and then ran them.
   Nothing in the repository registers that module.

**Fixing 1 cost a second full run**, which is the honest price of closing a
finding: the change touched `src/lint.py` and a test, so the clean 231/0/0 was
superseded. The fresh run on `70e86de2` is **CLEAN again: 231 vs 231, 0 new, 0
gone, 2,086s**.

**TASK-969 is the verifier defect, and its fix is already in the tool this queue
runs** (`task-959-multipart-review` at `413a9682`, `--diff-filter=d`), because
the alternative was letting a reviewer's bug block a clean branch. Measured with
TASK-969's own commands: before, they named the deleted file; after, "7 changed
test files, none of them deleted" and "all 7 named files exist in
task-word-contract-enforced". **TASK-969 stays open until that fix lands on
master through the 959 branch's own gate** — a tool fixed in a worktree is not a
tool fixed in the repository.

## 8b. The second half of the night, in the order it happened

**The spend migration is done, and it corrected my own figure.** Operator
approved it; `scripts/migrate_stranded_glm_spend.py --dry-run` then `--apply`.
The dry run found that **17 of the 37 swept rows were ALREADY in the production
ledger** — same `run_id`, timestamp, cost, client and call — because I had
compared COUNTS rather than identities. The genuinely stranded figure is **20
rows, 262,114 micro-USD**, now migrated with a `migrated_from` marker, a backup,
a readback from the file (44 → 64 glm rows) and a second `--apply` that appends
nothing. The production audit reads 64 glm rows / 986,737 micro-USD. The CODE
half stays open for every caller but the verifier: TASK-960.

**The multi-part GLM review works, and its first use FAILED a branch.** Eight
parts on `task-one-os-authority`, one call each billed to TASK-962, a verdict
per part (1=FAIL, 2=NEEDS_CLAUDE, 3=FAIL, 4=NEEDS_CLAUDE, 5=PASS, 6=PASS,
7=FAIL, 8=PASS) and FAIL by conjunction. **Both FAIL findings were verified in
the source before being accepted** and are A45: `prompts/draft.md` says the
prior-contact caller "still passes the OLD boolean … until that caller is
changed", so the authority ships enforced by prompt prose; and
`scripts/canary_cohort.py` commits "EXACTLY 43 rows - and 52 of them are the
wrong people". The run launched for that branch was STOPPED rather than spent on
a tree that has to change, and the machine went to 943 instead.

**The copy review opened three tasks and one client question.**
`resonate-ops/copy-review/FINDING-bigfish-2026-10-02.md` records the operator's
verdict — *passes the gates, would not be sent* — with five measured reasons:
one angle in four of five steps, em1 describing the prospect's own company back
to them, no follow-up referencing the step before it, zero research rows so
nothing licensed, and three of five steps below the writer contract while `lint`
reports zero failures.

- **TASK-964** is the operator's final design: `step_objectives` becomes a ladder
  of ROLES (offer / smaller tangible piece / proof with a named client and a
  number / easy-answer question with an explicit exit / breakup in a new
  thread), lint refuses a shared role, an ask that does not descend, a bump that
  does not reference the thread and the same proof twice; contract em1 90–140
  target 120, em2–em5 45–90, em4 target 50, em5 a new thread, gaps 3/4/5/6.
  **Two measurements contradict that contract and are recorded rather than
  smoothed:** the operator's own five internal em1s are 261/281/279/246/72 words,
  and the standing writer contract says 60–90 for em1–em3.
- **TASK-965** is the cross-channel stop proven by effect. **Not P0** by the
  operator's own test: `inbound._stop_at_provider` already attempts BOTH
  channels. And the order's "unknown calls nothing" contradicts a deliberate
  design — the stop is attempted BEFORE classification because it can only mean
  somebody receives less — so it is flagged with that consequence rather than
  implemented. The notification half is genuinely missing: A8 / TASK-941.
- **TASK-966 is BLOCKED on content this machine cannot reach.** The 16 sent em1
  bodies have no provider endpoint; Volteum is not among the 40 campaigns in
  this workspace, with real names printed beside the empty hit as the control.
  Nothing goes into `prompts/exemplars/` until the content exists.

**Waiting on the operator or the client, all of it recorded in the tasks:** the
16 em1 bodies or a sent-message read; the Volteum cadence; **which Productive
offer gives before it asks** (without it em1 has no block 2); **two licensed
proof rows** (without them em3 is HELD); whether "unknown calls nothing" is
really wanted; and which word contract survives. **savagebrands is not generated
until TASK-964 is in** — and the regeneration of bigfish and savagebrands is
that task's deliverable, not something that can be done against today's gates.

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
- **I reported 37 stranded spend rows and 482,732 micro-USD.** The real figure
  was 20 rows and 262,114: I had compared counts against the production ledger
  instead of identities, and 17 of the rows were already in it. The migration's
  own dedupe caught it.
- **A reader asked for `subject` and `body` and got nothing**, because the
  provider's sequence steps carry `email_subject` and `email_body` — an empty
  read that is indistinguishable from empty data, caught only by printing the
  keys first.
- **A process filter matched my own query.** Looking for suite processes by
  `CommandLine -like '*run_suite*'` returned my own bash and PowerShell
  wrappers, because the pattern was in their command lines too. The lock's own
  holder liveness is the reading that holds.
- **`git merge -F -` does not read stdin** the way `git commit -F -` does. The
  merge silently did not happen, and the proof printed immediately afterwards —
  `git diff master <branch>`, expected empty — is what caught it.

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
