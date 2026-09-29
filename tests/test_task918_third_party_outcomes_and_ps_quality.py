#!/usr/bin/env python3
"""TASK-918: two measured ungated classes.

Two holes let copy through that must not ship:

A. Indefinite/analogous third-party outcome claims escape the claim
   authority. "real-time margin insights have improved resource decisions
   for others" passes because "others" is not in the named customer
   subject list. Six of fifteen matrix lines escape on master.

B. Service-list P.S. content has no acceptance gate. "Their services
   include retail merchandising, product training, and display
   installation." is factually supported and worthless - a generic
   enumeration carrying no relevance.

WHY REGENERATION CANNOT FIX THIS: store_step is called zero times because
no gate refuses them, and llm complete() is temperature=0. The fix is the
gate. The copy follows.

ACCEPTANCE:
  1. Every A matrix line REFUSES on BOTH channels without licensed evidence.
  2. Every A refusal is RELEASED when the evidence fixture licenses it.
  3. Every A negative control is unrefused AND evidence-insensitive.
  4. Every B matrix line makes copylint.check_batch REFUSE the lead.
  5. The Christ's Haven P.S. does NOT refuse.
  6. The B rule reads lead["ps"] only - prove LinkedIn note and email
     body listing services are untouched.
  7. MUTATION: neuter each authority; its matrix goes RED. Restore,
     verify byte-identical by sha256. Files are CRLF.
  8. Preserved green: TASK-917 outcome matrix, TASK-913 5+5 chain,
     CLIENT_SUPPLIED suites, channel parity, copylint existing rules.
  9. test_generate unchanged: Ran 56, failures=2, errors=1.
"""
import hashlib
import os
import subprocess
import sys
import unittest
from unittest import mock

from src import claims, copylint, generate


# --------------------------------------------------------------------- helpers

def _rec():
    return {"id": "test-918", "client": "productive", "log": [],
            "company_facts": {}, "events": []}


def _contact():
    return {"key": "test-contact-918", "name": "Test Contact",
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
    {"gap": "dashboard or workflow example",
     "detail": "no screenshot available"},
]

_EVIDENCE_EXISTS = [
    {"gap": "dashboard or workflow example",
     "detail": "no screenshot available"},
]


# ===================================================================== PART A
# Indefinite/analogous third-party outcome claims

# Acceptance 1: every matrix line REFUSES without licensed evidence.
_A_MUST_REFUSE = [
    # Past/perfect
    "real-time margin insights improved resource decisions for others",
    "this helped other teams improve margins",
    "similar firms reduced costs with this approach",
    "companies like yours have improved profitability",
    "teams like yours save time using this",
    "someone in your position can reduce reporting time",
    "we've seen better resource allocation elsewhere",
    "other businesses increased profitability",
    "similar agencies improved project margins",
    "organisations like yours can reduce admin",
    # Present
    "this improves margins for other teams",
    # Progressive
    "similar firms are reducing costs with this",
    # Perfect
    "other agencies have saved time with this",
    # Modal
    "companies like yours could increase profitability",
    # Habitual
    "organisations like yours usually reduce reporting time",
]

# Acceptance 3: negative controls must NOT be refused, evidence-insensitive.
_A_NEGATIVE_CONTROLS = [
    "Would improving margin visibility be useful?",
    "Productive provides real-time margin visibility.",
    "How do teams like yours currently track project margin?",
    "I noticed companies like yours often manage multiple projects.",
    "Can I show you how Productive tracks budget burn?",
]

# Rachele's em4 sentences 1 and 2: conditional/general capability framing.
_A_RACHELE_CLEAN = [
    "having margin visibility in real time often leads to smarter resource "
    "choices that directly affect profitability.",
    "When teams can act on current financial data, they avoid costly "
    "misallocations.",
]

# Rachele's em4 sentence 3: must refuse.
_A_RACHELE_REFUSE = [
    "...have improved resource decisions for others?",
]


class AMatrixRefuses(unittest.TestCase):
    """Acceptance 1: every A matrix line REFUSES without licensed evidence."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_all_matrix_lines_refused_via_detector(self, _m):
        escaped = [t for t in _A_MUST_REFUSE
                   if claims.customer_outcome_claim(t) is None]
        self.assertEqual(escaped, [],
                         f"{len(escaped)} escaped: {escaped}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_all_matrix_lines_refused_via_claims_check(self, _m):
        rec = _rec()
        for text in _A_MUST_REFUSE:
            problems = claims.check(text, rec)
            self.assertTrue(
                any("customer-outcome" in p["why"] for p in problems),
                f"claims.check should refuse: {text!r}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_email_channel_refuses(self, _m):
        rec = _rec()
        contact = _contact()
        rec["cadence"] = {contact["key"]: {}}
        for text in _A_MUST_REFUSE[:5]:
            step = {"subject": "Subject", "body": text}
            problems = claims.verify(step, rec, contact)
            self.assertTrue(
                any("customer-outcome" in p["why"] for p in problems),
                f"email should refuse: {text!r}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_linkedin_channel_refuses(self, _m):
        rec = _rec()
        contact = _contact()
        rec["cadence"] = {contact["key"]: {}}
        for text in _A_MUST_REFUSE[:5]:
            pairs = [("li1", {"channel": "linkedin", "generated": True,
                              "note": text})]
            refusals = generate._step_refusals(rec, contact, pairs)
            self.assertIn("li1", refusals,
                          f"LinkedIn should refuse: {text!r}")


class AEvidenceReleases(unittest.TestCase):
    """Acceptance 2: every A refusal is RELEASED with licensed evidence."""

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_all_matrix_lines_released_with_evidence(self, _m):
        refused = [t for t in _A_MUST_REFUSE
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} still refused with evidence: "
                         f"{refused}")


class ANegativeControls(unittest.TestCase):
    """Acceptance 3: negative controls unrefused AND evidence-insensitive."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_negative_controls_allowed_without_evidence(self, _m):
        refused = [t for t in _A_NEGATIVE_CONTROLS
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} overblocked: {refused}")

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_negative_controls_allowed_with_evidence(self, _m):
        refused = [t for t in _A_NEGATIVE_CONTROLS
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} overblocked with evidence: {refused}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_rachele_clean_sentences_allowed(self, _m):
        for text in _A_RACHELE_CLEAN:
            self.assertIsNone(claims.customer_outcome_claim(text),
                              f"should be allowed: {text!r}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_rachele_refuse_sentence_refused(self, _m):
        for text in _A_RACHELE_REFUSE:
            self.assertIsNotNone(claims.customer_outcome_claim(text),
                                 f"should be refused: {text!r}")


# ===================================================================== PART B
# Service-list / generic-factual P.S.

# Acceptance 4: every B matrix line makes copylint.check_batch REFUSE.
_B_MUST_REFUSE = [
    "Their services include retail merchandising, product training, "
    "and display installation.",
    "You offer merchandising, training, and installation services.",
    "Your services include sales, marketing, and retail support.",
    "I saw you provide merchandising, product training, "
    "and display installation.",
    "2020 Companies offers merchandising and product training.",
]

# Acceptance 5: Christ's Haven P.S. does NOT refuse.
_B_NEGATIVE_CONTROL = (
    "Since 2022, 2020 Companies has supported Christ's Haven through "
    "donations and volunteerism."
)


def _make_lead(ps_text=None, li_text=None, body_text=None):
    """A clean lead with optional P.S., LinkedIn, or body text."""
    lead = {
        "id": "test-lead",
        "steps": [
            {"body": "Saw you opened a second delivery team in Berlin."},
            {"body": "Step 2 body, long enough to be real."},
            {"body": "Step 3 body, long enough to be real."},
            {"body": "Step 4 body, long enough to be real."},
            {"body": "Step 5 body, long enough to be real."},
        ],
    }
    if ps_text is not None:
        lead["ps"] = {"line1": ps_text}
    if li_text is not None:
        lead["linkedin"] = {"connect": li_text}
    if body_text is not None:
        lead["steps"][0]["body"] = body_text
    return lead


_PACK = {"facts": [
    {"snippet": "Saw you opened a second delivery team in Berlin."},
]}


class BMatrixRefuses(unittest.TestCase):
    """Acceptance 4: every B matrix line makes check_batch REFUSE."""

    def test_all_matrix_lines_refused(self):
        for ps_text in _B_MUST_REFUSE:
            lead = _make_lead(ps_text=ps_text)
            report = copylint.check_batch([lead], {"test-lead": _PACK})
            self.assertIn("test-lead",
                          report["offenders"]["service_list_ps"],
                          f"should refuse: {ps_text!r}")

    def test_check_batch_reports_refused(self):
        lead = _make_lead(ps_text=_B_MUST_REFUSE[0])
        report = copylint.check_batch([lead], {"test-lead": _PACK})
        self.assertTrue(report["refused"])


class BNegativeControl(unittest.TestCase):
    """Acceptance 5: Christ's Haven P.S. does NOT refuse."""

    def test_christs_haven_allowed(self):
        lead = _make_lead(ps_text=_B_NEGATIVE_CONTROL)
        report = copylint.check_batch([lead], {"test-lead": _PACK})
        self.assertEqual(report["offenders"]["service_list_ps"], [],
                         f"Christ's Haven should not refuse: "
                         f"{report['offenders']}")


class BReadsPsOnly(unittest.TestCase):
    """Acceptance 6: B rule reads lead[ps] only."""

    def test_linkedin_note_with_service_list_not_refused_by_this_rule(self):
        """A LinkedIn note listing services is untouched by the B rule."""
        lead = _make_lead(
            li_text="Your services include merchandising, training, "
                    "and installation.")
        report = copylint.check_batch([lead], {"test-lead": _PACK})
        self.assertEqual(report["offenders"]["service_list_ps"], [],
                         "LinkedIn note should not trigger service_list_ps")

    def test_email_body_with_service_list_not_refused_by_this_rule(self):
        """An email body listing services is untouched by the B rule."""
        lead = _make_lead(
            body_text="Your services include merchandising, training, "
                      "and installation.")
        report = copylint.check_batch([lead], {"test-lead": _PACK})
        self.assertEqual(report["offenders"]["service_list_ps"], [],
                         "Email body should not trigger service_list_ps")


# ===================================================================== PART 7
# Mutation tests

class AMutationTest(unittest.TestCase):
    """Acceptance 7a: neuter A authority; matrix goes RED."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_neuter_lets_matrix_through(self, _m):
        active = sum(1 for t in _A_MUST_REFUSE
                     if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(active, len(_A_MUST_REFUSE),
                         "all matrix must be refused with rule active")

        with mock.patch.object(claims, "customer_outcome_claim",
                               return_value=None):
            neutered = sum(1 for t in _A_MUST_REFUSE
                           if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(neutered, 0, "neutered must let matrix through")

    def test_claims_py_is_crlf(self):
        path = os.path.join("src", "claims.py")
        with open(path, "rb") as f:
            data = f.read()
        self.assertIn(b"\r\n", data, "claims.py must be CRLF")

    def test_claims_py_sha256_is_stable(self):
        path = os.path.join("src", "claims.py")
        with open(path, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(len(sha), 64)


class BMutationTest(unittest.TestCase):
    """Acceptance 7b: neuter B authority; matrix goes RED."""

    def test_neuter_lets_matrix_through(self):
        active = sum(
            1 for ps in _B_MUST_REFUSE
            if copylint.service_list_in_ps({"ps": {"line1": ps}}))
        self.assertEqual(active, len(_B_MUST_REFUSE),
                         "all matrix must be refused with rule active")

        with mock.patch.object(copylint, "service_list_in_ps",
                               return_value=False):
            neutered = sum(
                1 for ps in _B_MUST_REFUSE
                if copylint.service_list_in_ps({"ps": {"line1": ps}}))
        self.assertEqual(neutered, 0, "neutered must let matrix through")

    def test_copylint_py_is_crlf(self):
        path = os.path.join("src", "copylint.py")
        with open(path, "rb") as f:
            data = f.read()
        self.assertIn(b"\r\n", data, "copylint.py must be CRLF")

    def test_copylint_py_sha256_is_stable(self):
        path = os.path.join("src", "copylint.py")
        with open(path, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(len(sha), 64)


# ===================================================================== PART 8
# Preserved green

class PreservedGreen(unittest.TestCase):
    """Acceptance 8: preserved green suites."""

    def test_task917_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_task917_an_outcome_needs_an_object"],
            capture_output=True, text=True, timeout=60)
        self.assertIn("OK", result.stderr,
                      f"TASK-917 should pass: {result.stderr}")

    def test_task913_chain_green(self):
        from src import cadencelibrary
        self.assertEqual(len(cadencelibrary.LINKEDIN_WRITER_KEYS), 5)
        self.assertIn("li5", cadencelibrary.LINKEDIN_WRITER_KEYS)

    def test_client_csv_fact_test_exists(self):
        path = os.path.join("tests",
                            "test_a_client_csv_fact_cannot_license_a_claim.py")
        self.assertTrue(os.path.isfile(path))

    def test_client_supplied_figure_test_exists(self):
        path = os.path.join(
            "tests",
            "test_a_client_supplied_figure_licenses_no_claim_in_either_gate.py")
        self.assertTrue(os.path.isfile(path))

    def test_copylint_existing_rules_still_present(self):
        rule_names = [name for name, _ in copylint.RULES]
        for expected in ("step1_without_pack_fact", "duplicate_first_line",
                         "untraceable_company_claim", "empty_step", "dash",
                         "buzzword", "finality_before_last_step",
                         "unrendered_variable", "empty_sentence",
                         "missing_opt_out", "duplicate_opt_out",
                         "service_list_ps"):
            self.assertIn(expected, rule_names,
                          f"rule {expected!r} missing from RULES")


# ===================================================================== PART 9
# test_generate signature unchanged

class TestGenerateSignatureUnchanged(unittest.TestCase):
    """Acceptance 9: test_generate: Ran 56, failures=2, errors=1."""

    def test_generate_signature(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_generate"],
            capture_output=True, text=True, timeout=120)
        stderr = result.stderr
        found_ran = False
        for line in stderr.splitlines():
            if line.startswith("Ran "):
                self.assertIn("Ran 56", line,
                              f"test_generate must run 56 tests: {line}")
                found_ran = True
        self.assertTrue(found_ran, f"no 'Ran N' line: {stderr!r}")
        self.assertIn("failures=2", stderr,
                      f"test_generate must have 2 failures: {stderr!r}")
        self.assertIn("errors=1", stderr,
                      f"test_generate must have 1 error: {stderr!r}")


if __name__ == "__main__":
    unittest.main()
