"""TASK-249: privacy and routing tests for the new Slack agent queries.

Five categories:

1. **Lead lookup is DM-only.** A channel is a room with an audience; a
   lead's status is about one identifiable person.  In a channel the
   answer is one line saying it is DM-only, and it must not leak the
   answer while refusing.

2. **The answer never echoes the identifier.**  Asked "status of <email>",
   the reply says "that lead is enrolled in campaign 491" with no address
   and no name.

3. **Account answer carries the domain and never a contact.**

4. **The log row records who asked and what was asked.**

5. **Routing.** The new keyword patterns route to the correct query.
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import store as _store                                   # noqa: E402
from src import events as _events                                 # noqa: E402
from src import slackagentreadback as readback                    # noqa: E402


class _IsolatedStore:
    """Context manager that points every state override at a temp dir."""

    def __init__(self):
        self.tmp = tempfile.mkdtemp()
        self.overrides = {
            "QUEUE": os.path.join(self.tmp, "queue.jsonl"),
            "CAMPAIGNS": os.path.join(self.tmp, "campaigns.jsonl"),
            "CLIENT_APPROVAL": os.path.join(self.tmp, "client-approval.jsonl"),
            "NOTIFICATIONS": os.path.join(self.tmp, "notifications.jsonl"),
            "SPEND_LEDGER": os.path.join(self.tmp, "spend-ledger.jsonl"),
            "MX_CACHE": os.path.join(self.tmp, "mx"),
            "JOBS": os.path.join(self.tmp, "jobs.jsonl"),
            "WORKSPACES": os.path.join(self.tmp, "workspaces.jsonl"),
            "AUDIT": os.path.join(self.tmp, "audit.jsonl"),
            "SENDERS": os.path.join(self.tmp, "senders.jsonl"),
            "REPORTS": os.path.join(self.tmp, "reports"),
            "REPORT_DRAFTS": os.path.join(self.tmp, "drafts"),
            "OBSERVABILITY": os.path.join(self.tmp, "obs"),
            "CHECKPOINTS": os.path.join(self.tmp, "checkpoints"),
            "REPLY_WATCH_STATUS": os.path.join(self.tmp, "replywatch.json"),
            "TAG_OUTBOX": os.path.join(self.tmp, "tag-outbox.jsonl"),
            "AGENCY_DNC": os.path.join(self.tmp, "dnc.jsonl"),
            "SIGNALS": os.path.join(self.tmp, "signals.jsonl"),
            "GTM": os.path.join(self.tmp, "gtm.jsonl"),
            "DISCOVERY": os.path.join(self.tmp, "discovery.jsonl"),
            "CLIENT_REVIEW": os.path.join(self.tmp, "client-review.jsonl"),
            "CRAWL_CACHE": os.path.join(self.tmp, "crawl"),
            "ACTION_LEDGER": os.path.join(self.tmp, "action-ledger.jsonl"),
            "LEAD_OBSERVATIONS": os.path.join(self.tmp, "lead-obs.jsonl"),
        }
        self.old = {}

    def __enter__(self):
        for key, val in self.overrides.items():
            self.old[key] = os.environ.get(key)
            os.environ[key] = val
        for d in ("mx", "reports", "drafts", "obs", "checkpoints", "crawl"):
            os.makedirs(os.path.join(self.tmp, d), exist_ok=True)
        return self.tmp

    def __exit__(self, *exc):
        for key, val in self.old.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        return False


def _isolated_store():
    return _IsolatedStore()


def _make_record(domain="acme.com", state="verified", contacts=None,
                 events_list=None, verdict=None):
    return {
        "id": "rec-" + domain.replace(".", "-"),
        "lane": "cold",
        "client": "test-client",
        "company": "Acme Corp",
        "domain": domain,
        "state": state,
        "drop_reason": None,
        "contacts": contacts or [],
        "events": events_list or [],
        "verdict": verdict or {},
        "log": [],
    }


def _seed_queue(records):
    """Write records to the isolated queue."""
    path = _store.queue_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


# ============================================================== 1. DM-ONLY

class LeadLookupIsDMOnly(unittest.TestCase):
    """A lead lookup in a channel refuses AND does not echo the identifier.

    The refusal must not contain the email address or any part of it -
    "I cannot look up jane@acme.com here" has already said who was asked
    about.
    """

    def test_channel_refuses_without_echoing_email(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import slack_agent_loop as loop

        with _isolated_store():
            _seed_queue([_make_record(contacts=[
                {"email": "jane@acme.com", "key": "jane",
                 "first_name": "Jane", "last_name": "Doe"}
            ])])

            reply, how, query = loop.answer_for(
                "status of jane@acme.com", channel_type="channel")

        self.assertEqual(query, "lead")
        self.assertIn("refused", how.lower())
        self.assertIn("DM-only", reply)
        self.assertNotIn("jane", reply.lower())
        self.assertNotIn("acme.com", reply.lower())
        self.assertNotIn("@", reply)

    def test_channel_refuses_without_echoing_linkedin(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import slack_agent_loop as loop

        with _isolated_store():
            _seed_queue([_make_record(contacts=[
                {"linkedin_url": "https://linkedin.com/in/janedoe",
                 "key": "jane", "first_name": "Jane"}
            ])])

            reply, how, query = loop.answer_for(
                "status of https://linkedin.com/in/janedoe",
                channel_type="channel")

        self.assertEqual(query, "lead")
        self.assertIn("refused", how.lower())
        self.assertNotIn("janedoe", reply.lower())
        self.assertNotIn("linkedin", reply.lower())

    def test_dm_answers_without_echoing_address(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import slack_agent_loop as loop

        with _isolated_store():
            _seed_queue([_make_record(contacts=[
                {"email": "jane@acme.com", "key": "jane",
                 "first_name": "Jane", "last_name": "Doe"}
            ])])

            reply, how, query = loop.answer_for(
                "status of jane@acme.com", channel_type="im")

        self.assertEqual(query, "lead")
        self.assertNotIn("refused", how.lower())
        self.assertNotIn("jane@acme.com", reply)
        self.assertNotIn("Jane", reply)
        self.assertNotIn("Doe", reply)
        self.assertIn("acme.com", reply)


# ============================================================== 2. NO ECHO

class AnswerNeverEchoesIdentifier(unittest.TestCase):
    """The answer contains no address and no name, only the domain."""

    def test_lead_dm_answer_has_no_email(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import slack_agent_loop as loop

        with _isolated_store():
            _seed_queue([_make_record(domain="widget.io", contacts=[
                {"email": "bob@widget.io", "key": "bob",
                 "first_name": "Bob", "last_name": "Smith"}
            ])])

            reply, how, query = loop.answer_for(
                "status of bob@widget.io", channel_type="im")

        self.assertNotIn("bob@widget.io", reply)
        self.assertNotIn("Bob", reply)
        self.assertNotIn("Smith", reply)
        self.assertIn("widget.io", reply)


# ============================================================== 3. ACCOUNT

class AccountAnswerCarriesDomainNotContact(unittest.TestCase):
    """An account answer carries the domain and never a contact."""

    def test_account_lookup_returns_domain(self):
        with _isolated_store():
            _seed_queue([_make_record(
                domain="globex.com",
                contacts=[
                    {"email": "ceo@globex.com", "key": "ceo",
                     "first_name": "Ann"},
                ],
            )])
            result = readback.account_by_domain("globex.com")

        self.assertNotIn("_error", result)
        self.assertEqual(result["domain"], "globex.com")
        self.assertIn("state", result)
        self.assertIn("client_approval", result)
        self.assertIn("campaign_ids", result)
        self.assertIn("last_touch_at", result)
        self.assertIn("replies", result)
        self.assertIn("bounces", result)

    def test_account_not_found(self):
        with _isolated_store():
            _seed_queue([])
            result = readback.account_by_domain("no-such.com")

        self.assertIn("_error", result)

    def test_account_has_no_contact_fields(self):
        """The account answer must not carry email, name, or person fields."""
        from src.notify import STATUS_FORBIDDEN_FIELDS

        with _isolated_store():
            _seed_queue([_make_record(
                domain="example.org",
                contacts=[
                    {"email": "test@example.org", "key": "t",
                     "first_name": "Test", "last_name": "User"},
                ],
            )])
            result = readback.account_by_domain("example.org")

        person_keys = {"email", "address", "recipient", "prospect",
                       "contact_name", "first_name", "last_name",
                       "full_name", "person", "lead_email",
                       "reply_excerpt", "subject", "body", "copy",
                       "linkedin_url", "profile_url", "phone"}
        for key in result:
            self.assertNotIn(
                key.lower(), person_keys,
                f"account answer has forbidden key {key!r}")


# ============================================================== 4. LOG

class LogRecordsWhoAskedAndWhat(unittest.TestCase):
    """The log row records who asked and what was asked."""

    def test_log_contains_user_and_query(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import slack_agent_loop as loop

        with _isolated_store():
            _seed_queue([_make_record(domain="test.com")])

            log_dir = tempfile.mkdtemp()
            log_path = os.path.join(log_dir, "slack-agent.jsonl")
            old_log = loop.LOG
            loop.LOG = log_path
            try:
                event = {
                    "type": "app_mention",
                    "channel": "C123",
                    "channel_type": "channel",
                    "ts": "1234567890.123456",
                    "user": "U999",
                    "text": "is test.com in a campaign",
                }
                seen = set()
                loop.handle(event, seen, dry_run=True)

                with open(log_path, encoding="utf-8") as fh:
                    rows = [json.loads(line) for line in fh if line.strip()]

                question_rows = [r for r in rows if r.get("kind") == "question"]
                self.assertTrue(len(question_rows) >= 1)
                q_row = question_rows[0]
                self.assertEqual(q_row.get("user"), "U999")
                self.assertIn("is test.com in a campaign",
                              q_row.get("text", ""))
            finally:
                loop.LOG = old_log


# ============================================================== 5. ROUTING

class RoutingTests(unittest.TestCase):
    """The new keyword patterns route to the correct query."""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import slack_agent_loop as loop
        self.loop = loop

    def test_is_domain_in_campaign(self):
        q, arg = self.loop.route("is acme.com in a campaign")
        self.assertEqual(q, "account")
        self.assertEqual(arg, "acme.com")

    def test_status_of_email(self):
        q, arg = self.loop.route("status of jane@acme.com")
        self.assertEqual(q, "lead")
        self.assertEqual(arg, "jane@acme.com")

    def test_status_of_linkedin(self):
        q, arg = self.loop.route(
            "status of https://linkedin.com/in/janedoe")
        self.assertEqual(q, "lead")
        self.assertIn("linkedin.com/in/janedoe", arg.lower())

    def test_why_is_domain_held(self):
        q, arg = self.loop.route("why is acme.com held")
        self.assertEqual(q, "held")
        self.assertEqual(arg, "acme.com")

    def test_what_sent_to_domain(self):
        q, arg = self.loop.route("what did we send to acme.com")
        self.assertEqual(q, "sent_to")
        self.assertEqual(arg, "acme.com")

    def test_when_does_campaign_send_next(self):
        q, arg = self.loop.route("when does campaign 487 send next")
        self.assertEqual(q, "send_next")
        self.assertEqual(arg, "487")

    def test_how_many_replies_today(self):
        q, arg = self.loop.route("how many replies today")
        self.assertEqual(q, "replies_today")

    def test_credits_spent_today(self):
        q, arg = self.loop.route("credits spent today")
        self.assertEqual(q, "credits_today")


# ============================================================== 6. READBACK

class ReadbackFunctions(unittest.TestCase):
    """The new readback functions return correct shapes."""

    def test_why_held_returns_expected_keys(self):
        with _isolated_store():
            _seed_queue([_make_record(
                domain="held.com", state="held",
                verdict={"icp_status": "unknown", "icp_confidence": "low"},
            )])
            result = readback.why_held("held.com")

        self.assertNotIn("_error", result)
        self.assertEqual(result["domain"], "held.com")
        self.assertIn("state", result)
        self.assertIn("icp_status", result)
        self.assertIn("mx_decision", result)
        self.assertIn("client_approval", result)

    def test_what_sent_to_returns_events(self):
        with _isolated_store():
            evts = [
                {"type": "push_marked", "contact": "ceo",
                 "channel": "email", "at": "2026-09-20T10:00:00Z",
                 "step": 1, "id": "ev1"},
                {"type": "email_delivered", "contact": "ceo",
                 "channel": "email", "at": "2026-09-20T10:05:00Z",
                 "step": 1, "id": "ev2"},
            ]
            _seed_queue([_make_record(
                domain="sent.com", events_list=evts)])
            result = readback.what_sent_to("sent.com")

        self.assertNotIn("_error", result)
        self.assertEqual(len(result["sent"]), 2)

    def test_replies_today_counts(self):
        import datetime
        today = datetime.date.today().isoformat()
        with _isolated_store():
            evts = [
                {"type": "reply_received", "contact": "ceo",
                 "at": f"{today}T10:00:00Z", "id": "ev1"},
                {"type": "reply_received", "contact": "cto",
                 "at": "2026-01-01T10:00:00Z", "id": "ev2"},
            ]
            _seed_queue([_make_record(domain="r.com", events_list=evts)])
            result = readback.replies_today()

        self.assertEqual(result["replies_today"], 1)

    def test_credits_spent_today_reads_ledger(self):
        import datetime
        today = datetime.date.today().isoformat()
        with _isolated_store():
            _seed_queue([])
            spend_path = os.path.join(
                os.path.dirname(_store.queue_path()), "spend-ledger.jsonl")
            os.makedirs(os.path.dirname(spend_path), exist_ok=True)
            with open(spend_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": f"{today}T10:00:00Z",
                                     "credits": 5}) + "\n")
                fh.write(json.dumps({"at": f"{today}T11:00:00Z",
                                     "credits": 3}) + "\n")
                fh.write(json.dumps({"at": "2026-01-01T10:00:00Z",
                                     "credits": 100}) + "\n")
            result = readback.credits_spent_today()

        self.assertEqual(result["spent_today"], 8)


if __name__ == "__main__":
    unittest.main()
