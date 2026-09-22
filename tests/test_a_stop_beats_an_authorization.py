#!/usr/bin/env python3
"""A reply that lands after the gates must still stop the write.

REPRODUCED on 2026-09-11, and it is the sequence the mission named as a P0
condition: authorize, a reply arrives, the write is attempted.

    mint an Authorization                       16 gates pass
    persist a real unsubscribe                  accountpolicy.apply_reply
    eligibility.decide                          blocked:unsubscribed
    providerwrites.perform(the same token)      TRANSPORT CALLED
                                                ledger settled `sent`

No gate fired. Two separate causes, and both are answered by re-reading:

  * `perform` revalidated nothing. Its checks - genuine Authorization, unspent,
    matching channel, open reservation - all ask whether the TOKEN is good.
    None of them asks whether the PERSON still wants to hear from us.
  * `authorize` is handed the caller's own record dict, so a worker that loaded
    the record before the reply authorizes cleanly even though the reply is
    already on disk. The module docstring promises gate 4 is "RE-READ now";
    that was true of collision and of nothing else.

And `Authorization.at` was stamped at mint time and read by nothing, so a token
minted at any point in the past was as good as a fresh one.

Latent rather than exploitable when found - `providerwrites.SUPPORTED` is empty
and `authorize` has no caller in `src/` - which is the only reason this is a
test rather than an incident. The brakes were built before the caller; this one
had a hole in it.
"""
import unittest
from unittest import mock

from src import (accountpolicy, approval, actionledger, campaigns, clients, eligibility,
                 executionguard, providerwrites, store, verification)
from src.providers import heyreach
from src import campaigns
from tests.base import QueueTest

# TASK-137: `LINKEDIN_ADD_LEAD` IS NOW CONDITIONALLY SUPPORTED, so `perform`
# refuses it unless a provider read proves the destination campaign cannot
# send. This module uses that operation as its vehicle for a different
# question, so it names a DRAFT destination and fakes the one read the
# condition makes. It does NOT stub the condition itself - the predicate runs,
# on a real status string. Every test here failed loudly when the gate landed,
# which is how it is known to be reached from this path.
DRAFT_DESTINATION = 599020
CANON = "productive-linkedin-production-v1"
# PAUSED, not DRAFT: the provider answers 400 "You cannot add new leads to
# a draft campaign", so DRAFT is the one state it refuses.
DRAFT_ROW = {"id": DRAFT_DESTINATION, "status": "PAUSED", "name": "test",
             "organizationUnitId": "174892"}
CANON_ROW = {"campaign_id": CANON, "client": "productive",
             "heyreach_campaign_id": str(DRAFT_DESTINATION),
             "provider_status_expected": "PAUSED",
             "provider_note": "{connection_note}",
             "provider_actions": ["CHECK_IS_CONNECTION", "MESSAGE"]}

OPERATION = providerwrites.LINKEDIN_ADD_LEAD

# `perform` now refuses a prospect-facing write whose payload does not carry
# the approved words. These tests are about a STOP beating an authorization,
# not about that check, so they hand it a step that satisfies it - otherwise
# the words guard fires first and the refusal being measured never happens.
STEP = {"channel": "linkedin", "note": "a note somebody approved"}
FINGERPRINT = approval.fingerprint(STEP)


def a_contact(email="dana@acme.test"):
    return {"key": "acme-1", "name": "Dana Reed", "email": email,
            "linkedin": "https://www.linkedin.com/in/dana-reed",
            "selected": True, "primary": True, "verdict": "valid",
            "sendable": True, "persona": "champion", "angle": "operations",
            "verification": {"evidence": [
                verification.result("deliverable", "valid", email),
                verification.result("reoon", "valid", email)]}}


class TheDoorRevalidates(QueueTest):
    """Unit-level, against the real `revalidate`.

    Deliberately not driven through a full `authorize` run: the gates that mint
    a token need a whole approved estate, and what is under test here is
    whether the DOOR re-asks the question. A hand-built Authorization is the
    honest fixture for that, and `perform` already refuses one that has no
    reservation, which is asserted below.
    """

    def setUp(self):
        super().setUp()
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["state"] = "verified"
        rec["contacts"] = [a_contact()]
        rec["cadence"] = {"acme-1": {"day3": {
            "channel": "linkedin", "note": "hi Dana, worth a word?"}}}
        store.save([rec])
        self.auth = executionguard.Authorization(
            key="acme:acme-1:day3:linkedin", operation=OPERATION,
            channel="linkedin", workspace="productive",
            campaign_id="productive-canary", sender_id="116968",
            rec_id="acme", contact_key="acme-1", step_key="day3",
            fingerprint=FINGERPRINT, gates=("tenancy", "approval"),
            at=store.now())

    def stop_the_contact(self):
        """The canonical path, not a hand-set flag."""
        recs = store.load()
        accountpolicy.apply_reply(
            recs[0], "acme-1", outcome=accountpolicy.UNSUBSCRIBE,
            at=store.now(), reason="asked to be removed",
            channel="email", config=clients.load("productive"))
        store.save(recs)

    def test_an_age_older_than_the_ttl_is_refused(self):
        """`at` was stamped and never read. Now it decides."""
        self.auth.at = "2026-09-01T09:00:00+00:00"
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            executionguard.revalidate(self.auth)
        self.assertEqual(caught.exception.gate, "authorization_age")

    def test_a_future_stamp_buys_nothing(self):
        """A clock skew or an edited record must not buy an unlimited window -
        the same argument `readback_is_fresh` already makes for the read-back."""
        self.auth.at = "2099-01-01T00:00:00+00:00"
        with self.assertRaises(executionguard.NotAuthorized):
            executionguard.revalidate(self.auth)

    def test_a_contact_that_has_since_been_stopped_is_refused(self):
        self.stop_the_contact()
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            executionguard.revalidate(self.auth)
        self.assertEqual(caught.exception.gate, "revalidate")

    def test_the_refusal_says_what_changed(self):
        self.stop_the_contact()
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            executionguard.revalidate(self.auth)
        said = str(caught.exception)
        self.assertIn("changed after this was authorized", said)
        self.assertIn("Nothing", said)

    def test_a_record_that_has_gone_is_refused(self):
        store.save([])
        with self.assertRaises(executionguard.NotAuthorized):
            executionguard.revalidate(self.auth)

    def test_a_contact_the_record_does_not_hold_is_refused(self):
        """Asserted by naming somebody who was never there, rather than by
        deleting a contact: `refuse_evidence_loss` correctly refuses that write,
        so a vanished contact is not a state the store can reach. The branch is
        defensive and this is the honest way to exercise it."""
        self.auth.contact_key = "somebody-else"
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            executionguard.revalidate(self.auth)
        self.assertIn("no longer on record", str(caught.exception))

    def test_something_that_is_not_an_authorization_is_refused(self):
        with self.assertRaises(executionguard.NotAuthorized):
            executionguard.revalidate({"key": "acme:acme-1:day3:linkedin"})


class TheWriteIsRefusedNotJustTheToken(QueueTest):
    """`perform` must CONSULT it. A correct check nothing calls is the defect
    this repository names in its own contributing rules.

    THE FIRST VERSION OF THIS CLASS PROVED NOTHING. It asserted that the
    transport was not reached, and it passed with the `revalidate` call deleted
    from `perform` - because the fixture never reserved the key, so `perform`
    was refusing at the ledger check the whole time. A mutation sweep said so.
    The reservation below is what makes the door the only thing left that can
    refuse.
    """

    KEY = "acme:acme-1:day3:linkedin"

    def setUp(self):
        super().setUp()
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["state"] = "verified"
        rec["contacts"] = [a_contact()]
        store.save([rec])
        self.calls = []
        actionledger.reserve(
            self.KEY, channel="linkedin", workspace="productive",
            provider_workspace=10, campaign_id="productive-canary",
            sender_id="116968", rec_id="acme", contact_key="acme-1",
            step_key="day3", operation=OPERATION, fingerprint=FINGERPRINT,
            by="test", cap_per_day=10, cap_per_sender=10)

    def attempt(self, revalidate):
        auth = executionguard.Authorization(
            key=self.KEY, operation=OPERATION, channel="linkedin",
            workspace="productive", campaign_id="productive-canary",
            sender_id="116968", rec_id="acme", contact_key="acme-1",
            step_key="day3", fingerprint=FINGERPRINT, gates=("tenancy",),
            at=store.now())
        with mock.patch.object(providerwrites, "SUPPORTED", (OPERATION,)),              mock.patch.object(providerwrites,
                               "CAMPAIGN_LEVEL_STAGING_IS_PROVEN",
                               True), mock.patch.object(executionguard, "revalidate", revalidate),              mock.patch.object(heyreach, "campaign_read", return_value=dict(DRAFT_ROW)),              mock.patch.object(campaigns, "require", return_value=dict(CANON_ROW)):
            return providerwrites.perform(
                OPERATION, provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                authorization=auth,
                payload={"profile": "dana-reed", "note": STEP["note"]}, step=STEP,
                transport=lambda p: self.calls.append("transport") or {"ok": 1},
                readback=lambda: {"ok": 1}, expected={"ok": 1})

    def test_the_door_asks_before_it_writes(self):
        """The positive control AND the discriminator: with a reservation in
        place and nothing objecting, the transport is reached - and `revalidate`
        is consulted first. Delete the call from `perform` and the order is
        wrong, which is what the earlier version could not see."""
        self.attempt(lambda a, **kw: self.calls.append("revalidate"))
        self.assertEqual(self.calls, ["revalidate", "transport"])

    def test_a_refusal_from_the_door_stops_the_transport(self):
        def refuse(auth, **kw):
            self.calls.append("revalidate")
            raise executionguard.NotAuthorized(
                "revalidate", "the record changed after this was authorized",
                ())
        with self.assertRaises(executionguard.NotAuthorized):
            self.attempt(refuse)
        self.assertEqual(self.calls, ["revalidate"],
                         "the provider was written to after the door refused")

    def test_and_the_ledger_does_not_claim_a_send(self):
        def refuse(auth, **kw):
            raise executionguard.NotAuthorized("revalidate", "stopped", ())
        with self.assertRaises(executionguard.NotAuthorized):
            self.attempt(refuse)
        self.assertNotEqual(actionledger.state_of(self.KEY),
                            actionledger.SENT)

    def test_end_to_end_a_real_unsubscribe_stops_a_real_write(self):
        """No mocking of the door: the real `revalidate`, a real reply through
        `accountpolicy.apply_reply`, and a reserved key."""
        recs = store.load()
        accountpolicy.apply_reply(
            recs[0], "acme-1", outcome=accountpolicy.UNSUBSCRIBE,
            at=store.now(), reason="asked to be removed",
            channel="email", config=clients.load("productive"))
        store.save(recs)
        auth = executionguard.Authorization(
            key=self.KEY, operation=OPERATION, channel="linkedin",
            workspace="productive", campaign_id="productive-canary",
            sender_id="116968", rec_id="acme", contact_key="acme-1",
            step_key="day3", fingerprint=FINGERPRINT, gates=("tenancy",),
            at=store.now())
        with mock.patch.object(providerwrites, "SUPPORTED", (OPERATION,)), \
             mock.patch.object(providerwrites,
                               "CAMPAIGN_LEVEL_STAGING_IS_PROVEN",
                               True), \
             mock.patch.object(heyreach, "campaign_read",
                               return_value=dict(DRAFT_ROW)), \
             mock.patch.object(campaigns, "require",
                               return_value=dict(CANON_ROW)):
            with self.assertRaises(executionguard.NotAuthorized):
                providerwrites.perform(
                    OPERATION, provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                    authorization=auth,
                    payload={"profile": "dana-reed", "note": STEP["note"]}, step=STEP,
                    transport=lambda p: self.calls.append("transport"),
                    readback=lambda: {"ok": 1})
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
