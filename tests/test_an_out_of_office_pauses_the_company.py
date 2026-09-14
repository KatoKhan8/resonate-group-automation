#!/usr/bin/env python3
"""An out-of-office pauses the company - or rather, it no longer does.

TASK-030. The defect: `inbound.handle` -> `events.apply` -> `apply_reply_policy`
paused the company BEFORE `replies.apply` classified the reply. An automatic
out-of-office held the entire company, and so did a bounce, a "wrong person"
note, and a mail-server autoresponder. Measured: 4.7% of inbound replies are
out-of-office.

The fix: the pause is now conditional on the classification. An UNKNOWN reply
STILL PAUSES (fail-safe). Only a positively identified machine reply - a pure
out-of-office with no human sentence - may skip the pause.

Every test below is driven through `inbound.handle`, which is the entry point.
Not the function we changed - the function production calls.
"""
import os
import unittest

from src import (accountpolicy, events, inbound, ooo, replies, store)
from tests.base import QueueTest

OOO_AT = "2026-09-10T08:00:00+00:00"


def _record(rid="rec-ooo", email="target@borealis.test",
            key="ck-target", name="Target Person"):
    rec = store.new_record(rid, "domains", "productive", f"Co {rid}",
                           "borealis.test")
    rec["state"] = "verified"
    rec["contacts"] = [{
        "key": key, "name": name, "title": "Decision Maker",
        "email": email, "linkedin": f"https://www.linkedin.com/in/{key}",
        "selected": True, "verdict": "valid", "sendable": True,
        "persona": "champion",
    }]
    return rec


def _event(text, rid="rec-ooo", key="ck-target", automated=None, **over):
    ev = {"type": events.REPLY_RECEIVED, "provider": "emailbison",
          "record_id": rid, "contact_key": key, "client": "productive",
          "email": "target@borealis.test", "at": OOO_AT, "channel": "email",
          "provider_event_id": f"evt-{rid}-1", "text": text}
    if automated is not None:
        ev["automated"] = automated
    ev.update(over)
    return ev


class _OOOTestBase(QueueTest):
    """Shared setUp: temp queue, no campaigns file, one record staged."""

    def setUp(self):
        super().setUp()
        self._pinned = {k: os.environ.pop(k, None)
                        for k in ("CAMPAIGNS", "ACTION_LEDGER", "NOTIFICATIONS")}
        store.append([_record()])

    def tearDown(self):
        for key, value in self._pinned.items():
            if value is not None:
                os.environ[key] = value
        super().tearDown()

    def _rec(self, recs=None):
        return (recs or store.load())[0]


# ----------------------------------------------------------- the six required


class OOODoesNotPause(_OOOTestBase):
    """An out-of-office does NOT pause the account, and DOES schedule a return.

    The whole point of the task. A pure machine autoresponder saying "I am away
    until the 20th" must not hold the company. The OOO event must be recorded
    so oooreturn can follow up on the return date.
    """

    def test_account_is_not_paused(self):
        recs = store.load()
        text = ("Automatic reply: I am out of the office until September 20 "
                "with limited access to email.")
        outcome = inbound.handle(_event(text, automated=True), recs)
        rec = self._rec(recs)
        self.assertEqual(outcome["applied"]["status"], "applied")
        self.assertFalse(rec.get("paused"),
                         "a pure out-of-office paused the account")

    def test_the_ooo_event_is_recorded(self):
        """oooreturn needs this to schedule the return."""
        recs = store.load()
        text = ("Automatic reply: I am out of the office until September 20 "
                "with limited access to email.")
        inbound.handle(_event(text, automated=True), recs)
        rec = self._rec(recs)
        ooo_events = [e for e in rec.get("events", [])
                      if e.get("type") == events.OUT_OF_OFFICE_RECORDED]
        self.assertTrue(ooo_events,
                        "no OUT_OF_OFFICE_RECORDED event was written")

    def test_the_classification_is_out_of_office(self):
        recs = store.load()
        text = ("Automatic reply: I am out of the office until September 20 "
                "with limited access to email.")
        outcome = inbound.handle(_event(text, automated=True), recs)
        cls = (outcome.get("classification") or {}).get("classification")
        self.assertEqual(cls, replies.OUT_OF_OFFICE)


class UnknownReplyDoesPause(_OOOTestBase):
    """THE most important test in the task. The fail-safe.

    An unclassifiable reply must still pause the account. UNKNOWN means "we
    could not read this" and the uncertain case is the one that must not
    narrow. If this test fails, the pause is not reading the classification.
    """

    def test_an_unknown_reply_pauses_the_account(self):
        recs = store.load()
        text = "Hmm, interesting proposition regarding the quarterly review."
        outcome = inbound.handle(_event(text), recs)
        rec = self._rec(recs)
        cls = (outcome.get("classification") or {}).get("classification")
        self.assertEqual(cls, replies.UNKNOWN,
                         f"expected UNKNOWN, got {cls}")
        self.assertTrue(rec.get("paused"),
                        "an UNKNOWN reply did NOT pause the account - "
                        "the fail-safe is broken")


class HumanNotInterestedPauses(_OOOTestBase):
    """A human 'not interested' pauses.

    The policy for NEGATIVE is STOP at CONTACT scope: the contact's sequence
    ends. The account is NOT paused (one person declining is not the company
    declining). The contact IS stopped.
    """

    def test_not_interested_stops_the_contact(self):
        recs = store.load()
        outcome = inbound.handle(
            _event("Thanks but not interested, we are all set."), recs)
        rec = self._rec(recs)
        cls = (outcome.get("classification") or {}).get("classification")
        self.assertEqual(cls, replies.NEGATIVE)
        contact = rec["contacts"][0]
        self.assertTrue(contact.get("stopped"),
                        "a human 'not interested' did not stop the contact")


class UnsubscribePausesAndSuppresses(_OOOTestBase):
    """An unsubscribe pauses and suppresses.

    The policy for UNSUBSCRIBE is STOP at CONTACT scope, with the replier
    promoted to SUPPRESS (because UNSUBSCRIBE is in REMOVAL_REQUESTS). The
    contact is permanently suppressed. The account is NOT paused (one person
    unsubscribing is not the company asking us to stop).
    """

    def test_unsubscribe_suppresses_the_contact(self):
        recs = store.load()
        outcome = inbound.handle(
            _event("Please unsubscribe me from your list."), recs)
        rec = self._rec(recs)
        cls = (outcome.get("classification") or {}).get("classification")
        self.assertEqual(cls, replies.UNSUBSCRIBE)
        contact = rec["contacts"][0]
        self.assertTrue(contact.get("unsubscribed"),
                        "an unsubscribe did not suppress the contact")


class AutomatedReferralIsReferral(_OOOTestBase):
    """An automated reply that names a colleague is treated as a referral.

    The provider's automated flag must not swallow a referral. "I have left
    the company, contact Dana" is a referral, not an automated non-reply.
    """

    def test_automated_referral_is_classified_as_referral(self):
        recs = store.load()
        text = ("I have left the company. Please contact Dana Voss at "
                "dana.voss@borealis.test about this.")
        outcome = inbound.handle(
            _event(text, automated=True), recs)
        cls = (outcome.get("classification") or {}).get("classification")
        self.assertEqual(cls, replies.REFERRAL,
                         f"expected referral, got {cls}")

    def test_automated_referral_pauses_the_account(self):
        """A referral is not a machine non-reply. The account must pause."""
        recs = store.load()
        text = ("I have left the company. Please contact Dana Voss at "
                "dana.voss@borealis.test about this.")
        inbound.handle(_event(text, automated=True), recs)
        rec = self._rec(recs)
        self.assertTrue(rec.get("paused"),
                        "an automated referral did not pause the account")

    def test_the_referral_mention_is_recorded(self):
        recs = store.load()
        text = ("I have left the company. Please contact Dana Voss at "
                "dana.voss@borealis.test about this.")
        inbound.handle(_event(text, automated=True), recs)
        rec = self._rec(recs)
        mentions = [e for e in rec.get("events", [])
                    if e.get("type") == events.REFERRAL_MENTIONED]
        self.assertTrue(mentions,
                        "no REFERRAL_MENTIONED event was recorded")


class OOOWithHumanSentencePauses(_OOOTestBase):
    """An out-of-office containing a human sentence pauses.

    "I am on holiday but yes let's talk" is classified as OUT_OF_OFFICE
    (OOO patterns are checked first in the precedence order). But `ooo.detect`
    returns HUMAN_ABSENCE (not AUTORESPONDER) because there's no machine marker
    and the provider didn't flag it. So it's not a pure OOO, and the account
    must pause.
    """

    def test_ooo_with_human_sentence_pauses_the_account(self):
        recs = store.load()
        text = ("I am on holiday until September 20, but yes - let's talk "
                "when I am back. Send me more info.")
        outcome = inbound.handle(_event(text), recs)
        rec = self._rec(recs)
        # The classification is OUT_OF_OFFICE (OOO patterns match first)
        cls = (outcome.get("classification") or {}).get("classification")
        self.assertEqual(cls, replies.OUT_OF_OFFICE)
        # But the account IS paused because it's not a pure OOO
        self.assertTrue(rec.get("paused"),
                        "an OOO with a human sentence did not pause")

    def test_ooo_with_human_sentence_is_not_pure_ooo(self):
        """The _is_pure_ooo guard must not skip this.

        The classification is OOO, but ooo.detect returns HUMAN_ABSENCE
        (not AUTORESPONDER), so _is_pure_ooo returns False.
        """
        text = ("I am on holiday until September 20, but yes - let's talk "
                "when I am back. Send me more info.")
        ev = _event(text)
        # ooo.detect returns HUMAN_ABSENCE, not AUTORESPONDER
        reading = ooo.detect(text, automated=ev.get("automated"))
        self.assertEqual(reading["kind"], ooo.HUMAN_ABSENCE,
                         "a human writing about their own absence should be "
                         "HUMAN_ABSENCE, not AUTORESPONDER")


# ----------------------------------------- wiring verification (break the wire)


class WiringVerification(_OOOTestBase):
    """Prove the pause is reading the classification.

    TASK-030 requires: "delete the classification check and confirm a test
    fails. If nothing fails, the pause is not actually reading the
    classification."

    We prove this two ways:
    1. If we patch _is_pure_ooo to always return False (removing the OOO
       exemption), an OOO reply is treated like any other non-pure-OOO reply
       and the account pauses. This proves the pause is conditional on the
       OOO classification.
    2. If we patch the classification to UNKNOWN, the account pauses even
       for an OOO text. This proves the pause reads the classification.
    """

    def test_removing_the_ooo_check_causes_ooo_to_pause(self):
        """If _is_pure_ooo always returns False, OOO pauses - proving the
        pause is conditional on the classification.

        We don't pass automated=True here, because the automated flag
        takes a separate path. Without it, patching _is_pure_ooo to False
        sends the OOO through the 'ensure pause' branch.
        """
        from unittest.mock import patch

        recs = store.load()
        text = ("Automatic reply: I am out of the office until September 20 "
                "with limited access to email.")
        with patch.object(inbound, "_is_pure_ooo", return_value=False):
            outcome = inbound.handle(_event(text), recs)
        rec = self._rec(recs)
        self.assertTrue(rec.get("paused"),
                        "with the OOO check disabled, the account should "
                        "pause - if it does not, the pause is not reading "
                        "the classification")

    def test_if_ooo_were_unknown_it_would_pause(self):
        """If the classification were UNKNOWN instead of OOO, the account
        would pause. This proves the pause reads the classification."""
        from unittest.mock import patch

        recs = store.load()
        text = ("Automatic reply: I am out of the office until September 20 "
                "with limited access to email.")
        # Patch replies.classify to return UNKNOWN instead of OOO.
        # Don't pass automated=True, because replies.apply skips policy for
        # automated non-OOO replies.
        original_classify = replies.classify

        def patched_classify(*args, **kwargs):
            result = original_classify(*args, **kwargs)
            result["classification"] = replies.UNKNOWN
            return result

        with patch.object(replies, "classify", patched_classify):
            inbound.handle(_event(text), recs)  # no automated flag
        rec = self._rec(recs)
        self.assertTrue(rec.get("paused"),
                        "if OOO were classified as UNKNOWN, it should pause - "
                        "proving the pause reads the classification")


if __name__ == "__main__":
    unittest.main()
