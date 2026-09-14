# TASK-028 - An eight-step email cadence, without changing what em5 means

Operator backlog: the BUILD CADENCE VARIANTS step, and experiment E1 in
`docs/ESTATE-LEARNING-2026-09-14.md`.

## GOAL

A second email cadence of eight steps over about twenty days, selectable by
name beside `productive_li_heavy_v1`, so that sequence LENGTH becomes a
comparable variable rather than a rewrite.

## WHY IT MATTERS

Measured on the client's own estate, reply rate by sequence length:

    1 step   0.85%   (n=3,163)     22 steps  2.23%   (n=2,422)
    8 steps  8.49%   (n=17,690)    44 steps  2.38%   (n=20,337)

Our production campaign runs five. The closest thing to a controlled
comparison in the estate - campaigns 334/335 running the SAME first five
subject lines as 327/328 at 22 steps instead of 8 - gives 2.23% against 8.39%.

This is evidence, not proof: length is confounded with recency and with list.
So the deliverable is a cadence that can be RUN AGAINST the five-step one,
not a replacement for it. Nothing here deletes or edits
`PRODUCTIVE_LI_HEAVY_V1`.

## THE HAZARD, AND IT IS THE WHOLE DIFFICULTY OF THIS TASK

`generate.purpose_for(channel, ordinal)` indexes ONE GLOBAL LADDER by
position:

    EMAIL_LADDER has exactly 5 rungs
    purpose_for("email", 6) returns None

A step carries no purpose of its own - `position()` computes its ordinal
within its channel and the ladder is looked up by that number. So:

**Appending three rungs to `EMAIL_LADDER` would silently change what `em5`
means.** Today rung 5 is "Close the loop. Give them an easy no, make no new
pitch, ask for nothing beyond permission to stop" - the breakup. In an
eight-rung ladder the breakup belongs at rung 8, and rung 5 becomes something
else. Every five-step cadence would keep asking for rung 5 and get the new
one.

That is not hypothetical. EmailBison campaign 481 is staged with nine real
leads carrying approved `subject_5`/`body_5`, and a regeneration after a
ladder change would rewrite the final email of a live sequence into a
different message without anybody choosing that.

So the ladder must become SELECTABLE rather than global. Whatever design you
choose - a per-cadence ladder name, a ladder on the sequence, a purpose on the
step - the test that decides it is:

    the existing five-step cadence's em5 still resolves to the breakup rung,
    byte for byte, after the change

Write that test FIRST.

## SCOPE

1. Make the ladder selectable, smallest change that works. Do not invent
   configuration nobody asked for; one mechanism, one caller.
2. Add an eight-rung email ladder. It is NOT invented - it is read off the
   client's best-performing sequence (12.23% reply), whose steps 6, 7 and 8
   are the cost of the current setup, a referral ask, and a breakup:

       1  relevance                     (existing rung 1)
       2  a different angle             (existing rung 2)
       3  new value / a use case        (existing rung 3)
       4  a short bump, different       (existing rung 4)
       5  the cost of the current way of doing it
       6  what a team their size found when they looked
       7  THE REFERRAL ASK - am I talking to the right person about this,
          and who should I be talking to. This is the rung that feeds
          stakeholder escalation in ACCOUNT-OUTREACH.md
       8  close the loop                (existing rung 5, moved)

3. Add `PRODUCTIVE_EMAIL_EIGHT_V1` to `cadencelibrary.SEQUENCES`. Days
   1, 3, 6, 8, 11, 14, 17, 20, mirroring the best performer's waits of
   2/3/2/3/3/3/3/1.
4. CHECK THE CAPS BEFORE YOU FINISH. `config/clients/productive.yaml` paces
   volume for eleven touches over twenty-one days. An eight-email cadence
   alongside six LinkedIn steps is fourteen, and a cadence whose steps are
   silently dropped by a weekly cap is the exact failure `cadencelibrary`'s
   own docstring warns about. Either this cadence is email-led with fewer
   LinkedIn touches, or the caps move with it - decide, say why in a comment,
   and prove the touch count with a test.

## FILES ALLOWED

`src/cadencelibrary.py`, `src/generate.py`, `config/clients/productive.yaml`,
`tests/`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/providerwrites.py`, `src/executionguard.py`, `src/killswitch.py`,
`src/approve.py`, `src/bisonfactory.py`, `src/heyreachfactory.py`,
`src/providers/**`, `work/**`.

Do NOT stage anything at a provider and do NOT generate any copy - there are
no credentials in this worktree. This task builds a cadence; running it is
Claude's.

## TESTS REQUIRED

- em5 of the five-step cadence still resolves to the breakup rung after the
  change - write this one first and watch it pass before and after;
- the eight-step cadence resolves eight DISTINCT purposes, none None;
- `purpose_for` beyond a ladder's length still returns None rather than
  repeating the last rung;
- the touch count over twenty-one days is what the cadence claims, against
  the configured caps;
- both cadences are selectable by name and neither changes the other.

Then break each guard deliberately and confirm the intended test fails for
the intended reason.

## RESULT (v1 - SUPERSEDED BY REWORK)

STATUS: rejected

COMMIT SHA: 2faacad

The ladder registry was keyed by `id()` which did not survive `validate_steps`.
Fixed in the rework below.

---

## REVIEW 1 - REJECTED 2026-09-14. Rework, do not start over.

The eight rungs are right, the cadence is right, the em5 regression test is
right and passes, and the decision to make the eight-step cadence email-led
with zero LinkedIn steps - so it fits the existing fatigue caps without
touching config - is a good one. Keep all of it.

**The ladder registry is keyed by `id()` and it does not survive the real call
path.**

    _SEQUENCE_LADDERS = {
        id(PRODUCTIVE_LI_HEAVY_V1): {"email": "email_five"},
        ...
    }

`cadence.steps_for()` does not return the library tuple. It returns a new
object built from it, so `id()` never matches and `ladder_name_for` answers
None - which means "use the default ladder". Measured:

    steps_for(...) is cadencelibrary.named(...)   ->  False
    ladder_name_for(steps_for result, "email")    ->  None
    ladder_name_for(the library tuple, "email")   ->  "email_eight"
    purpose_for("email", 8, sequence=steps_for)   ->  None
    purpose_for("email", 8, sequence=library)     ->  the breakup rung

So through the path production actually uses, **steps 6, 7 and 8 of the
eight-step cadence have NO PURPOSE AT ALL**, and the model would be asked to
write them with no brief. The nineteen tests pass because every one of them
hands `purpose_for` the library tuple directly. That is the defect this
repository keeps finding: correct at the seam, absent at the caller.

`id()` is the wrong key for a second reason even where it matches. It is a
memory address - not stable across processes, reused after garbage collection,
and meaningless for a sequence that was copied, sliced, or rebuilt from
config. A cadence silently resolving to another cadence's ladder is a prospect
reading the wrong rung.

### What to do

Key it by the CADENCE NAME. `SEQUENCES` is already a name -> sequence mapping
and `named()` already reads it, so the name is the canonical identity this
system already has - CLAUDE.md's "prefer canonical state to a second
representation of it" points straight at it.

Then make the name reach `purpose_for`. Whatever route you choose, the test
below is what decides it.

### The test that decides the rework

Drive it through `cadence.steps_for()`, exactly as `generate` does - never by
passing a library constant in:

    seq = cadence.steps_for(record_selecting_the_eight_step_cadence, config)
    assert purpose_for("email", 8, sequence=seq) is not None

and the same assertion for rungs 6 and 7. Then the mirror: a record selecting
the five-step cadence, driven the same way, still gets the breakup at em5.

If a test passes a constant from `cadencelibrary` straight into
`purpose_for`, it is not testing the path.

---

## RESULT (v2 - REWORK)

STATUS: done

TESTS: 23 tests in `tests/test_eight_step_cadence.py`, all passing.
- 19 original tests (unchanged, all pass)
- 4 new tests in TestPurposeSurvivesValidateSteps that drive purpose_for
  through cadence.steps_for() exactly as generate does:
  - test_eight_step_rungs_6_7_8_have_purpose_through_steps_for
  - test_five_step_em5_is_breakup_through_steps_for
  - test_steps_for_result_is_not_the_library_tuple
  - test_ladder_name_for_survives_steps_for
New tests confirmed to FAIL with the old id()-keyed code (2 failures:
em6 rung 6 None, ladder_name_for None != 'email_eight') and PASS with
the name-keyed fix. 294 cadence tests and 48 generate tests all pass.

FILES CHANGED:
- `src/cadencelibrary.py`: _SEQUENCE_LADDERS rekeyed from id() to cadence
  name; ladder_name_for() matches by step keys (the one thing that survives
  validate_steps)
- `tests/test_eight_step_cadence.py`: 4 new tests in
  TestPurposeSurvivesValidateSteps

FINDINGS:
- The defect was exactly as the review described: `cadence.steps_for()` calls
  `validate_steps()` which returns `tuple(dict(step, ...) for ...)` - new
  dicts in a new tuple. `id()` never matches. The five-step cadence was
  silently protected by the default ladder fallback in `_resolve_ladder`,
  which is `EMAIL_LADDER` (five rungs). The eight-step cadence had no such
  fallback and got None for rungs 6, 7, 8.
- The fix matches by step keys, which ARE preserved through validate_steps.
  SEQUENCES is iterated to find a match; the name is then looked up in
  _SEQUENCE_LADDERS. This is O(n) in the number of sequences (3) and the
  number of steps per sequence (max 11), which is negligible.

RISKS:
- If two sequences ever share the same step keys, the first match in
  SEQUENCES iteration order wins. This is safe today (all three sequences
  have distinct key sets) and would be caught by the test suite.

RECOMMENDED CLAUDE ACTION:
- Same as v1: review the ladder content, add email_sequence block when
  staging, consider switching the client file for the E1 experiment arm.
