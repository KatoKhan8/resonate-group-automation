# Handoff — 2026-09-30, production window

Written at a safe checkpoint, per the operator's acceleration order. Compact
on purpose: what is true, what is next, and where to look.

## Production state

    master = origin/master = 55d30d66
    provider writes            0
    prospect-facing sends      0
    campaign activations       0
    enrolments                 0
    sending.live (productive)  off
    Rachele                    HELD, artifact + hash fba63864ca640b9e intact
    canary                     none. No contact has cleared every gate.

## Current candidate and first blocker

    CURRENT CANDIDATE   the queue below, in approved source order
    FIRST BLOCKER       repetition_across_rungs, and per-step copy quality
                        (short em4/em5, li3 mirroring em3)
    OWNER               Claude
    CLASSIFICATION      D/A - thin evidence plus genuine writer difficulty
                        differentiating five rungs. NOT a contradiction
                        between canonical rules, so bounded-convergence
                        policy says HELD and move on rather than loop.

## The queue (first 200 source rows, 17 qualified)

    65   sohoexp-com            NOT_QUALIFIED at ICP, "not an agency"
    71   cglife-com             HELD  repetition; li3 mirrors em3
    89   byhook-com             HELD  repetition 10/10
    109  upgrow-io              HELD  em4 short; li5 unsupported claim
    112  firstperson-is         running
    118  esparza-com            running
    126  l-s-com                running
    157  digitalposition-com    running
    161  ignitesocialmedia-com  not attempted
    168  interactmarketing-com  not attempted
    170  agencyhabitat-com      not attempted
    181  bakemorepies-com       not attempted
    185  wildstyle-network-com  closest: 5 problems, em1/em2 are old copy
    198  crawfordgroup-com      not attempted

`scripts/canary_candidate_walk.py --limit N` rebuilds this. Source position
is the CSV row number; the walk is resumable because it derives everything.

## What changed today — 13 defects, each tested and mutation-proved

Five were the same shape: two approved rules, each correct alone, jointly
impossible.

    d393a8f7  free crawler never SCORED what it retained - 550 of 1,224 rows
              across 213 records were unusable; 296 became admissible
    20d9fb12  normaliser rewrote an em dash into " - ", the exact pattern the
              copy lint bans, immediately before the lint
    d3dc4ca7  the approved ladder required naming "Report Intelligence" at
              rung 4 and the lint read it as invented; plus a NAMED customer
              outcome cleared both gates
    8b549d06  the same, at sequencegate's own call site - em4 10/10
    62c6ea06  li3 overwrote em3, so the email ladder was enforced at staging
              and silently NOT at generation
    f88d9eca  the planner refused to draft emails for 787 contacts the
              client's own policy had cleared
    4368bb46  channels.email_verdict asked under the defaults, not the policy
    4ae050c1  research.why had no reason for "the writer needs a fact"
    e7e7de7a  that reason could not reach execution
    233dd693  a rung naming the prospect's own situation must be a QUESTION
              (TASK-903, proved: em3 refused 10/10 on every account)
    921ad107  AUTONOMOUS_PRODUCTION approval authority
    01b7caf6  P.S. authority on the approved step; grant bound to campaign
    f7d4d5cd  personalization is a LADDER, not a gate
    55d30d66  TASK-930 research batching (Qwen, reviewed and integrated)

## Red tests

`docs/RED-TEST-CLASSIFICATION-2026-09-30.md`. Two were defects IN THE TESTS
and are fixed. `test_generate`'s three failures are ONE stale fixture with
zero pack facts. `test_e2e`, `test_preproduction`, `test_invariants` and
`test_contactout_first` are NAMED AS OUTSTANDING, not waved through.

## Workers

    TASK-930   DONE, reviewed, integrated at 55d30d66
    TASK-931   GLM adversarial verification - TODO, never dispatched
    TASK-932   stale fixtures - TODO, dispatch ABORTED
    TASK-933   durable controller - TODO, dispatch ABORTED

The two aborts were the pool's own safety check: `resonate-qwen-2` and
`resonate-qwen-4` are on stale SHAs with unpushed work from older tasks
(TASK-364, TASK-279). `resonate-qwen-4` has DIVERGED from its remote and was
NOT force-pushed. Reset those worktrees before dispatching again.

## The thing most worth doing next

The writer cannot yet produce eleven gate-clean messages for one contact. The
architectural cause is unchanged and is the one thing that would close it:
`_refuse_partial_regeneration` forbids rewriting one step, so every attempt
discards the 8-9 messages already clean and re-rolls all eleven, and
`_adapt_plan_to_cadence` stores all-or-nothing over the candidate set. Joint
satisfaction of ~15 constraints across 11 messages by whole-set sampling is
the wrong shape. A step-scoped rewrite holding the clean siblings fixed is
the fix. It is a design change and the operator has said NO NEW FEATURES
until a canary is live, so it needs an explicit decision.
