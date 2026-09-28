PRIORITY: READ FIRST

# HANDOFF — 2026-09-28 night — MINIMUM-CLAUDE MODE

**Supersedes `docs/PRODUCTION-HANDOFF-2026-09-28-EVENING.md`.** Read this, then
`docs/OPERATING-MODE.md`.

**Operator put this session into MINIMUM-CLAUDE MODE: Claude's weekly allowance
is nearly exhausted.** Claude's only remaining jobs are **final merge decisions
on GLM-verified work, operator decisions in `#resonate-os`, and this handoff.**
No implementation, no exploration, no reviews, no suite runs by Claude.

**NOTHING IS SENDING ON EITHER CHANNEL.** Email 487/489/493 paused by the
operator; all 34 RESONATE LinkedIn campaigns paused by approved write and read
back. `sending.live` is off for productive. Provider writes today: the 34
approved LinkedIn pauses and nothing else.

## 1. VERIFIED SHAs — `git rev-parse` after fetch, 2026-09-28 night

    origin/master                          3bc00f2d   (a3948cd4 after briefs)

    origin/task-p0b-copy-engine-pareto     556593a0   REWORK - see §4
    origin/review-p0b-round2               78e908e2   the blocking review
    origin/review-p0b-cdac64f4             d306bead   round-1 review
    origin/task-p0c-causal-fixture         2f2670dd   real account, matrix NOT run
    origin/task-p0a-signature-chain        d93b0674   criterion 2 BLOCKED
    origin/task-send-ledger-ingest         dc43ab6b   APPROVED, awaiting review
    origin/task-permanent-operator-exclusion f73cb9b6 complete, unmerged
    origin/task-runtime-approval-hash-probe  1330815c complete
    origin/task-p0d-production-caller      01dd7b78   complete
    origin/task-425-one-account-dry-run    2d54e274   MERGED to master

**`556593a0` IS NOW PUSHED AND VERIFIED** (`142ca537..556593a0`, both refs
identical). It was briefly reported as pushed while it was not: its agent ran
one verification, made two further commits, and re-asserted the **stale** check
rather than running a new one. **The review at `78e908e2` was written against
`142ca537`; the two differ only in one test file and docs — the `src/` tree is
identical (`319e22e5`), so every finding in that review holds at `556593a0`.**

**⚠ The review's own SHA caveat, kept: the real merge base is `d0e95d20`, not
the master head.** Diffing against the wrong base attributes master's own
commits to the branch.

**⚠ The local ref `task-425-one-account-dry-run` is pinned stale at `3e75b563`**
by an abandoned worktree and `git branch -f` refuses. `origin/` is the authority.

## 2. THE CRITICAL PATH

    P0-B rework (TASK-550..553)  ->  signature composition (TASK-554)
      ->  10-account zero-write  ->  operator review  ->  email canary

**Qwen implements from the briefs. GLM verifies every result against the exact
branch head SHA: PASS / BLOCK / NEEDS_EVIDENCE. A BLOCK goes straight back to
Qwen with the evidence, without Claude in between.**

## 3. THE FIVE BRIEFS — ready in `docs/qwen-tasks/TODO/`

    TASK-550  P0  the figure gate matches a 4-char prefix      BLOCKING
    TASK-551  P0  a possessive is still an assertion
    TASK-552  P0  a rung is a question, not an assertion
    TASK-553  P0  the P.S. must reach the person
    TASK-554  P1  compose the signature into the copy   DEPENDS: TASK-553

Each carries exact files, acceptance, **negative controls, a near-miss control
and a mandatory mutation**, and a one-task-per-file rule so no two workers
collide. TASK-550 owns `src/generate.py`; 551 owns `src/claims.py`; 552 owns
`copystages.py` + the offers yaml; 553 owns the rendering path; 554 follows 553.

## 4. P0-B — DO NOT MERGE `142ca537`

Round 1 was rejected for four defects; **all four are genuinely closed** and the
reviewer proved it (B4 fires on the production path under a targeted mutation;
B3 refuses on all five LinkedIn keys; B2/F1 15 of 15; nine mutations killed with
CRLF anchors asserted).

**One NEW blocking defect.** `_invented_quantities` builds its support set as
`{w[:4] for w in ...}` — **a four-character prefix, not a stem**. `threat` or
`threshold` licenses "three times"; `several` licenses "seven times"; `trip`
licenses "tripled". **Six of eight attacks bypass, on 134 of 394 records with a
research pack (34%), and nothing downstream catches it** — `claims.check`,
`copylint.untraceable`, `copylint.check_batch` and
`heyreachfactory.unsupported_claims` all report clean. Round 1 over-refused,
which is safe; round 2 under-refuses on a third of the estate, which is not.
**That is TASK-550.**

Non-blocking, same family: `_NOT_A_QUANTITY`'s `half\\s+the|half\\s+of` exempts
real magnitude claims — "half the cost of your current stack" passes while
"50% of" refuses.

**Measured effect, not rounded up:** the contact under test gets copy through
**2 of 5 runs (40%)** — the baseline rate, against a materially higher bar (10
required steps, the gate read natively, the figure gate on both channels).
`step_objectives` fell 8/23 → ~3%; **the claim family is now the dominant
blocker at ~37%**. Nobody should call this "reliably gets copy through".

## 5. TASK-425 — the four criteria

    1 causal matrix    BLOCKED     copy engine, not the causal machinery
    2 signature chain  BLOCKED     see §6
    3 offer sequencing PASS
    4 claim audit      UNPROVEN    the verifier tests FIELD LABELS, not values

**Criterion 4's verifier is confirmed broken**, line verified: it asks whether
the field label appears in rendered markdown and **never reads a value**. That
is how it certified nine messages whose "exact claim licensed" was empty.

## 6. CRITERION 2 — the signature exists and reaches nothing

The operator added signatures to all 222 productive inboxes. That was real and
it did not unblock anything:

    `email_signature` occurs ONCE in all of src/ - inside a docstring
    `src/sendersignature.py` has ZERO production callers
    0 of 99 queued messages carry their mailbox's signature, including all 37
      already sent - so the provider does not append one either

Chain: owner 159/225, identity 145, **signature present 145**, **rendered 0**,
**projection 0**. Operator chose option **A**: we compose it. That is TASK-554.

## 7. THE OFFER A CORRIDOR — and the operator's ruling

**0 of 93 accounts with an admitted pack can license rungs 1 and 3 of Offer A.**
Rung 1 needs "margin" AND "visibility"; rung 3 needs "resource" AND "margin".
18 packs contain the words; none clears the gate.

**Operator's ruling: the ladder design is wrong, not the research.** No company
publishes its margin or resourcing. The rung topic stays; the copy becomes a
question or a Productive-capability statement, never an assertion about the
prospect. **TASK-552.**

**And the hole that made the corridor survivable the wrong way:** a bare
second-person possessive matches none of `claims.SECOND_PERSON_ASSERTIONS`, so
*"Your margin visibility slips between projects"* ships while *"You have margin
visibility…"* is refused — **the same assertion**. P0-C found it and
deliberately did NOT exploit it. **TASK-551.**

## 8. THE SEND LEDGER — approved, not applied

`leadobserve.confirm_email_touches` was already correct and had **zero
production callers**. The provider confirms **912 sends** across our campaigns
against **one** recorded touch in 1,582 records; 487 was recorded as 0 sent and
had sent 6. Operator **APPROVED** ingesting after review.

### ⚠ REVIEW VERDICT: **DO NOT APPLY `dc43ab6b`.** Review at `a739d8c0`.

**The blocker is a live provider call from the test suite.**
`confirm_email_touches` now calls `email_step_ordinals` unconditionally, which
calls `bison.sequence_steps` — a **second** provider route on every call.
`tests/test_the_send_is_recorded_once_and_by_the_provider.py` patches
`scheduled_emails` but never `sequence_steps`, and its classes derive from
`QueueTest` rather than `ProviderTest`, so no transport is faked.

    without config/.env   15 ERRORs, visible
    WITH config/.env      they PASS while making a real HTTP GET to the live
                          EmailBison account on EVERY SUITE RUN

That second line is why this must not merge as it stands, and why master cannot
see it. **Master does not carry this code, so there is no active hazard today.**
Preferred fix per the review: `email_step_ordinals` returns `{}` on provider
failure, consistent with its own fail-closed design — that removes both faces.

Attribution is closed: of 19 new names, **15 are the branch**, 2 are
`productive.io` in master-era files, and 2 fail identically at the merge base.

**Everything else in the branch verified well:** provider writes 0 with an
interceptor fired deliberately, the 400-page cap **refuses rather than
truncates** (UNKNOWN, never zero), step resolution never clamped, both loss
guards run under the lock, and idempotency survived a reproduced mid-write
`PermissionError`.

**BEFORE ANY FUTURE APPLY** — the write is **~1,082 events, not ~850**; 24
production loops are running; `store.load()` takes no lock and every
transaction ends in `os.replace`, which is the exact mechanism that blinded
campaign 491 in run 1. **Stop the loops, hash the backup, and require
`complete: true` with an empty `blind` list.**

### A SAFETY GUARD THAT DOES NOT GUARD

`refuse_production_write` is **`ROOT`-relative, so it protects nothing when
called from a worktree** — confirmed by artifact. Every agent that "proved"
production safety by working on a copy was safe **because it used a copy, not
because the barrier would have stopped a mistake.** Not fixed; recorded.

**LinkedIn ingestion remains a separate, later task** — see below.

**LinkedIn is NOT covered.** `leadobserve.confirm_touches` exists with zero
production callers, and the approved branch contains a literal
`if provider != "emailbison": return {}`. **Required before any LinkedIn stage.**

## 9. LINKEDIN — paused, and one person needs an answer

All 34 paused, verified by an independent 121-of-121 walk; the workspace went
46 → 11 IN_PROGRESS, difference 35 = our 34 + one client campaign that moved on
its own (**not us**: 1,426 write-ledger rows, none names it).

**Nine accepted connections, eight of whom got no human reply.** One real
prospect reply — **StudioNorth, Senior Project Manager** — said **"no thank
you"** at 11:12 on 23-09 **and received another message from us at 11:19.**
Seven minutes after a refusal. The other "reply" is the operator's own test
identity. **A human owes her an answer; same-channel stop did not hold.**

## 10. WHAT CLAUDE MUST DECIDE WHEN CAPACITY RETURNS

1. **Merge P0-B** once TASK-550..553 land and GLM passes them against a named
   SHA. Two independent views, never one.
2. **Merge or reject** `task-permanent-operator-exclusion` (`f73cb9b6`),
   `task-send-ledger-ingest` (`dc43ab6b`), `task-p0c-causal-fixture`
   (`2f2670dd`), `task-p0a-signature-chain` (`d93b0674`),
   `task-runtime-approval-hash-probe` (`1330815c`),
   `task-p0d-production-caller` (`01dd7b78`).
3. **Apply the send ledger** to production after its review passes, then
   schedule it and prove one scheduled run.
4. **The 234 awaiting integration** — Qwen triage briefs TASK-538..545 exist;
   Claude decides integration, never Qwen.
5. **Regenerate the suite baseline** (TASK-549) — it is stale on master and has
   now cost two agents an hour each.

## 11. STILL OPEN WITH THE OPERATOR

    credential rotation      PARKED by the operator, 10 names + 2 passwords
    cross-channel validation one 🔴 decision ready, design at 20ee4648
    the ~609 MB host plaintext at /var/backups/prod-work
    the old age private key, on the laptop rather than offline
    the ~30k supply sample   brief written, needs one APPROVED
    the 9 LinkedIn people    a human must answer them

## 12. WHAT THIS SESSION GOT WRONG

1. **Reported a bounded "66 affected modules, zero new failures" twice** — the
   slice that produced it selected modules by grepping imports and missed a
   two-line `from src import (...)`, so it could not see three real failures.
   An instrument that cannot see the failing case returns green.
2. **A transport signature bug produced 34 UNVERIFIED provider writes.** The
   write layer refused to guess and forbade a retry; provider truth settled it
   at zero. Correct outcome, avoidable cause.
3. **Told the operator the P.S. renders.** It does not, anywhere.
4. **Claimed `age` was not installed** from a check that misses the WinGet shim.
5. **Framed the backup coverage question as prodwork-vs-prodwork**, which would
   have destroyed the estate's only off-host backup.
6. **Left Qwen and GLM idle for hours** while focused on the critical path.
