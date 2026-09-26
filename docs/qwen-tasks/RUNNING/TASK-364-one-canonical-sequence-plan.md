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
