#!/usr/bin/env python3
"""The account rule staggers by persona rather than blocking the whole account.

THE DEFECT THIS PINS. On 2026-09-24 the guard refused 212 accounts because the
rule was "same account = refuse". The operator's actual rule is staggered:

    same contact                              NEVER twice
    same account, a NEW persona               allowed after 5 days with no
                                              human reply
    a third persona                           7 days after that
    any reply or unsubscribe at the account   stops all others
    a stop carrying OUR OWN reason plus an
      operator-recorded move                  is NOT an account-level hold

Today's code has no staggering. It reads the provider estate and returns
STOP/HOLD/ALLOW based on whether anybody there has been touched, is in
sequence, or has replied. A second persona at the same account five days
after the first reads as the same refusal as a second persona five minutes
after. That is why the US cohort was empty that night.

THE TRAP THIS TEST EXISTS TO AVOID. The gap is measured from the last
CONFIRMED touch, never from a cache. `work/stage/last-touch.json` is stale
by up to 111 days - lead 133283 read 111 days untouched while its last
confirmed send was two days earlier from campaign 491. These tests construct
records with explicit confirmed touches in the event log and verify the
function reads them, not a cached `last_touch_at` field.

WHAT THIS TESTS. The `account_rule.evaluate` function, which the rewrite
will create. It takes a record and a target contact key, reads the confirmed
touches from the event log, and returns ALLOW or REFUSE with a reason.

WHY THESE TESTS FAIL TODAY. The module does not exist. After the rewrite
creates it, tests 2-7 will fail on assertions because today's
`collision.account_policy` has no concept of persona staggering or
time-based gaps. Test 1 (same contact twice) passes today because the
person-level collision gate already catches it, but it is included here to
pin the behaviour as part of the unified rule.
"""
import datetime
import unittest
from unittest import mock

from src import events, store
from src.account_rule import evaluate


def _days_ago(n):
    """An ISO timestamp n days before now, UTC."""
    now = datetime.datetime.now(datetime.timezone.utc)
    then = now - datetime.timedelta(days=n)
    return then.replace(microsecond=0).isoformat()


def _make_record(domain="acme.test", contacts=None):
    """A minimal record with the given contacts.

    Contacts is a list of dicts with at least `key` and `email`. Each gets
    `sendable: True` and `verified: True` so the eligibility gate does not
    object on their own account.
    """
    contacts = contacts or []
    for c in contacts:
        c.setdefault("sendable", True)
        c.setdefault("verified", True)
    return {
        "id": "test-record-001",
        "client": "test-client",
        "domain": domain,
        "company": "Acme Test Corp",
        "state": "ready",
        "contacts": contacts,
        "events": [],
    }


def _add_confirmed_touch(rec, contact_key, channel="email", at=None,
                         sender_id="sender-1"):
    """Record a confirmed send in the event log.

    CHANGED 2026-09-25 BY LANE G, AND ONLY HERE. As written, TASK-275 emitted
    `push_prepared` and called it a confirmed send. It is not one, and the
    codebase says so by name:

        src/touch.py, CONFIRMING_EVENTS and the module docstring -
        "`push_prepared` - a payload was built. A payload is not a send. ...
        in this build every payload is constructed and none is sent - so
        treating it as evidence would make *every* planned touch look like it
        had happened. It is the single most dangerous near-miss in the
        vocabulary and it is excluded by name."

    Building the account rule on `push_prepared` would have made every
    account with a drafted payload read as touched. The confirming events are
    `push_marked`, `email_delivered` and `linkedin_connected`; this helper now
    emits the first, which is what the rest of the system trusts.

    `push_prepared` also appears ZERO times in the 28,262 events of the live
    `work/queue.jsonl`, so the original shape was not one the real store
    carries either.

    NOT ONE ASSERTION IN THIS FILE WAS CHANGED - only the event this fixture
    writes. Left as it was, seven tests failed and three more (day 5, day 10,
    day 12) PASSED VACUOUSLY, because with no touch in the log every account
    reads as untouched and every verdict is a first-persona ALLOW. A test that
    passes because its fixture is inert is the failure mode this file exists
    to prevent.
    """
    events.record(rec, "push_marked", contact_key=contact_key,
                  channel=channel, at=at or store.now(),
                  sender_id=sender_id, state="sent", confirmed=True)


def _add_reply(rec, contact_key, outcome="positive", at=None,
               automated=False):
    """Record a reply event. `automated` marks it as machine-generated."""
    events.record(rec, "reply_classified", contact_key=contact_key,
                  at=at or store.now(), outcome=outcome,
                  classification="automated" if automated else outcome)


def _add_unsubscribe(rec, contact_key, at=None):
    """Record an unsubscribe at the account."""
    events.record(rec, "reply_classified", contact_key=contact_key,
                  at=at or store.now(), outcome="unsubscribe",
                  classification="unsubscribe")


def _add_stop(rec, contact_key, reason="operator_move", at=None,
              our_stop=True, operator_recorded=True):
    """Record a contact stop.

    `our_stop=True` means this system made the stop deliberately (e.g., to
    move the contact to a different campaign). `our_stop=False` means an
    external cause (bounce, provider stop, etc.).

    `operator_recorded=True` means an operator explicitly recorded the move.
    """
    events.record(rec, "contact_stopped", contact_key=contact_key,
                  at=at or store.now(), reason=reason,
                  our_stop=our_stop,
                  operator_recorded=operator_recorded)


# -------------------------------------------------------------------- tests

class TestSameContactTwiceIsRefused(unittest.TestCase):
    """Requirement 1: the same contact twice is refused, on every path."""

    def test_same_contact_email_twice_is_refused(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice"},
        ])
        _add_confirmed_touch(rec, "c1", channel="email", at=_days_ago(30))

        verdict = evaluate(rec, "c1")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "same contact twice on email must be refused")
        self.assertIn("already contacted", verdict["why"].lower())

    def test_same_contact_linkedin_twice_is_refused(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice"},
        ])
        _add_confirmed_touch(rec, "c1", channel="linkedin", at=_days_ago(10))

        verdict = evaluate(rec, "c1")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "same contact twice on linkedin must be refused")

    def test_same_contact_cross_channel_is_refused(self):
        """Email then LinkedIn to the same person is still the same contact."""
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice"},
        ])
        _add_confirmed_touch(rec, "c1", channel="email", at=_days_ago(20))
        _add_confirmed_touch(rec, "c1", channel="linkedin", at=_days_ago(15))

        verdict = evaluate(rec, "c1")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "same contact on both channels must be refused")


class TestSecondPersonaStaggers(unittest.TestCase):
    """Requirement 2: second persona refused at day 4, allowed at day 5."""

    def test_second_persona_at_day_4_is_refused(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice",
             "persona": "decision_maker"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob",
             "persona": "influencer"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(4))

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "second persona at day 4 must be refused; "
                         "the gap is 5 days, not 4")

    def test_second_persona_at_day_5_is_allowed(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice",
             "persona": "decision_maker"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob",
             "persona": "influencer"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(5))

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "ALLOW",
                         "second persona at day 5 must be allowed; "
                         "the gap is exactly 5 days")

    def test_second_persona_at_day_10_is_allowed(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice",
             "persona": "decision_maker"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob",
             "persona": "influencer"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(10))

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "ALLOW",
                         "second persona at day 10 must be allowed")


class TestThirdPersonaStaggers(unittest.TestCase):
    """Requirement 3: third persona refused at day 11, allowed at day 12.

    The 7-day gap is measured from the SECOND persona's first touch, not from
    the first. So if persona 1 was touched at day 0 and persona 2 at day 5,
    persona 3 needs day 5 + 7 = day 12.
    """

    def test_third_persona_at_day_11_is_refused(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice",
             "persona": "decision_maker"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob",
             "persona": "influencer"},
            {"key": "c3", "email": "carol@acme.test", "first_name": "Carol",
             "persona": "gatekeeper"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(16))
        _add_confirmed_touch(rec, "c2", at=_days_ago(11))

        verdict = evaluate(rec, "c3")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "third persona at day 11 after second must be "
                         "refused; the gap is 7 days from the second touch")

    def test_third_persona_at_day_12_is_allowed(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice",
             "persona": "decision_maker"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob",
             "persona": "influencer"},
            {"key": "c3", "email": "carol@acme.test", "first_name": "Carol",
             "persona": "gatekeeper"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(17))
        _add_confirmed_touch(rec, "c2", at=_days_ago(12))

        verdict = evaluate(rec, "c3")
        self.assertEqual(verdict["verdict"], "ALLOW",
                         "third persona at day 12 after second must be "
                         "allowed; the gap is exactly 7 days")


class TestHumanReplyStopsAllPersonas(unittest.TestCase):
    """Requirement 4: a HUMAN reply anywhere at the account stops every other
    persona. An automated reply is NOT a human reply."""

    def test_human_positive_reply_stops_other_personas(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice",
             "persona": "decision_maker"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob",
             "persona": "influencer"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(10))
        _add_reply(rec, "c1", outcome="positive", at=_days_ago(8),
                   automated=False)

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "a human reply at the account stops all other "
                         "personas, regardless of the stagger gap")

    def test_human_negative_reply_stops_other_personas(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(10))
        _add_reply(rec, "c1", outcome="negative", at=_days_ago(8),
                   automated=False)

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "even a negative human reply stops other personas; "
                         "the account has answered")

    def test_automated_reply_does_not_stop_other_personas(self):
        """An automated reply (out-of-office, assistant redirect) is not a
        human reply. The stagger rule still applies."""
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(6))
        _add_reply(rec, "c1", outcome="automated", at=_days_ago(5),
                   automated=True)

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "ALLOW",
                         "an automated reply must NOT stop other personas; "
                         "the 5-day gap is satisfied and no human replied. "
                         "See replies.is_automated for the definition.")


class TestUnsubscribeStopsAllPersonas(unittest.TestCase):
    """Requirement 5: an unsubscribe anywhere at the account stops every
    other persona."""

    def test_unsubscribe_from_contacted_person_stops_account(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(10))
        _add_unsubscribe(rec, "c1", at=_days_ago(8))

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "an unsubscribe at the account stops all personas")

    def test_unsubscribe_from_uncontacted_person_stops_account(self):
        """Even if the person who unsubscribed was never contacted by us
        (e.g., they were added by a colleague's campaign), the account is
        held."""
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob"},
        ])
        _add_unsubscribe(rec, "c1", at=_days_ago(2))

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "an unsubscribe from anybody at the account stops "
                         "all outreach there")


class TestOurOwnStopIsNotAccountHold(unittest.TestCase):
    """Requirement 6 (ISSUE-035): a stop THIS system made, carrying its own
    reason plus an operator-recorded move, does NOT read as an account-level
    hold.

    The gate is right to hold an account where a campaign ended early, and it
    cannot currently tell "we stopped this ourselves, an hour ago,
    deliberately, to move them" from "something went wrong at this account".
    The fix teaches the system to distinguish a deliberate act of ours from
    an observed fault.
    """

    def test_our_stop_with_operator_move_allows_other_personas(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(10))
        _add_stop(rec, "c1", reason="operator_move", at=_days_ago(1),
                  our_stop=True, operator_recorded=True)

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "ALLOW",
                         "a stop we made deliberately, with an operator-"
                         "recorded move, must NOT hold the account. "
                         "This is ISSUE-035.")

    def test_our_stop_without_operator_recorded_still_holds(self):
        """If we stopped but no operator recorded the move, the account is
        still held - the safety net is the operator's attestation."""
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(10))
        _add_stop(rec, "c1", reason="operator_move", at=_days_ago(1),
                  our_stop=True, operator_recorded=False)

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "our stop without operator attestation still holds "
                         "the account; both arms are required")


class TestExternalStopHoldsAccount(unittest.TestCase):
    """Requirement 7: a stop we did NOT make still holds the account."""

    def test_external_stop_holds_account(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(10))
        _add_stop(rec, "c1", reason="provider_stop", at=_days_ago(1),
                  our_stop=False, operator_recorded=False)

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "a stop we did NOT make still holds the account; "
                         "only our own deliberate stop with operator "
                         "attestation lifts it")

    def test_bounce_holds_account(self):
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(10))
        _add_stop(rec, "c1", reason="bounce", at=_days_ago(5),
                  our_stop=False, operator_recorded=False)

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "a bounce is an external stop and holds the account")


class TestGapReadsFromConfirmedTouchNotCache(unittest.TestCase):
    """The trap: the gap is measured from the last CONFIRMED touch in the
    event log, never from a cached `last_touch_at` field.

    `work/stage/last-touch.json` is stale by up to 111 days. A lead sent to
    yesterday must never read as untouched.
    """

    def test_recent_touch_in_event_log_is_not_untouched(self):
        """A contact touched yesterday must not be treated as untouched,
        even if `last_touch_at` is stale or missing."""
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice",
             "persona": "decision_maker"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob",
             "persona": "influencer"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(1))
        # Deliberately set last_touch_at to a stale value to prove the
        # function does NOT read it.
        rec["contacts"][0]["last_touch_at"] = _days_ago(200)

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "a touch yesterday in the event log must refuse "
                         "a second persona, regardless of stale cache. "
                         "The gap is 1 day, far short of the 5-day rule.")

    def test_stale_cache_does_not_satisfy_the_gap(self):
        """Even if `last_touch_at` says 200 days, a confirmed touch from
        yesterday in the event log is the truth."""
        rec = _make_record(contacts=[
            {"key": "c1", "email": "alice@acme.test", "first_name": "Alice"},
            {"key": "c2", "email": "bob@acme.test", "first_name": "Bob"},
        ])
        _add_confirmed_touch(rec, "c1", at=_days_ago(1))
        rec["contacts"][0]["last_touch_at"] = _days_ago(200)

        verdict = evaluate(rec, "c2")
        self.assertEqual(verdict["verdict"], "REFUSE",
                         "stale last_touch_at must not satisfy the gap; "
                         "the event log is the source of truth")


if __name__ == "__main__":
    unittest.main()
