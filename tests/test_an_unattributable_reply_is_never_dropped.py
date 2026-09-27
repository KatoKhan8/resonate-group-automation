"""TASK-351: a reply we cannot attribute must not vanish.

`events.apply` returns `contact_key = None` whenever the reply address
matches no contact - an alias, a forward, somebody writing from their phone.
This is common, not exotic.

For every outcome in the policy table, with `contact_key = None`, something
must be written. An outcome that writes nothing is a reply that vanished.

The rule that decides every case: **uncertainty never narrows.** An
unattributable outcome widens to the account or holds at account scope. It
never silently applies to nobody.

Constraints:
- Only a removal request suppresses. Non-removal outcomes must NOT set
  `unsubscribed`.
- Nothing subtracts. A replay may add a hold but may never lift one.
"""
import copy
import io
import sys
import unittest

from src import account, accountpolicy as ap, events, store
from tests.campaignbase import CampaignTest

WS = "productive"
JOHN, SARAH, MIKE = "john", "sarah", "mike"


def _make_record():
    """A minimal record with three contacts, no provider calls."""
    rec = {"id": "acme", "client": "demo", "events": [],
           "contacts": [
               {"key": JOHN, "name": "John Smith", "title": "COO",
                "email": "j@acme.test", "selected": True,
                "priority": account.PRIMARY},
               {"key": SARAH, "name": "Sarah Jones", "title": "CEO",
                "email": "s@acme.test", "selected": True,
                "priority": account.SECONDARY},
               {"key": MIKE, "name": "Michael Green", "title": "CFO",
                "email": "m@acme.test", "selected": True,
                "priority": account.TERTIARY},
           ]}
    return rec


def _what_was_written(rec):
    """Summarise the state an unattributable reply left behind."""
    written = []
    if rec.get("paused"):
        written.append("account_held")
    if (rec.get("suppression") or {}).get("unsubscribed"):
        written.append("account_suppressed")
    if (rec.get("review") or {}).get("open"):
        written.append("review_required")
    for c in rec.get("contacts", []):
        if c.get("paused"):
            written.append(f"contact_held:{c['key']}")
        if c.get("stopped"):
            written.append(f"contact_stopped:{c['key']}")
        if c.get("unsubscribed"):
            written.append(f"contact_suppressed:{c['key']}")
    event_types = [e["type"] for e in rec.get("events", [])]
    return written, event_types


class EnumerateEveryOutcome(CampaignTest):
    """Acceptance 1: enumerate every outcome against contact_key = None."""

    def test_every_outcome_writes_something(self):
        """Print a table and assert no row writes nothing."""
        rows = []
        for outcome in ap.OUTCOMES:
            rec = _make_record()
            moved = ap.apply_reply(rec, None, outcome,
                                   at="2026-09-26T10:00:00+00:00",
                                   channel="email", reason="email_reply")
            written, event_types = _what_was_written(rec)
            plan = ap.effects(outcome)
            rows.append((outcome, written, event_types,
                         plan["decision"]["scope"]))

        # Print the table for the result block.
        buf = io.StringIO()
        buf.write(f"{'OUTCOME':<20} {'SCOPE':<10} "
                  f"{'WRITTEN':<45} {'EVENTS'}\n")
        buf.write("-" * 110 + "\n")
        for outcome, written, evts, scope in rows:
            buf.write(f"{outcome:<20} {scope:<10} "
                      f"{str(written):<45} {evts}\n")
        sys.stderr.write(buf.getvalue())

        # Every row must write at least one state change or event.
        for outcome, written, evts, scope in rows:
            has_state = bool(written)
            has_event = len(evts) > 0
            self.assertTrue(
                has_state or has_event,
                f"{outcome}: wrote nothing with contact_key=None "
                f"(scope={scope})")


class OneTestPerOutcome(CampaignTest):
    """Acceptance 2: one test per outcome, not one aggregate."""

    def _apply(self, outcome):
        rec = _make_record()
        return rec, ap.apply_reply(rec, None, outcome,
                                   at="2026-09-26T10:00:00+00:00",
                                   channel="email", reason="email_reply")

    def test_positive_writes_an_account_hold(self):
        rec, moved = self._apply(ap.POSITIVE)
        self.assertTrue(rec.get("paused"),
                        "POSITIVE with no contact must hold the account")
        self.assertIn("account_held_unattributed", moved["changed"])

    def test_neutral_writes_an_account_hold(self):
        rec, moved = self._apply(ap.NEUTRAL)
        self.assertTrue(rec.get("paused"),
                        "NEUTRAL with no contact must hold the account")
        self.assertIn("account_held_unattributed", moved["changed"])

    def test_negative_writes_an_account_hold(self):
        rec, moved = self._apply(ap.NEGATIVE)
        self.assertTrue(rec.get("paused"),
                        "NEGATIVE with no contact must hold the account")
        self.assertIn("account_held_unattributed", moved["changed"])

    def test_not_now_writes_an_account_hold(self):
        rec, moved = self._apply(ap.NOT_NOW)
        self.assertTrue(rec.get("paused"),
                        "NOT_NOW with no contact must hold the account")
        self.assertIn("account_held_unattributed", moved["changed"])

    def test_not_icp_writes_an_account_hold(self):
        rec, moved = self._apply(ap.NOT_ICP)
        self.assertTrue(rec.get("paused"),
                        "NOT_ICP with no contact must hold the account")
        self.assertIn("account_held_unattributed", moved["changed"])

    def test_unsubscribe_suppresses_the_account(self):
        rec, moved = self._apply(ap.UNSUBSCRIBE)
        self.assertTrue((rec.get("suppression") or {}).get("unsubscribed"),
                        "UNSUBSCRIBE with no contact must suppress the account")
        self.assertIn("account_suppressed_unattributed", moved["changed"])

    def test_account_dnc_suppresses_the_account(self):
        rec, moved = self._apply(ap.ACCOUNT_DNC)
        self.assertTrue((rec.get("suppression") or {}).get("unsubscribed"),
                        "ACCOUNT_DNC with no contact must suppress the account")

    def test_referral_writes_an_account_hold(self):
        rec, moved = self._apply(ap.REFERRAL)
        self.assertTrue(rec.get("paused"),
                        "REFERRAL with no contact must hold the account")
        self.assertIn("account_held_unattributed", moved["changed"])

    def test_wrong_person_writes_an_account_hold(self):
        rec, moved = self._apply(ap.WRONG_PERSON)
        self.assertTrue(rec.get("paused"),
                        "WRONG_PERSON with no contact must hold the account")
        self.assertIn("account_held_unattributed", moved["changed"])

    def test_left_company_writes_an_account_hold(self):
        rec, moved = self._apply(ap.LEFT_COMPANY)
        self.assertTrue(rec.get("paused"),
                        "LEFT_COMPANY with no contact must hold the account")
        self.assertIn("account_held_unattributed", moved["changed"])

    def test_existing_client_writes_an_account_hold_and_review(self):
        rec, moved = self._apply(ap.EXISTING_CLIENT)
        self.assertTrue(rec.get("paused"),
                        "EXISTING_CLIENT with no contact must hold the account")
        self.assertTrue((rec.get("review") or {}).get("open"),
                        "EXISTING_CLIENT must require review")

    def test_unknown_writes_an_account_hold_and_review(self):
        rec, moved = self._apply(ap.UNKNOWN)
        self.assertTrue(rec.get("paused"),
                        "UNKNOWN with no contact must hold the account")
        self.assertTrue((rec.get("review") or {}).get("open"),
                        "UNKNOWN must require review")


class SuppressionIsNotWidened(CampaignTest):
    """Acceptance 4: a non-removal unattributable outcome does NOT suppress."""

    def test_negative_does_not_suppress(self):
        rec = _make_record()
        ap.apply_reply(rec, None, ap.NEGATIVE,
                       at="2026-09-26T10:00:00+00:00")
        self.assertFalse((rec.get("suppression") or {}).get("unsubscribed"),
                         "NEGATIVE must not set unsubscribed")
        for c in rec["contacts"]:
            self.assertFalse(c.get("unsubscribed"),
                             f"{c['key']} must not be unsubscribed")

    def test_neutral_does_not_suppress(self):
        rec = _make_record()
        ap.apply_reply(rec, None, ap.NEUTRAL,
                       at="2026-09-26T10:00:00+00:00")
        self.assertFalse((rec.get("suppression") or {}).get("unsubscribed"))

    def test_positive_does_not_suppress(self):
        rec = _make_record()
        ap.apply_reply(rec, None, ap.POSITIVE,
                       at="2026-09-26T10:00:00+00:00")
        self.assertFalse((rec.get("suppression") or {}).get("unsubscribed"))

    def test_wrong_person_does_not_suppress(self):
        rec = _make_record()
        ap.apply_reply(rec, None, ap.WRONG_PERSON,
                       at="2026-09-26T10:00:00+00:00")
        self.assertFalse((rec.get("suppression") or {}).get("unsubscribed"))


class NothingSubtracts(CampaignTest):
    """Acceptance 5: replay an unattributable reply twice.

    No state was removed or altered, and no duplicate suppression written.
    """

    def test_replaying_a_negative_writes_nothing_the_second_time(self):
        rec = _make_record()
        first = ap.apply_reply(rec, None, ap.NEGATIVE,
                               at="2026-09-26T10:00:00+00:00",
                               channel="email", reason="email_reply")
        snapshot = copy.deepcopy(rec)
        second = ap.apply_reply(rec, None, ap.NEGATIVE,
                                at="2026-09-26T10:01:00+00:00",
                                channel="email", reason="email_reply")
        # The hold was already in place, so the second call changes nothing.
        self.assertNotIn("account_held_unattributed", second["changed"])
        # The account is still held.
        self.assertTrue(rec.get("paused"))
        # No extra events beyond the first hold.
        hold_events = [e for e in rec["events"]
                       if e["type"] == events.COMPANY_PAUSED]
        self.assertEqual(len(hold_events), 1)

    def test_replaying_an_unsubscribe_writes_nothing_the_second_time(self):
        rec = _make_record()
        first = ap.apply_reply(rec, None, ap.UNSUBSCRIBE,
                               at="2026-09-26T10:00:00+00:00",
                               channel="email", reason="email_reply")
        self.assertIn("account_suppressed_unattributed", first["changed"])
        second = ap.apply_reply(rec, None, ap.UNSUBSCRIBE,
                                at="2026-09-26T10:01:00+00:00",
                                channel="email", reason="email_reply")
        self.assertNotIn("account_suppressed_unattributed", second["changed"])
        # Suppression is still in place.
        self.assertTrue((rec.get("suppression") or {}).get("unsubscribed"))
        suppress_events = [e for e in rec["events"]
                           if e["type"] == events.ACCOUNT_SUPPRESSED]
        self.assertEqual(len(suppress_events), 1)

    def test_replay_does_not_lift_existing_state(self):
        """A hold followed by a different outcome must not undo the hold."""
        rec = _make_record()
        ap.apply_reply(rec, None, ap.NEGATIVE,
                       at="2026-09-26T10:00:00+00:00")
        self.assertTrue(rec.get("paused"))
        ap.apply_reply(rec, None, ap.POSITIVE,
                       at="2026-09-26T10:01:00+00:00")
        # Still held - the second reply did not lift the first.
        self.assertTrue(rec.get("paused"))


if __name__ == "__main__":
    unittest.main()
