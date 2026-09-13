# TASK-007 - Finish the suite repair

## GOAL

Take the full suite from ~69 failures to as close to zero as the evidence
honestly allows, and classify every one that remains.

## WHY IT MATTERS

TASK-001 established the suite has never been green: 8093 tests, 60 failures,
74 errors. Claude fixed 65 of the 134 and the pattern is proven. The rest is
mechanical for most of the remaining modules and genuinely interesting for a
few, and a suite nobody can read a verdict from is a suite that hides the
next real defect.

## CURRENT CONTEXT - READ THIS BEFORE TOUCHING ANYTHING

The dominant cause is ONE thing. Commit `ee254e1` switched Productive to
`productive_li_heavy_v1` - steps `em1`..`em5` and `li1`..`li6` - and a great
many tests call `clients.load("productive")` while holding a fixture whose
stored cadence is keyed `day1`, `day3`, `day5`. Symptoms:

    NotApprovable: meridian:ivana-saric:day1: no such step
    KeyError: 'day1' / 'day3' / 'li2'
    AssertionError: 'blocked:agency_dnc' not found in ['skipped:no_such_step']
    AssertionError: 'li1' != 'day3'

`tests/base.py` now carries two helpers, both already used:

- `fixture_config(client="productive", **over)` - the client config with the
  cadence its own fixtures were built for, `productive_balanced_v1`, whose
  keys are exactly `day1`..`day21`. Enough for anything that TAKES a config.
- `pin_client_config(test, ...)` - patches `clients.load` for the test and
  registers its own cleanup. Needed whenever the module under test loads the
  client file itself, which `push.run` and `approve.pending` both do.

Worked examples to copy, in increasing order of subtlety:

    tests/test_push.py                          one line in setUp
    tests/test_approve.py                       one line in setUp
    tests/test_double_verification.py           EVERY setUp, not just the
                                                first - a second class called
                                                `clients.load` inside a test
                                                body and stayed red
    tests/test_the_agency_list_reaches_the_send_gate.py
                                                no `super().setUp()` to
                                                anchor on; placed by hand
    tests/test_the_cadence_reacts_to_what_the_prospect_did.py
                                                the OPPOSITE - see below

## THE TRAP, AND IT IS THE WHOLE POINT OF THIS TASK

**Do not pin a test that is about the live cadence.** Pinning makes red go
away; that is exactly why it is dangerous.

`tests/test_the_cadence_reacts_to_what_the_prospect_did` is about the
LinkedIn-heavy branch. Its base class `CampaignTest` loads client `demo`,
whose cadence is the default `day1`..`day21`, while every record in it is
Productive's and every assertion names `li1`, `li2`, `em1`. Its `KeyError:
'li2'` was a timeline CORRECTLY having no such step. It needed
`clients.load(WS)` - the live config - not a pin. Pinning it would have
hidden the thing it exists to test.

Before pinning any module, answer in one sentence: what is this module about?
If the answer mentions the cadence, the sequence, `li*`/`em*` steps, or the
branch, do not pin it - give it the client that runs that cadence instead.

## SCOPE

1. Run `py -3 scripts/run_suite.py --offline --timeout 7200`. It reports the
   real exit code. That is the starting number.
2. Work module by module. For each: state what the module is about, choose
   pin or live-config, apply, re-run that module alone.
3. Some failures are NOT this class. Three are already known and are NOT
   yours to fix - record them and move on:
   - `test_a_finished_campaign_with_no_reply_still_authorizes` - the
     account-collision gate refuses an account whose campaigns are all
     `stopped`/`sequence_finished` with zero replies, and the test says
     history is not a live conflict. A policy disagreement on a send path.
   - `cadence.build` omits `li2` for a contact whose connection has not
     landed, where the test expects it present with status `waiting`.
   - the state machine answers `linkedin:step_requirement_unmet` where
     `linkedinstate.HELD_REQUEST_OUTSTANDING` exists and nothing produces it.
4. `tests/test_fixture_hygiene` is its own thing entirely - it flags real
   strings in `src/` and `tests/`. Diagnose it separately and report.
5. Re-run the full suite at the end and record the honest number.

## FILES ALLOWED

`tests/**`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/**` - every remaining failure is either a test that asks about a world
that no longer exists, or a real defect somebody needs to decide about. Both
are findings. `work/**`. `config/clients/**`.

## PRODUCTION CONSTRAINTS

Offline. No provider calls. One test process at a time.

## TESTS REQUIRED

No new behaviour, so no new tests - but for EVERY module you touch, re-run it
alone and record before/after counts in the result. A module you changed and
did not re-run is not done.

## EXPECTED OUTPUT

A table of module, what-it-is-about, pin-or-live, before, after. The final
full-suite number. A list of everything not green with a classification:
`fixture-was-stale` (fixed), `real-defect` (reported), or `undiagnosed`.

## DONE CONDITION

The full suite's number is smaller, every module you touched was re-run
alone, and nothing was pinned that should not have been - which you can show
by naming, for each pin, what the module is about.

## RESULT

STATUS: TODO
COMMIT SHA:
TESTS:
FILES CHANGED:
FINDINGS:
RISKS:
RECOMMENDED CLAUDE ACTION:
