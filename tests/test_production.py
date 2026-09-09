"""The stop button, the plan, and the trail that explains a send afterwards.

These three exist for the three bad moments in running outbound at scale: the
one where something is going wrong and it must stop now, the one before launch
where somebody has to know how big this really is, and the one where a prospect
writes back angry and somebody has to explain how they ended up on the list.
"""
import inspect
import unittest

from src import (audit, campaigns, eligibility, orchestrator, plan, roles,
                 store, synthetic)
from tests.campaignbase import CampaignTest


class TestTheFreeze(CampaignTest):
    def frozen(self):
        campaign, recs, _ = self.approved_campaign()
        orchestrator.freeze(campaign, "a client asked us to stop", by="U0ADMIN")
        return campaign, store.load()

    def test_a_freeze_must_say_why(self):
        campaign, recs, _ = self.approved_campaign()
        with self.assertRaises(orchestrator.NotPermitted):
            orchestrator.freeze(campaign, "", by="U0ADMIN")

    def test_a_reviewer_may_stop_a_campaign(self):
        campaign, recs, _ = self.approved_campaign()
        orchestrator.freeze(campaign, "looks wrong", by="U0REV",
                            role=roles.REVIEWER)
        self.assertTrue(campaigns.is_frozen(campaign))

    def test_a_reviewer_may_not_start_one_again(self):
        campaign, recs = self.frozen()
        with self.assertRaises(roles.NotPermitted):
            orchestrator.unfreeze(campaign, by="U0REV", role=roles.REVIEWER)
        self.assertTrue(campaigns.is_frozen(campaign))

    def test_freezing_blocks_every_step(self):
        campaign, recs = self.frozen()
        for rec in recs:
            for contact in rec["contacts"]:
                decision = eligibility.decide(rec, contact, "day1", "email",
                                              campaign=campaign, recs=recs,
                                              config=self.config)
                self.assertEqual(decision["verdict"], eligibility.BLOCKED)
                self.assertIn(eligibility.BLOCKED_CAMPAIGN_FROZEN,
                              decision["reasons"])

    def test_a_freeze_outranks_a_perfectly_good_approval(self):
        campaign, recs = self.frozen()
        self.assertTrue(campaigns.approval_is_current(campaign, recs,
                                                      self.config))
        rec = recs[0]
        decision = eligibility.decide(rec, rec["contacts"][0], "day1", "email",
                                      campaign=campaign, recs=recs,
                                      config=self.config)
        self.assertIn(eligibility.BLOCKED_CAMPAIGN_FROZEN, decision["reasons"])

    def test_freezing_does_not_change_the_status(self):
        campaign, recs, _ = self.approved_campaign()
        before = campaign["status"]
        orchestrator.freeze(campaign, "stop", by="U0ADMIN")
        self.assertEqual(campaign["status"], before)
        orchestrator.unfreeze(campaign, by="U0ADMIN")
        self.assertEqual(campaign["status"], before)

    def test_freezing_does_not_invalidate_the_approval(self):
        """Whoever hits stop should not be punished with a re-approval."""
        campaign, recs, _ = self.approved_campaign()
        before = campaign["approval"]["fingerprint"]
        orchestrator.freeze(campaign, "stop", by="U0ADMIN")
        orchestrator.unfreeze(campaign, by="U0ADMIN")
        self.assertEqual(campaign["approval"]["fingerprint"], before)
        self.assertTrue(campaigns.approval_is_current(campaign, store.load(),
                                                      self.config))

    def test_a_frozen_campaign_cannot_pass_validation(self):
        campaign, recs = self.frozen()
        result = campaigns.validate(campaign["campaign_id"], recs, self.config,
                                    campaign=campaign, ignore_status=True)
        self.assertFalse(result["ok"])
        self.assertIn("not frozen", result["blockers"])

    def test_freezing_twice_records_the_first_reason(self):
        campaign, recs = self.frozen()
        orchestrator.freeze(campaign, "a different reason", by="U0OTHER")
        self.assertEqual(campaign["freeze"]["why"], "a client asked us to stop")

    def test_unfreezing_something_that_is_not_frozen_is_harmless(self):
        campaign, recs, _ = self.approved_campaign()
        orchestrator.unfreeze(campaign, by="U0ADMIN")
        self.assertFalse(campaigns.is_frozen(campaign))

    def test_both_events_are_recorded(self):
        campaign, recs = self.frozen()
        orchestrator.unfreeze(campaign, by="U0ADMIN")
        kinds = [e["type"] for e in campaign["events"]]
        self.assertIn("campaign_frozen", kinds)
        self.assertIn("campaign_unfrozen", kinds)


class TestTheSizeEstimate(CampaignTest):
    def synthetic_records(self, size=56):
        recs = synthetic.dataset(size, self.config)
        store.save(recs)
        return store.load()

    def test_the_funnel_narrows_at_every_step(self):
        recs = self.synthetic_records()
        counts = plan.size(None, recs, self.config)
        self.assertEqual(counts["domains"], len(recs))
        self.assertGreater(counts["domains"], counts["domains_qualified"])
        self.assertGreater(counts["contacts_found"],
                           counts["contacts_emailable"])

    def test_blocked_and_unreachable_contacts_are_counted_not_hidden(self):
        recs = self.synthetic_records()
        counts = plan.size(None, recs, self.config)
        self.assertGreater(counts["contacts_mx_blocked"], 0)

    def test_an_already_pushed_step_is_not_counted_as_work_to_do(self):
        from src import push
        recs = self.synthetic_records()
        before = plan.size(None, recs, self.config)
        rec = next(r for r in recs if r.get("cadence"))
        key = next(iter(rec["cadence"]))
        push.mark_pushed(rec, key, "day1", push.push_id(rec, key, "day1",
                                                        "email"))
        after = plan.size(None, recs, self.config)
        self.assertEqual(after["email_steps"], before["email_steps"] - 1)
        self.assertEqual(after["steps_already_pushed"], 1)

    def test_the_llm_ceiling_is_named_as_a_ceiling(self):
        recs = self.synthetic_records()
        counts = plan.size(None, recs, self.config)
        self.assertIn("llm_calls_if_regenerated", counts)


class TestTheSchedule(CampaignTest):
    def campaign_with(self, email=20, linkedin=10, size=56):
        recs = synthetic.dataset(size, self.config)
        store.save(recs)
        recs = store.load()
        campaign = campaigns.new_campaign("syn", "demo", "Synthetic")
        campaign["record_ids"] = [r["id"] for r in recs]
        campaign["daily_volume"] = {"email": email, "linkedin": linkedin}
        return campaign, recs

    def test_the_cap_is_never_exceeded_on_any_day(self):
        campaign, recs = self.campaign_with()
        result = plan.schedule(campaign, recs, self.config, days=30)
        for row in result["days"]:
            self.assertLessEqual(row["email"]["sent"], 20, row["day"])
            self.assertLessEqual(row["linkedin"]["sent"], 10, row["day"])

    def test_what_the_cap_holds_back_becomes_backlog(self):
        campaign, recs = self.campaign_with(email=1, linkedin=1)
        result = plan.schedule(campaign, recs, self.config, days=5)
        self.assertGreater(result["unsent_at_horizon"]["email"], 0)
        self.assertGreater(result["further_days_needed"], 0)

    def test_a_tight_cap_makes_the_campaign_take_longer_not_shorter(self):
        tight, recs = self.campaign_with(email=1, linkedin=1)
        loose, _ = self.campaign_with(email=500, linkedin=500)
        slow = plan.schedule(tight, recs, self.config, days=21)
        fast = plan.schedule(loose, recs, self.config, days=21)
        self.assertGreater(slow["further_days_needed"],
                           fast["further_days_needed"])

    def test_calendar_weeks_are_working_weeks(self):
        campaign, recs = self.campaign_with(email=500, linkedin=500)
        result = plan.schedule(campaign, recs, self.config, days=21)
        self.assertAlmostEqual(result["calendar_weeks"],
                               round(21 / plan.SENDING_DAYS_PER_WEEK, 1))

    def test_an_unset_cap_is_reported_rather_than_assumed_infinite(self):
        campaign, recs = self.campaign_with()
        campaign["daily_volume"] = {}
        result = plan.schedule(campaign, recs, self.config, days=21)
        self.assertTrue(result["warnings"])
        self.assertTrue(any("no daily cap" in w for w in result["warnings"]))

    def test_a_campaign_with_caps_warns_about_nothing(self):
        campaign, recs = self.campaign_with()
        self.assertEqual(plan.schedule(campaign, recs, self.config,
                                       days=21)["warnings"], [])


class TestTheExecutionPlan(CampaignTest):
    def test_it_would_send_nothing(self):
        campaign, recs, _ = self.approved_campaign()
        result = plan.execution_plan(campaign, store.load(), self.config)
        self.assertEqual(result["would_send"], 0)

    def test_it_names_every_eligibility_reason_it_found(self):
        campaign, recs, _ = self.approved_campaign()
        result = plan.execution_plan(campaign, store.load(), self.config)
        for reason in result["eligibility"]["reasons"]:
            self.assertIn(reason, eligibility.REASONS, reason)
        self.assertEqual(sorted(result["eligibility"]["counts"]),
                         sorted(eligibility.VERDICTS))

    def test_it_reports_launch_blockers_without_launching(self):
        campaign, recs, _ = self.approved_campaign()
        orchestrator.freeze(campaign, "stop", by="U0ADMIN")
        result = plan.execution_plan(campaign, store.load(), self.config)
        self.assertIn("not frozen", result["launch_blockers"])
        self.assertTrue(result["frozen"])

    def test_it_calls_no_provider(self):
        campaign, recs, _ = self.approved_campaign()
        plan.execution_plan(campaign, store.load(), self.config)
        self.assertEqual(self.cassette.calls, [])

    def test_the_module_contains_no_way_to_send(self):
        source = inspect.getsource(plan)
        for banned in ("push.run", "providers.request", "bison.", "heyreach.",
                       "live=True"):
            self.assertNotIn(banned, source, banned)


class TestTheAuditTrail(CampaignTest):
    def test_it_orders_the_whole_story(self):
        campaign, recs, _ = self.approved_campaign()
        rec = store.load()[0]
        trail = audit.for_contact(rec, rec["contacts"][0]["key"], campaign)
        self.assertTrue(trail)
        self.assertEqual([line["at"] for line in trail],
                         sorted(line["at"] for line in trail))

    def test_every_line_says_where_it_came_from(self):
        campaign, recs, _ = self.approved_campaign()
        rec = store.load()[0]
        for line in audit.for_contact(rec, rec["contacts"][0]["key"], campaign):
            self.assertIn(line["source"], audit.SOURCES)

    def test_it_admits_what_it_cannot_answer(self):
        campaign, recs, _ = self.approved_campaign()
        rec = store.load()[0]
        result = audit.why_contacted(rec, rec["contacts"][0]["key"], campaign)
        self.assertFalse(result["answered"], "nothing has been pushed yet")
        self.assertTrue(any("no push" in gap for gap in result["unanswered"]))

    def test_a_pushed_step_closes_that_gap(self):
        from src import push
        campaign, recs, _ = self.approved_campaign()
        recs = store.load()
        rec = recs[0]
        key = rec["contacts"][0]["key"]
        push.mark_pushed(rec, key, "day1", push.push_id(rec, key, "day1",
                                                        "email"))
        result = audit.why_contacted(rec, key, campaign)
        self.assertTrue(result["pushes"])
        self.assertFalse(any("no push" in gap for gap in result["unanswered"]))

    def test_it_names_who_approved_the_campaign(self):
        campaign, recs, _ = self.approved_campaign()
        rec = store.load()[0]
        result = audit.why_contacted(rec, rec["contacts"][0]["key"], campaign)
        self.assertTrue(result["campaign_approved_by"])
        self.assertTrue(result["campaign_fingerprint"])

    def test_without_a_campaign_it_says_nobody_signed_it_off(self):
        campaign, recs, _ = self.approved_campaign()
        rec = store.load()[0]
        result = audit.why_contacted(rec, rec["contacts"][0]["key"])
        self.assertFalse(result["answered"])
        self.assertTrue(any("no campaign" in gap
                            for gap in result["unanswered"]))

    def test_the_campaign_trail_shows_a_freeze(self):
        campaign, recs, _ = self.approved_campaign()
        orchestrator.freeze(campaign, "a client asked us to stop", by="U0ADMIN")
        result = audit.for_campaign(campaign, store.load())
        self.assertTrue(result["frozen"])
        self.assertTrue(any("froze" in line["what"] or "freeze" in line["what"]
                            for line in result["trail"]))

    def test_the_trail_never_writes_anything(self):
        source = inspect.getsource(audit)
        for banned in ("store.save", "campaigns.save", "store.patch"):
            self.assertNotIn(banned, source, banned)

    def test_it_calls_no_provider(self):
        campaign, recs, _ = self.approved_campaign()
        rec = store.load()[0]
        audit.why_contacted(rec, rec["contacts"][0]["key"], campaign)
        audit.for_campaign(campaign, store.load())
        self.assertEqual(self.cassette.calls, [])


if __name__ == "__main__":
    unittest.main()
