"""The change-request lifecycle: recognised, confirmed, ticketed, decided.

OPERATOR, 2026-09-21: "Tests for the ticket lifecycle."

The safety property - that the agent cannot execute any of this - is
structural and is asserted in `test_slack_agent_cannot_act.py`. What this
file tests is FIDELITY and the GATE:

- a request is recognised, and a question is not
- a request that cannot be pinned down becomes a question, never a ticket
- nothing is written until the requester confirms, in the same thread
- exactly one Slack id can approve, and an attempt by anybody else is
  recorded rather than dropped
- a decision cannot be applied twice, and an id cannot be guessed at
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import llm, slackconversation as conversation           # noqa: E402
from src import slackrequests as requests, slackscope            # noqa: E402

OPERATOR = "U0OPERATOR1"
CLIENT_USER = "U0CLIENT111"
CLIENT_CHANNEL = "C0CLIENTAAA"
INTERNAL_CHANNEL = "C0INTERNAL1"

ROWS = [{"kind": "workspace", "slug": "alpha", "name": "Alpha",
         "client": "alpha",
         "settings": {"policy": {
             slackscope.AGENT_CHANNEL_KEY: CLIENT_CHANNEL,
             slackscope.WORKSPACE_USERS_KEY: [CLIENT_USER]}}},
        {"kind": "workspace", "slug": "beta", "name": "Beta",
         "client": "beta", "settings": {"policy": {}}}]


class TicketEnvironment(unittest.TestCase):
    """A throwaway ticket directory, queue and workspace store."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-tickets-")
        self._prev = {}
        for key, value in (
                ("QUEUE", os.path.join(self.tmp, "queue.jsonl")),
                ("WORKSPACES", os.path.join(self.tmp, "workspaces.jsonl")),
                (requests.REQUESTS_DIR_VAR,
                 os.path.join(self.tmp, "requests")),
                (slackscope.INTERNAL_CHANNELS_VAR, INTERNAL_CHANNEL),
                (slackscope.OPERATOR_USER_VAR, OPERATOR),
                (slackscope.STATUS_CHANNEL_VAR, ""),
                (slackscope.OPS_CHANNEL_VAR, "")):
            self._prev[key] = os.environ.get(key)
            if value == "":
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._threads = conversation.THREADS
        conversation.THREADS = os.path.join(self.tmp, "threads.jsonl")
        from src import campaigns, store, workspaces as ws
        ws.save(ROWS)
        # ALPHA NEEDS AN ESTATE. `check_ownership` refuses a request whose
        # target is not in the requesting workspace, so a fixture with no
        # records would refuse every request and this whole file would be
        # testing the refusal instead of the lifecycle.
        store.save([
            {"id": "alpha-1", "domain": "acme.test", "client": "alpha",
             "state": "approved", "icp": {"verdict": "in"},
             "contacts": [{"email": "ada@acme.test", "name": "Ada",
                           "key": "ada", "sendable": True,
                           "verdict": "valid"}]},
        ])
        campaigns.save([
            {"kind": "campaign", "campaign_id": "alpha-c1",
             "client": "alpha", "name": "Alpha cohort", "status": "approved",
             "bison_campaign_id": 9001, "record_ids": ["alpha-1"]},
        ])

    def tearDown(self):
        conversation.THREADS = self._threads
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def say(self, text, channel=CLIENT_CHANNEL, user=CLIENT_USER,
            thread="T1"):
        return conversation.respond(text, channel=channel, user=user,
                                    thread_ts=thread, model=llm.NoModel())


# ============================================================ RECOGNITION

class TheSixKindsAreRecognised(TicketEnvironment):

    CASES = (
        ("remove lead ada@acme.test from campaign 9001", "remove_lead"),
        ("please stop contacting globex.test", "stop_account"),
        ("change the connection message of cadence li_v1 to \"new text "
         "goes here\"", "change_copy"),
        ("pause campaign 489", "pause_campaign"),
        ("add a lead: barbara@globex.test", "add_lead"),
        ("change the sending window to 08:00-16:00", "change_window"),
    )

    def test_each_kind_is_recognised(self):
        for text, kind in self.CASES:
            found, _fields = requests.recognise(text)
            self.assertEqual(found, kind, text)

    def test_a_question_is_not_a_change_request(self):
        for text in ("how many campaigns are approved?",
                     "what went out this week?",
                     "which cadence is active?",
                     "why did we pause 487?",
                     "how many leads were removed?",
                     "what is the sending window?"):
            kind, _fields = requests.recognise(text)
            self.assertIsNone(kind, text)

    def test_copy_wins_over_account_when_a_message_names_both(self):
        """"change the connection message for acme.test" is a COPY change
        that happens to name a domain, not a request to stop contacting
        them. Getting that backwards would suppress an account somebody
        wanted to keep writing to."""
        kind, _fields = requests.recognise(
            "change the connection message for acme.test to \"hello\"")
        self.assertEqual(kind, "change_copy")

    def test_the_target_is_extracted(self):
        _kind, fields = requests.recognise(
            "remove lead ada@acme.test from campaign 9001")
        self.assertEqual(fields["lead"], "ada@acme.test")
        self.assertEqual(fields["campaign"], "9001")

    def test_a_connection_message_is_understood_as_a_step(self):
        _kind, fields = requests.recognise(
            "change the connection message of cadence li_v1 to \"hi\"")
        self.assertEqual(fields["step"], "linkedin connection request")
        self.assertEqual(fields["cadence_or_campaign"], "li_v1")


# ======================================================== THE TWO TURNS

class NothingIsWrittenBeforeItIsConfirmed(TicketEnvironment):

    def test_the_first_turn_restates_and_writes_nothing(self):
        result = self.say("remove lead ada@acme.test")
        self.assertEqual(result["how"], "request_restated")
        self.assertEqual(requests.load(), [])
        self.assertFalse(os.path.isdir(requests.requests_dir())
                         and os.listdir(requests.requests_dir()))

    def test_the_restatement_says_what_would_happen(self):
        result = self.say("remove lead ada@acme.test")
        self.assertIn("suppression", result["reply"].lower())
        self.assertIn("both channels", result["reply"].lower())
        self.assertIn("approve", result["reply"].lower())

    def test_confirming_writes_the_ticket(self):
        self.say("remove lead ada@acme.test")
        result = self.say("yes")
        self.assertEqual(result["how"], "request_raised")
        self.assertTrue(result["ticket"])
        self.assertTrue(os.path.isfile(result["ticket_path"]))
        self.assertEqual(len(requests.pending()), 1)

    def test_the_ticket_records_who_asked_and_from_where(self):
        self.say("remove lead ada@acme.test")
        ticket = requests.get(self.say("yes")["ticket"])
        self.assertEqual(ticket["requester"], CLIENT_USER)
        self.assertEqual(ticket["workspace"], "alpha")
        self.assertEqual(ticket["channel"], CLIENT_CHANNEL)
        self.assertEqual(ticket["requester_scope"], "client")
        self.assertEqual(ticket["status"], requests.AWAITING)

    def test_the_ticket_file_carries_the_original_words(self):
        self.say("remove lead ada@acme.test because they asked us to")
        ticket = requests.get(self.say("yes")["ticket"])
        with open(requests.path_for(ticket), encoding="utf-8") as handle:
            body = handle.read()
        self.assertIn("because they asked us to", body)
        self.assertIn("ada@acme.test", body)

    def test_a_yes_with_no_open_request_is_not_a_confirmation(self):
        result = self.say("yes")
        self.assertNotEqual(result["how"], "request_raised")
        self.assertEqual(requests.load(), [])

    def test_declining_drops_it(self):
        self.say("remove lead ada@acme.test")
        result = self.say("no, forget it")
        self.assertEqual(result["how"], "request_withdrawn")
        self.assertEqual(requests.load(), [])

    def test_confirming_twice_raises_one_ticket(self):
        """The restatement is CLEARED when it is raised.

        Added after a mutation run: disabling the `pending_cleared` branch
        broke nothing, because every test confirmed exactly once. A second
        "yes" in the same thread would have raised a second identical
        ticket, and the operator would have had two approvals to make for
        one request.
        """
        self.say("remove lead ada@acme.test")
        first = self.say("yes")
        second = self.say("yes")
        self.assertEqual(first["how"], "request_raised")
        self.assertNotEqual(second["how"], "request_raised")
        self.assertEqual(len(requests.load()), 1)

    def test_a_stale_restatement_is_not_confirmable(self):
        """A yes an hour later is a yes to something nobody remembers."""
        self.say("remove lead ada@acme.test")
        rows = conversation.history(CLIENT_CHANNEL, "T1", limit=40)
        pending = [r for r in rows
                   if r.get("role") == conversation.PENDING_ROLE]
        self.assertTrue(pending)
        pending[-1]["epoch"] = 0
        with open(conversation.THREADS, "a", encoding="utf-8") as handle:
            import json
            handle.write(json.dumps(pending[-1]) + chr(10))
        self.assertIsNone(
            conversation.pending_request(CLIENT_CHANNEL, "T1"))

    def test_a_confirmation_cannot_cross_threads(self):
        """A yes in another thread is a yes to nothing."""
        self.say("remove lead ada@acme.test", thread="T1")
        result = self.say("yes", thread="T2")
        self.assertNotEqual(result["how"], "request_raised")
        self.assertEqual(requests.load(), [])

    def test_a_second_request_replaces_the_first_pending_one(self):
        self.say("remove lead ada@acme.test")
        self.say("pause campaign 9001")
        ticket = requests.get(self.say("yes")["ticket"])
        self.assertEqual(ticket["kind"], "pause_campaign")


class AVagueRequestBecomesAQuestion(TicketEnvironment):

    def test_a_request_with_no_target_asks_for_one(self):
        result = self.say("please remove that lead")
        self.assertEqual(result["how"], "request_needs_detail")
        self.assertIn("email address", result["reply"])
        self.assertEqual(requests.load(), [])

    def test_a_copy_change_with_no_wording_asks_for_it(self):
        result = self.say("change the step 2 copy on cadence li_v1")
        self.assertEqual(result["how"], "request_needs_detail")
        self.assertIn("new wording", result["reply"])

    def test_confirming_a_question_writes_nothing(self):
        self.say("please remove that lead")
        result = self.say("yes")
        self.assertNotEqual(result["how"], "request_raised")
        self.assertEqual(requests.load(), [])


# ============================================================== THE GATE

class OnlyTheOperatorDecides(TicketEnvironment):

    def raise_one(self):
        self.say("remove lead ada@acme.test")
        return self.say("yes")["ticket"]

    def decide(self, text, user, channel=INTERNAL_CHANNEL):
        return conversation.respond(text, channel=channel, user=user,
                                    model=llm.NoModel())

    def test_the_operator_can_approve(self):
        ticket_id = self.raise_one()
        result = self.decide("approve %s" % ticket_id, OPERATOR)
        self.assertEqual(result["how"], "decided")
        self.assertEqual(requests.get(ticket_id)["status"],
                         requests.APPROVED)

    def test_somebody_else_in_the_internal_channel_cannot(self):
        ticket_id = self.raise_one()
        result = self.decide("approve %s" % ticket_id, "U0SOMEBODYELSE")
        self.assertEqual(result["how"], "decision_refused")
        self.assertEqual(requests.get(ticket_id)["status"],
                         requests.AWAITING)

    def test_a_refused_attempt_is_recorded_on_the_ticket(self):
        """Somebody trying to approve their own request is exactly what the
        person reading this later needs to see."""
        ticket_id = self.raise_one()
        self.decide("approve %s" % ticket_id, "U0SOMEBODYELSE")
        path = requests.queue_path()
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
        self.assertIn("decision_attempt_by", body)
        self.assertIn("U0SOMEBODYELSE", body)

    def test_the_requester_cannot_approve_their_own_request(self):
        ticket_id = self.raise_one()
        result = self.decide("approve %s" % ticket_id, CLIENT_USER,
                             channel=CLIENT_CHANNEL)
        self.assertEqual(result["how"], "refused")
        self.assertEqual(requests.get(ticket_id)["status"],
                         requests.AWAITING)

    def test_approving_in_a_client_channel_is_refused_even_by_the_operator(
            self):
        """An approval belongs where the operator's decisions are recorded,
        not in the room the request came from."""
        ticket_id = self.raise_one()
        result = self.decide("approve %s" % ticket_id, OPERATOR,
                             channel=CLIENT_CHANNEL)
        self.assertEqual(result["how"], "refused")
        self.assertEqual(requests.get(ticket_id)["status"],
                         requests.AWAITING)

    def test_with_no_operator_configured_nobody_can_approve(self):
        ticket_id = self.raise_one()
        os.environ.pop(slackscope.OPERATOR_USER_VAR, None)
        result = self.decide("approve %s" % ticket_id, OPERATOR)
        self.assertEqual(result["how"], "decision_refused")
        self.assertEqual(requests.get(ticket_id)["status"],
                         requests.AWAITING)

    def test_a_decision_cannot_be_applied_twice(self):
        ticket_id = self.raise_one()
        self.decide("approve %s" % ticket_id, OPERATOR)
        result = self.decide("approve %s" % ticket_id, OPERATOR)
        self.assertEqual(result["how"], "decision_stale")

    def test_an_unknown_id_is_not_guessed_at(self):
        result = self.decide("approve 2026-01-01-ffff", OPERATOR)
        self.assertEqual(result["how"], "decision_unknown")

    def test_a_ticket_id_is_not_split_at_its_hyphens(self):
        """`approve 2026-09-21-7008` names ONE ticket.

        The first parser used `(\\S+?)` and let a hyphen end the id, so it
        read that as ticket `2026` with the note "09-21-7008" - and every
        id this module generates has three hyphens in it.
        """
        parsed = requests.parse_decision("approve 2026-09-21-7008")
        self.assertEqual(parsed, ("approve", "2026-09-21-7008", None))

    def test_a_note_after_a_spaced_dash_is_a_note(self):
        parsed = requests.parse_decision(
            "reject `2026-09-21-7008` - wrong person")
        self.assertEqual(parsed[1], "2026-09-21-7008")
        self.assertEqual(parsed[2], "wrong person")

    def test_approve_without_a_well_formed_id_is_not_a_decision(self):
        for text in ("approve the batch", "approve it", "approve 489",
                     "please approve"):
            self.assertIsNone(requests.parse_decision(text), text)


# ============================================================== REPORTING

class TheOutcomeGoesBackToTheThreadItCameFrom(TicketEnvironment):

    def raise_and_approve(self):
        self.say("remove lead ada@acme.test", thread="T-ORIGINAL")
        ticket_id = self.say("yes", thread="T-ORIGINAL")["ticket"]
        result = conversation.respond("approve %s" % ticket_id,
                                      channel=INTERNAL_CHANNEL,
                                      user=OPERATOR, model=llm.NoModel())
        return ticket_id, result

    def test_the_decision_names_the_original_thread(self):
        _ticket_id, result = self.raise_and_approve()
        note = result["post_to_thread"]
        self.assertEqual(note["channel"], CLIENT_CHANNEL)
        self.assertEqual(note["thread_ts"], "T-ORIGINAL")

    def test_a_rejection_is_reported_too(self):
        self.say("remove lead ada@acme.test", thread="T-ORIGINAL")
        ticket_id = self.say("yes", thread="T-ORIGINAL")["ticket"]
        result = conversation.respond(
            "reject %s - we still want them" % ticket_id,
            channel=INTERNAL_CHANNEL, user=OPERATOR, model=llm.NoModel())
        text = result["post_to_thread"]["text"]
        self.assertIn("not approved", text)
        self.assertIn("we still want them", text)

    def test_the_action_required_post_carries_the_id_and_both_verbs(self):
        self.say("remove lead ada@acme.test")
        result = self.say("yes")
        announcement = result["post_to_internal"]
        self.assertIn("ACTION REQUIRED", announcement)
        self.assertIn("approve %s" % result["ticket"], announcement)
        self.assertIn("reject %s" % result["ticket"], announcement)

    def test_an_executed_outcome_reaches_the_requester(self):
        ticket_id, _result = self.raise_and_approve()
        requests.record_outcome(
            ticket_id, "Suppressed and stopped on both channels; the "
                       "provider readback confirms it.")
        ticket = requests.get(ticket_id)
        self.assertEqual(ticket["status"], requests.EXECUTED)
        self.assertIn("provider readback",
                      requests.decision_note_for(ticket))

    def test_the_approved_queue_empties_when_it_is_executed(self):
        ticket_id, _result = self.raise_and_approve()
        self.assertEqual(len(requests.approved_unexecuted()), 1)
        requests.record_outcome(ticket_id, "done, readback confirms")
        self.assertEqual(requests.approved_unexecuted(), [])


class TheTicketFileAndTheJournalAgree(TicketEnvironment):

    def test_both_are_written_together(self):
        self.say("pause campaign 9001")
        ticket_id = self.say("yes")["ticket"]
        ticket = requests.get(ticket_id)
        self.assertTrue(os.path.isfile(requests.path_for(ticket)))

    def test_the_latest_journal_row_wins(self):
        self.say("pause campaign 9001")
        ticket_id = self.say("yes")["ticket"]
        requests.decide(ticket_id, "approve", OPERATOR)
        requests.record_outcome(ticket_id, "paused, provider agrees")
        rows = [r for r in requests.load() if r["id"] == ticket_id]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], requests.EXECUTED)

    def test_a_corrupt_journal_line_does_not_lose_the_queue(self):
        self.say("pause campaign 9001")
        ticket_id = self.say("yes")["ticket"]
        with open(requests.queue_path(), "a", encoding="utf-8") as handle:
            handle.write("{not json\n")
        self.assertEqual([r["id"] for r in requests.load()], [ticket_id])


if __name__ == "__main__":
    unittest.main()
