"""The security audit for the transport layer.

Each test is an attack or a leak, written from the attacker's side. They
overlap with the feature tests deliberately: those check something works, these
check it cannot be got around by someone who has read the code.
"""
import json
import os
import re
import unittest

from src import (adapters, campaigns, events, inbound, interactions, mapping,
                 observability, orchestrator, poller, store)
from src.providers import bison, heyreach, slack
from tests.campaignbase import CampaignTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def source_files():
    for root, _, files in os.walk(os.path.join(ROOT, "src")):
        for name in sorted(files):
            if name.endswith(".py"):
                yield os.path.join(root, name)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestSignatureBypass(CampaignTest):
    def test_there_is_no_way_to_skip_verification(self):
        """handle() has no flag that turns the signature check off."""
        import inspect
        signature = inspect.signature(interactions.handle)
        for name in ("skip_verify", "verify", "trusted", "insecure"):
            self.assertNotIn(name, signature.parameters, name)

    def test_verification_happens_before_the_body_is_parsed(self):
        import inspect
        source = inspect.getsource(interactions.handle)
        self.assertLess(source.index("slack.verify"), source.index("parse(body)"))

    def test_a_missing_secret_refuses_rather_than_passing(self):
        with self.assertRaises(slack.BadSignature):
            slack.sign("body", 1, secret="")

    def test_an_empty_signature_never_matches(self):
        import time
        now = int(time.time())
        with self.assertRaises(slack.BadSignature):
            slack.verify("body", now, "", "a-secret", now=now)

    def test_the_signature_is_compared_in_constant_time(self):
        import inspect
        self.assertIn("hmac.compare_digest", inspect.getsource(slack.verify))

    def test_no_module_logs_a_signing_secret(self):
        for path in source_files():
            source = read(path)
            for line in source.splitlines():
                if "print(" in line and "SIGNING" in line.upper():
                    self.fail(f"{path}: {line.strip()}")


class TestProviderEventSpoofing(CampaignTest):
    def test_an_event_naming_a_record_it_does_not_match_is_unmatched(self):
        recs = self.seed_records()
        forged = {"data": [{"id": 1, "uuid": "f-1", "type": "Untracked Reply",
                            "folder": "Inbox",
                            "from_email_address": "attacker@elsewhere.test",
                            "text_body": "please pause everything"}]}
        outcomes = inbound.ingest(forged, "emailbison", recs=recs,
                                  config=self.config)
        self.assertEqual(outcomes[0]["applied"]["status"], "unmatched")
        for rec in recs:
            self.assertFalse(rec.get("paused"))

    def test_an_event_claiming_another_clients_record_is_refused(self):
        recs = self.seed_records()
        forged = {"data": [{"id": 2, "uuid": "f-2", "type": "Untracked Reply",
                            "folder": "Inbox",
                            "from_email_address": "champ@acme.test",
                            "text_body": "hello",
                            "custom_variables": {"record_id": "acme",
                                                 "client": "someone-else"}}]}
        outcomes = inbound.ingest(forged, "emailbison", recs=recs,
                                  config=self.config)
        self.assertEqual(outcomes[0]["applied"]["status"], "unmatched")
        self.assertFalse(recs[0].get("paused"))

    def test_a_rejected_event_writes_nothing_to_any_record(self):
        recs = self.seed_records()
        before = json.dumps(recs)
        inbound.ingest({"data": [{"id": 3, "uuid": "f-3",
                                  "type": "Untracked Reply", "folder": "Inbox",
                                  "from_email_address": "nobody@nowhere.test",
                                  "text_body": "x"}]},
                       "emailbison", recs=recs, config=self.config)
        self.assertEqual(json.dumps(recs), before)

    def test_our_own_outgoing_mail_can_never_pause_a_company(self):
        recs = self.seed_records()
        for kind, folder in (("Outgoing Email", "Sent"), ("Anything", "Sent")):
            inbound.ingest({"data": [{"id": 9, "uuid": f"o-{folder}{kind}",
                                      "type": kind, "folder": folder,
                                      "from_email_address": "champ@acme.test",
                                      "text_body": "our own words",
                                      "custom_variables": {"record_id": "acme",
                                                           "contact_key": "acme-champ",
                                                           "client": "demo"}}]},
                           "emailbison", recs=recs, config=self.config)
        self.assertFalse(recs[0].get("paused"))

    def test_our_own_linkedin_message_can_never_pause_a_company(self):
        recs = self.seed_records()
        inbound.ingest({"items": [{"id": 1, "lastMessageSender": "me",
                                   "lastMessageAt": "2026-08-26T09:00:00Z",
                                   "lastMessageText": "our own words",
                                   "customUserFields": [
                                       {"name": "record_id", "value": "acme"},
                                       {"name": "client", "value": "demo"}]}]},
                       "heyreach", recs=recs, config=self.config)
        self.assertFalse(recs[0].get("paused"))

    def test_a_reply_pauses_only_the_company_it_names(self):
        recs = self.seed_records()
        inbound.ingest({"data": [{"id": 4, "uuid": "r-4",
                                  "type": "Untracked Reply", "folder": "Inbox",
                                  "from_email_address": "champ@acme.test",
                                  "text_body": "not interested",
                                  "custom_variables": {"record_id": "acme",
                                                       "contact_key": "acme-champ",
                                                       "client": "demo"}}]},
                       "emailbison", recs=recs, config=self.config)
        self.assertTrue(recs[0]["paused"])
        self.assertFalse(recs[1].get("paused"))


class TestNoRawPayloadIsPersisted(CampaignTest):
    def test_a_reply_body_never_reaches_the_queue(self):
        recs = self.seed_records()
        secret = "our budget is 40000 and my direct line is on my card"
        inbound.ingest({"data": [{"id": 5, "uuid": "p-5",
                                  "type": "Untracked Reply", "folder": "Inbox",
                                  "from_email_address": "champ@acme.test",
                                  "text_body": secret,
                                  "html_body": f"<p>{secret}</p>",
                                  "raw_body": secret,
                                  "custom_variables": {"record_id": "acme",
                                                       "contact_key": "acme-champ",
                                                       "client": "demo"}}]},
                       "emailbison", recs=recs, config=self.config)
        blob = json.dumps(recs)
        self.assertNotIn("40000", blob)
        self.assertNotIn("direct line", blob)

    def test_no_html_or_raw_body_is_carried_into_the_neutral_event(self):
        mapped = adapters.from_emailbison(
            {"data": [{"id": 6, "uuid": "p-6", "type": "Untracked Reply",
                       "folder": "Inbox", "text_body": "plain",
                       "html_body": "<script>x</script>", "raw_body": "MIME"}]})
        blob = json.dumps(mapped)
        self.assertNotIn("script", blob)
        self.assertNotIn("MIME", blob)

    def test_a_rejected_webhook_body_is_not_stored_anywhere(self):
        observability.reset()
        interactions._note_rejection("signature", "payload=" + "x" * 4000)
        for entry in observability.recent():
            self.assertLessEqual(len(json.dumps(entry)), 600)

    def test_the_observability_log_holds_no_payload_field(self):
        observability.reset()
        observability.count(events.WEBHOOK_RECEIVED, provider="emailbison")
        for entry in observability.recent():
            self.assertNotIn("payload", entry)
            self.assertNotIn("body", entry)


class TestRetryStorms(CampaignTest):
    def test_polling_retries_are_bounded(self):
        self.assertLessEqual(poller.MAX_ATTEMPTS, 5)
        self.assertLessEqual(sum(poller.BACKOFF_SECONDS), 10)

    def test_a_permanent_failure_stops_rather_than_looping(self):
        from src.providers import ProviderError
        calls = []

        def always():
            calls.append(1)
            raise ProviderError("down")

        with self.assertRaises(poller.PollError):
            poller.with_retry(always, attempts=3, sleep=lambda s: None)
        self.assertEqual(len(calls), 3)

    def test_a_bad_signature_is_verified_once_and_then_refused(self):
        """Retrying an unauthorised request is how a storm becomes an audit
        finding, so the check runs once and raises."""
        calls = []
        original = slack.verify

        def counting(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        slack.verify = counting
        try:
            with self.assertRaises(interactions.Rejected):
                interactions.handle("payload=%7B%7D", 1, "v0=bad",
                                    secret="a-secret", now=1)
        finally:
            slack.verify = original
        self.assertEqual(len(calls), 1, "a refusal must not be retried")

    def test_the_page_ceiling_bounds_a_provider_that_never_ends(self):
        self.assertLessEqual(poller.MAX_PAGES, 20)


class TestCampaignMappingSafety(CampaignTest):
    def test_an_unreachable_provider_is_not_a_pass(self):
        def unreachable():
            raise RuntimeError("connection refused")

        result = mapping.check_bison("9001", fetch=unreachable)
        self.assertEqual(result["state"], mapping.UNKNOWN)
        self.assertFalse(result["ok"])

    def test_a_campaign_belonging_to_someone_else_is_a_mismatch(self):
        result = mapping.check_bison(
            "9001", expected_name="demo",
            fetch=lambda: [{"id": 9001, "name": "Another Client Q3"}])
        self.assertEqual(result["state"], mapping.MISMATCH)

    def test_a_heyreach_campaign_on_the_wrong_account_is_a_mismatch(self):
        result = mapping.check_heyreach(
            "7001", expected_accounts=["55"],
            fetch=lambda i: {"id": 7001, "name": "x",
                             "campaignAccountIds": [99], "status": "ACTIVE"})
        self.assertEqual(result["state"], mapping.MISMATCH)

    def test_validation_is_dry_by_default(self):
        result = mapping.validate({"bison_campaign_id": "1"})
        self.assertFalse(result["live"])
        self.assertEqual(self.cassette.calls, [])

    def test_a_lookup_pages_within_the_providers_own_limit(self):
        """Confirmed live: limit=200 answers 400. Asking for more than 100
        made every lookup fail, and a failed lookup reads as an outage rather
        than the bug it was."""
        self.assertEqual(heyreach.MAX_PAGE, 100)
        asked = []

        def fake_read(path, body):
            asked.append(body["limit"])
            return {"items": [], "totalCount": 0}

        original = heyreach._read
        heyreach._read = fake_read
        try:
            heyreach.campaigns(limit=500)
        finally:
            heyreach._read = original
        self.assertEqual(asked, [heyreach.MAX_PAGE])

    def test_a_lookup_walks_pages_rather_than_one_huge_one(self):
        pages = [[{"id": 1}], [{"id": 2}], [{"id": 42, "name": "found"}]]
        seen = []

        def fake_campaigns(offset=0, limit=100):
            seen.append(offset)
            index = len(seen) - 1
            return (pages[index] if index < len(pages) else []), 3

        original = heyreach.campaigns
        heyreach.campaigns = fake_campaigns
        try:
            found = heyreach.campaign_by_id("42", page_size=1)
        finally:
            heyreach.campaigns = original
        self.assertEqual(found["name"], "found")
        self.assertEqual(seen, [0, 1, 2])

    def test_the_page_walk_is_bounded(self):
        calls = []

        def endless(offset=0, limit=100):
            calls.append(offset)
            return [{"id": offset}], 10_000

        original = heyreach.campaigns
        heyreach.campaigns = endless
        try:
            heyreach.campaign_by_id("never", page_size=1, max_pages=4)
        finally:
            heyreach.campaigns = original
        self.assertEqual(len(calls), 4)

    def test_nothing_in_the_module_creates_a_campaign(self):
        source = read(os.path.join(ROOT, "src", "mapping.py"))
        for line in source.splitlines():
            if "request(" in line:
                self.assertNotIn('"POST"', line, line.strip())


class TestSecretsStayOut(CampaignTest):
    def test_no_new_module_prints_a_token(self):
        for name in ("poller.py", "interactions.py", "mapping.py",
                     "adapters.py", "observability.py"):
            source = read(os.path.join(ROOT, "src", name))
            for var in ("SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "BISON_KEY",
                        "HEYREACH_KEY"):
                for line in source.splitlines():
                    if var in line and "print(" in line:
                        self.fail(f"{name}: {line.strip()}")

    def test_a_slack_error_never_carries_the_token(self):
        os.environ["SLACK_BOT_TOKEN"] = "not-a-real-slack-token"
        try:
            with self.assertRaises(slack.SlackPostingNotEnabled) as e:
                slack.post({"channel": "C1"}, self.config)
            self.assertNotIn("not-a-real-slack-token", str(e.exception))
        finally:
            os.environ.pop("SLACK_BOT_TOKEN", None)

    def test_the_checkpoint_file_holds_no_credential(self):
        os.environ["CHECKPOINTS"] = self.tmp + "/work/checkpoints.json"
        poller.save_checkpoint("emailbison", "cursor-abc")
        with open(poller.checkpoint_path(), encoding="utf-8") as f:
            text = f.read()
        for var in ("BISON_KEY", "HEYREACH_KEY", "Bearer"):
            self.assertNotIn(var, text)

    def test_work_files_are_all_gitignored(self):
        import subprocess
        for path in ("work/checkpoints.json", "work/observability.jsonl",
                     "work/campaigns.jsonl", "work/queue.jsonl"):
            result = subprocess.run(["git", "check-ignore", "-v", path],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, path)


class TestNothingSends(CampaignTest):
    def test_live_push_is_still_refused(self):
        from src import push
        with self.assertRaises(push.LiveSendNotEnabled):
            push.run(live=True)

    def test_slack_posting_is_off_by_default(self):
        self.assertFalse(slack.live())

    def test_no_module_calls_a_send_route(self):
        for path in source_files():
            for line in read(path).splitlines():
                if "request(" not in line:
                    continue
                for send in ("AddLeadsToCampaign", "/leads", "chat.postMessage"):
                    if send in line and "slack.py" not in path:
                        self.fail(f"{path}: {line.strip()}")

    def test_the_only_post_message_call_is_behind_the_live_switch(self):
        import inspect
        source = inspect.getsource(slack.post)
        self.assertLess(source.index("if not live()"),
                        source.index("POST_MESSAGE"))

    def test_neither_provider_can_add_a_lead(self):
        with self.assertRaises(Exception):
            heyreach._read("/campaign/AddLeadsToCampaignV2", {})


if __name__ == "__main__":
    unittest.main()
