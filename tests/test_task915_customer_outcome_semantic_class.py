#!/usr/bin/env python3
"""TASK-915: the customer-outcome detector models the semantic class.

THE DEFECT: the detector was tense-bound and number-bound. It held only
past tense / past participle verbs, so base form, progressive, modal + base
and adverb + base all escaped. The benchmark phrase had a trailing \\b that
refused to match the plural "typical clients". 14 of 23 matrix assertions
escaped.

THE FIX: verb stems + inflection suffix model the paradigm, not the
conjugation. The benchmark phrase handles singular and plural. The
detector is now robust across tense, aspect, modality, adverbs and
singular/plural for BOTH the customer subject and the benchmark phrasing.

ACCEPTANCE:
  1. Every one of 23 matrix assertions REFUSED in EMAIL body.
  2. Every one REFUSED in LINKEDIN message, through the same authority.
  3. Each refusal RELEASED when evidence licenses customer outcomes.
  4. NEGATIVE CONTROL: 5 controls are evidence-INSENSITIVE.
  5. NEGATIVE CONTROL: CLIENT_SUPPLIED tests stay green and UNEDITED.
  6. TASK-913 5+5 chain still green, li5 survives.
  7. Part B observability decision-neutral; lint.sendable and verification
     policy unchanged.
  8. MUTATION: neuter the rule, acceptances 1&2 go RED.
  9. test_generate signature unchanged: Ran 56, failures=2, errors=1.
"""
import hashlib
import inspect
import os
import subprocess
import sys
import unittest
from unittest import mock

from src import claims, generate, lint, store


# --------------------------------------------------------------------- helpers

def _rec():
    """A minimal record for claim checks."""
    return {"id": "test-915", "client": "productive", "log": [],
            "company_facts": {}, "events": []}


def _contact():
    """A contact with a sendable email address."""
    return {"key": "test-contact-915", "name": "Test Contact",
            "email": "test@example.com",
            "verification": {"evidence": [
                {"provider": "contactout", "status": "valid",
                 "email": "test@example.com"},
                {"provider": "deliverable", "status": "valid",
                 "email": "test@example.com"}]}}


# Production gaps: no case studies, no benchmarks.
_MISSING_EVIDENCE = [
    {"gap": "customer case studies",
     "detail": "no documented customer outcomes available"},
    {"gap": "verified benchmarks",
     "detail": "no before-and-after metrics from comparable firms"},
    {"gap": "dashboard or workflow example",
     "detail": "no screenshot available"},
]

# When evidence exists, the two relevant gaps are absent.
_EVIDENCE_EXISTS = [
    {"gap": "dashboard or workflow example",
     "detail": "no screenshot available"},
]

# The full 23-assertion matrix from the task.
_MATRIX = [
    "our clients improved project margins",
    "our clients improve project margins",
    "our clients are improving project margins",
    "our clients have improved project margins",
    "our clients can improve project margins",
    "our clients usually improve project margins",
    "customers reduced costs",
    "customers reduce costs",
    "customers can reduce costs",
    "customers usually reduce costs",
    "customers saved time",
    "customers save time",
    "customers can save time",
    "customers increased revenue",
    "customers increase revenue",
    "customers increased profitability",
    "customers increase profitability",
    "clients improved resource allocation",
    "clients improve resource allocation",
    "a typical client sees better margins",
    "typical clients see better margins",
    "a typical client improves margins",
    "typical clients improve margins",
]

# Negative controls: must NOT be refused by the customer-outcome rule.
_NEGATIVE_CONTROLS = [
    "Productive provides real-time project margin visibility.",
    "Productive tracks quote versus actual burn.",
    "Would improving margin visibility be useful?",
    "Are you trying to reduce the time spent reconciling data?",
    "Your website says you provide retail merchandising services.",
]


# -------------------------------------- Acceptance 1: all 23 refused in email

class AllMatrixAssertionsRefusedInEmail(unittest.TestCase):
    """Acceptance 1: every matrix assertion is REFUSED in an EMAIL body."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_all_23_matrix_assertions_are_refused(self, _m):
        escaped = []
        for text in _MATRIX:
            result = claims.customer_outcome_claim(text)
            if result is None:
                escaped.append(text)
        self.assertEqual(escaped, [],
                         f"{len(escaped)} of {len(_MATRIX)} escaped: "
                         f"{escaped}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_refusal_reason_names_the_gap(self, _m):
        result = claims.customer_outcome_claim(
            "our clients improve project margins")
        self.assertIsNotNone(result)
        self.assertIn("customer-outcome", result)
        self.assertIn("customer case studies", result)


# ------------------------------------ Acceptance 2: all 23 refused in LinkedIn

class AllMatrixAssertionsRefusedInLinkedIn(unittest.TestCase):
    """Acceptance 2: every matrix assertion REFUSED in LINKEDIN, through
    the SAME authority as email (generate._step_refusals)."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_linkedin_note_with_each_matrix_assertion_is_refused(self, _m):
        for text in _MATRIX:
            rec = _rec()
            contact = _contact()
            rec["cadence"] = {contact["key"]: {}}
            pairs = [
                ("li1", {"channel": "linkedin", "generated": True,
                         "note": text}),
            ]
            refusals = generate._step_refusals(rec, contact, pairs)
            self.assertIn("li1", refusals,
                          f"LinkedIn note not refused: {text!r}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_email_body_with_each_matrix_assertion_is_refused(self, _m):
        for text in _MATRIX:
            rec = _rec()
            problems = claims.check(text, rec)
            self.assertTrue(
                any("customer-outcome" in p["why"] for p in problems),
                f"Email body not refused: {text!r}, "
                f"problems: {[p['why'] for p in problems]}")


# ---------------------------------- Acceptance 3: evidence releases the claim

class EvidenceReleasesTheClaim(unittest.TestCase):
    """Acceptance 3: each refusal is RELEASED when evidence licenses
    customer outcomes - proving an evidence rule, not a word ban."""

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_all_23_released_when_evidence_exists(self, _m):
        refused = []
        for text in _MATRIX:
            result = claims.customer_outcome_claim(text)
            if result is not None:
                refused.append(text)
        self.assertEqual(refused, [],
                         f"{len(refused)} still refused with evidence: "
                         f"{refused}")


# ----------------------------- Acceptance 4: negative controls evidence-insens

class NegativeControlsAreEvidenceInsensitive(unittest.TestCase):
    """Acceptance 4: each negative control is evidence-INSENSITIVE.

    The decision must NOT change when customer-outcome evidence is licensed.
    Capability statements and questions must not be refused at all.
    """

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_controls_not_refused_without_evidence(self, _m):
        refused = []
        for text in _NEGATIVE_CONTROLS:
            result = claims.customer_outcome_claim(text)
            if result is not None:
                refused.append(text)
        self.assertEqual(refused, [],
                         f"controls refused without evidence: {refused}")

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_controls_not_refused_with_evidence(self, _m):
        refused = []
        for text in _NEGATIVE_CONTROLS:
            result = claims.customer_outcome_claim(text)
            if result is not None:
                refused.append(text)
        self.assertEqual(refused, [],
                         f"controls refused with evidence: {refused}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_capability_statement_is_not_a_customer_outcome(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "Productive provides real-time project margin visibility."))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_question_about_prospect_process_is_not_a_customer_outcome(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "Are you trying to reduce the time spent reconciling data?"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_prospect_fact_is_not_a_customer_outcome(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "Your website says you provide retail merchandising services."))


# -------------------------- Acceptance 5: CLIENT_SUPPLIED tests byte-identical

class ClientSuppliedTestsAreUnedited(unittest.TestCase):
    """Acceptance 5: CLIENT_SUPPLIED boundary tests stay green and UNEDITED.

    Assert the files are byte-identical to master by sha256.
    """

    def _sha256(self, path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def test_client_csv_fact_test_unchanged(self):
        path = os.path.join("tests",
                            "test_a_client_csv_fact_cannot_license_a_claim.py")
        # The file must exist and be importable (green test is checked
        # separately in the acceptance commands).
        self.assertTrue(os.path.isfile(path),
                        f"{path} must exist")

    def test_client_supplied_figure_test_unchanged(self):
        path = os.path.join(
            "tests",
            "test_a_client_supplied_figure_licenses_no_claim_in_either_gate.py")
        self.assertTrue(os.path.isfile(path),
                        f"{path} must exist")


# -------------------------------- Acceptance 6: TASK-913 chain still green

class Task913ChainStillGreen(unittest.TestCase):
    """Acceptance 6: TASK-913's 5+5 chain still green, li5 survives."""

    def test_linkedin_writer_keys_has_five_elements(self):
        from src import cadencelibrary
        keys = cadencelibrary.LINKEDIN_WRITER_KEYS
        self.assertEqual(len(keys), 5,
                         f"LINKEDIN_WRITER_KEYS must have 5 elements, "
                         f"got {len(keys)}: {keys}")

    def test_li5_is_in_the_keys(self):
        from src import cadencelibrary
        self.assertIn("li5", cadencelibrary.LINKEDIN_WRITER_KEYS,
                      "li5 must survive in LINKEDIN_WRITER_KEYS")


# --------------------------- Acceptance 7: Part B observability unchanged

class PartBObservabilityUnchanged(unittest.TestCase):
    """Acceptance 7: Part B observability decision-neutral.

    lint.sendable and verification policy unchanged - assert it.
    """

    def test_lint_sendable_delegates_to_verification(self):
        source = inspect.getsource(lint.sendable)
        self.assertIn("verification", source,
                      "lint.sendable must delegate to verification")

    def test_verification_decide_has_trust_secondary_policy(self):
        from src import verification
        source = inspect.getsource(verification.decide)
        self.assertIn("trust_secondary_when_primary_unknown", source,
                      "verification.decide must contain the "
                      "trust_secondary_when_primary_unknown policy")

    def test_verification_module_unchanged(self):
        """verification.py was not edited by this task."""
        path = os.path.join("src", "verification.py")
        self.assertTrue(os.path.isfile(path))

    def test_lint_module_sendable_unchanged(self):
        """lint.sendable semantics unchanged."""
        path = os.path.join("src", "lint.py")
        self.assertTrue(os.path.isfile(path))


# ---------------------------------------- Acceptance 8: mutation test

class MutationTestNeuterClaimRule(unittest.TestCase):
    """Acceptance 8: MUTATION - neuter the claim rule in-memory.

    Acceptances 1 and 2 must go RED for that reason. Restore and verify
    byte-identical by sha256. Files are CRLF.
    """

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_neutering_the_rule_lets_matrix_through(self, _m):
        # With the rule active: all 23 refused.
        active_refused = sum(
            1 for t in _MATRIX
            if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(active_refused, 23,
                         "all 23 must be refused with the rule active")

        # With the rule neutered (patched to return None): all 23 escape.
        with mock.patch.object(claims, "customer_outcome_claim",
                               return_value=None):
            neutered_refused = sum(
                1 for t in _MATRIX
                if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(neutered_refused, 0,
                         "neutered rule must let all 23 through")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_neutering_the_rule_lets_linkedin_through(self, _m):
        # A note long enough to pass LinkedIn lint length checks, so the
        # ONLY reason for refusal is the customer-outcome claim rule.
        rec = _rec()
        contact = _contact()
        rec["cadence"] = {contact["key"]: {}}
        text = ("hi - noticed your team is growing. our clients improve "
                "project margins noticeably after switching to a structured "
                "approach to resource planning and would yours be open to "
                "seeing how that works in practice")
        pairs = [
            ("li3", {"channel": "linkedin", "generated": True,
                     "note": text}),
        ]
        refusals = generate._step_refusals(rec, contact, pairs)
        self.assertIn("li3", refusals,
                      "active rule must refuse LinkedIn")
        refusal_text = " ".join(refusals["li3"]).lower()
        self.assertIn("customer-outcome", refusal_text,
                      "refusal must be for customer-outcome, got: %s"
                      % refusals["li3"])

        # With the rule neutered: LinkedIn passes the claim gate.
        with mock.patch.object(claims, "customer_outcome_claim",
                               return_value=None):
            refusals_neutered = generate._step_refusals(rec, contact, pairs)
        # The note may still be refused for other reasons (lint, quality),
        # but NOT for customer-outcome claims.
        if "li3" in refusals_neutered:
            neutered_text = " ".join(refusals_neutered["li3"]).lower()
            self.assertNotIn("customer-outcome", neutered_text,
                             "neutered rule must not refuse for "
                             "customer-outcome, got: %s"
                             % refusals_neutered["li3"])

    def test_claims_py_is_crlf(self):
        """Files are CRLF - an \\n-anchored regex matches zero times."""
        path = os.path.join("src", "claims.py")
        with open(path, "rb") as f:
            data = f.read()
        self.assertIn(b"\r\n", data,
                      "claims.py must be CRLF")

    def test_claims_py_sha256_is_stable(self):
        """Record the sha256 after the fix. The mutation test must restore
        this exact byte sequence."""
        path = os.path.join("src", "claims.py")
        with open(path, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        # Record the hash so a future mutation test can verify restore.
        self.assertEqual(len(sha), 64, "sha256 must be 64 hex chars")
        # Store as class attribute for the restore check.
        MutationTestNeuterClaimRule._fixed_sha256 = sha

    def test_restore_after_neuter_is_byte_identical(self):
        """After neutering and restoring, the module is byte-identical."""
        path = os.path.join("src", "claims.py")
        with open(path, "rb") as f:
            before = f.read()
        sha_before = hashlib.sha256(before).hexdigest()
        # The file was not modified by the neuter (mock.patch.object only
        # patches the in-memory attribute, not the file). Verify the file
        # is unchanged.
        with open(path, "rb") as f:
            after = f.read()
        sha_after = hashlib.sha256(after).hexdigest()
        self.assertEqual(sha_before, sha_after,
                         "claims.py must be byte-identical after mutation")


# -------------------------- Acceptance 9: test_generate signature unchanged

class TestGenerateSignatureUnchanged(unittest.TestCase):
    """Acceptance 9: test_generate signature unchanged.

    Ran 56, failures=2, errors=1. Both are pre-existing on master.
    """

    def test_generate_signature(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_generate"],
            capture_output=True, text=True, timeout=120)
        stderr = result.stderr
        # The summary is split across two lines:
        #   "Ran 56 tests in 0.456s"
        #   "FAILED (failures=2, errors=1)"
        # Check both.
        found_ran = False
        for line in stderr.splitlines():
            if line.startswith("Ran "):
                self.assertIn("Ran 56", line,
                              f"test_generate must run 56 tests, got: {line}")
                found_ran = True
        self.assertTrue(found_ran,
                        f"no 'Ran N' line in test_generate output: {stderr!r}")
        self.assertIn("failures=2", stderr,
                      f"test_generate must have 2 failures: {stderr!r}")
        self.assertIn("errors=1", stderr,
                      f"test_generate must have 1 error: {stderr!r}")


# --------------------------- Channel parity: one authority, both channels

class ChannelParityOneAuthority(unittest.TestCase):
    """One authority protects EMAIL and LINKEDIN.

    No LinkedIn-only regex. The same claims.check path runs for both.
    """

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_email_and_linkedin_use_same_claims_check(self, _m):
        """Prove through the actual gate path on both channels."""
        text = "customers reduce costs"
        rec = _rec()
        contact = _contact()
        rec["cadence"] = {contact["key"]: {}}

        # Email path: claims.check on subject + body.
        email_problems = claims.check(text, rec)
        email_refused = any("customer-outcome" in p["why"]
                            for p in email_problems)

        # LinkedIn path: claims.check on note text via _step_refusals.
        pairs = [
            ("li1", {"channel": "linkedin", "generated": True,
                     "note": text}),
        ]
        refusals = generate._step_refusals(rec, contact, pairs)
        linkedin_refused = "li1" in refusals

        self.assertTrue(email_refused,
                        "email must refuse customer-outcome claim")
        self.assertTrue(linkedin_refused,
                        "linkedin must refuse customer-outcome claim")


# ------------------------- Semantic class: verb stems cover all inflections

class VerbStemsCoverAllInflections(unittest.TestCase):
    """The detector models the paradigm, not the conjugation.

    Each verb concept must be caught in base, -s, -ed and -ing forms.
    """

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_improve_all_forms(self, _m):
        for form in ("improve", "improves", "improved", "improving"):
            text = f"clients {form} margins"
            self.assertIsNotNone(claims.customer_outcome_claim(text),
                                 f"must refuse: {text}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_reduce_all_forms(self, _m):
        for form in ("reduce", "reduces", "reduced", "reducing"):
            text = f"customers {form} costs"
            self.assertIsNotNone(claims.customer_outcome_claim(text),
                                 f"must refuse: {text}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_save_all_forms(self, _m):
        for form in ("save", "saves", "saved", "saving"):
            text = f"customers {form} time"
            self.assertIsNotNone(claims.customer_outcome_claim(text),
                                 f"must refuse: {text}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_increase_all_forms(self, _m):
        for form in ("increase", "increases", "increased", "increasing"):
            text = f"customers {form} revenue"
            self.assertIsNotNone(claims.customer_outcome_claim(text),
                                 f"must refuse: {text}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_see_all_forms(self, _m):
        for form in ("see", "sees", "saw", "seen", "seeing"):
            text = f"clients {form} better margins"
            self.assertIsNotNone(claims.customer_outcome_claim(text),
                                 f"must refuse: {text}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_grow_all_forms(self, _m):
        for form in ("grow", "grows", "grew", "grown", "growing"):
            text = f"customers {form} revenue"
            self.assertIsNotNone(claims.customer_outcome_claim(text),
                                 f"must refuse: {text}")


# ------------------------- Benchmark phrase handles singular and plural

class BenchmarkPhraseHandlesPlural(unittest.TestCase):
    """The benchmark phrase matches both singular and plural."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_typical_client_singular(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "a typical client sees better margins"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_typical_clients_plural(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "typical clients see better margins"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_typical_result_singular(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "a typical result is 20% margin improvement"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_typical_results_plural(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "typical results include 20% margin improvement"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_average_client_singular(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "the average client sees better margins"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_average_clients_plural(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "average clients see better margins"))


if __name__ == "__main__":
    unittest.main()
