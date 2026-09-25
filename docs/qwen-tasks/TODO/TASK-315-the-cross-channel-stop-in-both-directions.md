PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-315 — the cross-channel stop, both directions, tested

Operator directive, `docs/OPERATOR-DIRECTIVES-2026-09-25.md` section 5.

## What is known, so you do not re-derive it

**LinkedIn reply -> email stop: MEASURED AND WORKING.** 7.7 minutes on
2026-09-23, and 4m02s on 2026-09-25 by `reply_watch_loop.py`.

**Email reply -> LinkedIn stop: NOT VERIFIED.** `StopLeadInCampaign` returns
404 for a lead HeyReach's own `GetLeadsFromCampaign` reports as present and
`InSequence`. Three identifier shapes were tried; `profile.linkedin_id`
(687232001) is the one that answered 200 in a later test, while
`linkedInUserProfileId` (the ACoAA... value HeyReach support named) 404s.

**Do not label this production-ready.** The operator has asked for that
specifically.

## Build

Synthetic-event tests for both directions covering: contact identity matching
across providers, account-level resolution, reply ingestion, classification,
pending-step cancellation, provider removal or pause, **duplicate webhook
handling**, retries, delayed events, race conditions, suppression propagation,
and audit logging.

**THE TEST THAT MATTERS MOST.** A reply is not processed because a row
changed. `leadstop` once had `readback=lambda: {"stopped": True}` - a constant
identical to `expected`, so the readback ACCEPTED every time and could not
fail. Write the test that fails when a stop is reported without the provider
confirming it.

## Rules

- Synthetic events and safe integration tests. **No live provider writes
  without separate authorisation**, and never against an active campaign.
- Mocked provider responses are not proof of provider behaviour. Say which
  scenarios are covered by tests and which are LIVE VALIDATION REQUIRED.

## Acceptance

    py -3 -m unittest tests.test_a_reply_stops_the_other_channel

plus a table: scenario, direction, covered by test or live validation
required. Commit, push, report the remote SHA and URL.
