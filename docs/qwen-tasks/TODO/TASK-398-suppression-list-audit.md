PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-398 — suppression list audit: is it complete, and does every write path check it?

The 09-23 blank-email incident already proved 76 recipients needed manual
suppression. Audit the CURRENT suppression mechanism end to end.

## Trace first

1. Name every store of a suppression fact today (DNC list, the 76
   incident-suppressed recipients, `channels.email_verdict`, unsubscribes,
   bounces) — is it ONE canonical list or several that could disagree?
2. Name every write path that could reach a prospect (email send,
   LinkedIn message/connect) and confirm each checks suppression BEFORE
   writing, not after, with file:line.
3. Cross-check the 76 incident-suppressed recipients and the 4 who replied
   to a blank email (named in CLAUDE.md) are still correctly suppressed
   today — read it back, do not assume the incident fix is still in place.

## Acceptance

1. One canonical suppression source named, or the honest report that
   several exist and could disagree, with an example of how.
2. Every prospect-facing write path confirmed to check suppression
   pre-write, with file:line, or named as a gap.
3. The 76 (and the 4) reconfirmed suppressed by a fresh read, not memory.
4. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- READ-ONLY toward providers. No un-suppression, ever, without an explicit
  separate operator instruction naming who and why.
- Nothing sent, nothing activated.
