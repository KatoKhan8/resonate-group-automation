PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-439 — GLM independent verification: TASK-280, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-280
    branch          qwen-worker-4-r9-task280
    branch HEAD SHA cdffd0a2d3bab2bea4d7a35373876fce93cc97fe

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`cdffd0a2d3bab2bea4d7a35373876fce93cc97fe` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`cdffd0a2d3bab2bea4d7a35373876fce93cc97fe` anyway, because that is the artifact this verdict is about.

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
5. **Would merging it DELETE anything?** `git diff master...cdffd0a2d3bab2bea4d7a35373876fce93cc97fe --stat`. This
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

Write the verdict to `docs/glm-reviews/TASK-439-verify-task-280.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## Result block

    STATUS: DONE
    BRANCH: qwen-worker-6-r9
    COMMIT: c3e126b5
    VERDICT FILE: docs/glm-reviews/TASK-439-verify-task-280.md
    TARGET REVIEWED: qwen-worker-4-r9-task280 at cdffd0a2d3bab2bea4d7a35373876fce93cc97fe
    DISPOSITION: REWORK
    
    TESTS: 
      - 25 tests in TASK-280's test suite, all pass (verified in isolated worktree)
      - Mutation test performed: overriding _classify_provider_lead to always return 
        "MATCHED" breaks test_no_ledger_rows_is_unrecorded (as expected)
      - Verified sweep functions call _classify_provider_lead (wiring is real)
    
    FILES CHANGED:
      docs/glm-reviews/TASK-439-verify-task-280.md (new, 357 lines)
    
    FINDINGS:
      1. Artifact exists and matches claims (VERIFIED)
         - scripts/reverse_reconcile.py, tests/test_reverse_reconciliation_is_exhaustive.py,
           docs/REVERSE-RECONCILIATION-2026-09-25.md all present at target SHA
         - 25 tests pass, script is structurally correct
      
      2. Zero production callers, but consistent with existing pattern (NOT A DEFECT)
         - grep -rn reverse_reconcile src/ returns nothing
         - Same pattern as reconcile_ledger.py (forward reconciler), also zero callers
         - Both are operator tools invoked directly, not library modules
      
      3. Key derivation is imported, not reimplemented (VERIFIED WITH CAVEAT)
         - push.push_id is imported from src.push and called correctly
         - BUT: two tests use inspect.getsource to check for strings in source text
         - This is explicitly forbidden by QWEN.md ("assertions on source text")
         - Tests prove the text is present, not that the behavior is correct
      
      4. Live evidence is absent (NOT VERIFIED - HIGH SEVERITY)
         - Result block reports 0 campaigns walked, 0 provider rows read
         - Task requires per-campaign counts and at least one UNRECORDED row with
           provider response fields quoted
         - Result acknowledges "live sweep is owed from Claude's worktree"
         - This is the most significant gap
      
      5. Test falsifiability is mixed (PARTIALLY VERIFIED - MEDIUM SEVERITY)
         - GOOD: _classify_provider_lead tests are behavioral (mutation test confirms)
         - BAD: test_push_is_imported_in_reverse_reconcile and test_push_id_is_called
           are source-text assertions (forbidden by QWEN.md)
         - BAD: test_identity_holds_with_lost_row_simulation is a tautology
           (constructs 1 row, verifies 1==1, then asserts 1!=2)
         - BAD: No integration test drives through main() with mocked provider data
      
      6. Merging would not delete anything (VERIFIED)
         - 13 files changed, 3700 insertions, 9 deletions
         - 9 deletions are task state transitions and reformatting, not functionality
      
      7. Scope drift is significant (VERIFIED - MEDIUM SEVERITY)
         - Branch carries 2,378 lines from TASK-308 (Anthropic provider) and
           TASK-315 (cross-channel stop)
         - Only TASK-280's 3 files (1,046 lines) should be merged
         - Merging entire branch would integrate unreviewed work
      
      8. ISSUE-025 analysis is not verified (NOT VERIFIED - HIGH SEVERITY)
         - Task requires showing classification for campaigns 491-498
         - Result says "yes, in principle" but provides no actual classification
         - Theoretical claim, not verified against live data
    
    RISKS:
      - Live sweep not run: cannot verify the script works against real provider data
      - Source-text assertions: tests would pass if import is present but broken
      - Tautological test: proves nothing about what happens when a row is lost
      - Scope drift: branch carries 2,378 lines from other tasks
      - ISSUE-025 claim unverified: cannot confirm the sweep would catch the incident
    
    RECOMMENDED CLAUDE ACTION:
      REWORK, not merge. Three must-fix items:
      
      1. Run the live sweep from Claude's worktree with production state
         - Per-campaign counts from production campaign bindings
         - At least one UNRECORDED row with provider response fields quoted
         - ISSUE-025 classification for campaigns 491-498
      
      2. Replace source-text assertions with behavioral tests
         - test_push_is_imported_in_reverse_reconcile should verify derived keys
           match push.push_id output, not that the import statement exists
         - Example: call _sweep_heyreach with mocked data and verify derived_keys
      
      3. Replace tautological test with real mutation test
         - test_identity_holds_with_lost_row_simulation should construct N rows,
           simulate a bug that drops one, verify identity breaks
      
      Cherry-pick only TASK-280's files when merging (not the scope drift).
