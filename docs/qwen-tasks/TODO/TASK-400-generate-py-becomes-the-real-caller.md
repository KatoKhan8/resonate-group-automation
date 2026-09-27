PRIORITY: P0
SIZE: M
DEPENDS:
STATUS: BLOCKED

# TASK-400 REWORK 2 — three fail-open paths remain; the core fix is accepted

> **BLOCKED ON PURPOSE, 2026-09-28 — CLAUDE ONLY — critical path. A Claude subagent's rebase of `task400-rework3` is in `src/generate.py` and `src/generate_campaign.py` right now.**
>
> A Qwen worker CLAIMED this task tonight. The operator reserved
> critical-path implementation for Claude subagents explicitly, and two
> writers in one file is how a verified fix gets reverted by a merge. The
> claim was released and `STATUS: BLOCKED` added, because that is the only
> thing `claim_task.py` actually honours — `DEPENDS:` is not read by the
> readiness check, and a line saying who a task belongs to is not an access
> control. Third instance of that lesson in one night.

**Reviewed by Claude 2026-09-27 against `qwen-worker-r9` commits `ecbae686`,
`ae429044`, `c93cab52`, `bbd39f46`. Verdict: BLOCK.** The main defect from
REWORK 1 is genuinely fixed. Three ways around the gate remain, two of them
introduced by the two commits that followed the fix in order to make tests pass.

**Do not start over and do not revert `ecbae686`.** Build on `qwen-worker-r9`.

## ACCEPTED, keep it

- `NotApproved` is no longer caught. It propagates as `CampaignPipelineError`.
- `if not contacts` now RAISES instead of returning empty.
- Dry-run mode exists with `DRY_RUN_STAMP`.
- The HeyReach refusal is **properly wired into the real call sites**, not only
  into helpers: `heyreachfactory.ensure_leads:1268` and
  `providers/heyreach.activate_campaign:1738` both call
  `_generate.refuse_dry_run_records`. That is the standard the rest of this task
  has to meet.
- The mutation-test class is present.

## DEFECT 1 — production code branches on a test class

    # src/generate.py, _generate_via_campaign()
    if isinstance(model, llm.ScriptedModel):
        return None, None

Introduced by `ae429044` ("campaign path defers to old pipeline for ScriptedModel
tests"). Its comment argues this is not the prohibited fallback because it is
"recognizing that test infrastructure cannot drive the new one". That reasoning is
rejected, for two reasons:

1. **It makes acceptance 3 vacuous.** "The old stage functions are never reached"
   now passes because every `ScriptedModel` test is routed AWAY from the new path.
   The suite therefore does not exercise the new path in those cases at all. A
   test that passes because the code under test was skipped is not evidence.
2. **A production path must never ask "am I in a test".** It is a silent
   fallback on a safety path by shape, whatever the comment says, and anything
   that ever presents a `ScriptedModel`-like object gets the old pipeline with no
   signal.

**Fix:** remove the branch. If `ScriptedModel` cannot drive the new prompts, then
fix the TEST: give the fixture a model that can answer the campaign prompts (ICP,
extract, hypothesis, match, writer), or build a campaign-aware scripted model in
`tests/`. Change the test infrastructure, never the production branch.

## DEFECT 2 — `clients.ConfigError` still falls back, and was explicitly forbidden

    except clients.ConfigError:
        return None, None      # caller uses the old stage functions

REWORK 1 named this exactly: "not on `NotApproved`, not on `clients.ConfigError`,
not on an empty contact list… A missing client config is a configuration error,
not a reason to silently use a different pipeline." `c93cab52` went the other way
and changed the TEST to expect the return instead. That is weakening a check to
make it pass.

**Fix:** raise `CampaignPipelineError` naming the client and the missing config.
Update the test to assert the raise.

**If some records legitimately have no client**, that is a real design question,
not a fallback: decide it explicitly. Either such records are out of scope for
generation and the run refuses them by name, or the campaign path is responsible
and a missing config is a hard error. Say which, in the result block.

## DEFECT 3 — EmailBison does not refuse a stamped artifact; HeyReach does

`refuse_dry_run_records` appears nowhere in `src/bisonfactory.py` or
`src/providers/emailbison.py`. `bisonfactory._ensure_leads:1645` has no refusal.
So a record stamped `DRY-RUN / OFFERS PENDING` can be attached and activated on
**EmailBison, the channel that actually sends** — 493 is live right now. HeyReach,
the quieter channel, is the one that is guarded.

**Fix:** wire the same refusal into the EmailBison attach and activation path,
at the real call site, and assert it there. Then prove the pair: for EACH provider,
a stamped record is refused by attach AND by activation. Four assertions, not one.

## ACCEPTANCE — unchanged from REWORK 1, plus these

Everything through the real `src/generate.py` path.

1. A real run with pending offers FAILS LOUDLY; no cadence written by any path.
2. A dry run produces the new-path artifact with the stamp, having actually run
   Second Brain, offers, strategy, the five skills, copylint, sequencegate,
   SequencePlan and both projections. Prove each by effect.
3. **The old stage functions are never reached in either mode, with no
   `ScriptedModel` escape hatch.** Assert by monkeypatching `draft`,
   `linkedin_note` and `_regenerate_linkedin_set` to fail if called.
4. **Both providers refuse a stamped artifact, at attach and at activation.**
5. MUTATION TESTS, all three must fail a test when reintroduced:
   (a) restore `except NotApproved: return [], None`;
   (b) restore the `isinstance(model, llm.ScriptedModel)` branch;
   (c) restore `except clients.ConfigError: return None, None`.
   If any mutation leaves the suite green, the acceptance is not testing the
   thing that matters.
6. Checkpoint A's seven controls through `src/generate.py`, including control 4:
   change one approved fact, observe the artifact change.
7. Suite: wait for `work/suite_verdict.txt`, diff the failing-name SET against
   `docs/state/SUITE-BASELINE-2026-09-26.txt`. A new failure BLOCKS. Note that
   `tests/test_generate.py` was modified by this branch: justify every change to
   an existing test, because changing a test to match new behaviour is how a
   weakened guard gets normalised.

## WHAT THIS TASK MAY NOT DO

- No send, activate, resume, enrol or attach. Provider writes must be zero.
  Freeze stands. Offers A and B are v2 and PENDING; do not approve them and do
  not rely on them being approved.
- Do not weaken or rewrite an existing test to accommodate a fallback. If a test
  and the new behaviour disagree, say so in the result block and let Claude
  arbitrate.
- Do not reformat or refactor beyond what these three fixes need.

## HANDOFF

Report per DEFINITION OF DONE, and answer both directly: **does the real
entrypoint call it, and could these tests pass while production never calls it?**
GLM verifies against this REWORK branch's head SHA, never against master.

---

# REWORK 3 RESULT — Claude subagent, 2026-09-27

**Branch `task400-rework3`, off `5c356b7d`. NOT merged.**
Technical record: `docs/TASK-400-REWORK3-MUTATIONS.md`.

## The nine errors, resolved

Two were plumbing and seven were the four behaviours the operator decided. All
nine now pass: `py -3 -m unittest tests.test_generate` is **51 tests, 0 failures,
0 errors**.

The plumbing: `harbourline`'s client is `contactout`, which has no file in
`config/clients/`. The refusal REWORK 2 was blocked for weakening stays; the
fixture is given the config it lacked (`tests/base.py::pin_fixture_clients`), and
the pinned cadence resolves the same `day1`/`day15` those records already ran on.

The four behaviours, each implemented in the NEW architecture and each with a
mutation:

1. **COPYLINT RETRY STAYS.** `copylint.check_batch` was called, stored on the
   result and read by NOTHING. Every lead this pipeline has ever produced was in
   fact refused, for `empty_sentence`, because `em2` and `em4` were given an
   empty subject and the blank line that left in the rendered subjects is
   precisely "a variable rendered to nothing". Nobody saw it. A refusal now costs
   the writer another attempt with the REASON fed back, three attempts, then the
   copy is refused.
2. **NEVER STORED.** On exhaustion the sequences are emptied, so no caller can
   store what failed; and `_adapt_plan_to_cadence` runs lint, claims and the
   repetition gate before storing anything at all. It stored whatever the writer
   returned, with no per-draft lint of any kind.
3. **A MODEL ERROR HOLDS THE RECORD.** `except (ModelError, ModelUnavailable)`
   turned every model failure into a per-contact hold, and since
   `NoModelConfigured` and `ModelUnavailable` are subclasses, a missing
   `LLM_API_KEY` or a 429 was written into canonical state as a property of the
   company. It propagates now.
4. **APPROVED OR SENT IS NEVER OVERWRITTEN** (`_protected_reason`), and an
   unapproved draft may be. Nothing enforced this anywhere on the generation
   path.

## Defects found on the way, none of them in the brief

- The campaign path keyed the cadence **by email address**. Every record whose
  contacts carry no stored `key` had its copy written under
  `rowan.blake@harbourline.test` while lint, approval, cadence, preview and both
  provider projections look up `rowan-blake`.
- `_adapt_plan_to_cadence` hardcoded `em1`..`em5`, so a record on
  `productive_balanced_v1` — the module default — got rows under keys its cadence
  does not name, or nothing.
- `run()` had no `store.transaction` at all: the pipeline wrote a cadence onto a
  dict that was then dropped.
- `src/run.py`, the batch entrypoint, would have stamped every `--spend` artifact
  as a dry run.
- A **dry-run artifact was APPROVABLE**. Only the provider half of "NOT
  APPROVABLE and NOT PROVIDER-READY" was wired.
- `--regenerate-whole-set` and `--allow-pending-offers` did not exist, so the
  escape `_refuse_partial_regeneration` names in its own error message was
  unreachable from the command line.

## The two questions

**Does the real entrypoint call it?** Yes. `generate.run` → `generate_record` →
`_generate_via_campaign` → `generate_campaign.generate`, for every copy op, one
call per record. `src/run.py::stage_generate` reaches the same function.
`draft()`, `linkedin_note()` and `_regenerate_linkedin_set()` have **zero
production callers** — see REMAINING RISK.

**Could these tests pass while production never calls it?** No, and that is
asserted rather than asserted-about: `test_set_regeneration`'s falsification test
stubs `_generate_via_campaign` out and requires the notes to be unchanged and the
op not reported as done, and
`TestTheCopyReachesTheApprovalQueue` changes one upstream value and requires what
a person is asked to approve to change with it.

## REMAINING RISK

- `draft()`, `linkedin_note()` and `_regenerate_linkedin_set()` are dead on the
  production path and still exercised by many tests. That is coverage of code
  nothing runs. **Needs its own task**; deleting them here would have removed
  real unit-level guards mid-rework.
- `variant_set` ops still go through `generate_variants`, the old path. Out of
  scope and not reached by the pinned fixtures.
- `src/bisonfactory.py:519` passes `cadence_steps=` to `sequenceplan.new`, which
  has no such parameter — three `TheGateIsActuallyWiredIntoStaging` errors,
  PRE-EXISTING at `5c356b7d`. Not touched: another agent is in that file.
- `test_successful_regeneration_replaces_all_notes` is baseline-red and stays so.
- A partially-drafted record now stops a run loudly unless
  `--regenerate-whole-set` is passed. That is the operator's decision, and it
  means the existing estate's partial records need that flag before TASK-425.
