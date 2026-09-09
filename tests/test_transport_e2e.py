"""One fictional scenario across every transport, in order, with no network.

    campaign approved -> launch ready -> a real-shaped EmailBison reply
    -> company paused -> classified positive -> Slack alerted
    -> the same provider event again, ignored
    -> a forged Slack approval on a second campaign, refused
    -> a properly signed one, accepted

Written as one test on purpose: the ordering between these steps is the thing
being checked, and splitting it into eight would let each pass while the
sequence stayed broken.
"""
import json
import time
import unittest
import urllib.parse

from src import (adapters, cadence, campaigns, events, inbound, interactions,
                 observability, orchestrator, poller, replies, store)
from src.providers import slack
from tests.campaignbase import CampaignTest, contact
from tests.test_interactions import SECRET, payload_body

# Which EmailBison workspace this fixture is pretending to read.
# `poller.run` asks the provider rather than trusting the caller, so a
# test has to supply the answer the way it supplies `fetch`. A live run
# passes neither and gets `GET /api/users`.
WORKSPACE = {"id": 10, "name": "PRODUCTIVE"}

ADMIN = "U0DEMOADMIN1"

# The shape EmailBison really returns, values replaced.
def reply_page(uuid="e2e-0000-0001", text="This is interesting, happy to chat.",
               record_id="acme", contact_key="acme-champ"):
    return {"data": [
        {"id": 1700001, "uuid": uuid, "type": "Untracked Reply",
         "folder": "Inbox", "from_email_address": "champ@acme.test",
         "date_received": "2026-08-26T10:00:00Z", "text_body": text,
         "automated_reply": False,
         "custom_variables": {"record_id": record_id,
                              "contact_key": contact_key, "client": "demo"}},
        # Our own mail, in the same page. Must never become a reply.
        {"id": 1700000, "uuid": "e2e-0000-0002", "type": "Outgoing Email",
         "folder": "Sent", "from_email_address": "sender@demo.test",
         "date_received": "2026-08-26T09:00:00Z",
         "text_body": "Hi, quick question about your delivery teams."},
    ], "meta": {"next_cursor": None}}


class TestTheWholeTransportPath(CampaignTest):
    def setUp(self):
        super().setUp()
        import os
        os.environ["CHECKPOINTS"] = self.tmp + "/work/checkpoints.json"
        interactions.reset_seen()
        observability.reset()
        self.posted = []
        self.now = int(time.time())

    def post(self, payload, config=None):
        self.posted.append(payload)
        return {"ok": True, "ts": f"1712.{len(self.posted)}"}

    def test_the_whole_path(self):
        # --- 1. an approved, launch-ready campaign -------------------------
        campaign, recs, _ = self.approved_campaign("camp-live")
        recs = store.load()
        readiness = orchestrator.launch_readiness(campaign, recs, self.config)
        self.assertTrue(readiness["ok"], readiness["blockers"])
        self.assertEqual(campaign["status"], campaigns.LAUNCH_READY)
        self.save_campaign(campaign)

        # --- 2. a reply arrives through the poller -------------------------
        pages = [reply_page()]
        served = []

        def fetch(cursor=None, per_page=None):
            served.append(cursor)
            return pages[0]["data"], None

        result = poller.run("emailbison", live=True, identify=lambda: WORKSPACE, fetch=fetch, recs=recs,
                            config=self.config, post=self.post,
                            sleep=lambda s: None)
        self.assertEqual(result["applied"], 1, "one reply, not two")

        # --- 3. the company is paused, on both channels --------------------
        acme = next(r for r in recs if r["id"] == "acme")
        self.assertTrue(acme["paused"])
        timeline = cadence.build(acme, self.config, recs=recs)
        self.assertTrue(timeline["paused"])
        for steps in timeline["contacts"].values():
            for step in steps.values():
                self.assertNotEqual(step["status"], "eligible")

        # --- 4. and our own outgoing mail did not pause anyone --------------
        borealis = next(r for r in recs if r["id"] == "borealis")
        self.assertFalse(borealis.get("paused"),
                         "an Outgoing Email row must never pause a company")

        # --- 5. classified positive, and one alert raised ------------------
        classified = [e for e in acme["events"]
                      if e["type"] == events.REPLY_CLASSIFIED]
        self.assertEqual(len(classified), 1)
        self.assertEqual(classified[0]["classification"], replies.POSITIVE)
        alerts = [p for p in self.posted if p["kind"] == slack.POSITIVE_REPLY]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["channel"], "C0DEMOPOSITI")

        # --- 6. the same provider event again changes nothing ---------------
        before = len(acme["events"])
        poller.run("emailbison", live=True, identify=lambda: WORKSPACE, fetch=fetch, recs=recs,
                   config=self.config, post=self.post, sleep=lambda s: None)
        self.assertEqual(len(acme["events"]), before, "a duplicate must be inert")
        self.assertEqual(len([p for p in self.posted
                              if p["kind"] == slack.POSITIVE_REPLY]), 1)
        store.save(recs)

        # --- 7. a second campaign, and a forged approval on it -------------
        second = orchestrator.create("camp-two", "demo", "Second campaign",
                                     record_ids=["borealis"], created_by=ADMIN)
        second["senders"] = {"email": [{"id": "bison-1", "daily_limit": 10}],
                             "linkedin": [{"id": "hr-1", "daily_limit": 5}]}
        second["daily_volume"] = {"email": 5, "linkedin": 3}
        second["bison_campaign_id"] = "8100"
        second["heyreach_campaign_id"] = "6100"
        orchestrator.prepare(second, recs, self.config)
        request = orchestrator.request_approval(second, recs, self.config)
        self.save_campaign(second)
        fingerprint = request["summary"]["fingerprint"]

        body = payload_body("camp-two", fingerprint)
        with self.assertRaises(interactions.Rejected):
            interactions.handle(body, self.now, "v0=" + "f" * 64, secret=SECRET,
                                now=self.now, config=self.config, recs=recs)
        self.assertIsNone(campaigns.require("camp-two")["approval"],
                          "a forged payload must not approve anything")

        # --- 8. and a properly signed one is accepted ----------------------
        signature = slack.sign(body, self.now, SECRET)
        accepted = interactions.handle(body, self.now, signature, secret=SECRET,
                                       now=self.now, config=self.config,
                                       recs=recs)
        self.assertEqual(accepted["status"], "approved")
        self.assertEqual(campaigns.require("camp-two")["status"],
                         campaigns.APPROVED)

        # --- 9. the paused campaign still cannot launch --------------------
        blocked = campaigns.validate("camp-live", store.load(), self.config,
                                     campaign=campaigns.require("camp-live"))
        self.assertFalse(blocked["ok"])
        self.assertIn("no paused companies", blocked["blockers"])

        # --- 10. and nothing anywhere could send ---------------------------
        from src import push
        with self.assertRaises(push.LiveSendNotEnabled):
            orchestrator.launch(campaigns.require("camp-two"),
                                recs=store.load(), config=self.config, live=True)
        self.assertEqual(self.cassette.calls, [])

    def test_the_run_touched_no_network(self):
        self.test_the_whole_path()
        self.assertEqual(self.cassette.calls, [])

    def test_no_reply_body_was_persisted(self):
        self.test_the_whole_path()
        blob = json.dumps(store.load())
        self.assertNotIn("happy to chat", blob)
        self.assertNotIn("quick question about your delivery teams", blob)

    def test_the_counters_tell_the_story(self):
        self.test_the_whole_path()
        counts = observability.counts()
        self.assertGreaterEqual(counts.get(events.EVENT_INGESTED, 0), 1)
        self.assertGreaterEqual(counts.get(events.EVENT_DUPLICATE, 0), 1)
        self.assertGreaterEqual(counts.get(events.WEBHOOK_REJECTED, 0), 1)
        self.assertGreaterEqual(counts.get(events.SLACK_POST_SENT, 0), 1)


if __name__ == "__main__":
    unittest.main()
