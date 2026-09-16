"""TASK-168: hold-reason taxonomy, call-site wiring, return-to-queue predicate.

Tests three things:
1. The taxonomy classifies every known reason code correctly.
2. The hold call sites (enrich.outcome, generate ModelError handler) write
   hold_reason onto the record.
3. The return-to-queue predicate refuses unless all three safety conditions
   are provably met.
"""
import os
import unittest

from src import holdreasons, store


class TaxonomyTest(unittest.TestCase):
    """Every known reason code maps to its class."""

    def test_enrich_unresolved_is_waiting(self):
        self.assertEqual(holdreasons.WAITING,
                         holdreasons.classify(
                             holdreasons.ENRICH_UNRESOLVED_VERDICT))

    def test_enrich_accept_all_is_waiting(self):
        self.assertEqual(holdreasons.WAITING,
                         holdreasons.classify(
                             holdreasons.ENRICH_ACCEPT_ALL_UNCLEARED))

    def test_enrich_no_contacts_is_permanent(self):
        self.assertEqual(holdreasons.PERMANENT,
                         holdreasons.classify(
                             holdreasons.ENRICH_NO_CONTACTS))

    def test_enrich_verifiers_disagree_is_human_review(self):
        self.assertEqual(holdreasons.HUMAN_REVIEW,
                         holdreasons.classify(
                             holdreasons.ENRICH_VERIFIERS_DISAGREE))

    def test_generation_evidence_trace_is_retryable(self):
        self.assertEqual(holdreasons.RETRYABLE,
                         holdreasons.classify(
                             holdreasons.GENERATION_EVIDENCE_TRACE))

    def test_generation_evidence_empty_is_retryable(self):
        self.assertEqual(holdreasons.RETRYABLE,
                         holdreasons.classify(
                             holdreasons.GENERATION_EVIDENCE_EMPTY))

    def test_generation_json_parse_is_retryable(self):
        self.assertEqual(holdreasons.RETRYABLE,
                         holdreasons.classify(
                             holdreasons.GENERATION_JSON_PARSE))

    def test_generation_lint_failure_is_human_review(self):
        self.assertEqual(holdreasons.HUMAN_REVIEW,
                         holdreasons.classify(
                             holdreasons.GENERATION_LINT_FAILURE))

    def test_undrop_is_actionable(self):
        self.assertEqual(holdreasons.ACTIONABLE,
                         holdreasons.classify(
                             holdreasons.UNDROP_PENDING_REENRICHMENT))

    def test_unknown_code_defaults_to_human_review(self):
        self.assertEqual(holdreasons.HUMAN_REVIEW,
                         holdreasons.classify("something:unknown"))


class SetHoldReasonTest(unittest.TestCase):
    """set_hold_reason writes all three fields."""

    def test_writes_reason_class_and_timestamp(self):
        rec = {"id": "test-1"}
        holdreasons.set_hold_reason(rec, holdreasons.ENRICH_UNRESOLVED_VERDICT)
        self.assertEqual(holdreasons.ENRICH_UNRESOLVED_VERDICT,
                         rec["hold_reason"])
        self.assertEqual(holdreasons.WAITING, rec["hold_class"])
        self.assertIn("T", rec["hold_at"])

    def test_writes_detail_when_given(self):
        rec = {"id": "test-2"}
        holdreasons.set_hold_reason(rec, holdreasons.GENERATION_EVIDENCE_TRACE,
                                    detail="evidence not traceable: foo")
        self.assertEqual("evidence not traceable: foo", rec["hold_detail"])

    def test_no_detail_field_when_omitted(self):
        rec = {"id": "test-3"}
        holdreasons.set_hold_reason(rec, holdreasons.PERMANENT)
        self.assertNotIn("hold_detail", rec)


class ReturnToQueuePredicateTest(unittest.TestCase):
    """can_return_to_queue refuses unless all three safety conditions hold."""

    def test_permanent_refused(self):
        rec = {"id": "x", "hold_reason": holdreasons.ENRICH_NO_CONTACTS}
        safe, why = holdreasons.can_return_to_queue(rec)
        self.assertFalse(safe)
        self.assertIn("permanent", why)

    def test_waiting_with_unresolved_contacts_refused(self):
        rec = {
            "id": "x",
            "hold_reason": holdreasons.ENRICH_UNRESOLVED_VERDICT,
            "contacts": [{"verdict": None}],
        }
        safe, why = holdreasons.can_return_to_queue(rec)
        self.assertFalse(safe)
        self.assertIn("unresolved", why)

    def test_waiting_with_resolved_contacts_allowed(self):
        rec = {
            "id": "x",
            "hold_reason": holdreasons.ENRICH_UNRESOLVED_VERDICT,
            "contacts": [{"verdict": "valid"}],
        }
        safe, why = holdreasons.can_return_to_queue(rec)
        self.assertTrue(safe)

    def test_actionable_with_contacts_and_resolved_allowed(self):
        rec = {
            "id": "x",
            "hold_reason": holdreasons.UNDROP_PENDING_REENRICHMENT,
            "contacts": [{"verdict": "valid"}],
        }
        safe, why = holdreasons.can_return_to_queue(rec)
        self.assertTrue(safe)

    def test_actionable_without_contacts_refused(self):
        rec = {
            "id": "x",
            "hold_reason": holdreasons.UNDROP_PENDING_REENRICHMENT,
            "contacts": [],
        }
        safe, why = holdreasons.can_return_to_queue(rec)
        self.assertFalse(safe)
        self.assertIn("no contacts", why)

    def test_actionable_with_unresolved_contacts_refused(self):
        rec = {
            "id": "x",
            "hold_reason": holdreasons.UNDROP_PENDING_REENRICHMENT,
            "contacts": [{"verdict": "accept_all"}],
        }
        safe, why = holdreasons.can_return_to_queue(rec)
        self.assertFalse(safe)
        self.assertIn("enrichment", why)

    def test_retryable_always_refused(self):
        rec = {
            "id": "x",
            "hold_reason": holdreasons.GENERATION_EVIDENCE_TRACE,
        }
        safe, why = holdreasons.can_return_to_queue(rec)
        self.assertFalse(safe)
        self.assertIn("model", why)

    def test_human_review_always_refused(self):
        rec = {
            "id": "x",
            "hold_reason": holdreasons.GENERATION_LINT_FAILURE,
        }
        safe, why = holdreasons.can_return_to_queue(rec)
        self.assertFalse(safe)
        self.assertIn("human", why)

    def test_no_hold_reason_refused(self):
        rec = {"id": "x"}
        safe, why = holdreasons.can_return_to_queue(rec)
        self.assertFalse(safe)


class EnrichHoldCallSiteTest(unittest.TestCase):
    """enrich.outcome returns a reason code for the hold branch."""

    def test_unresolved_verdict_returns_reason(self):
        from src.enrich import outcome
        rec = {"contacts": [{"verdict": None, "email": "a@b.com"}]}
        state, reason = outcome(rec)
        self.assertEqual("held", state)
        self.assertIsNotNone(reason)
        self.assertIn("enrich:", reason)

    def test_accept_all_returns_accept_all_code(self):
        from src.enrich import outcome
        rec = {"contacts": [{"verdict": "accept_all", "email": "a@b.com"}]}
        state, reason = outcome(rec)
        self.assertEqual("held", state)
        self.assertEqual(holdreasons.ENRICH_ACCEPT_ALL_UNCLEARED, reason)

    def test_mixed_unresolved_returns_unresolved_code(self):
        from src.enrich import outcome
        rec = {"contacts": [
            {"verdict": None, "email": "a@b.com"},
            {"verdict": "accept_all", "email": "c@d.com"},
        ]}
        state, reason = outcome(rec)
        self.assertEqual("held", state)
        self.assertEqual(holdreasons.ENRICH_UNRESOLVED_VERDICT, reason)

    def test_verified_does_not_hold(self):
        from src.enrich import outcome
        rec = {"contacts": [{"verdict": "valid", "sendable": True,
                              "email": "a@b.com"}]}
        state, reason = outcome(rec)
        self.assertEqual("verified", state)


class EnrichRecordHoldReasonTest(unittest.TestCase):
    """enrich_record writes hold_reason when outcome is held."""

    def setUp(self):
        import tempfile
        import shutil
        self.tmp = tempfile.mkdtemp(prefix="rga-hold-")
        self._orig = os.environ.get("QUEUE"), os.environ.get("OUT")
        os.environ["QUEUE"] = os.path.join(self.tmp, "queue.jsonl")
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        os.makedirs(os.path.dirname(os.environ["QUEUE"]), exist_ok=True)

    def tearDown(self):
        q, o = self._orig
        for name, value in (("QUEUE", q), ("OUT", o)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_hold_writes_hold_reason(self):
        from src import enrich
        rec = {
            "id": "test-hold-reason",
            "domain": "example.com",
            "state": "queued",
            "contacts": [
                {"email": "a@example.com", "verdict": "accept_all",
                 "sendable": False, "verification": {
                     "state": "accept_all_uncleared",
                     "evidence": [],
                 }},
            ],
            "company_facts": {"name": "Test Co", "headcount": 10},
            "verdict": {"icp_status": "qualified",
                        "icp_confidence": "high"},
        }

        budget = enrich.Budget(cap=None)
        enrich.enrich_record(rec, budget)
        self.assertEqual("held", rec["state"])
        self.assertIn("hold_reason", rec)
        self.assertIn("hold_class", rec)
        self.assertIn("hold_at", rec)


class GenerateHoldCallSiteTest(unittest.TestCase):
    """generate writes hold_reason on ModelError through the real entry point."""

    def test_model_error_sets_hold_reason(self):
        from unittest.mock import patch
        from src import generate, llm

        rec = {
            "id": "test-gen-hold",
            "domain": "example.com",
            "state": "enriched",
            "contacts": [{"email": "a@example.com", "sendable": True,
                          "key": "a-example-com", "primary": True,
                          "name": "Test Person",
                          "linkedin": "https://linkedin.com/in/test"}],
            "company_facts": {"name": "Test Co", "headcount": 10},
            "research": {"evidence": ["fact one"]},
            "cadence": {},
            "verdict": {"icp_status": "qualified",
                        "icp_confidence": "high"},
            "log": [],
            "client": "test",
        }

        fake_op = {"step": "diagnose", "day": 1}

        def boom_diagnose(r, m):
            raise llm.ModelError(
                "evidence not traceable to the record: fabricated fact")

        with patch.object(generate, "plan", return_value=iter([fake_op])), \
             patch.object(generate, "diagnose", side_effect=boom_diagnose):
            generate.generate_record(rec, None)

        self.assertEqual("held", rec["state"])
        self.assertEqual(holdreasons.GENERATION_EVIDENCE_TRACE,
                         rec.get("hold_reason"))
        self.assertEqual(holdreasons.RETRYABLE, rec.get("hold_class"))


class BackfillClassifierTest(unittest.TestCase):
    """The backfill classifier reconstructs reasons from log data."""

    def test_undrop_detected(self):
        from scripts.task168_backfill import classify_from_log
        rec = {
            "log": [{"step": "un-dropped", "note": "reinstated"}],
            "contacts": [],
        }
        code, detail = classify_from_log(rec)
        self.assertEqual(holdreasons.UNDROP_PENDING_REENRICHMENT, code)

    def test_generation_evidence_trace_detected(self):
        from scripts.task168_backfill import classify_from_log
        rec = {
            "log": [{"step": "persona_angle",
                     "note": "held: evidence not traceable to the record: x"}],
            "contacts": [],
        }
        code, detail = classify_from_log(rec)
        self.assertEqual(holdreasons.GENERATION_EVIDENCE_TRACE, code)

    def test_generation_evidence_empty_detected(self):
        from scripts.task168_backfill import classify_from_log
        rec = {
            "log": [{"step": "persona_angle",
                     "note": "held: evidence must be a non-empty list"}],
            "contacts": [],
        }
        code, detail = classify_from_log(rec)
        self.assertEqual(holdreasons.GENERATION_EVIDENCE_EMPTY, code)

    def test_generation_json_parse_detected(self):
        from scripts.task168_backfill import classify_from_log
        rec = {
            "log": [{"step": "draft",
                     "note": "held: answer was not JSON"}],
            "contacts": [],
        }
        code, detail = classify_from_log(rec)
        self.assertEqual(holdreasons.GENERATION_JSON_PARSE, code)

    def test_enrich_accept_all_detected(self):
        from scripts.task168_backfill import classify_from_log
        rec = {
            "log": [{"step": "held", "note": "enriched: 2 provider call(s)"}],
            "contacts": [{"verdict": "accept_all"}],
        }
        code, detail = classify_from_log(rec)
        self.assertEqual(holdreasons.ENRICH_ACCEPT_ALL_UNCLEARED, code)

    def test_enrich_unresolved_detected(self):
        from scripts.task168_backfill import classify_from_log
        rec = {
            "log": [{"step": "held", "note": "enriched: 1 provider call(s)"}],
            "contacts": [{"verdict": None}],
        }
        code, detail = classify_from_log(rec)
        self.assertEqual(holdreasons.ENRICH_UNRESOLVED_VERDICT, code)

    def test_no_contacts_detected(self):
        from scripts.task168_backfill import classify_from_log
        rec = {
            "log": [{"step": "held", "note": "enriched: 2 provider call(s)"}],
            "contacts": [],
        }
        code, detail = classify_from_log(rec)
        self.assertEqual(holdreasons.ENRICH_NO_CONTACTS, code)

    def test_verifiers_disagree_detected(self):
        from scripts.task168_backfill import classify_from_log
        rec = {
            "log": [{"step": "held",
                     "note": "held (verifiers disagree)"}],
            "contacts": [{"verdict": "valid"}],
        }
        code, detail = classify_from_log(rec)
        self.assertEqual(holdreasons.ENRICH_VERIFIERS_DISAGREE, code)


if __name__ == "__main__":
    unittest.main()
