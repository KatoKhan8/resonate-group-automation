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

## RESULT

STATUS: DONE
COMMIT SHA: 10932cae
REMOTE: https://github.com/KatoKhan8/resonate-group-automation/commit/10932cae
TESTS: 36 tests in `tests.test_a_reply_stops_the_other_channel` - all pass
FILES CHANGED:
  - tests/test_a_reply_stops_the_other_channel.py (NEW, 1256 lines)
  - docs/qwen-tasks/RUNNING/TASK-315-the-cross-channel-stop-in-both-directions.md (moved from TODO)

FINDINGS:
  1. THE READBACK TRAP IS PINNED. `TheReadbackCannotLie` reproduces the exact
     defect: a constant readback identical to `expected` accepts every stop.
     The real readback reads provider truth and refuses when the provider
     still reports the lead as running. Four tests pin both directions.
  2. BOTH DIRECTIONS ARE TESTED end-to-end through `inbound.handle`:
     - LinkedIn reply -> email stop (Part 12, `test_linkedin_reply_stops_email`)
     - Email reply -> LinkedIn stop (Part 12, `test_email_reply_stops_linkedin`)
  3. ALL 12 SCENARIO CATEGORIES from the directive are covered by synthetic
     tests. The coverage table is in the test file's module docstring.
  4. LIVE VALIDATION REQUIRED for: provider visibility latency (term 1),
     email stop against a live lead, LinkedIn stop against a live lead,
     end-to-end timing < 15 minutes, and provider retry under load.

RISKS:
  - All tests use mocked provider responses. The identifier shape for
    HeyReach's `StopLeadInCampaign` (profile.linkedin_id, not
    linkedInUserProfileId) was measured live on 2026-09-25 but the full
    cross-channel flow has never run end-to-end against a real lead.
  - The positive reply classifier may return "question" rather than
    "positive" for some texts. The test asserts on stop behaviour, not
    classification label.

RECOMMENDED CLAUDE ACTION:
  1. Review the test file and the coverage table.
  2. Authorise a live validation of the email->LinkedIn direction against
     a DRAFT campaign with a single test lead.
  3. Move to DONE after review.

## SCENARIO COVERAGE TABLE

| Scenario                          | Direction       | Covered by              |
|-----------------------------------|-----------------|-------------------------|
| Contact identity by email         | both            | test (Part 2)           |
| Contact identity by LinkedIn URL  | both            | test (Part 2)           |
| Shared address refuses guess      | both            | test (Part 2)           |
| No provider binding               | both            | test (Part 2)           |
| Account-level pause               | both            | test (Part 3)           |
| Pure OOO no account pause         | both            | test (Part 3)           |
| Reply ingestion                   | both            | test (Part 4)           |
| Negative classification           | both            | test (Part 4)           |
| Positive classification           | both            | test (Part 4)           |
| Unknown classification (fail-safe)| both            | test (Part 4)           |
| Provider stop independent of class| both            | test (Part 4)           |
| Pending step cancellation         | both            | test (Part 5)           |
| Correct provider route (email)    | email           | test (Part 6)           |
| Correct provider route (LI)       | linkedin        | test (Part 6)           |
| Duplicate webhook                 | both            | test (Part 7)           |
| Duplicate stop event              | both            | test (Part 7)           |
| Delayed event                     | both            | test (Part 8)           |
| Stop failure reported as refused  | both            | test (Part 8)           |
| Race: two channels same poll      | both            | test (Part 9)           |
| Race: sweep after reply           | both            | test (Part 9)           |
| Suppression propagation           | both            | test (Part 10)          |
| Sweep both channels               | both            | test (Part 10)          |
| Audit: stop event logged          | both            | test (Part 11)          |
| Audit: reply+stop both logged     | both            | test (Part 11)          |
| Readback cannot lie               | both            | test (Part 1)           |
| Direction: LI->email              | linkedin->email | test (Part 12)          |
| Direction: email->LI              | email->linkedin | test (Part 12)          |
| Per-channel campaign resolution   | both            | test (Part 12)          |
| Single-channel: email only        | email           | test (Part 13)          |
| Single-channel: LI only           | linkedin        | test (Part 13)          |

### LIVE VALIDATION REQUIRED

| Scenario                          | Direction       | Why                       |
|-----------------------------------|-----------------|---------------------------|
| Provider visibility latency       | both            | Term 1: reply sent -> row |
|                                   |                 | in inbox feed. Needs a    |
|                                   |                 | human sending a real LI   |
|                                   |                 | message.                  |
| Email stop against live lead      | email           | Needs a real EmailBison   |
|                                   |                 | lead in a real campaign.  |
| LI stop against live lead         | linkedin        | Needs a real HeyReach     |
|                                   |                 | lead. Identifier shape    |
|                                   |                 | measured 2026-09-25 but   |
|                                   |                 | full flow never ran e2e.  |
| End-to-end timing < 15 min        | both            | Operator gate. Needs both |
|                                   |                 | providers live.           |
| Provider retry under load         | both            | Cannot simulate without   |
|                                   |                 | provider access.          |
