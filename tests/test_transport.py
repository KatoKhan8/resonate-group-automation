"""Inbound polling, Slack signing, and the traps in both providers' feeds.

The trap tests are the ones that matter most. Both providers return our own
outgoing messages in the same feed as the replies, so a naive reader pauses
every company it contacts. `TestOurOwnMessagesAreNotReplies` is the whole
reason src/adapters.py exists.
"""
import json
import time
import unittest

from src import adapters, events, inbound, observability, poller, store
from src.providers import bison, heyreach, slack
from tests.campaignbase import CampaignTest

# Which EmailBison workspace this fixture is pretending to read.
# `poller.run` asks the provider rather than trusting the caller, so a
# test has to supply the answer the way it supplies `fetch`. A live run
# passes neither and gets `GET /api/users`.
WORKSPACE = {"id": 10, "name": "PRODUCTIVE"}

SECRET = "synthetic-signing-secret-not-real"

# The real EmailBison shape, with the values replaced. Confirmed live
# 2026-08-26: cursor pagination under meta, type and folder per row.
BISON_PAGE = {
    "data": [
        {"id": 1608263, "uuid": "aaaaaaaa-0000-0000-0000-000000000001",
         "type": "Untracked Reply", "folder": "Inbox",
         "from_email_address": "champ@acme.test", "date_received": "2026-08-26",
         "created_at": "2026-08-26T11:00:00.000000Z",
         "text_body": "This is interesting, happy to chat.",
         "automated_reply": False, "campaign_id": None,
         "custom_variables": {"record_id": "acme", "contact_key": "acme-champ",
                              "client": "demo"}},
        {"id": 1608262, "uuid": "aaaaaaaa-0000-0000-0000-000000000002",
         "type": "Outgoing Email", "folder": "Sent",
         "from_email_address": "sender@demo.test", "date_received": "2026-08-26",
         "created_at": "2026-08-26T10:30:00.000000Z",
         "text_body": "Hi, quick question about your delivery teams.",
         "automated_reply": False},
        {"id": 1608261, "uuid": "aaaaaaaa-0000-0000-0000-000000000003",
         "type": "Bounced", "folder": "Bounced",
         "from_email_address": "gone@borealis.test", "date_received": "2026-08-26",
         "created_at": "2026-08-26T10:00:00.000000Z",
         "text_body": "550 no such user", "automated_reply": False,
         "custom_variables": {"record_id": "borealis",
                              "contact_key": "borealis-champ"}},
    ],
    "meta": {"next_cursor": "Y3Vyc29yLXBhZ2UtMg", "prev_cursor": None,
             "per_page": 15},
}

# The real HeyReach inbox shape, confirmed live 2026-08-26 over 600
# conversations, with every identifying value replaced. What is kept is the
# structure: threads with a complete `messages` list, senders that are exactly
# ME or CORRESPONDENT, identity under correspondentProfile, no campaign id and
# no populated customFields.
HEYREACH_PAGE = {
    "items": [
        # They replied and we have not answered: the simple case.
        {"id": "thread-0001", "lastMessageAt": "2026-08-26T11:00:00Z",
         "lastMessageSender": "CORRESPONDENT",
         "lastMessageText": "keen to hear more, send me some times",
         "lastMessageType": "TEXT", "linkedInAccountId": 55,
         "totalMessages": 2, "read": False, "groupChat": False,
         "correspondentProfile": {
             "profileUrl": "https://www.linkedin.com/in/acme-champ",
             "linkedin_id": "ACoAAA0000001", "firstName": "Champ",
             "lastName": "Acme", "companyName": "Acme Services",
             "position": "Operations Manager", "customFields": []},
         "messages": [
             {"sender": "ME", "body": "hi, saw you run delivery across teams",
              "createdAt": "2026-08-25T09:00:00Z", "isInMail": False},
             {"sender": "CORRESPONDENT",
              "body": "keen to hear more, send me some times",
              "createdAt": "2026-08-26T11:00:00Z", "isInMail": False}]},
        # We spoke last. 8 threads in 100 looked like this, and reading only
        # lastMessageSender would have missed the reply inside.
        {"id": "thread-0002", "lastMessageAt": "2026-08-26T12:00:00Z",
         "lastMessageSender": "ME",
         "lastMessageText": "great, sending an invite now",
         "lastMessageType": "TEXT", "linkedInAccountId": 55,
         "totalMessages": 3, "read": True, "groupChat": False,
         "correspondentProfile": {
             "profileUrl": "https://www.linkedin.com/in/borealis-champ",
             "linkedin_id": "ACoAAA0000002", "firstName": "Champ",
             "lastName": "Borealis", "customFields": []},
         "messages": [
             {"sender": "ME", "body": "quick question about delivery",
              "createdAt": "2026-08-24T09:00:00Z"},
             {"sender": "CORRESPONDENT",
              "body": "yes, interested - what does it cost?",
              "createdAt": "2026-08-25T16:00:00Z"},
             {"sender": "ME", "body": "great, sending an invite now",
              "createdAt": "2026-08-26T12:00:00Z"}]},
        # Only ever us: never an event.
        {"id": "thread-0003", "lastMessageAt": "2026-08-20T09:00:00Z",
         "lastMessageSender": "ME", "lastMessageText": "hello there",
         "lastMessageType": "TEXT", "linkedInAccountId": 55,
         "totalMessages": 1, "read": True, "groupChat": False,
         "correspondentProfile": {
             "profileUrl": "https://www.linkedin.com/in/never-replied",
             "linkedin_id": "ACoAAA0000003", "customFields": []},
         "messages": [
             {"sender": "ME", "body": "hello there",
              "createdAt": "2026-08-20T09:00:00Z"}]},
    ],
    "totalCount": 23893,
}


class TestOurOwnMessagesAreNotReplies(unittest.TestCase):
    """The trap: both feeds carry what we sent. Reading it back as a reply
    would pause every company the moment we contacted it."""

    def test_an_outgoing_email_is_not_an_event(self):
        mapped = adapters.from_emailbison(BISON_PAGE)
        ids = [e["provider_event_id"] for e in mapped]
        self.assertNotIn("emailbison:aaaaaaaa-0000-0000-0000-000000000002", ids)

    def test_the_reply_and_the_bounce_both_survive(self):
        mapped = adapters.from_emailbison(BISON_PAGE)
        self.assertEqual([e["type"] for e in mapped],
                         [events.REPLY_RECEIVED, events.EMAIL_BOUNCED])

    def test_a_row_in_the_sent_folder_is_outgoing_whatever_its_type(self):
        self.assertEqual(bison.classify_reply_row(
            {"type": "Something New", "folder": "Sent"}), "outgoing")

    def test_an_unrecognised_row_is_dropped_not_guessed(self):
        self.assertEqual(bison.classify_reply_row(
            {"type": "Quantum Email", "folder": "Elsewhere"}), "unknown")
        self.assertEqual(adapters.from_emailbison(
            {"data": [{"id": 1, "type": "Quantum Email", "folder": "Elsewhere"}]}),
            [])

    def test_our_own_linkedin_messages_are_not_replies(self):
        mapped = adapters.from_heyreach(HEYREACH_PAGE)
        for event in mapped:
            self.assertNotIn("never-replied", event["linkedin"])
        self.assertEqual(len(mapped), 2, "two prospect replies, three threads")

    def test_direction_is_an_allowlist_not_a_denylist(self):
        """Only CORRESPONDENT is inbound. A value HeyReach might add later -
        SYSTEM, TEAMMATE, AUTOMATION - must not read as a prospect reply."""
        self.assertEqual(heyreach.direction("CORRESPONDENT"), heyreach.THEIRS)
        self.assertEqual(heyreach.direction("ME"), heyreach.OURS)
        for unknown in ("SYSTEM", "TEAMMATE", "AUTOMATION", "lead", "them", ""):
            self.assertEqual(heyreach.direction(unknown), heyreach.UNKNOWN, unknown)

    def test_an_unknown_sender_produces_no_event(self):
        page = {"items": [{"id": "t", "correspondentProfile": {},
                           "messages": [{"sender": "SYSTEM", "body": "x",
                                         "createdAt": "2026-08-26T10:00:00Z"}]}]}
        self.assertEqual(adapters.from_heyreach(page), [])

    def test_a_reply_we_have_since_answered_is_still_found(self):
        """The bug this fixture exists for: 8 threads in 100 look like this."""
        mapped = adapters.from_heyreach(HEYREACH_PAGE)
        found = [e for e in mapped if "borealis" in e["linkedin"]]
        self.assertEqual(len(found), 1)
        self.assertIn("what does it cost", found[0]["text"])

    def test_a_conversation_with_no_sender_is_not_a_reply(self):
        self.assertFalse(heyreach.is_from_correspondent({}))
        self.assertEqual(heyreach.inbound_messages({}), [])


class TestTheEmailBisonMapping(unittest.TestCase):
    def test_the_event_id_is_the_providers_own_and_is_namespaced(self):
        mapped = adapters.from_emailbison(BISON_PAGE)
        self.assertTrue(mapped[0]["provider_event_id"].startswith("emailbison:"))

    def test_the_uuid_is_preferred_over_the_integer_id(self):
        mapped = adapters.from_emailbison(BISON_PAGE)
        self.assertIn("aaaaaaaa", mapped[0]["provider_event_id"])

    def test_our_identifiers_are_read_from_custom_variables(self):
        mapped = adapters.from_emailbison(BISON_PAGE)
        self.assertEqual(mapped[0]["record_id"], "acme")
        self.assertEqual(mapped[0]["contact_key"], "acme-champ")
        self.assertEqual(mapped[0]["client"], "demo")

    def test_the_providers_own_autoresponder_flag_is_carried(self):
        page = {"data": [dict(BISON_PAGE["data"][0], automated_reply=True)]}
        self.assertTrue(adapters.from_emailbison(page)[0]["automated"])

    def test_a_webhook_batch_maps_the_same_way(self):
        batch = {"events": [{"event": "replied", "id": "w-1",
                             "email": "champ@acme.test", "text": "interested",
                             "custom_variables": {"record_id": "acme"}}]}
        mapped = adapters.from_emailbison(batch)
        self.assertEqual(mapped[0]["type"], events.REPLY_RECEIVED)
        self.assertEqual(mapped[0]["record_id"], "acme")


class TestTheHeyReachMapping(unittest.TestCase):
    def test_the_event_id_is_the_thread_plus_the_messages_own_timestamp(self):
        mapped = adapters.from_heyreach(HEYREACH_PAGE)
        self.assertEqual(mapped[0]["provider_event_id"],
                         "heyreach:thread-0001:2026-08-26T11:00:00Z")

    def test_two_replies_in_one_thread_are_two_events(self):
        """A thread id alone would collapse them into one."""
        page = {"items": [{"id": "t9", "correspondentProfile": {},
                           "messages": [
                               {"sender": "CORRESPONDENT", "body": "one",
                                "createdAt": "2026-08-26T10:00:00Z"},
                               {"sender": "CORRESPONDENT", "body": "two",
                                "createdAt": "2026-08-26T11:00:00Z"}]}]}
        mapped = adapters.from_heyreach(page)
        self.assertEqual(len(mapped), 2)
        self.assertNotEqual(mapped[0]["provider_event_id"],
                            mapped[1]["provider_event_id"])

    def test_identity_comes_from_the_correspondent_profile(self):
        """customFields was empty on all 100 sampled, so the profile url is it."""
        mapped = adapters.from_heyreach(HEYREACH_PAGE)
        self.assertIn("acme-champ", mapped[0]["linkedin"])
        self.assertIsNone(mapped[0].get("record_id"))

    def test_no_campaign_id_is_invented_from_a_conversation(self):
        mapped = adapters.from_heyreach(HEYREACH_PAGE)
        self.assertIsNone(mapped[0].get("external_campaign_id"))

    def test_connection_acceptance_is_not_inferred_from_a_conversation(self):
        """Confirmed live: nothing in the inbox states it. `connections` is a
        follower count. Inferring it would unlock the day-8 follow-up for
        someone who never accepted."""
        self.assertFalse(heyreach.CONNECTION_STATUS_AVAILABLE)
        page = {"items": [{"id": "t", "correspondentProfile": {"connections": 500},
                           "messages": [{"sender": "CORRESPONDENT", "body": "hi",
                                         "createdAt": "2026-08-26T10:00:00Z"}]}]}
        kinds = {e["type"] for e in adapters.from_heyreach(page)}
        self.assertEqual(kinds, {events.REPLY_RECEIVED})
        self.assertNotIn(events.LINKEDIN_CONNECTED, kinds)

    def test_a_declared_connection_event_is_mapped(self):
        batch = {"items": [{"id": 5, "eventType": "connection_accepted",
                            "profileUrl": "https://www.linkedin.com/in/x",
                            "timestamp": "2026-08-26T10:00:00Z"}]}
        self.assertEqual(adapters.from_heyreach(batch)[0]["type"],
                         events.LINKEDIN_CONNECTED)

    def test_an_unknown_declared_event_is_dropped(self):
        batch = {"items": [{"id": 5, "eventType": "profile_viewed"}]}
        self.assertEqual(adapters.from_heyreach(batch), [])


class TestTheReadOnlyBoundary(CampaignTest):
    def test_heyreach_posts_only_to_its_read_routes(self):
        with self.assertRaises(Exception) as e:
            heyreach._read("/campaign/AddLeadsToCampaignV2", {})
        self.assertIn("not a read-only route", str(e.exception))

    def test_the_send_route_is_not_on_the_allowlist(self):
        self.assertNotIn("/campaign/AddLeadsToCampaignV2", heyreach.READ_ROUTES)
        self.assertIn("/campaign/GetAll", heyreach.READ_ROUTES)

    def test_no_code_calls_the_send_route(self):
        """add_leads_endpoint() builds a URL string and is reviewable for it.
        What must not exist is a call that sends to it."""
        import inspect
        import re
        for module in (bison, heyreach):
            source = inspect.getsource(module)
            for line in source.splitlines():
                if "request(" not in line:
                    continue
                for send in ("AddLeadsToCampaign", "leads_endpoint",
                             "add_leads_endpoint"):
                    self.assertNotIn(send, line, f"{module.__name__}: {line.strip()}")

    def test_the_endpoint_builders_only_build(self):
        url = heyreach.add_leads_endpoint()
        self.assertTrue(url.startswith("https://"))
        self.assertEqual(self.cassette.calls, [], "building a URL called nothing")


class TestTheRealFetchFunction(CampaignTest):
    """The poller tests inject a fake `fetch`, which is what let a missing
    import survive: `bison.fetch_replies` referenced `query` without importing
    it, so the function raised NameError the first time it was ever called for
    real. These call it through the transport seam instead, so the whole
    function body is exercised offline.
    """

    def wire(self, payload, status=200):
        recorded = []

        def transport(method, url, headers, body, timeout):
            recorded.append({"method": method, "url": url, "body": body})
            return status, json.dumps(payload)

        self.providers.set_transport(transport)
        return recorded

    def test_fetch_replies_builds_a_real_request(self):
        calls = self.wire(BISON_PAGE)
        rows, cursor = bison.fetch_replies()
        self.assertEqual(len(rows), 3)
        self.assertEqual(cursor, "Y3Vyc29yLXBhZ2UtMg")
        self.assertEqual(calls[0]["method"], "GET")
        self.assertIn("/replies", calls[0]["url"])

    def test_a_cursor_is_carried_in_the_query_string(self):
        calls = self.wire(BISON_PAGE)
        bison.fetch_replies(cursor="abc123")
        self.assertIn("cursor=abc123", calls[0]["url"])

    def test_no_cursor_means_no_cursor_parameter(self):
        calls = self.wire(BISON_PAGE)
        bison.fetch_replies()
        self.assertNotIn("cursor=", calls[0]["url"])

    def test_cursor_pagination_is_actually_requested(self):
        """The fixture honoured a contract the real API does not.

        `fetch_replies` reads `meta.next_cursor`, but EmailBison only puts
        that key in `meta` when the request asks for cursor pagination.
        Asking for the default offset pagination returns
        `current_page/last_page/total` and no cursor at all, so the helper
        returned None forever, the poller stopped after one page and never
        checkpointed, and every run re-read the same first fifteen replies.
        Against the real instance that is 15 of 269,877 - a reply that
        stops a cadence would never be seen.

        BISON_PAGE carries a next_cursor unconditionally, which is why
        every offline test passed while the live call could not work. This
        asserts on the request we build, not on the fake's answer.
        """
        calls = self.wire(BISON_PAGE)
        bison.fetch_replies()
        self.assertIn("pagination_type=cursor", calls[0]["url"])

    def test_the_page_size_is_capped_at_the_documented_maximum(self):
        calls = self.wire(BISON_PAGE)
        bison.fetch_replies(per_page=10_000)
        self.assertIn(f"per_page={bison.PER_PAGE_MAX}", calls[0]["url"])

    def test_a_non_2xx_raises_rather_than_returning_an_empty_page(self):
        self.wire({"message": "unauthorised"}, status=401)
        with self.assertRaises(bison.ProviderError):
            bison.fetch_replies()

    def test_a_response_that_is_not_an_object_raises(self):
        self.wire(["not", "a", "page"])
        with self.assertRaises(bison.ProviderError):
            bison.fetch_replies()

    def test_a_page_with_no_meta_yields_no_cursor_rather_than_failing(self):
        self.wire({"data": []})
        rows, cursor = bison.fetch_replies()
        self.assertEqual(rows, [])
        self.assertIsNone(cursor)

    def test_every_helper_a_provider_uses_is_in_its_namespace(self):
        """The bug in one line: `query` was used and never imported, so the
        function raised NameError the first time it was called for real.

        Checked across every provider, because the same slip anywhere else
        would also only show up live.
        """
        import inspect
        from src.providers import apify, contactout, deliverable, reoon
        helpers = ("query", "request", "ok", "key", "result", "failed", "first")
        for module in (bison, heyreach, contactout, reoon, apify, deliverable):
            source = inspect.getsource(module)
            for helper in helpers:
                if f"{helper}(" not in source:
                    continue
                self.assertTrue(hasattr(module, helper),
                                f"{module.__name__} uses {helper}() but does "
                                "not import it")


class TestPolling(CampaignTest):
    def setUp(self):
        super().setUp()
        import os
        os.environ["CHECKPOINTS"] = self.tmp + "/work/checkpoints.json"

    def test_a_dry_run_fetches_nothing(self):
        calls = []
        result = poller.run("emailbison", live=False,
                            fetch=lambda **kw: calls.append(kw))
        self.assertFalse(result["live"])
        self.assertEqual(calls, [])
        self.assertEqual(self.cassette.calls, [])

    def test_a_live_poll_walks_pages_until_the_cursor_runs_out(self):
        pages = [(BISON_PAGE["data"], "cursor-2"), ([], None)]
        seen = []

        def fetch(cursor=None, per_page=None):
            seen.append(cursor)
            return pages[len(seen) - 1]

        result = poller.run("emailbison", live=True, identify=lambda: WORKSPACE, fetch=fetch,
                            recs=self.seed_records(), config=self.config,
                            post=lambda p, c=None: {"ok": True},
                            sleep=lambda s: None)
        self.assertEqual(seen, [None, "cursor-2"])
        self.assertEqual(result["pages"], 1,
                         "the empty second page carried nothing to ingest")

    def test_what_is_stored_is_a_high_water_mark_not_the_provider_cursor(self):
        """This used to assert that "cursor-9" was stored, which is the
        defect rather than the contract.

        `/api/replies` is newest-first and its cursor bounds the page to
        *older* rows, so resuming from a stored cursor walks backwards into
        history and never sees a reply that arrives afterwards. What is
        worth remembering is how far forward we have read, so the mark is
        the newest `created_at` ingested. See tests/test_reply_high_water.py.
        """
        def fetch(cursor=None, per_page=None):
            return (BISON_PAGE["data"], "cursor-9") if cursor is None else ([], None)

        poller.run("emailbison", live=True, identify=lambda: WORKSPACE, fetch=fetch,
                   recs=self.seed_records(), config=self.config,
                   post=lambda p, c=None: {"ok": True}, sleep=lambda s: None)
        # Scoped now: the mark belongs to workspace 10, not to a slot
        # shared with whichever estate the key was last bound to.
        stored = poller.cursor_for("emailbison", "ws10")
        self.assertEqual(stored, "2026-08-26T11:00:00.000000Z")
        self.assertNotEqual(stored, "cursor-9", "a cursor points at history")

    def test_a_repeating_cursor_does_not_loop_forever(self):
        calls = []

        def fetch(cursor=None, per_page=None):
            calls.append(cursor)
            return (BISON_PAGE["data"], "same-cursor")

        poller.run("emailbison", live=True, identify=lambda: WORKSPACE, fetch=fetch, max_pages=10,
                   recs=self.seed_records(), config=self.config,
                   post=lambda p, c=None: {"ok": True}, sleep=lambda s: None)
        self.assertLessEqual(len(calls), 3, "a repeating cursor must stop")

    def test_max_pages_bounds_a_provider_that_never_ends(self):
        calls = []

        def fetch(cursor=None, per_page=None):
            calls.append(cursor)
            return (BISON_PAGE["data"], f"cursor-{len(calls)}")

        poller.run("emailbison", live=True, identify=lambda: WORKSPACE, fetch=fetch, max_pages=3,
                   recs=self.seed_records(), config=self.config,
                   post=lambda p, c=None: {"ok": True}, sleep=lambda s: None)
        self.assertEqual(len(calls), 3)

    def test_a_second_poll_of_the_same_page_changes_nothing(self):
        recs = self.seed_records()

        def fetch(cursor=None, per_page=None):
            return BISON_PAGE["data"], None

        for _ in range(2):
            poller.run("emailbison", live=True, identify=lambda: WORKSPACE, fetch=fetch, recs=recs,
                       config=self.config, post=lambda p, c=None: {"ok": True},
                       sleep=lambda s: None)
        applied = [e for e in recs[0]["events"]
                   if e["type"] == events.REPLY_RECEIVED]
        self.assertEqual(len(applied), 1)

    def test_a_corrupt_checkpoint_file_does_not_stop_the_world(self):
        import os
        path = poller.checkpoint_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(poller.load_checkpoints(), {})

    def test_heyreach_pages_by_offset_and_stops_on_a_short_page(self):
        calls = []

        def fetch(offset=0, limit=50):
            calls.append(offset)
            return (HEYREACH_PAGE["items"], 2)

        poller.run("heyreach", live=True, fetch=fetch, page_size=50,
                   recs=self.seed_records(), config=self.config,
                   post=lambda p, c=None: {"ok": True}, sleep=lambda s: None)
        self.assertEqual(calls, [0])


class TestRetry(unittest.TestCase):
    def test_a_transient_failure_is_retried_then_succeeds(self):
        attempts = []

        def flaky():
            attempts.append(1)
            if len(attempts) < 2:
                raise __import__("src.providers", fromlist=["x"]).ProviderError("down")
            return "ok"

        self.assertEqual(poller.with_retry(flaky, sleep=lambda s: None), "ok")
        self.assertEqual(len(attempts), 2)

    def test_it_gives_up_rather_than_looping(self):
        from src.providers import ProviderError

        def always():
            raise ProviderError("still down")

        with self.assertRaises(poller.PollError):
            poller.with_retry(always, attempts=3, sleep=lambda s: None)

    def test_the_backoff_is_finite(self):
        self.assertTrue(all(isinstance(x, (int, float))
                            for x in poller.BACKOFF_SECONDS))
        self.assertLessEqual(sum(poller.BACKOFF_SECONDS), 10)

    def test_a_programming_error_is_not_retried(self):
        def broken():
            raise ValueError("this is a bug, not an outage")

        with self.assertRaises(ValueError):
            poller.with_retry(broken, sleep=lambda s: None)


class TestSlackSigning(unittest.TestCase):
    def body(self):
        return "payload=%7B%22type%22%3A%22block_actions%22%7D"

    def test_a_valid_signature_verifies(self):
        now = int(time.time())
        signature = slack.sign(self.body(), now, SECRET)
        self.assertTrue(slack.verify(self.body(), now, signature, SECRET, now=now))

    def test_a_forged_signature_is_refused(self):
        now = int(time.time())
        with self.assertRaises(slack.BadSignature):
            slack.verify(self.body(), now, "v0=" + "0" * 64, SECRET, now=now)

    def test_a_tampered_body_is_refused(self):
        now = int(time.time())
        signature = slack.sign(self.body(), now, SECRET)
        with self.assertRaises(slack.BadSignature):
            slack.verify("payload=%7B%22evil%22%3Atrue%7D", now, signature,
                         SECRET, now=now)

    def test_an_old_timestamp_is_refused_even_with_a_real_signature(self):
        old = int(time.time()) - 10_000
        signature = slack.sign(self.body(), old, SECRET)
        with self.assertRaises(slack.BadSignature) as e:
            slack.verify(self.body(), old, signature, SECRET)
        self.assertIn("old", str(e.exception))

    def test_a_future_timestamp_is_refused_too(self):
        now = int(time.time())
        future = now + 10_000
        signature = slack.sign(self.body(), future, SECRET)
        with self.assertRaises(slack.BadSignature):
            slack.verify(self.body(), future, signature, SECRET, now=now)

    def test_a_missing_timestamp_is_refused(self):
        with self.assertRaises(slack.BadSignature):
            slack.verify(self.body(), None, "v0=x", SECRET)

    def test_no_signing_secret_refuses_rather_than_trusting(self):
        with self.assertRaises(slack.BadSignature) as e:
            slack.sign(self.body(), int(time.time()), secret="")
        self.assertIn("SLACK_SIGNING_SECRET", str(e.exception))

    def test_the_comparison_is_constant_time(self):
        import inspect
        self.assertIn("compare_digest", inspect.getsource(slack.verify))


class TestSlackPostingStaysOff(CampaignTest):
    def test_posting_is_off_without_the_explicit_flag(self):
        import os
        os.environ["SLACK_BOT_TOKEN"] = "not-a-real-slack-token"
        try:
            self.assertFalse(slack.live(), "a token alone must not enable posting")
        finally:
            os.environ.pop("SLACK_BOT_TOKEN", None)

    def test_a_flag_without_a_token_is_also_off(self):
        import os
        os.environ["SLACK_LIVE"] = "1"
        os.environ.pop("SLACK_BOT_TOKEN", None)
        try:
            self.assertFalse(slack.live())
        finally:
            os.environ.pop("SLACK_LIVE", None)

    def test_post_refuses_and_names_the_switch(self):
        with self.assertRaises(slack.SlackPostingNotEnabled) as e:
            slack.post({"channel": "C1", "text": "hi"}, self.config)
        self.assertIn("SLACK_LIVE", str(e.exception))

    def test_the_health_check_calls_nothing_while_posting_is_off(self):
        slack.check()
        self.assertEqual(self.cassette.calls, [])

    def test_a_payload_with_no_channel_is_refused_rather_than_defaulted(self):
        import os
        os.environ["SLACK_LIVE"] = "1"
        os.environ["SLACK_BOT_TOKEN"] = "not-a-real-slack-token"
        try:
            with self.assertRaises(slack.SlackPostingNotEnabled) as e:
                slack.post({"text": "hi"}, self.config)
            self.assertIn("no default", str(e.exception))
        finally:
            os.environ.pop("SLACK_LIVE", None)
            os.environ.pop("SLACK_BOT_TOKEN", None)


class TestObservability(unittest.TestCase):
    def setUp(self):
        observability.reset()

    def test_an_unknown_metric_is_refused(self):
        with self.assertRaises(events.UnknownEvent):
            observability.count("made_up_metric")

    def test_a_detail_is_truncated_rather_than_stored_whole(self):
        entry = observability.count(events.WEBHOOK_REJECTED, detail="x" * 5000)
        self.assertLessEqual(len(entry["detail"]), observability.DETAIL_LIMIT)

    def test_counts_accumulate(self):
        for _ in range(3):
            observability.count(events.EVENT_DUPLICATE)
        self.assertEqual(observability.counts()[events.EVENT_DUPLICATE], 3)

    def test_every_named_metric_is_registered(self):
        for name in ("WEBHOOK_RECEIVED", "WEBHOOK_REJECTED", "EVENT_INGESTED",
                     "EVENT_DUPLICATE", "EVENT_UNKNOWN", "EVENT_RETRY_SCHEDULED",
                     "SLACK_POST_PLANNED", "SLACK_POST_SENT", "SLACK_POST_FAILED",
                     "CAMPAIGN_MAPPING_VALIDATED", "CAMPAIGN_MAPPING_FAILED"):
            self.assertIn(getattr(events, name), events.OBSERVED, name)


if __name__ == "__main__":
    unittest.main()
