PRIORITY: P0
DEPENDS:

# TASK-184 - rehearse the write Claude is about to perform

## WHERE THIS SITS

Claude intends to perform one provider write, using only verbs already
authorized in `providerwrites.SUPPORTED`:

    bison.create_campaign    create a NEW email campaign
    bison.set_sequence       write the CONTROL sequence onto it

TASK-174 established why it must be a new campaign rather than 481: 481 holds
23 people, all with 6 to 40 historical touches, under a five-step sequence that
is not CONTROL - and `set_sequence` **APPENDS rather than replaces**, measured
2026-09-13, so writing CONTROL onto it would leave the campaign carrying both
plans. `bison.set_sequence` is authorized on the stated grounds that a sequence
written onto a campaign holding nobody reaches nobody, and that premise holds
for a new campaign and fails for 481.

`bison.add_lead` and `bison.activate` are NOT authorized, so the write stops
there by design: a campaign that exists, carries the audited CONTROL sequence,
holds nobody and cannot send.

This task rehearses that write end to end against a FAKE provider, so the real
one is the second time the code path runs, not the first.

## THE QUESTION

1. **Find the real path.** Which module creates a campaign and which writes a
   sequence - `bisonfactory`, `push`, `campaigns`? Do not hand-roll an HTTP
   call; the point is to exercise the path that carries the gates, the action
   ledger and the spend ledger. Name the entry point Claude should call, with
   its arguments.
2. **What name will the campaign get?** 481's name is
   `RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - BUYER - LIHEAVY-V1
   [productive/productive-email-liheavy-v1]`, and TASK-170's identity check
   initially failed because it compared against a name without the derived
   suffix. Establish what the factory derives for the CONTROL cohort, and make
   sure the identity check will recognise it.
3. **Rehearse it against a fake transport.** Create, set sequence, read back.
   Assert: the campaign is created holding zero leads; the sequence written is
   the three CONTROL steps with threading F/T/F and the `thread_reply` booleans
   in the right positions; the readback returns what was written; and a second
   `set_sequence` call APPENDS, which is the behaviour to prove rather than
   assume, because it decides whether the write is idempotent. **It is not, if
   it appends - so establish what happens if the write is retried.**
4. **The retry question, answered.** If Claude's write fails halfway - campaign
   created, sequence write times out - what is the correct recovery? A blind
   retry appends a second copy of the sequence. Write the procedure down as
   steps a person can follow, and a check that distinguishes "sequence written
   once" from "sequence written twice".
5. **Wire TASK-170's pre-write check to the new campaign id.** It currently
   targets 481. It must take the campaign id as input, and for a
   not-yet-created campaign its identity check has nothing to read - say what
   it should do then, and make it fail closed rather than pass vacuously.

## THE TRAP

`set_sequence` appending is the single most dangerous fact in this task. Every
instinct on a failed write says retry, and retrying this one produces a
campaign carrying the CONTROL sequence twice - which, once leads are eventually
added, is a prospect receiving six messages instead of three. Make the
idempotency answer impossible to miss in the deliverable.

Second trap: do not perform the real write. Not one call. The rehearsal is
against a fake, and the real write is Claude's, after reading what you found.

## WHAT YOU MAY NOT DO

- **No provider writes. No real create_campaign, no real set_sequence.** Fake
  transport only. Reads against the provider are allowed if you need the
  factory's naming inputs.
- Do not add anything to `SUPPORTED` or `CONDITIONAL`. Do not touch
  `bison.add_lead` or `bison.activate`.
- Do not modify campaign 481 in any way.
- Do not break TASK-170's 32 tests; if you change that script, they stay green
  and you say what you changed.
- Never commit an email address, a name, a domain or a key.

## FILES ALLOWED

    tests/test_bison_campaign_write.py   (new)
    scripts/bison_prewrite_check.py      (to take a campaign id)
    tests/test_bison_prewrite_check.py
    docs/BISON-WRITE-REHEARSAL-2026-09-16.md   (new)
    scripts/task184_*.py

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 879364d

**TESTS:**
- `tests/test_bison_campaign_write.py`: 15 tests, all pass
- `tests/test_bison_prewrite_check.py`: 35 tests (32 original + 3 new), all pass
- `tests/test_staging_a_campaign_twice_builds_one`: 17 tests, all pass (regression check)
- `tests/test_a_five_step_campaign_sends_five_different_emails`: 11 tests, all pass (regression check)
- `tests/test_crash_restart_idempotency`: 7 tests, all pass (regression check)

**FILES CHANGED:**
- `tests/test_bison_campaign_write.py` (new) — 15 rehearsal tests
- `tests/test_bison_prewrite_check.py` (modified) — 3 new tests for pre-creation case
- `scripts/bison_prewrite_check.py` (modified) — fail-closed for not-yet-created campaigns
- `docs/BISON-WRITE-REHEARSAL-2026-09-16.md` (new) — full documentation

**FINDINGS:**

1. **The entry point is `bisonfactory.stage(campaign_id, live=True)`.** It carries the gates, action ledger and spend ledger through `providerwrites.perform`. NOT a hand-rolled HTTP call.

2. **The derived campaign name is `{human} [{client}/{campaign_id}]`.** For the CONTROL cohort: `RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - CONTROL [productive/control-rehearsal]`. The identity check uses `bisonfactory.provider_campaign_name()` so it tracks the derivation automatically.

3. **The CONTROL sequence is three steps with threading F/T/F:** persona_pain (F), comparable_proof (T), breakup (F). Waits: 3, 4, 0 (last unchecked).

4. **`bison.set_sequence` APPENDS. PROVEN.** A second write produces 6 steps, not 3. The provider renumbers orders across writes. There is no replace verb and no per-step delete route.

5. **The brake is `_ensure_sequence`:** it reads `bison.sequence_steps()` BEFORE writing. Identical steps → skip. Different steps → FactoryRefused. This prevents the append trap in production.

6. **Recovery procedure for half-failed write:**
   - Read `bison.sequence_steps(provider_id)` FIRST
   - Empty → safe to write
   - 3 correct steps → already done, do NOT write again
   - 6 steps → append trap fired, delete campaign and rebuild
   - Other → investigate

7. **Pre-write check now fails closed for not-yet-created campaigns.** No `bison_campaign_id` → exit code 1, clear reason, local checks still run.

**RISKS:**
- The append behaviour is structural at the provider. Any code path that calls `bison.set_sequence` without reading first will double the sequence. The `_ensure_sequence` brake is the only protection.
- A crash between `create_campaign` and `_bind` leaves an orphan campaign. Recovery is by name lookup (`find_campaigns_by_name`), which is wired and tested.

**RECOMMENDED CLAUDE ACTION:**
Review the rehearsal documentation at `docs/BISON-WRITE-REHEARSAL-2026-09-16.md`. The entry point, derived name, sequence shape, recovery procedure and append trap are all documented with test evidence. The pre-write check now handles the pre-creation case. Ready for the real write when Claude decides.

## FILES FORBIDDEN

    src/providerwrites.py   work/   config/

## DELIVERABLE

The exact entry point and arguments Claude should call, the derived campaign
name, the rehearsal green against a fake with the append behaviour proven, the
written recovery procedure for a half-failed write with its once-or-twice
check, and the pre-write check taking a campaign id and failing closed on a
campaign that does not exist yet.
