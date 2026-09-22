"""The six faults in the first live client answer, each with its test.

OPERATOR, 2026-09-22, after one reply went out in a real client channel.
The reply is worth quoting because every fault in it is visible:

    "Da, prvi mailovi su prošli: ... 3 poslana maila iz US-hours kontrolne
     kampanje ... prvi u 13:03 i drugi u 13:55 (UTC) ... lokalno je upisano
     724 leada na 643 računa ... pa to provjeravam s timom. Želite li da
     vam pošaljem kratki update?"

    1 the enrolled figure was the LOCAL store's, not the provider's
    2 the times were UTC, to a Zagreb client
    3 two promises with no mechanism behind either
    4 "US-hours control campaign" is our experiment design
    5 the question was banter and got a paragraph of counters
    6 "the first emails have gone out" was false of the batch asked about

Four of those are the same fault: **the material handed to the model was
internal material**, and the model wrote it down faithfully. None is
fixable by telling the model to behave, so each is fixed in the readback
and tested here.
"""
import datetime
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackclientview as clientview                    # noqa: E402
from src import slackconversation as conversation                # noqa: E402
from src import slackfollowup as followup, slackscope            # noqa: E402


# ============================================ 1. THE ENROLLED FIGURE

class EnrolledIsTheProvidersOrItIsAbsent(unittest.TestCase):
    """`724 leads on 643 accounts` was the local store's enrolled state
    across everything ever staged. The batch asked about held 393, which
    is what the provider's own membership count says."""

    def test_the_local_keys_are_removed_not_corrected_alongside(self):
        """A readback carrying both invites an answer carrying both."""
        import src.slackagenttools as tools

        scope = slackscope.Scope(slackscope.CLIENT, workspace="alpha",
                                 source="test")
        source = {"leads_enrolled_locally": 724, "accounts": 643,
                  "bound_to_provider": []}
        original = tools.readback.batch_state
        tools.readback.batch_state = lambda *a, **k: dict(source)
        counted = tools.provider_enrolled
        tools.provider_enrolled = lambda *a, **k: {
            "total": 393, "per_campaign": {"491": 34}, "unreadable": 0,
            "sent_per_campaign": {"491": 0}, "sent_total": 0}
        try:
            state = tools.batch_state(scope)
        finally:
            tools.readback.batch_state = original
            tools.provider_enrolled = counted
        self.assertNotIn("leads_enrolled_locally", state)
        self.assertNotIn("accounts", state)
        self.assertEqual(state["enrolled_confirmed_by_provider"], 393)
        self.assertEqual(json.dumps(state).count("724"), 0)

    def test_an_internal_channel_still_sees_the_local_figure(self):
        """The local number is not wrong, it answers a different question,
        and internally that question is sometimes the one being asked."""
        import src.slackagenttools as tools

        scope = slackscope.Scope(slackscope.INTERNAL, source="test")
        original = tools.readback.batch_state
        tools.readback.batch_state = lambda *a, **k: {
            "leads_enrolled_locally": 724}
        try:
            state = tools.batch_state(scope)
        finally:
            tools.readback.batch_state = original
        self.assertEqual(state["leads_enrolled_locally"], 724)

    def test_sent_travels_with_enrolled(self):
        """"Enrolled is not sent" is only checkable if both are present."""
        import src.slackagenttools as tools

        scope = slackscope.Scope(slackscope.CLIENT, workspace="alpha",
                                 source="test")
        original = tools.readback.batch_state
        counted = tools.provider_enrolled
        tools.readback.batch_state = lambda *a, **k: {
            "bound_to_provider": ["491"]}
        tools.provider_enrolled = lambda *a, **k: {
            "total": 393, "per_campaign": {"491": 393}, "unreadable": 0,
            "sent_per_campaign": {"491": 0}, "sent_total": 0}
        try:
            state = tools.batch_state(scope)
        finally:
            tools.readback.batch_state = original
            tools.provider_enrolled = counted
        self.assertEqual(state["sent_from_these_campaigns"], 0)
        self.assertIn("sent_per_campaign", state)


# ================================================= 2. LOCAL TIME

class TimesToAClientAreInTheirZoneAndNameIt(unittest.TestCase):

    def test_a_utc_stamp_becomes_zagreb_time_with_the_zone(self):
        out = clientview.in_zone("2026-09-22T13:03:00Z", "Europe/Zagreb")
        self.assertIn("15:03", out)
        self.assertIn("CEST", out)

    def test_the_zone_moves_with_the_calendar(self):
        winter = clientview.in_zone("2026-12-01T13:00:00Z", "Europe/Zagreb")
        self.assertIn("14:00", winter)
        self.assertIn("CET", winter)

    def test_every_nested_timestamp_is_converted(self):
        source = {"read_at": "2026-09-22T13:03:00Z",
                  "rows": [{"sent_at": "2026-09-22T13:55:00Z"}]}
        out = clientview.localise(source, "Europe/Zagreb")
        self.assertIn("15:03", out["read_at"])
        self.assertIn("15:55", out["rows"][0]["sent_at"])

    def test_a_workspace_with_no_zone_is_left_in_utc(self):
        """No zone configured is not a licence to guess one."""
        source = {"read_at": "2026-09-22T13:03:00Z"}
        self.assertEqual(clientview.localise(source, None), source)

    def test_the_zone_comes_from_the_workspaces_own_sending_window(self):
        entry = {"sending": {"timezone": "Europe/Zagreb"}}
        self.assertEqual(clientview.zone_for(entry), "Europe/Zagreb")
        self.assertIsNone(clientview.zone_for({"sending": {}}))

    def test_something_that_is_not_a_time_is_untouched(self):
        self.assertEqual(clientview.in_zone("491", "Europe/Zagreb"), "491")


# ============================================ 4. NO INTERNAL FRAMING

class OurExperimentDesignIsNotTheirCampaignName(unittest.TestCase):

    NAME = "RESONATE - PRODUCTIVE - EMAIL - US-HOURS - CONTROL - COHORT B"

    def test_the_internal_words_are_recognised(self):
        self.assertTrue(clientview.carries_internal_label(self.NAME))
        self.assertTrue(clientview.carries_internal_label("canary run"))
        self.assertFalse(clientview.carries_internal_label("Acme outreach"))

    def test_the_channel_and_the_id_survive_and_nothing_else(self):
        plain = clientview.plain_campaign_label(self.NAME, "491")
        self.assertEqual(plain, "email campaign 491")
        for word in ("US-HOURS", "CONTROL", "COHORT", "RESONATE"):
            self.assertNotIn(word, plain)

    def test_a_linkedin_campaign_keeps_its_channel(self):
        self.assertIn("LinkedIn", clientview.plain_campaign_label(
            "RESONATE - LI - CONTROL", "605732"))


# ===================================== 3. NO PROMISE WITHOUT A MECHANISM

class TheOnlyOfferIsOneItCanKeep(unittest.TestCase):
    """And "can keep" now includes "something is running".

    The offer shipped with `slackfollowup.register()` wired in and
    `slackfollowup.due()` read by no process at all - so a client said yes,
    a row was written, and the silence that the module exists to prevent
    followed anyway. These tests stand up a heartbeat for the deliverer
    because the agent will not make the offer without one.
    """

    def setUp(self):
        import json
        import tempfile
        import time
        self.tmp = tempfile.mkdtemp(prefix="rga-fu-beat-")
        self.beat = os.path.join(self.tmp, "slack-followup.json")
        self._prev = os.environ.get(followup.HEARTBEAT_VAR)
        os.environ[followup.HEARTBEAT_VAR] = self.beat
        with open(self.beat, "w", encoding="utf-8") as handle:
            json.dump({"watcher": followup.WATCHER,
                       "epoch": int(time.time())}, handle)

    def tearDown(self):
        import shutil
        if self._prev is None:
            os.environ.pop(followup.HEARTBEAT_VAR, None)
        else:
            os.environ[followup.HEARTBEAT_VAR] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_client_tone_forbids_the_phrases_that_went_out(self):
        tone = conversation.TONE[slackscope.CLIENT].lower()
        self.assertIn("promise nothing you cannot keep", tone)
        for banned in ("i will check with the team", "i will get back to you",
                       "want me to send you an update"):
            self.assertIn(banned, tone)

    def test_the_offer_is_only_available_when_nothing_has_sent(self):
        """Offering to announce a first send that already happened is not
        an offer."""
        scope = slackscope.Scope(slackscope.CLIENT, workspace="alpha",
                                 source="test")
        nothing_sent = [("batch_state", None,
                         {"sent_per_campaign": {"491": 0, "492": 0}})]
        already_sent = [("batch_state", None,
                         {"sent_per_campaign": {"491": 3}})]
        self.assertIsNotNone(
            conversation.offer_is_available(scope, nothing_sent))
        self.assertIsNone(
            conversation.offer_is_available(scope, already_sent))

    def test_an_internal_channel_is_never_offered_it(self):
        scope = slackscope.Scope(slackscope.INTERNAL, source="test")
        self.assertIsNone(conversation.offer_is_available(
            scope, [("batch_state", None, {"sent_per_campaign": {"1": 0}})]))

    def test_the_offer_carries_the_baseline_the_watch_needs(self):
        scope = slackscope.Scope(slackscope.CLIENT, workspace="alpha",
                                 source="test")
        offer = conversation.offer_is_available(
            scope, [("batch_state", None,
                     {"sent_per_campaign": {"491": 0, "492": 0}})])
        self.assertEqual(offer["baseline"], {"491": 0, "492": 0})
        self.assertEqual(offer["campaign_ids"], ["491", "492"])

    def test_a_cold_deliverer_withdraws_the_offer_entirely(self):
        """The one check that makes "build the mechanism" stick.

        With nothing beating there is no process to fire the watch, so the
        sentence is not available - not softened, not hedged, absent. This
        is what a committed-but-unstarted `slack_followup_loop.py` looks
        like from the client's side: the agent simply does not offer.
        """
        import json
        import time
        scope = slackscope.Scope(slackscope.CLIENT, workspace="alpha",
                                 source="test")
        material = [("batch_state", None, {"sent_per_campaign": {"491": 0}})]
        self.assertIsNotNone(conversation.offer_is_available(scope, material))

        with open(self.beat, "w", encoding="utf-8") as handle:
            json.dump({"watcher": followup.WATCHER,
                       "epoch": int(time.time())
                       - followup.MAX_BEAT_AGE_SECONDS - 1}, handle)
        self.assertIsNone(conversation.offer_is_available(scope, material))

        os.remove(self.beat)
        self.assertIsNone(conversation.offer_is_available(scope, material))
        self.assertFalse(followup.deliverer_is_running())

    def test_an_unreadable_beat_is_not_given_the_benefit_of_the_doubt(self):
        with open(self.beat, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertFalse(followup.deliverer_is_running())

    def test_a_yes_is_recognised_in_both_languages(self):
        for text in ("da", "može", "yes please", "ok", "molim"):
            self.assertTrue(conversation.accepts_offer(text), text)
        for text in ("no thanks", "ne treba", "what about linkedin?"):
            self.assertFalse(conversation.accepts_offer(text), text)


class TheWatchFiresOnTheCounterMoving(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="rga-followup-")
        self._prev = os.environ.get(followup.JOURNAL_VAR)
        os.environ[followup.JOURNAL_VAR] = os.path.join(self.tmp, "f.jsonl")

    def tearDown(self):
        import shutil
        if self._prev is None:
            os.environ.pop(followup.JOURNAL_VAR, None)
        else:
            os.environ[followup.JOURNAL_VAR] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def arm(self, baseline=None):
        return followup.register(
            channel="C1", thread_ts="T1", workspace="alpha",
            campaign_ids=["491", "492"],
            baseline=baseline if baseline is not None else {"491": 0,
                                                            "492": 0},
            language="hr", asked_by="U1")

    def test_a_registered_watch_is_open(self):
        watch = self.arm()
        self.assertEqual(watch["status"], followup.REGISTERED)
        self.assertEqual(len(followup.open_watches()), 1)

    def test_one_watch_per_thread(self):
        first, second = self.arm(), self.arm()
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(followup.open_watches()), 1)

    def test_nothing_fires_while_the_counter_stands_still(self):
        self.arm()
        self.assertEqual(
            followup.due(lambda ids: {"491": 0, "492": 0}), [])

    def test_it_fires_when_the_counter_moves(self):
        self.arm()
        due = followup.due(lambda ids: {"491": 2, "492": 0})
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0][1], {"491": 2})

    def test_a_campaign_that_had_already_sent_does_not_fire_it(self):
        """Without a baseline the client is told "the first mail has gone
        out" about mail that went out before they asked."""
        self.arm(baseline={"491": 3, "492": 0})
        self.assertEqual(followup.due(lambda ids: {"491": 3, "492": 0}), [])
        self.assertTrue(followup.due(lambda ids: {"491": 4, "492": 0}))

    def test_the_message_is_in_the_language_of_the_thread(self):
        watch = self.arm()
        text = followup.message_for(watch, {"491": 2})
        self.assertIn("Javljam", text)
        self.assertNotIn("As promised", text)

    def test_the_message_says_it_is_the_providers_confirmation(self):
        watch = self.arm()
        text = followup.message_for(watch, {"491": 2})
        self.assertIn("provider", text.lower())

    def test_an_expired_watch_says_so_rather_than_going_quiet(self):
        watch = self.arm()
        followup.close(watch, followup.REGISTERED)
        rows = followup.load()
        rows[0]["expires_epoch"] = 0
        followup._append(rows[0])
        due = followup.due(lambda ids: {"491": 0})
        self.assertEqual(len(due), 1)
        self.assertIsNone(due[0][1])
        self.assertIn("24", followup.message_for(due[0][0], None))

    def test_closing_a_watch_takes_it_off_the_list(self):
        watch = self.arm()
        followup.close(watch, followup.FIRED)
        self.assertEqual(followup.open_watches(), [])

    def test_the_module_posts_nothing(self):
        """Asserted on the AST, not on the text.

        The first version searched the source for "slack.post" and failed
        on this module's own docstring, which says there is no `slack.post`
        in it. That is the trap CLAUDE.md names: a test that breaks when
        somebody writes a comment is testing the prose.
        """
        import ast

        with open(followup.__file__, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        used = {node.attr for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in ("slack", "providers")}
        self.assertNotIn("post", used)
        imported = {alias.name for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in node.names}
        self.assertNotIn("slack", imported)


# ==================================================== 5. BANTER

class BanterGetsOneLightSentence(unittest.TestCase):
    """The message that prompted this: a client wrote "jesi nam struju
    provukao?" - did you run the electricity in for us - about whether the
    campaigns had been switched on. It got a paragraph of counters."""

    def test_the_electricity_joke_is_recognised(self):
        self.assertTrue(conversation.is_banter(
            "<@U07KWV94J0H>, jesi nam struju provukao?"))

    def test_croatian_banter_with_an_emoji_is_recognised(self):
        self.assertTrue(conversation.is_banter(
            "nemoj misliti na torticu :face_with_spiral_eyes:"))
        self.assertTrue(conversation.is_banter(
            "šalim se, možemo ju maknuti ak želite"))

    def test_a_straight_question_is_not_banter(self):
        for text in ("koliko je domena aktivno?",
                     "what went out this week?",
                     "trebam popis domena s kojih šaljete mailove"):
            self.assertFalse(conversation.is_banter(text), text)

    def test_the_notice_keeps_the_facts_unchanged(self):
        notice = conversation.BANTER_NOTICE.lower()
        self.assertIn("one light sentence", notice)
        self.assertIn("numbers do not change", notice)
        self.assertIn("invent none", notice)


# ============================================== 6. PRECISE OPENERS

class TheOpenerDoesNotOverstate(unittest.TestCase):

    def test_the_client_tone_says_lead_with_the_precise_fact(self):
        tone = conversation.TONE[slackscope.CLIENT]
        self.assertIn("LEAD WITH THE PRECISE FACT", tone)
        self.assertIn("Do not generalise from one campaign", tone)

    def test_it_says_to_report_the_absence_first(self):
        tone = conversation.TONE[slackscope.CLIENT].lower()
        self.assertIn("has not happened, say that", tone)


if __name__ == "__main__":
    unittest.main()
