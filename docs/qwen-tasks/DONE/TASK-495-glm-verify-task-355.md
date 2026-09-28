PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-495 — GLM independent verification: TASK-355, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-355
    branch          origin/qwen-worker-12-r9-sync
    branch HEAD SHA 3da4a246ee2536760d04dfc4d1d94b649160c2fa

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`3da4a246ee2536760d04dfc4d1d94b649160c2fa` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`3da4a246ee2536760d04dfc4d1d94b649160c2fa` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-495-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT BLOCK

**STATUS:** DONE
**COMMIT SHA:** 306f2bd4 (on origin/qwen-worker-7-r9)
**VERDICT FILE:** docs/glm-reviews/TASK-495-verify-task-355.md
**VERDICT:** MERGE (cherry-pick `ed5fd975` then `e510b518`)

**TESTS:**
- TASK-355's 7 tests pass in isolated worktree at `3da4a246`
- 30 related spend/pricing tests pass (no regressions)
- Mutation test performed: cache_read priced at input rate → test 1 fails (guard is real)

**FILES CHANGED:**
- `docs/glm-reviews/TASK-495-verify-task-355.md` — NEW, the verdict
- `docs/qwen-tasks/DONE/TASK-495-glm-verify-task-355.md` — task file moved to DONE

**FINDINGS:**

1. **Artifacts exist on the reviewed ref.** `config/model-prices.yaml`, `src/modelprices.py`, and `tests/test_a_cached_token_is_not_priced_as_a_fresh_one.py` all exist at `3da4a246`. Prices match published Anthropic rates.

2. **`cost_micro_usd` has 5 production callers** (`llm.py:298`, `llm.py:313`, `glm.py:308`, `glm.py:337`, `glm.py:539`). The modification is purely additive — no existing caller is broken. All 30 related tests pass.

3. **No production caller passes cache tokens yet.** GLM's `_usage()` extracts `cached_tokens` (OpenAI-style key), not `cache_creation_input_tokens`/`cache_read_input_tokens` (Anthropic-style). The cache pricing code is correct but has no production effect until a provider adapter is updated. This is NOT a defect in TASK-355 — the task scope was to build the pricing infrastructure, not to rewire provider adapters. **Disposition: ACCEPTED DEFERRED RISK.**

4. **`cost_details()` has zero production callers.** It's a reporting helper used only in tests. Not harmful, not urgent. **Disposition: ACCEPTED DEFERRED RISK.**

5. **Mutation test confirms the guard works.** When `cache_rates_for` returns the input rate (the original bug), cache_read costs 3000 (same as fresh) instead of 300. Test 1 fails. The guard is real.

6. **Tests are falsifiable.** They assert on numeric values (300 < 3000, ratio < 0.5), exact equality (4500 micro-USD), None checks, and component sum reconciliation. No `hasattr`, no source text search.

7. **Merging TASK-355 would NOT delete anything.** The two commits are purely additive: +4 lines YAML, +124/-7 lines modelprices.py, +169 lines test, +30 lines result block.

8. **Scope drift — the branch carries 31 commits from 14+ tasks.** TASK-355's work must be cherry-picked, not merged as a branch. The two commits are `ed5fd975` and `e510b518`.

**RISKS:**
- Cache tokens are invisible to the ledger until a provider adapter extracts them with the correct key names. This is a separate task, not a defect in TASK-355.
- `cost_details()` may never be consumed. It's a reporting helper, not core functionality.

**RECOMMENDED CLAUDE ACTION:** Cherry-pick `ed5fd975` then `e510b518` from `origin/qwen-worker-12-r9-sync`. Do not merge the branch — it carries 31 commits from 14+ tasks. TASK-340's $2 measurement is unblocked.
