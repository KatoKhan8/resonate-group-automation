# The Qwen workforce is down until 2026-09-20

Measured 2026-09-16 ~09:51 UTC. Every worker dispatch now fails in about five
seconds with the same answer:

    Quota exhausted: Your token-plan 1-week quota has been exhausted.
    The quota will reset at 09-20 19:27:00 UTC.
    (cause: insufficient_quota: 429)

All eight worktrees, three rounds in a row (r42, r43, r44). This is an account
quota, not a per-key or per-worktree problem, and it does not reset for four
days.

## What this costs

Qwen has been the bulk workforce for this entire run: 57 tasks integrated
today, TASK-157 through TASK-214. Everything delegable was delegated to it.
With it down, the delegation layer in `PROVIDER-ROUTING-POLICY.md` has a hole
in the middle:

    Python          deterministic work, unaffected
    QWEN            DOWN until 2026-09-20 19:27 UTC
    GROK / xAI      available, and billed per call - TASK-166 and TASK-192
                    spent $2.78 between them
    CLAUDE          available, and the expensive option for bulk work

So work that would have gone to a worker now goes to Claude or to Grok, and
neither is a bulk engine at Qwen's price.

## No damage was done

Worth recording, because a failing dispatch could have been much worse. The
worker process dies BEFORE its first action, which is the `git mv` that claims
a task by moving it out of `TODO/`. So:

    claims held                 0, released cleanly
    task files                  intact in TODO/
    worker branches             no commits, still at master
    working tree                clean

Had the workers died just after the claim commit instead, three tasks would
have been moved out of `TODO/` on branches that did no work, and
`_claimed_on_a_branch` would have hidden them from the dispatcher - the
TASK-183 failure, which took a re-issue under a new id to escape. The pool got
lucky on ordering.

## What not to do

**Do not keep sweeping the pool.** Each sweep costs nothing in tokens but
writes false `DONE ... exit=0` lines into `pool-logs/pool.log`, which is the
file a fresh session reads to learn what happened. An exit code of 0 from a
worker that never started is the most misleading thing in that log.

**Do not switch the workers to another model to keep the pool busy.** The
tasks written for Qwen assume its context handling and its instruction
discipline, and several carry hard prohibitions - no provider writes, no
approval setting, no gate weakening - that were written knowing which model
would read them. Re-pointing eight workers at an untested model to avoid
idleness is how a prohibition gets missed.

## What to do instead

Three tasks are queued and ready: TASK-214 (P0), TASK-212 and TASK-213 (P1).
TASK-214 is the throughput defect - the free crawl is in the routing table and
has never produced a ledger row - and it is worth Claude doing directly rather
than waiting four days.

The production path is unaffected by this. It was already blocked on two
operator commands, and those need no worker:

    py -3 scripts/apply_control_approval.py --live
    py -3 scripts/stage_canary_lead.py --live
