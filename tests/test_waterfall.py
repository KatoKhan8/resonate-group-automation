"""ContactOut first, and a paid fallback only with a reason.

The invariant is one line and the tests are mostly about the ways it gets
broken quietly: a fallback that runs because it exists, a reason invented at
the call site, a stage that starts somewhere other than the provider we have
already paid for.
"""
import unittest

from src import verification
from src import enrich, store, waterfall
from tests.test_enrich import EnrichTest


class TestTheShape(unittest.TestCase):
    def test_every_stage_starts_with_contactout(self):
        for stage in waterfall.STAGE_NAMES:
            self.assertTrue(waterfall.contactout_is_first(stage), stage)

    def test_the_seven_stages_the_brief_asks_for_all_exist(self):
        for stage in ("company_information", "people_discovery", "linkedin_url",
                      "email_discovery", "email_verification",
                      "company_research", "person_research"):
            self.assertIn(stage, waterfall.STAGES)

    def test_every_stage_asks_a_question_in_words(self):
        for stage, spec in waterfall.STAGES.items():
            self.assertTrue(spec["question"], stage)

    def test_every_step_says_why_it_exists_and_when_it_is_enough(self):
        for stage, spec in waterfall.STAGES.items():
            for step in spec["providers"]:
                self.assertTrue(step["why"], f"{stage}/{step['provider']}")
                self.assertTrue(step["sufficient_when"],
                                f"{stage}/{step['provider']}")

    def test_every_step_that_leaves_contactout_declares_its_reason(self):
        """The rule that makes the invariant enforceable rather than aspirational."""
        for stage, spec in waterfall.STAGES.items():
            for step in spec["providers"]:
                if step["provider"] == waterfall.CONTACTOUT:
                    continue
                # Free primary-path steps (webfetch) need no reason; the rule
                # is that PAID fallbacks must state why they are running.
                if step.get("is_fallback") is False:
                    continue
                if step["provider"] == waterfall.WEBFETCH:
                    continue
                self.assertTrue(step.get("requires_reason"),
                                f"{stage}/{step['provider']} may be called "
                                "without stating why")

    def test_every_declared_reason_is_one_enrich_actually_produces(self):
        known = set(enrich.FALLBACK_REASONS) | {"verification_inconclusive",
                                                "verification_contradiction"}
        for stage in waterfall.STAGE_NAMES:
            for step in waterfall.STAGES[stage]["providers"]:
                for reason in waterfall.accepted_reasons(stage,
                                                          step["provider"],
                                                          step["call"]):
                    self.assertIn(reason, known, f"{stage}: {reason}")

    def test_every_step_carries_a_cost_in_a_named_unit(self):
        for stage, spec in waterfall.describe().items():
            for step in spec["providers"]:
                self.assertIsNotNone(step["expected_cost"], stage)
                self.assertTrue(step["cost_unit"], stage)

    def test_apify_cost_is_not_presented_as_free(self):
        """Zero credits is true and misleading without the unit beside it."""
        step = [s for s in waterfall.describe()["company_research"]["providers"]
                if s["provider"] == waterfall.APIFY][0]
        self.assertEqual(step["expected_cost"], 0)
        self.assertIn("compute units", step["cost_unit"])


class TestTheRule(unittest.TestCase):
    def test_the_first_provider_needs_no_reason(self):
        ok, _ = waterfall.may_fall_back("company_information",
                                        waterfall.CONTACTOUT, None)
        self.assertTrue(ok)

    def test_a_second_contactout_call_is_the_primary_path_not_a_fallback(self):
        ok, why = waterfall.may_fall_back("people_discovery",
                                          waterfall.CONTACTOUT, None,
                                          "decision-makers")
        self.assertTrue(ok)
        self.assertIn("primary path", why)

    def test_a_paid_fallback_without_a_reason_is_refused(self):
        ok, why = waterfall.may_fall_back("people_discovery", waterfall.AIARK,
                                          None)
        self.assertFalse(ok)
        self.assertIn("needs a reason", why)

    def test_an_invented_reason_is_refused(self):
        ok, why = waterfall.may_fall_back("company_research", waterfall.APIFY,
                                          "seemed like a good idea")
        self.assertFalse(ok)
        self.assertIn("not a reason", why)

    def test_a_declared_reason_is_accepted(self):
        ok, _ = waterfall.may_fall_back("people_discovery", waterfall.AIARK,
                                        enrich.CONTACTOUT_NO_PEOPLE)
        self.assertTrue(ok)

    def test_a_reason_from_a_different_stage_does_not_transfer(self):
        ok, _ = waterfall.may_fall_back("company_research", waterfall.APIFY,
                                        enrich.CONTACTOUT_NO_PEOPLE)
        self.assertFalse(ok, "no people found is not a reason to scrape a site")

    def test_a_provider_not_in_the_stage_is_refused(self):
        ok, why = waterfall.may_fall_back("company_research", waterfall.REOON,
                                          "anything")
        self.assertFalse(ok)
        self.assertIn("not part of", why)

    def test_an_unknown_stage_raises_rather_than_permitting(self):
        with self.assertRaises(KeyError):
            waterfall.may_fall_back("wishful_thinking", waterfall.APIFY, "x")

    def test_require_raises_with_the_reason_named(self):
        with self.assertRaises(waterfall.WaterfallViolation) as e:
            waterfall.require("company_research", waterfall.APIFY, None)
        self.assertIn("needs a reason", str(e.exception))

    def test_the_third_verification_opinion_never_resolves_automatically(self):
        step = waterfall.step_for("email_verification", waterfall.REOON)
        self.assertIn("holds the contact", step["sufficient_when"])


class TestTheLedger(unittest.TestCase):
    def record(self):
        return {"id": "acme"}

    def test_a_step_records_all_six_required_fields(self):
        rec = self.record()
        row = waterfall.record_step(rec, "people_discovery",
                                    waterfall.CONTACTOUT, "decision-makers",
                                    result="2 people", next_reason="none")
        for field in ("reason", "provider", "expected_cost", "actual_cost",
                      "result", "next_reason"):
            self.assertIn(field, row)

    def test_an_unjustified_step_is_refused_rather_than_logged(self):
        rec = self.record()
        with self.assertRaises(waterfall.WaterfallViolation):
            waterfall.record_step(rec, "company_research", waterfall.APIFY,
                                  "apify-research")
        self.assertEqual(waterfall.ledger(rec), [],
                         "a refused step must leave no trace of having run")

    def test_the_expected_cost_comes_from_the_cost_table(self):
        rec = self.record()
        row = waterfall.record_step(rec, "company_information",
                                    waterfall.CONTACTOUT,
                                    "company-information-from-domain")
        self.assertEqual(row["expected_cost"],
                         enrich.COSTS["company-information-from-domain"])

    def test_actual_cost_stays_none_when_nobody_told_us(self):
        rec = self.record()
        row = waterfall.record_step(rec, "company_information",
                                    waterfall.CONTACTOUT,
                                    "company-information-from-domain")
        self.assertIsNone(row["actual_cost"],
                          "a guess in this field makes the ledger useless")

    def test_reported_spend_is_none_when_no_provider_reported_any(self):
        rec = self.record()
        waterfall.record_step(rec, "company_information", waterfall.CONTACTOUT,
                              "company-information-from-domain")
        self.assertIsNone(waterfall.spend(rec)["reported"])

    def test_reported_spend_appears_once_a_provider_reports(self):
        rec = self.record()
        waterfall.record_step(rec, "people_discovery", waterfall.AIARK,
                              "aiark-people-search",
                              reason=enrich.CONTACTOUT_NO_PEOPLE,
                              actual_cost=2)
        self.assertEqual(waterfall.spend(rec)["reported"], 2)

    def test_spend_splits_by_provider_and_stage(self):
        rec = self.record()
        waterfall.record_step(rec, "people_discovery", waterfall.CONTACTOUT,
                              "decision-makers")
        waterfall.record_step(rec, "people_discovery", waterfall.AIARK,
                              "aiark-people-search",
                              reason=enrich.CONTACTOUT_NO_TARGET_PERSONA)
        spend = waterfall.spend(rec)
        self.assertEqual(spend["by_provider"]["contactout"]["calls"], 1)
        self.assertEqual(spend["by_stage"]["people_discovery"]["calls"], 2)

    def test_the_audit_is_clean_when_every_step_was_justified(self):
        rec = self.record()
        waterfall.record_step(rec, "people_discovery", waterfall.CONTACTOUT,
                              "people-count")
        waterfall.record_step(rec, "people_discovery", waterfall.AIARK,
                              "aiark-people-search",
                              reason=enrich.CONTACTOUT_NO_PEOPLE)
        self.assertEqual(waterfall.audit(rec)["unjustified"], [])

    def test_the_audit_catches_a_step_written_around_the_check(self):
        rec = self.record()
        rec["waterfall"] = [waterfall.entry("company_research",
                                            waterfall.APIFY, "apify-research")]
        problems = waterfall.audit(rec)["unjustified"]
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["provider"], waterfall.APIFY)

    def test_the_audit_admits_what_it_cannot_see(self):
        self.assertIn("never called record_step",
                      waterfall.audit(self.record())["unlogged"])


if __name__ == "__main__":
    unittest.main()


class TestTheLedgerIsActuallyWritten(EnrichTest):
    """The audit must not be able to report a clean record it never watched.

    `waterfall.audit()` reads the ledger, so an empty ledger reports zero
    unjustified steps. That is indistinguishable from a disciplined run unless
    something proves the ledger is written by the code that actually spends.
    Before these tests, `record_step` was called only from tests, and every
    real record audited clean on no evidence.
    """

    def test_enrichment_that_spent_leaves_a_ledger(self):
        enrich.run(live=True, ids=["meridian"])
        rec = store.get("meridian")
        self.assertTrue(waterfall.ledger(rec),
                        "enrichment ran and the waterfall ledger is empty")

    def test_the_audit_cannot_report_zero_activity_after_a_real_run(self):
        enrich.run(live=True, ids=["meridian"])
        report = waterfall.audit(store.get("meridian"))
        self.assertGreater(report["steps"], 0,
                           "the spend audit reported no provider activity for "
                           "a record that was actually enriched")

    def test_the_ledger_accounts_for_every_call_that_was_charged(self):
        """The ledger and the bill cannot diverge - including the verifiers.

        This used to exclude them, on the grounds that "the verifiers run
        through verification.py and keep their own evidence trail". An
        evidence trail is not a spend ledger: `verification.verify` charged
        the budget and wrote nothing here, so one to three credits per address
        - most of the bill at any real list size - were invisible to
        `waterfall.audit`. CLAUDE.md calls an audit that reports clean because
        it watched nothing worse than no audit at all.
        """
        result = enrich.run(live=True, ids=["meridian"])
        rec = store.get("meridian")
        ledger = waterfall.ledger(rec)

        # Every enrichment call that was charged has a row.
        entry = next(r for r in result["records"] if r["id"] == "meridian")
        charged = [op["call"] for op in entry["ops"]
                   if op["call"] in enrich.CALL_STAGE]
        logged = [row["call"] for row in ledger]
        for call in charged:
            self.assertIn(call, logged, call)

        # And so does every verifier that ran, named as the waterfall names it.
        for provider in {e["provider"] for c in (rec.get("contacts") or [])
                         for e in verification.all_evidence(c)}:
            self.assertIn(verification.CALL_NAMES.get(provider, provider),
                          logged, provider)

        # The totals agree: what the ledger says was spent is what was spent.
        self.assertEqual(waterfall.spend(rec)["expected"], result["spent"])

    def test_a_real_run_is_justified_at_every_step(self):
        enrich.run(live=True)
        for rec in store.load():
            report = waterfall.audit(rec)
            self.assertEqual(report["unjustified"], [],
                             f"{rec['id']}: {report['unjustified']}")

    def test_every_charged_call_is_routed_to_a_stage(self):
        """An unrouted call would land in the default stage and misreport."""
        for call in enrich.COSTS:
            self.assertIn(call, enrich.CALL_STAGE,
                          f"{call} has a cost but no waterfall stage")

    def test_every_routed_stage_is_a_real_stage(self):
        for call, stage in enrich.CALL_STAGE.items():
            self.assertIn(stage, waterfall.STAGES, f"{call} -> {stage}")

    def test_every_reason_enrich_can_offer_is_one_the_policy_accepts(self):
        """The direction the original test did not check.

        `test_every_declared_reason_is_one_enrich_actually_produces` asserts
        the policy names no reason enrich cannot produce. It said nothing about
        the reverse, which is how the AI Ark step came to accept two of the
        five reasons enrich hands it: a rebrand, a parked domain and an
        all-collisions result set were all refused at audit while enrich went
        on producing them.
        """
        accepted = waterfall.accepted_reasons(
            waterfall.PEOPLE_DISCOVERY, waterfall.AIARK, "aiark-people-search")
        for reason in (enrich.CONTACTOUT_NO_PEOPLE,
                       enrich.CONTACTOUT_NO_TARGET_PERSONA,
                       enrich.CONTACTOUT_RESULT_COLLISION,
                       enrich.CONTACTOUT_REBRAND_DETECTED,
                       enrich.DOMAIN_UNSTAFFED):
            self.assertIn(reason, accepted,
                          f"enrich falls back on {reason} and the policy "
                          "refuses it")
