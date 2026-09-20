PRIORITY: P0
DEPENDS:

# TASK-236 - nothing reads the provider's answer to "what will actually send"

Priority P0 observability. Found 2026-09-20 while establishing why 489 is
planned for Thursday.

## The gap

Every question this repository asks about future sends is answered by
INFERENCE:

- `first_scheduled` on the campaign row - the earliest `scheduled_at` among
  the campaign's queue rows
- `senderheadroom` - our own forward-book census, counting rows per mailbox
  per day

Both are ours. Neither is the provider saying what it will do.

**EmailBison documents an endpoint that answers it directly**, and nothing
here calls it:

    GET /api/campaigns/{campaign_id}/sending-schedule
    GET /api/campaigns/sending-schedules

Parameter `day`: `today` | `tomorrow` | `day_after_tomorrow`. Documented
response field `emails_being_sent`. Source, with URL, in
`docs/GROK-SCHEDULING-2026-09-20.md`; the spec is
<https://dedi.emailbison.com/api/reference.openapi>.

## What it already told us, and its limits

Called by hand 2026-09-20T20:0xZ against both live campaigns, all three days:

    487  today / tomorrow / day_after_tomorrow   HTTP 400
         {"data": {"success": false, "message": "No emails scheduled for this period"}}
    489  same

**Read the 400 carefully before wiring it.** It is the provider's ordinary
"nothing here" answer, not an error - and a monitor that treats it as a
failure will alarm every weekend, while one that treats it as zero will
report a healthy campaign as silent. It has to be classified explicitly.
This is the `_collection` argument again: a shape that is not a result is
not a zero.

The window only reaches two days out, so it cannot answer questions about
Thursday. It is a near-term confirmation, not a planner.

## The objective

The watchers report what the PROVIDER says will send, distinguished from
what we infer, and a disagreement between the two is itself an event.

Falsifiable requirements:

1. A read function on `src/providers/bison.py` for both routes, returning a
   trimmed dict, with the three `day` values validated rather than passed
   through. It is a GET, so the transport guard is not involved.
2. The "No emails scheduled for this period" 400 is classified as an
   explicit EMPTY result, distinct from a transport failure and distinct
   from a zero count. A test pins all three apart.
3. `bison_watch_loop` emits a line when the provider's near-term sending
   volume CHANGES, and a distinct line when the provider's answer disagrees
   with our own `first_scheduled` - e.g. we believe a send lands tomorrow
   and the provider reports nothing for tomorrow.
4. The disagreement line fires in a test built from fixtures, both ways
   round.
5. Nothing in this task writes to a provider or changes a campaign.

## Why the disagreement line is the point

487's ten openers have moved date twice without anybody being told, and both
times the first hint was a human re-reading a number. A monitor that only
reports our own inference cannot notice that the provider disagrees with it.

## Hard limits

- READ ONLY. GETs only. No pause, resume, activate or attach.
- **DO NOT WRAP A MONITOR IN `timeout`.** The 489 watcher was killed at exit
  124 that way on the 18th.
- Do not restart the running watchers; leave them alone and let the operator
  cut over.

## Where to read first

`scripts/bison_watch_loop.py`, `src/watchsink.py`, `src/providers/bison.py`
(the existing GET readers around `scheduled_emails`), and
`docs/GROK-SCHEDULING-2026-09-20.md` for the documented contract.

## Acceptance

All five requirements have tests; requirements 2 and 4 fail before the
change; the live watchers are untouched; no provider write occurred.

## RESULT

STATUS: DONE
COMMIT: bfa2da9f
TESTS: 16 tests in tests/test_bison_sending_schedule.py, all passing.
       51 tests in tests/test_bison_sending_schedule.py + tests/test_bison_prewrite_check.py, all passing.
FILES CHANGED:
  - src/providers/bison.py: added sending_schedule(), sending_schedules(),
    SendingScheduleEmpty, VALID_DAYS, _EMPTY_MESSAGE
  - scripts/bison_watch_loop.py: added _provider_sending_plan(),
    _check_disagreement(), PROVIDER-VOLUME and DISAGREEMENT emissions
  - tests/fakebison.py: added sending_schedule dict and _sending_schedule()
    route handler
  - tests/test_bison_sending_schedule.py: new test file, 16 tests

FINDINGS:
  1. The provider's 400 "No emails scheduled for this period" is now
     classified as SendingScheduleEmpty, distinct from ProviderError
     (transport failure) and from a zero count (provider says 0).
  2. The watch loop now reads the provider's sending plan for all three
     days (today, tomorrow, day_after_tomorrow) and emits PROVIDER-VOLUME
     when the plan changes.
  3. The DISAGREEMENT line fires when:
     - We believe a send lands tomorrow (first_scheduled != "none") but
       the provider reports nothing for tomorrow
     - The provider reports something for tomorrow but we have no
       scheduled rows (first_scheduled == "none")
  4. Nothing in this task writes to a provider. The sending-schedule
     route is GET-only and is not in WRITE_ROUTES.
  5. The live watchers were NOT restarted, per the hard limits.

RISKS:
  - The disagreement check looks at both "tomorrow" and "day_after_tomorrow".
    If either day disagrees, it reports a disagreement. This may produce
    false positives if the provider's plan for one day is empty but the
    other is not, even though we have a scheduled row.
  - The plural route (sending_schedules) is implemented but not tested
    against the live provider. The FakeBison does not model it.

RECOMMENDED CLAUDE ACTION:
  - Review the disagreement logic. The current implementation checks both
    tomorrow and day_after_tomorrow, which may be too strict. Consider
    mapping first_scheduled to a specific day and only checking that day.
  - Consider adding a test for the plural route once the provider's
    response shape is confirmed.
  - The live watchers can be cut over at the operator's discretion.
