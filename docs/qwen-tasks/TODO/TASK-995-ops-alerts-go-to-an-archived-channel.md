# TASK-995 — operational alerts are posted to an archived Slack channel

STAGE: QUEUED
PRIORITY: P1

## Measured 2026-10-12 via `conversations.info`

    SLACK_OPS_CHANNEL     C0C34GCAR27  #resonate-notifications  is_archived: TRUE
    SLACK_STATUS_CHANNEL  C0C3C6MDN9L  #resonate-os             is_archived: false
    SLACK_OUTPUT_CHANNEL  C0C6DES2L7L  #resonate-os-output      is_archived: false

The most recent message in `#resonate-notifications` is literally "archived the
channel". Immediately before it sit fourteen
`[ACTION REQUIRED] UNMATCHED REPLY NEEDS REVIEW` alerts, each ending
"a person decides; nothing is auto-attributed".

So the channel configured for operational alerts is archived, and the alerts
that say a person must decide something have been landing where nobody reads
them. 44 unmatched replies were recorded at 2026-10-11T22:23:34 alone.

## Acceptance

- Point `SLACK_OPS_CHANNEL` at a live channel.
- A startup check that refuses, or at minimum alarms, when a configured channel
  is archived. `conversations.info` returns `is_archived` and the bot credential
  already has the scope. An alert path that cannot be read is worse than none,
  because it looks like coverage.
- Decide what happens to the unmatched replies already posted there.
