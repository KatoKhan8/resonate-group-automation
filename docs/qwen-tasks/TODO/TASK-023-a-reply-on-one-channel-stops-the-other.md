# TASK-023 - A reply on one channel must stop the other

Operator backlog: QWEN-14, QWEN-15, QWEN-16.

## GOAL

Prove, behaviourally, that an outcome on one channel changes what happens on
the other - and at the ACCOUNT level, not just for the person who answered.

## WHY IT MATTERS

`ACCOUNT-OUTREACH.md` makes the account the unit of outreach. The operator's
instruction is explicit: "Reply / meeting / unsubscribe must suppress
inappropriate subsequent outreach", and "a response from stakeholder B may
have been influenced by earlier touches to stakeholder A".

The engine runs two channels against the same person and up to four email
contacts and two LinkedIn contacts at the same account. Every one of these is
a real way to embarrass a client:

- somebody replies to an email and still receives LinkedIn message 3;
- somebody says "not interested" on LinkedIn and gets email 4;
- somebody unsubscribes and a SECOND person at that account is opened;
- a meeting is booked with one contact and three colleagues stay in sequence.

The pieces exist - `src/suppression`-adjacent modules, `src/agencydnc.py`,
`src/collision.py`, `src/accountpolicy.py`, `src/fatigue.py`,
`src/cadencereplies.py`, `src/cadenceexposure.py`. What has never been shown
is that they are CONNECTED, and the recurring defect here is exactly that: a
thing computed correctly that nothing downstream reads. The collision gate was
in this state until 2026-09-14 - `executionguard.authorize()` consulted it and
`_ensure_leads` never obtained an Authorization, so nine people the client was
already emailing entered our campaign and `grep -c collision src/bisonfactory.
py` returned 0.

## THE MEASUREMENT THAT MAKES THIS URGENT

From `docs/ESTATE-LEARNING-2026-09-14.md`: the client's campaigns have
`can_unsubscribe: false`, so there is NO unsubscribe link and NO unsubscribe
event - the estate reports 0 unsubscribes across 237,935 emails. Classifying
the replies says 12% of them are unsubscribe requests in words. So opt-out
arrives here as a REPLY that something has to classify and act on, and if
that chain is broken there is no second line.

## SCOPE

For each pair below, write a test that drives the real path - confirm the
event, then ask the planner what happens next - and assert on what it
returns:

1. email reply -> the LinkedIn steps for that CONTACT;
2. LinkedIn reply -> the email steps for that CONTACT;
3. unsubscribe (however it arrives) -> every channel for that contact AND
   the account policy for their colleagues;
4. meeting booked -> every other contact at that ACCOUNT;
5. negative / not interested -> that contact, and what it means for the
   account;
6. bounce -> that address, and whether it says anything about the account.

Where the answer is "nothing happens", that is a FINDING. Write it up; do not
build the missing link until Claude has read the finding, because several of
these are product decisions rather than bugs - whether a colleague's meeting
should stop your sequence is a business question and guessing it builds the
wrong product.

## FILES ALLOWED

`tests/`, `docs/qwen-tasks/`, a report under `docs/`. `src/**` only for a link
that is UNAMBIGUOUSLY missing rather than undecided, and name it in FINDINGS.

## FILES FORBIDDEN

`src/providers/**`, `src/providerwrites.py`, `src/executionguard.py`,
`src/killswitch.py`, `work/**`.

## PRODUCTION CONSTRAINTS

ZERO network. ZERO credentials. Build estates in fixtures. No real prospect
data anywhere - `tests/test_fixture_hygiene` is currently failing on exactly
that and you must not add to it.

## TESTS REQUIRED

Behavioural, end to end through the real planner. Assert on the plan, never on
the import graph and never on source text. A test that proves module A imports
module B proves nothing about whether B's answer is used.
