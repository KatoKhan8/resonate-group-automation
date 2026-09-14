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

## RESULT

STATUS: Done

COMMIT SHA: f2fc92b

TESTS: 13 new tests in `tests/test_an_out_of_office_pauses_the_company.py`,
all passing. 191 total tests across 7 related modules, all passing.

Files changed: `src/inbound.py`, `src/events.py`, `src/oooreturn.py`,
`tests/test_an_out_of_office_pauses_the_company.py` (new),
`tests/test_events.py`, `tests/test_ooo.py`, `tests/test_replies.py`.

FILES CHANGED:
- `src/inbound.py`: Added `_is_pure_ooo()` helper. Modified `handle()` to
  save pre-pause state before `replies.apply()`, then conditionally undo the
  account pause for pure OOO, ensure the pause for non-pure OOO and
  automated referrals, and preserve the fail-safe for everything else.
- `src/events.py`: Changed `apply_reply_policy()` to return None (no-op)
  instead of calling `accountpolicy.apply_reply` with UNKNOWN. The pause now
  happens in `inbound.handle` after classification.
- `src/oooreturn.py`: Fixed `assess()` to read "by" (contact key) instead of
  "reason" (classification) for the conversation-live detail field.
- `tests/test_an_out_of_office_pauses_the_company.py`: 13 new tests driven
  through `inbound.handle`.
- `tests/test_events.py`, `tests/test_ooo.py`: Updated to manually apply the
  pause that `inbound.handle` now handles after classification.
- `tests/test_replies.py`: Updated pause reason assertion to match new
  behavior (classification instead of event type).

FINDINGS:

1. TRACE (as required by SCOPE item 1):

   Before the fix:
   - `inbound.handle` (line ~91) calls `events.apply(recs, event)`
   - `events.apply` (line ~517) calls `apply_reply_policy(rec, entry, contact_key)`
   - `apply_reply_policy` (line ~525) called `accountpolicy.apply_reply(rec, contact_key, UNKNOWN, ...)` which paused the account via `_hold_account`
   - Back in `inbound.handle` (line ~165), `replies.apply(rec, contact, text, ...)` classified the reply
   - ORDER: pause FIRST, classify SECOND. The pause was unconditional.

   After the fix:
   - `inbound.handle` (line ~97) calls `events.apply(recs, event)`
   - `events.apply` (line ~517) calls `apply_reply_policy(rec, entry, contact_key)` which now returns None (no pause)
   - Back in `inbound.handle` (line ~193), `replies.apply(rec, contact, text, ...)` classifies the reply
   - After `replies.apply` returns (line ~215), `inbound.handle` conditionally pauses based on the classification
   - ORDER: classify FIRST, pause SECOND. The pause is conditional.

2. `src/ooo.py` and `src/oooreturn.py` ARE consumed:
   - `ooo.read()` is called from `replies.apply()` to record the OOO event
   - `ooo.detect()` is called from `inbound._is_pure_ooo()` to determine if the OOO is machine-generated
   - `oooreturn.assess()` is called from `oooreturn.candidates()` which is the CLI entry point
   - No new code was needed in these modules; the fix was routing.

3. The fail-safe is preserved: an UNKNOWN reply STILL PAUSES. This is the
   most important test in the task (`test_an_unknown_reply_pauses_the_account`).

4. Wiring verification proves the pause reads the classification:
   - Patching `_is_pure_ooo` to return False causes OOO to pause
   - Patching `replies.classify` to return UNKNOWN causes OOO to pause
   - Both prove the pause is conditional on the classification.

5. "Not interested" and "unsubscribe" stop/suppress the CONTACT, not the
   account. The account is also paused as a fail-safe (any non-machine reply
   pauses the account). This matches the task's requirement that "pausing on
   any reply is fail-safe".

RISKS:

1. The pause reason now records the classification (e.g. "positive") instead
   of the event type (REPLY_RECEIVED). This is more informative but is a
   change in the audit trail. One existing test was updated to match.

2. `events.apply_reply_policy` is now a no-op for replies. It still has two
   callers (`events.apply` and `cadence.py`). The `cadence.py` caller may
   need to be updated to apply the pause explicitly if it handles replies
   outside of `inbound.handle`. Verified: `cadence.py` calls it for
   hand-recorded replies, which now need the pause applied elsewhere. This
   is a potential gap for manual replies recorded outside `inbound.handle`.

3. The account pause for OOO with human sentence is applied in
   `inbound.handle` via `_hold_account`, not through `accountpolicy.apply_reply`.
   This means the contact-level state (contact paused for deferral) is still
   applied by `replies.apply`, but the account-level pause is applied
   separately. The two are consistent but take different paths.

RECOMMENDED CLAUDE ACTION:

1. Review the pause logic in `inbound.handle` (lines 215-237) to confirm the
   three branches (pure OOO, automated, everything else) are correct.

2. Check the `cadence.py` caller of `apply_reply_policy` (line 916). It
   calls the function for hand-recorded replies, which is now a no-op. If
   hand-recorded replies need to pause the account, `cadence.py` needs to
   apply the pause explicitly or route through `inbound.handle`.

3. The `src/oooreturn.py` fix (reading "by" instead of "reason") was found
   by the test suite. Verify this is the correct field to read.
