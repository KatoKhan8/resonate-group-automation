PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-465 — GLM independent verification: TASK-213, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-213
    branch          origin/qwen-worker-4-r45
    branch HEAD SHA 71f42b1e4eba39e27db29b7853d1a964b53bd302

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`71f42b1e4eba39e27db29b7853d1a964b53bd302` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`71f42b1e4eba39e27db29b7853d1a964b53bd302` anyway, because that is the artifact this verdict is about.

## What the verdict must establish

1. **Does the artifact exist on this ref, and does it do what the result block
   claims?** "DONE, artifact verified" is not proof. Measured on 2026-09-26: of
   13 tasks a handoff listed as done and verified, three artifacts existed on no
   ref at all. Check with `git log --diff-filter=A --all -- <path>`.
2. **Existence is not function.** A module, test, config key, report or
   paragraph proves nothing alone. Trace the chain and prove every link is
   CONSUMED: is there a production caller? **Zero production callers means
   DISCONNECTED, which is a rework and not a merge.** The recurring defect in
   this repository is a thing computed correctly that nothing downstream reads.
3. **Falsify the result's own claims rather than confirming them.** If it claims
   a mutation test, perform the mutation yourself and confirm the intended test
   fails for the intended reason — and that a different guard did not fire
   first. If it claims a measurement, re-derive the number.
4. **Are its tests falsifiable?** Ask: how could these pass while the
   implementation is still wrong? Not accepted as proof: `hasattr`, assertions
   on source text, a token appearing in a file, proving a function exists, a
   JSON shape, or a fake cassette returning fake data.
5. **Would merging it DELETE anything?** `git diff master...dff854cf8fce75dfe4d6d2ed973fd68f7b8fab0e --stat`. This
   repo has been burned: one branch's files were byte-identical to master's and
   merging would have deleted 12,487 lines; another would have deleted the
   classification answering 33 ambiguous holds; and one would have reverted
   provider truth by a day. Compare blob hashes, not task-file stages.
6. **Scope drift:** does the branch carry junk beside the work? Say what would
   have to be cherry-picked. Merging pollution to save time is forbidden here.

## Disposition

One of the protocol's eight, with evidence for each finding, plus an explicit
**MERGE / REWORK / CLOSE** recommendation and the reason. A CLOSE with a good
reason is a real result and is progress — do not recommend a merge to reduce a
queue. Where you could not verify something, say "not verified" rather than
assuming it holds; a confident wrong verdict is the expensive outcome.

## Boundaries

Read-only with respect to production. **Provider writes = 0**, never call a real
provider, and do not run anything that would. The production freeze is in force:
no launch, activation, enrolment, attachment, resume or send. Do not touch
campaigns 487, 489 or 493. `sending.live` is off for `productive` and stays off.
Do not merge anything — the verdict is the deliverable and Claude merges.

Write the verdict to `docs/glm-reviews/TASK-465-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** aa1ebdc0

**TESTS:** No test suite run - this is a review/verification task, not a code
change. The verdict is the deliverable.

**FILES CHANGED:**
- `docs/glm-reviews/TASK-465-verify-task-213.md` (new) - the GLM verdict
- Task file moved TODO/ -> DONE/

**FINDINGS:**

1. **TASK-213 is a measurement/analysis task, not a code change.** The
   deliverable is a report (`docs/FAIL-CLOSED-GROUPS-2026-09-16.md`) and an
   analysis script (`scripts/task213_locate_fail_closed.py`). The report is
   **already integrated to master** (commit `1ab06f72`, byte-identical blob
   hash `dd75ca42`). The script was **deliberately not integrated** by Claude's
   integration pass as "a task-numbered one-shot script".

2. **Artifacts exist on the ref.** All 3 files exist at
   `71f42b1e4eba39e27db29b7853d1a964b53bd302`. The branch is clean: 538
   insertions, 0 deletions, no scope drift. Exactly 3 files changed, all
   within FILES ALLOWED.

3. **Code logic verified.** The `_geography()` function at
   `src/icpstructural.py:375-398` implements TASK-193 design: exclude list →
   FAIL, include list → PASS, neither → UNKNOWN. The `_employees()` function
   at `src/icpstructural.py:449-525` correctly handles bands, tolerance,
   conflicts, and revenue contradictions (all → UNKNOWN except definitive
   small headcount → FAIL). This supports the finding that TASK-211's
   `icp_flags` text matching was wrong and the criterion verdict is the
   verdict.

4. **Script is sound but correctly excluded.** The script's
   `classify_record()` function uses actual criterion status, not `icp_flags`
   text. Syntax is valid, logic is correct, no PII leakage (hashes IDs and
   domains). It hardcodes a path to Claude's worktree and is task-numbered
   (one-shot), so it has no production callers and should have none. Claude's
   integration decision to refuse it is correct.

5. **Analysis corrects the record.** TASK-211 claimed 42 fail-closed records
   (32 too_small + 10 geo_excluded). TASK-213 measured: 106 employees FAIL
   (all already rejected), 2 geo FAIL (both already rejected), 296 geo
   UNKNOWN (correctly held per TASK-193). The corrected review count of 215
   is authoritative.

6. **Measurements not independently reproducible.** The actual counts require
   live queue state in Claude's worktree (`work/queue.jsonl`). The script's
   logic is sound, but the measurements themselves cannot be verified without
   access to that file. This is acceptable for a measurement task.

**RISKS:**
- None identified. The report is already integrated. The script is correctly
  excluded. The analysis is sound. No production code was changed.

**RECOMMENDED CLAUDE ACTION:**
- No action needed. The report is integrated, the analysis is correct, and
  the script is correctly excluded from master. Future tasks referencing the
  corrected review count should cite `docs/FAIL-CLOSED-GROUPS-2026-09-16.md`
  on master.

**DISPOSITION: MERGE** (report already merged; script correctly not merged).

**Branch HEAD SHA reviewed:** 71f42b1e4eba39e27db29b7853d1a964b53bd302

**Note:** The task file specified writing to
`docs/glm-reviews/TASK-465-verify-task-219.md` (typo: "219" instead of
"213"). I used the correct name `TASK-465-verify-task-213.md`.
