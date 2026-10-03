# GLM VERDICT — TASK-500: Independent verification of TASK-372

## Target

    task            TASK-372
    branch          origin/qwen-worker-2-r9
    named HEAD SHA  f03c74fc01a40df45419742e122268d11c8395a1
    actual HEAD SHA 84268e53233e37441d9b58414eb432d163537e9f (branch has moved)
    reviewed SHA    f03c74fc01a40df45419742e122268d11c8395a1 (as named)
    worktree        .qwen/worktrees/glm-task500 (detached at named SHA)

**Branch movement noted:** `origin/qwen-worker-2-r9` has moved 5 commits past
the named SHA. This verdict reviews `f03c74fc01` as instructed.

## What TASK-372 claims

Regenerate the suite baseline (a named set of failing tests, not a count) on
clean master, diff against the old 128-name baseline, categorise every new
failure, and fix the `run_suite.py` timeout that was killing long runs.

## Findings

### F1 — Baseline artifact exists and has correct counts [VERIFIED]

- `docs/state/SUITE-BASELINE-2026-09-27.txt`: 239 lines, 228 FAIL/ERROR names,
  all unique (verified by `sort -u | wc -l`).
- Header says "228 distinct fully-qualified failing names" — matches.
- Old baseline (`docs/state/SUITE-BASELINE-2026-09-26.txt` on master): 128
  names, all unique. Matches its own header.

### F2 — Set difference independently recomputed [VERIFIED]

Independent `comm` computation against the two baseline files:

    still failing (intersection):  122
    new (in new, not old):         106
    gone (in old, not new):          6
    122 + 106 = 228 ✓
    122 + 6   = 128 ✓

All numbers match the delta document's claims exactly.

### F3 — The 6 fixed tests match [VERIFIED]

The 6 gone names are exactly:
- 5 from `test_a_resume_leaves_a_ledger_row` (the "PRE-EXISTING RED" from
  TASK-331/Buggie H5)
- 1 from `test_nothing_writes_to_a_provider`

This matches the delta document's "Fixed tests" section verbatim.

### F4 — Three "new module" claims verified [VERIFIED]

`git show 0af11fcb:tests/<module>.py` returns "not in commit" for:
- `test_an_offer_cannot_be_invented` ✓
- `test_strategy_is_set_per_segment_not_per_lead` ✓
- `test_a_dead_cta_link_is_refused` ✓

These modules genuinely did not exist at the baseline commit.

### F5 — Test counts at baseline match delta's claims [VERIFIED, sampled]

Spot-checked four modules at commit `0af11fcb`:

    test_staging_a_campaign_twice_builds_one          12 tests  (delta says 12) ✓
    test_a_five_step_campaign_sends_five_different_emails  27 tests  (delta says 27) ✓
    test_staging_refuses_colliding_contacts             7 tests  (delta says  7) ✓
    test_lead_writes_respect_the_killswitch             5 tests  (delta says  5) ✓

### F6 — Delta document categorisation narrative has factual errors [DEFECT]

**F6a: two_campaigns count is wrong.** The delta says "18 new" from
`test_two_campaigns_do_not_collide_at_the_provider`. Independent `comm`
computation yields **24 new** from this module. The delta's own detailed
listing for this module enumerates 24 names, contradicting its own heading
of "18 new."

**F6b: "test classes that did not exist at baseline" is false.** The delta
says the 18 (actually 24) new names are "from test classes that did not exist
at baseline." I checked: all 12 classes in `test_two_campaigns_do_not_collide_at_the_provider`
are byte-identical at commits `0af11fcb` and `f03c74fc01`. The classes
existed at baseline; the tests within them now fail where they previously
passed. This is a regression, not a "new test class."

**F6c: "68 genuine regressions from 16 modules that ALL PASS" is wrong.**
`test_two_campaigns_do_not_collide_at_the_provider` had 7 errors at baseline
(the delta's own table says so). It is not a module that "ALL PASS[ed] at
baseline." The correct breakdown:
- 3 new modules: 19 failures
- Existing modules that ALL PASSED at baseline: 63 failures from 15 modules
- Existing modules with PREVIOUS failures that now have MORE: 24 from
  two_campaigns (which had 7 at baseline)
- Total: 19 + 63 + 24 = 106 ✓

The total of 106 is correct. The narrative breakdown is not.

**Impact:** The baseline file itself (the named set) is correct and usable as
a merge gate. The delta document's categorisation is misleading but does not
corrupt the baseline. The error is in the explanation, not the data.

### F7 — Stability check NOT performed [ACKNOWLEDGED GAP]

The task's acceptance criterion §6 requires a second full run to diff named
sets and identify flaky tests. The result block explicitly states "NOT YET
PERFORMED" and "a second full run (another ~35 min) is needed." This is
honestly acknowledged but not satisfied.

The regenerated baseline has NOT been proven stable. It may contain flaky
tests that would produce a non-empty diff on re-run.

### F8 — Timeout fix verified [VERIFIED]

`scripts/run_suite.py`: default timeout changed from 1800s (30 min) to 7200s
(120 min). The suite takes 35-100 minutes on this machine; the old default
was insufficient. Fix is correct and minimal.

### F9 — Scope drift is massive [NOTED]

The branch carries 46 commits and 93 changed files vs master. TASK-372's own
artifacts are ~6 files:

    docs/state/SUITE-BASELINE-2026-09-27.txt         (NEW)
    docs/state/SUITE-BASELINE-DELTA-2026-09-26.md     (REPLACED)
    scripts/run_suite.py                              (timeout fix)
    scripts/task372_diff_baseline.py                  (NEW helper)
    scripts/task372_verify_preexisting.sh             (NEW helper)
    docs/qwen-tasks/REVIEW/TASK-372-...md             (moved from TODO)

The remaining ~87 files belong to other tasks (TASK-293, TASK-318, TASK-364,
TASK-387, TASK-400, TASK-403, TASK-411, offers work, status reports, GLM
verdicts, etc.). Merging the whole branch would import all of that.

Cherry-picking the 6 TASK-372 files is straightforward and clean.

### F10 — No dangerous deletions [VERIFIED]

`git diff master...f03c74fc01 --diff-filter=D` returns only the TODO task
file (moved to REVIEW, correct state transition). No source, test, config, or
data files would be deleted by merge. The only file with significant
deletions is `TASK-REGISTRY.json` (123 deletions, 766 additions — net
addition).

### F11 — Suite log correctly excluded [VERIFIED]

`scripts/suite_full_run.log` is not committed (correctly treated as a build
artifact). Not present in the tree or in git.

### F12 — Result block minor issues [NOTED]

- "STATUS: DONE" but file is in REVIEW/ — correct location per QWEN.md rules,
  minor inconsistency with the status label.
- "COMMIT: pending (this commit)" — vague, no specific SHA named.

## Disposition

| Finding | Severity | Evidence |
|---------|----------|----------|
| F1: Baseline exists, correct counts | PASS | 228 unique names, matches header |
| F2: Set difference correct | PASS | Independent comm: 122/106/6 |
| F3: Fixed tests match | PASS | 6 names match verbatim |
| F4: New modules verified | PASS | 3 modules absent at 0af11fcb |
| F5: Test counts at baseline | PASS | 4 modules sampled, all match |
| F6a: two_campaigns count wrong | DEFECT | 24 actual, 18 claimed |
| F6b: "classes did not exist" false | DEFECT | All 12 classes exist at baseline |
| F6c: Breakdown narrative wrong | DEFECT | 63+24, not 68+19 |
| F7: Stability check not done | GAP | Acknowledged, not performed |
| F8: Timeout fix correct | PASS | 1800→7200, minimal change |
| F9: Massive scope drift | NOTED | 6 of 93 files are TASK-372's |
| F10: No dangerous deletions | PASS | Only TODO→REVIEW move |
| F11: Suite log excluded | PASS | Not in tree or git |
| F12: Result block minor issues | NOTED | Vague commit ref, status label |

## Recommendation: REWORK

The core artifact (the regenerated baseline with 228 named failures) is
**correct and usable**. The set difference is verified. The baseline can
serve as the new merge gate.

However, three defects in the delta document's narrative require correction:

1. **Fix the two_campaigns count**: 24, not 18. The detailed listing already
   has 24 names; the heading and summary need updating.
2. **Correct the "new test classes" claim**: The classes existed at baseline.
   The correct characterisation is "tests in existing classes that now fail
   where they previously passed" (regression), not "new test classes."
3. **Fix the breakdown**: 63 regressions from modules that all passed + 24
   new failures from a module that had 7 at baseline, not "68 genuine
   regressions from 16 modules that ALL PASS."

The stability check (F7) is owed but does not block acceptance of the
baseline — it should be done before the baseline becomes the authoritative
merge gate.

**Cherry-pick path:** The 6 TASK-372 files can be cherry-picked cleanly from
this branch. The other 87 files belong to other tasks and should not be
merged as part of TASK-372.

## Reproducible commands

All verification was performed in worktree `.qwen/worktrees/glm-task500`
(detached at `f03c74fc01`):

    # Count names in each baseline
    grep -cE "^(FAIL|ERROR) " docs/state/SUITE-BASELINE-2026-09-27.txt  # 228
    git show master:docs/state/SUITE-BASELINE-2026-09-26.txt | grep -cE "^(FAIL|ERROR) "  # 128

    # Independent set difference
    comm -12 <(grep -E "^(FAIL|ERROR) " docs/state/SUITE-BASELINE-2026-09-27.txt | sed 's/^[A-Z]* //' | sort -u) \
             <(git show master:docs/state/SUITE-BASELINE-2026-09-26.txt | grep -E "^(FAIL|ERROR) " | sed 's/^[A-Z]* //' | sort -u) | wc -l  # 122

    comm -23 <(...) <(...) | wc -l  # 106 new
    comm -13 <(...) <(...) | wc -l  # 6 gone

    # two_campaigns actual new count
    comm -23 <(grep "test_two_campaigns" docs/state/SUITE-BASELINE-2026-09-27.txt | sed 's/^[A-Z]* //' | sort -u) \
             <(git show master:docs/state/SUITE-BASELINE-2026-09-26.txt | grep "test_two_campaigns" | sed 's/^[A-Z]* //' | sort -u) | wc -l  # 24

    # Verify classes exist at baseline
    git show 0af11fcb:tests/test_two_campaigns_do_not_collide_at_the_provider.py | grep "^class "
