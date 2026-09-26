PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-369 — one versioned production entrypoint for campaign generation

**This is the critical path.** TASK-321's rework concluded that **no production
entrypoint for generation exists in git**. The only path that has ever produced
copy is `work/v2_run.py`, which is **gitignored and not in version control**.
Every "wire the v2 layer" task has produced a closed loop because the thing the
layer is supposed to terminate in does not exist. Three did that on 2026-09-26.

You are building the thing they were trying to wire into.

## What exists today, precisely

`work/v2_run.py`, 234 lines, last modified 2026-09-25. Read it first. It:

- calls Groq and Anthropic **directly** through `urllib` (`post()`, `groq()`,
  `sonnet()`), so **no model call it makes reaches `src/llm.py` or the spend
  ledger** — the fifty's copy spend is invisible;
- loads its inputs from hardcoded paths: `work/ten-OLD-v1.json`,
  `work/sample50-built.json`, `work/researchpack*.jsonl`;
- runs stages A-G from `copyprompts` / `copystages`, then `sequencegate.check`
  and `copylint.check_batch`;
- dumps `work/v2-data.json` and prints counts;
- consumes **no** Second Brain, **no** offers, **no** campaign strategy, **no**
  skills, **no** approval, and produces **no** provider payload.

`src/copyengine.py`, `copystages.py`, `copyprompts.py` have **zero production
callers** on master. `src/secondbrain.py`, `src/offers.py`,
`src/campaignstrategy.py`, `src/copylint.py`, `src/sequencegate.py` are on
master and are real.

## Build

    src/generate_campaign.py    NEW. The single versioned production entrypoint.
    src/sequenceplan.py         NEW, if no canonical plan object exists yet.
    tests/test_the_entrypoint_is_the_only_generation_path.py    NEW
    tests/test_changing_an_approved_fact_changes_the_output.py  NEW

**Cherry-pick, by path, from `origin/qwen-worker-4-r9`** (TASK-319, verified
complete there; this absorbs TASK-334):

    src/skills/__init__.py  account_research.py  signal_verification.py
    src/skills/campaign_strategy.py  cold_email_writing.py  linkedin_writing.py
    tests/test_a_skill_is_loaded_by_the_stage_that_uses_it.py

**CHECK EVERY FILE YOU TAKE.** Three branches on 2026-09-26 carried a pre-322
`src/secondbrain.py` that would have silently reverted the provenance fix. Take
`src/skills/*` and that one test file and **nothing else** — no `secondbrain.py`,
no `copylint.py`, no config, from that branch. Run `git diff origin/master --`
on every file before you stage it, and paste the file list you took.

## The shape it must have

One function, one version constant, one plan object:

    ENTRYPOINT_VERSION = "1"        # bump when the plan shape changes

    def generate(client, account, contacts, *, config=None, live=False)
        -> SequencePlan

**`SequencePlan` is the one truth (§5).** Preview, the XLSX workbook, the
approval hash, the EmailBison payload and the HeyReach payload are **projections
of it** — each derives from the plan, none re-implements it. If a projection
needs a field the plan does not carry, add the field to the plan; do not compute
it twice. Existing projections (`src/preview.py`, `src/bisonfactory.py`,
`src/heyreachfactory.py`) are the consumers — **read them before you design the
plan**, and shape it so they can be fed by it.

It must consume, for real, not by import:

1. **Second Brain** — `src/secondbrain.py`. Only `verified` / `CLIENT_APPROVED`
   facts reach copy. Provenance is never fabricated; `INFERRED` may inform
   strategy and must never become a prospect-facing assertion.
2. **Offers** — `src/offers.py`. All six offers are `approval_status: pending`
   and the operator has **not** approved Offer A or Offer B. So the correct
   behaviour today is **`NotApproved`, raised by name, fail-closed** — build it
   so that approving an offer is the only thing needed to make it flow, and
   prove the refusal in a test. Do not approve an offer. Do not work around one.
3. **Campaign strategy** — `src/campaignstrategy.py`, decided **once per
   segment**, not once per lead. `model_call_count() == 1` for 50 leads is the
   property already proven on master; do not regress it.
4. **The five skills** — loaded by the stage that uses them, the TASK-319
   contract. A skill file nothing loads is not integrated.
5. **`copylint`** and **`sequencegate`** — sequencegate runs **after** copylint
   and **before** any provider call, refusing and naming the step. That call
   site already exists inside `bisonfactory.stage()` line 54; do not build a
   second one, route through it.

**Every model call goes through `src/llm.py`.** Not `urllib`, not a copied
`post()`. That is how the call reaches the spend ledger, and it is the reason
the fifty's spend is invisible today. No model slug appears outside
`config/model_policy.yaml`.

Inputs come from the client config and the record store, **not** from
`work/*.json` literals. Where you genuinely need the existing fifty as a
fixture, copy it into `tests/fixtures/` and say so.

## Acceptance — RUN each, paste real output

1. **THE SECTION 4 TEST. This is the one that closes the task.** Directive §4:

   > Changing valid upstream information changes the intended downstream
   > production context/output through the real production entrypoint.

   Change **one approved Second Brain fact**, call `generate(...)` through the
   real entrypoint, and assert the produced `SequencePlan` **differs in the
   place that fact belongs**. Then change it back and assert the output returns.
   A test that asserts "output is not empty", or that reaches inside and calls
   an internal function, **does not close this task**.

2. **The negative control for 1.** Change a fact that is **not approved** —
   `INFERRED` or `UNKNOWN` — and assert the prospect-facing output does **not**
   change. If both changes move the output, the pipeline is passing unapproved
   material to prospects and the task has found a P0; stop and report it.

3. **One plan, six projections.** Take one `SequencePlan`, derive preview, the
   XLSX workbook, the approval hash and both provider payloads from it. Change
   **one step body** in the plan and assert **all** of them change. Any
   projection that does not move is a second implementation — name it.

4. **The offer refuses by name.** With all offers `pending`, `generate(...)`
   raises `NotApproved` naming the offer. Paste the message.

5. **Strategy is decided once.** 50 leads in one segment gives
   `campaignstrategy.model_call_count() == 1`.

6. **Every model call is ledgered.** Run the entrypoint against a fixture model
   and assert a `spendledger` row exists for each call, with a real client
   (not `"_model"` — see TASK-346). Assert `src/generate_campaign.py` contains
   no `urllib`, no `requests`, and no API base URL.

7. **`work/v2_run.py` is reproducible from a clone.** State plainly whether the
   entrypoint now produces the same shape v2_run produced. If it does not,
   say what differs and why — an honest difference is acceptable, a silent one
   is not.

8. Full suite: wait for `work/suite_verdict.txt` to exist, then diff the
   **failing-name SET** against `docs/state/SUITE-BASELINE-2026-09-26.txt`
   (128 named failures). A new failing name BLOCKS. Do not grep a running log
   for a FAIL prefix — mid-run it always returns nothing.

## What this task may NOT do

- **Nothing is sent, activated, resumed, enrolled or attached.** The production
  freeze (`docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md`) is in force. 493 is
  ACTIVE and sending and is not touched. Use fake transports. `live=False` is
  the default and the only mode you may exercise.
- **Do not approve an offer.** All six stay `pending`; that is an operator
  decision.
- Do not delete or rewrite `work/v2_run.py` — it is the reference. Promote from
  it; leave it where it is.
- Do not add a second copy pipeline. If `copyengine`/`copystages` already do a
  stage, call them.
- Do not invent a second research store. Facts reach copy through
  `packfacts.pack_for(rec)` today (`src/bisonfactory.py:559`); `researchpack`
  has no production consumer and **whether it becomes one is an open operator
  decision** — do not decide it here.
- Do not change the cadence. Five emails on days 1/4/8/12/21, LinkedIn
  `PRODUCTIVE_LI_HEAVY_V1` five steps on days 1/3/6/10/15, two branches.

## Report

TASK · STATUS · FILES · SCOPE DEVIATIONS · TESTS · TEST RESULTS · PRODUCTION
ENTRYPOINT · CONSUMER · END-TO-END EFFECT · LOCAL SHA · REMOTE SHA · BRANCH ·
PRODUCTION IMPACT · REMAINING RISK.

If you conclude the task cannot be done as specified, **say so with the
evidence** — that is what TASK-321 did, and it was the right answer. A closed
loop reported as success is the failure mode here.
