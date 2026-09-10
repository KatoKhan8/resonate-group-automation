"""ContactOut is the primary. Part 23.

The credits are the operator's own, so ContactOut is asked first wherever it can
answer. That is a rule about order and necessity, not a licence to call it more:
a stored answer still beats a call, and a free call still beats a paid one.
"""
import os
import shutil
import tempfile
import unittest

from src import clients, enrich, research, store, verification
from src.providers import apify, deliverable
from tests.base import FIXTURES, ProviderTest, qualify_everything


class WaterfallTest(ProviderTest):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-first-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase4.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.config = clients.load("productive")
        # These fixtures are the *waterfall* under test - which call runs
        # first, what a fallback costs, how a collision is excluded. Person-
        # level enrichment is gated on an ICP verdict, so without one they
        # would be asserting the gate instead. `tests/test_icp_spend_gate.py`
        # holds the other side of that rule.
        qualify_everything()

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def enrich(self, ids=None, **kw):
        return enrich.run(live=True, ids=ids, **kw)

    def urls(self):
        return " ".join(self.cassette.urls())


class TestStoredDataWinsFirst(WaterfallTest):
    def test_a_record_with_contacts_buys_no_discovery(self):
        self.enrich(ids=["meridian"])
        self.assertNotIn("decision-makers", self.urls())
        self.assertNotIn("ai-ark", self.urls())

    def test_a_stored_verdict_is_not_bought_again(self):
        self.enrich(ids=["meridian"])
        verify = "contactout.com/v1/email/verify"
        first = len([u for u in self.cassette.urls() if verify in u])
        self.enrich(ids=["meridian"])
        second = len([u for u in self.cassette.urls() if verify in u])
        # Both counts were zero while this matched the wrong path, so the
        # equality held on nothing. It has to count a real call to mean anything.
        self.assertGreater(first, 0)
        self.assertEqual(first, second)

    def test_a_resumed_run_repeats_no_paid_call(self):
        self.enrich()
        before = len(self.cassette.calls)
        self.enrich()
        self.assertEqual(len(self.cassette.calls), before)


class TestFreeBeforePaid(WaterfallTest):
    def test_the_free_count_runs_before_any_paid_discovery(self):
        self.enrich(ids=["samename"])
        urls = self.cassette.urls()
        self.assertIn("people/count", urls[0])
        paid = next(i for i, u in enumerate(urls) if "decision-makers" in u)
        self.assertLess(0, paid)

    def test_a_zero_count_stops_the_paid_search_entirely(self):
        self.enrich(ids=["parked"])
        self.assertNotIn("decision-makers", self.urls())
        self.assertIn("domain/enrich", self.urls())

    def test_the_free_call_is_costed_at_zero(self):
        self.assertEqual(enrich.COSTS["people-count"], 0)


class TestContactOutBeatsAiArk(WaterfallTest):
    def test_ai_ark_does_not_run_when_contactout_found_people(self):
        self.enrich(ids=["samename"])
        self.assertIn("decision-makers", self.urls())
        self.assertNotIn("ai-ark", self.urls())

    def test_ai_ark_runs_only_after_contactout_found_nobody(self):
        self.enrich(ids=["parked"])
        urls = self.cassette.urls()
        self.assertIn("ai-ark", " ".join(urls))
        contactout_first = min(i for i, u in enumerate(urls) if "contactout" in u)
        aiark_at = min(i for i, u in enumerate(urls) if "ai-ark" in u)
        self.assertLess(contactout_first, aiark_at)

    def test_the_fallback_carries_a_machine_readable_reason(self):
        result = self.enrich(ids=["parked"])
        rec = store.get("parked")
        reasons = [e.get("reason") for e in rec["events"]
                   if e["type"] == "provider_call_planned" and e.get("provider") == "aiark"]
        self.assertTrue(reasons)
        self.assertTrue(any(r in enrich.FALLBACK_REASONS or
                            any(code in r for code in enrich.FALLBACK_REASONS)
                            for r in reasons), reasons)

    def test_every_fallback_reason_is_from_the_documented_set(self):
        for code in enrich.FALLBACK_REASONS:
            self.assertRegex(code, r"^[a-z_]+$")


class TestApifyIsLastAndOptional(WaterfallTest):
    def test_apify_does_not_run_when_structured_evidence_is_enough(self):
        """With the evidence actually present, so the claim is tested.

        This ran the whole fixture and asserted no apify URL, which passed
        because the client had not enabled apify at all - the assertion was
        true for a reason that had nothing to do with structured evidence.
        The client now opts in, so the condition has to be established here.

        AND "ENOUGH" HAS TO MEAN ENOUGH FOR EVERY CONSUMER. Setting industry
        and specialties satisfies the hook and the angle, and says nothing to
        the six ICP dimensions that match against PROSE - which is a question
        structured providers do not answer at all, and the reason
        NEED_ICP_EVIDENCE is a separate branch of `research.why`. Once that
        branch became reachable (it never fired before 2026-09-10, because the
        verdict it reads is written by a later stage) this test failed, and it
        was right to: the fixture was not actually sufficient.

        So the description now carries an operational phrase, which is what
        genuine sufficiency looks like.
        """
        with store.transaction() as recs:
            for rec in recs:
                rec["company_facts"] = dict(
                    rec.get("company_facts") or {},
                    industry="Advertising", specialties=["SEO"],
                    description="Our delivery team of account managers runs "
                                "resource planning across concurrent client "
                                "projects, tracking utilisation and billable "
                                "time against project margin.")
        self.enrich()
        self.assertNotIn("apify", self.urls())

    def test_apify_does_run_when_only_the_prose_dimensions_are_missing(self):
        """The other half, and the behaviour that made the above fail.

        Rich firmographics and no operational prose is the ordinary case - it
        is what ContactOut returns for almost every company - and it leaves
        six of twelve ICP dimensions unscoreable. Reading the company's own
        site is the only way to answer them, so research SHOULD fire here even
        though the hook and the angle are both satisfied.

        Measured on the real 50-domain cohort: 30 records in exactly this
        state, and zero scrapes on any of them, because the branch could not
        be reached.
        """
        with store.transaction() as recs:
            for rec in recs:
                rec["company_facts"] = dict(rec.get("company_facts") or {},
                                            industry="Advertising",
                                            specialties=["SEO"])
        self.enrich()
        self.assertIn("apify", self.urls())

    def test_apify_is_not_planned_without_a_stated_need(self):
        rec = store.get("meridian")
        rec["company_facts"] = {"industry": "Advertising", "specialties": ["SEO"]}
        self.assertIsNone(research.why(rec))

    def test_apify_is_not_run_even_when_needed_unless_the_client_enables_it(self):
        rec = store.get("samename")
        rec["lane"] = "cold"
        rec["hook"] = None
        rec["company_facts"] = {}
        # The client's own file with the opt-in taken out, rather than a
        # client that happens not to have opted in yet.
        proposal = research.plan(rec, dict(self.config, research={}))
        self.assertFalse(proposal["planned"])
        self.assertIn("not enabled", proposal["why_not"])

    def test_with_the_client_enabled_a_need_produces_a_bounded_plan(self):
        config = dict(self.config, research={"apify": {"enabled": True}})
        rec = store.get("samename")
        rec["lane"] = "cold"
        rec["hook"] = None
        rec["company_facts"] = {}
        proposal = research.plan(rec, config)
        self.assertTrue(proposal["planned"])
        self.assertEqual(proposal["reason"], research.NEED_HOOK_EVIDENCE)
        self.assertTrue(proposal["urls"])


class TestVerificationSpendStopsEarly(WaterfallTest):
    def test_an_invalid_address_buys_no_second_opinion(self):
        c = {"key": "x", "email": "gone@retired.test"}
        verification.verify(c, live=True)
        self.assertNotIn("reoon", self.urls())
        self.assertNotIn("deliverable", self.urls())

    def test_reoon_never_runs_for_an_obviously_invalid_address(self):
        c = {"key": "x", "email": "gone@retired.test"}
        verification.verify(c, live=True)
        self.assertEqual([u for u in self.cassette.urls() if "reoon" in u], [])

    def test_deliverable_does_not_run_when_the_primary_settled_it(self):
        c = {"key": "x", "email": "tomislav.baric@meridian.test"}
        verification.verify(c, live=True)
        self.assertNotIn("deliverable", self.urls())

    def test_the_cap_stops_the_fan_out_before_the_over_cap_call(self):
        result = self.enrich(cap=1)
        self.assertLessEqual(result["spent"], 1)
        self.assertTrue(result["refused"])
        self.assertNotIn("decision-makers", self.urls())


class TestTheSection9SafeguardsSurvive(WaterfallTest):
    def test_current_work_location_is_never_sent(self):
        self.enrich()
        self.assertNotIn("current_work_location", self.urls())

    def test_a_company_name_collision_is_still_excluded(self):
        self.enrich(ids=["samename"])
        rec = store.get("samename")
        self.assertEqual([c["name"] for c in rec["contacts"]], ["Mirna Zorić"])
        self.assertTrue(any("collision" in e["why"] for e in rec["excluded"]))

    def test_domain_and_mail_domain_stay_distinct(self):
        self.enrich(ids=["parked"])
        rec = store.get("parked")
        self.assertEqual(rec["domain"], "parked.test")
        self.assertEqual(rec["company_facts"]["email_domain"], "halcyon.test")

    def test_no_raw_provider_payload_reaches_the_queue(self):
        self.enrich()
        import json
        blob = json.dumps(store.load())
        for noise in ("contact_info", "profile_picture", "smtp_transcript",
                      "debug_log", "raw_smtp", "totalElements", "<html>"):
            self.assertNotIn(noise, blob, noise)


class TestDeliverableStaysBehindItsContract(WaterfallTest):
    def test_it_refuses_to_call_while_the_contract_is_unconfirmed(self):
        with self.assertRaises(deliverable.ContractNotVerified):
            deliverable.verify("someone@example.test")
        self.assertEqual(self.cassette.calls, [])

    def test_the_waterfall_treats_that_refusal_as_no_evidence(self):
        c = {"key": "x", "email": "luka.peric@lumen.test"}
        verification.verify(c, live=True)
        entry = next(e for e in c["verification"]["evidence"]
                     if e["provider"] == "deliverable")
        self.assertEqual(entry["status"], "error")
        self.assertFalse(c["sendable"])

    def test_a_confirmed_contract_lets_it_build_a_request(self):
        self.confirm_deliverable_contract()
        plan = deliverable.build_request("someone@example.test")
        self.assertEqual(plan["method"], "POST")
        self.assertEqual(plan["body"], {"email": "someone@example.test"})
        self.assertTrue(plan["url"].endswith("/verify/single"))
        self.assertEqual(plan["headers"]["x-api-key"], "test-key-not-real")


if __name__ == "__main__":
    unittest.main()
