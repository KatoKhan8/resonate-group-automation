# MERGE DECISIONS — 2026-09-28 late — the GLM round on the artifact critical path

**Claude, orchestration/merge authority. Base `origin/master` `143f132f`
(local == remote, tree clean).** `sending.live` false, freeze active, provider
writes 0. Nothing in this round touched a provider.

## 0. THE ONE-LINE ANSWER

**Four results verified, four FAIL, NOTHING MERGED.** The cause is not four
independent code defects: it is that the results live on **shared long-lived
worker branches carrying tens of tasks each**, so no single task is
attributable, verifiable or mergeable. GLM refused correctly.

## 1. VERDICTS — GLM, against exact SHAs

    TASK-901  task-901-figure-gate-fix  43d4ae2b  FAIL   72% of insertions out of scope
    TASK-560  qwen-worker-r9            afef8fb2  FAIL   6 new failures, no attributable caller
    TASK-903  qwen-worker-3-r9          b9452001  FAIL   9 new failures
    TASK-564  qwen-worker-r9            afef8fb2  FAIL   collateral - same branch as 560

Reports: `docs/glm-reviews/branch-TASK-{901,560,903,564}.md`.

## 2. THE STRUCTURAL FINDING — why all four failed

    branch                  distinct TASK ids   commits ahead   src/ files
    qwen-worker-r9          45                  184             7
    qwen-worker-3-r9        69                  202             2

`qwen-worker-r9` carries TASK-553, 558, **560**, **564** and **902** among 45
ids. GLM's own words on 560: *"no hunk is attributable to 560 from this
diffstat, so I cannot cite a call site."* That is a true statement about the
branch, not a gap in the review.

**This is the mechanism behind the 237 tasks "awaiting integration."** The
integration queue is not jammed on review capacity; it is jammed because
results are entangled on mega-branches that cannot be merged one task at a
time.

**The `src/` surface is small (7 and 2 files), so extraction is feasible — but
the hunks inside those files serve ~45 tasks, so extraction is not free.**

## 3. VERDICT-BY-VERDICT, and what is actually true

### TASK-560 — the P.S. — CRITICAL PATH, REWORK
Two real defects, separated from the branch noise:

1. **The branch adds the P.S. tests TWICE**, under two ids:
   `tests/test_task553_ps_must_reach_the_person.py` (340 lines, **3 tests
   FAILING**) and `tests/test_task560_ps_reaches_the_person.py` (324 lines,
   claimed passing). Two modules encode two different contracts for one
   feature and one of them is red. Neither module exists on master.
2. **Two REAL regressions**, confirmed independently rather than taken from
   GLM: `test_the_research_pack_has_one_shape.AbsenceIsNotAnError` —
   `test_a_record_with_no_research_still_produces_copy` and
   `test_an_empty_list_is_the_same_as_absent`. **Both PASS on master
   `143f132f`** and fail on the branch, so they are regressions, not baseline
   drift. A record with no research must still produce copy; the branch breaks
   that.

### TASK-564 — the provider write surface — NOT INVALIDATED, BUT UNMERGEABLE
564 is a **read-only audit**; its deliverable is a findings table and it
changed no production code. Its FAIL is **collateral**: it shares `afef8fb2`
with 560, so it inherits 560's six failures. **The audit content is not
refuted by those failures** — but it cannot be merged off that branch as it
stands. Its substantive finding is worth carrying forward on its own:

> **Finding 1 of 564 REFUTED the handoff.** `refuse_unauthorized_write` does
> **not** use `ROOT`. It uses `_prospect_facing_hosts` (import-time),
> a `_write_scopes` ContextVar, and the `RESONATE_PROVIDER_WRITES` env var.
> **The real bypass is the env var, not `ROOT`.** The
> NIGHT-MINIMUM-CLAUDE handoff §8's "safety guard that does not guard
> (ROOT-relative)" is therefore **wrong about the mechanism** while right that
> a bypass exists. Correct the mechanism before anyone "fixes" `ROOT`.

### TASK-903 — rungs as questions — REWORK
9 new failures in `test_generate` and `test_set_regeneration`. One of the named
`test_set_regeneration` failures is **pre-existing on master** and must not be
charged to the branch (see §4); the `test_generate` failures
(`test_em4_is_stored_when_all_five_pass_lint`,
`test_an_existing_draft_is_not_regenerated`) are real — `test_generate` passes
on master.

**903 also implemented TASK-902's deliverable** — it extended
`claims.asserts_about_them` with the possessive branch — crossing the
one-task-per-file rule. 902 additionally has
`tests/test_a_possessive_is_still_an_assertion.py` on `qwen-worker-r9`. **902's
work exists twice, on two branches, and 902's own claim is still held.**

### TASK-901 — the figure gate — REWORK
Not a correctness refutation: GLM could not find a TASK-901 test outcome
because **~11,616 of 16,166 insertions (72%) are TASK-425/copy-engine work**
that does not answer to 901. The fix may well be right; **the branch makes it
unprovable.** Isolate it.

## 4. A PRE-EXISTING MASTER FAILURE, MEASURED

Run on a clean worktree of `143f132f`, modules
`test_the_research_pack_has_one_shape`, `test_generate`,
`test_set_regeneration`: **84 tests, 1 failure.**

    test_set_regeneration.SetRegenerationTransactionTest
      .test_successful_regeneration_replaces_all_notes    AssertionError: 5 != 6

**Master is not green.** The verifier's baseline is
`docs/state/SUITE-BASELINE-2026-09-26.txt`, **two days stale** (TASK-549), so
this failure is reported as "new" against branches that did not cause it. That
is the instrument error TASK-549 exists to fix and it has now cost three
rounds, not two.

## 5. TOOLING BLOCKER FOUND AND WORKED AROUND

`scripts/glm_verify_branch.py` decodes subprocess output with the **locale
codec** (three `subprocess.run(..., text=True)` sites, lines ~70, ~314, ~349).
On this host that is cp1250; worker output contains byte `0x90`, which kills
the reader thread with `UnicodeDecodeError` and the script produces **no
verdict at all** — a silent blind gate, not a visible failure.

**Worked around with zero code change: `PYTHONUTF8=1`.** All four
verifications above ran under it. The durable 3-line fix is
`encoding="utf-8", errors="replace"` at those three sites, so a fresh clone on
another host is not silently blind. **Filed, not applied — no unrequested
code change on a verification path.**

## 6. WORKTREES HAVE NO `config/.env`

A dry run inside a worktree reported *"REFUSED: --spend includes the generate
stage and no model is configured: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
unset."* **That is worktree isolation, not a missing credential.** In the main
checkout `scripts/credential_health.py --verify` reports `LLM_BASE_URL`,
`LLM_API_KEY` and `LLM_MODEL` all `CREDENTIAL_CONFIGURED_UNVERIFIED`. **The
model is configured and the artifact is not blocked on credentials.** Recorded
because an ad-hoc `os.environ` check reported UNSET and was wrong — the
registry is the authority, exactly as `CLAUDE.md` says.

## 7. MERGE HAZARD — `task-p0c-causal-fixture`, DO NOT MERGE

`origin/task-p0c-causal-fixture` `2f2670dd` is based on `d0e95d20`. Its diff
against master **deletes** `docs/PRODUCTION-HANDOFF-2026-09-28-NIGHT-MINIMUM-CLAUDE.md`,
`docs/OPERATING-MODE.md` (−130) and **nine briefs on the critical path** —
TASK-548, 549, 560, 564, 565, 901, 902, 903, 904, 905, 906 — and rewrites
`docs/state/TASK-REGISTRY.json` by −195 lines.

**Cherry-pick only. Never merge.** This is the TASK-229 failure mode, where a
merge would have deleted 12,487 lines.

## 8. THE ARTIFACT — what it is blocked on, stated exactly

The operator's milestone is ONE REAL ACCOUNT with the actual final messages.

**The real account exists and is not a fixture: Brand IQ, `brandiq.com`**,
record `brandiq-com`, claim `ISO 9001:2015` sourced to
`https://brandiq.com/about`, 1 sendable contact, persona `economic_buyer`;
operator chose it 2026-09-28 (`docs/P0C-CAUSAL-FIXTURE-2026-09-28.md`).
Nothing about the contact is in git — it resolves at runtime from `work/`,
which is correct.

**`docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md` (7,092 lines) cannot be that
artifact.** It is the right shape and the wrong content: the account is the
**invented fixture** "Brightmoor Studio" on the reserved domain
`brightmoor.test`, and measured against the operator's required fields it
contains **P.S. 0, opt-out 0, approval hash 0, Offer A/B named 0, LinkedIn
URL 0.**

**Those four absences are exactly TASK-560 / 904 / 905 / 906.** The chain is
serial by construction — each brief says "same rendering path, do not start
until the previous lands" — and **904/905/906 do not exist in any form on any
branch.**

### The ~30k discrepancy, stated rather than buried
The milestone says "from the approved ~30k source". **P0-C's own result says
that is NOT MET:** Brand IQ came from a 50-record pilot batch. The large
sources hold **0 qualified records because nothing was ever run on them**, not
because they were searched and found wanting — 24k staging track 0/554,
batch-1+2 0/477, intake 0/250; all 113 qualified records in the estate come
from 300 pilot records. Qualifying the pool needs the operator's `APPROVED`
and credit spend and is a separate unstarted task. **TASK-904's brief is
written against "the Brand IQ slice", so the chain already targets Brand IQ.**

## 9. DECISIONS

1. **MERGE NOTHING this round.** Four FAIL, and the shared-branch structure
   means a pass could not have been attributed anyway.
2. **The rendering chain is re-implemented on clean single-task branches off
   `143f132f`**, not extracted from `qwen-worker-r9`. Rationale: the chain's
   four tasks touch the same five files (`render.py`, `bisonfactory.py`,
   `sequenceplan.py`, `copystages.py`, `approve.py`), which is *why* they are
   serialised; untangling those hunks from 45 other tasks is slower and less
   verifiable than implementing a crisp 6-point acceptance clean.
3. **TASK-564's audit finding is carried forward in §3 of this document** so
   the ROOT-vs-env-var correction is not lost with its branch.
4. **TASK-902 is not dispatched again.** Its work exists on two branches and
   its claim is still held. It is an integration decision, not new
   implementation.
5. **TASK-549 (baseline) is promoted**: it is now corrupting every verdict on
   the critical path. Master is not green and the verifier cannot tell a
   regression from a pre-existing failure without it.
6. **No new features, audits or architecture.** Everything above is either a
   verdict, a correction to a false statement in the handoff, or the smallest
   remediation the failed gate requires.

## 10. WHY THE POOL STALLED — 8 OF 12 WORKERS CANNOT BE DISPATCHED TO

Measured 2026-09-28 19:38 across all twelve worker worktrees:

    resonate-qwen-worker   qwen-worker-r9      dirty=13
    resonate-qwen-2        qwen-worker-2-r9    dirty=2
    resonate-qwen-3        qwen-worker-3-r9    dirty=0   <- used
    resonate-qwen-4        qwen-worker-4-r9    dirty=2
    resonate-qwen-5        qwen-worker-5-r9    dirty=0
    resonate-qwen-6        qwen-worker-6-r9    dirty=3
    resonate-qwen-7        qwen-worker-7-r9    dirty=2
    resonate-qwen-8        qwen-worker-8-r9    dirty=0
    resonate-qwen-9        qwen-worker-9-r9    dirty=2
    resonate-qwen-10       qwen-worker-10-r9   dirty=0
    resonate-qwen-11       qwen-worker-11-r9   dirty=3
    resonate-qwen-12       qwen-worker-12-r9   dirty=2

**A dirty worktree makes `git checkout -B <br> origin/master` fail, so the
dispatch lands on the OLD round branch and the 2026-09-26 guard aborts it.**
Observed exactly once before using a worker: dispatching TASK-560 to
`resonate-qwen-2` aborted with *"checkout landed on `f03c74fc`, expected
origin/master `180c274f`"* and released the claim. **The guard worked: no qwen
turn was spent on stale history.**

**This is a capacity loss, not a data-loss risk** — the guard aborts rather
than discarding, so the uncommitted content is not destroyed. But **two thirds
of the pool is unusable until each dirty worktree is triaged**, and the
uncommitted content is task-stage files (e.g. a modified
`REVIEW/TASK-397-*.md`, an untracked `RUNNING/TASK-309-*.md`) that may or may
not be a result. **Triage is per-worker and is NOT started here** (FOCUS
RULE): the critical path needed one clean worker and had four.

**This is also the second mechanism behind the 237-task integration jam.** The
first is mega-branches (§2); this is workers that cannot accept a new task at
all.

### Dispatch that worked, for the next session to copy

    POOL_ROUND=r10 bash scripts/pool_dispatch.sh resonate-qwen-3:TASK-560

**A fresh `POOL_ROUND` is what buys a clean single-task branch.** `branch_for`
maps worker -> `qwen-worker-<N>-$ROUND`, so every task a worker takes in one
round targets the same branch name — which is the structural reason
`qwen-worker-r9` accumulated 45 task ids. Verified after dispatch:
`resonate-qwen-3` HEAD = `qwen-worker-3-r10` = `180c274f` = `origin/master`.

## 11. THE ARTIFACT NEEDS ONE MORE THING, AND NOTHING HAD FLAGGED IT

**Measured 2026-09-28 20:1xZ. The rendering chain is NOT the last dependency.**

`scripts/task425_one_account_dry_run.py` is bound to `fixture.RECORD_ID`, and
**on master that fixture is the INVENTED account**:

    master  tests/task425fixture.py   RECORD_ID = "task425-brightmoor-studio"
                                      no `work/` read anywhere in the file

    origin/task-p0c-causal-fixture    RECORD_ID = "brandiq-com"
                                      reads work/queue.jsonl through store.,
                                      resolves the real record and its one
                                      sendable contact

**So even with 560 -> 907 -> 904 -> 905 -> 906 all merged, running the
generator on master today would produce the operator's artifact for a company
that does not exist.** The real-account capability is on `2f2670dd` and
**has never reached master.**

### The chain, corrected

    560 -> 907 -> 904 -> 905 -> 906 -> P0-C fixture reaches master -> artifact

### Why this is a cherry-pick and not a merge
§7 stands: merging `2f2670dd` deletes the current handoff, `OPERATING-MODE.md`
(−130) and nine critical-path briefs. **What the artifact actually needs is
narrow** — `tests/task425fixture.py` and `tests/fixtures/task425-evidence.json`
— but the branch also carries 7 modified `src/` files
(`generate.py` +469, `generate_campaign.py` +475, `bisonfactory.py`,
`campaignstrategy.py`, `copystages.py`, `offers.py`, `sequencegate.py`) which
are P0-B/P0-C copy-engine work, and the fixture may depend on them.

**Not attempted in this round.** It is a merge decision that needs its own
attributable diff, and doing it while the rendering chain is mid-flight on the
same `src/` files would recreate exactly the entanglement §2 is about. **It is
the last gate before the artifact and it should be sized before it is
started** — specifically: does the `brandiq-com` fixture resolve with ONLY the
two test files cherry-picked onto master, or does it require the copy-engine
changes too? That single question decides whether this is a 2-file pick or a
second P0-B merge.

**Operator impact, stated plainly: the artifact cannot show a real company
until this lands, regardless of how the rendering chain goes.**

## 12. TASK-560 REWORK 2 — REFUSED BY CLAUDE, AND THE ORDERING ERROR WAS MINE

**Branch `qwen-worker-3-r10` head `75b8c26a`. GLM: `NEEDS_CLAUDE` with ZERO
findings** — it could construct no defeat and said so, blocked by instrument
limits (no diff hunks, no repo listing, and **0 acceptance commands extracted,
because the rework sections Claude appended contained no runnable commands** —
that is a defect in the brief, not in the worker).

So the second independent view had to be Claude's. It found a regression.

### MEASURED, both sides

    branch  75b8c26a   tests.test_render_preview   29 tests, 2 FAILURES
    master  a0434a62   tests.test_render_preview   29 tests, OK

    FAIL TestEmailPreviewUsesTheProductionCodePath
           .test_email_preview_renders_through_bisonfactory_variables_for
    FAIL TestEmailPreviewUsesTheProductionCodePath
           .test_email_five_no_issues_for_clean_copy

**The worker's result block claims "no regressions". That claim is false.**

### THE MECHANISM — proven at runtime, not inferred

`scripts/render_preview._fixture_rec_email()` has five steps, **em1 through
em5, and NONE of them carries a `ps` field** — which is exactly what the whole
estate looks like today, because nothing produces a P.S. yet. Through the
production path:

    rendered subject_1  =  "A different angle on the numbers"      <- em2
    stored em1 subject  =  "Your project visibility gap at ..."    <- em1

**em1 was dropped.** Rework 2's guard does `continue` when a step in
`STEPS_REQUIRING_PS` has no `ps`, so **it silently removes every em1 and em3
in the estate.** The sequence loses its opener and its third email.

**A first probe of `_approved_copy` with synthetic steps was inconclusive** —
all three steps came back `missing` because the approval fingerprint guard
fired first, not the P.S. guard. Recorded because that is precisely the trap
CLAUDE.md names: confirm the intended guard fired and not a different one. The
proof above uses the real fixture through the real path instead.

### THE ORDERING ERROR, AND IT IS CLAUDE'S

Rework 2 did exactly what Claude's brief told it to do. **The brief was
wrong.** It ordered 560 to BLOCK a required-but-missing P.S. while TASK-907 —
the only thing that puts a `ps` on the step dict — did not exist. So:

    TASK-560 alone   drops every em1/em3, because no ps is ever produced
    TASK-907 alone   produces a ps that nothing reads

**Neither task is correct on its own. They are one atomic unit and must land
together.** Round 1 over-refused and was safe; this over-refuses on the live
path, which is not.

### DECISION

1. **Do NOT merge `75b8c26a`.** Not for a defect in the work — the bypass fix
   and `STEPS_REQUIRING_PS` are right and are kept.
2. **TASK-907 is dispatched onto the SAME branch `qwen-worker-3-r10`**, so the
   producer and the consumer form ONE attributable diff, verified once and
   merged once. This also removes a merge cycle from the critical path.
3. **The pair's acceptance is `test_render_preview` green with em1's subject
   rendering as em1's** — the regression above is the pair's real gate.
4. **Every future brief carries explicit acceptance COMMANDS**, because GLM
   extracts them and returned `NEEDS_CLAUDE` twice for their absence.

### A MIGRATION CONSEQUENCE TO FLAG BEFORE THE CANARY

Once the pair lands, **the guard will refuse every already-stored message that
has no P.S.** — all 99 queued, including the 37 already sent. That is arguably
correct, since the operator condemned exactly that copy on 2026-09-28 (*"old
copy, no signature, no opt-out route; the canary replaces them"*), but it means
**the existing estate must be regenerated, not just re-approved.** Nobody
should discover that during a canary.

### NON-BLOCKING, RECORDED SO IT DOES NOT MULTIPLY

`_append_ps` is defined **twice** — `src/bisonfactory.py:1639` and
`src/render.py:61` — with **byte-identical logic**, only the docstring
differing. No divergence today, so it is not a merge blocker. But TASK-906
will append a signature to the same two surfaces, and a third copy would make
"what the person receives" and "what the projection contains" drift on the
exact invariant this chain exists to guarantee. **TASK-906's brief now forbids
adding a third appender.**

## 13. THE 560+907 PAIR — MEASURED, AND THE MIGRATION COST IS ~1,946 NOT 99

**Branch `qwen-worker-3-r10` head `cab4f06b`, 8 commits ahead of `628e73c5`,
9 files, every one attributable to TASK-560 or TASK-907.**

### Claude's independent view — the pair's gate PASSES

    tests.test_render_preview                    29 tests  OK   <- the gate
    tests.test_task560_ps_reaches_the_person     14 tests  OK
    tests.test_the_research_pack_has_one_shape   19 tests  OK
    tests.test_approve                           43 tests  OK
    tests.test_generate                          51 tests  OK

`test_render_preview` was **2 failures with 560 alone** and is **29/29 with the
pair**. Through the real path, `subject_1` renders em1's subject again, and
per-step P.S. presence is `em1 True, em2 False, em3 True, em4 False,
em5 False` — **no fabricated P.S. on the steps that never had one.**

### The producer hop is real and minimal

`src/generate.py` **+8 lines**: `_candidate_steps` reads
`sequences.get("ps_" + source)` and sets `step["ps"]` only when truthy, so a
step with no P.S. gets **no key at all**. No hardcoded `em1`/`em3`.
**No import cycle** — `STEPS_REQUIRING_PS` stays in `bisonfactory`; the
producer carries whatever `sequences` has and the consumer decides what
absence means. That division is right.

`tests/test_task907_ps_producer_hop.py` exercises the **real**
`_candidate_steps` and asserts the P.S. **VALUE**, not a key or a field label —
the trap TASK-425's criterion-4 verifier fell into.

### A CAVEAT ON CLAUDE'S OWN GATE TEST — recorded rather than hidden

907 also edited `scripts/render_preview.py` (+24) to give the fixtures a `ps`
and recompute their approval fingerprints. **That makes Claude's first gate
probe partly circular**: it proved the pipeline renders a P.S. the *fixture*
supplied, not that generation produces one. The producer is proven instead by
`test_task907_ps_producer_hop` against the real function, and by reading the
8-line diff. The fixture edit is itself legitimate — those fixtures build
cadence steps directly, bypassing `_candidate_steps`, so they had to carry
`ps` and a recomputed fingerprint, and the fingerprint change is 560's
acceptance 3 proving itself.

### THE MIGRATION COST, MEASURED AGAINST PRODUCTION — read-only, counts only

    records with a cadence        1099
    email steps total             4066
    email steps carrying a P.S.      0     <- estate-wide, nothing produces one
    email steps with an approval  2949
    APPROVED em1/em3 with NO ps   1946     <- the new guard REFUSES all of these

**Earlier in this document and in the handoff the figure was "99 queued,
including the 37 already sent." That is wrong by an order of magnitude.** The
real blast radius is **1,946 approved steps across ~1,099 records.**

**This is not a reason to refuse the merge.** It is correct behaviour: the
operator condemned exactly this copy on 2026-09-28 (*"old copy, no signature,
no opt-out route; the canary replaces them"*), every campaign is paused and
`sending.live` is false, so nothing can act on a refusal. But:

1. **The estate must be REGENERATED, not re-approved.** Any count of
   "approved steps" drops by ~1,946 the moment this lands, and a process that
   reads that count without knowing why will look broken.
2. **The artifact's own account is affected.** The Brand IQ record must be
   regenerated so its em1/em3 carry a P.S., or the one-account artifact will
   render with those two steps refused. **That is now a step in producing the
   artifact, not an afterthought.**

## 14. THE AUTONOMOUS POOL IS STOPPED, AND HOW TO RESTART IT

**`scripts/pool_watchdog.sh loop` (pid 84532) and its `pool.sh sweep` children
were STOPPED by Claude at ~20:58Z.** Verified afterwards: zero processes match
`pool(_watchdog|\.sh)`.

### Why
The sweep grabs a task the instant it becomes ready, on **whatever master it
last fetched**. Because integrating each chain task is what makes the next one
ready, there is always a window, and it lost that race **three times**:

    TASK-904  dispatched on 910ff50e  - master BEFORE the 560+907 merge
    TASK-905  dispatched on c6da73a1  - master BEFORE the probe cherry-pick,
                                        so its own gate command could not run
    TASK-907  dispatched 3x in 11s to dirty worktrees, all aborted

Each was caught within ~2 minutes and killed, but each cost a dispatch cycle.
**The guard never failed** — it aborted or the base was simply behind; nothing
built on months-old history. The problem is throughput, not safety.

**The critical path is strictly serial** — `560+907 -> 904 -> 905 -> 906`, all
on the same rendering files — so exactly one task is ever runnable and the
sweep adds **no** parallelism, only races. And the operator's superseding order
already settled the utilisation question: **idle workers are fine**; the
100%-utilisation directive was explicitly revoked.

### Restart it with
    bash scripts/pool_watchdog.sh loop        # from the main checkout

**Restart it once the chain is merged and the backlog is the queue again.**
While Claude is driving a serial critical path, named dispatch is correct:

    POOL_ROUND=r<fresh> bash scripts/pool_dispatch.sh resonate-qwen-N:TASK-NNN

### THREE STALE WORKTREE LOCKS, CLEARED
`work/worktree-locks/` held `resonate-qwen-5`, `-8` and `-10` — orphaned by the
killed dispatches. A lock is just a directory (`mkdir` succeeds only for the
creator), so a killed worker never removes its own. **That is why dispatches to
those three were silently SKIPPED** while `resonate-qwen-3`, which had no lock,
worked every time. Cleared after confirming zero pool processes were running.

**If a dispatch reports `SKIPPED (already claimed, or worktree locked)` while
`--status` shows the task ready and unclaimed, the lock is the cause.** Check
`work/worktree-locks/` before concluding anything about the claim.

## 15. THE P0-C SIZING QUESTION IS ANSWERED: IT IS A TWO-FILE CHERRY-PICK

§11 asked the one question that sizes the last hop before the artifact — *does
the `brandiq-com` fixture resolve with ONLY the two test files cherry-picked
onto master, or does it need the copy-engine changes too?*

**MEASURED 2026-09-28 ~21:2xZ. Only the two files are needed.** In a scratch
worktree of master `8191b6a9`, with **just**

    tests/task425fixture.py             (from origin/task-p0c-causal-fixture)
    tests/fixtures/task425-evidence.json

and nothing else:

    record resolved : True
    record id       : brandiq-com
    company/domain  : brandiq.com
    contacts        : 1
    contact resolved: True
    is placeholder  : False      <- the REAL contact, not the `Ada Tester` placeholder
    research rows   : 2

**The fixture imports cleanly and needs none of P0-C's seven modified `src/`
files** (`generate.py` +469, `generate_campaign.py` +475, `bisonfactory.py`,
`campaignstrategy.py`, `copystages.py`, `offers.py`, `sequencegate.py`).

**So the last hop is a 2-file cherry-pick, NOT a second P0-B-sized merge.**
§7's refusal to merge the branch stands unchanged and is now also unnecessary:
nothing in it is needed except those two files.

### The one non-obvious prerequisite, and it is the documented trap
`record_from_store()` returns **None** in a worktree, because a worktree has no
`work/` of its own — gitignored state does not come along. The fixture reaches
the real record only when state is pointed at a **copy** of production `work/`:

    from src import store
    store.use_directory(r"<a COPY of production work/>")

`WORKSPACES` alone is NOT enough — `store.queue_path()` reads **`QUEUE`**, and
`store.use_directory()` is the helper that sets it and clears the other
overrides. **Pointing at production `work/` directly is forbidden; copy it.**

### What this means for the artifact
The remaining hops are now:

    906 (signature)  ->  2-file cherry-pick  ->  regenerate the Brand IQ record
      ->  run the artifact against brandiq-com  ->  operator review

**`research rows: 2` is lower than the 4 that `docs/P0C-CAUSAL-FIXTURE-2026-09-28.md`
recorded.** Not investigated and not a blocker for a zero-write artifact, but
**it must be checked before the artifact is called complete**, because the
research pack is what licenses every prospect-specific claim — and a claim
licensed by a row that is no longer there would be exactly the defect the
artifact exists to expose.

## 16. THE BRAND IQ RECORD, READ DIRECTLY — AND THE LINKEDIN HALF DOES NOT EXIST

**Measured 2026-09-28 ~21:2xZ, read-only against production `work/`, no
generation and no spend.** Record `brandiq-com`, contact `deyan-m`:

    em1 .. em5   subject YES   body YES   ps NO    approved NO
    li1 .. li6   subject NO    body NO    ps NO    approved NO
    research rows on the record: 4

### Three consequences for the operator's artifact

1. **The five emails exist as copy but are NOT approved and carry NO P.S.**
   The guard merged today refuses em1/em3 without one, so **this record must be
   REGENERATED**, not re-approved. That is the 1,946-step migration cost
   landing on the one account the operator wants to read.

2. **THE FIVE LINKEDIN MESSAGES DO NOT EXIST.** `li1` through `li6` carry no
   subject and no body. The operator's artifact explicitly requires *"exact 5
   LinkedIn messages"* — **there is currently nothing to show, and no task in
   the chain produces them.** This is not a rendering gap like the P.S. was; the
   copy was never generated. **It is the largest remaining gap in the artifact
   and it was not on the list.**

   Note also the SHAPE: **six** li steps are declared where the artifact wants
   five, and `src/generate.py`'s own docstring describes the LinkedIn cadence as
   *"connect, msg1 to msg3"* — three messages plus a connect, not five or six.
   **Which of those is canonical must be settled before the artifact claims to
   show "the 5 LinkedIn messages"**, and `cadence.steps_for` is the authority,
   not a docstring. Related: TASK-548, `li5 must block rather than vanish`.

3. **`research rows: 4` on the record**, which matches
   `docs/P0C-CAUSAL-FIXTURE-2026-09-28.md`. **§15's worry was misdirected** —
   the `2` came from `task425fixture.research_rows()`'s own default argument,
   not from the record's stored research. The claim-licensing pack is intact at
   4 rows. §15's flag is withdrawn on that point; the instruction to check the
   pack before calling the artifact complete still stands, because a claim must
   trace to a row that is actually there.

### What this does to the remaining plan

    906 (signature)                      running
    2-file P0-C fixture cherry-pick      sized: two files, nothing else
    REGENERATE brandiq-com email copy    required: P.S. + opt-out + signature + approval
    GENERATE the LinkedIn copy           MISSING ENTIRELY - no task owns it
    settle the li cadence shape          5 vs 6 vs "connect + msg1-3"
    run the artifact, operator review

**Regeneration and LinkedIn generation both call the model and therefore spend
credits.** That is unavoidable for an artifact of real final messages, and it
is NOT a provider write: no send, no enrolment, no prospect-facing call.
`sending.live` stays false and the freeze is untouched. **But it is real spend
and the operator should know it is coming rather than find it in a ledger.**

### 16a. CONFIRMED, AND THE SHAPE QUESTION IS SETTLED

**The "merge variables" note in `CLAUDE.md` does not rescue this.** It was
worth checking — if HeyReach held the message text in its own sequence and only
merged a name per lead, nothing would be missing. It does not.
`src/heyreachfactory.py` documents the mapping from OUR stored li steps to the
provider's graph roles:

    li1  (connect,  day 1)   -> connection_note
    li2  (message,  day 3)   -> connected_1 AND message_2
    li3  (message,  day 6)   -> connected_2 AND message_3
    li3  (alternative)       -> inmail  (InMail fallback)
    li4  (message, day 10)   -> connected_3 AND message_4
    li5  (message, day 15)   -> connected_4

and `assemble_linkedin_copy(source, contact_key, ...)` builds that block from
the record. **So the words are ours and they are absent.** The merge variables
personalise; they do not supply the message.

**Estate-wide, measured read-only: 467 li steps declared, ZERO carry copy, and
ZERO of 1,099 records have any LinkedIn copy at all.** The generation path
exists — `generate._linkedin_candidate_keys` at `src/generate.py:2119` — and
has produced nothing for anybody. **Existence is not function, again.**

**The canonical shape is `li1`..`li5`** — one connect note plus four messages —
which is exactly the operator's "5 LinkedIn messages". So §16's 5-vs-6 worry
resolves: `li6` is outside the documented graph, and
`generate.py`'s "connect, msg1 to msg3" docstring is describing a
different/older cadence. **`cadence.steps_for` remains the runtime authority
and should be read at artifact time rather than trusted from either
docstring.**

**This is the single largest remaining gap in the operator's artifact**, and
unlike the P.S. it is not a rendering fix: the copy must be generated, which
means model spend, for a channel where nothing has ever been generated in this
estate.

## 17. HOW THE ARTIFACT WILL BE GENERATED — INTO A COPY, NOT INTO PRODUCTION

The artifact needs copy that does not exist yet: the Brand IQ emails must be
regenerated (they carry no P.S. and no approval) and the LinkedIn messages must
be generated for the first time in this estate's history (§16, §16a).

`py -3 -m src.generate --live --id brandiq-com` would do it, and it does **two**
things that CLAUDE.md says to ask about, not one:

1. **Real credit spend** — `--live` calls the model.
2. **A production data mutation** — it writes the new copy into
   `work/queue.jsonl`, **overwriting that record's current stored copy.**

### The second one is avoidable, so it will be avoided

**The artifact is a REVIEW artifact. It does not need production state
changed.** Generation will run against a **COPY** of production `work/`, using
the same pattern the approval-hash probe already proved:

    from src import store
    store.use_directory(r"<a COPY of production work/>")

`store.use_directory()` sets **`QUEUE`** and clears the other state overrides.
`WORKSPACES` alone is NOT sufficient — `store.queue_path()` reads `QUEUE`
(§15).

**Consequences, all good:**

- Production `work/queue.jsonl` and `work/campaigns.jsonl` stay byte-identical,
  provable by sha256 before and after, the way the probe proved it.
- The record's existing copy is not destroyed, so nothing is lost if the
  operator dislikes the regenerated version.
- The operator still reads **exactly what this person would receive**, because
  the copy is produced by the real generation path through the real gates — the
  only difference is which directory the state lives in.
- `sending.live` stays false, the freeze is untouched, and generation is
  **not** a provider write: no send, no enrolment, no prospect-facing call.

### What still spends, and is unavoidable
**Model credits.** An artifact of real final messages cannot be produced
without calling the model. This is bounded to **one account and one contact**
(`--id brandiq-com`, one sendable contact). `scripts/task425_one_account_dry_run.py`
carries a `--usd-ceiling` defaulting to **10.00** for the same reason.

**The operator has been told this spend is coming rather than left to find it
in the waterfall ledger.** Every paid call still goes through `enrich.spend()`,
so it remains visible to the spend audit.

## 18. THE ARTIFACT IS BLOCKED ON THE ACCOUNT, NOT ON THE CODE

**Measured 2026-09-28 ~22:3xZ in the isolated generation worktree, `--live`,
against a COPY of production `work/`. Production untouched.**

**Every code blocker is merged and the chain works. The artifact cannot be
produced for Brand IQ because the campaign pipeline holds the account
UNQUALIFIED.**

### What the canonical generator returned

`generate_campaign.generate(client, account, contacts, config=, model=,
live=True)`, called with production's own mapping (`generate._account_sources`,
`lint.contact_key`):

    strategy_id      66af074526274383
    offer selected   OFFER-B-OPERATIONS      <- the offer machinery WORKS
    step objectives  present (em1..em5)      <- the strategy machinery WORKS
    contact          deyan-m, Co-Chief Executive Officer, deyan@brandiq.com
    sequences        []                      <- NO COPY
    qualification    UNQUALIFIED
    held             "not an agency: advertising technology and services firm"
    hold_kind        qualification
    gate_attempts    0                       <- never reached the copy gates

**`gate_attempts: 0` is the important number.** The copy gates — copylint, the
claim family, the figure gate, step_objectives — were never consulted. This is
not the marginal-copy problem the handoff describes at ~40%. The account is
refused before generation begins.

### TWO QUALIFICATION VERDICTS FOR ONE RECORD

    STORED (qualify.state_of)     qualified
      segment.vertical            "Performance Marketing Agency"
      qualification.at            2026-09-13T09:48:14+00:00
      inputs_fingerprint          ad524a59d3106d28
    STORED contact deyan-m        persona economic_buyer, sendable True

    CAMPAIGN PIPELINE, live       UNQUALIFIED
      reason                      "not an agency: advertising technology and
                                   services firm"

**Same record, two authorities, opposite answers.** The stored verdict is 15
days old and says Performance Marketing Agency; the pipeline re-qualifies from
the current research pack (2 admitted sources) and says not an agency.

**This is the defect `CLAUDE.md` names as the recurring one, in its purest
form:** *"Prefer canonical state to a second representation of it... a parallel
state machine for the same fact is how the two drift."* And it breaks
OPERATING-MODE **invariant 0** — one operational state, exactly one canonical
authority — on the single account the operator's milestone depends on.

**`docs/P0C-CAUSAL-FIXTURE-2026-09-28.md` says Brand IQ came through "the
normal qualification and eligibility path" with "its contact is sendable" and
"contacts / sendable 1 / 1". That is true of the STORED verdict and false of
the pipeline's.** P0-C measured the stored authority and never ran the
generation path on it — its own section 0 says the A/A2/B/C/D matrix "waits for
the P0-B signal and is NOT claimed here". So this was not caught.

### The persona discrepancy, recorded because it is separate and also real

    contact deyan-m persona            economic_buyer   (stored, per P0-C)
    account persona the pipeline used  champion         (DEFAULTED)

Production maps `account["persona"] = rec.get("persona", "champion")` — an
**account-level** field. `brandiq-com` has none, so it defaults to `champion`,
and `OFFER-B-OPERATIONS` (champion) was selected rather than
`OFFER-A-ECONOMIC-BUYER` (economic_buyer), **even though the contact under test
is an economic buyer.** The operator's artifact asks for "selected Offer A/B and
why" — the honest answer today is "B, because an absent account persona
defaulted to champion", which is a defaulting artefact, not a decision.
**Not fixed, recorded.** It is a second finding and must not be bundled into the
first.

### WHAT THIS MEANS FOR THE MILESTONE — stated plainly

**The one-account artifact cannot be produced for Brand IQ through the normal
production pipeline.** Not because of the rendering chain, which is finished and
verified, but because the account is refused at qualification. Producing it
anyway would require either bypassing the ICP gate — which would make the
artifact a lie about what the pipeline does — or overriding the pipeline's
verdict with the stored one, which is choosing the authority that disagrees.

**This is an operator decision and it is genuinely theirs**, because it is a
question about which account the first real artifact should describe and which
qualification authority governs. The options are in the session report; none of
them is a code fix.

### Spend, for the record
**2 model calls, `usd_estimate` 0.000000**, provider `openrouter`, model
`openai/gpt-4.1-mini`, run `run-45527dfeecc9` — plus the direct generator calls
above. The account was refused before the copy writer ran, so almost nothing
was spent. Production `work/queue.jsonl` and `work/campaigns.jsonl` remain
sha256-identical to the pre-generation baseline.

### 18a. THE EXACT GATE, AND THE EVIDENCE SAYS THE GATE IS RIGHT

**FAILED GATE/PATH:** `src/generate_campaign.py:481-492`, step **A. ICP check**
— a **live model call** through the `signal_verification` skill with
`copyprompts.icp_user(company, domain, sources)`. The model returns
`is_agency`; when false the pipeline sets `qualification="UNQUALIFIED"`,
`held="not an agency: %s" % what_they_actually_are`, `hold_kind="qualification"`
and **returns before step B**, so no facts are extracted and no copy is written.
That single call is one of the two metered model calls.

**THE GATE IS CORRECT, and the account's own website is the evidence.** The two
admitted sources the pipeline was given:

    https://brandiq.com/about  "About Us | Global Ad Tech & Programmatic
                                Experts Brand IQ is a global advertising
                                technology and services firm that empowers
                                organizations of all size..."
    https://brandiq.com/       "Digital Marketing & Advertising Strategy Built
                                for Growth..."

**Brand IQ describes itself as an advertising technology and services firm.**
Productive's ICP is agencies. `is_agency: false` is the right answer, and the
refusal is the gate doing its job — not a defect to route around.

**So the STALE authority is the stored verdict, not the pipeline.** The record's
stored `qualification.segment.vertical` reads `"Performance Marketing Agency"`,
measured **2026-09-13**, fingerprint `ad524a59d3106d28`. That is the one that
disagrees with the account's own words.

**ISO 9001:2015 IS NOT IN THIS RECORD'S EVIDENCE.** Measured: **0 of 4** stored
research rows contain `9001`; all four are adtech/marketing page text (about,
company_website, e-commerce advertising, financial services advertising).
`docs/P0C-CAUSAL-FIXTURE-2026-09-28.md` §0 names
`claim ISO 9001:2015 (token 9001) page https://brandiq.com/about` as the claim
under test. **No claim could be licensed from it today**, because the token is
absent from the pack the pipeline reads.

**Conclusion, stated as a decision for the operator and not taken here:
Brand IQ cannot produce copy through the normal production pipeline, and the
smallest remediation is NOT a code change.** Either the account is out of ICP
and a different qualified account must carry the first artifact, or the operator
rules Brand IQ in-ICP — which would mean overriding a live gate with a 15-day-old
stored verdict that the account's own homepage contradicts. Bypassing the ICP
gate would make the artifact a false description of what the pipeline does.
