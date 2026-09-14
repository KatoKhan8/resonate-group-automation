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

---

## REVIEW 1 - REWORK 2026-09-14. The trace is right and two things are not.

Removing the unconditional pause from `events.apply` and deciding after
classification is the right shape. Keep it. Two things to settle first.

**1. An orchestrator docstring now asserts something false.**

`orchestrator.positive_reply_notification` says, as its stated safety
property:

    "The ordering is the safety property. `events.apply()` has already paused
     the company by the time this runs; this function only tells someone. If
     Slack is off, misconfigured or broken, the pause is untouched and the
     alert stays retryable."

`events.apply()` no longer pauses. The PROPERTY may still hold - a positive
reply pauses a few lines later in `inbound.handle` - but "it happens to still
be true" and "it is guaranteed" are different, and the sentence a future
reader trusts now names a function that does not do it.

Establish whether the pause still precedes the notification ON EVERY PATH that
reaches `positive_reply_notification`, fix the docstring to name whatever
actually guarantees it, and write a test that FAILS if a notification can
precede the pause. That test is the point: the docstring was the only thing
holding this and docstrings do not fail.

**2. The out-of-office case still pauses and then un-pauses.**

    _pre_pause = rec.get("paused")
    ...
    rec["paused"] = _pre_pause

`replies.apply` still calls `accountpolicy` which pauses, and the OOO branch
reverses it. The `_pre_pause` capture is right and means a pre-existing pause
cannot be lifted - keep that - but reversing a policy decision is a second
place that decides the same fact, and CLAUDE.md's "prefer canonical state to a
second representation of it" is about exactly this.

Prefer not pausing in the first place: `replies.apply` knows the
classification, so the policy it applies can depend on it rather than being
applied and then partly undone.

If that cannot be done inside your allowed files, say so plainly and keep the
undo - but then it must also RECORD why the pause was lifted. An account that
is not paused with nothing in the log saying why is indistinguishable from one
nobody ever paused, and the next person reading that record cannot tell.

## STILL REQUIRED, unchanged

The most important test remains: an UNKNOWN reply STILL PAUSES. Confirm it is
in place and that it fails when the classification check is removed.

---

## REVIEW 2 - NOT REJECTED. REBASE AND RE-SUBMIT. 2026-09-14.

The rework is CORRECT and both review points are addressed:

- `orchestrator.positive_reply_notification`'s docstring now names the real
  pause path, and `src/replies.py`'s module docstring says the pause is
  conditional on the classification;
- a pure out-of-office SKIPS `accountpolicy.apply_reply` entirely rather than
  being paused and undone, which is what REVIEW 1 asked for. The residual
  safety restore logs via `store.log(rec, "pause_restored", ...)`;
- the wiring is proved: removing `_is_pure_ooo` makes an out-of-office pause,
  and an UNKNOWN reply still pauses.

**A note on FILES FORBIDDEN.** It listed `src/replies.py`, and REVIEW 1 then
asked for exactly the change that requires editing it. The review wins; the
list was wrong. Editing it was right.

## WHY THIS COULD NOT BE INTEGRATED AS IT STANDS

TASK-038 landed on master while this ran, and both changed
`tests/test_reply_transitions.py`. TASK-038 changed the REFERRAL policy:

    reply.on_referral                HOLD -> STOP
    reply.activate_referred_contact  HOLD -> CONTINUE

Your branch predates it, so applying your test file reverted those
expectations, and keeping master's leaves four tests asserting that
`events.apply` pauses - which your change deliberately stops.

Neither version is wrong. They are two true things written at different times,
and reconciling them from the outside means guessing which assertion belongs
to which task.

## WHAT TO DO

1. `git merge master` - it now carries TASK-038 and TASK-035.
2. Re-apply your change on top. The four tests that will fail are in
   `tests/test_reply_transitions.py::EveryEntryPointGoesThroughThePolicy` and
   `ReplayAndRaces`, and they assert the pause happens in `events.apply`.
   Update them to assert it happens after classification, keeping TASK-038's
   referral expectations untouched.
3. Run `tests/test_account_saturation.py` as well. It is TASK-038's and it
   exercises the same policy table; if your change moves what a referral or a
   positive reply does to an ACCOUNT, that file will say so.

Nothing of yours is lost - this is a rebase, not a rewrite.
