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
