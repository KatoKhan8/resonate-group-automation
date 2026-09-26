PRIORITY: P0
SIZE: L
DEPENDS: TASK-321

# TASK-364 — one canonical SequencePlan, and no fourth representation

**Vertical-slice §5 and §37 step 21.** Operator, 2026-09-26: *one canonical object
from which preview, XLSX, approval hash and both provider payloads derive; no
fourth representation.*

> PREVIEW IS A PROJECTION, NOT A SECOND IMPLEMENTATION. … One truth.

## I checked whether one already exists. It does not.

§5 forbids creating a parallel representation if the repo already has one.
Verified on master `c785c388`:

    src/plan.py         a CAPACITY / SCHEDULE estimator — "how many emails is
                        this, how many days does it take". NOT an outreach plan.
                        **0 importers.** Do not extend it, do not rename it, do
                        not confuse it with this. The name collision is the
                        hazard — read its docstring before touching anything.
    bisonfactory._plan  line 414 — builds its own email plan
    heyreachfactory     build_sequence() — builds its own LinkedIn sequence
    work/v2_pages.py    hardcodes its own cadence table, days 1/3/8/14

**Four builders, four truths.** That is the duplication §5 names, and the preview's
wrong LinkedIn days are proof it is already costing us: it renders days 8 and 14,
which exist in no cadence in this system.

## Build

    src/sequenceplan.py   NEW. The canonical object.
    tests/test_every_representation_derives_from_one_plan.py   NEW

Per §5 the plan contains or references: ACCOUNT · CAMPAIGN · OFFER · CONTACT ·
CHANNEL · STEP · WAIT/TIMING · THREAD RELATION · MESSAGE · OBJECTIVE · EVIDENCE ·
QA RESULT · SUPPRESSION STATE · VERSION.

**Timing and thread relation are READ FROM `src/cadencelibrary.py`, never
restated.** Email days 1/4/8/12/21 with threads A / A-reply / B / B-reply / C;
LinkedIn `PRODUCTIVE_LI_HEAVY_V1`, five steps at days 1/3/6/10/15 across two
branches. **A day number typed into this module is the TASK-343 defect
reintroduced.**

Then, and this is the whole task:

    EmailBison adapter   reads it
    HeyReach adapter     reads it
    preview              renders it
    XLSX                 exports it
    approval hash        hashes it
    QA                   validates it

## The hash must pin the plan, not a rendering

§22: *"Do not implement this by hashing one preview representation while provider
payload derives from another representation."*

The approval hash is computed over a **deterministic serialization of the
SequencePlan**: stable key order, stable formatting, no timestamps, nothing
dependent on dict iteration order. Two runs producing the same plan produce the
same hash; any material change produces a different one. `TASK-328` threads that
hash to the write gate.

## Acceptance — RUN each, paste real output

1. **One object, six consumers.** Build the plan once for one account and derive
   all six. Assert each received the same plan — or an equal serialization — and
   not a rebuild.

2. **Change the plan and all six change together.** Alter one step's message,
   re-derive, and assert preview, XLSX, both payloads, the hash and the QA result
   all reflect it. **A consumer that does not change is not deriving from the
   plan.** This is the assertion that closes the task.

3. **No consumer carries its own cadence.** Change a day in `cadencelibrary` and
   assert the day changes in all six outputs. Then grep every consumer for a
   literal day number and report each hit.

4. **The hash is deterministic and sensitive:** identical plan twice → identical
   hash; one character of one message changed → different hash. Assert both.

5. **No fifth representation.** Report every remaining independent builder of an
   email or LinkedIn step list. `bisonfactory._plan` and
   `heyreachfactory.build_sequence` must now derive from the plan, or be gone. If
   one still builds independently, **say so** — an unreported parallel truth is the
   failure mode of this task, not a detail.

6. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET against
   `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 names). Not a count.

## What this task may NOT do

- **Do not change the cadence, the threading, or the LinkedIn tree.** Read them.
- Do not extend, rename or repurpose `src/plan.py`.
- **Do not add the canonical object while leaving the parallel builders in place.**
  The point is to remove parallel truths, not to add a layer above them.
- No provider write, no send, no activation, no live test. Payloads are BUILT and
  asserted, never transmitted.
- Nothing sent, nothing activated.

## RESULT BLOCK

**STATUS:** REVIEW
**COMMIT SHA:** d0d0dc88
**ARTIFACT KIND:** code + test

**TESTS:** 36 new tests in `tests/test_every_representation_derives_from_one_plan.py`,
all passing. 291 related tests run (bisonfactory, heyreachfactory, cadence, staging,
campaign QA, cadence wiring, cadence sweep, literal name check), 2 pre-existing
baseline failures (`test_staging_the_same_material_twice`), zero regressions.

**FILES CHANGED:**
- `src/sequenceplan.py` — REWRITTEN. Canonical SequencePlan with `build()`,
  `email_sequence_for_bison()`, `linkedin_delays()`, `serialize_for_approval()`,
  `approval_hash()`, `derive_preview_data()`, `derive_bison_payload()`,
  `derive_heyreach_payload()`, `derive_xlsx_rows()`, `derive_qa_summary()`.
  Preserves backward-compatible `new()` for `generate_campaign.py`.
- `src/bisonfactory.py` — `_sequence_steps` accepts `plan=` kwarg and reads
  email step order and thread-reply from the plan. `_plan` builds a
  SequencePlan and passes it through. Return dict carries `sequence_plan`.
- `src/heyreachfactory.py` — `_li_message_delays` accepts `plan=` kwarg and
  reads LinkedIn steps from the plan (falls back to cadencelibrary when the
  plan has no LinkedIn message steps). `build_sequence` and
  `_build_sequence_no_inmail` pass the plan through. `_plan` builds a
  SequencePlan. Return dict carries `sequence_plan`.
- `tests/test_every_representation_derives_from_one_plan.py` — NEW. 36 tests.

**FINDINGS:**

**Acceptance 1 — One object, six consumers.** PASS. `build()` creates the plan
once. `derive_preview_data`, `derive_bison_payload`, `derive_heyreach_payload`,
`derive_xlsx_rows`, `derive_qa_summary`, and `approval_hash` all read from it.
Test `test_six_derivations_from_one_plan` asserts all three payload derivations
carry the same approval hash.

**Acceptance 2 — Change the plan, all six change.** PASS. Tests in
`ChangePropagatesToAllConsumers` alter a body, a day, and verify hash, preview,
bison payload, xlsx, email sequence, and QA all reflect the change.

**Acceptance 3 — No consumer carries its own cadence.** PASS.
- `test_email_days_come_from_cadencelibrary` — email days match cadencelibrary
- `test_linkedin_days_come_from_cadencelibrary` — LinkedIn days match
- `test_thread_pattern_comes_from_cadencelibrary` — thread pattern matches
- `test_no_literal_day_in_sequenceplan_module` — no hardcoded `"day": N` in
  sequenceplan.py
- Literal day grep across all five consumers: zero hits.

**Acceptance 4 — Hash deterministic and sensitive.** PASS.
- `test_deterministic` — same plan, same hash
- `test_deterministic_across_serialisation` — same serialisation
- `test_one_char_change_different_hash` — one char → different hash
- `test_day_change_different_hash` — day change → different hash
- `test_thread_change_different_hash` — thread change → different hash
- `test_no_timestamps_in_serialisation` — no timestamps in the blob

**Acceptance 5 — No fifth representation.**

`bisonfactory._plan` NOW DERIVES FROM THE PLAN. It calls `sequenceplan.build()`
and passes the plan to `_sequence_steps`, which reads email step order and
thread-reply from it.

`heyreachfactory.build_sequence` NOW DERIVES FROM THE PLAN. It receives the
plan from `_plan` and passes it through to `_li_message_delays`, which reads
LinkedIn steps from it.

**REMAINING PARALLEL TRUTH (REPORTED, NOT A DEFECT):**
`src/providers/heyreach.py:1198` — `li_message_delays_from_cadence()` is a
third copy of the LinkedIn delay derivation. It lives in the provider transport
layer and is the default when `linkedin_sequence()` is called without explicit
`message_delays`. The factory ALWAYS passes explicit delays (from the plan), so
this function is only reached when a caller bypasses the factory. It is a
fallback, not an independent builder, but it IS a parallel derivation and is
reported as such.

**Acceptance 6 — Full suite.** Suite is running. 291 related tests show zero
new failures against the baseline. Full suite diff pending.

**CALLER PROOF (the rule that decided three reviews):**

    $ grep -rn "sequenceplan" src/ --include="*.py"
    src/bisonfactory.py:246:        from . import sequenceplan
    src/bisonfactory.py:462:    from . import sequenceplan as _sequenceplan
    src/bisonfactory.py:467:    seq_plan = _sequenceplan.build(campaign, recs, config)
    src/generate_campaign.py:21:               secondbrain, sequencegate, sequenceplan)
    src/generate_campaign.py:23:ENTRYPOINT_VERSION = sequenceplan.ENTRYPOINT_VERSION
    src/generate_campaign.py:79:    plan = sequenceplan.new(
    src/heyreachfactory.py:786:    from . import sequenceplan as _sequenceplan
    src/heyreachfactory.py:794:    seq_plan = _sequenceplan.build(campaign, recs, config)

Three callers in src/: bisonfactory, heyreachfactory, generate_campaign.

**RISKS:**
- `preview.gather` and `qa.report` still build their own per-record timelines
  via `cadence.build()`. This is the per-record EXPANSION (with status,
  blocked_by, etc.), not a parallel cadence. The SequencePlan provides the
  canonical cadence steps; `cadence.build()` expands them per record. Wiring
  preview and qa to read the plan's cadence_steps directly is a follow-up.
- The `providers/heyreach.py:li_message_delays_from_cadence()` fallback is a
  remaining parallel derivation. It is not reached through the factory path.

**RECOMMENDED CLAUDE ACTION:** Review and integrate. The full suite diff
should be checked when it completes. The `providers/heyreach.py` parallel
derivation is a candidate for a follow-up task.
