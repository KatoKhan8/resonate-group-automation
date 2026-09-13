# TASK-005 - Crash the staging path at every seam and prove what survives

## GOAL

For each point at which a staging run can die, a test that says exactly what
the next run does: recovers, refuses as ambiguous, or silently duplicates.

## WHY IT MATTERS

This has already happened for real. `src/bisonfactory.py` carries a measured
note from 2026-09-13: a crash between the POST and the persist left a
provider campaign no local state named, and the next run built a second one -
two campaigns, byte-identical names. The fix (a derived
`provider_campaign_name`, looked up before creating) is in. Nothing proves it
holds at the OTHER seams.

## CURRENT CONTEXT

`bisonfactory.stage()` runs, in order:

    _find_or_create -> _ensure_limits -> _ensure_schedule -> _ensure_senders
    -> _ensure_sequence -> _ensure_stopped -> _ensure_leads -> _readback

Two properties that make this delicate and are already documented in the
module: the sequence route APPENDS and has no replace and no delete, so a
second sequence write leaves a campaign that sends twice; and a lead attached
to a campaign that has not been stopped reads `in_sequence` at once, and an
`in_sequence` lead cannot be attached anywhere else.

`_remember_lead` writes the provider's lead id in its own transaction,
immediately, for the same reason.

## SCOPE

Using a FAKE transport - never the real provider - inject a failure after
each of those calls and after each individual lead within `_ensure_leads`,
then re-run `stage()` against the state the crash left behind. For each seam
record which of these it is:

    RECOVERS      the second run reaches the same end state
    REFUSES       the second run raises FactoryRefused/FactoryAmbiguous with
                  a reason a human can act on
    DUPLICATES    the second run creates a second something - a DEFECT

Pay particular attention to:
- a crash between `set_sequence` returning and the readback (does the second
  run see a sequence it does not recognise and refuse, per the module's
  stated contract?)
- a crash after `create_lead` but before `_remember_lead`
- a crash between `_ensure_stopped` and `_ensure_leads`

## FILES ALLOWED

`tests/`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/**` - report defects, do not fix them. `work/**` - the fake estate lives
in a temp directory. Never point a test at the real `work/campaigns.jsonl`.

## PRODUCTION CONSTRAINTS

ZERO real provider calls. EmailBison campaign 451 is production evidence with
a scheduled send on it; nothing in this task may touch it, and a test that
reaches the network at all has failed regardless of its assertion. Use the
fake transport the existing tests already use.

## TESTS REQUIRED

One test per seam, named for the seam. A DUPLICATES verdict is written as a
failing test with a name that states the defect.

## EXPECTED OUTPUT

A seam-by-seam table in this file, plus the test module.

## DONE CONDITION

Every seam in `stage()` has a named verdict backed by a test.

## RESULT

STATUS: TODO
COMMIT SHA:
TESTS:
FILES CHANGED:
FINDINGS:
RISKS:
RECOMMENDED CLAUDE ACTION:
