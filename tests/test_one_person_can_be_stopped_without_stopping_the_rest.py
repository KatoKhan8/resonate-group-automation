#!/usr/bin/env python3
"""After a reply, the NEXT email to that one person does not go.

The invariant the whole safety argument rests on, and until `leadstop` existed
it was not true: a reply paused the record, which stops US planning another
step, while the provider kept its own queue and its own scheduler. "Suppressed"
meant "we will not plan another one" and never "they will not receive another
one". For a reply EmailBison happens to stop natively; for a suppression, an
agency DNC or an account stop, nothing was telling it anything at all.

Proven live on 2026-09-13 (campaign 444: one lead `sending_paused` ->
`stopped` while its sibling did not move and the campaign did not move) and
pinned here.

The tests that matter most are the ones about what must NOT happen: the
bystander must not move, and a stop that cannot be confirmed must never be
recorded as a stop.
"""
import unittest

from src import campaigns, events, leadstop, store
from src import providers
from tests.base import QueueTest


class FakeBison:
    """EmailBison's measured behaviour, including the parts that mislead.

    Chiefly: `stop-future-emails` answers 200 for a lead the campaign does not
    hold, and does nothing. A caller that trusts the status code records a
    stop that never happened.
    """

    STOPPED_STATES = ("stopped", "replied", "bounced", "sequence_finished",
                      "unsubscribed")

    def __init__(self):
        self.members = {77: {11: "in_sequence", 12: "in_sequence"}}
        self.campaigns = {77: {"id": 77, "status": "paused"}}
        self.writes = 0
        self.lands = True

    def membership(self, campaign_id, lead_ids=None, per_page=200):
        rows = dict(self.members.get(int(campaign_id), {}))
        if lead_ids is None:
            return rows
        wanted = {int(i) for i in lead_ids}
        return {k: v for k, v in rows.items() if k in wanted}

    def campaign(self, campaign_id):
        return dict(self.campaigns[int(campaign_id)])

    def stop_lead(self, campaign_id, lead_ids, attempts=8, interval=0):
        held = self.members[int(campaign_id)]
        absent = [int(i) for i in lead_ids if int(i) not in held]
        if absent:
            raise providers.ProviderError(
                f"lead(s) {absent} are not in campaign {campaign_id}")
        self.writes += 1
        if not self.lands:
            raise providers.ProviderError(
                "the provider accepted the request but the lead still does "
                "not read as stopped. Provider state is UNKNOWN")
        for i in lead_ids:
            held[int(i)] = "stopped"
        return {"stopped": {int(i): "stopped" for i in lead_ids},
                "untouched": {k: v for k, v in held.items()
                              if int(k) not in {int(i) for i in lead_ids}}}


class StoppingOnePerson(QueueTest):

    def setUp(self):
        super().setUp()
        self.bison = FakeBison()
        self._real = leadstop.bison
        leadstop.bison = self.bison
        self.addCleanup(setattr, leadstop, "bison", self._real)

        store.save([
            self._record("rec-subject", "subject@example.com", 11),
            self._record("rec-bystander", "bystander@example.com", 12)])
        row = campaigns.new_campaign("camp-stop", "productive", "Stop test")
        row["record_ids"] = ["rec-subject", "rec-bystander"]
        row["bison_campaign_id"] = 77
        campaigns.save([row])

    @staticmethod
    def _record(rid, email, lead_id):
        return {"id": rid, "client": "productive", "domain": "example.com",
                "company": "Example", "state": "ready",
                "contacts": [{"key": f"{rid}-c1", "email": email,
                              "first_name": "Test", "last_name": "Person",
                              "sendable": True, "bison_lead_id": lead_id}]}

    def _subject(self):
        rec = next(r for r in store.load() if r["id"] == "rec-subject")
        return rec, rec["contacts"][0]

    def test_the_person_stops_and_nobody_else_does(self):
        rec, contact = self._subject()
        report = leadstop.stop_contact(rec, contact, "reply_received",
                                       live=True)
        self.assertTrue(report["stopped"])
        self.assertEqual(self.bison.members[77][11], "stopped")
        self.assertEqual(self.bison.members[77][12], "in_sequence",
                         "stopping one person moved somebody else")
        self.assertEqual(self.bison.campaign(77)["status"], "paused",
                         "a per-lead stop changed the campaign")

    def test_a_dry_run_does_not_write(self):
        rec, contact = self._subject()
        report = leadstop.stop_contact(rec, contact, "reply_received",
                                       live=False)
        self.assertFalse(report["stopped"])
        self.assertEqual(self.bison.writes, 0)
        self.assertEqual(self.bison.members[77][11], "in_sequence")

    def test_stopping_an_already_stopped_person_writes_nothing(self):
        self.bison.members[77][11] = "stopped"
        rec, contact = self._subject()
        report = leadstop.stop_contact(rec, contact, "reply_received",
                                       live=True)
        self.assertTrue(report["already"])
        self.assertTrue(report["stopped"])
        self.assertEqual(self.bison.writes, 0)

    def test_a_stop_that_cannot_be_confirmed_is_not_recorded(self):
        """The failure that would matter most: believing somebody stopped."""
        self.bison.lands = False
        rec, contact = self._subject()
        with self.assertRaises(leadstop.StopUnverified):
            leadstop.stop_contact(rec, contact, "reply_received", live=True)
        saved = next(r for r in store.load() if r["id"] == "rec-subject")
        self.assertEqual(
            [e for e in saved.get("events") or []
             if e.get("type") == events.PROVIDER_STOP_CONFIRMED], [],
            "an unconfirmed stop was written down as confirmed")

    def test_an_unbound_contact_is_refused_not_guessed(self):
        """No provider id means nobody to stop. Searching by address guesses."""
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "rec-subject":
                    row["contacts"][0].pop("bison_lead_id")
        rec, contact = self._subject()
        with self.assertRaises(leadstop.StopRefused) as caught:
            leadstop.stop_contact(rec, contact, "reply_received", live=True)
        self.assertIn("bison_lead_id", str(caught.exception))
        self.assertEqual(self.bison.writes, 0)

    def test_a_cross_tenant_stop_is_refused(self):
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "rec-subject":
                    row["client"] = "someone-else"
        rec, contact = self._subject()
        with self.assertRaises(leadstop.StopRefused):
            leadstop.stop_contact(rec, contact, "reply_received", live=True)
        self.assertEqual(self.bison.writes, 0)

    def test_the_stop_event_goes_through_the_canonical_writer(self):
        """A writer that goes round the door hides a locked door.

        This appended to `rec["events"]` directly, and the bypass concealed a
        bug in itself: `PROVIDER_STOP_CONFIRMED` was in neither `INTERNAL` nor
        `EXTERNAL`, so it was absent from `events.KNOWN` and `events.record`
        RAISED on it. Nothing noticed because nothing called `events.record`.
        """
        self.assertIn(events.PROVIDER_STOP_CONFIRMED, events.KNOWN)
        rec, contact = self._subject()
        leadstop.stop_contact(rec, contact, "reply_received", live=True)
        saved = next(r for r in store.load() if r["id"] == "rec-subject")
        stop = next(e for e in saved["events"]
                    if e.get("type") == events.PROVIDER_STOP_CONFIRMED)
        # The canonical writer stamps these. A hand-appended dict has neither,
        # and an event with no id is an event nothing can deduplicate.
        self.assertTrue(stop.get("id"), "no id: this bypassed events.record")
        self.assertTrue(stop.get("provider_event_id"))

    def test_recording_the_same_stop_twice_writes_one_event(self):
        """A re-run, a retry, or a sweep crossing a reply."""
        rec, contact = self._subject()
        leadstop.stop_contact(rec, contact, "reply_received", live=True)
        fresh = next(r for r in store.load() if r["id"] == "rec-subject")
        leadstop._record(fresh, contact,
                         {"lead_id": 11, "provider_campaign": 77,
                          "why": "reply_received", "status_after": "stopped"})
        saved = next(r for r in store.load() if r["id"] == "rec-subject")
        stops = [e for e in saved["events"]
                 if e.get("type") == events.PROVIDER_STOP_CONFIRMED]
        self.assertEqual(len(stops), 1, stops)

    def test_the_record_says_when_and_why(self):
        rec, contact = self._subject()
        leadstop.stop_contact(rec, contact, "agency_dnc", live=True)
        saved = next(r for r in store.load() if r["id"] == "rec-subject")
        stops = [e for e in saved.get("events") or []
                 if e.get("type") == events.PROVIDER_STOP_CONFIRMED]
        self.assertEqual(len(stops), 1)
        self.assertEqual(stops[0]["why"], "agency_dnc")
        self.assertEqual(stops[0]["status"], "stopped")


class TheSweepCatchesEveryStopReason(QueueTest):
    """A reply comes through `inbound`. Nothing else did.

    A suppression, an agency DNC, an account stop and an unsubscribe read
    from a file all change canonical state and told the provider nothing.
    The sweep asks the question the other way round - of the people actually
    staged at the provider, who is now ineligible for a do-not-contact
    reason - so a stop reason added later is covered without editing it.
    """

    def setUp(self):
        super().setUp()
        self.bison = FakeBison()
        self._real = leadstop.bison
        leadstop.bison = self.bison
        self.addCleanup(setattr, leadstop, "bison", self._real)
        row = campaigns.new_campaign("camp-stop", "productive", "Sweep test")
        row["record_ids"] = ["rec-subject", "rec-bystander"]
        row["bison_campaign_id"] = 77
        campaigns.save([row])

    @staticmethod
    def _record(rid, email, lead_id, **extra):
        rec = {"id": rid, "client": "productive", "domain": "example.com",
               "company": "Example", "state": "ready",
               "contacts": [{"key": f"{rid}-c1", "email": email,
                             "first_name": "Test", "last_name": "Person",
                             "sendable": True, "bison_lead_id": lead_id}]}
        rec.update(extra)
        return rec

    def test_an_unsubscribed_person_is_stopped_at_the_provider(self):
        subject = self._record("rec-subject", "subject@example.com", 11)
        subject["contacts"][0]["unsubscribed"] = True
        store.save([subject,
                    self._record("rec-bystander", "b@example.com", 12)])
        report = leadstop.sweep(live=True)
        self.assertEqual(report["checked"], 2)
        self.assertEqual([r["contact"] for r in report["stopped"]],
                         ["rec-subject-c1"])
        self.assertEqual(self.bison.members[77][11], "stopped")
        self.assertEqual(self.bison.members[77][12], "in_sequence",
                         "the sweep stopped somebody it had no reason to")

    def test_a_dry_sweep_writes_nothing(self):
        subject = self._record("rec-subject", "subject@example.com", 11)
        subject["contacts"][0]["unsubscribed"] = True
        store.save([subject])
        leadstop.sweep(live=False)
        self.assertEqual(self.bison.writes, 0)
        self.assertEqual(self.bison.members[77][11], "in_sequence")

    def test_an_unstaged_contact_is_never_checked(self):
        """Nobody at the provider, nothing to stop."""
        rec = self._record("rec-subject", "subject@example.com", 11)
        rec["contacts"][0].pop("bison_lead_id")
        rec["contacts"][0]["unsubscribed"] = True
        store.save([rec])
        report = leadstop.sweep(live=True)
        self.assertEqual(report["checked"], 0)
        self.assertEqual(self.bison.writes, 0)

    def test_running_it_twice_writes_once(self):
        subject = self._record("rec-subject", "subject@example.com", 11)
        subject["contacts"][0]["unsubscribed"] = True
        store.save([subject])
        leadstop.sweep(live=True)
        before = self.bison.writes
        second = leadstop.sweep(live=True)
        self.assertEqual(self.bison.writes, before,
                         "the second sweep wrote again")
        self.assertEqual(len(second["already"]), 1)


if __name__ == "__main__":
    unittest.main()
