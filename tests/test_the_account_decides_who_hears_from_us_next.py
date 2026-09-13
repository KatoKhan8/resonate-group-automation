"""The account is the unit of outreach, so the account decides who is next.

Every test here is a counterfactual pair: the same account, one fact
changed, a different answer. A file of tests that all pass together and all
fail together is a file with one test in it.

The property the whole file defends:

    `next_best_action` never says ACT where the send gate below it would
    refuse, and every WAIT names the exact thing that would have to change.

Nothing here performs a provider call. `collision.check_account` is
booby-trapped in one test precisely to prove that.
"""
import unittest

from src import (account, cadence, cadencearms, clients, collision, eligibility,
                 events, fatigue, nextaction as na, store)
from src import senderidentity as si
from tests.campaignbase import CampaignTest

WS = "productive"

BROOKE = "brooke"          # Head of Production - operations family, primary
JOSEPH = "joseph"          # Design Director   - delivery family
NATHAN = "nathan"          # CEO               - founder family, last


def roster():
    """Two email humans and two LinkedIn humans, each owning an account.

    The live Productive roster has seven humans and 257 provider accounts
    with `sender_id: null` on every one, so nothing joins them and
    `eligible_senders` is empty. That is reported as a finding; a fixture
    that reproduced it would test nothing but the emptiness.
    """
    return [
        si.new_sender(WS, "anna", "Anna Novak", team="growth"),
        si.new_sender(WS, "mark", "Mark Weber", team="growth"),
        si.new_sender(WS, "petar", "Petar Horvat", team="partnerships"),
        si.new_sender(WS, "sara_s", "Sara Simic", team="partnerships"),
        si.new_email_account(WS, "anna07", "anna", "anna07@productive.test"),
        si.new_email_account(WS, "mark02", "mark", "mark02@productive.test"),
        si.new_linkedin_account(WS, "petar-li", "petar",
                                "https://www.linkedin.com/in/petar"),
        si.new_linkedin_account(WS, "sara-li", "sara_s",
                                "https://www.linkedin.com/in/sara"),
    ]


def clear_estate(domain="acme.test"):
    """What `collision.check_account` returns for an untouched company."""
    return {"domain": domain, "workspace": WS, "leads": 0, "people": [],
            "emails_sent_total": 0, "anyone_in_sequence": False,
            "unknown_statuses": [], "any_bounce": False,
            "verdict": collision.CLEAR, "checked_at": "2026-09-13T09:00:00+00:00"}


def in_sequence_estate(domain="acme.test"):
    """One colleague is mid-sequence in an EmailBison campaign right now."""
    return dict(clear_estate(domain), leads=1, anyone_in_sequence=True,
                verdict=collision.IN_SEQUENCE,
                people=[{"email": "someone@acme.test", "in_sequence": True,
                         "emails_sent": 2, "replies": 0, "campaigns": [],
                         "lead_status": "active", "unknown_statuses": []}])


def answered_estate(domain="acme.test"):
    """Somebody here already replied. The account is answered."""
    return dict(clear_estate(domain), leads=1, emails_sent_total=3,
                verdict=collision.TOUCHED,
                people=[{"email": "someone@acme.test", "in_sequence": False,
                         "emails_sent": 3, "replies": 1, "campaigns": [],
                         "lead_status": "active", "unknown_statuses": []}])


class NextActionTest(CampaignTest):

    def setUp(self):
        super().setUp()
        si.install(roster())
        self.config = self._config()

    def _config(self, **fatigue_overrides):
        """The Productive client file, so the numbers under test are the
        numbers the client actually runs."""
        config = clients.load("productive")
        for dotted, value in fatigue_overrides.items():
            level, key = dotted.split(".", 1)
            config.setdefault("fatigue", {}).setdefault(level, {})[key] = value
        return config

    def record(self, rid="acme", contacts=None):
        rec = store.new_record(rid, "domains", WS, "Acme Ltd", "acme.test")
        # A 20-49 person creative agency, which is `nineyards.ie`'s measured
        # shape and the one Productive's own routing sends to operations
        # first. Stated rather than left empty: with no segment,
        # `routing.strategy_for` correctly falls back to `founder_led` and
        # the CEO outranks the Head of Production - which is the module
        # being right about a company whose size nobody established, and
        # would make this file test the fallback instead of the plan.
        rec["qualification"] = {
            "segment": {"employee_band": "20_49", "employees": 31,
                        "vertical": "Creative / Branding Agency"},
            "verdict": {"icp_tier": "C", "icp_status": "qualified"},
        }
        rec["contacts"] = contacts if contacts is not None else [
            self.person(BROOKE, "Brooke Baron", "Head of Production",
                        primary=True),
            self.person(JOSEPH, "Joseph O'Neill", "Design Director"),
            self.person(NATHAN, "Nathan Dean", "Chief Executive Officer"),
        ]
        rec["cadence"] = {}
        store.save([rec])
        return rec

    def person(self, key, name, title, primary=False, sendable=True,
               linkedin=True, persona="champion", angle="operations"):
        from tests.campaignbase import contact as build

        entry = build(key, name, f"{key}@acme.test",
                      linkedin=(f"https://www.linkedin.com/in/{key}"
                                if linkedin else None),
                      persona=persona, angle=angle, sendable=sendable,
                      title=title)
        if not linkedin:
            entry["linkedin"] = None
        entry["primary"] = primary
        return entry

    def touch(self, rec, key, sender_id, channel, day, at, step=None):
        events.record(rec, events.PUSH_MARKED, contact_key=key,
                      channel=channel, day=day, sender_id=sender_id, at=at,
                      step=step, account_id=f"{sender_id}-acct")
        return rec

    def ask(self, rec, estate="clear", config=None, at="2026-09-14T09:00:00+00:00",
            campaign=None):
        if estate == "clear":
            estate = clear_estate()
        return na.next_best_action(rec, config=config or self.config,
                                   workspace=WS, estate=estate, at=at,
                                   campaign=campaign, suppressed=set())


# --------------------------------------------------------- the plain answer

class AClearAccount(NextActionTest):

    def test_it_names_a_person_a_channel_a_sender_and_a_step(self):
        decision = self.ask(self.record())
        self.assertEqual(decision["action"], na.ACT, decision["reason"])
        self.assertEqual(decision["person"], BROOKE)
        # THE FIRST STEP IS WHATEVER THE CADENCE SAYS IT IS. This asserted
        # "email" against `productive_default`, whose day 1 was an email.
        # Productive moved to `productive_li_heavy_v1` on 2026-09-13 and its
        # day 1 opens on LinkedIn beside an email. Pinning the channel here
        # asserted the client's cadence choice while claiming to test that a
        # decision NAMES a channel, so it now asserts the naming and takes
        # the channel from the sequence.
        opening = cadence.steps_for(config=self.config)[0]
        self.assertEqual(decision["channel"], opening["channel"])
        self.assertIn(decision["channel"], ("email", "linkedin"))
        self.assertTrue(decision["sender"]["sender_id"])
        self.assertTrue(decision["copy"]["step_key"])
        self.assertTrue(decision["execute_after"])
        self.assertTrue(decision["reason"])

    def test_the_primary_operations_contact_outranks_the_ceo(self):
        """Productive's own routing puts operations ahead of founders."""
        decision = self.ask(self.record())
        self.assertEqual(decision["person"], BROOKE)
        order = [c["key"] for c in decision["considered"]]
        self.assertLess(order.index(BROOKE), order.index(NATHAN))

    def test_it_writes_nothing(self):
        rec = self.record()
        before = store.load()
        self.ask(rec)
        self.assertEqual(store.load(), before)


# ------------------------------------------------------------- the reply

class AReplySuppressesTheNextAction(NextActionTest):

    def test_an_unclassified_reply_stops_the_next_action_entirely(self):
        """The counterfactual is the line above it: the same account, one
        reply event, and the answer stops being ACT."""
        rec = self.record()
        self.assertEqual(self.ask(rec)["action"], na.ACT)

        events.record(rec, events.REPLY_RECEIVED, contact_key=BROOKE,
                      channel="email", at="2026-09-13T10:00:00+00:00")
        decision = self.ask(rec)
        self.assertEqual(decision["action"], na.WAIT)
        self.assertEqual(decision["reason_code"], na.WAIT_ACCOUNT_HELD)

    def test_a_narrow_reply_ends_the_replier_and_the_colleague_carries_on(self):
        """"Not interested" from one person is not the company declining.
        The replier's sequence ends, the account is not held, and the next
        action moves to somebody else - which is the case that proves the
        test above is about the reply and not about the record."""
        rec = self.record()
        from src import accountpolicy as ap

        ap.apply_reply(rec, BROOKE, outcome=ap.NEGATIVE, config=self.config,
                       at="2026-09-13T10:00:00+00:00")
        decision = self.ask(rec)
        self.assertEqual(decision["action"], na.ACT, decision["reason"])
        self.assertNotEqual(decision["person"], BROOKE)
        brooke = next(c for c in decision["considered"] if c["key"] == BROOKE)
        self.assertIn(brooke["reason_code"],
                      (eligibility.BLOCKED_CONTACT_STOPPED,
                       eligibility.BLOCKED_REPLIED))
        self.assertTrue(brooke["terminal"])

    def test_a_held_account_stops_every_colleague_too(self):
        """The counterfactual that matters: the reply did not only remove
        the replier, it held the company. A planner that skipped to the
        next colleague would be the 'one agency that does not talk to
        itself' this architecture exists to prevent."""
        rec = self.record()
        from src import accountpolicy as ap

        ap.apply_reply(rec, BROOKE, outcome=ap.POSITIVE, config=self.config,
                       at="2026-09-13T10:00:00+00:00")
        decision = self.ask(rec)
        self.assertEqual(decision["action"], na.WAIT)
        self.assertEqual(decision["reason_code"], na.WAIT_ACCOUNT_HELD)

    def test_a_removal_request_is_a_stop_not_a_wait(self):
        rec = self.record()
        from src import accountpolicy as ap

        ap.apply_reply(rec, BROOKE, outcome=ap.ACCOUNT_DNC, config=self.config,
                       at="2026-09-13T10:00:00+00:00")
        decision = self.ask(rec)
        self.assertEqual(decision["action"], na.STOP)


# ------------------------------------------------------------- the fatigue

class FatigueBlocksTheThirdContact(NextActionTest):

    def _two_open(self, rec):
        self.touch(rec, BROOKE, "anna", "email", 1, "2026-09-01T09:00:00+00:00")
        self.touch(rec, JOSEPH, "mark", "email", 1, "2026-09-03T09:00:00+00:00")
        return rec

    def test_a_third_decision_maker_is_refused_at_a_limit_of_two(self):
        rec = self._two_open(self.record())
        config = self._config(**{"account.max_active_contacts": 2})
        decision = na.next_best_action(
            rec, config=config, workspace=WS, estate=clear_estate(),
            at="2026-09-14T09:00:00+00:00", suppressed=set())
        nathan = next(c for c in decision["considered"] if c["key"] == NATHAN)
        self.assertFalse(nathan["ok"])
        self.assertEqual(nathan["reason_code"], na.WAIT_ACCOUNT_CONCURRENCY)

    def test_the_same_account_allows_him_at_a_limit_of_three(self):
        """The counterfactual. If this failed too, the test above would be
        proving that Nathan is unreachable rather than that the limit
        bites."""
        rec = self._two_open(self.record())
        config = self._config(**{"account.max_active_contacts": 3})
        decision = na.next_best_action(
            rec, config=config, workspace=WS, estate=clear_estate(),
            at="2026-09-14T09:00:00+00:00", suppressed=set())
        nathan = next(c for c in decision["considered"] if c["key"] == NATHAN)
        self.assertTrue(nathan["ok"], nathan["why"])

    def test_a_company_worked_to_its_weekly_limit_waits_with_a_date(self):
        rec = self.record()
        for i, key in enumerate((BROOKE, JOSEPH, NATHAN, BROOKE)):
            self.touch(rec, key, "anna", "email", i + 1,
                       f"2026-09-1{i}T09:00:00+00:00")
        config = self._config(**{"account.max_touches_per_week": 4})
        decision = na.next_best_action(
            rec, config=config, workspace=WS, estate=clear_estate(),
            at="2026-09-14T09:00:00+00:00", suppressed=set())
        self.assertEqual(decision["action"], na.WAIT)
        self.assertEqual(decision["reason_code"], na.WAIT_ACCOUNT_FATIGUE)
        self.assertTrue(decision["execute_after"])
        self.assertGreater(decision["execute_after"], decision["at"])


# -------------------------------------------------------------- the bounce

class ABounceDisablesTheIdentityNotTheAccount(NextActionTest):

    def record_with_email_only_primary(self):
        return self.record(contacts=[
            self.person(BROOKE, "Brooke Baron", "Head of Production",
                        primary=True, linkedin=False),
            self.person(JOSEPH, "Joseph O'Neill", "Design Director"),
        ])

    def test_the_bounced_person_loses_email_and_the_colleague_is_next(self):
        rec = self.record_with_email_only_primary()
        self.assertEqual(self.ask(rec)["person"], BROOKE)

        events.record(rec, events.EMAIL_BOUNCED, contact_key=BROOKE,
                      channel="email", at="2026-09-13T10:00:00+00:00")
        decision = self.ask(rec)
        self.assertEqual(decision["action"], na.ACT, decision["reason"])
        self.assertEqual(decision["person"], JOSEPH)
        brooke = next(c for c in decision["considered"] if c["key"] == BROOKE)
        self.assertEqual(brooke["closed_channels"].get("email"),
                         na.CONTACT_BOUNCED)

    def test_a_bounce_on_one_address_closes_nothing_else(self):
        """Not the colleague's email, not the bounced person's LinkedIn,
        and not the account."""
        rec = self.record()
        events.record(rec, events.EMAIL_BOUNCED, contact_key=BROOKE,
                      channel="email", at="2026-09-13T10:00:00+00:00")
        decision = self.ask(rec)
        self.assertNotEqual(decision["action"], na.STOP)
        brooke = next(c for c in decision["considered"] if c["key"] == BROOKE)
        self.assertEqual(brooke["channel"], "linkedin")
        joseph = next(c for c in decision["considered"] if c["key"] == JOSEPH)
        self.assertNotIn("email", joseph["closed_channels"])

    def test_the_projection_is_per_contact(self):
        rec = self.record()
        events.record(rec, events.EMAIL_BOUNCED, contact_key=BROOKE,
                      channel="email", at="2026-09-13T10:00:00+00:00")
        self.assertEqual(len(account.bounces(rec, BROOKE)), 1)
        self.assertEqual(account.bounces(rec, JOSEPH), [])
        graph = account.graph(rec, workspace=WS)
        self.assertEqual(len(graph["by_contact"][BROOKE]["bounces"]), 1)
        self.assertEqual(graph["by_contact"][JOSEPH]["bounces"], [])


# ------------------------------------------------- the EmailBison constraint

class OnePersonCannotBeInTwoEmailCampaigns(NextActionTest):
    """EmailBison 422s a lead that is `in_sequence` elsewhere, and this
    system's own account gate is stricter still: `collision.account_policy`
    STOPs the whole domain while anyone there is mid-sequence.

    So multi-stakeholder email at one account is SEQUENTIAL, not parallel,
    and these tests pin that rather than leaving it to be rediscovered by a
    422 in production.
    """

    def test_a_colleague_mid_sequence_holds_the_whole_account(self):
        decision = self.ask(self.record(), estate=in_sequence_estate())
        self.assertEqual(decision["action"], na.WAIT)
        self.assertEqual(decision["reason_code"], na.WAIT_IN_SEQUENCE)

    def test_mid_sequence_is_a_wait_and_answered_is_a_stop(self):
        """`account_policy` says STOP to both. An orchestrator that treated
        them the same would either write off a whole account because one
        campaign was running, or re-approach a company that already
        answered."""
        rec = self.record()
        self.assertEqual(self.ask(rec, estate=in_sequence_estate())["action"],
                         na.WAIT)
        self.assertEqual(self.ask(rec, estate=answered_estate())["action"],
                         na.STOP)

    def test_an_unread_estate_is_never_read_as_a_clear_one(self):
        decision = self.ask(self.record(), estate=None)
        self.assertEqual(decision["action"], na.WAIT)
        self.assertEqual(decision["reason_code"], na.WAIT_ESTATE_UNREAD)

    def test_it_is_never_more_permissive_than_the_send_gate(self):
        """The invariant. `executionguard` requires ALLOW; so does this."""
        rec = self.record()
        for estate in (in_sequence_estate(), answered_estate(),
                       dict(clear_estate(), any_bounce=True),
                       dict(clear_estate(), unknown_statuses=["paused?"]),
                       dict(clear_estate(), verdict=collision.UNKNOWN)):
            decision, _ = collision.account_policy(estate), None
            with self.subTest(estate=estate["verdict"]):
                answer = self.ask(rec, estate=estate)
                if collision.account_policy(estate)[0] != collision.ALLOW:
                    self.assertNotEqual(answer["action"], na.ACT,
                                        answer["reason"])

    def test_it_performs_no_provider_call(self):
        """A planner that fetched its own evidence would spend a credit on
        every screen refresh, and would make an offline plan impossible."""
        def explode(*a, **kw):
            raise AssertionError("nextaction called the provider")

        for name in ("check_account", "leads_for_domain", "check_address",
                     "check_linkedin_profile"):
            self.addCleanup(setattr, collision, name,
                            getattr(collision, name))
            setattr(collision, name, explode)
        self.assertEqual(self.ask(self.record())["action"], na.ACT)


# ------------------------------------------------------------ the spacing

class SequencingComesFromConfigurationNotFromCode(NextActionTest):

    def opened(self, rec):
        return self.touch(rec, BROOKE, "anna", "email", 1,
                          "2026-09-14T09:00:00+00:00")

    def test_the_second_stakeholder_waits_the_configured_gap(self):
        rec = self.opened(self.record(contacts=[
            self.person(BROOKE, "Brooke Baron", "Head of Production",
                        primary=True),
            self.person(JOSEPH, "Joseph O'Neill", "Design Director"),
        ]))
        config = self._config(
            **{"account.min_hours_between_first_touches": 72,
               "contact.min_hours_between_touches": 999})
        decision = na.next_best_action(
            rec, config=config, workspace=WS, estate=clear_estate(),
            at="2026-09-14T10:00:00+00:00", suppressed=set())
        self.assertEqual(decision["action"], na.WAIT)
        self.assertEqual(decision["reason_code"], na.WAIT_SPACING)
        self.assertEqual(decision["person"], JOSEPH)
        self.assertEqual(decision["execute_after"], "2026-09-17T09:00:00+00:00")

    def test_moving_the_number_moves_the_plan(self):
        """The hypothesis is tested, not hard-coded. Day 4-5 is 96 hours;
        24 hours is a different plan and the module has no opinion about
        which is right."""
        rec = self.opened(self.record(contacts=[
            self.person(BROOKE, "Brooke Baron", "Head of Production",
                        primary=True),
            self.person(JOSEPH, "Joseph O'Neill", "Design Director"),
        ]))
        config = self._config(
            **{"account.min_hours_between_first_touches": 24,
               "contact.min_hours_between_touches": 999})
        decision = na.next_best_action(
            rec, config=config, workspace=WS, estate=clear_estate(),
            at="2026-09-16T10:00:00+00:00", suppressed=set())
        self.assertEqual(decision["action"], na.ACT, decision["reason"])
        self.assertEqual(decision["person"], JOSEPH)

    def test_nobody_is_opened_simultaneously_by_default(self):
        """Six people at once is what four independently-correct plans
        produce. The account gate is what stops it.

        About a SECOND PERSON, which is what "opened simultaneously" means.
        It used to pass with one contact because the cross-channel minimum
        was 48 hours and refused the same person a second touch - a true
        answer to a different question. That minimum is zero now, on purpose:
        the LinkedIn-heavy cadence opens on both channels the same day, and
        the stagger that matters is between PEOPLE.
        """
        rec = self.opened(self.record(contacts=[
            self.person(BROOKE, "Brooke Baron", "Head of Production",
                        primary=True),
            self.person(JOSEPH, "Joseph O'Neill", "Design Director"),
        ]))
        decision = self.ask(rec, at="2026-09-14T09:30:00+00:00")
        self.assertNotEqual(decision["person"], JOSEPH,
                            "a second person was opened half an hour after "
                            "the first")


# ----------------------------------------------------------- the senders

class TheSenderIsAFactNotACalculation(NextActionTest):

    def test_a_stored_assignment_wins(self):
        rec = self.record()
        contact = rec["contacts"][0]
        # The channel the CADENCE opens on, not a channel typed in here.
        # Productive's day 1 is LinkedIn now, so an email assignment was
        # being looked up for a step that is not on email.
        opening = cadence.steps_for(config=clients.load("productive"))[0]
        channel = opening["channel"]
        contact["sender_assignment"] = {
            channel: {"sender_id": "mark", "account_id": "mark02",
                      "channel": channel, "workspace": WS}}
        store.save([rec])
        decision = self.ask(rec)
        self.assertEqual(decision["sender"]["sender_id"], "mark")

    def test_no_eligible_sender_is_a_wait_with_the_reason(self):
        si.install([r for r in roster() if r.get("kind") == "sender"])
        decision = self.ask(self.record())
        self.assertEqual(decision["action"], na.WAIT)
        self.assertEqual(decision["reason_code"], na.WAIT_NO_CANDIDATE)
        self.assertIn("owns an active", decision["reason"])


# -------------------------------------------------------- the experiment

def two_arm_experiment():
    short = cadencearms.arm("short", "Two steps", [
        {"key": "day1", "day": 1, "channel": "email", "generated": True},
        {"key": "day5", "day": 5, "channel": "email",
         "template": "persona_pain"}])
    li = cadencearms.arm("li_first", "LinkedIn first", [
        {"key": "day1li", "day": 1, "channel": "linkedin",
         "template": "linkedin_intro"},
        {"key": "day5", "day": 5, "channel": "email",
         "template": "persona_pain"}])
    return cadencearms.experiment("acct-shape-01", [short, li],
                                  unit=cadencearms.ACCOUNT)


class TheArmIsStickyAndItChangesWhatIsSent(NextActionTest):

    def campaign(self):
        return {"campaign_id": "c1", "client": WS,
                cadencearms.EXPERIMENT_KEY: two_arm_experiment()}

    def test_the_same_account_lands_in_the_same_arm_every_time(self):
        rec = self.record()
        first = self.ask(rec, campaign=self.campaign())["experiment"]["arm_id"]
        for _ in range(5):
            again = self.ask(rec, campaign=self.campaign())
            self.assertEqual(again["experiment"]["arm_id"], first)

    def test_it_survives_a_restart(self):
        """Deterministic on (experiment_id, unit_key, allocation_version),
        so a reload from disk with no recorded assignment lands in the same
        arm - and a recorded one outranks the calculation."""
        rec = self.record()
        before = self.ask(rec, campaign=self.campaign())["experiment"]["arm_id"]
        reloaded = next(r for r in store.load() if r["id"] == rec["id"])
        after = self.ask(reloaded,
                         campaign=self.campaign())["experiment"]["arm_id"]
        self.assertEqual(before, after)

    def test_two_accounts_do_not_all_land_in_one_arm(self):
        arms = set()
        for i in range(24):
            rec = self.record(rid=f"acct{i}")
            arms.add(self.ask(rec, campaign=self.campaign())["experiment"]["arm_id"])
        self.assertEqual(arms, {"short", "li_first"})

    def test_the_arm_changes_the_executed_step_graph(self):
        """An arm that assigns, reports and changes nothing about what is
        sent is a label. The arm has to reach the decision."""
        seen = {}
        for i in range(24):
            rec = self.record(rid=f"acct{i}")
            decision = self.ask(rec, campaign=self.campaign())
            if decision["action"] != na.ACT:
                continue
            seen.setdefault(decision["experiment"]["arm_id"], set()).add(
                (decision["channel"], decision["copy"]["step_key"]))
        self.assertEqual(seen["short"], {("email", "day1")})
        self.assertEqual(seen["li_first"], {("linkedin", "day1li")})

    def test_assignment_is_not_exposure(self):
        """An account in an arm has been exposed to nothing until a touch
        is confirmed, and this decision is a plan rather than a touch."""
        rec = self.record()
        decision = self.ask(rec, campaign=self.campaign())
        self.assertEqual(decision["counts"]["touches"], 0)
        self.assertIsNone(account.graph(rec, workspace=WS)["by_contact"]
                          [BROOKE]["last_touch_at"])


# ----------------------------------------------------- the productive file

class ProductiveHasChosenItsNumbers(NextActionTest):

    def test_every_fatigue_limit_is_configured_rather_than_defaulted(self):
        """A screen showing 'max 3 per week' without saying whether anybody
        chose 3 invites an operator to treat a default as a decision."""
        limits = fatigue.limits(clients.load("productive"))
        unchosen = sorted(k for k, v in limits.items() if not v["configured"])
        self.assertEqual(unchosen, [])

    def test_the_account_week_is_not_looser_than_the_pilot_ceiling(self):
        from src import pilotcaps

        config = clients.load("productive")
        limits = fatigue.limits(config)
        self.assertLessEqual(
            limits["account.max_touches_per_week"]["value"],
            pilotcaps.CEILING["touches_per_account_per_week"],
            "fatigue is what actually binds - executionguard never reads "
            "the touches_per_account_per_week ceiling - so the configured "
            "number has to be the safe one on its own")

    def test_the_configured_account_week_reaches_a_decision(self):
        """Existence is not function. The file could carry perfect numbers
        that nothing reads. Four touches at one company is the configured
        week, and it is the number the account gate refuses on - at the
        library default of 8 this same record would be actionable."""
        rec = self.record()
        # DERIVED, not typed. This filled the week with four touches because
        # four was the configured cap when it was written; the cadence change
        # of 2026-09-13 raised it to eight and the test then proved nothing.
        # The number under test is the CONFIGURED one, so it is read.
        config = clients.load("productive")
        cap = fatigue.limits(config)["account.max_touches_per_week"]["value"]
        for i in range(cap):
            self.touch(rec, BROOKE, "anna", "email", i + 1,
                       f"2026-09-{10 + i:02d}T09:00:00+00:00")
        decision = na.next_best_action(
            rec, config=clients.load("productive"), workspace=WS,
            estate=clear_estate(), at="2026-09-14T09:00:00+00:00",
            suppressed=set())
        self.assertEqual(decision["action"], na.WAIT)
        self.assertEqual(decision["reason_code"], na.WAIT_ACCOUNT_FATIGUE)

        loose = self._config(**{"account.max_touches_per_week": cap * 4})
        counterfactual = na.next_best_action(
            rec, config=loose, workspace=WS, estate=clear_estate(),
            at="2026-09-14T09:00:00+00:00", suppressed=set())
        self.assertNotEqual(counterfactual["reason_code"],
                            na.WAIT_ACCOUNT_FATIGUE)

    def test_the_configured_contact_pace_reaches_a_decision(self):
        """The other half: a person four touches into their own week is
        refused, and the library default of 3 would have refused them a
        step earlier - which is the default blocking this system's own
        shipped cadence at day 8."""
        rec = self.record()
        config = clients.load("productive")
        cap = fatigue.limits(config)["contact.max_touches_per_week"]["value"]
        for i in range(cap):
            self.touch(rec, BROOKE, "anna", "email", i + 1,
                       f"2026-09-{10 + i:02d}T09:00:00+00:00")
        decision = na.next_best_action(
            rec, config=clients.load("productive"), workspace=WS,
            estate=clear_estate(), at="2026-09-14T09:00:00+00:00",
            suppressed=set())
        # The contact-level refusal, asserted against `fatigue` directly so
        # this test fails for its own reason rather than for the account's.
        self.assertEqual(
            fatigue.contact_check(rec, BROOKE, at="2026-09-14T09:00:00+00:00",
                                  config=clients.load("productive"))["state"],
            fatigue.BLOCK)
        # AND THE PLANNER PASSES OVER THEM, which is not the same as
        # stopping. This asserted the whole account waits, and that was only
        # true because the account cap fired first at the old numbers. With
        # the account week raised for the LinkedIn-heavy cadence the account
        # still has room, so the right answer is that somebody ELSE is
        # chosen - a person at their limit is skipped, not a company halted.
        self.assertNotEqual(decision["person"], BROOKE, decision["reason"])


if __name__ == "__main__":
    unittest.main()
