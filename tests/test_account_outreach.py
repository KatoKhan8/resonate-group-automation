"""Account-based outreach: the graph, the claims, the fatigue, the referrals.

The property this whole file exists to defend:

    A message may only say a thing about our prior outreach if that thing
    actually happened.

Everything else here supports that one sentence. The account graph is what
"actually happened" means; the claim resolver is what "may say" means; the
fatigue rules are what stops four people saying it in the same week.

The tests are written so that each one fails for a *different* reason. A file
where every test would fail together is a file with one test in it, and the
mutation audit is what proves the difference.
"""
import unittest

from src import account, cadencegraph as cg, events, fatigue
from src import outreachclaims as oc
from src import senderidentity as si, senderteam as st, store
from tests.campaignbase import CampaignTest

WS = "productive"

# Three decision makers at one company, which is the shape the old model
# could not express.
JOHN = "john"
SARAH = "sarah"
MIKE = "mike"


def roster():
    """Two email humans and two LinkedIn humans - four, not two."""
    return [
        si.new_sender(WS, "anna", "Anna Novak", team="growth"),
        si.new_sender(WS, "mark", "Mark Reilly", team="growth"),
        si.new_sender(WS, "petar", "Petar Horvat", team="growth"),
        si.new_sender(WS, "sara_s", "Sara Simic", team="growth"),
        si.new_email_account(WS, "anna07", "anna", "anna07@productive.test"),
        si.new_email_account(WS, "mark02", "mark", "mark02@productive.test"),
        si.new_linkedin_account(WS, "petar-li", "petar",
                                "https://www.linkedin.com/in/petar"),
        si.new_linkedin_account(WS, "sara-li", "sara_s",
                                "https://www.linkedin.com/in/sara"),
    ]


class AccountTest(CampaignTest):

    def setUp(self):
        super().setUp()
        si.install(roster())

    def record(self, rid="acme"):
        rec = store.new_record(rid, "domains", WS, "Acme Ltd", "acme.test")
        rec["contacts"] = [
            {"key": JOHN, "name": "John Smith", "title": "COO",
             "email": "john@acme.test", "selected": True, "primary": True,
             "priority": account.PRIMARY,
             "linkedin": "https://www.linkedin.com/in/johnsmith"},
            {"key": SARAH, "name": "Sarah Jones", "title": "CEO",
             "email": "sarah@acme.test", "selected": True,
             "priority": account.SECONDARY,
             "linkedin": "https://www.linkedin.com/in/sarahjones"},
            {"key": MIKE, "name": "Michael Green", "title": "CFO",
             "email": "mike@acme.test", "selected": True,
             "priority": account.TERTIARY},
        ]
        rec["cadence"] = {}
        store.save([rec])
        return rec

    def touch(self, rec, contact_key, sender_id, channel, day, at=None,
              confirmed=True):
        events.record(rec, events.PUSH_MARKED if confirmed
                      else events.PUSH_PREPARED,
                      contact_key=contact_key, channel=channel, day=day,
                      sender_id=sender_id, at=at,
                      account_id=f"{sender_id}-acct")
        return rec

    def reply(self, rec, contact_key, at=None, positive=False):
        events.record(rec, events.REPLY_RECEIVED, contact_key=contact_key,
                      channel="email", at=at)
        if positive:
            events.record(rec, events.POSITIVE_REPLY_DETECTED,
                          contact_key=contact_key, channel="email", at=at)
        return rec

    def refer(self, rec, from_key, to_key, at=None):
        events.record(rec, events.REFERRAL_RECORDED, contact_key=from_key,
                      referred_to=to_key, channel="email", at=at)
        return rec


# ------------------------------------------------------------- the graph

class TheAccountGraph(AccountTest):

    def test_it_knows_every_decision_maker(self):
        graph = account.graph(self.record(), WS)
        self.assertEqual(graph["counts"]["decision_makers"], 3)
        self.assertEqual({c["key"] for c in graph["contacts"]},
                         {JOHN, SARAH, MIKE})

    def test_a_planned_touch_is_not_a_contacted_contact(self):
        """The distinction the whole architecture rests on."""
        rec = self.touch(self.record(), JOHN, "anna", "email", 1,
                         confirmed=False)
        graph = account.graph(rec, WS)
        self.assertEqual(graph["counts"]["contacted"], 0)
        self.assertEqual(graph["counts"]["planned"], 1)
        self.assertEqual(graph["by_contact"][JOHN]["state"],
                         account.NOT_STARTED)

    def test_a_confirmed_touch_is(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        graph = account.graph(rec, WS)
        self.assertEqual(graph["counts"]["contacted"], 1)
        self.assertEqual(graph["by_contact"][JOHN]["state"], account.ACTIVE)

    def test_it_records_which_human_and_which_account(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        touch = account.graph(rec, WS)["by_contact"][JOHN]["touches"][0]
        self.assertEqual(touch["sender_id"], "anna")
        self.assertEqual(touch["account_id"], "anna-acct")

    def test_one_contact_can_be_touched_by_four_humans(self):
        """The case the old one-email-one-LinkedIn model could not hold."""
        rec = self.record()
        self.touch(rec, JOHN, "anna", "email", 1)
        self.touch(rec, JOHN, "mark", "email", 5)
        self.touch(rec, JOHN, "petar", "linkedin", 3)
        self.touch(rec, JOHN, "sara_s", "linkedin", 8)
        entry = account.graph(rec, WS)["by_contact"][JOHN]
        self.assertEqual(len(entry["confirmed_touches"]), 4)
        self.assertEqual(entry["sender_names"],
                         ["Anna Novak", "Mark Reilly", "Petar Horvat",
                          "Sara Simic"])
        self.assertEqual(entry["channels"], ["email", "linkedin"])

    def test_the_account_team_is_who_actually_touched_it(self):
        rec = self.record()
        self.touch(rec, JOHN, "anna", "email", 1)
        self.touch(rec, SARAH, "petar", "linkedin", 3)
        team = account.team_for(rec, WS)
        self.assertEqual(team, {"email": ["Anna Novak"],
                               "linkedin": ["Petar Horvat"]})

    def test_a_reply_pauses_every_contact_not_only_the_replier(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        rec["paused"] = {"since": store.now(), "reason": "reply_received"}
        graph = account.graph(rec, WS)
        for key in (JOHN, SARAH, MIKE):
            self.assertEqual(graph["by_contact"][key]["state"],
                             account.PAUSED, key)

    def test_an_unselected_contact_still_appears(self):
        """Knowing a CFO exists but was not selected is worth seeing."""
        rec = self.record()
        rec["contacts"][2]["selected"] = False
        graph = account.graph(rec, WS)
        self.assertIn(MIKE, graph["by_contact"])
        self.assertFalse(graph["by_contact"][MIKE]["selected"])

    def test_a_reassignment_does_not_rewrite_who_sent_what(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        rec["contacts"][0]["senders"] = {"email": {"sender_id": "mark"}}
        touch = account.graph(rec, WS)["by_contact"][JOHN]["touches"][0]
        self.assertEqual(touch["sender_id"], "anna",
                         "history followed the current assignment")


class TheAccountTimeline(AccountTest):

    def test_it_interleaves_touches_replies_and_referrals(self):
        rec = self.record()
        self.touch(rec, JOHN, "anna", "email", 1, at="2026-08-01T09:00:00+00:00")
        self.touch(rec, JOHN, "petar", "linkedin", 3,
                   at="2026-08-03T09:00:00+00:00")
        self.touch(rec, SARAH, "mark", "email", 4,
                   at="2026-08-04T09:00:00+00:00")
        self.reply(rec, JOHN, at="2026-08-05T09:00:00+00:00")
        self.refer(rec, JOHN, SARAH, at="2026-08-05T10:00:00+00:00")
        feed = account.timeline(rec, WS)
        self.assertEqual([e["kind"] for e in feed],
                         ["touch", "touch", "touch", "reply", "referral"])

    def test_each_entry_names_the_human_and_the_contact(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        entry = account.timeline(rec, WS)[0]
        self.assertEqual(entry["sender"], "Anna Novak")
        self.assertEqual(entry["contact"], "John Smith")
        self.assertIn("Anna Novak to John Smith", entry["summary"])

    def test_a_referral_says_who_referred_whom(self):
        rec = self.refer(self.record(), JOHN, SARAH)
        entry = [e for e in account.timeline(rec, WS)
                 if e["kind"] == "referral"][0]
        self.assertIn("John Smith referred us to Sarah Jones",
                      entry["summary"])


class ReferralsAreRecordedNotInferred(AccountTest):

    def test_a_recorded_referral_is_an_edge(self):
        rec = self.refer(self.record(), JOHN, SARAH)
        edges = account.referrals(rec)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["from_contact"], JOHN)
        self.assertEqual(edges[0]["to_contact"], SARAH)

    def test_a_reply_alone_is_not_a_referral(self):
        """"Sarah handles this" in free text creates nothing."""
        rec = self.reply(self.record(), JOHN)
        self.assertEqual(account.referrals(rec), [])
        self.assertIsNone(account.referred_by(rec, SARAH))

    def test_an_edge_missing_a_target_is_ignored(self):
        rec = self.record()
        events.record(rec, events.REFERRAL_RECORDED, contact_key=JOHN)
        self.assertEqual(account.referrals(rec), [])


# -------------------------------------------------------------- the claims

class TheClaimLadder(AccountTest):
    """Each rung needs its own evidence, and refuses without it."""

    def allow_everything(self):
        return {"outreach": {
            "claim_same_contact": "on", "claim_colleague": "on",
            "claim_other_dm": "on", "claim_other_dm_colleague": "on",
            "claim_other_dm_reply": "on", "claim_referral": "on",
            "claim_conversation": "on"}}

    # -- same contact

    def test_own_prior_touch_needs_a_confirmed_touch(self):
        rec = self.record()
        refused = oc.resolve(oc.SAME_CONTACT_PRIOR_TOUCH, rec, JOHN, WS,
                             sender_id="anna", config=self.allow_everything())
        self.assertFalse(refused)
        self.touch(rec, JOHN, "anna", "email", 1)
        allowed = oc.resolve(oc.SAME_CONTACT_PRIOR_TOUCH, rec, JOHN, WS,
                             sender_id="anna", config=self.allow_everything())
        self.assertTrue(allowed)

    def test_a_planned_touch_does_not_support_it(self):
        """planned != contacted. The single most important line here."""
        rec = self.touch(self.record(), JOHN, "anna", "email", 1,
                         confirmed=False)
        self.assertFalse(oc.resolve(oc.SAME_CONTACT_PRIOR_TOUCH, rec, JOHN,
                                    WS, sender_id="anna",
                                    config=self.allow_everything()))

    def test_a_colleagues_touch_does_not_support_your_own_claim(self):
        rec = self.touch(self.record(), JOHN, "mark", "email", 1)
        self.assertFalse(oc.resolve(oc.SAME_CONTACT_PRIOR_TOUCH, rec, JOHN,
                                    WS, sender_id="anna",
                                    config=self.allow_everything()))

    # -- colleague

    def test_colleague_handoff_needs_that_colleagues_touch(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        allowed = oc.resolve(oc.SAME_CONTACT_COLLEAGUE_TOUCH, rec, JOHN, WS,
                             sender_id="petar", about_sender="anna",
                             config=self.allow_everything())
        self.assertTrue(allowed)
        self.assertIn("Anna Novak", allowed["why"])

    def test_naming_a_colleague_who_did_not_write_is_refused(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        self.assertFalse(oc.resolve(oc.SAME_CONTACT_COLLEAGUE_TOUCH, rec,
                                    JOHN, WS, sender_id="petar",
                                    about_sender="mark",
                                    config=self.allow_everything()))

    def test_you_are_not_your_own_colleague(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        decision = oc.resolve(oc.SAME_CONTACT_COLLEAGUE_TOUCH, rec, JOHN, WS,
                              sender_id="anna", about_sender="anna",
                              config=self.allow_everything())
        self.assertFalse(decision)
        self.assertIn("not a colleague", decision["why"])

    # -- other decision makers

    def test_other_dm_touch_needs_a_touch_to_that_person(self):
        rec = self.record()
        refused = oc.resolve(oc.OTHER_DM_PRIOR_TOUCH, rec, SARAH, WS,
                             sender_id="anna", about_contact=JOHN,
                             config=self.allow_everything())
        self.assertFalse(refused)
        self.touch(rec, JOHN, "anna", "email", 1)
        self.assertTrue(oc.resolve(oc.OTHER_DM_PRIOR_TOUCH, rec, SARAH, WS,
                                   sender_id="anna", about_contact=JOHN,
                                   config=self.allow_everything()))

    def test_the_recipient_is_not_another_decision_maker(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        decision = oc.resolve(oc.OTHER_DM_PRIOR_TOUCH, rec, JOHN, WS,
                              sender_id="anna", about_contact=JOHN,
                              config=self.allow_everything())
        self.assertFalse(decision)
        self.assertIn("that is the recipient", decision["why"])

    def test_other_dm_reply_needs_a_reply(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        self.assertFalse(oc.resolve(oc.OTHER_DM_REPLY, rec, SARAH, WS,
                                    about_contact=JOHN,
                                    config=self.allow_everything()))
        self.reply(rec, JOHN)
        self.assertTrue(oc.resolve(oc.OTHER_DM_REPLY, rec, SARAH, WS,
                                   about_contact=JOHN,
                                   config=self.allow_everything()))

    # -- referral

    def test_referral_needs_a_recorded_edge(self):
        rec = self.reply(self.record(), JOHN)
        self.assertFalse(oc.resolve(oc.REFERRAL, rec, SARAH, WS,
                                    config=self.allow_everything()),
                         "a reply was read as a referral")
        self.refer(rec, JOHN, SARAH)
        allowed = oc.resolve(oc.REFERRAL, rec, SARAH, WS,
                             config=self.allow_everything())
        self.assertTrue(allowed)
        self.assertEqual(allowed["referred_by"], JOHN)

    def test_a_referral_to_somebody_else_does_not_license_this_one(self):
        rec = self.refer(self.record(), JOHN, MIKE)
        self.assertFalse(oc.resolve(oc.REFERRAL, rec, SARAH, WS,
                                    config=self.allow_everything()))

    def test_naming_the_wrong_referrer_is_refused(self):
        rec = self.refer(self.record(), JOHN, SARAH)
        decision = oc.resolve(oc.REFERRAL, rec, SARAH, WS,
                              about_contact=MIKE,
                              config=self.allow_everything())
        self.assertFalse(decision)
        self.assertIn("somebody else", decision["why"])

    # -- conversation, the hardest rung

    def test_a_sent_message_is_not_a_conversation(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        decision = oc.resolve(oc.ACTIVE_CONVERSATION, rec, SARAH, WS,
                              about_contact=JOHN,
                              config=self.allow_everything())
        self.assertFalse(decision)
        self.assertIn("has not replied", decision["why"])

    def test_a_reply_alone_is_not_a_conversation(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1,
                         at="2026-08-01T09:00:00+00:00")
        self.reply(rec, JOHN, at="2026-08-02T09:00:00+00:00")
        decision = oc.resolve(oc.ACTIVE_CONVERSATION, rec, SARAH, WS,
                              about_contact=JOHN,
                              config=self.allow_everything())
        self.assertFalse(decision)
        self.assertIn("nobody has answered", decision["why"])

    def test_reply_then_answer_is_a_conversation(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1,
                         at="2026-08-01T09:00:00+00:00")
        self.reply(rec, JOHN, at="2026-08-02T09:00:00+00:00")
        self.touch(rec, JOHN, "anna", "email", 3,
                   at="2026-08-03T09:00:00+00:00")
        self.assertTrue(oc.resolve(oc.ACTIVE_CONVERSATION, rec, SARAH, WS,
                                   about_contact=JOHN,
                                   config=self.allow_everything()))


class PolicyIsCheckedBeforeEvidence(AccountTest):
    """Evidence existing is not permission to use it."""

    def test_third_party_claims_are_off_by_default(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        decision = oc.resolve(oc.OTHER_DM_PRIOR_TOUCH, rec, SARAH, WS,
                              sender_id="anna", about_contact=JOHN)
        self.assertFalse(decision)
        self.assertIs(decision["policy"], False)
        self.assertIn("does not allow", decision["why"])

    def test_own_prior_touch_is_on_by_default(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        self.assertTrue(oc.resolve(oc.SAME_CONTACT_PRIOR_TOUCH, rec, JOHN, WS,
                                   sender_id="anna"))

    def test_a_refusal_distinguishes_policy_from_evidence(self):
        """Two different problems with two different fixes."""
        rec = self.record()
        no_evidence = oc.resolve(oc.SAME_CONTACT_PRIOR_TOUCH, rec, JOHN, WS,
                                 sender_id="anna")
        self.assertIs(no_evidence["policy"], True)
        self.assertIn("no confirmed touch", no_evidence["why"])

        self.touch(rec, JOHN, "anna", "email", 1)
        off = oc.resolve(oc.SAME_CONTACT_PRIOR_TOUCH, rec, JOHN, WS,
                         sender_id="anna",
                         config={"outreach": {"claim_same_contact": "off"}})
        self.assertIs(off["policy"], False)

    def test_an_unknown_claim_type_is_refused(self):
        self.assertFalse(oc.resolve("whatever", self.record(), JOHN, WS))


class WhatThePreviewShows(AccountTest):

    def test_it_lists_every_claim_with_a_reason(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        listed = oc.available(rec, JOHN, WS, sender_id="anna")
        self.assertEqual(len(listed), len(oc.TYPES))
        for entry in listed:
            self.assertTrue(entry["why"], entry["claim"])

    def test_an_allowed_claim_carries_its_evidence(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        listed = oc.available(rec, JOHN, WS, sender_id="anna")
        allowed = [c for c in listed if c["allowed"]]
        self.assertTrue(allowed)
        for entry in allowed:
            self.assertIsNotNone(entry["evidence"], entry["claim"])


# ------------------------------------------------------------- the fatigue

class ContactFatigue(AccountTest):

    def test_no_touches_is_fine(self):
        verdict = fatigue.contact_check(self.record(), JOHN)
        self.assertEqual(verdict["state"], fatigue.OK)

    def test_a_fourth_touch_in_a_week_is_blocked(self):
        rec = self.record()
        for day, at in enumerate(("2026-08-01T09:00:00+00:00",
                                  "2026-08-02T09:00:00+00:00",
                                  "2026-08-03T09:00:00+00:00"), start=1):
            self.touch(rec, JOHN, "anna", "email", day, at=at)
        verdict = fatigue.contact_check(rec, JOHN,
                                        at="2026-08-04T09:00:00+00:00")
        self.assertEqual(verdict["state"], fatigue.BLOCK)

    def test_two_touches_in_one_hour_is_blocked(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1,
                         at="2026-08-01T09:00:00+00:00")
        verdict = fatigue.contact_check(rec, JOHN,
                                        at="2026-08-01T10:00:00+00:00")
        self.assertEqual(verdict["state"], fatigue.BLOCK)
        self.assertIn("since the last touch",
                      " ".join(f["why"] for f in verdict["findings"]))

    def test_three_different_humans_in_a_week_warns(self):
        """Nobody planned it; it is what three correct plans produce."""
        rec = self.record()
        for sender, at in (("anna", "2026-08-01T09:00:00+00:00"),
                           ("mark", "2026-08-02T09:00:00+00:00"),
                           ("petar", "2026-08-03T09:00:00+00:00")):
            self.touch(rec, JOHN, sender, "email", 1, at=at)
        verdict = fatigue.contact_check(rec, JOHN)
        self.assertIn("different people",
                      " ".join(f["why"] for f in verdict["findings"]))

    def test_a_configured_limit_replaces_the_default(self):
        rec = self.record()
        for day, at in enumerate(("2026-08-01T09:00:00+00:00",
                                  "2026-08-02T09:00:00+00:00",
                                  "2026-08-03T09:00:00+00:00"), start=1):
            self.touch(rec, JOHN, "anna", "email", day, at=at)
        loose = {"fatigue": {"contact": {"max_touches_per_week": 10,
                                         "min_hours_between_touches": 1}}}
        verdict = fatigue.contact_check(rec, JOHN,
                                        at="2026-08-04T09:00:00+00:00",
                                        config=loose)
        self.assertNotEqual(verdict["state"], fatigue.BLOCK)

    def test_the_limits_say_whether_anybody_chose_them(self):
        default = fatigue.limits()["contact.max_touches_per_week"]
        self.assertFalse(default["configured"])
        chosen = fatigue.limits(
            {"fatigue": {"contact": {"max_touches_per_week": 5}}})
        self.assertTrue(chosen["contact.max_touches_per_week"]["configured"])


class AccountFatigue(AccountTest):

    def test_a_fourth_active_contact_is_blocked(self):
        rec = self.record()
        rec["contacts"].append({"key": "extra", "name": "Extra Person",
                                "email": "e@acme.test", "selected": True})
        for key in (JOHN, SARAH, MIKE):
            self.touch(rec, key, "anna", "email", 1,
                       at="2026-08-0%dT09:00:00+00:00" % (1 + len(key) % 3))
        verdict = fatigue.account_check(rec, contact_key="extra")
        self.assertEqual(verdict["state"], fatigue.BLOCK)
        self.assertIn("decision makers",
                      " ".join(f["why"] for f in verdict["findings"]))

    def test_two_people_opened_hours_apart_warns(self):
        rec = self.record()
        self.touch(rec, JOHN, "anna", "email", 1,
                   at="2026-08-01T09:00:00+00:00")
        self.touch(rec, SARAH, "mark", "email", 1,
                   at="2026-08-01T11:00:00+00:00")
        verdict = fatigue.account_check(rec)
        self.assertIn("apart", " ".join(f["why"] for f in verdict["findings"]))

    def test_both_levels_report_together(self):
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        verdict = fatigue.check(rec, JOHN)
        self.assertIn("contact", verdict)
        self.assertIn("account", verdict)
        self.assertIn(verdict["state"],
                      (fatigue.OK, fatigue.WARN, fatigue.BLOCK))


# --------------------------------------------------------------- the teams

class TheOutreachTeam(AccountTest):

    def team(self):
        return st.new_team(WS, "alpha", "Team Alpha",
                           email_senders=["anna", "mark"],
                           linkedin_senders=["petar", "sara_s"])

    def test_a_member_is_allowed(self):
        allowed, why = st.allows(self.team(), "anna", "email")
        self.assertTrue(allowed)

    def test_a_stranger_is_refused(self):
        allowed, why = st.allows(self.team(), "outsider")
        self.assertFalse(allowed)
        self.assertIn("must not enter", why)

    def test_the_right_person_on_the_wrong_channel_is_refused(self):
        allowed, why = st.allows(self.team(), "anna", "linkedin")
        self.assertFalse(allowed)
        self.assertIn("not for linkedin", why)

    def test_no_team_means_no_restriction_recorded_and_says_so(self):
        allowed, why = st.allows(None, "anybody")
        self.assertTrue(allowed)
        self.assertIn("no outreach team is configured", why)

    def test_an_empty_team_is_refused_at_construction(self):
        with self.assertRaises(st.TeamError):
            st.new_team(WS, "empty", "Nobody")

    def test_a_cadence_naming_an_outsider_is_blocked(self):
        graph = cg.from_template("standard", email_sender="outsider",
                                 linkedin_sender="petar")
        blocking = cg.blocking(cg.validate(graph, team=st.members(self.team())))
        self.assertTrue(blocking)
        self.assertIn("outreach team", blocking[0]["why"])


if __name__ == "__main__":
    unittest.main()


class TheCadenceGraphRefusesWhatItCannotRun(unittest.TestCase):
    """Structural guards, each with its own failing fixture.

    These were verified by hand while the module was written, which is not
    the same as being tested - the mutation audit reported both as uncaught,
    correctly, because nothing here would have failed if either guard were
    deleted.
    """

    def blocks(self, graph, team=None):
        return [f["why"] for f in cg.blocking(cg.validate(graph, team))]

    def test_an_unvalidated_provider_capability_is_blocked(self):
        """Present in the vocabulary, refused until somebody proves it.

        The brief names post reactions and connection withdrawal. No recorded
        contract here shows HeyReach doing either, so a cadence using one is
        refused rather than quietly planned against an assumption.
        """
        self.assertTrue(cg.UNVALIDATED,
                        "no node is marked unvalidated, so this proves "
                        "nothing")
        for kind in cg.UNVALIDATED:
            graph = cg.graph("x", [cg.node("a", kind, sender_id="petar")], "a")
            blocking = self.blocks(graph)
            self.assertTrue(blocking, kind)
            self.assertIn("validated", blocking[0])

    def test_a_validated_node_is_not_blocked_for_that_reason(self):
        """The other half: the check must not refuse everything."""
        graph = cg.graph("x", [cg.node("a", "email", day=1,
                                       sender_id="anna")], "a")
        self.assertEqual(self.blocks(graph), [])

    def test_a_cadence_that_loops_is_blocked(self):
        nodes = [cg.node("a", "email", day=1, sender_id="anna"),
                 cg.node("b", "email", day=2, sender_id="anna")]
        graph = cg.graph("loop", nodes, "a")
        cg.connect(graph, "a", "b")
        cg.connect(graph, "b", "a")
        blocking = self.blocks(graph)
        self.assertTrue(blocking)
        self.assertIn("loops back", blocking[0])

    def test_a_long_sequence_that_does_not_loop_is_fine(self):
        """A thirty-step cadence is not a cycle."""
        nodes = [cg.node(f"n{i}", "wait", wait_days=1) for i in range(30)]
        graph = cg.graph("long", nodes, "n0")
        for i in range(29):
            cg.connect(graph, f"n{i}", f"n{i + 1}")
        self.assertEqual(self.blocks(graph), [])
        self.assertEqual(len(cg.walk(graph)), 30)

    def test_a_dangling_branch_is_blocked(self):
        graph = cg.graph("x", [cg.node("a", "email", day=1,
                                       sender_id="anna")], "a")
        graph["nodes"]["a"]["next"]["yes"] = "nowhere"
        self.assertIn("does not exist", self.blocks(graph)[0])

    def test_a_wait_with_no_duration_is_blocked(self):
        graph = cg.graph("x", [cg.node("a", "wait")], "a")
        self.assertIn("waits forever", self.blocks(graph)[0])

    def test_a_branch_with_no_condition_is_blocked(self):
        graph = cg.graph("x", [cg.node("a", "branch")], "a")
        self.assertIn("cannot branch", self.blocks(graph)[0])

    def test_a_contacting_node_with_no_sender_is_blocked(self):
        graph = cg.graph("x", [cg.node("a", "email", day=1)], "a")
        self.assertIn("no sender", self.blocks(graph)[0])

    def test_every_template_validates(self):
        team = ["anna", "mark", "petar", "sara_s"]
        for key in cg.TEMPLATES:
            graph = cg.from_template(key, email_sender="anna",
                                     linkedin_sender="petar",
                                     second_email="mark",
                                     second_linkedin="sara_s")
            self.assertEqual(self.blocks(graph, team), [], key)

    def test_a_wait_is_not_counted_as_a_touch(self):
        """Fatigue counts contacting nodes; a wait is not one."""
        graph = cg.from_template("standard", email_sender="anna",
                                 linkedin_sender="petar")
        touching = {n["type"] for n in cg.steps_of(graph)}
        self.assertNotIn("wait", touching)
        self.assertNotIn("branch", touching)
        self.assertIn("email", touching)

    def test_an_old_cadence_is_read_under_its_own_version(self):
        from src import cadence

        graph = cg.from_legacy(cadence.STEPS, "anna", "petar")
        self.assertEqual(graph["version"], 1)
        findings = cg.validate(graph)
        self.assertTrue(any("schema version" in f["why"] for f in findings),
                        "an old graph was read as if it were current")


class TheSentenceIsBuiltFromItsOwnEvidence(AccountTest):
    """The P0 regression.

    A manual review found the account screen showing:

        ALLOWED  "my colleague Anna emailed you earlier this week"
                 evidence: Mark Weber confirmed email on day 6

    The resolver was right - the evidence really was Mark's. `CLAIMS` held a
    hardcoded illustration naming a different colleague, and the screen
    rendered it as the sentence this message would say. An operator reading
    that row would have believed a sentence about Anna had been cleared.

    Every test here asserts the same property from a different angle: the
    person named in the sentence is the person in the evidence.
    """

    def allow_everything(self):
        return {"outreach": {
            "claim_same_contact": "on", "claim_colleague": "on",
            "claim_other_dm": "on", "claim_other_dm_colleague": "on",
            "claim_other_dm_reply": "on", "claim_referral": "on",
            "claim_conversation": "on"}}

    def two_senders(self):
        """Anna wrote to John. Mark wrote to Sarah. Nobody else wrote."""
        rec = self.record()
        self.touch(rec, JOHN, "anna", "email", 1,
                   at="2026-08-01T09:00:00+00:00")
        self.touch(rec, SARAH, "mark", "email", 6,
                   at="2026-08-06T09:00:00+00:00")
        return rec

    def test_the_exact_reported_case(self):
        """Asking about Sarah must never produce a sentence naming Anna."""
        rec = self.two_senders()
        listed = oc.available(rec, SARAH, WS, sender_id="sara_s",
                              config=self.allow_everything())
        colleague = next(c for c in listed
                         if c["claim"] == oc.SAME_CONTACT_COLLEAGUE_TOUCH)
        self.assertTrue(colleague["allowed"])
        self.assertIn("Mark Reilly", colleague["phrase"])
        self.assertNotIn("Anna", colleague["phrase"])
        self.assertIn("Mark Reilly", colleague["why"])

    def test_no_allowed_sentence_names_somebody_absent_from_its_evidence(self):
        """The general form of the bug, swept over every claim and contact."""
        rec = self.two_senders()
        self.reply(rec, JOHN, at="2026-08-07T09:00:00+00:00")
        self.refer(rec, JOHN, SARAH, at="2026-08-07T10:00:00+00:00")
        names = {"anna": "Anna Novak", "mark": "Mark Reilly",
                 "petar": "Petar Horvat", "sara_s": "Sara Simic"}
        people = {JOHN: "John Smith", SARAH: "Sarah Jones",
                  MIKE: "Michael Green"}

        offenders = []
        for contact_key in (JOHN, SARAH, MIKE):
            for sender_id in names:
                for claim in oc.available(rec, contact_key, WS, sender_id,
                                          self.allow_everything()):
                    if not claim["allowed"] or not claim["phrase"]:
                        continue
                    sentence = claim["phrase"]
                    evidence = claim["evidence"] or {}
                    permitted = {
                        names.get(claim["about_sender"]),
                        people.get(claim["about_contact"]),
                        people.get(evidence.get("from_contact")
                                   if isinstance(evidence, dict) else None),
                    }
                    for who in list(names.values()) + list(people.values()):
                        if who in sentence and who not in permitted:
                            offenders.append(
                                f"{claim['claim']} to {contact_key} as "
                                f"{sender_id}: names {who} but its evidence "
                                f"is {claim['why']!r}")
        self.assertEqual(sorted(set(offenders)), [],
                         chr(10).join(sorted(set(offenders))))

    def test_a_refused_claim_names_nobody_at_all(self):
        """A refusal has no evidence, so it must not invent a person."""
        rec = self.record()
        for claim in oc.available(rec, SARAH, WS, sender_id="mark",
                                  config=self.allow_everything()):
            self.assertFalse(claim["allowed"])
            self.assertIsNone(claim["phrase"])
            for who in ("Anna", "Mark", "Petar", "Sara", "John", "Sarah",
                        "Michael"):
                self.assertNotIn(who, claim["example"], claim["claim"])

    def test_the_template_carries_no_person(self):
        """The class of bug, checked at its source."""
        for claim_type, entry in oc.CLAIMS.items():
            template = entry[1]
            for who in ("Anna", "Mark", "Petar", "Sara", "John", "Sarah",
                        "Michael"):
                self.assertNotIn(who, template, claim_type)

    def test_a_referral_sentence_names_the_referrer(self):
        rec = self.two_senders()
        self.refer(rec, JOHN, SARAH, at="2026-08-07T10:00:00+00:00")
        decision = oc.resolve(oc.REFERRAL, rec, SARAH, WS,
                              config=self.allow_everything())
        sentence = oc.phrase(oc.REFERRAL, decision, rec, WS)
        self.assertIn("John Smith", sentence)
        self.assertNotIn("Michael", sentence)

    def test_an_other_dm_sentence_names_that_decision_maker(self):
        rec = self.two_senders()
        decision = oc.resolve(oc.OTHER_DM_PRIOR_TOUCH, rec, SARAH, WS,
                              sender_id="anna", about_contact=JOHN,
                              config=self.allow_everything())
        sentence = oc.phrase(oc.OTHER_DM_PRIOR_TOUCH, decision, rec, WS)
        self.assertIn("John Smith", sentence)
        self.assertNotIn("Michael Green", sentence)

    def test_the_verb_follows_the_channel_in_the_evidence(self):
        rec = self.record()
        self.touch(rec, JOHN, "petar", "linkedin", 3,
                   at="2026-08-03T09:00:00+00:00")
        decision = oc.resolve(oc.SAME_CONTACT_COLLEAGUE_TOUCH, rec, JOHN, WS,
                              sender_id="anna", about_sender="petar",
                              config=self.allow_everything())
        sentence = oc.phrase(oc.SAME_CONTACT_COLLEAGUE_TOUCH, decision, rec,
                             WS)
        self.assertIn("messaged", sentence)
        self.assertNotIn("emailed", sentence)

    def test_a_sentence_is_never_produced_for_a_refused_claim(self):
        rec = self.record()
        refused = oc.resolve(oc.SAME_CONTACT_PRIOR_TOUCH, rec, JOHN, WS,
                             sender_id="anna")
        self.assertIsNone(oc.phrase(oc.SAME_CONTACT_PRIOR_TOUCH, refused,
                                    rec, WS))

    def test_a_sentence_needing_a_name_it_cannot_find_is_not_produced(self):
        """Better no sentence than one with a blank where a person goes."""
        decision = oc.Decision(allowed=True, claim=oc.REFERRAL,
                               why="x", evidence={})
        self.assertIsNone(oc.phrase(oc.REFERRAL, decision, None, WS))


class TemporalLanguageFollowsTheDate(unittest.TestCase):
    """"Earlier this week" is a claim about a date, checkable by the reader."""

    def at(self, day, hour=9):
        return {"at": f"2026-08-{day:02d}T{hour:02d}:00:00+00:00"}

    def now(self, day, hour=12):
        import datetime

        return datetime.datetime(2026, 8, day, hour,
                                 tzinfo=datetime.timezone.utc)

    def test_today(self):
        self.assertEqual(oc.when(self.at(12), self.now(12)), " earlier today")

    def test_yesterday(self):
        self.assertEqual(oc.when(self.at(11), self.now(12)), " yesterday")

    def test_earlier_this_week(self):
        # Monday 10th to Wednesday 12th: same ISO week.
        self.assertEqual(oc.when(self.at(10), self.now(12)),
                         " earlier this week")

    def test_a_few_days_ago_when_the_week_boundary_intervenes(self):
        # Saturday 8th to Monday 10th: two days, different ISO weeks.
        self.assertEqual(oc.when(self.at(8), self.now(10)), " a few days ago")

    def test_last_week(self):
        self.assertEqual(oc.when(self.at(3), self.now(12)), " last week")

    def test_anything_older_is_only_recently(self):
        self.assertEqual(oc.when(self.at(1), self.now(28)), " recently")

    def test_an_unreadable_date_produces_no_phrase(self):
        self.assertEqual(oc.when({"at": "not a date"}, self.now(12)), "")

    def test_a_missing_date_produces_no_phrase(self):
        self.assertEqual(oc.when({}, self.now(12)), "")
        self.assertEqual(oc.when(None, self.now(12)), "")

    def test_a_future_date_produces_no_phrase(self):
        """Nothing honest can be said about a touch that has not happened."""
        self.assertEqual(oc.when(self.at(20), self.now(12)), "")

    def test_every_phrase_starts_with_a_space_or_is_empty(self):
        """The templates concatenate it directly; a missing space runs words
        together and a trailing one shows as a gap before a full stop."""
        for day in range(1, 29):
            value = oc.when(self.at(day), self.now(28))
            self.assertTrue(value == "" or value.startswith(" "), value)
            self.assertFalse(value.endswith(" "), value)


class ARealisticCadence(unittest.TestCase):
    """Thirty-nine nodes, four humans, six phases, eight branches.

    The point is not the size. It is that every primitive the brief asks for
    appears in one plausible sequence, and that the model holds it without
    anything special-casing "long".
    """

    def graph(self):
        from src.web import democadence

        return democadence.build()

    def test_it_is_actually_complex(self):
        summary = cg.describe(self.graph())
        self.assertGreaterEqual(summary["nodes"], 30)
        self.assertGreaterEqual(summary["branches"], 6)
        self.assertGreaterEqual(summary["touches"], 10)

    def test_two_email_humans_and_two_linkedin_humans(self):
        """The shape a one-sender-per-channel model could not express."""
        graph = self.graph()
        email = {n["sender_id"] for n in cg.steps_of(graph)
                 if n["channel"] == "email"}
        linkedin = {n["sender_id"] for n in cg.steps_of(graph)
                    if n["channel"] == "linkedin"}
        self.assertGreaterEqual(len(email), 2, email)
        self.assertGreaterEqual(len(linkedin), 2, linkedin)

    def test_more_than_one_decision_maker_is_targeted(self):
        self.assertGreaterEqual(len(cg.roles_of(self.graph())), 3)

    def test_a_second_linkedin_profile_takes_over(self):
        """Petar opens; Sara continues where he stalled."""
        graph = self.graph()
        petar = [n for n in cg.steps_of(graph)
                 if n["sender_id"] == "petar" and n["channel"] == "linkedin"]
        sara = [n for n in cg.steps_of(graph)
                if n["sender_id"] == "sara_s" and n["channel"] == "linkedin"]
        self.assertTrue(petar)
        self.assertTrue(sara)
        self.assertLess(min(n["day"] or 0 for n in petar),
                        min(n["day"] or 0 for n in sara))

    def test_it_has_a_long_re_engagement_arm(self):
        self.assertGreaterEqual(cg.describe(self.graph())["longest_wait"], 30)

    def test_it_validates_against_its_own_team(self):
        findings = cg.validate(self.graph(),
                               team=["anna", "mark", "petar", "sara_s"])
        self.assertEqual([f for f in findings if f["level"] == "block"], [])

    def test_a_sender_missing_from_the_team_blocks_it(self):
        """The team check has to bite on a realistic graph, not just a toy."""
        findings = cg.validate(self.graph(), team=["anna", "petar"])
        blocking = [f["why"] for f in findings if f["level"] == "block"]
        self.assertTrue(blocking)
        self.assertTrue(any("outreach team" in why for why in blocking))

    def test_the_team_finding_names_the_human_when_it_can(self):
        """"john is not on the team" beside a step saying "John Adeyemi".

        A reviewer reading an id in one line and a name in the next has to
        establish they are the same person before they can act on either.
        """
        findings = cg.validate(self.graph(), team=["anna", "petar"],
                               names={"mark": "Mark Weber",
                                      "sara_s": "Sara Simic"})
        blocking = " ".join(f["why"] for f in findings
                            if f["level"] == "block")
        self.assertIn("Mark Weber", blocking)
        self.assertNotIn("sara_s is not", blocking)

    def test_it_falls_back_to_the_id_rather_than_to_nothing(self):
        findings = cg.validate(self.graph(), team=["anna", "petar"],
                               names={})
        blocking = " ".join(f["why"] for f in findings
                            if f["level"] == "block")
        self.assertIn("mark", blocking)

    def test_every_branch_has_a_condition_somebody_can_read(self):
        graph = self.graph()
        for node in graph["nodes"].values():
            if node["type"] != "branch":
                continue
            self.assertIn(node["condition"], cg.CONDITIONS, node["key"])

    def test_it_does_not_loop(self):
        self.assertFalse(cg._has_cycle(self.graph()))

    def test_no_node_is_unreachable(self):
        findings = cg.validate(self.graph(),
                               team=["anna", "mark", "petar", "sara_s"])
        unreachable = [f for f in findings if "no path reaches" in f["why"]]
        self.assertEqual(unreachable, [], unreachable)


class PhasesMakeALongCadenceReadable(unittest.TestCase):

    def graph(self):
        from src.web import democadence

        return democadence.build()

    def test_every_node_lands_in_exactly_one_phase(self):
        graph = self.graph()
        grouped = cg.phases_of(graph)
        counted = sum(len(g["nodes"]) for g in grouped)
        self.assertEqual(counted, len(graph["nodes"]))
        keys = [n["key"] for g in grouped for n in g["nodes"]]
        self.assertEqual(len(keys), len(set(keys)))

    def test_a_phase_is_a_set_not_a_run(self):
        """The walk jumps between phases; grouping by runs fragments them.

        Before this, a six-phase cadence came back as twenty-three groups
        because the secondary-DM arm is reached from two places.
        """
        grouped = self.graph() and cg.phases_of(self.graph())
        self.assertLessEqual(len(grouped), 8)
        names = [g["phase"] for g in grouped]
        self.assertEqual(len(names), len(set(names)))

    def test_the_phases_come_back_in_running_order(self):
        names = [g["phase"] for g in cg.phases_of(self.graph())]
        self.assertEqual(names[0], cg.OPENING)
        self.assertEqual(names[-1], cg.CLOSING)

    def test_a_cadence_with_no_phases_is_one_group(self):
        graph = cg.from_template("standard", email_sender="anna",
                                 linkedin_sender="petar")
        self.assertEqual(len(cg.phases_of(graph)), 1)

    def test_a_workspace_may_name_its_own_phase(self):
        nodes = [cg.node("a", "email", day=1, sender_id="anna",
                         phase="Something we invented"),
                 cg.node("b", "stop", phase="Something we invented")]
        graph = cg.graph("x", nodes, "a")
        cg.connect(graph, "a", "b")
        self.assertEqual([g["phase"] for g in cg.phases_of(graph)],
                         ["Something we invented"])
