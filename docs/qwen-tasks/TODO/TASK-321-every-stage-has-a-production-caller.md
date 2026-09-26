PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-321 — REWORK. The wiring certified a closed loop.

**First attempt: `qwen-worker-3-r73`, reported DONE. Partially integrated,
partially rejected. Read this before starting.**

## WHAT WAS ACCEPTED AND IS NOW ON MASTER

`src/bisonfactory.py` — `sequencegate` is imported and `_refuse_sequence_gate(plan,
report)` is called from `stage()` (line 54), **after copylint and before any
provider call**, and it REFUSES rather than warns, naming the failing step.

Verified by hand: the call site is inside `stage()`'s real flow, 19 sequencegate
tests pass, and 76 tests across the four suites that import `bisonfactory` pass
with it in place. **This genuinely closes the audit's Bug 5.** Do not redo it.

## WHAT WAS REJECTED, AND WHY

`src/copyengine.py` was NOT taken, and its test was NOT taken.

**The wiring is a closed loop.** Measured on the branch:

    copyengine        -> copyprompts, copystages, campaignstrategy
    campaignstrategy  -> copystages, offers
    copystages        -> secondbrain
    NOTHING           -> copyengine

Searched every `.py` under `src/` and `scripts/` on that branch: **nothing imports
or calls `copyengine`.** So the chain terminates in an orchestrator no production
path invokes, and the modules "have callers" only because they call each other.

**Proof it was a closed loop:** with `copyengine.py` removed,
`test_copyprompts_has_caller`, `test_campaignstrategy_has_caller` and
`test_all_v2_modules_have_callers` all FAIL, and `test_copyengine_has_caller`
errors. Their only caller was the module with no caller.

**The branch's own finding 1 says it plainly, and it is correct:**

> The real production path that produces copy today: `bisonfactory.stage()` ->
> `_plan()` -> `_contact_material()` -> `_approved_copy()`. The approved copy comes
> from the record's cadence data, not from the v2 pipeline. The v2 pipeline is a
> NEW path that was disconnected.

That is the honest answer, and it means the task is not done: **the v2 pipeline is
still not the thing that produces production copy.**

This is the third time this exact pattern has appeared — TASK-322 added
`copystages.business_context_for`, which called `secondbrain` and had no caller
itself; now `copyengine` does the same one level up. **An AST test asserting "module
X has a caller" cannot distinguish a production path from a mutual-import cluster.**

## WHAT REWORK MUST DO

**Either** connect the v2 pipeline to a real production entrypoint so that
generated copy actually flows through it, **or** report — with evidence — that no
such entrypoint exists on master and that the only path to copy is
`work/v2_run.py`, which is gitignored and not in git.

**The second answer is acceptable and may well be the true one.** If so, say it
plainly and name what would have to exist. Do not manufacture a caller to satisfy
a test.

`src/copyengine.py` remains available on `origin/qwen-worker-3-r73` and is not
lost. It is not on master because a module with no production caller is
DISCONNECTED by the directive's own definition, and adding one is what these rules
exist to prevent.

## THE ACCEPTANCE, RESTATED BY THE OPERATOR 2026-09-26 — this supersedes the list below

**Vertical-slice §4, through the REAL production entrypoint. An import chain is not
proof.**

> Change one **VERIFIED or CLIENT_APPROVED** fact in the Second Brain and show the
> strategy context **and the final output** change accordingly.

Concretely, and nothing less closes this task:

1. Pick a **CLIENT_APPROVED** fact. A `product.capabilities` sentence in
   `config/clients/productive.yaml` is the clean case, because `secondbrain._fact`
   now derives its source from the client actually loaded.
2. Generate for one account **through the production entrypoint** — not by calling
   `copystages`, `secondbrain` or `campaignstrategy` directly. Capture the strategy
   context and the final copy.
3. **Change that one fact.** Re-generate the same account the same way.
4. Show that **both the strategy context AND the final output** changed, and that
   they changed *because of that fact*. Quote before and after.
5. Revert the fact. Re-generate. Show it changed back.

A test that imports a module, asserts a symbol exists, or calls an internal
function directly **does not count.** Neither does a change in a variable nothing
renders. The chain must terminate in observable output.

**Report the production entrypoint by name.** If the only path to copy is
`work/v2_run.py` — gitignored and not in git — say so plainly. That is the finding,
and it means the wiring has nowhere to terminate yet.

## Acceptance - RUN each, paste real output

1. `py -3 -m unittest tests.test_every_stage_has_a_production_caller -v`
2. **Seen to fail:** plant a public function with no caller, re-run, confirm the
   test FAILS and NAMES it, delete the probe, confirm green. Paste all runs, and
   confirm the plant actually landed.
3. `sequencegate` REFUSES a staging: a real `bisonfactory` staging call with a
   failing sequence, asserting the refusal names the step. Fake transport only.
4. **The ten and the fifty are unaffected.** They run from `work/v2_run.py`, which
   must not import your changed path. Prove it, do not assume it - the plan claims
   this is verified and the file is not in git, so verify it yourself and say how.
5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## Rollback

State it explicitly in your result block: which single commit reverts this, and
what returns to the previous behaviour.

## What this task may NOT do

- **No provider call, no live staging, no activation, no send.** The production
  freeze is in force and 493 is sending.
- Do not modify `copystages.py`, `copyprompts.py` or `sequencegate.py` contents -
  they are READ ONLY here. Wire them; do not edit them.
- Do not weaken `copylint` or `sequencegate` to make the wired path pass. If
  wiring them refuses copy that used to ship, that is the finding.
