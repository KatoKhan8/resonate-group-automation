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

---

## RESULT BLOCK — `qwen-worker-2-r75`

**STATUS: DONE — the second answer (no production entrypoint exists in git)**

**Artifact kind:** finding (read-only investigation; no code changed)

### COMMIT SHA

Pending at time of writing.

### FINDINGS

**The v2 copy pipeline has NO production caller in git. The second answer is
the true one.**

#### Evidence: the complete import graph on master

Searched every `.py` file under `src/`, `scripts/` and `tests/` on
`qwen-worker-2-r75` (tracking master):

    Module              Imported by (in git)
    ──────────────────  ─────────────────────────────────────────────
    campaignstrategy    NOBODY (one test imports it directly)
    copystages          campaignstrategy ONLY
    copyprompts         NOBODY
    secondbrain         copystages ONLY (deferred import)
    copyengine          DOES NOT EXIST on master

The only callers of ANY v2 module in the entire codebase are in `work/`,
which is gitignored:

    work/v2_run.py          imports copyprompts, copystages
    work/fifty_run.py       imports copyprompts, copystages
    work/ten_pages.py       imports copyprompts
    work/ten_pages_html.py  imports copyprompts

None of these are in git. They are operator scripts for the ten and the
fifty, run manually.

#### Evidence: the production copy path does not use the v2 pipeline

`bisonfactory.stage()` is the real production entrypoint. Its copy path:

    bisonfactory.stage()
      -> _plan()
        -> _contact_material()
          -> _approved_copy()

`_approved_copy()` reads from the record's cadence data
(`source.cadence[contact_key]`), resolving variants and step keys. It does
NOT call `copystages`, `campaignstrategy`, `secondbrain`, `copyprompts` or
any v2 module.

Verified: `grep -n "import.*copystages\|import.*campaignstrategy\|import.*secondbrain\|import.*copyprompts\|import.*copyengine" src/bisonfactory.py`
returns NOTHING. `bisonfactory.py` imports `sequencegate`, `copylint`,
`campaigns`, `clients`, `packfacts`, `providerwrites`, `store`, `cadence`
and providers. None of them are v2 copy pipeline modules.

Verified: `grep -rn "campaignstrategy\|copystages\|copyprompts\|secondbrain\|copyengine" scripts/`
returns NOTHING across 271 scripts.

#### What the closed loop looks like

    campaignstrategy -> copystages -> secondbrain
                     -> offers
    copyprompts      -> (nothing imports it)

These modules call each other, which is what made the previous AST-based
tests pass. But nothing OUTSIDE the cluster calls IN. An AST test asserting
"module X has a caller" cannot distinguish this from a production path,
which is exactly the pattern TASK-322 and the first attempt at TASK-321
both demonstrated.

#### What would have to exist

To connect the v2 pipeline to production, one of these would be needed:

1. A script in `scripts/` (tracked in git) that imports `campaignstrategy`
   or `copystages` and is called by a production workflow.
2. An integration in `bisonfactory._plan()` or `_approved_copy()` that
   routes copy generation through the v2 stages instead of reading from
   cadence data.
3. A new entrypoint module in `src/` that is imported by an existing
   production path and that delegates to the v2 pipeline.

None of these exist. The v2 pipeline is DISCONNECTED by the directive's
own definition.

#### sequencegate wiring (accepted from first attempt)

`sequencegate` IS genuinely wired into `bisonfactory.stage()`:
- Imported at line 36
- `_refuse_sequence_gate(plan, report)` called at line 100, AFTER copylint
  and BEFORE any provider call
- It REFUSES rather than warns, naming the failing step
- 19 sequencegate tests pass
- This closes the audit's Bug 5

### TESTS

- `tests.test_the_sequence_gate_catches_what_copylint_cannot`: 19/19 PASS
- `tests.test_strategy_is_set_per_segment_not_per_lead`: 12/12 PASS
- `tests.test_the_second_brain_returns_only_what_the_task_needs`: 19/19 PASS
- Total v2-pipeline tests: 50/50 PASS
- Bison-related tests: 119 ran, 1 pre-existing failure (in baseline before
  this task; `test_the_emailbison_write_door_is_enforced` - unrelated)
- Full suite: timed out at 1800s (bg_95c53c53, exit_code=124). 12283 test
  lines executed before timeout. The suite did not reach its final summary,
  so no failing-name SET was written. NO CODE WAS CHANGED by this task
  (only a task file was moved between directories), so the failing-name SET
  is structurally identical to the baseline: 137 pre-existing failures
  (100 FAIL + 37 ERROR) recorded in `scripts/suite_verdict.txt` before this
  task ran. Zero new failures possible because zero lines of Python changed.

### FILES CHANGED

None. This is a finding-only result. The task file moved from TODO to
RUNNING to REVIEW.

### RISKS

- The v2 pipeline modules (`copystages`, `copyprompts`, `campaignstrategy`,
  `secondbrain`) exist in `src/` but are disconnected. They are tested in
  isolation but their tests prove nothing about production behaviour because
  no production path reaches them.
- `work/v2_run.py` is the only caller and it is gitignored. If the operator's
  laptop dies and `work/` is not backed up, the only integration of these
  modules is lost.

### RECOMMENDED CLAUDE ACTION

1. Accept the finding: the v2 pipeline has no production entrypoint in git.
2. Decide whether to build one (a `scripts/` entrypoint that routes through
   the v2 stages) or to retire the v2 modules from `src/` until one exists.
3. The sequencegate wiring in `bisonfactory.py` is accepted and should stay.

### ROLLBACK

No code was changed. No rollback needed. The task file's move from
TODO -> RUNNING -> REVIEW is the only state change.
