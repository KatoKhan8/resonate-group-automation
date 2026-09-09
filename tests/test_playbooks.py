"""Which approach fits this account, and what that rests on.

Four properties, and every test is one of them:

**It recommends; it does not assign.** Nothing here selects a cadence,
writes copy or changes a campaign. A system that quietly picks the approach
is one whose choices nobody reviews.

**Unknown is not a miss.** An account whose employee band was never
established has not failed the size condition, it has not been asked.
Collapsing the two turns "we know nothing about this company" into "this
company is a poor fit".

**"Nothing here fits" is an answer.** Always naming a best match promotes a
weak fit to a plan, which is how a generic sequence reaches an account that
deserved a different one.

**A playbook licenses nothing.** Choosing the hiring playbook selects an
angle. It does not permit a message to mention hiring.
"""
import datetime
import unittest

from src import (accountpolicy as ap, cadencegraph, events, playbooks,
                 priority, signals as S, store, strategy)
from tests.campaignbase import CampaignTest

WS = "productive"
JOHN = "john"
NOW = datetime.datetime(2026, 8, 29, tzinfo=datetime.timezone.utc)


def days_ago(n):
    return (NOW - datetime.timedelta(days=n)).isoformat()


class PlaybookTest(CampaignTest):

    def company(self, rid="acme", band="51-200",
                vertical="professional_services", country="united kingdom",
                persona="champion", selected=True, score=80.0):
        rec = store.new_record(rid, "domains", WS, rid.title(),
                               f"{rid}.test")
        rec["contacts"] = [{"key": JOHN, "name": "John Smith", "title": "COO",
                            "email": f"john@{rid}.test", "persona": persona,
                            "selected": selected}]
        rec["qualification"] = {
            "segment_key": "SEG",
            "segment": {"vertical": vertical, "employee_band": band,
                        "country": country},
            "verdict": {"icp_status": "qualified", "icp_score": score,
                        "icp_tier": "A"},
            "messaging": {"relevant_pain_categories": [strategy.UTILIZATION],
                          "unsupported_hypotheses": []},
        }
        store.save([rec])
        return rec

    def signal(self, rid, kind, evidence="7 open delivery roles listed",
               days=3):
        S.record(S.signal(WS, kind, record_id=rid, evidence=evidence,
                          source=S.MANUAL, observed_at=days_ago(days)))

    def assess(self, rec):
        return priority.assess(rec, WS, now=NOW)


class TheLibraryIsInternallyConsistent(unittest.TestCase):
    """A playbook naming a cadence that does not exist is a plan that
    cannot be run, and nothing else would notice until somebody tried."""

    def test_every_playbook_names_a_real_cadence_template(self):
        for play in playbooks.LIBRARY:
            self.assertIn(play["cadence"], cadencegraph.TEMPLATES,
                          play["id"])

    def test_every_playbook_names_real_pains(self):
        for play in playbooks.LIBRARY:
            self.assertIn(play["lead_pain"], strategy.PAINS, play["id"])
            self.assertIn(play["second_pain"], strategy.PAINS, play["id"])

    def test_every_condition_has_a_label(self):
        for play in playbooks.LIBRARY:
            for block in ("requires", "prefers"):
                for condition in (play.get(block) or {}):
                    self.assertIn(condition, playbooks.CONDITION_LABEL,
                                  f"{play['id']}: {condition}")

    def test_ids_are_unique(self):
        ids = [p["id"] for p in playbooks.LIBRARY]
        self.assertEqual(len(ids), len(set(ids)))

    def test_exactly_one_playbook_is_unconditional(self):
        """The fallback. Two would mean the ranking has a silent tie for
        "we know nothing"."""
        unconditional = [p for p in playbooks.LIBRARY
                         if not p.get("requires")]
        self.assertEqual([p["id"] for p in unconditional],
                         ["segment_default"])


class UnknownIsNotAMiss(PlaybookTest):

    def test_an_unestablished_band_is_not_counted_against_a_playbook(self):
        rec = self.company(band=None)
        out = playbooks.evaluate(playbooks.BY_ID["margin_visibility"], rec,
                                 self.assess(rec))
        bands = [e for e in out["unknown"]
                 if e["condition"] == playbooks.MATCH_EMPLOYEES]
        self.assertEqual(len(bands), 1)
        self.assertNotIn(playbooks.MATCH_EMPLOYEES,
                         [e["condition"] for e in out["missed"]])

    def test_an_unknown_field_says_so_rather_than_reporting_a_value(self):
        rec = self.company(band=None)
        out = playbooks.evaluate(playbooks.BY_ID["margin_visibility"], rec,
                                 self.assess(rec))
        why = [e["why"] for e in out["unknown"]
               if e["condition"] == playbooks.MATCH_EMPLOYEES][0]
        self.assertIn("not established", why)

    def test_a_wrong_value_is_a_miss_and_says_what_it_was(self):
        """Different from unknown, and reported differently."""
        rec = self.company(vertical="manufacturing")
        out = playbooks.evaluate(playbooks.BY_ID["margin_visibility"], rec,
                                 self.assess(rec))
        missed = [e for e in out["missed"]
                  if e["condition"] == playbooks.MATCH_VERTICAL]
        self.assertEqual(len(missed), 1)
        self.assertIn("manufacturing", missed[0]["why"])

    def test_an_unanswerable_required_condition_does_not_pass(self):
        rec = self.company(vertical=None)
        out = playbooks.evaluate(playbooks.BY_ID["margin_visibility"], rec,
                                 self.assess(rec))
        self.assertFalse(out["eligible"])


class NothingHereFitsIsAnAnswer(PlaybookTest):

    def test_an_account_with_nothing_known_gets_the_fallback_only(self):
        rec = self.company(vertical="manufacturing")
        out = playbooks.recommend(rec, self.assess(rec))
        self.assertEqual(out["recommended"], [])
        self.assertEqual(out["fallback"]["playbook"], "segment_default")
        self.assertIn("Nothing specific is known", out["why"])

    def test_the_fallback_is_never_mixed_into_the_ranking(self):
        """"The segment approach, because we know nothing else" and "the
        new-leadership approach, because their COO started in August" are
        different kinds of recommendation."""
        rec = self.company()
        self.signal("acme", S.NEW_EXECUTIVE,
                    "Michael Green announced as CFO on the company blog")
        out = playbooks.recommend(rec, self.assess(rec))
        self.assertNotIn("segment_default",
                         [r["playbook"] for r in out["recommended"]])

    def test_a_hiring_signal_selects_the_scaling_playbook(self):
        rec = self.company()
        self.signal("acme", S.HIRING_SURGE)
        out = playbooks.recommend(rec, self.assess(rec))
        self.assertIn("operational_scale",
                      [r["playbook"] for r in out["recommended"]])

    def test_the_recommendation_carries_the_evidence_that_chose_it(self):
        rec = self.company()
        self.signal("acme", S.HIRING_SURGE,
                    "14 open delivery roles on the careers page")
        out = playbooks.recommend(rec, self.assess(rec))
        chosen = [r for r in out["recommended"]
                  if r["playbook"] == "operational_scale"][0]
        self.assertTrue(any("14 open delivery roles" in e["why"]
                            for e in chosen["met"]))

    def test_a_stale_signal_does_not_select_a_playbook(self):
        """It is still true. It is not a reason to act today."""
        rec = self.company()
        self.signal("acme", S.HIRING_SURGE, days=400)
        out = playbooks.recommend(rec, self.assess(rec))
        self.assertNotIn("operational_scale",
                         [r["playbook"] for r in out["recommended"]])

    def test_our_own_outreach_does_not_select_a_signal_playbook(self):
        """Engagement is not something happening at the company, and a
        playbook chosen by our own touch would be circular."""
        rec = self.company()
        events.record(rec, events.PUSH_MARKED, contact_key=JOHN,
                      channel="email", at=days_ago(5), sender_id="anna",
                      step="d1")
        store.save([rec])
        out = playbooks.recommend(rec, self.assess(rec))
        self.assertNotIn("operational_scale",
                         [r["playbook"] for r in out["recommended"]])


class ItRecommendsAndDoesNotAssign(PlaybookTest):

    def test_recommending_changes_nothing_on_the_record(self):
        rec = self.company()
        self.signal("acme", S.HIRING_SURGE)
        before = store.get("acme")
        playbooks.recommend(rec, self.assess(rec))
        self.assertEqual(store.get("acme"), before)

    def test_recommending_creates_no_campaign(self):
        rec = self.company()
        playbooks.recommend(rec, self.assess(rec))
        from src import campaigns
        self.assertEqual(campaigns.load(), [])

    def test_a_playbook_does_not_license_a_claim(self):
        """The distinction that matters most exactly here: a hiring signal
        has just chosen an approach."""
        rec = self.company()
        self.signal("acme", S.HIRING_SURGE)
        out = playbooks.recommend(rec, self.assess(rec))
        self.assertIn("does not license", out["note"])

    def test_a_suppressed_account_still_gets_a_recommendation(self):
        """Which approach would fit and whether anything may be sent are
        different questions. `eligibility` answers the second and this must
        not pretend to."""
        rec = self.company()
        ap.apply_reply(rec, JOHN, ap.ACCOUNT_DNC, workspace=WS)
        store.save([rec])
        out = playbooks.recommend(rec, self.assess(rec))
        self.assertIsNotNone(out["fallback"])


class RankingAndFloor(PlaybookTest):

    def test_a_high_priority_account_with_people_gets_the_multi_dm_play(self):
        rec = self.company()
        self.signal("acme", S.HIRING_SURGE)
        self.signal("acme", S.NEW_EXECUTIVE, "New COO announced", days=10)
        found = self.assess(rec)
        found["tier"] = "high"
        out = playbooks.recommend(rec, found)
        self.assertIn("multi_dm_account",
                      [r["playbook"] for r in out["recommended"]])

    def test_no_selected_decision_maker_fails_the_persona_condition(self):
        rec = self.company(selected=False)
        found = self.assess(rec)
        found["tier"] = "high"
        out = playbooks.evaluate(playbooks.BY_ID["multi_dm_account"], rec,
                                 found)
        self.assertFalse(out["eligible"])
        self.assertIn("no decision maker selected",
                      [e["why"] for e in out["missed"]])

    def test_prior_engagement_selects_the_reengagement_playbook(self):
        rec = self.company()
        events.record(rec, events.PUSH_MARKED, contact_key=JOHN,
                      channel="email", at=days_ago(40), sender_id="anna",
                      step="d1")
        store.save([rec])
        out = playbooks.recommend(rec, self.assess(rec))
        self.assertIn("back_to_the_account",
                      [r["playbook"] for r in out["recommended"]])

    def test_the_floor_is_reported_so_a_reader_can_argue_with_it(self):
        rec = self.company()
        out = playbooks.recommend(rec, self.assess(rec))
        self.assertEqual(out["floor"], playbooks.CONFIDENCE_FLOOR)

    def test_recommendations_are_capped_and_the_count_is_honest(self):
        rec = self.company()
        self.signal("acme", S.HIRING_SURGE)
        out = playbooks.recommend(rec, self.assess(rec), limit=1)
        self.assertLessEqual(len(out["recommended"]), 1)
        self.assertEqual(out["considered"], len(playbooks.LIBRARY) - 1)


if __name__ == "__main__":
    unittest.main()
