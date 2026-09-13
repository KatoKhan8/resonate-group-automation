"""The cadence is event-driven, so a state change has to change the plan.

Every test here is a counterfactual pair: the same account, one recorded
fact changed, a different answer. A file whose tests all pass together and
all fail together is a file with one test in it.

The properties the whole file defends:

    a LinkedIn step is chosen by where the prospect STANDS, not by where the
    calendar is - and "they declined", "they have not accepted yet" and
    "nobody has read whether they accepted" are three different answers

    a state this build cannot read produces a WAIT that names the read,
    never an assumed state and never a silent skip

    a reply, a meeting, a bounce and an unsubscribe each reach exactly the
    scope they are about: the address, the person, or the company

Nothing here performs a provider call. `linkedinstate` imports no provider
module at all, which is asserted rather than trusted.
"""
import unittest

from src import (accountpolicy as ap, cadence, cadencelibrary as cl, channels,
                 clients, collision, eligibility, events)
from src import linkedinstate as ls
from src import nextaction as na
from src import senderidentity as si
from src import store
from tests.campaignbase import CampaignTest

WS = "productive"
KEY = "brooke"
COLLEAGUE = "joseph"

REQUEST_AT = "2026-09-01T09:00:00+00:00"
INSIDE_WINDOW = "2026-09-03T09:00:00+00:00"
PAST_WINDOW = "2026-09-20T09:00:00+00:00"

LI_STEPS = cl.PRODUCTIVE_LI_HEAVY_V1
REQUEST_STEP = next(s for s in LI_STEPS if ls.action_of(s) == ls.CONNECT)
MESSAGE_STEP = next(s for s in LI_STEPS if s["key"] == "li2")
FORK_STEP = next(s for s in LI_STEPS if s["key"] == "li3")


def a_record(events_=()):
    """The smallest record the connection axis needs: one person, a log."""
    return {"id": "acme", "client": WS, "domain": "acme.test",
            "contacts": [{"key": KEY, "name": "Brooke Baron",
                          "linkedin": f"https://www.linkedin.com/in/{KEY}"}],
            "events": list(events_)}


def request_sent(step="li1", at=REQUEST_AT):
    return {"type": events.PUSH_MARKED, "contact": KEY, "channel": "linkedin",
            "step": step, "at": at}


def accepted(at="2026-09-02T09:00:00+00:00"):
    return {"type": events.LINKEDIN_CONNECTED, "contact": KEY, "at": at}


def replied(channel="email", at="2026-09-02T09:00:00+00:00"):
    return {"type": events.REPLY_RECEIVED, "contact": KEY, "channel": channel,
            "at": at}


class ConnectionAxis(unittest.TestCase):
    """`linkedinstate` on its own. No store, no campaign, no provider."""

    def state(self, rec, observed=None, at=PAST_WINDOW):
        return ls.connection(rec, rec["contacts"][0], observed=observed,
                             steps=LI_STEPS, at=at)["state"]

    def move(self, rec, spec, observed=None, at=PAST_WINDOW, config=None):
        return ls.plan_step(rec, rec["contacts"][0], spec, observed=observed,
                            steps=LI_STEPS, config=config, at=at)


# ---------------------------------------------- connection accepted -> message

class AnAcceptedConnectionEntersTheMessageSequence(ConnectionAxis):

    def test_the_request_is_skipped_and_the_message_goes(self):
        rec = a_record([request_sent(), accepted()])
        self.assertEqual(self.state(rec), ls.CONNECTION_ACCEPTED)
        self.assertEqual(self.move(rec, REQUEST_STEP)["status"], ls.SKIP)
        self.assertEqual(self.move(rec, MESSAGE_STEP)["status"], ls.GO)

    def test_without_the_acceptance_the_message_waits(self):
        """The counterfactual. If this passed too, the test above would be
        proving that a message always goes rather than that acceptance
        releases it."""
        rec = a_record([request_sent()])
        self.assertNotEqual(self.state(rec), ls.CONNECTION_ACCEPTED)
        self.assertEqual(self.move(rec, MESSAGE_STEP)["status"], ls.WAIT)

    def test_acceptance_cancels_the_inmail_path(self):
        """`li3` forks: connected it is a message, refused it is an InMail.
        An acceptance has to take the first branch and not merely make the
        second one nicer."""
        accepted_rec = a_record([request_sent(), accepted()])
        move = self.move(accepted_rec, FORK_STEP)
        self.assertEqual(move["status"], ls.GO)
        self.assertEqual(move["action"], ls.MESSAGE)
        self.assertIsNone(move["inmail"])

    def test_a_refusal_takes_the_other_branch_of_the_same_step(self):
        rec = a_record([request_sent()])
        observed = ls.observation(lifecycle="connectionsent", source="test")
        self.assertEqual(self.state(rec, observed), ls.CONNECTION_NOT_ACCEPTED)
        move = self.move(rec, FORK_STEP, observed)
        self.assertEqual(move["action"], ls.INMAIL)


# ------------------------------------------- the window asks, it does not answer

class TheWaitWindowOpensAQuestionRatherThanAnsweringIt(ConnectionAxis):

    def test_inside_the_window_the_request_is_pending(self):
        rec = a_record([request_sent()])
        self.assertEqual(self.state(rec, at=INSIDE_WINDOW),
                         ls.REQUEST_PENDING)

    def test_past_the_window_with_nobody_reading_is_not_a_refusal(self):
        """THE CRUX. Elapsed time is not evidence. Somebody may have
        accepted on day two and nobody looked, and an InMail sent on the
        strength of the calendar goes to a person who is already
        connected."""
        rec = a_record([request_sent()])
        self.assertEqual(self.state(rec), ls.UNKNOWN_ACCEPTANCE)
        move = self.move(rec, FORK_STEP)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_ACCEPTANCE_UNREAD)
        self.assertNotEqual(move["action"], ls.INMAIL)

    def test_the_same_window_with_a_reading_is_a_refusal(self):
        """The counterfactual, and the pair is the whole design: the window
        decides when the question may be asked and the provider answers
        it."""
        rec = a_record([request_sent()])
        observed = ls.observation(lifecycle="connectionsent", source="test")
        self.assertEqual(self.state(rec, observed), ls.CONNECTION_NOT_ACCEPTED)

    def test_the_window_is_configurable_and_moving_it_moves_the_answer(self):
        rec = a_record([request_sent()])
        long = {"linkedin": {"connection_wait_days": 60}}
        found = ls.connection(rec, rec["contacts"][0], steps=LI_STEPS,
                              config=long, at=PAST_WINDOW)
        self.assertEqual(found["state"], ls.REQUEST_PENDING)
        self.assertEqual(ls.settings(long)["connection_wait_days"]["value"], 60)
        self.assertTrue(ls.settings(long)["connection_wait_days"]["configured"])
        self.assertFalse(ls.settings({})["connection_wait_days"]["configured"])

    def test_a_pending_request_carries_a_date_and_an_unread_one_does_not(self):
        """Two different remedies. A window carries a clock; "nobody has
        read the provider" carries none, because no amount of waiting
        performs the read."""
        rec = a_record([request_sent()])
        pending = self.move(rec, MESSAGE_STEP, at=INSIDE_WINDOW)
        self.assertTrue(pending["execute_after"])
        self.assertEqual(pending["code"], ls.HELD_REQUEST_OUTSTANDING)
        self.assertIsNone(self.move(rec, MESSAGE_STEP)["execute_after"])


# ------------------------------------------------------- the second invitation

class ASecondInvitationIsNotARetry(ConnectionAxis):

    def test_a_pending_request_refuses_another(self):
        rec = a_record([request_sent()])
        move = self.move(rec, REQUEST_STEP, at=INSIDE_WINDOW)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_REQUEST_OUTSTANDING)

    def test_a_cold_prospect_gets_one(self):
        rec = a_record()
        self.assertEqual(self.state(rec), ls.NO_EVIDENCE)
        self.assertEqual(self.move(rec, REQUEST_STEP)["status"], ls.GO)

    def test_a_sequence_carrying_two_requests_is_refused_outright(self):
        """The authoring half. A denser LinkedIn cadence gets this wrong by
        forgetting `requires` on a message step, and a second request that
        can never run is a cadence reporting a touch it will not make."""
        doubled = list(LI_STEPS[:2]) + [
            {"key": "li_extra", "day": 5, "channel": "linkedin",
             "linkedin_action": "connect", "capability": cl.CAP_CONNECT,
             "template": "linkedin_intro"}]
        with self.assertRaises(cadence.BadCadence):
            cadence.validate_steps(doubled)
        self.assertEqual(len(ls.connection_requests(LI_STEPS)), 1)
        self.assertTrue(cadence.validate_steps(LI_STEPS))


# ---------------------------------------------------------- the open profile

class AnOpenProfileSkipsTheRequest(ConnectionAxis):

    def test_an_observed_open_profile_releases_the_message_on_day_one(self):
        rec = a_record()
        observed = ls.observation(open_profile=True, source="test")
        self.assertEqual(self.state(rec, observed), ls.OPEN_PROFILE)
        self.assertEqual(self.move(rec, MESSAGE_STEP, observed)["status"],
                         ls.GO)

    def test_without_the_observation_the_message_waits(self):
        rec = a_record()
        self.assertEqual(self.move(rec, MESSAGE_STEP)["status"], ls.WAIT)

    def test_an_unobserved_profile_is_not_read_as_closed_or_as_open(self):
        """Nothing in this build reads whether a profile is open, so the
        absence is "nobody looked". It costs a connection request that was
        not needed, which is the only safe direction."""
        self.assertFalse(ls.PROVIDER_REPORTS_OPEN_PROFILE)
        rec = a_record()
        self.assertEqual(self.state(rec), ls.NO_EVIDENCE)
        self.assertEqual(self.move(rec, REQUEST_STEP)["status"], ls.GO)

    def test_the_open_profile_message_is_held_rather_than_run_or_dropped(self):
        """`li1`'s alternative messages an open profile directly, and this
        build cannot prove it can. Held, with the capability named - never
        executed as if it worked, and never quietly skipped."""
        rec = a_record()
        observed = ls.observation(open_profile=True, source="test")
        move = self.move(rec, REQUEST_STEP, observed)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN)
        self.assertEqual(move["action"], ls.OPEN_PROFILE_MESSAGE)


# ------------------------------------------------------------------- InMail

class InMailIsEvaluatedAndRefused(ConnectionAxis):

    def refused(self):
        return a_record([request_sent()]), ls.observation(
            lifecycle="connectionsent", inmail=True, source="test")

    def enabled(self):
        return {"linkedin": {"inmail": {"enabled": True}}}

    def test_it_is_never_evaluated_merely_because_nothing_was_accepted(self):
        rec = a_record([request_sent()])
        verdict, why = ls.evaluate_inmail(ls.UNKNOWN_ACCEPTANCE,
                                          config=self.enabled())
        self.assertEqual(verdict, ls.INMAIL_NOT_AVAILABLE)

    def test_an_unread_eligibility_is_not_an_eligibility(self):
        rec = a_record([request_sent()])
        observed = ls.observation(lifecycle="connectionsent", source="test")
        verdict, why = ls.evaluate_inmail(ls.CONNECTION_NOT_ACCEPTED, observed,
                                          self.enabled())
        self.assertEqual(verdict, ls.INMAIL_UNKNOWN)

    def test_a_workspace_that_has_not_enabled_it_refuses(self):
        rec, observed = self.refused()
        verdict, _ = ls.evaluate_inmail(ls.CONNECTION_NOT_ACCEPTED, observed,
                                        {})
        self.assertEqual(verdict, ls.INMAIL_NOT_AVAILABLE)

    def test_every_condition_met_is_still_held_on_the_capability(self):
        """The one that matters. Policy on, provider says eligible, state
        correct - and this build has no validated way to send an InMail, so
        the step is HELD. An eligibility nothing can act on is not a
        permission."""
        rec, observed = self.refused()
        verdict, _ = ls.evaluate_inmail(ls.CONNECTION_NOT_ACCEPTED, observed,
                                        self.enabled())
        self.assertEqual(verdict, ls.INMAIL_ELIGIBLE)
        move = self.move(rec, FORK_STEP, observed, config=self.enabled())
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN)

    def test_validating_the_capability_is_the_only_thing_that_changes_it(self):
        """The counterfactual, and it is also the instruction for whoever
        validates it: one table entry, nothing else."""
        rec, observed = self.refused()
        original = dict(ls.CAPABILITIES)
        ls.CAPABILITIES[cl.CAP_INMAIL] = (True, "validated in this test")
        try:
            move = self.move(rec, FORK_STEP, observed, config=self.enabled())
            self.assertEqual(move["status"], ls.GO)
            self.assertEqual(move["action"], ls.INMAIL)
        finally:
            ls.CAPABILITIES.clear()
            ls.CAPABILITIES.update(original)

    def test_every_capability_the_shipped_sequences_name_is_classified(self):
        """A capability nobody classified must not read as satisfied. This
        is what stops a new `linkedin_action` arriving with no gate."""
        for name in cl.SEQUENCES:
            for cap in cl.capabilities_used(cl.named(name)):
                with self.subTest(sequence=name, capability=cap):
                    self.assertIn(cap, ls.CAPABILITIES)
        self.assertEqual(ls.capability("linkedin.something_new")[0], False)


# ------------------------------------------------- the provider's own words

class AProviderWordIsTranslatedOrRefused(ConnectionAxis):

    def test_an_unseen_word_becomes_unknown_and_holds_everything(self):
        rec = a_record([request_sent()])
        observed = ls.observation(lifecycle="Withdrawn", source="test")
        self.assertEqual(self.state(rec, observed), ls.UNKNOWN)
        move = self.move(rec, MESSAGE_STEP, observed)
        self.assertEqual(move["code"], ls.HELD_PROVIDER_STATE_UNKNOWN)

    def test_failed_is_refused_rather_than_read_as_not_connected(self):
        """27 of 851 observed leads read `Failed` while carrying an accepted
        connection and a sent message, so `Failed` is not "nothing reached
        them" and must not re-invite anybody."""
        state, why = ls.from_provider_lifecycle("failed")
        self.assertEqual(state, ls.UNKNOWN)
        self.assertNotEqual(state, ls.NOT_CONNECTED)
        self.assertTrue(why)

    def test_every_heyreach_lifecycle_word_is_mapped_or_named(self):
        """The allowlist has to cover the provider's own vocabulary, or a
        state it publishes lands in `UNKNOWN` by accident rather than by
        decision."""
        from src.providers import heyreach

        for word in heyreach.LIFECYCLE:
            with self.subTest(word=word):
                self.assertIn(word, set(ls.PROVIDER_LIFECYCLE)
                              | set(ls.PROVIDER_REFUSED))

    def test_the_two_modules_agree_on_the_state_words(self):
        """A sequence asking for `connected` and a machine answering
        `CONNECTED` have to be the same string, or the branch silently never
        fires. Asserted on the values rather than on the source text."""
        self.assertEqual(ls.CONNECTED, cl.CONNECTED)
        self.assertEqual(ls.OPEN_PROFILE, cl.OPEN_PROFILE)
        self.assertEqual(ls.CONNECTION_ACCEPTED, cl.CONNECTION_ACCEPTED)
        self.assertEqual(ls.CONNECTION_NOT_ACCEPTED, cl.CONNECTION_NOT_ACCEPTED)
        self.assertEqual(ls.LEGACY_ACCEPT_REQUIREMENT, cadence.ACCEPT_EVENT)

    def test_it_imports_no_provider(self):
        """A state machine that fetched its own provider evidence would
        spend on every screen refresh and make an offline plan impossible."""
        import sys

        self.assertNotIn("providers", ls.__dict__)
        module = sys.modules[ls.__module__]
        for name, value in vars(module).items():
            if getattr(value, "__name__", "").startswith("src.providers"):
                self.fail(f"linkedinstate imports {name}")


# ------------------------------------------------- an unplaceable LinkedIn act

class AnActionNobodyCanNameProvesNothing(ConnectionAxis):

    def test_a_linkedin_touch_with_no_step_does_not_start_the_window(self):
        """`leadobserve._linkedin_step` records `step: None` whenever a
        sequence has more than one LinkedIn step - which the LinkedIn-heavy
        cadence has six of. Reading that as a connection request would start
        a window nothing began."""
        rec = a_record([request_sent(step=None)])
        found = ls.connection(rec, rec["contacts"][0], steps=LI_STEPS,
                              at=PAST_WINDOW)
        self.assertEqual(found["state"], ls.UNKNOWN_ACCEPTANCE)
        self.assertIsNone(found["request_at"])
        self.assertEqual(self.move(rec, MESSAGE_STEP)["status"], ls.WAIT)

    def test_a_named_step_does_start_it(self):
        rec = a_record([request_sent(step="li1")])
        found = ls.connection(rec, rec["contacts"][0], steps=LI_STEPS,
                              at=INSIDE_WINDOW)
        self.assertEqual(found["state"], ls.REQUEST_PENDING)
        self.assertEqual(found["request_at"], REQUEST_AT)


# ================================================================= the wiring
#
# Everything above is the branch on its own. Everything below proves it is
# CONSUMED - by the timeline the send path reads, and by the planner an
# operator reads. A branch nothing consults is the recurring defect this
# repository names by name.


class TheTimelineReadsTheBranch(CampaignTest):

    def record(self):
        from tests.campaignbase import contact

        self.reset_estate()
        rec = store.new_record("acme", "domains", WS, "Acme Ltd", "acme.test")
        rec["state"] = "verified"
        rec["hook"] = "resourcing visibility"
        rec["company_facts"] = {"name": "Acme Ltd", "industry": "agency"}
        rec["contacts"] = [contact(KEY, "Brooke Baron", f"{KEY}@acme.test",
                                   angle="operations")]
        rec["cadence"] = {}
        store.save([rec])
        return rec

    def steps(self, rec):
        return cadence.build(rec, self.config)["contacts"][KEY]

    def test_a_message_step_waits_until_the_connection_lands(self):
        rec = self.record()
        self.assertEqual(self.steps(rec)["li2"]["status"], "waiting")

    def test_the_acceptance_releases_it(self):
        rec = self.record()
        events.record(rec, events.LINKEDIN_CONNECTED, contact_key=KEY,
                      at="2026-09-02T09:00:00+00:00")
        self.assertNotEqual(self.steps(rec)["li2"]["status"], "waiting")

    def test_an_already_connected_person_skips_the_request(self):
        """The operator's branch, on the path `eligibility` reads."""
        rec = self.record()
        self.assertNotEqual(self.steps(rec)["li1"]["status"], "skipped")
        events.record(rec, events.LINKEDIN_CONNECTED, contact_key=KEY,
                      at="2026-09-02T09:00:00+00:00")
        step = self.steps(rec)["li1"]
        self.assertEqual(step["status"], "skipped")
        self.assertIn("connection request is skipped", step["skipped_reason"])

    def test_the_state_travels_onto_the_step_for_a_reviewer(self):
        rec = self.record()
        self.assertEqual(self.steps(rec)["li2"]["linkedin_state"],
                         ls.NO_EVIDENCE)


class ThePlannerReadsTheBranch(CampaignTest):
    """`next_best_action` over a LinkedIn-heavy account."""

    def setUp(self):
        super().setUp()
        si.install([
            si.new_sender(WS, "anna", "Anna Novak", team="growth"),
            si.new_sender(WS, "petar", "Petar Horvat", team="growth"),
            si.new_email_account(WS, "anna07", "anna", "anna07@productive.test"),
            si.new_linkedin_account(WS, "petar-li", "petar",
                                    "https://www.linkedin.com/in/petar"),
        ])

    def record(self, contacts=None):
        from tests.campaignbase import contact

        self.reset_estate()
        rec = store.new_record("acme", "domains", WS, "Acme Ltd", "acme.test")
        rec["state"] = "verified"
        rec["company_facts"] = {"name": "Acme Ltd", "industry": "agency"}
        rec["qualification"] = {"segment": {"employee_band": "20_49",
                                            "employees": 31}}
        rec["contacts"] = contacts or [
            dict(contact(KEY, "Brooke Baron", f"{KEY}@acme.test",
                         title="Head of Production", angle="operations"),
                 primary=True),
            contact(COLLEAGUE, "Joseph O'Neill", f"{COLLEAGUE}@acme.test",
                    title="Design Director", angle="operations"),
        ]
        rec["cadence"] = {}
        store.save([rec])
        return rec

    def clear_estate(self):
        return {"domain": "acme.test", "workspace": WS, "leads": 0,
                "people": [], "emails_sent_total": 0,
                "anyone_in_sequence": False, "unknown_statuses": [],
                "any_bounce": False, "verdict": collision.CLEAR,
                "checked_at": "2026-09-13T09:00:00+00:00"}

    def ask(self, rec, at="2026-09-14T09:00:00+00:00", linkedin=None,
            config=None):
        return na.next_best_action(rec, config=config or self.config,
                                   workspace=WS, estate=self.clear_estate(),
                                   at=at, suppressed=set(), linkedin=linkedin)

    def considered(self, decision, key=KEY):
        return next(c for c in decision["considered"] if c["key"] == key)

    # -------------------------------------------------- the LinkedIn lane

    def test_a_pending_request_holds_the_lane_with_a_date(self):
        rec = self.record()
        rec["events"].append(request_sent(at="2026-09-13T09:00:00+00:00"))
        store.save([rec])
        found = self.considered(self.ask(rec))
        self.assertEqual(found["linkedin"]["state"], ls.REQUEST_PENDING)

    def test_an_unread_acceptance_asks_for_the_read_rather_than_a_clock(self):
        rec = self.record()
        rec["events"].append(request_sent())
        store.save([rec])
        found = self.considered(self.ask(rec, at=PAST_WINDOW))
        self.assertEqual(found["linkedin"]["code"], ls.HELD_ACCEPTANCE_UNREAD)

    def test_supplying_the_reading_changes_the_answer(self):
        """The counterfactual for the pair above: the planner never fetches,
        so the only thing that moves this lane is a caller handing it a read
        it has already paid for."""
        rec = self.record()
        rec["events"].append(request_sent())
        store.save([rec])
        observed = {KEY: ls.observation(lifecycle="connectionaccepted",
                                        at="2026-09-10T09:00:00+00:00",
                                        source="test")}
        found = self.considered(self.ask(rec, at=PAST_WINDOW,
                                         linkedin=observed))
        self.assertEqual(found["linkedin"]["state"], ls.CONNECTION_ACCEPTED)

    def test_the_planner_performs_no_provider_call(self):
        def explode(*a, **kw):
            raise AssertionError("the planner called the provider")

        for name in ("check_account", "check_linkedin_profile"):
            self.addCleanup(setattr, collision, name, getattr(collision, name))
            setattr(collision, name, explode)
        self.assertTrue(self.ask(self.record())["action"])

    # ------------------------------------------------- the cross-channel stop

    def test_an_email_reply_stops_the_linkedin_follow_ups(self):
        rec = self.record()
        self.assertEqual(self.ask(rec)["action"], na.ACT)
        rec["events"].append(replied(channel="email",
                                     at="2026-09-13T10:00:00+00:00"))
        store.save([rec])
        decision = self.ask(rec)
        self.assertEqual(decision["action"], na.WAIT)
        found = self.considered(decision)
        self.assertIn(found["reason_code"],
                      (eligibility.BLOCKED_REPLIED,
                       eligibility.BLOCKED_CONTACT_PAUSED))

    def test_a_linkedin_reply_stops_the_email_follow_ups(self):
        """The mirror, and it has to be tested separately: a guard written
        on one channel and not the other is this repository's other
        recurring defect."""
        rec = self.record()
        rec["events"].append(replied(channel="linkedin",
                                     at="2026-09-13T10:00:00+00:00"))
        store.save([rec])
        found = self.considered(self.ask(rec))
        self.assertFalse(found["ok"])
        self.assertNotEqual(found["channel"], "email")

    def test_the_branch_stops_on_a_reply_from_either_channel_on_its_own(self):
        """Two independent guards, as `ACCOUNT-OUTREACH.md` §12 describes.
        This is the branch's own, asserted without the eligibility gate in
        front of it, so removing either fails a different test."""
        for channel in ("email", "linkedin"):
            with self.subTest(channel=channel):
                rec = a_record([request_sent(), accepted(), replied(channel)])
                move = ls.plan_step(rec, rec["contacts"][0], MESSAGE_STEP,
                                    steps=LI_STEPS, at=PAST_WINDOW)
                self.assertEqual(move["status"], ls.WAIT)
                self.assertEqual(move["code"], ls.HELD_REPLIED)

    # --------------------------------------------------------- reply policy

    def test_a_positive_reply_stops_the_person_and_holds_the_account(self):
        rec = self.record()
        ap.apply_reply(rec, KEY, outcome=ap.POSITIVE, config=self.config,
                       at="2026-09-13T10:00:00+00:00")
        store.save([rec])
        decision = self.ask(rec)
        self.assertEqual(decision["action"], na.WAIT)
        self.assertEqual(decision["reason_code"], na.WAIT_ACCOUNT_HELD)
        self.assertTrue(rec["contacts"][0].get("paused"))

    def test_a_narrow_reply_leaves_the_colleague_working(self):
        """The counterfactual. "Not interested" from one person is not the
        company declining, and if this failed the test above would be
        proving that any reply stops everything."""
        rec = self.record()
        ap.apply_reply(rec, KEY, outcome=ap.NEGATIVE, config=self.config,
                       at="2026-09-13T10:00:00+00:00")
        store.save([rec])
        decision = self.ask(rec)
        self.assertEqual(decision["action"], na.ACT, decision["reason"])
        self.assertEqual(decision["person"], COLLEAGUE)

    def test_an_unsubscribe_suppresses_the_person_not_the_company(self):
        rec = self.record()
        ap.apply_reply(rec, KEY, outcome=ap.UNSUBSCRIBE, config=self.config,
                       at="2026-09-13T10:00:00+00:00")
        store.save([rec])
        self.assertTrue(rec["contacts"][0]["unsubscribed"])
        self.assertFalse((rec.get("suppression") or {}).get("unsubscribed"))
        decision = self.ask(rec)
        self.assertEqual(decision["action"], na.ACT, decision["reason"])
        self.assertEqual(decision["person"], COLLEAGUE)

    def test_a_company_wide_removal_stops_everybody(self):
        rec = self.record()
        ap.apply_reply(rec, KEY, outcome=ap.ACCOUNT_DNC, config=self.config,
                       at="2026-09-13T10:00:00+00:00")
        store.save([rec])
        self.assertEqual(self.ask(rec)["action"], na.STOP)

    # ------------------------------------------------------------ a meeting

    def test_a_booked_meeting_stops_cold_outreach_for_the_whole_account(self):
        """`MEETING_MARKED` had six reporting consumers and none on a send
        or plan path, so a meeting with the COO did not stop the cold
        sequence to the CFO."""
        rec = self.record()
        self.assertEqual(self.ask(rec)["action"], na.ACT)
        events.record(rec, events.MEETING_MARKED, contact_key=KEY,
                      at="2026-09-13T10:00:00+00:00")
        store.save([rec])
        decision = self.ask(rec)
        self.assertEqual(decision["action"], na.WAIT)
        self.assertEqual(decision["reason_code"], na.WAIT_ACCOUNT_HELD)

    def test_the_meeting_reaches_the_send_gate_too(self):
        """A plan that stopped while the send path carried on would be the
        worse half of the defect."""
        rec = self.record()
        events.record(rec, events.MEETING_MARKED, contact_key=COLLEAGUE,
                      at="2026-09-13T10:00:00+00:00")
        self.assertEqual(
            eligibility.must_not_contact(rec, rec["contacts"][0],
                                         config=self.config,
                                         suppressed=set())[3],
            eligibility.BLOCKED_COMPANY_PAUSED)
        self.assertEqual(cadence.pause_state(rec, self.config)["outcome"],
                         "meeting_booked")

    def test_without_the_meeting_the_account_is_workable(self):
        rec = self.record()
        self.assertIsNone(cadence.pause_state(rec, self.config))

    # -------------------------------------------------------------- a bounce

    def test_a_bounce_closes_the_address_and_nothing_else(self):
        rec = self.record()
        events.record(rec, events.EMAIL_BOUNCED, contact_key=KEY,
                      channel="email", at="2026-09-13T10:00:00+00:00")
        store.save([rec])
        found = self.considered(self.ask(rec))
        self.assertEqual(found["closed_channels"].get("email"),
                         na.CONTACT_BOUNCED)
        self.assertFalse(channels.email_verdict(rec, rec["contacts"][0],
                                                self.config, set())[0])
        # The person's LinkedIn is untouched, and so is the colleague's
        # address - the account carries on through another stakeholder.
        self.assertTrue(channels.linkedin_verdict(rec, rec["contacts"][0],
                                                  self.config, set())[0])
        colleague = self.considered(self.ask(rec), COLLEAGUE)
        self.assertNotIn("email", colleague["closed_channels"])
        self.assertNotEqual(self.ask(rec)["action"], na.STOP)

    def test_the_bounced_person_can_still_be_worked_on_linkedin(self):
        rec = self.record()
        events.record(rec, events.EMAIL_BOUNCED, contact_key=KEY,
                      channel="email", at="2026-09-13T10:00:00+00:00")
        store.save([rec])
        found = self.considered(self.ask(rec))
        self.assertEqual(found["channel"], "linkedin")


# ----------------------------------------------------- the client's own numbers

class TheConfiguredCadenceAndTheConfiguredCapsAgree(unittest.TestCase):
    """The caps have to permit the sequence the client actually runs. A
    limit that blocks its own cadence is a number nobody chose."""

    def setUp(self):
        self.config = clients.load(WS)
        self.steps = cadence.steps_for(config=self.config)

    def test_the_client_file_selects_the_linkedin_heavy_sequence(self):
        shape = cl.shape(self.steps)
        self.assertEqual(shape["total"], 11)
        self.assertEqual(shape["email"], 5)
        self.assertEqual(shape["linkedin"], 6)
        self.assertEqual(shape["days"], 21)

    def test_the_total_cap_does_not_block_the_last_step(self):
        from src import fatigue

        limits = fatigue.limits(self.config)
        self.assertGreaterEqual(limits["contact.max_touches_total"]["value"],
                                len(self.steps))

    def test_the_weekly_cap_does_not_block_the_densest_week(self):
        from src import fatigue

        weeks = {}
        for step in self.steps:
            weeks.setdefault((int(step["day"]) - 1) // 7, 0)
            weeks[(int(step["day"]) - 1) // 7] += 1
        limits = fatigue.limits(self.config)
        self.assertGreaterEqual(
            limits["contact.max_touches_per_week"]["value"], max(weeks.values()),
            "the configured weekly cap is below this client's own densest "
            "week, so the cadence would stop partway through and report "
            "touches it never made")

    def test_every_limit_in_force_was_chosen_rather_than_defaulted(self):
        from src import fatigue

        unchosen = sorted(k for k, v in fatigue.limits(self.config).items()
                          if not v["configured"])
        self.assertEqual(unchosen, [])


if __name__ == "__main__":
    unittest.main()
