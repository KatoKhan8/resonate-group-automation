PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-392 — signature read per attested mailbox (verify/complete TASK-341)

TASK-341 ("no mailbox has a signature stored") is already queued. This task
exists in case TASK-341 lands partial or stale by the time a worker reaches
it — read TASK-341's own file and current state FIRST; if it is already
complete and merged, close this as superseded rather than duplicating work.

## If TASK-341 is not yet done, do this

1. Enumerate every attested sender mailbox (`bison.sender_emails()` /
   `heyreach` seat roster) and check, per mailbox, whether a signature block
   is stored anywhere the render path reads (email template footer, a
   per-sender config field — name the real field, do not assume one exists).
2. Report the honest count: N attested mailboxes, M with a stored signature,
   the rest named individually.
3. Do not invent a signature or a default - an empty signature block
   rendering is the LAUNCH BLOCKER TASK-341 already names (155 email steps
   render empty per OPERATING-MODE.md). This task verifies and completes the
   read/report; whether to require a signature before send is an operator
   decision already recorded as a launch blocker.

## Acceptance

1. Real counts: N mailboxes, M with signatures, named list of the rest.
2. If TASK-341 already produced this: verify it against a fresh read (not
   the worker's own report) and confirm or refute the numbers.
3. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not write or invent a signature for any mailbox — that is a content
  decision, not this task's.
- No provider write beyond the read.
