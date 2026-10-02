# TASK-965 — the cross-channel stop, proven by effect

Operator's order, 2026-10-02: simulate a negative reply on email for a record
active on BOTH channels, and prove that within fifteen minutes the system calls
`bison.stop_lead` AND `heyreach.stop_lead` for exactly that lead, with a mock
transport that records the calls. Then the same in the other direction. A
mutation that removes one provider's call must turn the test red.

## MEASURED FIRST: is it P0? NO, and here is the reading

The operator's own test was *"if the path from classification to provider stop
does not exist for some channel, that is P0 and goes ahead of phase 0."*

**The path exists for both channels.** `src/inbound.py` iterates them:

    for channel, binding, stopper in (
            ("email", "bison_lead_id", leadstop.stop_contact),
            ("linkedin", "heyreach_lead_id", leadstop.stop_linkedin_contact)):

and the comment above it records WHY that is worth checking: *"Only the
EmailBison half was ever called from here, while `STOP_ROUTES` has authorised
the HeyReach route the whole time and `leadstop.sweep` has stopped both channels
since TASK-235. So the guarantee in ACCOUNT-OUTREACH.md — a confirmed reply
stops that lead on BOTH channels — was true of the sweep and not of the live
reply path, which is the path that matters."* It was fixed after the operator's
own 2026-09-23 test. So this task is a PROOF obligation, not a P0 repair.

**It is not ahead of phase 0.** What remains unproven is the EFFECT, and that is
what this task adds.

## MEASURED SECOND: one half of the order contradicts the code, deliberately

The order says: *"bez klasifikacije (unknown) ne zove ništa ali diže
notifikaciju"* — unknown calls nothing but raises a notification.

The code does the opposite ON PURPOSE, and says so in a comment at the call
site:

    # THE PROVIDER STOP IS INDEPENDENT OF CLASSIFICATION.
    # ... Whether the reply was positive, negative or an out-of-office does not
    # change that they should stop receiving the sequence. ... it is attempted
    # BEFORE classification because the stop is a safety REDUCTION - it can
    # only ever mean somebody receives less.

**So implementing "unknown calls nothing" would make the system send MORE to
somebody who has replied and whose reply we could not classify.** That is a
reduction of safety, it is the opposite of every other rule in force, and it is
NOT implemented on the strength of one line. It needs the operator's explicit
confirmation WITH that consequence stated. If confirmed, it also needs a
decision about what happens to the 274 unknown replies already sitting there.

**The notification half IS missing and is already open.** Measured: in
`replies.apply` only `is_positive` calls `_announce`, and
`notify.UNMATCHED_REPLY` fires from `inbound.py` on ATTRIBUTION failure, never
on CLASSIFICATION failure — so an unknown verdict notifies nobody. That is A8 in
the defect map and TASK-941. This task does not duplicate it; it asserts it, so
the proof covers the notification the operator asked about.

## MEASURED THIRD: what "within fifteen minutes" rests on

The live path is synchronous — `inbound` stops at the provider while handling the
event, so the latency is the poller's cycle, not a timer. There is a branch
`task-reply-stop-15min` and the defect map's D7 records that
`scripts/batch_linkedin_push.py` has **0** references to `heyreachfactory`,
`providerwrites`, `eligibility` and `executionguard`, so the fifteen minutes was
proven for a module that script never calls. **The proof must therefore name
WHICH path it measured** — the live `inbound` path, the sweep, or the push
script — because they are three different answers.

## The proof

A test module, `tests/test_a_negative_reply_stops_both_channels.py`:

1. A record with BOTH `bison_lead_id` and `heyreach_lead_id`, built through the
   real staging path rather than by hand — a hand-built contact is how a wrong
   shape gets in, and `collision.touches_of` exists for exactly that reason.
2. A recording transport installed through `providers.set_transport`, the ONE
   seam, which records every call with its URL, method and body. **Seal by HOST,
   not by a blanket sentinel**: that is what broke Phase 0's first attempt.
3. A negative reply arrives on EMAIL through the real `inbound` entry point.
   Assert: `bison` stop called for that lead id, `heyreach` stop called for that
   lead id, and **no call naming any other lead**. The last clause is the one
   that catches a sweep stopping everybody.
4. The same with the reply arriving on LINKEDIN. Assert both again.
5. An UNKNOWN verdict: assert what the code actually does today (both stops
   attempted, nobody notified) and mark the notification assertion as the one
   TASK-941 must flip. **Do not assert the operator's version until it is
   confirmed** — a test written to an unconfirmed rule is a test that will be
   deleted.

## Acceptance

```
python -m unittest tests.test_a_negative_reply_stops_both_channels -v
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import inbound, leadstop; src=inbound.__file__; import inspect; text=inspect.getsource(inbound._stop_at_provider); assert 'stop_contact' in text and 'stop_linkedin_contact' in text, 'the live reply path no longer attempts both channels'; print('OK both channels are attempted from the live reply path')"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import notify; kind=getattr(notify,'UNCLASSIFIED_REPLY',None); assert kind, 'there is still no notification kind for a reply nobody could classify - A8/TASK-941'; assert kind in notify.ROUTES, 'the kind exists but routes nowhere, which is this repository signature defect'; print('OK an unclassified reply has a route:', notify.ROUTES[kind])"
```

### NEGATIVE CONTROL

Command 1 fails today with `No module named` — the module is the deliverable.

Command 2 PASSES today and is a regression guard, stated as such: it asserts the
two-channel attempt is still there. It reads source text, which this repository
forbids as a rule, and the exception is argued rather than hidden — the
alternative is a paid provider call, and the assertion is written so any rewrite
that keeps both stoppers passes it. If the implementation introduces a seam that
can be observed instead, replace this command with one that asserts the effect.

Command 3 fails today with `there is still no notification kind` and is the A8
half of the operator's requirement.

## Mutation

Remove the `("linkedin", "heyreach_lead_id", leadstop.stop_linkedin_contact)`
row from `inbound._stop_at_provider` and the email-direction test must go red
naming the missing HeyReach call — not merely fail. Then remove the email row
and the LinkedIn-direction test must go red the same way. Each alone, with
`__pycache__` wiped, and the restore verified byte-identical.

## Files

`tests/test_a_negative_reply_stops_both_channels.py`, and nothing under `src/`
unless the proof exposes a defect — in which case the defect gets its own task
rather than being fixed inside the proof.
