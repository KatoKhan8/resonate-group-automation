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

## NOTE — real WIP exists on a branch, 2026-09-26 evening

A prior attempt got partway before being reassigned: `derive_xlsx_data()` and
`qa_validate()` were added to `src/sequenceplan.py` on commit `59f8647f`,
branch `qwen-worker-4-r9` (pushed). **Read that commit before starting from
scratch** - it may be usable as-is or need only the factory-consumer wiring
this task actually asks for. Not yet reviewed by Claude; verify it does what
it claims before building on it.

## REWORK 2026-09-27 — GLM BLOCKED this, 4 of 6 acceptance criteria fail

**GLM first-pass verification (TASK-401, commit 778e8724 on
`qwen-worker-r9`): BLOCKED — NOT SAFE TO MERGE.** The canonical SequencePlan
object and its derive functions are correct in isolation
(`approval_hash()` passes a mutation test) but this is the TASK-029
pattern: correct code, absent wiring, green tests.

**The four failed criteria, named:**

1. **`bisonfactory._plan()` (line 428) and `heyreachfactory.build_sequence()`
   (line 587) do NOT import `sequenceplan`.** Zero hits in both files, on
   master and at the branch's own completion commit. The production
   factories still build their payloads independently — the plan is
   decorative.
2. **`derive_xlsx_data()` and `qa_validate()` do not exist on master.** Two
   of the six consumers this task's own acceptance names were never
   implemented outside the worker's own branch.
3. **The derive functions are called only by tests**, never by the
   production factories. No production code path reaches them.
4. **The existing tests assert the WRONG thing** — they confirm the
   parallel builders (`bisonfactory`/`heyreachfactory`'s own payload
   construction) still exist and pass, which is the opposite of what
   "SequencePlan is the one canonical representation" requires. A green
   suite here proves the old, uncanonical path still works, not that the
   new one is used.

## What the rework must do

1. Implement `derive_xlsx_data()` and `qa_validate()` in
   `src/sequenceplan.py` (real WIP from an earlier attempt exists at commit
   `59f8647f` on `qwen-worker-4-r9` — GLM's disposition marks it SUPERSEDED
   by a later commit `3213472f`; read both before choosing which to build
   from, do not assume the newer one is complete just because it is newer).
2. Wire `bisonfactory._plan()` to call `sequenceplan.derive_bison_payload()`
   — or, if keeping a separate builder is deliberate, remove
   `derive_bison_payload()` rather than leave a second, uncalled
   implementation of the same thing. Same choice for
   `heyreachfactory.build_sequence()` and `derive_heyreach_payload()`.
3. **Write the negative control TASK-029's own pattern requires**: a test
   that drives through the PRODUCTION factory (not `sequenceplan` directly),
   asserts the derive function's output reached the provider payload, then
   breaks the wiring and confirms THAT test fails. A test proving the
   derive function works in isolation does not close this gap.
4. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against the current baseline.

## What this rework may NOT do

- Do not remove `bisonfactory`/`heyreachfactory`'s own payload logic without
  first proving `sequenceplan`'s derive functions produce an identical
  payload for real existing test fixtures — a silent behavior change in the
  production write path is a P0 regression risk this task must not create.
- Nothing sent, nothing activated. Production freeze.

---

## REQUEUED BY CLAUDE, 2026-09-27

Requeued because a worker branch held this task in REVIEW with a commit newer
than master's, which made `claim_task.py` classify it as active work and hid it
from every sweep. Rewriting master's copy is the documented re-queue mechanism:
master's timestamp now beats every branch's, so the task is dispatchable again.

**The four failed criteria from TASK-401 stand exactly as written above.** GLM's
verdict was BLOCK, "dead code, TASK-029 pattern". The two independent builders
it named are the whole job:

    src/bisonfactory.py       _plan                 around line 428
    src/heyreachfactory.py    build_sequence        around line 587

and `sequenceplan` is imported by neither. Until both consume one plan, preview,
XLSX, approval hash and both provider payloads are separate implementations of
the same thing, which is what criterion 5 refuses.

**Verify before you start**, because two of this repository's recurring defects
apply here: check whether an earlier branch already did part of this (the work
may exist unintegrated, as TASK-400's did), and do not trust a tip commit message
that says DONE. Read the code on master.

Acceptance is by effect: change the one SequencePlan and prove BOTH provider
projections change. A test asserting that both modules import the same symbol is
not evidence.
