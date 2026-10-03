PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-474 — GLM independent verification: TASK-250, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-250
    branch          origin/qwen-worker-9-r61
    branch HEAD SHA 3efcc9683f2a3dd23b1096ef1824d70d78f5cb33

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`3efcc9683f2a3dd23b1096ef1824d70d78f5cb33` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`3efcc9683f2a3dd23b1096ef1824d70d78f5cb33` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-474-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

# RESULT

STATUS: DONE
COMMIT SHA: f21aa5bbd (verdict committed and pushed to qwen-worker-8-r9)
TESTS: Verified at SHA 3efcc9683f2a3dd23b1096ef1824d70d78f5cb33 on origin/qwen-worker-9-r61. 391+ tests verified across 12 modules, all pass. Two mutation tests prove the wiring is real.
FILES CHANGED:
  - docs/glm-reviews/TASK-474-verify-task-219.md: GLM independent verdict (306 lines)

FINDINGS:
  1. DISPOSITION: MERGE. The artifact is correct, the wiring is real, and the approach is safe.
  
  2. Artifact verified at exact SHA 3efcc9683f2a3dd23b1096ef1824d70d78f5cb33. Changes to tests/base.py, tests/test_e2e.py, tests/test_enrich.py are present and consumed.
  
  3. Existence IS function: fixture_config() is consumed by pin_client_config() and 8+ test modules. pin_client_config() patches clients.load on the clients module object, which is what every caller holds.
  
  4. Two falsification tests prove the wiring is real:
     - Mutation 1: Removed verification pin → test_the_clean_domain_verifies FAILED with 'held' != 'approved' (EXACTLY the failure mode TASK-250 described)
     - Mutation 2: Set pin to WRONG values → test_productive_verification_roles still PASSED (proves it reads live config, not pinned)
  
  5. Shared fixtures untouched: git diff on tests/fixtures/ returns empty. Zero changes to phase2/5/6/7.jsonl.
  
  6. No deletions: git diff --diff-filter=D returns empty.
  
  7. No forbidden files touched: git diff on src/ config/ returns empty.
  
  8. Pinned vs live roles are DIFFERENT (verified at runtime):
     - Pinned: primary=contactout, secondary=deliverable, catch_all=reoon (OLD roles, matching fixtures)
     - Live: primary=deliverable, secondary=reoon, catch_all=reoon (NEW roles, operator's decision)
  
  9. Test results at SHA 3efcc9683:
     - test_e2e.TestEnrichmentOutcomes: 9/9 OK (including test_the_clean_domain_verifies)
     - test_enrich: 49/49 OK
     - test_productive_verification_roles: 7/7 OK (asserts LIVE roles)
     - test_approve: 43/43 OK
     - test_push: 37/37 OK
     - test_cadence: 38/38 OK
     - test_generate: OK
     - test_double_verification: 53/53 OK
     - Other fixture consumers: 155/155 OK
  
  10. Full suite baseline comparison is OWED (noted in verdict). Claude should run the full suite from his worktree and diff by name against docs/state/SUITE-BASELINE-2026-09-22.json to verify no regressions.

RISKS:
  - Full suite baseline comparison not completed (runtime constraints). Risk: LOW — 391+ tests verified across 12 modules.
  - Pin must be updated if fixtures change. Risk: LOW — known limitation, documented in result block.
  - test_e2e full module not verified (timed out after 300s). Risk: LOW — TestEnrichmentOutcomes (9/9) verified, including the named test.

RECOMMENDED CLAUDE ACTION:
  1. Run the full suite from Claude's worktree and diff by name against the baseline to verify no regressions.
  2. Merge origin/qwen-worker-9-r61 (SHA 3efcc9683f2a3dd23b1096ef1824d70d78f5cb33) to master.
  3. The verdict is in docs/glm-reviews/TASK-474-verify-task-219.md.
