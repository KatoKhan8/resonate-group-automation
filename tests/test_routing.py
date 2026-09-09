"""Who to look for, what it would cost, and the gate before anybody pays.

The property this file exists to protect: a 5,000-domain upload cannot turn
into thousands of paid person searches because somebody ran the next command.
Rejected companies cost nothing, review companies cost nothing, and even a
qualified company costs nothing until a human approves a plan that is
fingerprinted against the verdicts it was built from.
"""
import unittest

from src import (campaignseg, companies, dmplan, icp, qualify, routing,
                 segments, store, strategy, waterfall)
from tests.campaignbase import CampaignTest
from tests.test_icp import AGENCY_TEXT, rec


def qualified(tier=icp.TIER_A):
    return {"icp_status": icp.QUALIFIED, "icp_tier": tier, "icp_score": 80,
            "icp_confidence": icp.HIGH, "positive_signals": []}


def segment_of(**kw):
    return segments.classify(rec(**kw))


class TestPersonaRouting(CampaignTest):
    def plan_for(self, verdict=None, **kw):
        company = rec(**kw)
        segment = segments.classify(company)
        return routing.plan(company, segment, verdict or qualified())

    def test_a_tiny_agency_is_routed_to_the_founder(self):
        plan = self.plan_for(industry="Marketing", employees=8,
                             specialties=["digital marketing",
                                          "content marketing"])
        self.assertEqual(plan["strategy"], routing.FOUNDER_LED)
        self.assertEqual(plan["persona_priority"][0], "founder")

    def test_a_mid_agency_is_routed_to_operations(self):
        plan = self.plan_for(industry="Marketing", employees=90,
                             specialties=["digital marketing",
                                          "content marketing"])
        self.assertEqual(plan["strategy"], routing.OPERATIONS_LED)
        self.assertEqual(plan["persona_priority"][0], "operations")

    def test_a_large_agency_is_routed_to_finance(self):
        plan = self.plan_for(industry="Marketing", employees=400,
                             specialties=["digital marketing",
                                          "content marketing"])
        self.assertEqual(plan["strategy"], routing.FINANCE_LED)
        self.assertEqual(plan["persona_priority"][0], "finance")

    def test_a_software_agency_is_routed_to_delivery_not_operations(self):
        """Vertical overrides size: capacity is a delivery question here."""
        plan = self.plan_for(industry="Software", employees=90,
                             specialties=["software development",
                                          "custom software"])
        self.assertEqual(plan["strategy"], routing.DELIVERY_LED)
        self.assertEqual(plan["persona_priority"][0], "delivery")

    def test_a_tiny_software_shop_still_goes_to_the_founder(self):
        plan = self.plan_for(industry="Software", employees=6,
                             specialties=["software development",
                                          "custom software"])
        self.assertEqual(plan["strategy"], routing.FOUNDER_LED)

    def test_the_titles_differ_between_strategies(self):
        small = self.plan_for(industry="Marketing", employees=8,
                              specialties=["digital marketing",
                                           "content marketing"])
        large = self.plan_for(industry="Marketing", employees=400,
                              specialties=["digital marketing",
                                           "content marketing"])
        self.assertNotEqual(small["target_titles"], large["target_titles"])
        self.assertIn("Founder", small["target_titles"])
        self.assertIn("CFO", large["target_titles"])

    def test_an_unknown_size_uses_the_safest_strategy(self):
        plan = self.plan_for(industry="Marketing",
                             specialties=["digital marketing",
                                          "content marketing"])
        self.assertEqual(plan["strategy"], routing.FOUNDER_LED)
        self.assertIn("unknown", plan["strategy_reason"])

    def test_every_plan_says_why_those_people(self):
        plan = self.plan_for(industry="Marketing", employees=90,
                             specialties=["digital marketing",
                                          "content marketing"])
        self.assertTrue(plan["persona_reason"])
        self.assertTrue(plan["strategy_reason"])

    def test_the_strategies_are_configurable(self):
        config = {"routing": {"band_strategy": {"50_99": routing.FINANCE_LED}}}
        company = rec(industry="Marketing", employees=90,
                      specialties=["digital marketing", "content marketing"])
        plan = routing.plan(company, segments.classify(company), qualified(),
                            config)
        self.assertEqual(plan["strategy"], routing.FINANCE_LED)

    def test_titles_can_be_overridden_per_strategy(self):
        config = {"routing": {"strategies": {
            routing.FOUNDER_LED: {"personas": {"founder": ["Grand Poobah"]}}}}}
        company = rec(industry="Marketing", employees=8,
                      specialties=["digital marketing", "content marketing"])
        plan = routing.plan(company, segments.classify(company), qualified(),
                            config)
        self.assertIn("Grand Poobah", plan["target_titles"])

    def test_an_unknown_strategy_name_in_config_is_ignored(self):
        config = {"routing": {"band_strategy": {"50_99": "vibes_led"}}}
        policy = routing.settings(config)
        self.assertEqual(policy["band_strategy"]["50_99"],
                         routing.DEFAULT_BAND_STRATEGY["50_99"])


class TestContactCaps(CampaignTest):
    def cap_for(self, status, tier):
        company = rec(industry="Marketing", employees=90,
                      specialties=["digital marketing", "content marketing"])
        verdict = {"icp_status": status, "icp_tier": tier}
        return routing.plan(company, segments.classify(company), verdict)

    def test_tier_a_b_and_c_get_descending_caps(self):
        a = self.cap_for(icp.QUALIFIED, icp.TIER_A)["max_contacts_to_enrich"]
        b = self.cap_for(icp.QUALIFIED, icp.TIER_B)["max_contacts_to_enrich"]
        c = self.cap_for(icp.QUALIFIED, icp.TIER_C)["max_contacts_to_enrich"]
        self.assertEqual((a, b, c), (3, 2, 1))

    def test_a_review_company_gets_zero(self):
        plan = self.cap_for(icp.REVIEW, icp.TIER_REVIEW)
        self.assertEqual(plan["max_contacts_to_enrich"], 0)
        self.assertIn("human", plan["cap_reason"])

    def test_a_rejected_company_gets_zero(self):
        self.assertEqual(
            self.cap_for(icp.REJECTED, icp.TIER_NOT_ICP)["max_contacts_to_enrich"],
            0)

    def test_an_unknown_company_gets_zero(self):
        self.assertEqual(
            self.cap_for(icp.UNKNOWN, icp.TIER_REVIEW)["max_contacts_to_enrich"],
            0)

    def test_the_caps_are_configurable(self):
        config = {"routing": {"caps": {icp.TIER_A: 5}}}
        company = rec(industry="Marketing", employees=90,
                      specialties=["digital marketing", "content marketing"])
        plan = routing.plan(company, segments.classify(company),
                            qualified(icp.TIER_A), config)
        self.assertEqual(plan["max_contacts_to_enrich"], 5)


class TestCreditPlanning(CampaignTest):
    def entry(self, status=icp.QUALIFIED, tier=icp.TIER_A, contacts=3,
              rid="a"):
        return {
            "record": {"id": rid, "domain": f"{rid}.test"},
            "verdict": {"icp_status": status, "icp_tier": tier},
            "persona_plan": {"max_contacts_to_enrich": contacts,
                             "target_titles": ["CEO"],
                             "cap_reason": f"tier {tier}"},
        }

    def test_a_rejected_company_plans_zero_credits(self):
        plan = dmplan.for_company(**{
            "rec": self.entry(icp.REJECTED, icp.TIER_NOT_ICP, 0)["record"],
            "persona_plan": self.entry(icp.REJECTED, icp.TIER_NOT_ICP,
                                       0)["persona_plan"],
            "verdict": self.entry(icp.REJECTED, icp.TIER_NOT_ICP, 0)["verdict"],
        })
        self.assertEqual(plan["expected_credits"], 0)
        self.assertEqual(plan["maximum_credits"], 0)
        self.assertFalse(plan["enrichment_required"])

    def test_expected_and_maximum_are_different_numbers(self):
        entry = self.entry()
        plan = dmplan.for_company(entry["record"], entry["persona_plan"],
                                  entry["verdict"])
        self.assertLess(plan["expected_credits"], plan["maximum_credits"])
        self.assertEqual(plan["fallback_exposure"],
                         plan["maximum_credits"] - plan["expected_credits"])

    def test_the_fallback_is_conditional_and_carries_its_reasons(self):
        entry = self.entry()
        plan = dmplan.for_company(entry["record"], entry["persona_plan"],
                                  entry["verdict"])
        fallback = [c for c in plan["calls"] if c["conditional"]]
        self.assertEqual(len(fallback), 1)
        self.assertTrue(fallback[0]["requires_reason"])

    def test_contactout_is_planned_before_any_fallback(self):
        entry = self.entry()
        plan = dmplan.for_company(entry["record"], entry["persona_plan"],
                                  entry["verdict"])
        providers = [c["provider"] for c in plan["calls"]]
        self.assertEqual(providers[0], waterfall.CONTACTOUT)
        self.assertEqual(providers[-1], waterfall.AIARK)

    def test_the_batch_totals_add_up(self):
        entries = [self.entry(rid="a"), self.entry(icp.REVIEW, icp.TIER_REVIEW,
                                                   0, "b"),
                   self.entry(icp.REJECTED, icp.TIER_NOT_ICP, 0, "c")]
        summary = dmplan.for_batch(entries)
        self.assertEqual(summary["companies"], 3)
        self.assertEqual(summary["companies_requiring_enrichment"], 1)
        self.assertEqual(summary["companies_skipped"], 2)
        self.assertEqual(summary["planned_dm_searches"], 1)

    def test_a_batch_cap_can_refuse_a_plan(self):
        entries = [self.entry(rid=f"r{i}") for i in range(10)]
        config = {"dm_plan": {"max_batch_credits": 5}}
        summary = dmplan.for_batch(entries, config)
        self.assertTrue(summary["over_cap"])
        self.assertIn("cannot be approved", summary["cap_note"])

    def test_with_no_cap_the_note_says_so_rather_than_implying_safety(self):
        summary = dmplan.for_batch([self.entry()])
        self.assertFalse(summary["over_cap"])
        self.assertIn("no batch credit cap", summary["cap_note"])


class TestTheApprovalGate(CampaignTest):
    def entries(self, contacts=3):
        return [{
            "record": {"id": "a", "domain": "a.test"},
            "verdict": {"icp_status": icp.QUALIFIED, "icp_tier": icp.TIER_A},
            "persona_plan": {"max_contacts_to_enrich": contacts,
                             "target_titles": ["CEO"], "cap_reason": "tier A"},
        }]

    def test_nothing_may_be_enriched_before_approval(self):
        entries = self.entries()
        allowed, why = dmplan.may_enrich({}, entries, entries[0]["record"],
                                         entries[0]["verdict"])
        self.assertFalse(allowed)
        self.assertIn("no person-enrichment approval", why)

    def test_approval_opens_the_gate(self):
        batch, entries = {}, self.entries()
        dmplan.approve(batch, entries, by="operator")
        allowed, _ = dmplan.may_enrich(batch, entries, entries[0]["record"],
                                       entries[0]["verdict"])
        self.assertTrue(allowed)

    def test_a_rejected_company_is_refused_even_after_approval(self):
        batch, entries = {}, self.entries()
        dmplan.approve(batch, entries, by="operator")
        allowed, why = dmplan.may_enrich(
            batch, entries, {"id": "x", "domain": "x.test"},
            {"icp_status": icp.REJECTED, "icp_tier": icp.TIER_NOT_ICP})
        self.assertFalse(allowed)
        self.assertIn("ever", why)

    def test_a_review_company_is_refused_even_after_approval(self):
        batch, entries = {}, self.entries()
        dmplan.approve(batch, entries, by="operator")
        allowed, why = dmplan.may_enrich(
            batch, entries, {"id": "x", "domain": "x.test"},
            {"icp_status": icp.REVIEW, "icp_tier": icp.TIER_REVIEW})
        self.assertFalse(allowed)
        self.assertIn("human decision", why)

    def test_changing_the_qualification_makes_the_approval_stale(self):
        batch, entries = {}, self.entries()
        dmplan.approve(batch, entries, by="operator")
        entries[0]["persona_plan"]["max_contacts_to_enrich"] = 1
        current, why = dmplan.is_current(batch, entries)
        self.assertFalse(current)
        self.assertIn("changed after approval", why)

    def test_a_changed_verdict_makes_the_approval_stale(self):
        batch, entries = {}, self.entries()
        dmplan.approve(batch, entries, by="operator")
        entries[0]["verdict"]["icp_tier"] = icp.TIER_C
        self.assertFalse(dmplan.is_current(batch, entries)[0])

    def test_the_fingerprint_is_stable_across_ordering(self):
        first = [{"record": {"id": "a"}, "verdict": {"icp_status": "qualified",
                                                     "icp_tier": "A"},
                  "persona_plan": {"max_contacts_to_enrich": 3,
                                   "target_titles": ["CEO"]}},
                 {"record": {"id": "b"}, "verdict": {"icp_status": "qualified",
                                                     "icp_tier": "B"},
                  "persona_plan": {"max_contacts_to_enrich": 2,
                                   "target_titles": ["COO"]}}]
        self.assertEqual(dmplan.fingerprint(first),
                         dmplan.fingerprint(list(reversed(first))))

    def test_approving_an_over_cap_plan_is_refused(self):
        entries = [{"record": {"id": f"r{i}", "domain": f"r{i}.test"},
                    "verdict": {"icp_status": icp.QUALIFIED,
                                "icp_tier": icp.TIER_A},
                    "persona_plan": {"max_contacts_to_enrich": 3,
                                     "target_titles": ["CEO"],
                                     "cap_reason": "tier A"}}
                   for i in range(10)]
        with self.assertRaises(dmplan.NotApproved):
            dmplan.approve({}, entries, by="operator",
                           config={"dm_plan": {"max_batch_credits": 5}})

    def test_require_raises_rather_than_returning_false(self):
        entries = self.entries()
        with self.assertRaises(dmplan.NotApproved):
            dmplan.require({}, entries, entries[0]["record"],
                           entries[0]["verdict"])


class TestCampaignSegments(CampaignTest):
    def entries(self, count, **kw):
        fields = dict(industry="Marketing", employees=90,
                      specialties=["digital marketing", "content marketing"],
                      country="United Kingdom", description=AGENCY_TEXT)
        fields.update(kw)
        out = []
        for i in range(count):
            company = rec(rid=f"c{i}", **fields)
            segment = segments.classify(company)
            verdict = qualified()
            out.append({"record": company, "segment": segment,
                        "verdict": verdict,
                        "persona_plan": routing.plan(company, segment, verdict)})
        return out

    def test_a_key_looks_like_the_documented_example(self):
        """Five parts, and the first one is *this* client.

        This asserted the key began with "PRODUCTIVE-" while passing no client
        config at all, which is how a real client's name came to be the global
        default prefix: the test was satisfied by the leak. The shape is the
        documented thing; whose name leads it is a property of the client.
        """
        assigned = campaignseg.assign(self.entries(60),
                                      config={"name": "Productive"})
        key = assigned[0]["segment_key"]
        self.assertTrue(key.startswith("PRODUCTIVE-"), key)
        self.assertEqual(len(key.split("-")), 5)

    def test_another_client_gets_its_own_name_on_its_own_keys(self):
        """The defect this file used to enshrine."""
        key = campaignseg.assign(self.entries(60),
                                 config={"name": "Acme Ltd"})[0]["segment_key"]
        self.assertTrue(key.startswith("ACMELTD-"), key)
        self.assertNotIn("PRODUCTIVE", key)

    def test_the_key_is_stable_for_the_same_company(self):
        first = campaignseg.assign(self.entries(60))[0]["segment_key"]
        second = campaignseg.assign(self.entries(60))[0]["segment_key"]
        self.assertEqual(first, second)

    def test_a_full_size_group_keeps_its_specific_key(self):
        assigned = campaignseg.assign(self.entries(60))
        self.assertEqual(assigned[0]["segment_rung"], "full")
        self.assertIn("UK", assigned[0]["segment_key"])
        self.assertIn("50_99", assigned[0]["segment_key"])

    def test_a_small_group_merges_upward(self):
        assigned = campaignseg.assign(self.entries(5))
        self.assertNotEqual(assigned[0]["segment_rung"], "full")
        self.assertTrue(assigned[0]["segment_reason"])

    def test_merging_says_what_was_given_up(self):
        assigned = campaignseg.assign(self.entries(5))
        self.assertIn("too few", assigned[0]["segment_reason"])

    def test_the_minimum_size_is_configurable(self):
        config = {"campaign_segments": {"min_segment_size": 3}}
        assigned = campaignseg.assign(self.entries(5), config)
        self.assertEqual(assigned[0]["segment_rung"], "full")

    def test_only_qualified_companies_are_segmented(self):
        entries = self.entries(60)
        entries[0]["verdict"] = {"icp_status": icp.REJECTED,
                                 "icp_tier": icp.TIER_NOT_ICP}
        assigned = campaignseg.assign(entries)
        rejected = next(e for e in assigned
                        if e["verdict"]["icp_status"] == icp.REJECTED)
        self.assertIsNone(rejected["segment_key"])
        self.assertIn("not segmented", rejected["segment_reason"])

    def test_two_companies_in_one_segment_can_be_explained(self):
        assigned = campaignseg.assign(self.entries(60))
        answer = campaignseg.why_together(assigned[0], assigned[1])
        self.assertTrue(answer["same_segment"])
        self.assertTrue(answer["why"])
        self.assertIn("region", answer["shared"])

    def test_two_companies_in_different_segments_are_told_apart(self):
        uk = campaignseg.assign(self.entries(60))
        de = campaignseg.assign(self.entries(60, country="Germany"))
        answer = campaignseg.why_together(uk[0], de[0])
        self.assertFalse(answer["same_segment"])

    def test_no_segment_explosion_at_scale(self):
        batch = companies.dataset(600, client="productive")
        result = qualify.run(batch, client="productive", store_result=False)
        summary = campaignseg.summarise(result["companies"])
        self.assertLess(summary["segments"], 40,
                        "the ladder is not merging small groups")

    def test_the_summary_names_segments_still_below_the_minimum(self):
        summary = campaignseg.summarise(campaignseg.assign(self.entries(5)))
        self.assertTrue(summary["below_minimum"])
        self.assertIn("nothing left to merge", summary["note"])


class TestMessagingStrategy(CampaignTest):
    def strategy_for(self, **kw):
        fields = dict(industry="Marketing", employees=90,
                      specialties=["digital marketing", "content marketing"],
                      country="United Kingdom", description=AGENCY_TEXT)
        fields.update(kw)
        company = rec(**fields)
        segment = segments.classify(company)
        verdict = icp.score(company)
        plan = routing.plan(company, segment, verdict)
        return strategy.for_company(segment, verdict, plan)

    def test_a_qualified_agency_gets_angles(self):
        result = self.strategy_for()
        self.assertTrue(result["recommended_angles"])
        self.assertTrue(result["relevant_pain_categories"])

    def test_every_recommended_angle_is_supported_by_evidence(self):
        result = self.strategy_for()
        for row in result["recommended_detail"]:
            self.assertTrue(row["supported"], row)
            self.assertTrue(row["supported_by"], row)

    def test_unsupported_angles_are_kept_as_hypotheses_not_recommendations(self):
        result = self.strategy_for()
        for pain in result["unsupported_hypotheses"]:
            self.assertNotIn(pain, result["recommended_angles"])

    def test_a_thinly_evidenced_company_gets_fewer_angles_not_invented_ones(self):
        """The case the previous test could not see.

        Where every typical angle happens to be supported, dropping the
        supported/unsupported split changes nothing and the test still passes.
        This company has the vertical and the size but none of the operational
        language, so most of its typical angles are hypotheses - and none of
        them may be recommended.
        """
        # Qualified, and deliberately silent about resourcing. The order
        # matters: for this vertical, resource_planning is the *first*
        # candidate angle, so a version that stopped filtering by support
        # would recommend it first. A company whose unsupported angles all sat
        # at the end of the list could not tell the two apart.
        result = self.strategy_for(
            offices=["London", "Leeds"],
            description=("We work on retainer for a client portfolio and "
                         "report project margin per engagement."))
        self.assertTrue(result["unsupported_hypotheses"])
        for pain in result["unsupported_hypotheses"]:
            self.assertNotIn(pain, result["recommended_angles"])
        for row in result["recommended_detail"]:
            self.assertTrue(row["supported"])
        self.assertLess(len(result["recommended_angles"]),
                        len(result["unsupported_hypotheses"])
                        + len(result["recommended_angles"]))

    def test_personas_get_the_pains_they_actually_own(self):
        result = self.strategy_for()
        for persona, rows in result["persona_angles"].items():
            owned = strategy.PERSONA_PAINS.get(persona, ())
            for row in rows:
                self.assertIn(row["pain"], owned)

    def test_a_software_agency_gets_different_angles_to_a_marketing_one(self):
        marketing = self.strategy_for()
        software = self.strategy_for(
            industry="Software", specialties=["software development",
                                              "custom software"],
            description=("Sprint based delivery for concurrent projects with "
                         "capacity planning and resourcing."))
        self.assertNotEqual(set(marketing["recommended_angles"]),
                            set(software["recommended_angles"]))

    def test_an_unqualified_company_gets_no_strategy(self):
        result = self.strategy_for(description="software as a service "
                                               "with pricing plans")
        self.assertEqual(result["recommended_angles"], [])
        self.assertIn("not qualified", result["why"])

    def test_no_email_copy_is_generated_here(self):
        import inspect
        source = inspect.getsource(strategy)
        for banned in ("Subject:", "Hi {", "llm.", "model.complete"):
            self.assertNotIn(banned, source, banned)


class TestThePipeline(CampaignTest):
    def batch(self, size=60):
        return companies.dataset(size, client="productive", batch="b1")

    def test_it_runs_end_to_end_without_a_provider(self):
        qualify.run(self.batch(), client="productive", batch="b1",
                    store_result=False)
        self.assertEqual(self.cassette.calls, [])

    def test_no_company_is_deleted(self):
        batch = self.batch()
        result = qualify.run(batch, client="productive", batch="b1",
                             store_result=False)
        self.assertEqual(len(result["companies"]), len(batch))

    def test_rejected_companies_keep_their_reasons(self):
        result = qualify.run(self.batch(), client="productive", batch="b1",
                             store_result=False)
        rejected = [e for e in result["companies"]
                    if e["verdict"]["icp_status"] == icp.REJECTED]
        self.assertTrue(rejected)
        for entry in rejected:
            self.assertTrue(entry["verdict"]["classification_reasons"])

    def test_the_batch_plans_zero_credits_for_everything_not_qualified(self):
        result = qualify.run(self.batch(), client="productive", batch="b1",
                             store_result=False)
        for entry in result["companies"]:
            if entry["verdict"]["icp_status"] == icp.QUALIFIED:
                continue
            self.assertEqual(entry["cost_plan"]["expected_credits"], 0)
            self.assertEqual(entry["cost_plan"]["maximum_credits"], 0)

    def test_prioritisation_puts_tier_a_first(self):
        result = qualify.run(self.batch(), client="productive", batch="b1",
                             store_result=False)
        ordered = qualify.prioritise(result["companies"])
        tiers = [e["verdict"]["icp_tier"] for e in ordered]
        self.assertEqual(tiers[0], icp.TIER_A)
        self.assertEqual(tiers[-1], icp.TIER_NOT_ICP)

    def test_prioritisation_is_deterministic(self):
        result = qualify.run(self.batch(), client="productive", batch="b1",
                             store_result=False)
        first = [e["record"]["id"] for e in qualify.prioritise(result["companies"])]
        second = [e["record"]["id"] for e in qualify.prioritise(result["companies"])]
        self.assertEqual(first, second)

    def test_the_summary_reports_every_dimension_the_brief_asks_for(self):
        result = qualify.run(self.batch(), client="productive", batch="b1",
                             store_result=False)
        summary = qualify.summarise(result)
        for name in ("vertical", "subvertical", "region", "country",
                     "employee_band", "timezone", "business_model"):
            self.assertIn(name, summary["distribution"], name)
        for name in ("qualified", "review", "rejected", "unknown"):
            self.assertIn(name, summary["icp"]["status"], name)


class TestResume(CampaignTest):
    def test_a_stopped_batch_resumes_where_it_stopped(self):
        batch = companies.dataset(40, client="productive", batch="b1")
        store.save(batch)
        first = qualify.run(store.load(), client="productive", batch="b1",
                            limit=15)
        store.save(store.load())
        self.assertEqual(first["processed"], 15)
        self.assertEqual(first["remaining"], 25)

    def test_completed_work_is_not_repeated(self):
        batch = companies.dataset(30, client="productive", batch="b1")
        store.save(batch)
        recs = store.load()
        qualify.run(recs, client="productive", batch="b1")
        store.save(recs)

        again = qualify.run(store.load(), client="productive", batch="b1")
        self.assertEqual(again["processed"], 0)
        self.assertEqual(again["reused"], 30)

    def test_changed_company_facts_are_requalified(self):
        batch = companies.dataset(10, client="productive", batch="b1")
        store.save(batch)
        recs = store.load()
        qualify.run(recs, client="productive", batch="b1")
        store.save(recs)

        recs = store.load()
        recs[0]["company_facts"]["employees"] = 500
        again = qualify.run(recs, client="productive", batch="b1")
        self.assertEqual(again["processed"], 1)
        self.assertEqual(again["reused"], 9)

    def test_force_requalifies_everything(self):
        batch = companies.dataset(10, client="productive", batch="b1")
        store.save(batch)
        recs = store.load()
        qualify.run(recs, client="productive", batch="b1")
        store.save(recs)
        again = qualify.run(store.load(), client="productive", batch="b1",
                            force=True)
        self.assertEqual(again["processed"], 10)

    def test_every_state_is_distinguishable(self):
        self.assertEqual(len(set(dmplan.STATES)), len(dmplan.STATES))
        for name in ("not_processed", "classified", "review_required",
                     "qualified", "rejected", "dm_enrichment_approved",
                     "dm_enrichment_pending"):
            self.assertIn(name, dmplan.STATES, name)

    def test_a_records_state_is_read_from_the_record(self):
        batch = companies.dataset(len(companies.ARCHETYPES),
                                  client="productive", batch="b1")
        self.assertEqual(qualify.state_of(batch[0]), dmplan.NOT_PROCESSED)
        qualify.run(batch, client="productive", batch="b1")
        states = {qualify.state_of(rec) for rec in batch}
        self.assertIn(dmplan.QUALIFIED, states)
        self.assertIn(dmplan.REJECTED, states)
        self.assertIn(dmplan.REVIEW_REQUIRED, states)


class TestTheDossier(CampaignTest):
    def entry(self):
        batch = companies.dataset(len(companies.ARCHETYPES),
                                  client="productive", batch="b1")
        result = qualify.run(batch, client="productive", batch="b1",
                             store_result=False)
        return next(e for e in result["companies"]
                    if e["verdict"]["icp_status"] == icp.QUALIFIED)

    def test_it_carries_every_section_the_brief_lists(self):
        dossier = qualify.dossier(self.entry())
        for section in ("icp", "segment", "evidence", "persona_plan",
                        "messaging_plan", "cost_plan", "campaign"):
            self.assertIn(section, dossier, section)

    def test_the_icp_section_explains_itself(self):
        icp_block = qualify.dossier(self.entry())["icp"]
        for field in ("score", "tier", "status", "confidence", "reasons",
                      "positive_signals", "negative_signals",
                      "missing_evidence"):
            self.assertIn(field, icp_block, field)

    def test_the_segment_section_carries_the_timezone_trio(self):
        segment = qualify.dossier(self.entry())["segment"]
        for field in ("timezone", "timezone_source", "timezone_confidence"):
            self.assertIn(field, segment, field)

    def test_the_cost_plan_is_visible_before_any_person_is_looked_up(self):
        cost = qualify.dossier(self.entry())["cost_plan"]
        self.assertIn("expected_credits", cost)
        self.assertIn("maximum_credits", cost)
        self.assertTrue(cost["calls"])

    def test_it_is_json_serialisable(self):
        import json
        json.dumps(qualify.dossier(self.entry()))

    def test_it_calls_no_provider(self):
        qualify.dossier(self.entry())
        self.assertEqual(self.cassette.calls, [])


if __name__ == "__main__":
    unittest.main()
