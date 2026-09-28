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
