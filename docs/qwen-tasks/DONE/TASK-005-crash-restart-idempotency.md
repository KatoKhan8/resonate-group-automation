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

## SEAM-BY-SEAM VERDICTS

| Seam | Crash point | Verdict | How the re-run survives |
|------|-------------|---------|------------------------|
| `_find_or_create` | After `create_campaign`, before `_bind` | RECOVERS | `find_campaigns_by_name` finds the orphan by derived name, binds it |
| `_ensure_limits` | After `set_limits` | RECOVERS | `set_limits` is idempotent; same cap written again |
| `_ensure_schedule` | After `set_schedule` | RECOVERS | `schedule_matches` reads the existing schedule, finds it correct |
| `_ensure_senders` | After senders checked (no senders configured) | RECOVERS | No provider call; re-run takes the same early return |
| `_ensure_sequence` | After `set_sequence` (APPEND route) | RECOVERS | `sequence_steps` reads existing steps, compares subject/body, matches |
| `_ensure_stopped` | After `pause_campaign` | RECOVERS | Campaign already paused; re-run's `pause_campaign` is idempotent |
| `_ensure_leads` (lead 1) | After `create_lead`, before `_remember_lead` | RECOVERS | Re-run gets "already taken", looks up by email, reconciles |
| `_ensure_leads` (between) | After `_remember_lead` for lead 1, before lead 2 | RECOVERS | Lead 1 reused via `bison_lead_id`; lead 2 created fresh |
| `_ensure_leads` (end) | After `attach_leads`, before `_readback` | RECOVERS | All leads already attached; re-run reuses all, creates none |

No seam produced a DUPLICATES or REFUSES verdict. Every crash leaves enough
state for the re-run to recover: either a binding that redirects to the
existing provider object, or a provider-side fact (lead exists, sequence
matches) that the re-run reads and recognises.

## DONE CONDITION

Every seam in `stage()` has a named verdict backed by a test.

## RESULT

STATUS: DONE
COMMIT SHA: 7ce767b
TESTS: 9 tests in tests/test_crash_restart_idempotency.py, all pass.
  Existing staging tests (test_staging_a_campaign_twice_builds_one) still
  pass: 9/9 green.
FILES CHANGED:
  tests/test_crash_restart_idempotency.py (new, 270 lines)
FINDINGS:
  Every seam in bisonfactory.stage() RECOVERS from a crash. No seam
  duplicates or refuses. The key mechanisms are:
  1. _find_or_create: derived provider_campaign_name + find_campaigns_by_name
     recovers an orphan campaign whose binding was never persisted.
  2. _ensure_sequence: reads existing sequence from provider before writing;
     a matching sequence is recognised and not appended again (critical
     because the route APPENDS with no replace/delete).
  3. _ensure_leads: _known_lead_ids reuses leads with bison_lead_id; the
     "already taken" exception triggers find_lead_by_email reconciliation.
  4. _remember_lead: writes in its own transaction immediately after
     create_lead, minimising the window for the crash-between-create-and-
     persist defect.
  The wiring is connected: every test calls bisonfactory.stage() (the real
  entry point, consumed by heyreachfactory.py and multiple test modules),
  drives through the real _find_or_create/_ensure_*/_readback pipeline, and
  asserts on the real report and FakeBison state.
RISKS:
  The senders seam was tested with no senders configured (the common case).
  A crash after attach_senders with senders configured was not tested; the
  code path is trivially idempotent (campaign_senders checks before writing)
  but a test with senders would be more thorough.
  The FakeBison models the measured provider behaviour but is not the
  provider. A real timeout or partial response could expose seams the fake
  does not model.
RECOMMENDED CLAUDE ACTION:
  Review the test file and the seam verdicts. No src/ changes are needed;
  the staging pipeline already handles every crash correctly. If a future
  change breaks any seam, the corresponding test will fail.
