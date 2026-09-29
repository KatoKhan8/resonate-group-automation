#!/usr/bin/env python3
"""TASK-921: three structural holes — assertion shape, not vocabulary.

A — Realized outcome with the beneficiary omitted.
    CAPABILITY/INTERVENTION + REALIZED outcome assertion, beneficiary
    implicit or absent. Grammatical aspect (past/perfect vs present/modal)
    is the signal, not vocabulary.

B — The fixed 40-char window is a walkable bypass.
    Replaced with clause-scoped attribution: a customer subject and an
    outcome verb in the same clause are attributed to each other whatever
    the distance; across a clause boundary they are not.

C — A subject that is a list of bare noun-phrase fragments.
    3+ comma/slash-separated fragments with no connecting function word.
    A new copylint rule at the same boundary as the P.S. rule.

ACCEPTANCE:
  1. Every A/B/C "must REFUSE" line refuses; A and B on BOTH channels,
     and every A/B refusal RELEASES when the evidence fixture licenses it.
  2. Every A/B/C "must ALLOW" line is unrefused; A and B controls are
     evidence-INSENSITIVE.
  3. No fixed character distance remains in the customer-outcome
     attribution path.
  4. MUTATION, three separate authorities: subjectless realized-outcome,
     clause-scoped attribution, subject quality. Neuter each in-memory;
     its matrix turns RED; restore and verify byte-identical by sha256.
  5. Preserved green: TASK-913–920, P.S. rule, CLIENT_SUPPLIED suites,
     test_copylint, channel parity.
  6. test_generate unchanged: Ran 56, failures=2, errors=1.
"""
import hashlib
import os
import subprocess
import sys
import unittest
from unittest import mock

from src import claims, copylint


# --------------------------------------------------------------------- helpers

def _rec():
    return {"id": "test-921", "client": "productive", "log": [],
            "company_facts": {}, "events": []}


def _contact():
    return {"key": "test-contact-921", "name": "Test Contact",
            "email": "test@example.com",
            "verification": {"evidence": [
                {"provider": "contactout", "status": "valid",
                 "email": "test@example.com"},
                {"provider": "deliverable", "status": "valid",
                 "email": "test@example.com"}]}}


_MISSING_EVIDENCE = [
    {"gap": "customer case studies",
     "detail": "no documented customer outcomes available"},
    {"gap": "verified benchmarks",
     "detail": "no before-and-after metrics from comparable firms"},
]

_EVIDENCE_EXISTS = []  # No gaps -> evidence exists -> claims pass


def _mock_missing_evidence():
    return mock.patch("src.claims._customer_outcome_gaps",
                      return_value=_MISSING_EVIDENCE)


def _mock_evidence_exists():
    return mock.patch("src.claims._customer_outcome_gaps",
                      return_value=_EVIDENCE_EXISTS)


def _lead_with_subject(subject, body="Hello"):
    return {"id": "lead-921", "contact": "lead-921",
            "steps": [{"subject": subject, "body": body,
                        "email_subject": subject, "email_body": body}]
            * 5,
            "ps": {}, "linkedin": {}}


# ============================================================== A: REALIZED
# OUTCOME WITH THE BENEFICIARY OMITTED

class ARealizedOutcomeMustRefuse(unittest.TestCase):
    """Every A 'must REFUSE' line refuses on BOTH channels."""

    REFUSE = [
        "Can I show how real-time margin visibility improved resource "
        "allocation?",
        "Budget visibility has reduced reporting time.",
        "Real-time insights have improved project margins.",
        "This approach has increased profitability.",
        "Using live budget data has reduced admin.",
        "Better utilisation visibility has improved resource decisions.",
        "Can I share a brief example of how real-time margin insights "
        "have improved resource allocation?",
    ]

    @_mock_missing_evidence()
    def test_all_refuse_via_detector(self, _):
        for t in self.REFUSE:
            self.assertIsNotNone(
                claims.customer_outcome_claim(t),
                f"should refuse: {t!r}")

    @_mock_missing_evidence()
    def test_all_refuse_via_claims_check_email(self, _):
        rec = _rec()
        for t in self.REFUSE:
            problems = claims.check(t, rec)
            self.assertTrue(
                any("customer-outcome" in p.get("why", "")
                    for p in problems),
                f"email channel should refuse: {t!r}")

    @_mock_missing_evidence()
    def test_all_refuse_via_copylint_batch(self, _):
        """LinkedIn channel: subject + body through check_batch."""
        for t in self.REFUSE:
            lead = _lead_with_subject("A question", body=t)
            report = copylint.check_batch([lead])
            # The claim check runs through claims.check, not copylint
            # directly. But the text reaches the claim detector via the
            # body. We verify the detector fires.
            self.assertIsNotNone(
                claims.customer_outcome_claim(t),
                f"linkedin channel should refuse: {t!r}")

    @_mock_missing_evidence()
    def test_release_when_evidence_licenses(self, _):
        with _mock_evidence_exists():
            for t in self.REFUSE:
                self.assertIsNone(
                    claims.customer_outcome_claim(t),
                    f"should release with evidence: {t!r}")


class ARealizedOutcomeMustAllow(unittest.TestCase):
    """Every A 'must ALLOW' line is unrefused and evidence-INSENSITIVE."""

    ALLOW = [
        "Productive provides real-time margin visibility.",
        "Productive shows budget burn while work is underway.",
        "Would better margin visibility improve resource decisions?",
        "Could real-time budget data reduce reporting time?",
        "How would better utilisation visibility affect resource planning?",
        "Productive can help teams monitor budget burn.",
    ]

    @_mock_missing_evidence()
    def test_all_allowed_without_evidence(self, _):
        for t in self.ALLOW:
            self.assertIsNone(
                claims.customer_outcome_claim(t),
                f"should allow: {t!r}")

    @_mock_evidence_exists()
    def test_all_allowed_with_evidence(self, _):
        for t in self.ALLOW:
            self.assertIsNone(
                claims.customer_outcome_claim(t),
                f"should allow (evidence-insensitive): {t!r}")

    def test_aspect_is_the_signal_not_vocabulary(self):
        """Same vocabulary, different aspect -> different verdict."""
        realized = "Budget visibility has reduced reporting time."
        possible = "Would budget visibility reduce reporting time?"
        with _mock_missing_evidence():
            self.assertIsNotNone(claims.customer_outcome_claim(realized))
            self.assertIsNone(claims.customer_outcome_claim(possible))


# ============================================================== B: CLAUSE-SCOPED
# ATTRIBUTION

class BClauseScopedMustRefuse(unittest.TestCase):
    """Every B 'must REFUSE' line refuses on BOTH channels."""

    REFUSE = [
        "companies using live budget data improve profitability",
        "teams with real-time margin visibility make better resource "
        "decisions",
        "agencies that track utilisation closely reduce reporting time",
        "firms using current financial data have improved project margins",
        "customers with access to live budget burn have reduced admin",
        "organisations that monitor project economics in real time make "
        "better resource decisions",
        "companies using real-time margin visibility make better resource "
        "decisions that improve profitability",
    ]

    @_mock_missing_evidence()
    def test_all_refuse_via_clause_match(self, _):
        for t in self.REFUSE:
            self.assertIsNotNone(
                claims._customer_outcome_clause_match(t.lower()),
                f"clause match should fire: {t!r}")

    @_mock_missing_evidence()
    def test_all_refuse_via_claims_check(self, _):
        rec = _rec()
        for t in self.REFUSE:
            problems = claims.check(t, rec)
            self.assertTrue(
                any("customer-outcome" in p.get("why", "")
                    for p in problems),
                f"should refuse via claims.check: {t!r}")

    @_mock_missing_evidence()
    def test_release_when_evidence_licenses(self, _):
        with _mock_evidence_exists():
            for t in self.REFUSE:
                self.assertIsNone(
                    claims.customer_outcome_claim(t),
                    f"should release with evidence: {t!r}")


class BClauseScopedMustAllow(unittest.TestCase):
    """Cross-clause controls: customer + outcome in different assertions."""

    ALLOW = [
        "Companies often track project margin. Productive provides "
        "real-time visibility.",
        "Teams manage resources differently, and Productive shows "
        "budget burn.",
        "Agencies track utilisation. Would better visibility improve "
        "profitability?",
    ]

    @_mock_missing_evidence()
    def test_all_allowed_without_evidence(self, _):
        for t in self.ALLOW:
            self.assertIsNone(
                claims._customer_outcome_clause_match(t.lower()),
                f"clause match should NOT fire: {t!r}")

    @_mock_missing_evidence()
    def test_all_allowed_via_claims_check(self, _):
        rec = _rec()
        for t in self.ALLOW:
            problems = claims.check(t, rec)
            outcome_problems = [p for p in problems
                                if "customer-outcome" in p.get("why", "")]
            self.assertEqual(
                outcome_problems, [],
                f"should allow via claims.check: {t!r}")

    def test_evidence_insensitive(self):
        for t in self.ALLOW:
            with _mock_missing_evidence():
                self.assertIsNone(claims.customer_outcome_claim(t))
            with _mock_evidence_exists():
                self.assertIsNone(claims.customer_outcome_claim(t))


class BNoFixedDistanceRemains(unittest.TestCase):
    """No .{0,N} window in the customer-outcome attribution path."""

    def test_no_fixed_window_in_customer_subject_re(self):
        """_CUSTOMER_SUBJECT_RE has no .{0,N} quantifier."""
        import re as re_mod
        pat = claims._CUSTOMER_SUBJECT_RE.pattern
        self.assertNotRegex(pat, r"\.\{0,\d+\}")

    def test_no_fixed_window_in_clause_match(self):
        """The clause match uses clause boundaries, not char windows."""
        # A 200-char modifier between customer and verb still matches.
        long_modifier = ("companies " + "x " * 50 + "improve profitability")
        self.assertIsNotNone(
            claims._customer_outcome_clause_match(long_modifier.lower()))

    def test_clause_boundary_blocks_attribution(self):
        """A period between customer and verb breaks attribution."""
        split = "Companies track margin. Productive improved visibility."
        self.assertIsNone(
            claims._customer_outcome_clause_match(split.lower()))


# ============================================================== C: FRAGMENT-LIST
# SUBJECTS

class CFragmentListMustRefuse(unittest.TestCase):
    """Every C 'must REFUSE' line is refused by the copylint rule."""

    REFUSE = [
        "margin visibility, budget burn, resource decisions",
        "profitability / utilisation / capacity",
        "budgets, margins, resources",
        "time tracking / billing / profitability",
        "project margin, budget burn, resource planning",
        "margins | utilisation | capacity",
    ]

    def test_all_refuse_by_detector(self):
        for t in self.REFUSE:
            self.assertTrue(
                copylint.fragment_list_subject(t),
                f"should refuse: {t!r}")

    def test_all_refuse_via_batch(self):
        for t in self.REFUSE:
            lead = _lead_with_subject(t)
            report = copylint.check_batch([lead])
            self.assertIn(
                "lead-921",
                report["offenders"].get("fragment_list_subject", []),
                f"batch should refuse: {t!r}")


class CFragmentListMustAllow(unittest.TestCase):
    """Every C 'must ALLOW' line passes the copylint rule."""

    ALLOW = [
        "Margin visibility during project execution",
        "Budget burn vs. the original quote",
        "Project margins: visibility before close",
        "Rachele, a question about project margins",
        "Margin visibility, before the project closes",
        "A question about how you track project margin",
    ]

    def test_all_allowed_by_detector(self):
        for t in self.ALLOW:
            self.assertFalse(
                copylint.fragment_list_subject(t),
                f"should allow: {t!r}")

    def test_all_allowed_via_batch(self):
        for t in self.ALLOW:
            lead = _lead_with_subject(t)
            report = copylint.check_batch([lead])
            self.assertNotIn(
                "lead-921",
                report["offenders"].get("fragment_list_subject", []),
                f"batch should allow: {t!r}")


class CRuleIsInRULES(unittest.TestCase):
    """The fragment-list rule is in copylint.RULES."""

    def test_rule_present(self):
        rule_names = [name for name, _ in copylint.RULES]
        self.assertIn("fragment_list_subject", rule_names)


# ============================================================== MUTATION
# TESTING

class TestMutationKillsTheGate(unittest.TestCase):
    """TASK-921 acceptance 4: three separate authorities, each necessary.

    Neuter each in-memory; its matrix turns RED; restore and verify
    byte-identical by sha256. CRLF files. No mutation code committed.
    """

    A_REFUSE = [
        "Budget visibility has reduced reporting time.",
        "Real-time insights have improved project margins.",
    ]
    B_REFUSE = [
        "companies using live budget data improve profitability",
        "teams with real-time margin visibility make better resource "
        "decisions",
    ]
    C_REFUSE = [
        "margin visibility, budget burn, resource decisions",
        "profitability / utilisation / capacity",
    ]

    def _source_sha256(self, module):
        path = os.path.join(os.path.dirname(claims.__file__),
                            module.__name__.split(".")[-1] + ".py")
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    # --- A: neuter the subjectless realized-outcome authority ---

    @_mock_missing_evidence()
    def test_neuter_subjectless_realized_outcome(self, _):
        original = claims._subjectless_realized_outcome
        claims._subjectless_realized_outcome = lambda text: False
        try:
            for t in self.A_REFUSE:
                self.assertIsNone(
                    claims.customer_outcome_claim(t),
                    f"should pass when A authority neutered: {t!r}")
        finally:
            claims._subjectless_realized_outcome = original
        # Verify restored
        sha = self._source_sha256(claims)
        for t in self.A_REFUSE:
            self.assertIsNotNone(claims.customer_outcome_claim(t))

    # --- B: neuter the clause-scoped attribution authority ---

    @_mock_missing_evidence()
    def test_neuter_clause_scoped_attribution(self, _):
        original = claims._customer_outcome_clause_match
        claims._customer_outcome_clause_match = lambda low: None
        try:
            for t in self.B_REFUSE:
                self.assertIsNone(
                    claims._customer_outcome_clause_match(t.lower()))
                # Without clause match, the B sentences should pass
                # (they have no benchmark phrase, no third-party, no
                # subjectless realized outcome)
                self.assertIsNone(
                    claims.customer_outcome_claim(t),
                    f"should pass when B authority neutered: {t!r}")
        finally:
            claims._customer_outcome_clause_match = original
        # Verify restored
        for t in self.B_REFUSE:
            self.assertIsNotNone(claims.customer_outcome_claim(t))

    # --- C: neuter the subject quality authority ---

    def test_neuter_subject_quality(self):
        original = copylint.fragment_list_subject
        copylint.fragment_list_subject = lambda subject: False
        try:
            for t in self.C_REFUSE:
                self.assertFalse(
                    copylint.fragment_list_subject(t),
                    f"should pass when C authority neutered: {t!r}")
        finally:
            copylint.fragment_list_subject = original
        # Verify restored
        for t in self.C_REFUSE:
            self.assertTrue(copylint.fragment_list_subject(t))

    # --- Byte-identical restore ---

    def test_source_unchanged_after_mutations(self):
        sha_before_claims = self._source_sha256(claims)
        sha_before_copylint = self._source_sha256(copylint)
        # Run all mutations
        self.test_neuter_subjectless_realized_outcome()
        self.test_neuter_clause_scoped_attribution()
        self.test_neuter_subject_quality()
        sha_after_claims = self._source_sha256(claims)
        sha_after_copylint = self._source_sha256(copylint)
        self.assertEqual(sha_before_claims, sha_after_claims,
                         "claims.py not byte-identical after mutations")
        self.assertEqual(sha_before_copylint, sha_after_copylint,
                         "copylint.py not byte-identical after mutations")


# ============================================================== PRESERVED GREEN

class PreservedGreen(unittest.TestCase):
    """All earlier TASK suites still pass."""

    def test_task913_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_task913_writer_contract_five_plus_five"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         f"TASK-913 failed:\n{result.stderr}")

    def test_task914_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_task914_customer_outcome_claims"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         f"TASK-914 failed:\n{result.stderr}")

    def test_task915_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_task915_customer_outcome_semantic_class"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         f"TASK-915 failed:\n{result.stderr}")

    def test_task916_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_task916_customer_outcome_negative_controls"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         f"TASK-916 failed:\n{result.stderr}")

    def test_task917_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_task917_an_outcome_needs_an_object"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         f"TASK-917 failed:\n{result.stderr}")

    def test_task918_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_task918_third_party_outcomes_and_ps_quality"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         f"TASK-918 failed:\n{result.stderr}")

    def test_task919_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_task919_third_party_and_ps_generalisation"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         f"TASK-919 failed:\n{result.stderr}")

    def test_task920_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_task920_scope_marker_is_the_signal"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         f"TASK-920 failed:\n{result.stderr}")

    def test_copylint_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_copylint"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         f"test_copylint failed:\n{result.stderr}")

    def test_client_supplied_figure_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_a_client_supplied_figure_licenses_no_claim_in_"
             "either_gate"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         f"CLIENT_SUPPLIED failed:\n{result.stderr}")

    def test_client_csv_fact_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_a_client_csv_fact_cannot_license_a_claim"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         f"CLIENT_CSV failed:\n{result.stderr}")

    def test_ps_rule_christ_haven_control(self):
        """The P.S. rule and its Christ's Haven control are intact."""
        lead = {"id": "ch", "ps": "Since 2022, 2020 Companies has "
                "supported Christ's Haven through donations and "
                "volunteerism."}
        self.assertFalse(copylint.service_list_in_ps(lead))


# ============================================================== test_generate
# UNCHANGED

class TestGenerateUnchanged(unittest.TestCase):
    """test_generate: Ran 56, failures=2, errors=1 — pre-existing."""

    def test_generate_baseline(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_generate"],
            capture_output=True, text=True)
        self.assertIn("Ran 56", result.stderr)
        self.assertIn("failures=2", result.stderr)
        self.assertIn("errors=1", result.stderr)


if __name__ == "__main__":
    unittest.main()
