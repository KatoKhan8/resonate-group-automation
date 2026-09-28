PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-475 — GLM independent verification: TASK-262, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-262
    branch          origin/qwen-worker-10-r59
    branch HEAD SHA 1c8377bd4dcc398b0e9536ccbda3df05295b3903

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`1c8377bd4dcc398b0e9536ccbda3df05295b3903` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`1c8377bd4dcc398b0e9536ccbda3df05295b3903` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-475-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

**STATUS: DONE**

**COMMIT SHA:** 1cd1fa79

**TESTS:**
- `tests/test_productive_verification_roles.py`: 7/7 pass (untouched, uses clients.load directly)
- `tests/test_enrich.py`: 49/49 pass
- `tests/test_fixture_hygiene.py`: 17/17 pass
- `tests/test_preproduction.py`: 28/28 pass
- `tests/test_approve.py` + `test_push.py` + `test_cadence.py` + `test_double_verification.py` + `test_events.py` + `test_personas.py`: 256/256 pass
- `tests/test_e2e.py` (partial run before 300s timeout): all completed test classes pass

**FILES CHANGED:**
- `docs/glm-reviews/TASK-475-verify-task-262.md`: verdict document (artifact)

**FINDINGS:**
- Artifact exists on ref `1c8377bd4dcc398b0e9536ccbda3df05295b3903` and does what the result block claims
- Shared fixtures (phase2/5/6/7.jsonl) untouched — zero diff confirmed
- Pin is consumed by 15+ test modules (45 call sites found by grep)
- Falsification confirmed: removing the verification pin from `fixture_config` causes `'held' != 'verified'` failures in tests that were claimed fixed
- Tests are falsifiable — they assert on outcomes (record state, verdict values), not source text
- Tests that ARE about live verification roles (test_productive_verification_roles) bypass the pin and pass 7/7
- No production impact: zero diff on src/, config/, scripts/
- No deletion risk: only the task file lifecycle move (TODO→DONE)
- No scope drift: 5 files changed on the branch, all relevant to the task

**RISKS:**
- The verdict filename in the task file says `TASK-475-verify-task-219.md` but the target is TASK-262. I wrote the verdict to `TASK-475-verify-task-262.md` (correct target). This is a typo in the task file, not a finding about the branch.

**RECOMMENDED CLAUDE ACTION:**
- Merge TASK-262. The change is minimal, correct, well-scoped, and falsifiable.
- Regenerate the baseline JSON at the merge commit to record the new 50-failure state.

**DISPOSITION: MERGE**
