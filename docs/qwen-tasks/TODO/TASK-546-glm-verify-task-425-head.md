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
