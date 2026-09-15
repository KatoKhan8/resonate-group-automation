# Autonomous run checkpoint - 2026-09-15, post-shutdown recovery

Written by Claude. Regenerate the machine-readable half with
`py -3 scripts/durable_state.py` and `py -3 scripts/provider_truth.py`.

This file exists so a fresh session on a different computer, with a clone and
the secrets supplied separately, can say what happened and what to do next
without this terminal.

---

## GIT

    master HEAD     398948e  (later commits may follow; git log is the authority)
    origin/master   identical
    worktree        clean
    branches        round-6 and round-7 worker branches, all pushed

## WHAT THE SHUTDOWN COST - NOTHING, AS IT TURNED OUT

The laptop went down after 01:29. Three processes died: the regeneration
(which had already completed, exit 0), TASK-070's outcomes collection, and
TASK-059 on worker 4.

**TASK-059 had finished.** It wrote `docs/ESTATE-BISON-OUTCOMES-2026-09-15.md`
at 01:26 and the shutdown caught it before it could commit. Recovered verbatim
from the `resonate-qwen-4` worktree and committed at `f164f8c`. The collection
was NOT re-run. TASK-037's result block was recovered the same way.

Nothing was lost. That was luck, not design, and it is why the durability
policy now exists.

## RECOVERED, NOT RE-RUN

    TASK-059   estate outcomes report, complete, on qwen-worker-4
    TASK-037   result block, already salvaged into master at 9358703

## PROVIDER TRUTH - THE THING NO LOCAL ARTEFACT CAN TELL YOU

`docs/HEYREACH-PROVIDER-TRUTH-2026-09-15.md`,
`docs/state/PROVIDER-CAMPAIGNS.json`, `docs/state/SENDER-CAPACITY.json`.

### HeyReach

    599020   RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1
             DRAFT, created 2026-09-13, startedAt NULL
             list 933603 attached, 0 LEADS
             1 sender attached, resolves and is active
             24 nodes, readable, hash 32f8dde79bfa0f27
             readback 27/27 PASS, re-verified this morning

    account  83 campaigns. Exactly ONE created by Resonate OS.
             8 DRAFT, 32 PAUSED, 31 FINISHED, 12 IN_PROGRESS - the
             IN_PROGRESS ones are the client's own, not ours.

**It exists. It is empty. It has never started.** Internal state and provider
state AGREE - no consistency defect.

**Every copy-bearing node holds exactly ONE message.** The five-variant
machinery has never reached this campaign.

### Sender estate

    41 seats, 33 healthy, 1 active-but-auth-invalid, 7 inactive
    1054 connection requests/day, 1143 messages/day across healthy seats
    healthy seats with NO active campaign: ZERO

Throughput was never the constraint. And no healthy seat is uncommitted, so
adding senders to a cohort means reassigning seats already working.

### EmailBison

    481   paused, 23 leads, 5 steps, 0 sent     ours
    451   completed, 1 sent, 0 bounced          ours
    15 campaigns total; the rest are the client's own history

## PRODUCTION BLOCKERS - BOTH DELIBERATE

1. **The copy has not passed a human read.**
   `docs/LEADS-ARE-BLOCKED-2026-09-14.md`. Copy that passes every automated
   gate fails a person, and the operator's hand-written fallbacks beat
   everything the model produced on both channels. `pushable` is retired as
   the promotion criterion.
2. **`heyreach.add_leads` is not in `providerwrites.SUPPORTED`.** Six routes
   are enabled; adding leads is not one. Enabling it is an operator decision.

Neither may be removed by an engineer acting alone. Bulk-approving to raise a
count remains the most damaging action available.

## WHAT CHANGED THIS SESSION

- Durability policy in CLAUDE.md and QWEN.md; `scripts/durable_state.py`
  generating `LEDGER.json` and a PII-safe `QUEUE-MANIFEST.json`.
- `scripts/provider_truth.py` and `scripts/sender_capacity.py` - provider
  truth, committed, regenerable.
- `docs/PRODUCTION-SCALE-POLICY.md` - campaigns are cohorts, ~50 leads,
  signal-based grouping, consolidation over proliferation.
- Three environment documents corrected after being found asserting the
  opposite of the truth: the queue README (said qwen was not installed while
  eight workers ran against it), `src/providerwrites.py` (said SUPPORTED was
  empty while six routes were live), and QWEN.md's dispatch rule.
- A PII leak Claude introduced and scrubbed: the sender's real name in
  `docs/state/PROVIDER-CAMPAIGNS.json`, pushed at `abae39b`, scrubbed at
  `ca53cb5`. Still in history; a rewrite is an operator decision.

## THE DISPATCH DEFECT, AND THE FIX

QWEN.md said "take the task Claude named, OR the highest-priority file in
TODO" and "take the next task". Six of eight workers self-selected the SAME
task and four produced the same answer; two more converged on another. Five
workers wasted and TASK-089 went unstarted.

Fixed in `55e56c8`: a named task is the ONLY task, claimed by moving it to
RUNNING as the first action, and a finished worker STOPS. Round 7 took
correctly.

## QUEUE

    TODO     088, 089, 090, 091, 092, 093, 096, 097
    REVIEW   059, 094, 095      <- results on several branches each
    DONE     84

Round-7 assignment: worker->089, 2->096, 3->097, 4->090, 5->093, 6->092,
7->091, 8->088.

## NEXT ACTIONS, IN ORDER

1. **Review TASK-095 and land ONE worker's fix**, not four. The hygiene guard
   is still red on master and a red PII guard is indistinguishable from an
   absent one - which is how the last leak survived, and how Claude's own
   leak landed in the noise this morning.
2. **TASK-089** - LinkedIn arms still all open and close with a question.
   This is the open half of TASK-087 and it gates the variant requirement.
3. **TASK-096** - whether this estate supports a 50-lead cohort at all. 92
   contacts on not-dropped records says the honest answer may be "one cohort,
   and not fifty".
4. Only after a human read passes: approve per step, then leads.

## RULES THAT MUST NOT BE BROKEN

Do not bulk-approve to raise `pushable`. Do not re-run the HeyReach write.
Do not widen any gate. Do not raise a sender limit for volume. Do not quote
8.49% - unreproduced. Do not quote any open rate - `open_tracking` is False
estate-wide. Do not count an UNKNOWN as negative. Do not read a test verdict
through a pipe. Do not trust a Qwen "tests pass" without running the
neighbours. Do not merge a worker branch wholesale - take named files. Do not
believe a document about the environment without checking it; three were
wrong this session.
