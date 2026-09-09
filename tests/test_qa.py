"""The state machine and the QA engine.

Two properties carry most of the weight here: a sent step can never return to a
state where it would send again, and a blocker is never averaged away by a good
score somewhere else.
"""
import unittest

from src import (campaigns, clients, demo, dedupe, mx, qa, stepstate, store)
from tests.campaignbase import CampaignTest, contact


class TestTheStateMachine(unittest.TestCase):
    def test_every_state_is_reachable_from_somewhere(self):
        reachable = {s for targets in stepstate.TRANSITIONS.values()
                     for s in targets}
        for state in stepstate.STATES:
            if state in (stepstate.PLANNED,):
                continue                 # where every step starts
            self.assertIn(state, reachable, state)

    def test_a_pushed_step_can_only_be_confirmed(self):
        self.assertEqual(stepstate.TRANSITIONS[stepstate.PUSHED],
                         (stepstate.CONFIRMED,))

    def test_a_sent_step_can_never_become_sendable_again(self):
        for terminal in (stepstate.PUSHED, stepstate.CONFIRMED,
                         stepstate.CANCELLED):
            for target in (stepstate.ELIGIBLE, stepstate.PENDING,
                           stepstate.PREPARED, stepstate.UNAPPROVED):
                self.assertFalse(stepstate.allowed(terminal, target),
                                 f"{terminal} -> {target}")

    def test_an_illegal_transition_raises_and_names_the_options(self):
        with self.assertRaises(stepstate.IllegalTransition) as e:
            stepstate.check(stepstate.PUSHED, stepstate.ELIGIBLE)
        self.assertIn("may only go to", str(e.exception))

    def test_recomputing_the_same_status_is_legal(self):
        for state in stepstate.STATES:
            self.assertTrue(stepstate.allowed(state, state), state)

    def test_an_unknown_state_is_never_legal(self):
        self.assertFalse(stepstate.allowed(stepstate.ELIGIBLE, "invented"))
        self.assertFalse(stepstate.allowed("invented", stepstate.ELIGIBLE))

    def test_a_prepared_step_can_fall_back_to_eligible(self):
        """A crash between payload and push must be safe to repeat."""
        self.assertTrue(stepstate.allowed(stepstate.PREPARED,
                                          stepstate.ELIGIBLE))

    def test_a_skipped_step_cannot_jump_straight_to_pushed(self):
        self.assertFalse(stepstate.allowed(stepstate.SKIPPED,
                                           stepstate.PUSHED))

    def test_applying_a_move_records_where_it_came_from(self):
        step = {"status": stepstate.ELIGIBLE}
        stepstate.apply(step, stepstate.PREPARED, where="day1")
        self.assertEqual(step["status"], stepstate.PREPARED)
        self.assertEqual(step["history"][-1]["from"], stepstate.ELIGIBLE)

    def test_applying_an_illegal_move_changes_nothing(self):
        step = {"status": stepstate.PUSHED}
        with self.assertRaises(stepstate.IllegalTransition):
            stepstate.apply(step, stepstate.ELIGIBLE)
        self.assertEqual(step["status"], stepstate.PUSHED)

    def test_reconcile_refuses_to_move_a_terminal_step(self):
        result = stepstate.reconcile({"status": stepstate.PUSHED},
                                     stepstate.ELIGIBLE)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], stepstate.PUSHED)
        self.assertIn("terminal", result["why"])

    def test_reconcile_accepts_a_legal_recomputation(self):
        result = stepstate.reconcile({"status": stepstate.UNAPPROVED},
                                     stepstate.ELIGIBLE)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], stepstate.ELIGIBLE)

    def test_the_four_ways_of_not_sending_stay_distinct(self):
        for state in (stepstate.HELD, stepstate.BLOCKED, stepstate.SKIPPED,
                      stepstate.CANCELLED):
            self.assertIn(state, stepstate.STATES)
        self.assertEqual(len({stepstate.HELD, stepstate.BLOCKED,
                              stepstate.SKIPPED, stepstate.CANCELLED}), 4)

    def test_the_statuses_cadence_emits_are_all_known(self):
        for status in ("pending", "eligible", "paused", "pushed", "blocked",
                       "waiting", "skipped", "unapproved"):
            self.assertTrue(stepstate.known(status), status)


class QATest(CampaignTest):
    def campaign_and_records(self):
        campaign, recs, config = demo.build(self.config)
        return campaign, recs, config


class TestTheReport(QATest):
    def test_it_produces_every_section(self):
        campaign, recs, config = self.campaign_and_records()
        result = qa.report(campaign, recs, config)
        for section in ("targeting", "contact_data", "personalization", "copy",
                        "safety", "cadence", "scores", "issues"):
            self.assertIn(section, result)

    def test_it_counts_personas(self):
        campaign, recs, config = self.campaign_and_records()
        result = qa.report(campaign, recs, config)
        self.assertGreater(result["targeting"]["champions"], 0)
        self.assertGreater(result["targeting"]["buyers"], 0)

    def test_it_counts_personalisation_quality(self):
        campaign, recs, config = self.campaign_and_records()
        result = qa.report(campaign, recs, config)
        personal = result["personalization"]
        self.assertGreater(personal["strong"] + personal["medium"], 0)
        self.assertGreater(personal["none"], 0)

    def test_it_finds_the_deliberate_lint_failure(self):
        campaign, recs, config = self.campaign_and_records()
        result = qa.report(campaign, recs, config)
        self.assertGreater(result["copy"]["lint_failures"], 0)
        self.assertGreater(result["copy"]["placeholders"], 0)

    def test_it_calls_no_provider(self):
        campaign, recs, config = self.campaign_and_records()
        qa.report(campaign, recs, config)
        self.assertEqual(self.cassette.calls, [])


class TestBlockersAreNeverAveragedAway(QATest):
    def clean(self):
        """A campaign with nothing wrong, to move one thing at a time."""
        campaign, recs, _ = self.approved_campaign()
        recs = store.load()
        for rec in recs:
            for c in rec["contacts"]:
                c["mx"] = mx.decide(["aspmx.l.google.com"],
                                    mx.settings(self.config), domain="acme.test")
                c["personalization"] = {"quality": "strong",
                                        "selected_evidence_ids": []}
        store.save(recs)
        return campaign, store.load()

    def test_a_clean_campaign_does_not_block(self):
        campaign, recs = self.clean()
        result = qa.report(campaign, recs, self.config)
        self.assertNotEqual(result["verdict"], qa.BLOCK, result["reasons"])

    def test_one_placeholder_blocks_however_good_everything_else_is(self):
        campaign, recs = self.clean()
        for steps in recs[0]["cadence"].values():
            for step in steps.values():
                if step.get("generated"):
                    step["body"] = "Hi {{first_name}}, quick one.\n"
        store.save(recs)
        result = qa.report(campaign, store.load(), self.config)
        self.assertEqual(result["verdict"], qa.BLOCK)
        # Contactability is untouched by a copy defect and stays high. It does
        # not help. (Safety legitimately drops too: editing approved copy makes
        # the campaign approval stale, which is the fingerprint doing its job.)
        self.assertGreater(result["scores"]["contactability"], 0.9,
                           "a perfect score elsewhere must not rescue it")

    def test_a_duplicate_blocks(self):
        campaign, recs = self.clean()
        recs[0]["contacts"][0]["duplicate_of"] = {"record_id": "x",
                                                  "contact_key": "y"}
        store.save(recs)
        result = qa.report(campaign, store.load(), self.config)
        self.assertEqual(result["verdict"], qa.BLOCK)

    def test_a_stale_approval_blocks(self):
        campaign, recs = self.clean()
        campaign["approval"]["fingerprint"] = "a-fingerprint-from-yesterday"
        result = qa.report(campaign, recs, self.config)
        self.assertEqual(result["verdict"], qa.BLOCK)
        self.assertTrue(any("changed since" in r for r in result["reasons"]))

    def test_a_blocker_can_be_switched_off_but_never_silently(self):
        campaign, recs = self.clean()
        for steps in recs[0]["cadence"].values():
            for step in steps.values():
                if step.get("generated"):
                    step["body"] = "Hi {{first_name}}, quick one.\n"
        store.save(recs)
        config = dict(self.config)
        config["qa"] = {"block_on": {"unresolved_placeholders": False,
                                     "lint_failures": False,
                                     "stale_approval": False}}
        result = qa.report(campaign, store.load(), config)
        self.assertNotEqual(result["verdict"], qa.BLOCK)

    def test_low_coverage_warns_rather_than_blocks(self):
        campaign, recs = self.clean()
        for rec in recs:
            for c in rec["contacts"]:
                c["personalization"] = {"quality": "none",
                                        "selected_evidence_ids": []}
        store.save(recs)
        result = qa.report(campaign, store.load(), self.config)
        self.assertEqual(result["verdict"], qa.WARN)
        self.assertTrue(any("personalization_coverage" in r
                            for r in result["reasons"]))


class TestTheHealthScore(QATest):
    def test_there_are_six_named_sub_scores(self):
        campaign, recs, config = self.campaign_and_records()
        scores = qa.report(campaign, recs, config)["scores"]
        self.assertEqual(sorted(scores), sorted(qa.DIMENSIONS))

    def test_every_score_is_between_zero_and_one(self):
        campaign, recs, config = self.campaign_and_records()
        for value in qa.report(campaign, recs, config)["scores"].values():
            if value is not None:
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)

    def test_there_is_no_single_overall_number_to_hide_behind(self):
        campaign, recs, config = self.campaign_and_records()
        result = qa.report(campaign, recs, config)
        self.assertNotIn("score", result)
        self.assertNotIn("overall", result["scores"])

    def test_a_lint_failure_moves_the_copy_score_and_not_the_others(self):
        campaign, recs, config = self.campaign_and_records()
        before = qa.report(campaign, recs, config)["scores"]
        for steps in recs[0]["cadence"].values():
            for step in steps.values():
                if step.get("generated"):
                    step["body"] = "Hi {{first_name}}.\n"
        after = qa.report(campaign, recs, config)["scores"]
        self.assertLessEqual(after["copy"], before["copy"])
        self.assertEqual(after["safety"], before["safety"])


class TestTheReviewQueue(QATest):
    def test_critical_comes_before_held_and_warn(self):
        campaign, recs, config = self.campaign_and_records()
        issues = qa.report(campaign, recs, config)["issues"]
        seen = [qa.SEVERITY_ORDER.get(i["severity"], 9) for i in issues]
        self.assertEqual(seen, sorted(seen))

    def test_the_order_is_deterministic(self):
        campaign, recs, config = self.campaign_and_records()
        first = qa.report(campaign, recs, config)["issues"]
        second = qa.report(campaign, recs, config)["issues"]
        self.assertEqual(first, second)

    def test_every_issue_names_where_it_is(self):
        campaign, recs, config = self.campaign_and_records()
        for issue in qa.report(campaign, recs, config)["issues"]:
            self.assertTrue(issue.get("record_id") or issue.get("contact_key"))
            self.assertIn(issue["dimension"], qa.DIMENSIONS)
            self.assertTrue(issue["message"])

    def test_a_paused_company_is_critical(self):
        campaign, recs, config = self.campaign_and_records()
        recs[0]["paused"] = {"since": "x", "reason": "reply_received"}
        issues = qa.report(campaign, recs, config)["issues"]
        self.assertTrue(any(i["severity"] == "critical" and "paused" in i["message"]
                            for i in issues))

    def test_a_held_verification_is_held_not_critical(self):
        campaign, recs, config = self.campaign_and_records()
        issues = qa.report(campaign, recs, config)["issues"]
        verification = [i for i in issues if "verification" in i["message"]]
        for issue in verification:
            self.assertEqual(issue["severity"], "held")


if __name__ == "__main__":
    unittest.main()
