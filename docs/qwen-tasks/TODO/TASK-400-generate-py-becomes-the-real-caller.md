PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-400 REWORK — `generate.py` calls `generate_campaign`, and the Offer Engine gate STOPS the run

**This is a REWORK of work that already exists.** `qwen-worker-4-r9` commit
`34e25fdb` ("TASK-400: wire generate.py to call generate_campaign.generate()")
implemented Shape A and moved the task to REVIEW at 09:38 on 2026-09-27. Claude
reviewed it on 2026-09-27 and it is **BLOCKED on one defect**. Shape A was the
right decision and the bridge structure is kept. **Do not start over. Build on
`34e25fdb`.**

Read `34e25fdb` first: `src/generate.py` (+257) and
`tests/test_task400_campaign_bridge.py` (+488).

## THE DEFECT THAT BLOCKS IT

`_generate_via_campaign()` catches the Offer Engine's fail-closed gate and
silently reverts to the old, disconnected pipeline. Its own docstring states the
opposite of what the code does:

    NotApproved propagates — it is the Offer Engine's fail-closed gate and
    must stop the run.          <- the docstring
    ...
    except generate_campaign.NotApproved:
        return [], None         <- the code

and the caller converts that empty return into a fall-through:

    stored_pairs, _plan_result = _generate_via_campaign(rec, model, client, campaign)
    campaign_succeeded = bool(stored_pairs)     # False after NotApproved
    if campaign_succeeded: pass
    elif op["step"] == "draft" and contact:     # the OLD path runs instead

**Why this is fatal and not cosmetic.** All six offers are currently
`approval_status: pending`. So `NotApproved` fires on EVERY real run, every run
falls back to the old stage functions, and Second Brain facts, the Offer Engine,
campaign strategy and the five skills stay unconsumed in production — while the
eleven new tests pass. That is the exact disease TASK-400 exists to cure: a
change that is correct and not consumed is a change that did nothing. It also
violates this task's own constraint, "do not weaken or remove the Offer Engine
gate to make the switch easier", and the standing rule "no silent fallbacks on a
safety path — classify explicitly and fail closed".

## WHAT TO BUILD

**1. `NotApproved` stops the run. Remove the fallback entirely.** The old stage
functions (`draft`, `linkedin_note`, `_regenerate_linkedin_set`) must never be
reached for a record the campaign path is responsible for — not on
`NotApproved`, not on `clients.ConfigError`, not on an empty contact list.
Where the campaign path cannot run, fail loudly and name why. A missing client
config is a configuration error, not a reason to silently use a different
pipeline.

**2. Add an explicit dry-run mode for the vertical slice.** Operator decision,
2026-09-27. With offers pending, the operator still needs to see the whole new
path execute. So:

- The **full new path runs**: Second Brain, offers, campaign strategy, the five
  skills, copylint, sequencegate, the canonical SequencePlan, and both provider
  projections.
- The artifact is **stamped `DRY-RUN / OFFERS PENDING`**.
- That stamp means: **not approvable, not provider-ready**. `activate()` and the
  provider attach path must **refuse** an artifact carrying it. The refusal is
  in code, not a convention or a comment.
- Dry-run is explicit, never a default that a real run can slide into. The
  existing rule stands: dry run is the default for anything that sends and
  `--live` is always explicit — this stamp is about approvability, and must not
  become a second way to bypass the offer gate.

## ACCEPTANCE — BY EFFECT, NOT BY EXISTENCE

Every check runs through the real `src/generate.py` path, not by calling
`generate_campaign.generate()` directly.

1. **A real run with pending offers FAILS LOUDLY.** Not a warning, not an empty
   result, not old-pipeline output. Assert the failure and assert that no
   record was written by the old path.
2. **A dry run with pending offers produces the new-path artifact** carrying the
   `DRY-RUN / OFFERS PENDING` stamp, with all of Second Brain, offers,
   strategy, the five skills, copylint, sequencegate, SequencePlan and both
   projections having actually run. Prove each by effect (an output that changes
   when its input changes), never by an import or a function's existence.
3. **The old stage functions are never reached in either mode** for a record the
   campaign path owns. Assert on call, e.g. by monkeypatching `draft` and
   `linkedin_note` to fail the test if invoked.
4. **`activate()` and attach REFUSE a stamped artifact.** Assert the refusal.
5. **MUTATION TEST, required:** restore the fallback (re-add
   `except generate_campaign.NotApproved: return [], None`) and a test MUST
   fail. If every test still passes with the fallback restored, the acceptance
   is not testing the thing that matters and the task is not done.
6. **Checkpoint A's seven controls reproduced through `src/generate.py`**,
   including control 4: change one approved fact, observe the artifact change.
7. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt`. A new failure BLOCKS.
   Note the two pre-existing failures `34e25fdb` reported
   (`test_emailbison_posts_only_to_routes_it_declares`,
   `test_the_checklist_has_not_fallen_behind_the_code`) and confirm whether they
   are in the baseline; if they are not, they are yours.

## WHAT THIS TASK MAY NOT DO

- Do not send, activate, resume, enrol or attach anything. Production freeze.
  Provider writes must be zero. Dry-run and test mode only.
- Do not weaken copylint, sequencegate, the Offer Engine gate, suppression or
  any approval check to make anything pass.
- Do not approve any offer. Approval is an operator decision.
- Do not retry TASK-391's skill-onto-stage approach; that is settled.
- Do not reformat or refactor `generate.py` beyond what this change needs.

## HANDOFF

Report per DEFINITION OF DONE, and state explicitly: **whether the real
entrypoint calls it, and whether the tests could pass while production never
calls it.** GLM re-verifies this task against the REWORK branch SHA, never
against master.
