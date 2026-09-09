"""One fictional campaign, all the way through, with nothing mocked but the wire.

Five invented companies on .test domains, two channels, two senders, and one of
each thing that is supposed to go wrong: a held contact, a dropped record, a
draft that fails lint, a positive email reply and a positive LinkedIn reply. The
test walks the whole path and asserts at each stage - not just that it finished,
but that the failures stayed failures and the pause reached everyone it should.

The last two assertions are the ones worth having: a company that replied is
paused on both channels, and a company that did not is still running.
"""
import json
import unittest

from src import (approve, cadence, campaigns, events, inbound, lint,
                 orchestrator, push, replies, report, store)
from src.providers import slack
from tests.campaignbase import CampaignTest, contact

ADMIN = "U0DEMOADMIN1"

# Five fictional companies. The last two are the ones designed to misbehave.
COMPANIES = (
    ("northwind", "Northwind Studio", "northwind.test"),
    ("belmont", "Belmont Partners", "belmont.test"),
    ("caldera", "Caldera Group", "caldera.test"),
    ("driftwood", "Driftwood Agency", "driftwood.test"),
    ("evergreen", "Evergreen Works", "evergreen.test"),
)


class TestTheWholeCampaign(CampaignTest):
    maxDiff = None

    def setUp(self):
        super().setUp()
        self.posted = []
        self.recs = self.build_batch()
        self.campaign = None

    def post(self, payload, config=None):
        """A workspace that accepts everything, so the flow can be observed."""
        self.posted.append(payload)
        return {"ok": True, "ts": f"171000.{len(self.posted)}"}

    # ------------------------------------------------------- 1. the batch

    def build_batch(self):
        recs = self.seed_records(COMPANIES)

        # A second contact at Northwind, on the buyer track.
        recs[0]["contacts"].append(
            contact("northwind-buyer", "Buyer Northwind", "buyer@northwind.test",
                    persona="economic_buyer", angle="founder",
                    title="Managing Director"))

        # Caldera's contact never cleared verification: held, not sendable.
        # Built that way rather than de-verified - `contact(sendable=False)`
        # produces a real one-confirmation catch-all, and wiping the evidence
        # off a verified contact is the loss `store.save` now refuses.
        self.reset_estate()
        recs[2]["contacts"][0] = contact(
            "caldera-champ", "Champ Caldera", "champ@caldera.test",
            sendable=False)
        recs[2]["state"] = "held"

        # Driftwood was dropped before the campaign was built.
        recs[3]["state"] = "dropped"
        recs[3]["drop_reason"] = "out of geo: flagged and dropped by a human"

        self.draft_everything(recs)

        # Evergreen's draft is broken: an unexpanded placeholder.
        for steps in recs[4]["cadence"].values():
            for step in steps.values():
                if step.get("generated"):
                    step["body"] = ("Hi {{first_name}}, quick one about "
                                    "{{company}} and how you run delivery.\n")
        store.save(recs)
        return store.load()

    # ------------------------------------------------------- the walk

    def test_the_campaign_runs_end_to_end(self):
        recs = self.recs

        # --- 2. lint sorts the good drafts from the broken one -------------
        broken = [r["id"] for r in recs
                  if any(lint.check(r, ck, s)
                         for ck, steps in cadence.build(r, self.config,
                                                        recs=recs)["contacts"].items()
                         for s in steps.values() if s.get("channel") == "email")]
        self.assertIn("evergreen", broken, "the placeholder draft must fail lint")
        self.assertNotIn("northwind", broken)

        # --- 3. draft approval, which refuses what lint refused ------------
        self.approve_drafts(recs)
        store.save(recs)
        recs = store.load()
        evergreen = next(r for r in recs if r["id"] == "evergreen")
        for steps in (evergreen.get("cadence") or {}).values():
            for step in steps.values():
                if step.get("generated"):
                    self.assertIsNone(step.get("approval"),
                                      "a draft that fails lint cannot be approved")

        # --- 4. the campaign, over the healthy records only ----------------
        healthy = [r["id"] for r in recs if r["id"] in ("northwind", "belmont")]
        campaign = orchestrator.create("demo-q3", "demo", "Demo Q3",
                                       record_ids=healthy, created_by=ADMIN)
        campaign["senders"] = {
            "email": [{"id": "bison-a", "daily_limit": 25},
                      {"id": "bison-b", "daily_limit": 25}],
            "linkedin": [{"id": "hr-a", "daily_limit": 15},
                         {"id": "hr-b", "daily_limit": 15}],
        }
        campaign["daily_volume"] = {"email": 20, "linkedin": 10}
        orchestrator.map_external(campaign, bison_campaign_id="8100",
                                  heyreach_campaign_id="6100", by=ADMIN)
        self.campaign = campaign

        summary = orchestrator.prepare(campaign, recs, self.config)
        self.assertEqual(campaign["status"], campaigns.READY_FOR_REVIEW)
        self.assertEqual(summary["domains"], 2)
        self.assertEqual(summary["contacts"], 3)      # two at northwind

        # --- 5. approval is requested and posted to Slack ------------------
        request = orchestrator.request_approval(campaign, recs, self.config)
        self.assertEqual(campaign["status"], campaigns.AWAITING_APPROVAL)
        self.assertTrue(request["notification"]["planned"])
        self.assertEqual(request["payload"]["channel"], "C0DEMOAPPROV")

        # --- 6. an outsider cannot approve; the configured admin can -------
        with self.assertRaises(slack.NotPermitted):
            orchestrator.decide(campaign, "U0IMPOSTOR", "approve",
                                fingerprint=request["summary"]["fingerprint"],
                                interaction_id="x-1", config=self.config,
                                recs=recs)
        decision = orchestrator.decide(
            campaign, ADMIN, "approve",
            fingerprint=request["summary"]["fingerprint"],
            interaction_id="ok-1", config=self.config, recs=recs)
        self.assertEqual(decision["status"], "approved")

        # --- 7. launch readiness, then the door that stays shut ------------
        readiness = orchestrator.launch_readiness(campaign, recs, self.config)
        self.assertTrue(readiness["ok"], readiness["blockers"])
        self.assertEqual(campaign["status"], campaigns.LAUNCH_READY)
        with self.assertRaises(push.LiveSendNotEnabled):
            orchestrator.launch(campaign, recs=recs, config=self.config, live=True)

        # --- 8. the dry run and its payloads -------------------------------
        plan = campaigns.dry_run("demo-q3", day=21, recs=recs,
                                 config=self.config, campaign=campaign)
        self.assertEqual(sorted(plan["channels"]), ["email", "linkedin"])
        self.assertGreater(plan["payload_count"], 0)
        self.assertIn("8100", plan["payloads"]["emailbison"]["endpoint"])
        self.assertEqual(plan["payloads"]["heyreach"]["body"]["campaignId"], "6100")
        self.assertEqual(self.cassette.calls, [], "the dry run called nothing")

        # --- 9. a positive email reply from Northwind ----------------------
        email_reply = {"events": [{
            "event": "replied", "id": "bison-evt-1",
            "email": "champ@northwind.test",
            "timestamp": "2026-08-26T10:00:00+00:00",
            "text": "This is interesting - happy to chat next week, what does "
                    "it cost?",
            "custom_variables": {"record_id": "northwind",
                                 "contact_key": "northwind-champ",
                                 "client": "demo"}}]}
        outcomes = inbound.ingest(email_reply, "emailbison", recs=recs,
                                  config=self.config, post=self.post)
        self.assertEqual(outcomes[0]["classification"]["classification"],
                         replies.POSITIVE)

        # --- 10. a positive LinkedIn reply from Belmont --------------------
        linkedin_reply = {"events": [{
            "eventType": "message_reply", "id": "hr-evt-1",
            "profileUrl": "https://www.linkedin.com/in/belmont-champ",
            "timestamp": "2026-08-26T11:00:00+00:00",
            "text": "keen to hear more, send me some times",
            "customUserFields": [{"name": "record_id", "value": "belmont"},
                                 {"name": "contact_key", "value": "belmont-champ"},
                                 {"name": "client", "value": "demo"}]}]}
        outcomes = inbound.ingest(linkedin_reply, "heyreach", recs=recs,
                                  config=self.config, post=self.post)
        self.assertEqual(outcomes[0]["classification"]["classification"],
                         replies.POSITIVE)

        # --- 11. both companies paused, on both channels -------------------
        northwind = next(r for r in recs if r["id"] == "northwind")
        belmont = next(r for r in recs if r["id"] == "belmont")
        for rec in (northwind, belmont):
            self.assertTrue(rec["paused"], rec["id"])
            timeline = cadence.build(rec, self.config, recs=recs)
            self.assertTrue(timeline["paused"])
            for steps in timeline["contacts"].values():
                for step in steps.values():
                    self.assertNotEqual(step["status"], "eligible")

        # The email reply pauses Northwind's *buyer* too, who never replied.
        buyer_steps = cadence.build(northwind, self.config,
                                    recs=recs)["contacts"]["northwind-buyer"]
        for step in buyer_steps.values():
            self.assertNotEqual(step["status"], "eligible")

        # --- 12. an unrelated company carries on ---------------------------
        caldera = next(r for r in recs if r["id"] == "caldera")
        self.assertFalse(caldera.get("paused"))

        # --- 13. two Slack alerts, one per positive reply ------------------
        positives = [p for p in self.posted if p["kind"] == slack.POSITIVE_REPLY]
        self.assertEqual(len(positives), 2)
        self.assertEqual({p["channel"] for p in positives}, {"C0DEMOPOSITI"})
        sources = {p["metadata"]["source"] for p in positives}
        self.assertEqual(sources, {"emailbison", "heyreach"})

        # --- 14. the campaign can no longer launch -------------------------
        store.save(recs)
        blocked = campaigns.validate("demo-q3", store.load(), self.config,
                                     campaign=campaign)
        self.assertFalse(blocked["ok"])
        self.assertIn("no paused companies", blocked["blockers"])

        # --- 15. reporting sees the whole thing ----------------------------
        rows = report.rows(store.load())
        self.assertTrue({row["record_id"] for row in rows}
                        >= {"northwind", "belmont"})
        kinds = [e["type"] for r in store.load() for e in r.get("events") or []]
        for expected in (events.REPLY_RECEIVED, events.REPLY_CLASSIFIED,
                         events.POSITIVE_REPLY_DETECTED, events.COMPANY_PAUSED,
                         events.SLACK_NOTIFICATION_PLANNED,
                         events.SLACK_NOTIFICATION_SENT):
            self.assertIn(expected, kinds, expected)

        campaign_kinds = [e["type"] for e in campaign["events"]]
        for expected in (events.CAMPAIGN_CREATED, events.CAMPAIGN_READY_FOR_REVIEW,
                         events.CAMPAIGN_APPROVAL_REQUESTED,
                         events.CAMPAIGN_APPROVED, events.CAMPAIGN_LAUNCH_READY,
                         events.EXTERNAL_CAMPAIGN_MAPPED):
            self.assertIn(expected, campaign_kinds, expected)

    def test_nothing_in_the_whole_run_touched_a_network(self):
        self.test_the_campaign_runs_end_to_end()
        self.assertEqual(self.cassette.calls, [])

    def test_no_reply_body_reached_the_queue(self):
        self.test_the_campaign_runs_end_to_end()
        blob = json.dumps(store.load())
        self.assertNotIn("what does it cost", blob)
        self.assertNotIn("send me some times", blob)

    def test_the_held_and_dropped_records_never_became_payloads(self):
        self.test_the_campaign_runs_end_to_end()
        plan = campaigns.dry_run("demo-q3", day=21, recs=store.load(),
                                 config=self.config, campaign=self.campaign)
        blob = json.dumps(plan["payloads"])
        for excluded in ("caldera.test", "driftwood.test", "evergreen.test"):
            self.assertNotIn(excluded, blob, excluded)


if __name__ == "__main__":
    unittest.main()
