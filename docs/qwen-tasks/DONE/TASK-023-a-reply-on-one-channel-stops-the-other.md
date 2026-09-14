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


## RESULT

STATUS: done
COMMIT SHA: 3e5fca7
TESTS: 12 tests in tests/test_a_reply_on_one_channel_stops_the_other.py, all
passing. 6 drive cadence.build() (the timeline), 6 drive
nextaction.next_best_action() (the planner). Both are the real entry points.

FILES CHANGED:
- tests/test_a_reply_on_one_channel_stops_the_other.py (new)
- docs/qwen-tasks/RUNNING/TASK-023-a-reply-on-one-channel-stops-the-other.md
  (moved to DONE/)

FINDINGS:

1. EMAIL REPLY -> LinkedIn steps: CONNECTED. An email reply pauses the whole
   account via accountpolicy.apply_reply(UNKNOWN) -> HOLD at ACCOUNT scope.
   cadence.build() returns "paused" for every step of every contact.
   next_best_action() returns WAIT with reason "wait:account_held". The chain
   is complete.

2. LINKEDIN REPLY -> email steps: CONNECTED. Same mechanism as (1). A LinkedIn
   reply pauses the whole account. cadence.build() returns "paused" for every
   step. next_best_action() returns WAIT. The chain is complete.

3. UNSUBSCRIBE -> contact and colleagues: PARTIALLY CONNECTED. The contact is
   suppressed (contact["unsubscribed"] = True). The account is NOT suppressed
   (policy is CONTACT scope). The SEND GATE (eligibility._replied) correctly
   blocks the contact with BLOCKED_UNSUBSCRIBED. next_best_action() correctly
   reports the contact as not ok. However, cadence.build() does NOT check
   contact.get("unsubscribed") or contact.get("stopped") in status_for(), so
   the timeline shows "unapproved" or "waiting" instead of "blocked". This is
   a DISPLAY GAP, not a send gap: nothing would actually send, but the
   timeline is misleading. Colleagues are unaffected by the current policy,
   which is a product decision (one person's unsubscribe is not the company's).

4. MEETING BOOKED -> other contacts: CONNECTED. cadence.pause_state() reads
   MEETING_MARKED from the event log and returns a pause. cadence.build()
   returns "paused" for every contact. next_best_action() returns WAIT with
   reason "wait:account_held". The chain is complete.

5. NEGATIVE / NOT INTERESTED -> contact and account: PARTIALLY CONNECTED. The
   policy is (CONTINUE, CONTACT): the replier is stopped, the account carries
   on. The SEND GATE correctly blocks the stopped contact with
   BLOCKED_CONTACT_STOPPED. next_best_action() correctly reports the contact
   as not ok. Colleagues are unaffected. Same DISPLAY GAP as (3):
   cadence.build() does not check contact.get("stopped"), so the timeline
   shows "unapproved" or "waiting" instead of "blocked". Whether a colleague's
   sequence should continue after a negative reply from another contact is a
   BUSINESS DECISION, not a bug. The current policy says yes.

6. BOUNCE -> address and account: CONNECTED. A bounce closes email for that
   address only. nextaction._bounced_channels reads EMAIL_BOUNCED events and
   removes the email channel for that contact. LinkedIn remains open. The
   account and colleagues are unaffected. This is correct: a bounce is a fact
   about one address, not the company.

DISPLAY GAP (findings 3 and 5): cadence.status_for() does not check the
contact's "unsubscribed", "suppressed", or "stopped" flags. The timeline
therefore shows "unapproved" or "waiting" for contacts the send gate would
correctly block. The send path is safe (eligibility.must_not_contact checks
all three flags), but the timeline display is misleading. Fixing this would
require adding contact-state checks to cadence.status_for(), which is in
src/** and therefore out of scope for this task. Named for Claude.

PRODUCT DECISIONS (not bugs, requiring Claude's input):
- Whether a contact's unsubscribe should suppress their colleagues (currently:
  no, CONTACT scope).
- Whether a negative reply from one contact should stop colleagues (currently:
  no, CONTINUE at CONTACT scope).
- Whether a meeting with one contact should stop colleagues (currently: yes,
  the account is paused).

RISKS:
- The display gap means an operator looking at the timeline might think a
  suppressed contact's sequence is still active. The send gate prevents
  actual sends, but the confusion could lead to unnecessary manual intervention.
- The pre-existing test failures in test_the_cadence_reacts_to_what_the_prospect_did.py
  (2 errors in ThePlannerReadsTheBranch) are the SAME behaviour these tests
  prove: the planner returns WAIT at account level after a reply, so there are
  no "considered" contacts. Those tests expected to find the contact in the
  considered list, which is no longer how the planner works.

RECOMMENDED CLAUDE ACTION:
1. Read the DISPLAY GAP finding and decide whether cadence.status_for() should
   check contact-level stop flags. This is a src/** change.
2. Read the PRODUCT DECISIONS and confirm or change the policies. In
   particular: should a negative reply from one contact stop colleagues?
3. The 2 pre-existing test failures in test_the_cadence_reacts_to_what_the_prospect_did.py
   need updating: they expect the planner to list the contact in "considered"
   after a reply, but the planner now short-circuits at account level.
