"""Push preparation. BUILD-SPEC section 5.4, 5.5, phase 7.

Nothing in this file sends anything, and nothing in the module under test can:
`--live` refuses by design. These tests cover what would be sent, what is
refused, and the guarantee that a retry cannot send the same step twice.
"""
import os
import shutil
import tempfile
import unittest

from src import cadence, lint, push, store
from tests.base import FIXTURES, ProviderTest, approve_everything


class PushTest(ProviderTest):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-push-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._queue_prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        approve_everything()

    def tearDown(self):
        if self._queue_prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._queue_prev
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def rec(self, rid="meridian"):
        return store.get(rid)

    def run_push(self, day=21, **kw):
        return push.run(day=day, campaign_id=42, linkedin_account_id=3, **kw)


class TestNothingSends(PushTest):
    def test_live_is_refused_by_design(self):
        with self.assertRaises(push.LiveSendNotEnabled) as e:
            push.run(day=21, live=True)
        self.assertIn("preparation only", str(e.exception))

    def test_a_dry_run_makes_no_http_call_at_all(self):
        self.run_push()
        self.assertEqual(self.cassette.calls, [])

    def test_a_dry_run_marks_nothing_as_pushed(self):
        with open(self.queue, "rb") as f:
            before = f.read()
        self.run_push()
        with open(self.queue, "rb") as f:
            self.assertEqual(f.read(), before)

    def test_the_module_has_no_send_function(self):
        names = [n for n in dir(push) if not n.startswith("_")]
        for banned in ("send", "post", "deliver", "add_leads", "start_campaign"):
            self.assertNotIn(banned, names)


class TestTheEmailBisonPayload(PushTest):
    def test_the_payload_is_the_documented_shape(self):
        result = self.run_push()
        payload = result["payloads"]["emailbison"]
        self.assertEqual(payload["method"], "POST")
        self.assertTrue(payload["endpoint"].endswith("/campaigns/42/leads"))
        lead = payload["body"]["leads"][0]
        self.assertEqual(set(lead), {"email", "first_name", "last_name",
                                     "company_name", "custom_variables"})
        self.assertEqual(set(lead["custom_variables"]),
                         {"subject", "body", "title",
                          # Our own identity, so a reply can name the person
                          # and not only the company. `adapters` reads all
                          # three back; before, none was ever sent.
                          "record_id", "contact_key", "client",
                          # Which human owns this relationship and which of
                          # their inboxes carries it. Identifiers, not
                          # credentials. Whether EmailBison echoes these back
                          # has not been validated against the live API, so
                          # nothing reads them yet - they are sent so that a
                          # person looking at the lead in EmailBison's own UI
                          # can see who owns it.
                          "sender_id", "sender_account_id",
                          "provider_account_id"})

    def test_no_credential_travels_in_the_payload(self):
        """The sender fields are identifiers. This is what stops them drifting."""
        lead = self.run_push()["payloads"]["emailbison"]["body"]["leads"][0]
        blob = str(lead).lower()
        for forbidden in ("token", "secret", "password", "api_key", "bearer",
                          "authorization"):
            self.assertNotIn(forbidden, blob)

    def test_the_generated_subject_and_body_travel_in_custom_variables(self):
        """Section 5.4: so the client's own 5 to 7 step cadence continues."""
        lead = self.run_push()["payloads"]["emailbison"]["body"]["leads"][0]
        self.assertTrue(lead["custom_variables"]["subject"])
        self.assertGreater(len(lead["custom_variables"]["body"].split()), 39)

    def test_every_lead_in_the_payload_has_a_sendable_recipient(self):
        result = self.run_push()
        by_email = {}
        for rec in store.load():
            for c in rec.get("contacts") or []:
                if c.get("email"):
                    by_email[c["email"]] = c
        for lead in result["payloads"]["emailbison"]["body"]["leads"]:
            self.assertTrue(lint.sendable(by_email[lead["email"]]), lead["email"])

    def test_a_record_that_is_not_shippable_never_reaches_the_payload(self):
        store.drop("meridian", "suppressed (live account)")
        result = self.run_push()
        emails = [l["email"] for l in result["payloads"]["emailbison"]["body"]["leads"]]
        self.assertFalse(any(e.endswith("@meridian.test") for e in emails))

    def test_the_builder_refuses_an_item_that_would_fail_lint(self):
        """Belt and braces: the payload builder re-checks, it does not trust."""
        rec = self.rec()
        contact = rec["contacts"][0]
        item = {"record": rec, "contact": contact, "contact_key": contact["key"],
                "step_key": "day1", "channel": "email",
                "step": {"channel": "email", "subject": "s",
                         "body": "too short", "day": 1},
                "push_id": "x"}
        with self.assertRaises(AssertionError):
            push.emailbison_rows([item])

    def test_the_builder_refuses_an_unverified_recipient(self):
        from src import verification
        rec = self.rec()
        contact = dict(rec["contacts"][0])
        evidence = [verification.result("contactout", verification.S_UNKNOWN,
                                        contact["email"])]
        verification.apply(contact, verification.decide(evidence), evidence)
        step = rec["cadence"][contact["key"]]["day1"]
        item = {"record": rec, "contact": contact, "contact_key": contact["key"],
                "step_key": "day1", "channel": "email", "step": step, "push_id": "x"}
        with self.assertRaises(AssertionError):
            push.emailbison_rows([item])

    def test_a_stored_sendable_flag_cannot_smuggle_an_unverified_address_through(self):
        """Sendability is recomputed from the evidence, never read off the record."""
        from src import verification
        rec = self.rec()
        contact = dict(rec["contacts"][0])
        evidence = [verification.result("contactout", verification.S_ACCEPT_ALL,
                                        contact["email"], catch_all=True)]
        verification.apply(contact, verification.decide(evidence), evidence)
        contact["sendable"] = True             # a lie planted on the record
        contact["verification"]["state"] = verification.VERIFIED
        step = rec["cadence"][contact["key"]]["day1"]
        item = {"record": rec, "contact": contact, "contact_key": contact["key"],
                "step_key": "day1", "channel": "email", "step": step, "push_id": "x"}
        with self.assertRaises(AssertionError):
            push.emailbison_rows([item])


class TestTheHeyReachPayload(PushTest):
    def test_the_payload_is_the_documented_shape(self):
        payload = self.run_push()["payloads"]["heyreach"]
        self.assertTrue(payload["endpoint"].endswith("AddLeadsToCampaignV2"))
        pair = payload["body"]["accountLeadPairs"][0]
        self.assertEqual(pair["linkedInAccountId"], 3)
        self.assertEqual(set(pair["lead"]), {"profileUrl", "firstName", "lastName",
                                             "companyName", "position",
                                             "customUserFields"})

    def test_a_contact_with_no_profile_url_is_never_included(self):
        recs = store.load()
        for rec in recs:
            if rec["id"] == "meridian":
                rec["contacts"][0]["linkedin"] = None
        store.save(recs)
        pairs = self.run_push()["payloads"]["heyreach"]["body"]["accountLeadPairs"]
        self.assertTrue(all(p["lead"]["profileUrl"] for p in pairs))

    def test_the_same_profile_is_never_added_twice_in_one_push(self):
        pairs = self.run_push()["payloads"]["heyreach"]["body"]["accountLeadPairs"]
        urls = [p["lead"]["profileUrl"] for p in pairs]
        self.assertEqual(len(urls), len(set(urls)))

    def test_the_note_travels_in_custom_user_fields(self):
        pair = self.run_push()["payloads"]["heyreach"]["body"]["accountLeadPairs"][0]
        field = pair["lead"]["customUserFields"][0]
        self.assertEqual(field["name"], "note")
        self.assertTrue(field["value"])

    def test_the_note_never_mentions_the_email(self):
        for pair in self.run_push()["payloads"]["heyreach"]["body"]["accountLeadPairs"]:
            note = pair["lead"]["customUserFields"][0]["value"].lower()
            for word in cadence.NOTE_MENTIONS_EMAIL:
                self.assertNotIn(word, note)


class TestIdempotency(PushTest):
    """A retry after a crash must not send the same logical step twice."""

    def push_ids(self, result):
        return sorted(item["push_id"] for item in result["ready"])

    def test_the_push_identity_is_stable_and_specific(self):
        first = self.push_ids(self.run_push())
        second = self.push_ids(self.run_push())
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(set(first)))
        self.assertIn("meridian:ivana-saric:day1:email", first)

    def test_a_marked_step_is_not_offered_again(self):
        result = self.run_push()
        item = next(i for i in result["ready"] if i["step_key"] == "day1")
        recs = store.load()
        rec = next(r for r in recs if r["id"] == item["record"]["id"])
        push.mark_pushed(rec, item["contact_key"], "day1", item["push_id"])
        store.save(recs)

        again = self.run_push()
        self.assertNotIn(item["push_id"], self.push_ids(again))
        self.assertTrue(any(s.get("why") == "already pushed" for s in again["skipped"]))

    def test_a_crash_after_the_payload_but_before_marking_resends_once_only(self):
        """The payload was built, the process died, the retry marks it once."""
        first = self.run_push()
        item = next(i for i in first["ready"] if i["step_key"] == "day1")

        # crash: nothing was marked. The retry sees it as still to do.
        retry = self.run_push()
        self.assertIn(item["push_id"], self.push_ids(retry))

        recs = store.load()
        rec = next(r for r in recs if r["id"] == item["record"]["id"])
        push.mark_pushed(rec, item["contact_key"], "day1", item["push_id"])
        store.save(recs)

        third = self.run_push()
        self.assertNotIn(item["push_id"], self.push_ids(third))

    def test_running_the_same_batch_twice_prepares_the_same_work_once_marked(self):
        first = self.run_push()
        recs = store.load()
        for item in first["ready"]:
            rec = next(r for r in recs if r["id"] == item["record"]["id"])
            push.mark_pushed(rec, item["contact_key"], item["step_key"], item["push_id"])
        store.save(recs)
        second = self.run_push()
        self.assertEqual(second["ready"], [])
        self.assertEqual(second["counts"]["email"], 0)
        self.assertEqual(second["counts"]["linkedin"], 0)

    def test_a_partially_pushed_batch_resumes_on_the_remainder(self):
        first = self.run_push()
        half = first["ready"][: len(first["ready"]) // 2]
        recs = store.load()
        for item in half:
            rec = next(r for r in recs if r["id"] == item["record"]["id"])
            push.mark_pushed(rec, item["contact_key"], item["step_key"], item["push_id"])
        store.save(recs)

        second = self.run_push()
        done = {i["push_id"] for i in half}
        remaining = set(self.push_ids(second))
        self.assertEqual(done & remaining, set())
        self.assertEqual(len(remaining), len(first["ready"]) - len(half))

    def test_the_pushed_state_survives_a_reload_from_disk(self):
        item = next(i for i in self.run_push()["ready"] if i["step_key"] == "day1")
        recs = store.load()
        rec = next(r for r in recs if r["id"] == item["record"]["id"])
        push.mark_pushed(rec, item["contact_key"], "day1", item["push_id"])
        store.save(recs)

        reloaded = store.get(item["record"]["id"])
        step = reloaded["cadence"][item["contact_key"]]["day1"]
        self.assertEqual(step["status"], "pushed")
        self.assertEqual(step["push_id"], item["push_id"])
        self.assertTrue(step["pushed_at"])

    def test_marking_goes_through_the_store_and_is_auditable(self):
        item = next(i for i in self.run_push()["ready"] if i["step_key"] == "day1")
        recs = store.load()
        rec = next(r for r in recs if r["id"] == item["record"]["id"])
        push.mark_pushed(rec, item["contact_key"], "day1", item["push_id"])
        store.save(recs)
        notes = [e["note"] for e in store.get(item["record"]["id"])["log"]
                 if e["step"] == "pushed"]
        self.assertIn(item["push_id"], notes)


class TestPauseStopsThePush(PushTest):
    def test_a_replied_company_prepares_nothing(self):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        cadence.record_event(rec, "email_reply", "ivana-saric")
        store.save(recs)

        result = self.run_push()
        self.assertFalse(any(i["record"]["id"] == "meridian" for i in result["ready"]))
        self.assertTrue(any("paused" in str(s["why"]) for s in result["skipped"]))

    def test_the_other_companies_still_prepare(self):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        cadence.record_event(rec, "email_reply", "ivana-saric")
        store.save(recs)
        result = self.run_push()
        self.assertTrue(any(i["record"]["id"] == "harbourline" for i in result["ready"]))

    def test_the_payload_builder_refuses_a_paused_company_even_if_handed_one(self):
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        cadence.record_event(rec, "email_reply", "ivana-saric")
        store.save(recs)
        contact = store.get("meridian")["contacts"][0]
        step = store.get("meridian")["cadence"][contact["key"]]["day1"]
        item = {"record": store.get("meridian"), "contact": contact,
                "contact_key": contact["key"], "step_key": "day1",
                "channel": "email", "step": step, "push_id": "x"}
        with self.assertRaises(AssertionError):
            push.emailbison_rows([item])


class TestScheduling(PushTest):
    def test_only_steps_whose_day_has_arrived_are_prepared(self):
        early = self.run_push(day=1)
        steps = {i["step_key"] for i in early["ready"]}
        self.assertEqual(steps, {"day1"})

    def test_a_later_day_includes_the_earlier_steps(self):
        self.assertLess(len(self.run_push(day=3)["ready"]),
                        len(self.run_push(day=21)["ready"]))

    def test_the_buyer_is_not_prepared_before_their_offset(self):
        ready = self.run_push(day=1)["ready"]
        self.assertFalse(any(i["contact_key"] == "damir-vukovic" for i in ready))
        later = self.run_push(day=6)["ready"]
        self.assertTrue(any(i["contact_key"] == "damir-vukovic" for i in later))


if __name__ == "__main__":
    unittest.main()


class TestOurIdentifiersTravelWithTheLead(PushTest):
    """`adapters` reads `record_id`, `contact_key` and `client` back off an
    inbound reply on both providers. Until this was fixed, `push` sent none of
    them on either, so those three branches could never fire and every reply
    fell through to a weaker key: a URL on LinkedIn, and on email a record with
    no idea which of its contacts had answered.

    Sending them does not make HeyReach round-trip them - confirmed live on
    2026-08-26, it returns `customFields: []` - so the canonical profile URL
    stays the correlation key there. EmailBison's custom variables are the
    mechanism the client's own cadence already relies on.
    """

    def bison_leads(self):
        return self.run_push()["payloads"]["emailbison"]["body"]["leads"]

    def heyreach_fields(self, pair):
        return {f["name"]: f["value"] for f in pair["lead"]["customUserFields"]}

    def test_emailbison_carries_all_three(self):
        for lead in self.bison_leads():
            variables = lead["custom_variables"]
            self.assertTrue(variables.get("record_id"))
            self.assertTrue(variables.get("contact_key"))
            self.assertTrue(variables.get("client"))

    def test_heyreach_carries_all_three(self):
        pairs = self.run_push()["payloads"]["heyreach"]["body"]["accountLeadPairs"]
        for pair in pairs:
            fields = self.heyreach_fields(pair)
            self.assertTrue(fields.get("record_id"))
            self.assertTrue(fields.get("contact_key"))
            self.assertTrue(fields.get("client"))

    def test_the_emailbison_identifiers_round_trip_through_the_adapter(self):
        """The branch that could never fire before."""
        from src import adapters
        lead = self.bison_leads()[0]
        events_ = adapters.from_emailbison({"data": [{
            "id": "evt-1",
            "type": "Reply",
            "folder": "Inbox",
            "custom_variables": lead["custom_variables"],
            "from_email": lead["email"],
            "body": "sounds useful, send it over",
        }]})
        self.assertTrue(events_)
        event = events_[0]
        self.assertEqual(event["record_id"],
                         lead["custom_variables"]["record_id"])
        self.assertEqual(event["contact_key"],
                         lead["custom_variables"]["contact_key"])

    def test_the_heyreach_identifiers_round_trip_through_the_adapter(self):
        from src import adapters
        pairs = self.run_push()["payloads"]["heyreach"]["body"]["accountLeadPairs"]
        fields = self.heyreach_fields(pairs[0])
        events_ = adapters.from_heyreach({"items": [{
            "id": "thread-1",
            "lastMessageSender": "CORRESPONDENT",
            "customUserFields": [{"name": k, "value": v}
                                 for k, v in fields.items()],
            "profileUrl": pairs[0]["lead"]["profileUrl"],
            "messages": [{"sender": "CORRESPONDENT", "body": "sure",
                          "createdAt": "2026-08-26T10:00:00Z"}],
        }]})
        self.assertTrue(events_)
        self.assertEqual(events_[0]["record_id"], fields["record_id"])
        self.assertEqual(events_[0]["contact_key"], fields["contact_key"])

    def test_the_note_is_still_the_first_custom_field(self):
        """The push CLI prints `customUserFields[0]`."""
        pairs = self.run_push()["payloads"]["heyreach"]["body"]["accountLeadPairs"]
        for pair in pairs:
            self.assertEqual(pair["lead"]["customUserFields"][0]["name"], "note")

    def test_the_identifiers_match_a_real_record_and_contact(self):
        recs = {r["id"]: r for r in store.load()}
        for lead in self.bison_leads():
            variables = lead["custom_variables"]
            rec = recs[variables["record_id"]]
            keys = {c.get("key") for c in rec.get("contacts") or []}
            self.assertIn(variables["contact_key"], keys)
