"""Meetings booked: a ledger fed by hand, because nothing else holds it.

`docs/SLACK-AGENT-QUESTION-CATALOGUE.md` names it first on the build list —
93 questions about replies and meetings, and *meetings booked is the single
most-asked number the agent cannot produce. It is the number the commercial
relationship runs on.*

OPERATOR, 2026-09-22: `@Resonate OS meeting booked <domain> <date>`
(optionally `with <role>`), internal users only, source tagged, counts in
the digest / weekly plan / client answers, per-domain detail only
internally or in that client's channel. *Add a second source later; never
merge sources silently.*

Four properties, and each is a way the number could quietly become wrong:

1. **A question never writes a row.** "how many meetings booked this week"
   is the far more common message, and it arrives in the same words.
2. **Only a Resonate person feeds it** — the person, not only the room. The
   number the contract is measured by is not one the other party writes.
3. **A row is never filed against a guessed client**, and a duplicate is
   refused rather than counted twice.
4. **Sources never merge**, and that is enforced by the return type rather
   than by anybody remembering it.
"""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackconversation as conversation                # noqa: E402
from src import slackagenttools as tools                         # noqa: E402
from src import slackmeetings as meetings, slackscope            # noqa: E402

INTERNAL_CHANNEL = "C0INTERNALX"
OPERATOR = "U0OPERATORX"
OUTSIDER = "U0CLIENTAAA"


def internal():
    return slackscope.Scope(slackscope.INTERNAL, source="test")


def client(workspace="alpha"):
    return slackscope.Scope(slackscope.CLIENT, workspace=workspace,
                            source="test")


class Ledger(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-meetings-")
        self._prev = {}
        for key, value in (
                (meetings.JOURNAL_VAR, os.path.join(self.tmp, "m.jsonl")),
                (slackscope.INTERNAL_CHANNELS_VAR, INTERNAL_CHANNEL),
                (slackscope.OPERATOR_USER_VAR, OPERATOR)):
            self._prev[key] = os.environ.get(key)
            os.environ[key] = value

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def add(self, domain="acme.test", date="2026-09-24", workspace="alpha",
            by=OPERATOR, source=meetings.MANUAL, role=None):
        return meetings.record(workspace=workspace, domain=domain,
                               date=date, recorded_by=by, with_role=role,
                               source=source)


# ================================ 1. A QUESTION NEVER WRITES A ROW

class AskingIsNotRecording(Ledger):

    def test_the_questions_people_actually_ask_record_nothing(self):
        for asked in ("how many meetings booked this week?",
                      "koliko meetinga booked imamo?",
                      "any meetings booked for acme.test 2026-09-24?",
                      "what meetings booked acme.test 24.09.2026",
                      "show meetings booked acme.test 2026-09-24"):
            self.assertIsNone(meetings.parse(asked), asked)

    def test_the_instruction_is_recognised(self):
        found = meetings.parse(
            "<@U0BOT> meeting booked acme.test 2026-09-24 with CFO")
        self.assertEqual(found["domain"], "acme.test")
        self.assertEqual(found["date"], "2026-09-24")
        self.assertEqual(found["with_role"], "CFO")

    def test_a_message_that_merely_mentions_a_meeting_is_not_one(self):
        for text in ("we talked about the meeting yesterday",
                     "meeting booked",
                     "meeting booked acme.test",
                     "booked the room for a meeting"):
            self.assertIsNone(meetings.parse(text), text)

    def test_a_date_it_cannot_read_records_nothing_rather_than_guessing(self):
        self.assertIsNone(meetings.parse(
            "meeting booked acme.test sometime next week"))
        self.assertIsNone(meetings.parse(
            "meeting booked acme.test 99.99.2026"))


# ================================ 2. THE PERSON, NOT ONLY THE ROOM

class OnlyAResonatePersonFeedsIt(Ledger):

    def respond(self, text, user, channel=INTERNAL_CHANNEL,
                channel_type=None):
        return conversation.respond(text, channel=channel, user=user,
                                    channel_type=channel_type,
                                    thread_ts="T1", rows=[])

    def test_an_outsider_in_an_internal_channel_cannot_record(self):
        """`scope.is_internal` is true for anybody speaking in one of our
        rooms. The ledger asks who is speaking."""
        out = self.respond("meeting booked acme.test 2026-09-24", OUTSIDER)
        self.assertEqual(out["how"], "refused")
        self.assertEqual(meetings.load(), [])

    def test_a_client_channel_cannot_reach_it_at_all(self):
        out = self.respond("meeting booked acme.test 2026-09-24", OPERATOR,
                           channel="C0SOMEWHEREELSE")
        self.assertEqual(out["how"], "refused")
        self.assertEqual(meetings.load(), [])

    def test_the_refusal_says_so_rather_than_going_quiet(self):
        out = self.respond("meeting booked acme.test 2026-09-24", OUTSIDER)
        self.assertIn("Nothing was recorded", out["reply"])

    def test_an_internal_person_records(self):
        with mock.patch.object(meetings, "workspace_for_domain",
                               lambda d: ("alpha", None)):
            out = self.respond("meeting booked acme.test 2026-09-24",
                               OPERATOR)
        self.assertEqual(out["how"], "meeting_recorded")
        rows = meetings.load()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["workspace"], "alpha")
        self.assertEqual(rows[0]["recorded_by"], OPERATOR)
        self.assertEqual(rows[0]["source"], meetings.MANUAL)


# ================================ 3. NEVER A GUESSED CLIENT, NEVER TWICE

class AttributionIsRefusedRatherThanGuessed(Ledger):

    def test_an_unknown_domain_records_nothing_and_says_what_to_type(self):
        with mock.patch.object(meetings, "workspace_for_domain",
                               lambda d: (None, "no client of ours has it")):
            out = conversation.respond(
                "meeting booked stranger.test 2026-09-24",
                channel=INTERNAL_CHANNEL, user=OPERATOR, thread_ts="T1",
                rows=[])
        self.assertEqual(out["how"], "meeting_unattributed")
        self.assertIn("for <workspace>", out["reply"])
        self.assertEqual(meetings.load(), [])

    def test_an_ambiguous_domain_refuses_rather_than_choosing(self):
        rows = [{"domain": "shared.test", "client": "alpha"},
                {"domain": "shared.test", "client": "beta"}]
        with mock.patch("src.store.load", lambda *a, **k: rows):
            slug, why = meetings.workspace_for_domain("shared.test")
        self.assertIsNone(slug)
        self.assertIn("more than one client", why)

    def test_a_domain_only_one_client_holds_resolves(self):
        rows = [{"domain": "shared.test", "client": "alpha"},
                {"domain": "other.test", "client": "beta"}]
        with mock.patch("src.store.load", lambda *a, **k: rows):
            self.assertEqual(meetings.workspace_for_domain("shared.test"),
                             ("alpha", None))

    def test_a_record_with_no_client_never_attributes_a_meeting(self):
        rows = [{"domain": "shared.test"}]
        with mock.patch("src.store.load", lambda *a, **k: rows):
            slug, why = meetings.workspace_for_domain("shared.test")
        self.assertIsNone(slug)
        self.assertIn("no client of ours", why)

    def test_a_named_workspace_is_accepted_when_the_domain_cannot_say(self):
        with mock.patch.object(meetings, "_known_slugs",
                               lambda: {"alpha", "beta"}):
            out = conversation.respond(
                "meeting booked stranger.test 2026-09-24 for alpha",
                channel=INTERNAL_CHANNEL, user=OPERATOR, thread_ts="T1",
                rows=[])
        self.assertEqual(out["how"], "meeting_recorded")
        self.assertEqual(meetings.load()[0]["workspace"], "alpha")

    def test_for_is_only_a_workspace_when_it_names_one(self):
        """"with the head of ops for EMEA" is a role containing the word."""
        found = meetings.parse(
            "meeting booked acme.test today with the head of ops for EMEA",
            slugs=["alpha"])
        self.assertIsNone(found["workspace"])
        self.assertEqual(found["with_role"], "the head of ops for EMEA")

    def test_the_same_meeting_twice_is_refused_and_names_the_first_row(self):
        first = self.add()
        with self.assertRaises(meetings.MeetingRefused) as caught:
            self.add()
        self.assertIn(first["id"], str(caught.exception))
        self.assertEqual(len(meetings.recorded()), 1)

    def test_a_different_date_for_the_same_account_is_a_second_meeting(self):
        self.add(date="2026-09-24")
        self.add(date="2026-10-01")
        self.assertEqual(len(meetings.recorded()), 2)


# ================================ 4. SOURCES NEVER MERGE

class TheReturnTypeIsTheRule(Ledger):

    def test_the_count_is_per_source_and_there_is_no_bare_number(self):
        self.add(domain="a.test")
        self.add(domain="b.test")
        self.add(domain="c.test", source="calendly")
        self.assertEqual(meetings.counts(),
                         {meetings.MANUAL: 2, "calendly": 1})

    def test_a_total_always_says_which_sources_it_spans(self):
        self.add(domain="a.test")
        self.add(domain="c.test", source="calendly")
        total = meetings.total_across(meetings.counts())
        self.assertEqual(total["meetings"], 2)
        self.assertEqual(total["sources"], ["calendly", meetings.MANUAL])
        self.assertIn("not one system's number", total["note"])

    def test_an_empty_ledger_says_it_is_empty_rather_than_zero_meetings(self):
        total = meetings.total_across(meetings.counts())
        self.assertEqual(total["meetings"], 0)
        self.assertIn("no meeting is recorded", total["note"])


# ================================ 5. WHAT EACH CHANNEL IS SHOWN

class DetailIsScopedAndTheCountIsNot(Ledger):

    def setUp(self):
        super().setUp()
        self.add(domain="alpha-one.test", workspace="alpha")
        self.add(domain="alpha-two.test", workspace="alpha")
        self.add(domain="beta-one.test", workspace="beta")

    def test_a_client_sees_its_own_rows_and_only_its_own(self):
        out = tools.meetings_booked(client("alpha"))
        domains = {r["domain"] for r in out["meetings"]}
        self.assertEqual(domains, {"alpha-one.test", "alpha-two.test"})
        self.assertEqual(len(out["meetings"]), 2)
        self.assertEqual(out["workspace"], "alpha")
        self.assertEqual(out["meetings"], sorted(
            out["meetings"], key=lambda r: (r["date"], r["domain"])))

    def test_a_client_can_never_reach_another_clients_rows(self):
        """The workspace comes from the SCOPE. There is no argument that
        reaches another client's."""
        for phrasing in ("beta", "all", "beta-one.test", None):
            out = tools.meetings_booked(client("alpha"), phrasing)
            self.assertNotIn("beta-one.test",
                             {r["domain"] for r in out["meetings"]})

    def test_an_internal_channel_sees_everything_grouped(self):
        out = tools.meetings_booked(internal())
        self.assertEqual(out["by_workspace"], {"alpha": 2, "beta": 1})
        self.assertEqual(len(out["meetings"]), 3)

    def test_the_answer_says_it_is_a_hand_fed_ledger(self):
        """An absent meeting is an unrecorded one, not a meeting that did
        not happen, and the reader has to be told which claim this is."""
        out = tools.meetings_booked(client("alpha"))
        self.assertIn("unrecorded", out["meetings_note"])

    def test_it_is_on_the_tool_list_for_both_scopes(self):
        self.assertIn("meetings_booked", tools.for_scope(client()))
        self.assertIn("meetings_booked", tools.for_scope(internal()))

    def test_the_weekly_plan_carries_the_count(self):
        plan = tools._meetings_for_plan(client("alpha"))
        self.assertEqual(plan["by_source"], {meetings.MANUAL: 2})
        self.assertIn("sources", plan)


if __name__ == "__main__":
    unittest.main()
