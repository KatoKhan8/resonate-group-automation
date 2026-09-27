PRIORITY: READ FIRST

# PRODUCTION HANDOFF — 2026-09-27/28 night

**Read this, then `docs/OPERATING-MODE.md`.** Supersedes the 2026-09-27 afternoon
handoff on everything it covers.

**Nothing was sent. No campaign was activated, resumed, paused, enrolled or
attached. No provider-changing test ran. Provider writes = 0.** Freeze stands.
487, 489 and 493 untouched and unchanged, verified before and after every step
that could have touched them.

**`sending.live` is `off` for `productive`** — the killswitch is ENGAGED. Three
independent protections now stand: the freeze, the killswitch, and review
approval.

## 0. THE ONE THING TO KNOW BEFORE ACTING

**Derive every state claim. This file is a snapshot and goes stale by design.**

    git fetch origin && git rev-parse master origin/master
    py -3 scripts/claim_task.py --status          # claims, ready depth, queue
    py -3 -c "from src import killswitch as k; print(k.workspace_state('productive'))"

Master moved **twelve times in six hours** tonight. Any SHA in prose here is
historical the moment it is written.

## 1. MASTER SHA

    origin/master   c0e47464        (local == origin, verified 2026-09-28 00:05)

## 2. WHAT LANDED TONIGHT

**`TASK-426` — MERGED. The single highest-value fix in the repo.**
`bisonfactory.stage()` passed ONE of `sequencegate.check`'s five inputs since
`6fa49014` (2026-09-26 15:27), so it could not succeed for ANY input. It failed
CLOSED — nothing reached a provider — but no campaign could be staged.
Acceptance reproduced independently: `tests/test_lead_writes_respect_the_killswitch`
went **2 failures + 3 errors → 5/5**. Staging works for the first time since
09-26, and **the killswitch is provably reachable on the EmailBison path**.
Merged on Claude's own verification PLUS a second Claude subagent's adversarial
review (UPHELD / MERGE) — GLM had not returned, and **a timeout is not a PASS**.

**`CLIENT_SUPPLIED` provenance — MERGED. The pack path landed 09-27 night; the
`src/claims.py` half landed 09-28 on operator decision B. Read section 4 for what
B deliberately over-refuses, because it is temporary and it is not free.**

**Launch blocker 5 — CLOSED.** `TASK-330`: grounding binds a claim to the pack
SENTENCE, not a token anywhere in the pack. "raised 50M in 2019" can no longer
launder "grew revenue by 50M last quarter".

**The killswitch scope was PROVED before it was engaged**, because "it blocks our
writes" and "it stops the estate" are different claims:
`tests/test_sending_live_off_blocks_only_our_new_writes.py`, 6/6, provider
transport booby-trapped so a refusal arriving after a network call FAILS the test
instead of passing quietly. Mutation performed on the source, three tests failed
for the intended reasons, restored and verified byte-identical. **It is a START
control. It cannot stop a campaign already running at the provider — turning it
off is NOT a pause and must never be reported as one.**

**~40 integrated results** across two integration passes, with four saves worth
the whole exercise: a branch that would have reverted provider truth by a day;
`TASK-344`'s consumer audit, which certified the LIVE `sequencegate` as
DISCONNECTED and would have committed that as a test; five parallel review
renderers against master's one; and a self-caught regression that was REVERTED
rather than patched on the reply-safety path.

## 3. WHERE THE CRITICAL PATH ACTUALLY IS

    TASK-426  MERGED on master.
    TASK-364  RUNNING (phase 2). Phase 1 pushed:
              worktree-agent-abf3e260cec92585d, head 6a307457 at last check.
              Phase 1 built src/sequenceplan.py + 11 tests WITHOUT touching
              either factory, deliberately, to avoid colliding with TASK-426.
              Phase 2 = wiring both factories to read only the plan.
              ITS FINDING: the HeyReach graph's delays come from a MODULE
              CONSTANT, so a cadence change cannot move the graph at all today.
    TASK-447  BRIEF WRITTEN, NOT DISPATCHED — docs/BRIEF-dry-run-executes-the-
              safety-path.md. Dispatch the moment 364 merges (same file).
    TASK-400  DONE ON BRANCH, NOT MERGED. task400-rework3, head 848a0832.
              51/51 in tests/test_generate.py, six mutations each verified.
              GLM verification dispatched against 848a0832 at 23:57.
              *** ITS BASE IS 5c356b7d, NOT AN ANCESTOR OF MASTER. It must be
              REBASED onto master and RE-MEASURED before merge. Its suite
              numbers (258 -> 192 names) are against its own broken base and are
              NOT comparable to master's 128. It also touches
              src/sequenceplan.py, which TASK-364 owns — so 364 merges FIRST.
    TASK-425  NOT STARTED. Acceptance criteria FROZEN in OPERATING-MODE.
              Blocked on criterion 3 by the dry-run defect (TASK-447).

**Merge order is not a preference: 364 → 447 (dry run) → 400 rebased → 425.**

## 4. THE OPERATOR DECISION THAT IS ONLY HALF IN FORCE

`CLIENT_SUPPLIED` is merged on the **pack path**. `packfacts.pack_for` no longer
folds client-CSV facts into the claim licence; they come back separately with
`verification: CLIENT_SUPPLIED`, the source file AND the row.

**`src/claims.py` IS A SECOND, INDEPENDENT CLAIM GATE AND IT STILL LICENSES A
CSV FIGURE.** Reproduced directly, twice:

    "You have 4000 employees."  + company_facts{headcount: 4000}  -> NO objection
    "You have 4000 employees."  with that fact removed  -> "the figure 4000
                                   appears in no stored fact"

Six live callers. **ANSWERED AND NOW FIXED. The operator chose B on 2026-09-28**
(A: add per-fact provenance, a day; B: block the six keys now, an hour). The two
claim gates now license from the same narrower list: `claims.support_text` skips
`packfacts.INGEST_FACT_KEYS`, taken from `packfacts` rather than retyped so the
two cannot drift. Proof, provider writes 0:
`tests/test_a_client_supplied_figure_licenses_no_claim_in_either_gate.py` — the
figure is refused through `eligibility.decide` AND through `bisonfactory.stage`,
refused IDENTICALLY once the client's value is removed, still decisive for
`icp.score` / `segments.classify` / `qualify.company` / `qualify.dossier`, and a
control in which the same figure on the account's own page reaches `eligible`
and stages one lead.

**B IS DELIBERATELY BLUNTER THAN CORRECT AND IS TEMPORARY.** `company_facts`
carries no per-key provenance, so two of the six keys — `headcount` (written by
`headcount.observe` from the ContactOut people-count and `blitz.company`) and
`industry` (written by `enrich`'s merge of `contactout.company_info`) — can hold
a legitimately provider-sourced value that B refuses anyway. That is the accepted
cost of failing closed. **The real fix is fact-level provenance, `TASK-462`, and
it is required POST-SLICE work — do not build it during the slice.** Read the
DECISION B section of `docs/OPERATING-MODE.md` before describing this as the
final data architecture, because it is not.

## 5. THE SUITE — 128 NAMES, NOT 197. DO NOT REGENERATE THE BASELINE.

Three parties measured the suite tonight and reported **126, 128 and 197**
distinct failing names for essentially the same tree. One concluded the standing
baseline "under-reports master by 75 names" and that somebody must regenerate it.
**That conclusion is wrong and acting on it would repeat the `TASK-372` mistake
the operator rejected this morning.**

Measured with `scripts/suite_baseline.py --measure`, the same tool and harness
that produced the committed baseline, at `0a4c9317`: **128 distinct failing names
(full), 120 (standalone), 8 order-dependent, 0 only-standalone.** The 197 is not
reproducible with this tool. **Two harnesses exist here and are NOT comparable** —
one process via `tests.offline` versus each module in its own process.

And the count was still the wrong question: 128 against a 128-name baseline,
with **7 new and 7 cleared**. Full diagnosis in
`docs/SUITE-TRUTH-2026-09-27-NIGHT.md`. Four of the seven are **a test
contradicting a recorded operator decision** — including
`test_an_offer_cannot_be_invented`, which asserts that NO offer is approved and
now fails because the operator approved Offers A and B. Two are `productive.io`
in tracked files, which is **not a PII leak** — it is the client's own domain and
the approved CTA. Three are order-dependent. `TASK-448` and `TASK-449`.

**The baseline is short by 4 names, not 75. It was deliberately NOT regenerated
tonight**: changing a standing reference point during a critical-path night is
how a regression becomes invisible.

## 6. WHAT TASK-400 FOUND, WHICH IS BIGGER THAN TASK-400

Reported by its implementer and **not yet independently verified** — treat as a
claim until GLM or a reviewer confirms it:

**Every lead the pipeline has ever produced was in fact REFUSED by copylint, for
`empty_sentence`**, because `em2`/`em4` were given an empty subject and the blank
line that leaves is "a variable rendered to nothing". `copylint.check_batch` was
computed, stored on the result, and **read by nothing**. That is this project's
signature defect — a thing computed correctly that nothing downstream consumes.

It also reports: the cadence was keyed by **email address** instead of
`identity.contact_key`, so copy went where nothing reads it; `run()` had no
`store.transaction`, so the pipeline wrote to a dict that was dropped; and a
dry-run artifact was **APPROVABLE**.

## 7. WORKFORCE AND THE QUEUE

    Qwen        12 workers configured; 4-5 holding claims at any moment tonight
    ready depth 18 (refilled twice: 0 -> 16, then 6 -> 18)
    GLM         glm_verify_branch.py is THE dispatcher (shipped tonight);
                one run in flight against task400-rework3 @ 848a0832
    queue       ~140 enumerated; ~40 integrated across two passes

**THE COUNTER CANNOT GO DOWN.** `claim_task.py --status`'s "awaiting integration"
counts *branches carrying a result*, and merging leaves the branch alone. **Use
it to enumerate, NEVER as a burn-down.**

**READY DEPTH 0 WITH A DEEP TODO IS NORMAL AND MEANS SOMETHING SPECIFIC.** 133
task files sat in TODO with a ready depth of zero, because nearly every one
already had a finished result on a branch. That is not an empty backlog — it is
the integration bottleneck wearing the costume of idle capacity. Refill from
REAL work: verification of finished results, the ICP audit, `TASK-423`,
`TASK-424`, the workforce report. **Never invented work.**

**A TASK FILE IN `docs/qwen-tasks/TODO/` IS CLAIMABLE BY ANY WORKER.**
`claim_task.py` has NO model routing and NO "CLAUDE ONLY" filter — verified by
reading it. A comment naming an owner is not an access control. Critical-path
briefs therefore live in `docs/`, not in `TODO/`.

## 8. OPEN OPERATOR DECISIONS

    ISSUE-048   ANSWERED 2026-09-28: the operator chose B. Implemented on both
                claim paths; see section 4. TASK-462 (fact-level provenance) is
                the required post-slice follow-up and is NOT slice work.
    491-500     TASK-430 (claimed) is measuring how many of 786 contacts would
                NOT pass the current ICP gate. THE DECISION ABOUT THOSE NINE
                CAMPAIGNS IS THE OPERATOR'S, after the numbers exist. A verdict
                recorded today does NOT make a past send retroactively approved.

## 9. TWO NEW BLOCKERS SURFACED BY WORKING GATES

Both are **pre-existing problems that became visible** once gates could run.
Neither is a regression, and neither is fixed by relaxing anything.

1. **786 sendable contacts in 491-500 belong to companies with NO ICP verdict.**
   The working gate refuses them — correct under "Company first". **491-498 have
   already SENT.** `TASK-430` is sizing it.
2. **`TASK-271` integrated a compliance gate on the send path that "refuses every
   email cadence today"** (its own commit message). Read it before TASK-425:
   it may be a third thing standing between the slice and a green dry run.

## 10. WHAT THIS SESSION GOT WRONG

1. **Reported the cadence mismatch as blocking TASK-425.** It does not. Measured:
   a NEW campaign gets the canonical five-plus-five; the 60 unstageable campaigns
   are stale STORED rows. **I read the reason off a refusal message — a refusal
   names the gate that fired, not why it fired.** Corrected in the file and in
   `#resonate-os`.
2. **First baseline diff reported "128 new and 128 cleared"** — compared the
   baseline's `FAIL `/`ERROR `-prefixed strings against bare test names. A diff is
   only evidence once both sides are shaped the same way.
3. **Reset a worktree while its own suite measurement was running in it**,
   invalidating two hours of measurement. Restarted and left alone.
4. **Wrote a critical-path brief into `docs/qwen-tasks/TODO/`** with "CLAUDE ONLY"
   at the top, then discovered no such filter exists. A Qwen worker would have
   taken it at the next sweep.
5. **Lost a phrase from a merge commit message to shell command substitution** —
   backticks inside `-m`. Amended. CLAUDE.md's heredoc rule exists for this.

## 11. THE FIRST THREE ACTIONS FOR THE NEXT SESSION

1. **Check whether `TASK-364` phase 2 finished** (`worktree-agent-abf3e260cec92585d`).
   Verify against its head SHA, merge, then **dispatch
   `docs/BRIEF-dry-run-executes-the-safety-path.md` immediately** — it is the
   blocker for TASK-425 criterion 3 and it is in the same file as 364.
2. **Rebase `task400-rework3` (848a0832) onto master, RE-MEASURE the suite by
   NAME, then merge.** Its own numbers are against a broken base. Read the GLM
   verdict if it returned; a timeout is not a PASS.
3. **Then TASK-425**, criteria frozen, provider writes 0, and **STOP** — post the
   artifact to `#resonate-os` and start no ten-account run.
