PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-546 — GLM adversarial verification: the TASK-425 branch head

**Operator decision, Zvonimir, 2026-09-28:** idle GLM capacity goes to
adversarial verification of completed critical-path work, in this priority —
**TASK-425 branch review first**, then the runtime approval-hash finding, then
P0-A, then P0-B, then canonical projection integration later.

Follow `docs/GLM-REVIEW-PROTOCOL.md`. It is the standing contract: review
triggers, the isolated-worktree rule, falsification over confirmation, and the
eight dispositions every finding must carry. This file names the target, not
the procedure.

## Target — review THIS and nothing else

    task            TASK-425
    branch          origin/task-425-one-account-dry-run
    branch HEAD SHA 2d54e274f1dbf646907073047ede73b5999ab273

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID**, and a
verdict against an older SHA is not a verdict on the current branch. Check out
`2d54e274f1dbf646907073047ede73b5999ab273` in an isolated worktree and review
that tree. **Do not review master.** The local ref of this branch in the main
checkout is STALE at `3e75b563` and pinned there by an abandoned worktree —
`origin/` is the authority.

## What is already settled — do NOT re-litigate

    criterion 1  causal matrix                    BLOCKED
    criterion 2  signature chain                  TESTING (separate task)
    criterion 3  offer sequencing + negative test  PASS
    criterion 4  claim/message audit              UNPROVEN

## The question this verdict answers

**Is this branch safe to merge to master as it stands?** Specifically:

1. **Does it weaken any gate, widen any rule, or make any check inert?** This is
   the highest-value thing to find. The branch's own history contains a fix that
   WAS a loosening — the first `no_repetition/subjects` attempt made the check
   structurally incapable of firing, and an adversarial review caught it, not the
   author. **Assume there may be another one.** For every gate it touches, ask:
   can this still fail, and on what input?
2. **Does it silently revert anything on master?** Check the `CLIENT_SUPPLIED`
   claim-licensing split, the `copylint._traces` grounding fix, and the
   killswitch gates specifically.
3. **Scope drift and junk** — anything that does not answer to TASK-425.
4. **Criterion 4's verifier**: does it check the ACTUAL rendered claims in the
   copy, or merely that audit FIELDS exist? The operator downgraded criterion 4
   to UNPROVEN on exactly this question. An independent read of that verifier is
   the single most useful thing in this review.

**Falsification over confirmation.** A verdict that agrees with the author adds
nothing; show what you attacked. Read-only — do not merge, do not push to the
branch under review.

---

## RESULT BLOCK

**STATUS:** DONE
**ARTIFACT KIND:** finding (adversarial review document)
**COMMIT SHA:** review artifact committed at `be1a7739` in worktree review-546;
  copied to `docs/glm-reviews/TASK-546-verify-task-425-head.md` on qwen-worker-3-r9
**TESTS:** 24/24 ladder tests pass at `2d54e274` (unittest, full module).
  Mutation harness (7/7 killed) verified by code review, not re-run.
**FILES CHANGED:**
  - `docs/glm-reviews/TASK-546-verify-task-425-head.md` (new, review document)
  - `docs/qwen-tasks/REVIEW/TASK-546-glm-verify-task-425-head.md` (moved from TODO)

**FINDINGS:**

1. **Criterion 4 verifier checks FIELD PRESENCE, not semantic correctness.**
   The completeness checker (`scripts/task425_criterion4_completeness.py`)
   checks that audit field NAMES appear in rendered text, not that the claims
   are correct. The operator's UNPROVEN verdict is CORRECT. The artifact
   generator does substantive verification through `claims_in()`, but the
   completeness checker does not verify that verification is correct.

2. **`no_repetition/subjects` is structurally unreachable on every configured
   cadence** (all declare one thread starter). The check warns when it cannot
   compare, which is the fix for the first version that was silently inert.
   Real loss, disclosed.

3. **`step_objectives` order test passes a genuine partial shuffle** where each
   step keeps one word of its own rung. Limitation of a new check, not a
   regression. Master enforced `step_objectives` not at all.

4. **`ai_is_supporting` does not reach LinkedIn on the staging path.** The
   writer prompt overstates the gate's reach. Pre-existing behaviour, but the
   prompt edit makes it a new misstatement.

5. **`bisonfactory._offer_for` parameter mismatch** (`client` where
   `segment_key` is expected). Latent — all offers are `segment: all`.

6. **Config `enforcement_status` is now false** — the branch wired the
   enforcement it said was missing. One-line fix owed.

7. **`copylint._traces` substring defect (ISSUE-055)** known, disclosed in
   artifact, not fixed. Tightening the gate would change what is "licensed".

8. **`generate.run` has no production caller.** Integration tested, not
   production active. Disclosed in findings.

**WHAT I ATTACKED AND COULD NOT BREAK:**
- The `comparable` flag: correctly computed, correctly fails closed.
- The ladder tests: 24/24 pass, with controls and a booby trap.
- Killswitch, CLIENT_SUPPLIED, copylint._traces: byte-identical to master.
- Provider writes: zero, verified by mtime and content.
- No PII/credentials in artifact.
- No scope drift.

**RISKS:** None that block merge. Follow-ups 1-4 from the previous review
are owed but non-blocking.

**VERDICT: MERGE** at `2d54e274f1dbf646907073047ede73b5999ab273`, as a true
`git merge` and never as a squash or replace. Confirms the previous review's
MERGE verdict independently.

**RECOMMENDED CLAUDE ACTION:** Accept the review. File follow-ups for the
config misstatement and the `_offer_for` parameter mismatch if not already
tracked. Regenerate the suite baseline on master (now 7+ names adrift).
