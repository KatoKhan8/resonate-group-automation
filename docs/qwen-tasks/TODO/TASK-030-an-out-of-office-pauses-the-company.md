# TASK-030 - An out-of-office reply pauses the whole company

Found by TASK-020 while tracing the consumer chain, and recorded rather than
fixed because it lay outside that task's allowed files.

## THE DEFECT

`inbound.handle()` calls `events.apply()`, which pauses the company on ANY
reply event - and it happens BEFORE `replies.apply()` classifies the reply.

So the order is: a reply arrives, the account is paused, and only then does
anything ask what the reply said. An automatic out-of-office pauses outreach
to the entire company, and so does a bounce notification, a "wrong person"
note, and a mail-server autoresponder.

Measured on the client's estate: out-of-office is 4.7% of inbound email
replies and the provider's own `automated_reply` flag is set on about one in
ten. So this is not a rare path.

## WHY IT IS NOT SIMPLY A BUG

Pausing on any reply is FAIL-SAFE, and that is why it was written this way.
The cost of pausing an account that did not need pausing is a delay; the cost
of not pausing one that did is a message sent to somebody who just asked you
to stop. If those are the only two options, the current behaviour is right.

They are not the only two options, because `replies.classify` now exists and
has a category for exactly this. But the fix has to keep the fail-safe
property: **an unclassifiable reply must still pause.** `classify` returns
`UNKNOWN` rather than `neutral` for anything the rules cannot read - that
change landed today - and UNKNOWN must pause exactly as it does now.

The only replies that should NOT pause are the ones positively identified as
machine-generated and non-committal:

    out_of_office         defer, do not pause - `src/ooo.py` and
                          `src/oooreturn.py` already model the return date
    provider automated    the `automated_reply` flag, which is the provider
                          telling us its own classification

Everything else pauses, including UNKNOWN, including anything the rules
half-matched, and including an out-of-office that ALSO contains a human
sentence.

## SCOPE

1. Trace it first and write the trace into the result block: `inbound.handle`
   -> `events.apply` -> the pause -> `replies.apply`. Name the line that
   pauses and the line that classifies, and confirm the order.
2. Make the pause conditional on the classification rather than on the
   existence of a reply, preserving the fail-safe default.
3. `src/ooo.py` and `src/oooreturn.py` already exist. Establish whether they
   are CONSUMED before writing anything new - if an out-of-office already
   schedules a return, the answer here may be to route to them rather than to
   add a branch.
4. A reply that is automated AND says something a human would not have sent
   automatically - "I have left the company, contact Dana" - is a referral,
   not an out-of-office. Do not let the automated flag swallow it.

## FILES ALLOWED

`src/inbound.py`, `src/events.py`, `src/ooo.py`, `src/oooreturn.py`,
`tests/`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/replies.py` - the classifier is correct and is being changed by another
task; consume it, do not edit it. `src/providerwrites.py`,
`src/executionguard.py`, `src/killswitch.py`, `src/providers/**`, `work/**`.

## TESTS REQUIRED

Behavioural, driven through `inbound.handle` - the entry point, not the
function you change:

- an out-of-office does NOT pause the account, and DOES schedule a return;
- an UNKNOWN reply DOES pause - this is the fail-safe and it is the most
  important test in the task;
- a human "not interested" pauses;
- an unsubscribe pauses and suppresses;
- an automated reply that names a colleague is treated as a referral;
- an out-of-office containing a human sentence pauses.

Then delete the classification check and confirm a test fails. If nothing
fails, the pause is not actually reading the classification.
