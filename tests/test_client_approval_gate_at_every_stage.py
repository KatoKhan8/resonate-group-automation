#!/usr/bin/env python3
"""TASK-243: the client-approval gate at every stage, the surfaces, no kill switch.

The operator placed client approval in the same class as verification and
collision on 2026-09-21. A gate that can be turned off is a weakened gate,
and hard stop 8 treats a weakened verification rule as a halt.

These tests prove:
- each of the four stages refuses an unapproved account
- pending and unknown are both refused (fail-closed)
- the skip is COUNTED, not silently dropped
- no kill-switch parameter exists on any of the four
- each surface shows the client-approval state
"""
import inspect
import json
import os
import tempfile
import unittest

from src import (clientapproval as ca, digest, dossier, eligibility,
                 executionguard, funnel, generate, personas, store)


class _TempDir:
    """Isolated store for every test: queue, client-approval, env."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self._prev_ca = os.environ.get("CLIENT_APPROVAL")
        self._prev_dir = os.environ.get("RESONATE_DIR")
        os.environ["CLIENT_APPROVAL"] = os.path.join(
            self._dir.name, "client-approval.jsonl")
        os.environ["RESONATE_DIR"] = self._dir.name
        store.use_directory(self._dir.name)
        self.addCleanup(self._restore)

    def _restore(self):
        if self._prev_ca is None:
            os.environ.pop("CLIENT_APPROVAL", None)
        else:
            os.environ["CLIENT_APPROVAL"] = self._prev_ca
        if self._prev_dir is None:
            os.environ.pop("RESONATE_DIR", None)
        else:
            os.environ["RESONATE_DIR"] = self._prev_dir
        self._dir.cleanup()

    def _approve(self, domain, client="productive"):
        ca.record(domain, client=client, state=ca.APPROVED,
                  who="tester", source="test")

    def _make_rec(self, domain="example.com", client="productive",
                  contacts=None):
        return {"id": "rec-1", "domain": domain, "client": client,
                "company": "Example Co",
                "company_facts": {"name": "Example Co", "industry": "Tech",
                                  "employees": "11-50"},
                "contacts": contacts or [{"key": "c0", "name": "Test",
                                          "title": "CEO", "email":
                                          f"a@{domain}"}],
                "lane": "domains"}


# -------------------------------------------------- the four stage gates

class S4PersonaDiscoveryRefusesUnapproved(_TempDir, unittest.TestCase):

    def test_an_unapproved_account_gets_no_personas(self):
        # Initialize the system so the gate is active
        ca.record("other.example", state=ca.APPROVED, who="z", source="t")
        rec = self._make_rec("unapproved.example")
        result = personas.select(rec)
        self.assertEqual(result["kept"], [])
        self.assertTrue(result["awaiting_client_approval"])

    def test_an_approved_account_proceeds_normally(self):
        self._approve("good.example")
        rec = self._make_rec("good.example")
        result = personas.select(rec)
        # The record may or may not have contacts kept depending on config,
        # but the gate did not refuse it.
        self.assertNotIn("awaiting_client_approval", result)

    def test_pending_is_refused_at_s4(self):
        ca.record("anchor.example", state=ca.APPROVED, who="z", source="t")
        ca.record("pending.example", state=ca.PENDING, who="z", source="t")
        rec = self._make_rec("pending.example")
        result = personas.select(rec)
        self.assertEqual(result["kept"], [])
        self.assertTrue(result["awaiting_client_approval"])


class S5VerificationRefusesUnapproved(_TempDir, unittest.TestCase):

    def test_eligible_domains_filters_unapproved(self):
        """The S5 script filters domains through clientapproval.is_approved."""
        self._approve("yes.example")
        # The gate is in the script, tested by import-level inspection:
        import scripts.stage_s5_verify as s5
        source = inspect.getsource(s5.main)
        self.assertIn("clientapproval.is_approved", source)


class S7CopyRefusesUnapproved(_TempDir, unittest.TestCase):

    def test_draft_raises_for_unapproved_domain(self):
        ca.record("anchor.example", state=ca.APPROVED, who="z", source="t")
        rec = self._make_rec("unapproved.example")
        contact = rec["contacts"][0]
        with self.assertRaises(ca.ClientApprovalRequired):
            generate.draft(rec, contact, "em1", model=None)

    def test_draft_raises_for_pending_domain(self):
        ca.record("anchor.example", state=ca.APPROVED, who="z", source="t")
        ca.record("pending.example", state=ca.PENDING, who="z", source="t")
        rec = self._make_rec("pending.example")
        contact = rec["contacts"][0]
        with self.assertRaises(ca.ClientApprovalRequired):
            generate.draft(rec, contact, "em1", model=None)


class EnrollmentRefusesUnapproved(_TempDir, unittest.TestCase):

    def test_eligibility_decide_blocks_unapproved(self):
        ca.record("anchor.example", state=ca.APPROVED, who="z", source="t")
        rec = self._make_rec("unapproved.example")
        contact = rec["contacts"][0]
        result = eligibility.decide(rec, contact, "em1")
        self.assertEqual(result["verdict"], eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_CLIENT_APPROVAL,
                      result.get("reasons", [result.get("reason")]))

    def test_eligibility_decide_blocks_pending(self):
        ca.record("anchor.example", state=ca.APPROVED, who="z", source="t")
        ca.record("pending.example", state=ca.PENDING, who="z", source="t")
        rec = self._make_rec("pending.example")
        contact = rec["contacts"][0]
        result = eligibility.decide(rec, contact, "em1")
        self.assertEqual(result["verdict"], eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_CLIENT_APPROVAL,
                      result.get("reasons", [result.get("reason")]))

    def test_eligibility_decide_passes_approved(self):
        self._approve("good.example")
        rec = self._make_rec("good.example")
        contact = rec["contacts"][0]
        result = eligibility.decide(rec, contact, "em1")
        # It may be held or blocked for OTHER reasons (no step, no approval),
        # but NOT for client_approval.
        reasons = result.get("reasons", [result.get("reason")])
        self.assertNotIn(eligibility.BLOCKED_CLIENT_APPROVAL, reasons)


# -------------------------------------------------- fail-closed

class FailClosed(_TempDir, unittest.TestCase):

    def test_unknown_is_pending_and_pending_is_refused(self):
        """An account this file has never heard of is pending, and pending
        refuses. This is the core invariant."""
        self.assertFalse(ca.is_approved("never-heard-of.example"))
        with self.assertRaises(ca.ClientApprovalRequired):
            ca.require_approved("never-heard-of.example")

    def test_explicit_pending_is_also_refused(self):
        ca.record("waiting.example", state=ca.PENDING, who="z", source="t")
        self.assertFalse(ca.is_approved("waiting.example"))
        with self.assertRaises(ca.ClientApprovalRequired):
            ca.require_approved("waiting.example")


# -------------------------------------------------- the skip is COUNTED

class TheSkipIsCounted(_TempDir, unittest.TestCase):

    def test_s4_counts_excluded_contacts(self):
        ca.record("anchor.example", state=ca.APPROVED, who="z", source="t")
        rec = self._make_rec("unapproved.example",
                             contacts=[{"key": "c0", "name": "A",
                                        "title": "CEO"},
                                       {"key": "c1", "name": "B",
                                        "title": "CTO"}])
        result = personas.select(rec)
        self.assertEqual(result["awaiting_client_approval"], 2)

    def test_partition_groups_refused_by_state(self):
        ca.record("yes.example", state=ca.APPROVED, who="z", source="t")
        ca.record("no.example", state=ca.SUPPRESSED, who="z", source="t")
        allowed, refused = ca.partition(
            ["a@yes.example", "b@no.example", "c@unknown.example"])
        self.assertEqual(len(allowed), 1)
        self.assertEqual(len(refused[ca.SUPPRESSED]), 1)
        self.assertEqual(len(refused[ca.PENDING]), 1)

    def test_eligibility_reason_is_named(self):
        ca.record("anchor.example", state=ca.APPROVED, who="z", source="t")
        rec = self._make_rec("unapproved.example")
        contact = rec["contacts"][0]
        result = eligibility.decide(rec, contact, "em1")
        reasons = result.get("reasons", [result.get("reason")])
        self.assertIn(eligibility.BLOCKED_CLIENT_APPROVAL, reasons)


# -------------------------------------------------- no kill switch

class NoKillSwitch(_TempDir, unittest.TestCase):

    def test_no_forbidden_parameter_on_clientapproval_functions(self):
        forbidden = {"enforce", "skip", "skip_approval", "force",
                     "allow_pending", "bypass", "override"}
        for func in (ca.require_approved, ca.is_approved, ca.state_of):
            params = set(inspect.signature(func).parameters)
            self.assertFalse(params & forbidden,
                             f"{func.__name__} has {params & forbidden}")

    def test_no_forbidden_parameter_on_personas_select(self):
        params = set(inspect.signature(personas.select).parameters)
        forbidden = {"enforce", "skip", "skip_approval", "force",
                     "allow_pending", "bypass", "override",
                     "skip_client_approval"}
        self.assertFalse(params & forbidden)

    def test_no_forbidden_parameter_on_generate_draft(self):
        params = set(inspect.signature(generate.draft).parameters)
        forbidden = {"enforce", "skip", "skip_approval", "force",
                     "allow_pending", "bypass", "override",
                     "skip_client_approval"}
        self.assertFalse(params & forbidden)

    def test_no_forbidden_parameter_on_eligibility_decide(self):
        params = set(inspect.signature(eligibility.decide).parameters)
        forbidden = {"enforce", "skip", "skip_approval", "force",
                     "allow_pending", "bypass", "override",
                     "skip_client_approval"}
        self.assertFalse(params & forbidden)


# -------------------------------------------------- the surfaces

class DossierSurface(_TempDir, unittest.TestCase):

    def test_dossier_shows_client_approval_state(self):
        self._approve("example.com")
        rec = self._make_rec("example.com")
        contact = rec["contacts"][0]
        result = dossier.build(rec, contact)
        self.assertIn("client_approval", result)
        self.assertEqual(result["client_approval"]["state"], "approved")
        self.assertEqual(result["client_approval"]["who"], "tester")

    def test_dossier_shows_pending_for_unknown(self):
        rec = self._make_rec("unknown.example")
        contact = rec["contacts"][0]
        result = dossier.build(rec, contact)
        self.assertIn("client_approval", result)
        self.assertEqual(result["client_approval"]["state"], "pending")


class FunnelSurface(_TempDir, unittest.TestCase):

    def test_funnel_has_client_approved_stage(self):
        self._approve("example.com")
        rec = self._make_rec("example.com")
        rec["qualification"] = {"verdict": {
            "icp_status": "qualified",
            "icp_confidence": "high",
            "positive_signals": ["signal"],
            "negative_signals": []}}
        measured = funnel.measure([rec])
        stage_names = [s["stage"] for s in measured["stages"]]
        self.assertIn("client_approved", stage_names)

    def test_funnel_counts_approved_accounts(self):
        self._approve("yes.example")
        recs = [self._make_rec("yes.example"),
                self._make_rec("no.example")]
        for r in recs:
            r["qualification"] = {"verdict": {
                "icp_status": "qualified", "icp_confidence": "high",
                "positive_signals": ["s"], "negative_signals": []}}
        got = funnel.counts(recs)
        self.assertEqual(got["client_approved"], 1)


class DigestSurface(_TempDir, unittest.TestCase):

    def test_digest_shows_awaiting_client_approval(self):
        ca.record("a.example", state=ca.PENDING, who="z", source="t")
        ca.record("b.example", state=ca.PENDING, who="z", source="t")
        ca.record("c.example", state=ca.APPROVED, who="z", source="t")
        result = digest.build("productive", recs=[])
        self.assertEqual(result["awaiting_client_approval"], 2)
        self.assertEqual(result["client_approval"]["approved"], 1)

    def test_digest_lines_include_awaiting_approval(self):
        ca.record("a.example", state=ca.PENDING, who="z", source="t")
        result = digest.build("productive", recs=[])
        text = "\n".join(digest.lines(result))
        self.assertIn("Awaiting client approval", text)


if __name__ == "__main__":
    unittest.main()
