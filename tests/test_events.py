"""Event ingestion and the reporting model. Tasks E and F.

Nothing here calls a provider. The adapters are fed payloads shaped the way
EmailBison and HeyReach send them, so wiring a real webhook later is a
transport change rather than a behaviour change.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import accountpolicy, cadence, events, report, store
from tests.base import FIXTURES

BISON_PAYLOAD = {
    "events": [
        {"id": "eb-1001", "event": "delivered", "email": "ivana.saric@meridian.test",
         "timestamp": "2026-08-26T09:00:00+00:00",
         "custom_variables": {"record_id": "meridian", "contact_key": "ivana-saric",
                              "client": "productive"}},
        {"id": "eb-1002", "event": "bounced", "email": "nikola@vantage.test",
         "timestamp": "2026-08-26T09:05:00+00:00",
         "custom_variables": {"record_id": "vantage", "contact_key": "nikola-feric",
                              "client": "productive"}},
        {"id": "eb-1003", "event": "replied", "email": "ivana.saric@meridian.test",
         "timestamp": "2026-08-26T10:00:00+00:00",
         "custom_variables": {"record_id": "meridian", "contact_key": "ivana-saric",
                              "client": "productive"}},
        {"id": "eb-1004", "event": "opened", "email": "ivana.saric@meridian.test",
         "timestamp": "2026-08-26T10:01:00+00:00", "custom_variables": {}},
    ]
}

HEYREACH_PAYLOAD = {
    "events": [
        {"id": "hr-2001", "eventType": "CONNECTION_ACCEPTED",
         "profileUrl": "https://www.linkedin.com/in/ivana-saric",
         "timestamp": "2026-08-26T11:00:00+00:00",
         "customUserFields": [{"name": "record_id", "value": "meridian"},
                              {"name": "contact_key", "value": "ivana-saric"}]},
        {"id": "hr-2002", "eventType": "MESSAGE_REPLY",
         "profileUrl": "https://www.linkedin.com/in/rowan-blake",
         "timestamp": "2026-08-26T12:00:00+00:00",
         "customUserFields": [{"name": "record_id", "value": "harbourline"},
                              {"name": "contact_key", "value": "rowan-blake"}]},
    ]
}


class EventTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-events-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rec(self, rid="meridian"):
        return store.get(rid)

    def types(self, rid="meridian"):
        return [e["type"] for e in self.rec(rid).get("events") or []]


class TestTheNeutralShape(EventTest):
    def test_every_event_carries_the_stable_identifiers(self):
        event = events.neutral(client="productive", record_id="meridian",
                               contact_key="ivana-saric", channel="email",
                               type=events.REPLY_RECEIVED, provider="emailbison",
                               provider_event_id="eb-1", at="2026-08-26T09:00:00+00:00")
        for field in events.NEUTRAL_FIELDS:
            self.assertIn(field, event)

    def test_an_unknown_event_type_is_refused_not_guessed(self):
        result = events.apply(store.load(), events.neutral(
            record_id="meridian", type="telepathy"))
        self.assertEqual(result["status"], "unknown")

    def test_an_unknown_record_is_held_not_guessed(self):
        result = events.apply(store.load(), events.neutral(
            record_id="nobody", type=events.EMAIL_DELIVERED))
        self.assertEqual(result["status"], "unmatched")
        self.assertIn("no record", result["why"])

    def test_an_unknown_contact_is_held_not_guessed(self):
        result = events.apply(store.load(), events.neutral(
            record_id="meridian", contact_key="nobody-here",
            type=events.EMAIL_DELIVERED))
        self.assertEqual(result["status"], "unmatched")
        self.assertIn("no contact", result["why"])

    def test_a_mismatched_client_is_refused(self):
        result = events.apply(store.load(), events.neutral(
            record_id="meridian", client="someone-else",
            type=events.EMAIL_DELIVERED))
        self.assertEqual(result["status"], "unmatched")

    def test_a_record_can_be_matched_by_address_when_no_id_is_given(self):
        results = events.ingest([events.neutral(
            type=events.EMAIL_DELIVERED, channel="email",
            provider="emailbison", provider_event_id="eb-x",
            email="ivana.saric@meridian.test")])
        self.assertEqual(results[0]["status"], "applied")
        self.assertEqual(results[0]["record_id"], "meridian")
        self.assertEqual(results[0]["contact"], "ivana-saric")


class TestIdempotency(EventTest):
    def test_the_same_provider_event_twice_changes_state_once(self):
        event = events.neutral(record_id="meridian", contact_key="ivana-saric",
                               type=events.EMAIL_DELIVERED, channel="email",
                               provider="emailbison", provider_event_id="eb-1001")
        first = events.ingest([event])
        second = events.ingest([event])
        self.assertEqual(first[0]["status"], "applied")
        self.assertEqual(second[0]["status"], "duplicate")
        self.assertEqual(self.types().count(events.EMAIL_DELIVERED), 1)

    def test_a_replayed_webhook_page_is_harmless(self):
        events.ingest(events.from_emailbison(BISON_PAYLOAD))
        before = len(self.rec()["events"])
        events.ingest(events.from_emailbison(BISON_PAYLOAD))
        self.assertEqual(len(self.rec()["events"]), before)

    def test_a_replayed_reply_does_not_pause_twice(self):
        # TASK-030: events.ingest no longer pauses; the pause now lives in
        # inbound.handle after classification. Simulate what inbound.handle
        # does for the reply in the payload.
        events.ingest(events.from_emailbison(BISON_PAYLOAD))
        recs = store.load()
        accountpolicy._hold_account(
            store.get("meridian", recs=recs), "ivana-saric", "unknown",
            "2026-08-26T10:00:00+00:00", channel="email",
            reason=events.REPLY_RECEIVED)
        store.save(recs)
        paused_at = self.rec()["paused"]["since"]
        events.ingest(events.from_emailbison(BISON_PAYLOAD))
        recs = store.load()
        accountpolicy._hold_account(
            store.get("meridian", recs=recs), "ivana-saric", "unknown",
            "2026-08-26T10:00:00+00:00", channel="email",
            reason=events.REPLY_RECEIVED)
        store.save(recs)
        self.assertEqual(self.rec()["paused"]["since"], paused_at)
        self.assertEqual(self.types().count(events.COMPANY_PAUSED), 1)


class TestRepliesPauseTheCompany(EventTest):
    def test_an_email_reply_pauses_both_tracks_company_wide(self):
        # TASK-030: events.ingest no longer pauses; simulate the pause that
        # inbound.handle now applies after classification.
        events.ingest(events.from_emailbison(BISON_PAYLOAD))
        recs = store.load()
        accountpolicy._hold_account(
            store.get("meridian", recs=recs), "ivana-saric", "unknown",
            "2026-08-26T10:00:00+00:00", channel="email",
            reason=events.REPLY_RECEIVED)
        store.save(recs)
        rec = self.rec()
        self.assertTrue(rec["paused"])
        timeline = cadence.build(rec)
        statuses = {s["status"] for steps in timeline["contacts"].values()
                    for s in steps.values()}
        self.assertEqual(statuses, {"paused"})

    def test_a_linkedin_reply_pauses_that_company(self):
        # TASK-030: events.ingest no longer pauses; simulate the pause that
        # inbound.handle now applies after classification.
        events.ingest(events.from_heyreach(HEYREACH_PAYLOAD))
        recs = store.load()
        accountpolicy._hold_account(
            store.get("harbourline", recs=recs), "rowan-blake", "unknown",
            "2026-08-26T12:00:00+00:00", channel="linkedin",
            reason=events.REPLY_RECEIVED)
        store.save(recs)
        self.assertTrue(self.rec("harbourline")["paused"])
        self.assertEqual(self.rec("harbourline")["paused"]["channel"], "linkedin")

    def test_an_unrelated_company_carries_on(self):
        events.ingest(events.from_emailbison(BISON_PAYLOAD))
        self.assertIsNone(self.rec("harbourline").get("paused"))
        self.assertIsNone(cadence.build(self.rec("harbourline"))["paused"])

    def test_a_delivery_does_not_pause_anything(self):
        events.ingest([events.neutral(
            record_id="meridian", contact_key="ivana-saric", channel="email",
            type=events.EMAIL_DELIVERED, provider="emailbison",
            provider_event_id="eb-only-delivered")])
        self.assertIsNone(self.rec().get("paused"))

    def test_a_bounce_does_not_pause_anything(self):
        events.ingest([events.neutral(
            record_id="vantage", contact_key="nikola-feric", channel="email",
            type=events.EMAIL_BOUNCED, provider="emailbison",
            provider_event_id="eb-bounce")])
        self.assertIsNone(self.rec("vantage").get("paused"))
        self.assertIn(events.EMAIL_BOUNCED, self.types("vantage"))

    def test_a_connection_accepted_does_not_pause_but_is_recorded(self):
        events.ingest(events.from_heyreach(
            {"events": [HEYREACH_PAYLOAD["events"][0]]}))
        self.assertIsNone(self.rec().get("paused"))
        self.assertIn(events.LINKEDIN_CONNECTED, self.types())
        self.assertTrue(cadence.accepted_connection(self.rec()))

    def test_every_event_is_auditable_on_the_record(self):
        # TASK-030: events.ingest no longer pauses; simulate the pause that
        # inbound.handle now applies after classification.
        events.ingest(events.from_emailbison(BISON_PAYLOAD))
        recs = store.load()
        accountpolicy._hold_account(
            store.get("meridian", recs=recs), "ivana-saric", "unknown",
            "2026-08-26T10:00:00+00:00", channel="email",
            reason=events.REPLY_RECEIVED)
        store.save(recs)
        rec = self.rec()
        self.assertTrue(any(e["step"] == "event" for e in rec["log"]))
        self.assertTrue(any(e["step"] == "paused" for e in rec["log"]))
        stored = [e for e in rec["events"] if e.get("provider") == "emailbison"]
        self.assertTrue(all(e.get("provider_event_id") for e in stored))


class TestTheAdapters(EventTest):
    def test_emailbison_maps_its_vocabulary_onto_ours(self):
        mapped = events.from_emailbison(BISON_PAYLOAD)
        kinds = [e["type"] for e in mapped]
        self.assertEqual(kinds, [events.EMAIL_DELIVERED, events.EMAIL_BOUNCED,
                                 events.REPLY_RECEIVED])
        self.assertTrue(all(e["channel"] == "email" for e in mapped))
        self.assertTrue(all(e["provider"] == "emailbison" for e in mapped))

    def test_an_event_we_do_not_act_on_is_dropped_by_the_adapter(self):
        kinds = [e["type"] for e in events.from_emailbison(BISON_PAYLOAD)]
        self.assertEqual(len(kinds), 3)          # the "opened" event is not mapped

    def test_heyreach_maps_its_vocabulary_onto_ours(self):
        mapped = events.from_heyreach(HEYREACH_PAYLOAD)
        self.assertEqual([e["type"] for e in mapped],
                         [events.LINKEDIN_CONNECTED, events.REPLY_RECEIVED])
        self.assertTrue(all(e["channel"] == "linkedin" for e in mapped))

    def test_the_adapters_call_nothing(self):
        import inspect
        for adapter in (events.from_emailbison, events.from_heyreach):
            source = inspect.getsource(adapter)
            self.assertNotIn("request", source)
            self.assertNotIn("http", source)

    def test_an_adapter_survives_a_payload_with_missing_fields(self):
        mapped = events.from_emailbison({"events": [{"event": "delivered"}]})
        self.assertEqual(len(mapped), 1)
        self.assertIsNone(mapped[0]["record_id"])
        result = events.apply(store.load(), mapped[0])
        self.assertEqual(result["status"], "unmatched")


class TestTheReportingModel(EventTest):
    def setUp(self):
        super().setUp()
        events.ingest(events.from_emailbison(BISON_PAYLOAD))
        events.ingest(events.from_heyreach(HEYREACH_PAYLOAD))
        # TASK-030: events.ingest no longer pauses; simulate the pauses that
        # inbound.handle now applies after classification for each reply.
        recs = store.load()
        accountpolicy._hold_account(
            store.get("meridian", recs=recs), "ivana-saric", "unknown",
            "2026-08-26T10:00:00+00:00", channel="email",
            reason=events.REPLY_RECEIVED)
        accountpolicy._hold_account(
            store.get("harbourline", recs=recs), "rowan-blake", "unknown",
            "2026-08-26T12:00:00+00:00", channel="linkedin",
            reason=events.REPLY_RECEIVED)
        store.save(recs)

    def test_metrics_are_derived_from_events_not_counters(self):
        stats = report.funnel()
        self.assertEqual(stats["delivered"], 1)
        self.assertEqual(stats["bounced"], 1)
        self.assertEqual(stats["replies"], 2)
        self.assertEqual(stats["connections_accepted"], 1)
        self.assertEqual(stats["companies_paused"], 2)

    def test_counts_can_be_grouped_by_client(self):
        grouped = report.by_dimension("client")
        self.assertIn("productive", grouped)
        self.assertEqual(grouped["productive"]["replies"], 2)

    def test_counts_can_be_grouped_by_batch(self):
        grouped = report.by_dimension("batch")
        self.assertTrue(grouped)

    def test_counts_can_be_grouped_by_persona(self):
        grouped = report.by_dimension("persona")
        self.assertIn("champion", grouped)
        self.assertGreaterEqual(grouped["champion"]["replies"], 1)

    def test_counts_can_be_grouped_by_angle(self):
        grouped = report.by_dimension("angle")
        self.assertTrue(any(v["replies"] for v in grouped.values()))

    def test_counts_can_be_grouped_by_channel(self):
        grouped = report.by_dimension("channel")
        self.assertEqual(grouped["email"]["replies"], 1)
        self.assertEqual(grouped["linkedin"]["replies"], 1)

    def test_a_row_carries_every_dimension_it_can_be_sliced_by(self):
        row = report.rows()[0]
        for field in report.DIMENSIONS:
            self.assertIn(field, row)

    def test_what_cannot_be_measured_is_named_rather_than_estimated(self):
        missing = report.unavailable()
        self.assertIn("meetings_booked", missing)
        for why in missing.values():
            self.assertTrue(why)

    def test_positive_replies_are_measurable_now_that_replies_are_classified(self):
        """It was on the unavailable list until a classifier existed. It is not
        an estimate: it counts positive_reply_detected events."""
        self.assertNotIn("positive_replies", report.unavailable())
        self.assertIn("positive_replies", report.daily_summary([], []))

    def test_a_metric_with_no_source_is_absent_rather_than_zero(self):
        summary = report.daily_summary([], [])
        self.assertIsNone(summary["meetings_booked"])
        self.assertIsNone(summary["provider_spend"])

    def test_grouping_by_something_that_is_not_a_dimension_is_refused(self):
        with self.assertRaises(ValueError):
            report.count(report.rows(), by="favourite_colour")


class TestPipelineEventsAreEmitted(unittest.TestCase):
    """The internal stream, from a real offline pipeline run."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-pipeline-events-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ingest_records_the_batch_and_the_suppression(self):
        from src import ingest
        csv_path = os.path.join(self.tmp, "b.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("company,domain,lane,client\n"
                    "Blocked Co,blocked.test,domains,productive\n"
                    "Meridian,meridian.test,domains,productive\n")
        ingest.run(csv_path, client="productive", lane="domains",
                   suppress_path=os.path.join(FIXTURES, "suppress-test.txt"))

        meridian = store.get("meridian")
        blocked = store.get("blocked-co")
        self.assertIn(events.BATCH_INGESTED, [e["type"] for e in meridian["events"]])
        self.assertIn(events.RECORD_SUPPRESSED, [e["type"] for e in blocked["events"]])
        self.assertTrue(meridian["batch"]["id"])
        self.assertEqual(meridian["batch"]["client"], "productive")

    def test_a_batch_id_lets_reporting_group_by_batch(self):
        from src import ingest
        csv_path = os.path.join(self.tmp, "b.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("company,domain,lane,client\nMeridian,meridian.test,domains,productive\n")
        ingest.run(csv_path, client="productive", lane="domains",
                   suppress_path=os.path.join(FIXTURES, "suppress-test.txt"))
        grouped = report.by_dimension("batch")
        self.assertEqual(len(grouped), 1)
        self.assertNotIn("unbatched", grouped)


if __name__ == "__main__":
    unittest.main()


class AmbiguousIdentityRefusesForBothIdentifiers(unittest.TestCase):
    """A reply nobody can attribute must not be attributed to somebody.

    THE ASYMMETRY THIS PINS. `match_contact` gathered LinkedIn candidates and
    refused when there were two, under a comment saying picking one "would
    attribute somebody's reply to the wrong person" - and the email branch
    three lines above returned on its first hit. So the rule held for one
    identifier and not the other.

    A shared inbox is where that bites: two people at one company both listed
    against info@ or sales@. The account-level hold means nothing ships either
    way, so this is not a send bug; it is a wrong-person bug, and it surfaces
    the day an operator lifts the account hold and the individual block is on
    the colleague rather than on whoever wrote.
    """

    def rec(self, *contacts):
        return {"id": "acme", "domain": "acme.test", "contacts": list(contacts)}

    def contact(self, key, email=None, linkedin=None):
        return {"key": key, "email": email, "linkedin": linkedin}

    def test_one_email_match_is_an_answer(self):
        rec = self.rec(self.contact("a", email="ana@acme.test"),
                       self.contact("b", email="bo@acme.test"))
        self.assertEqual(
            events.match_contact(rec, {"email": "ana@acme.test"}), "a")

    def test_a_shared_inbox_on_two_contacts_refuses(self):
        rec = self.rec(self.contact("a", email="info@acme.test"),
                       self.contact("b", email="info@acme.test"))
        self.assertIsNone(
            events.match_contact(rec, {"email": "info@acme.test"}),
            "a reply to a shared inbox was attributed to whichever contact "
            "happened to be listed first")

    def test_it_is_case_insensitive_before_it_is_ambiguous(self):
        rec = self.rec(self.contact("a", email="Info@Acme.test"),
                       self.contact("b", email="info@acme.test"))
        self.assertIsNone(
            events.match_contact(rec, {"email": "INFO@acme.test"}))

    def test_two_identifiers_pointing_at_different_people_refuses(self):
        """The new failure mode the fix introduces, and it is the right one."""
        rec = self.rec(
            self.contact("a", email="ana@acme.test"),
            self.contact("b", linkedin="https://www.linkedin.com/in/bo"))
        self.assertIsNone(events.match_contact(
            rec, {"email": "ana@acme.test",
                  "linkedin": "https://www.linkedin.com/in/bo"}))

    def test_both_identifiers_on_the_same_person_still_resolves(self):
        rec = self.rec(self.contact("a", email="ana@acme.test",
                                    linkedin="https://www.linkedin.com/in/ana"))
        self.assertEqual(events.match_contact(
            rec, {"email": "ana@acme.test",
                  "linkedin": "https://www.linkedin.com/in/ana"}), "a")

    def test_an_explicit_contact_key_still_wins(self):
        rec = self.rec(self.contact("a", email="info@acme.test"),
                       self.contact("b", email="info@acme.test"))
        self.assertEqual(
            events.match_contact(rec, {"contact_key": "b",
                                         "email": "info@acme.test"}), "b")

    def test_the_linkedin_side_still_refuses_ambiguity(self):
        rec = self.rec(
            self.contact("a", linkedin="https://www.linkedin.com/in/ana"),
            self.contact("b", linkedin="https://www.linkedin.com/in/ana"))
        self.assertIsNone(events.match_contact(
            rec, {"linkedin": "https://www.linkedin.com/in/ana"}))
