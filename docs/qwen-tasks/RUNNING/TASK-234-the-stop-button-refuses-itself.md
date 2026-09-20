# TASK-234 - the stop button refuses itself on the second press

## The defect

`scripts/nudge_487_scheduler.py` performed a pause on 2026-09-17T10:33:18Z
with payload `{'campaign_id': 487}`. That recorded fingerprint
`c879dc1ddd133e34` on the canonical row.

`material_fingerprint({'campaign_id': 487})` recomputes to **exactly**
`c879dc1ddd133e34`. So the NEXT pause of campaign 487 is refused as a repeat
**before the transport is called**, by `providerwrites.perform`'s
staging-repeat guard.

`orchestrator._perform_pause` catches that into
`{'stopped': False, 'error': 'WriteRefused'}` while `pause()` has ALREADY set
`campaign['pause']` and canonical status PAUSED.

**So the emergency stop reports stopped and does not stop.** Canonical state
says PAUSED, the provider is still sending, and the audit row's reason string
is stale and wrong - it says no pause route is supported, when the route IS
in `SUPPORTED` and was refused by our own idempotency guard.

`bisonfactory._ensure_stopped` explicitly refuses to pause a started campaign
and points at `orchestrator.pause`, so there is no second wired stop path.

## Why `staged_already` is the wrong oracle here

It is right for a CREATING verb: creating the same campaign twice is a
duplicate and must be refused. It is wrong for a **state-SETTING** verb.
Pausing an already-paused campaign is not a duplicate, it is a no-op that
should succeed - and pausing a campaign that has since been RESUMED is a
completely different act that happens to carry the same payload.

The fingerprint is over the PAYLOAD. For a setter the payload is identical
every time by construction, so the guard can only ever fire.

## The objective

An authorized emergency stop of a currently ACTIVE campaign must reach the
provider, however many times the campaign has been paused before.

Falsifiable requirements:

1. Seed the matching fingerprint on the canonical row, call
   `orchestrator.pause(..., provider=True)` against a fake transport, and
   assert BOTH that `provider_stop['email']['stopped'] is True` AND that the
   transport actually recorded a call. **This test fails today** - write it
   first and watch it fail before changing anything.
2. Repeated pause: two pauses in a row both reach the provider and both
   report truthfully. The second is a no-op at the provider and must NOT be
   reported as a refusal.
3. Pause after resume: pause, resume, pause again. The third act reaches the
   provider.
4. **Local state must not read PAUSED until the provider is reconciled.**
   Today `pause()` sets `campaign['pause']` and canonical PAUSED before the
   provider call's outcome is known. A stop that was refused must leave
   canonical state saying so.
5. Ambiguous provider response - a 200 whose readback does not confirm
   `paused` - must NOT be recorded as stopped. Fail closed.
6. Provider refusal (4xx/5xx) must surface, not land in a dict field nobody
   renders. State where it surfaces.
7. Local/provider disagreement - canonical says PAUSED, provider says active
   - must be detectable. A function that answers it is enough; wiring a
   monitor is out of scope.

## The shape of the fix, and the choice is yours to justify

Two candidates, both named in the audit:

A. Declare `repeatable` in `OPERATIONS` - pause/stop/activate/assign_sender
   YES, create/set_sequence NO - so the staging-repeat guard applies only to
   creating verbs.
B. Ask the provider what it holds, as `bisonfactory._ensure_campaign`
   already does. `_perform_pause` already passes
   `expected={'status': 'paused'}`.

Pick one, implement it, and write down in FINDINGS why the other was not
chosen. Do not do both.

## Explicitly NOT in scope

- Do NOT make any real provider call. The transport now refuses
  prospect-facing mutations without an explicit opt-in
  (`providers.refuse_unauthorized_write`); do not reach for that opt-in, and
  do not add it to any library. Use a fake transport.
- Do NOT touch campaign 487, 489 or 605732 in any way. 487 is mid-incident.
- Do NOT change `material_fingerprint` itself. Other callers depend on it and
  it is correct for creating verbs.
- Do NOT widen `SUPPORTED` or `WRITE_ROUTES`.
- Do not touch `src/providers/__init__.py`.

## Files you own

    src/providerwrites.py
    src/orchestrator.py
    tests/test_an_emergency_stop_is_not_refused_by_its_own_history.py  (new)

If the work appears to need another file, stop and write why under FINDINGS.

## Invariants

- Dry run is the default for anything that sends or stops. `--live` explicit.
- No silent fallbacks on a safety path: classify explicitly and fail closed.
- `work/` is production state and is never written by a test.
- Test behaviour, not the text of the source.
- A red test is not proof by itself: when you break the fix deliberately,
  confirm the INTENDED test failed for the intended reason and that a
  different guard did not fire first.

## Result block, required

    STATUS
    COMMIT SHA
    TESTS              named modules, actual pass/fail counts
    FILES CHANGED
    FINDINGS           including WHY you chose A or B
    RISKS
    RECOMMENDED CLAUDE ACTION

## Provenance

Buggie audit 2026-09-20, finding #1, graded CRITICAL. Its panel upheld both
the reproduction (the transport recorded zero calls) and the reachability.
The reproduction there was read-only. Reproduce it yourself against a fake
transport before you fix it.
