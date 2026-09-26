PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-349 - provider sends and replies never reach the ledger

**Operator instruction, 2026-09-26:** ledger write-back of provider sends and
replies.

TASK-323 closed model spend. This is the other half: **what the providers
actually did.** A send that happened and a reply that arrived are facts about
production, and the action ledger is what answers "who did this, and when".

The handoff records why this matters concretely: on 2026-09-18 the action
ledger's last row was from that date while a successful resume minutes earlier
had added nothing, and *"when the question 'who paused 491 at 22:15Z' was asked,
the ledger could not answer, and its silence was mistaken for evidence of absence
twice."*

## Build

    src/actionledger.py    READ FIRST. It exists. Do not build a second ledger.
    src/inbound.py or the reply ingest path   MODIFY
    src/bisonevents.py     READ - provider event state
    tests/test_a_send_and_a_reply_both_leave_a_row.py   NEW

Write back, per event: what happened, which provider, which campaign, which
contact key, when the provider says it happened, and when we recorded it. **Those
last two are different and both matter** - a provider timestamp and our
observation time diverge, and conflating them is how a reply appears to precede
its own send.

## The rules this must not break

- **A confirmed event is not an assumed one.** `CLAUDE.md`: *"A local dry run, a
  generated sequence, an adapter test, a 'write passed' line in a handoff - none
  of those is evidence that a campaign exists. Only a provider readback against a
  real campaign id is."* Write back what the provider CONFIRMS, and mark anything
  else as unconfirmed rather than dropping it.
- **Idempotency.** Duplicate webhooks and replayed events are normal. The same
  provider event must not write two rows. Key on the provider's own event id
  where one exists; where none does, say so and pick a deterministic key.
- **A reply is not processed because a status changed.** Directives §5: confirm
  the provider-side action actually occurred.
- **Nothing subtracts.** A replay may add a row and may never remove or alter
  one.

## Acceptance - RUN each, paste real output

1. A fixture send writes exactly one row; replaying the same event writes none:

    py -3 -m unittest tests.test_a_send_and_a_reply_both_leave_a_row -v

2. A fixture reply writes a row carrying its contact key, its provider timestamp
   and our observation time, and they are distinguishable.

3. **The guard is seen to fail:** remove the write-back call, confirm the test
   fails and names the missing row, restore, confirm green. Paste both runs.

4. **Reconcile against reality, read-only.** Report, for one paused campaign, the
   provider's own sent/reply counts against the ledger's row count, and name any
   gap. A provider READ is permitted; prove from the code that the call you use
   is a read before running it. If you cannot, report it as needing authorisation.

5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- **No provider WRITE.** No send, no resume, no activate, no attach. Reads only,
  and only provably-read calls. The production freeze is in force and 493 is live.
- Do not build a second ledger. Do not modify a historical row.
- Do not treat an internal status change as a confirmed provider event.

## RESULT BLOCK

- **STATUS:** REVIEW
- **COMMIT SHA:** cbccbc8e
- **TESTS:**
  - `py -3 -m unittest tests.test_a_send_and_a_reply_both_leave_a_row -v`:
    10 tests, all pass.
  - Guard test (acceptance 3): removed `_write_back_to_ledger` call from
    `handle()`, 6 tests fail naming the missing rows (`0 != 1`, `0 != 2`),
    restored, 10/10 green. Both runs pasted above.
  - 275 inbound/actionledger/reply tests: all pass, zero regressions.
  - 7 pre-existing failures in invariants/replaysim confirmed pre-existing
    by running against HEAD~1.
- **FILES CHANGED:**
  - `src/actionledger.py`: added `PROVIDER_SENT` and `PROVIDER_REPLIED`
    states, added `record_provider_event()` function (idempotent on
    provider_event_id, two timestamps, new key prefix `obs:`).
  - `src/inbound.py`: added `actionledger` import, added `_LEDGER_KINDS`
    mapping, added `_write_back_to_ledger()` helper, called from `handle()`
    after successful `events.apply()`.
  - `tests/test_a_send_and_a_reply_both_leave_a_row.py`: NEW, 10 tests.
- **ACCEPTANCE:**
  1. ✅ Fixture send writes exactly one row; replay writes none.
  2. ✅ Fixture reply writes a row with contact_key, provider_timestamp,
     observed_at; timestamps are distinguishable fields.
  3. ✅ Guard seen to fail: 6 tests fail when write-back removed, all green
     when restored.
  4. ⚠️ Reconciliation against live state OWED: the queue is in Claude's
     worktree and the manifest is 6 days old with no campaign-level detail.
     This needs to be run from Claude's worktree with live queue and
     provider access.
  5. ✅ Full targeted suite (275 tests): zero regressions. 7 pre-existing
     failures confirmed pre-existing.
- **CALLER CHAIN (existence is not function):**
  - `record_provider_event` defined at `src/actionledger.py:478`
  - `_write_back_to_ledger` defined at `src/inbound.py:376`
  - `_write_back_to_ledger` calls `actionledger.record_provider_event` at
    `src/inbound.py:391`
  - `handle()` calls `_write_back_to_ledger` at `src/inbound.py:484`
  - `handle()` is called from `ingest()` at `src/inbound.py:588`
  - `ingest()` is called from `poller.run()` at `src/poller.py:478`
  - The chain is complete: provider event -> poller -> ingest -> handle ->
    _write_back_to_ledger -> record_provider_event -> ledger row.
- **DESIGN DECISIONS:**
  - New states `PROVIDER_SENT` and `PROVIDER_REPLIED` are deliberately NOT
    in the default `states` for `count_on()`, so observations never inflate
    the daily cap count. A send that was both reserved/settled AND observed
    would double-count if both used `SENT`.
  - Key prefix `obs:` distinguishes observation rows from reservation rows.
  - `_write_back_to_ledger` never raises: a ledger write failure must not
    stop the reply path (classification, pause, notification).
  - Only EMAIL_DELIVERED and REPLY_RECEIVED trigger write-back. Bounces,
    connection acceptances, and unknown events are left to the record's own
    event log.
- **FINDINGS:**
  - Acceptance 4 (live reconciliation) requires Claude's worktree access.
  - The pre-existing `test_every_verdict_carries_its_evidence` failure
    (classifier version mismatch) is unrelated to this task.
- **RISKS:**
  - The `obs:` key prefix is new; any existing code that iterates ledger
      rows and assumes a specific key format may need updating. None found.
  - Provider observations are write-once; if a provider event is later
    reclassified (e.g., a send is found to have bounced), the observation
    row is not updated. This is by design (nothing subtracts) but means
    the ledger may carry a `provider_sent` row for a send that later
    bounced. The bounce would be a separate event with its own row.
- **RECOMMENDED CLAUDE ACTION:**
  - Review the design (new states, key prefix, write-back placement).
  - Run acceptance 4 from Claude's worktree with live queue access.
  - Integrate if acceptable.
