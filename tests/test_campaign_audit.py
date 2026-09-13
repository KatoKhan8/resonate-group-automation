"""The audit for the campaign and Slack layer.

Every test here is a property that must hold no matter what any caller does.
They overlap with tests elsewhere on purpose: the ones elsewhere check that a
feature works, and these check that the safety cannot be got around, including
by a future change made by someone who has not read the other file.
"""
import ast
import json
import os
import re
import unittest

from src import (campaigns, events, inbound, orchestrator, replies, roles,
                 senders, store)
from src.providers import slack
from tests.campaignbase import CampaignTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN = "U0DEMOADMIN1"


def source_files():
    for root, _, files in os.walk(os.path.join(ROOT, "src")):
        for name in sorted(files):
            if name.endswith(".py"):
                yield os.path.join(root, name)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestNothingLaunchesWithoutApproval(CampaignTest):
    def test_a_campaign_with_no_approval_cannot_launch(self):
        campaign, recs = self.ready_campaign()
        with self.assertRaises(orchestrator.NotReady):
            orchestrator.launch(campaign, recs=recs, config=self.config)

    def test_a_hand_written_approval_block_does_not_count(self):
        campaign, recs = self.ready_campaign()
        campaign["approval"] = {"action": "approve", "by": "whoever",
                                "fingerprint": "whatever"}
        campaign["status"] = campaigns.APPROVED
        with self.assertRaises(orchestrator.NotReady):
            orchestrator.launch(campaign, recs=recs, config=self.config)

    def test_a_stale_approval_cannot_launch(self):
        campaign, recs, _ = self.approved_campaign()
        orchestrator.set_daily_volume(campaign, email=77)
        with self.assertRaises(orchestrator.NotReady):
            orchestrator.launch(campaign, recs=store.load(), config=self.config)

    def test_the_approval_check_is_one_of_many_not_the_only_one(self):
        names = [label for label, _ in campaigns.CHECKS]
        self.assertIn("campaign approved", names)
        self.assertGreaterEqual(len(names), 14)

    def test_only_the_orchestrator_writes_a_campaign_approval(self):
        """Draft approval is a different thing with a different writer.

        src/approve.py writes `step["approval"]` - whether these words are
        blessed. Only the orchestrator writes `campaign["approval"]` - whether
        this whole run may go. Both are needed; neither substitutes.
        """
        offenders = []
        for path in source_files():
            if os.path.basename(path) == "orchestrator.py":
                continue
            if re.search(r'campaign\["approval"\]\s*=', read(path)):
                offenders.append(os.path.relpath(path, ROOT))
        self.assertEqual(offenders, [])

    def test_only_campaigns_writes_a_campaign_status(self):
        """Records and steps have their own `status`; this is the campaign's."""
        offenders = []
        for path in source_files():
            if os.path.basename(path) == "campaigns.py":
                continue
            if re.search(r'campaign\["status"\]\s*=', read(path)):
                offenders.append(os.path.relpath(path, ROOT))
        self.assertEqual(offenders, [])


class TestSlackCannotOverrideSafety(CampaignTest):
    def test_slack_never_writes_sendable(self):
        self.assertIsNone(re.search(r'\["sendable"\]\s*=', read(
            os.path.join(ROOT, "src", "providers", "slack.py"))))

    def test_slack_never_writes_a_record_state(self):
        source = read(os.path.join(ROOT, "src", "providers", "slack.py"))
        self.assertIsNone(re.search(r'\["state"\]\s*=', source))
        self.assertIsNone(re.search(r'\["paused"\]\s*=', source))

    def test_an_approval_cannot_clear_an_unverified_recipient(self):
        campaign, recs, _ = self.approved_campaign()
        recs = store.load()
        recs[0]["contacts"][0]["verification"] = {"state": "unknown"}
        # Planting a degraded state deliberately. `store.save` refuses a
        # write that drops paid evidence, so this replaces the estate
        # rather than updating it - the contact is being constructed
        # unverified, not un-verified after the fact.
        store.save([])
        store.save(recs)
        result = campaigns.validate("camp-1", store.load(), self.config,
                                    campaign=campaign)
        self.assertIn("recipients sendable", result["blockers"])

    def test_an_approval_cannot_clear_a_company_pause(self):
        campaign, recs, _ = self.approved_campaign()
        recs = store.load()
        recs[0]["paused"] = {"since": "x", "reason": "reply_received"}
        store.save(recs)
        result = campaigns.validate("camp-1", store.load(), self.config,
                                    campaign=campaign)
        self.assertIn("no paused companies", result["blockers"])

    def test_the_permission_check_cannot_be_satisfied_by_an_empty_config(self):
        for config in ({}, {"slack": {}}, {"slack": {"enabled": True}}):
            self.assertFalse(slack.may_approve(config, ADMIN), config)


class TestNoClassificationResumesAnything(CampaignTest):
    def test_no_module_clears_a_pause(self):
        offenders = []
        for path in source_files():
            source = read(path)
            for pattern in (r'\["paused"\]\s*=\s*None',
                            r'\.pop\(\s*["\']paused["\']'):
                if re.search(pattern, source):
                    offenders.append(os.path.relpath(path, ROOT))
        self.assertEqual(offenders, [], "a company pause is never lifted in code")

    def test_the_classifier_cannot_reach_the_pause(self):
        source = read(os.path.join(ROOT, "src", "replies.py"))
        self.assertNotIn('rec["paused"]', source.replace('rec.get("paused")', ""))

    def test_every_classification_leaves_the_pause_in_place(self):
        for text in ("Not interested.", "Out of office.", "Wrong person.",
                     "unsubscribe", "Sounds great, let's talk."):
            recs = self.seed_records()
            event = inbound.manual("acme", "acme-champ", text, client="demo")
            inbound.handle(event, recs, config=self.config,
                           post=lambda p, c=None: {"ok": True})
            self.assertTrue(recs[0].get("paused"), text)

    def test_a_slack_failure_leaves_the_pause_in_place(self):
        recs = self.seed_records()

        def broken(payload, config=None):
            raise RuntimeError("down")

        event = inbound.manual("acme", "acme-champ", "Interested!", client="demo")
        inbound.handle(event, recs, config=self.config, post=broken)
        self.assertTrue(recs[0]["paused"])


class TestNoDirectProviderMutation(CampaignTest):
    def test_no_module_reaches_a_route_that_starts_sending(self):
        """A lead may now be staged. Nothing may be STARTED.

        This used to forbid posting to `/leads` at all, which was the right
        guarantee while EmailBison had no proven write verbs. It has them
        now - a lead is created and attached to a campaign that is left
        `paused` - so the guarantee moved to the routes that actually begin a
        send. `heyreach`'s AddLeadsToCampaignV2 adds a lead to a RUNNING
        campaign, which is why it stays here while `bison`'s staging does not.
        """
        starting = ("AddLeadsToCampaignV2", "/resume", "/StartCampaign",
                    "send-test")
        for path in source_files():
            for line in read(path).splitlines():
                if "request(" not in line:
                    continue
                for route in starting:
                    self.assertNotIn(route, line, f"{path}: {line.strip()}")

    def test_live_push_is_still_refused(self):
        from src import push
        with self.assertRaises(push.LiveSendNotEnabled):
            push.run(live=True)

    def test_a_ready_campaign_still_cannot_send(self):
        from src import push
        campaign, recs, _ = self.approved_campaign()
        with self.assertRaises(push.LiveSendNotEnabled):
            orchestrator.launch(campaign, recs=store.load(), config=self.config,
                                live=True)

    def test_slack_posting_is_refused(self):
        with self.assertRaises(slack.SlackPostingNotEnabled):
            slack.post({"channel": "C1"}, self.config)

    def test_both_senders_can_now_read_events_but_still_not_send(self):
        """The retrieval contract was confirmed live on 2026-08-26. Reading is
        what became possible; sending did not."""
        from src.providers import bison, heyreach
        for module in (bison, heyreach):
            self.assertTrue(module.EVENTS_CONTRACT_CONFIRMED)
            contract = module.events_contract()
            self.assertIn("confirmed live", contract["polling"])
            self.assertIn("hazard", contract)
        # Reading is confirmed. The send route still is not reachable.
        with self.assertRaises(Exception):
            heyreach._read("/campaign/AddLeadsToCampaignV2", {})
        # EmailBison posts now, and every route it may post to is declared.
        # The one that starts a campaign is not among them, which is the
        # property this assertion used to get from banning POST outright.
        # One route can start a send and it is named; nothing gated reaches
        # it. See `test_providers` for the full statement.
        starting = [r for r in bison.WRITE_ROUTES
                    if "resume" in r or "activate" in r]
        self.assertEqual(starting, ["/campaigns/{campaign_id}/resume"])
        from src import providerwrites
        self.assertFalse(
            providerwrites.is_supported(providerwrites.EMAIL_ACTIVATE))

    def test_a_campaign_created_on_a_provider_cannot_send(self):
        """Creating one is allowed now. Starting one is still not.

        `bison.create_campaign` returns a DRAFT, `bisonfactory` leaves it
        `paused`, and the provider refuses to resume a campaign without a
        sequence, a schedule, senders and leads - in its own words. The thing
        that keeps it harmless is that no supported operation can start it.
        """
        from src import providerwrites
        self.assertFalse(providerwrites.is_supported(providerwrites.EMAIL_ACTIVATE))
        self.assertFalse(
            providerwrites.is_supported(providerwrites.LINKEDIN_ACTIVATE))
        for operation, (_channel, facing, _why) in                 providerwrites.OPERATIONS.items():
            if facing:
                self.assertFalse(providerwrites.is_supported(operation),
                                 operation)


class TestStateIsResumable(CampaignTest):
    def test_a_campaign_reloads_with_its_approval_intact(self):
        campaign, recs, _ = self.approved_campaign()
        self.save_campaign(campaign)
        again = campaigns.require("camp-1")
        self.assertTrue(campaigns.is_approved(again, store.load(), self.config))

    def test_the_fingerprint_survives_a_reload(self):
        campaign, recs, _ = self.approved_campaign()
        self.save_campaign(campaign)
        before = campaigns.fingerprint(campaign, store.load(), self.config)
        after = campaigns.fingerprint(campaigns.require("camp-1"), store.load(),
                                      self.config)
        self.assertEqual(before, after)

    def test_an_applied_event_is_not_applied_twice_after_a_reload(self):
        recs = self.seed_records()
        payload = {"events": [{"event": "replied", "id": "dup-1",
                               "email": "champ@acme.test", "text": "Interested",
                               "custom_variables": {"record_id": "acme",
                                                    "contact_key": "acme-champ"}}]}
        inbound.ingest(payload, "emailbison", config=self.config,
                       post=lambda p, c=None: {"ok": True})
        inbound.ingest(payload, "emailbison", config=self.config,
                       post=lambda p, c=None: {"ok": True})
        rec = store.get("acme")
        replies_seen = [e for e in rec["events"]
                        if e["type"] == events.REPLY_RECEIVED]
        self.assertEqual(len(replies_seen), 1)

    def test_the_campaign_file_is_gitignored(self):
        import subprocess
        result = subprocess.run(["git", "check-ignore", "-v",
                                 "work/campaigns.jsonl"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class TestNoSecretsOrRealPeople(CampaignTest):
    def setUp(self):
        super().setUp()
        self.campaign, _, _ = self.approved_campaign()

    def test_the_demo_client_uses_only_test_domains(self):
        text = read(os.path.join(ROOT, "config", "clients", "demo.yaml"))
        for match in re.finditer(r"[\w.-]+@([\w.-]+)", text):
            self.assertTrue(match.group(1).endswith(".test"), match.group(0))

    def test_the_demo_slack_ids_are_obvious_placeholders(self):
        text = read(os.path.join(ROOT, "config", "clients", "demo.yaml"))
        for match in re.finditer(r"\b([CU]0[A-Z0-9]+)\b", text):
            self.assertIn("DEMO", match.group(1))

    def test_no_credential_value_reaches_a_campaign_or_a_report(self):
        """The launch checklist has to *ask* whether a key is configured, so
        naming the variable is fine. Storing the value is not."""
        import os as _os
        from src import campaigns as _campaigns, clients as _clients, store as _store
        sentinel = "sk-synthetic-audit-do-not-use-000111222"
        saved = {}
        for var in ("BISON_KEY", "BISON_BASE", "HEYREACH_KEY", "APIFY_TOKEN",
                    "CONTACTOUT_TOKEN"):
            saved[var] = _os.environ.get(var)
            _os.environ[var] = sentinel
        try:
            result = _campaigns.validate("camp-1", _store.load(),
                                         _clients.load("demo"),
                                         campaign=self.campaign)
        finally:
            for var, value in saved.items():
                if value is None:
                    _os.environ.pop(var, None)
                else:
                    _os.environ[var] = value
        self.assertNotIn(sentinel, json.dumps(result))
        self.assertNotIn(sentinel, json.dumps(self.campaign))

    def test_the_slack_module_holds_no_channel_or_user_id(self):
        source = read(os.path.join(ROOT, "src", "providers", "slack.py"))
        self.assertIsNone(re.search(r'["\']C[0-9A-Z]{8,}["\']', source),
                          "a channel id is hardcoded")
        self.assertIsNone(re.search(r'["\']U[0-9A-Z]{8,}["\']', source),
                          "a user id is hardcoded")

    def test_no_test_fixture_carries_a_real_looking_slack_token(self):
        for root, _, files in os.walk(os.path.join(ROOT, "tests")):
            for name in files:
                if not name.endswith((".py", ".json")):
                    continue
                text = read(os.path.join(root, name))
                self.assertIsNone(re.search(r"xox[baprs]-[A-Za-z0-9-]{10,}", text),
                                  name)


class TestTheNewModulesRespectTheOldRules(CampaignTest):
    def test_no_new_module_writes_sendable(self):
        for name in ("campaigns.py", "orchestrator.py", "replies.py",
                     "senders.py", "inbound.py", "roles.py"):
            source = read(os.path.join(ROOT, "src", name))
            self.assertIsNone(re.search(r'\["sendable"\]\s*=', source), name)

    def test_no_new_module_deletes_a_record(self):
        for name in ("campaigns.py", "orchestrator.py", "inbound.py"):
            source = read(os.path.join(ROOT, "src", name))
            self.assertNotIn("recs.remove(", source)
            self.assertNotIn("del recs[", source)

    def test_no_new_module_widens_a_lint_rule(self):
        for name in ("campaigns.py", "orchestrator.py"):
            source = read(os.path.join(ROOT, "src", name))
            self.assertNotIn("lint.MIN_WORDS =", source)
            self.assertNotIn("lint.BANNED", source)

    def test_the_campaign_holds_no_message_text(self):
        """One copy of every fact: the words live on the record."""
        campaign, recs, _ = self.approved_campaign()
        blob = json.dumps(campaign)
        self.assertNotIn("Worth a short call", blob)
        self.assertNotIn("@acme.test", blob)

    def test_every_new_event_name_is_registered(self):
        for name in ("CAMPAIGN_CREATED", "CAMPAIGN_APPROVED",
                     "CAMPAIGN_APPROVAL_INVALIDATED", "REPLY_CLASSIFIED",
                     "POSITIVE_REPLY_DETECTED", "SLACK_NOTIFICATION_PLANNED",
                     "SLACK_NOTIFICATION_SENT", "SLACK_NOTIFICATION_FAILED",
                     "SENDER_ASSIGNED", "EXTERNAL_CAMPAIGN_MAPPED",
                     "MEETING_MARKED", "OWNER_ASSIGNED"):
            self.assertIn(getattr(events, name), events.KNOWN, name)

    def test_every_module_parses_and_has_a_docstring(self):
        for name in ("campaigns.py", "orchestrator.py", "replies.py",
                     "senders.py", "roles.py", "inbound.py"):
            tree = ast.parse(read(os.path.join(ROOT, "src", name)))
            self.assertTrue(ast.get_docstring(tree), name)


if __name__ == "__main__":
    unittest.main()
