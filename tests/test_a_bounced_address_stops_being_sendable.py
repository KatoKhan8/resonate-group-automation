#!/usr/bin/env python3
"""An address that bounced does not get written to again.

Measured 2026-09-13: `email_bounced` was recorded by `adapters`, counted by
`cadencesafety` and reported by `report.py`, and read by NO gate. `eligibility`
never mentioned a bounce and `channels.email_verdict` asked about
unsubscribes, suppression, MX and verification but not this. A bounced address
was exactly as sendable the day after as the day before.

The cost does not land on the bounced prospect. Writing again to an address
that has already failed is how a sending domain gets itself blocked, and that
falls on every other prospect in the estate.

Keyed to the CONTACT. One colleague's dead address says nothing about anybody
else's, and closing the whole company on it would throw away good addresses -
the account-level question is `collision.account_policy`'s, and it answers it
differently and on purpose.
"""
import unittest

from src import channels, eligibility, events


def record(*entries):
    return {"id": "rec-1", "client": "productive", "domain": "acme.test",
            "company": "Acme", "events": list(entries), "contacts": []}


def contact(key="ck-1", email="dana@acme.test"):
    """A contact that would otherwise be sendable."""
    return {"key": key, "email": email, "name": "Dana Reed",
            "sendable": True, "verdict": "valid",
            "verification": {"evidence": [
                {"provider": "contactout", "status": "valid", "email": email},
                {"provider": "reoon", "status": "valid", "email": email}]}}


def bounce(contact_key=None, email=None):
    entry = {"type": events.EMAIL_BOUNCED, "channel": "email",
             "at": "2026-09-01T09:00:00Z"}
    if contact_key:
        entry["contact"] = contact_key
    if email:
        entry["email"] = email
    return entry


class TheChannelClosesOnTheBounce(unittest.TestCase):

    def test_a_bounced_contact_is_not_sendable(self):
        ok, why = channels.email_verdict(record(bounce("ck-1")), contact())
        self.assertFalse(ok)
        self.assertEqual(why, channels.BOUNCED)

    def test_an_event_naming_only_the_address_still_counts(self):
        """Not every provider row carries our contact key."""
        ok, why = channels.email_verdict(
            record(bounce(email="dana@acme.test")), contact())
        self.assertFalse(ok)
        self.assertEqual(why, channels.BOUNCED)

    def test_the_address_match_is_case_and_space_insensitive(self):
        ok, why = channels.email_verdict(
            record(bounce(email="  Dana@Acme.test ")), contact())
        self.assertFalse(ok)
        self.assertEqual(why, channels.BOUNCED)

    def test_without_a_bounce_the_same_contact_is_sendable(self):
        """Guard the guard: a check that refuses everything proves nothing."""
        ok, why = channels.email_verdict(record(), contact())
        self.assertTrue(ok, why)


class ItIsTheIDENTITYThatCloses(unittest.TestCase):

    def test_a_colleagues_bounce_does_not_close_this_address(self):
        rec = record(bounce("ck-other"))
        ok, why = channels.email_verdict(rec, contact("ck-1"))
        self.assertTrue(ok, why)

    def test_a_different_address_bouncing_does_not_close_this_one(self):
        rec = record(bounce(email="someone.else@acme.test"))
        ok, why = channels.email_verdict(rec, contact("ck-1"))
        self.assertTrue(ok, why)

    def test_linkedin_survives_an_email_bounce(self):
        """A dead mailbox says nothing about a LinkedIn profile."""
        person = contact()
        person["linkedin"] = "https://www.linkedin.com/in/dana-reed"
        ok, why = channels.linkedin_verdict(record(bounce("ck-1")), person)
        self.assertTrue(ok, why)


class TheSENDPathReadsIt(unittest.TestCase):
    """A gate nothing consults is not a gate.

    `channels.email_verdict` learned about bounces first and `eligibility`
    does not consult `channels`, so for one commit the check existed and the
    send path did not read it. That is the same defect one layer along, and
    it is the one this repository keeps finding.
    """

    @staticmethod
    def _rec(*entries):
        rec = record(*entries)
        rec["state"] = "ready"
        rec["contacts"] = [contact()]
        rec["cadence"] = {"ck-1": {"day1": {"channel": "email",
                                            "subject": "s", "body": "b" * 200}}}
        return rec

    def test_decide_blocks_a_bounced_address(self):
        rec = self._rec(bounce("ck-1"))
        step = {"channel": "email", "subject": "s", "body": "b" * 200}
        verdict = eligibility.decide(rec, rec["contacts"][0], "day1",
                                     channel="email", step=step)
        self.assertEqual(verdict.get("verdict"), "blocked")
        self.assertEqual(verdict.get("reason"), eligibility.BLOCKED_BOUNCED)

    def test_without_a_bounce_it_fails_for_a_different_reason(self):
        """Guard the guard: the check must not be refusing everything."""
        rec = self._rec()
        step = {"channel": "email", "subject": "s", "body": "b" * 200}
        verdict = eligibility.decide(rec, rec["contacts"][0], "day1",
                                     channel="email", step=step)
        self.assertNotEqual(verdict.get("reason"), eligibility.BLOCKED_BOUNCED)

    def test_the_reason_has_a_sentence(self):
        self.assertIn("bounced", eligibility.HUMAN[eligibility.BLOCKED_BOUNCED])


class TheReasonIsReportable(unittest.TestCase):

    def test_the_code_is_in_the_declared_vocabulary(self):
        self.assertIn(channels.BOUNCED, channels.REASONS)

    def test_it_has_a_sentence_a_human_can_read(self):
        self.assertEqual(channels.explain(channels.BOUNCED),
                         "mail to this address has already bounced")

    def test_no_address_outranks_a_bounce(self):
        """A contact with no address has no address, whatever else happened."""
        person = contact()
        person["email"] = ""
        ok, why = channels.email_verdict(record(bounce("ck-1")), person)
        self.assertFalse(ok)
        self.assertEqual(why, channels.NO_ADDRESS)

    def test_an_unsubscribe_outranks_a_bounce(self):
        """Both stop the send; the one the person asked for is the reason."""
        person = contact()
        person["unsubscribed"] = True
        ok, why = channels.email_verdict(record(bounce("ck-1")), person)
        self.assertFalse(ok)
        self.assertEqual(why, channels.UNSUBSCRIBED)


if __name__ == "__main__":
    unittest.main()
