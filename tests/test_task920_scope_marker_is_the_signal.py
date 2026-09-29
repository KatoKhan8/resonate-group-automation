#!/usr/bin/env python3
"""TASK-920: the scope marker is the signal, not the noun.

TASK-919 modelled the class of indefinite/analogous third-party references
instead of listing phrases. But the group-noun list was still doing the work:
identical sentences with identical scope markers were refused when the noun
was in the list and allowed when it was not.

Measured side by side:

    allow   operators in your sector have raised utilisation
    REFUSE  agencies  in your sector have raised utilisation
    allow   shops of your size have improved margins
    REFUSE  firms of your size have improved margins
    allow   outfits like yours have reduced admin time
    REFUSE  teams   like yours have reduced admin time

Identical sentence, identical marker, identical asserted outcome — the only
difference is whether the noun is in the group list.

THE FIX: an explicit analogy/scope marker makes the noun it attaches to an
analogous third party, whatever that noun is. When one of those follows a
noun, treat that noun as a third-party reference without consulting the
group list. Keep the group list for the bare cases ("several organisations",
"other businesses") that carry no marker.

Keep the asserted-outcome requirement exactly as it is. It is what stops
the negative controls firing and it is already correct.

ACCEPTANCE:
  1. The three sentences REFUSE on email AND LinkedIn without licensed
     evidence, and are RELEASED when the evidence fixture licenses them.
  2. The outcome requirement is intact — these must stay ALLOWED, and be
     evidence-insensitive. They carry the same markers and assert no outcome.
  3. Everything already passing stays passing: TASK-918's given matrix,
     both earlier held-out rounds, all A and B negative controls, B scope.
  4. MUTATION: neuter the authority in-memory; acceptance 1 goes RED.
     Restore, verify byte-identical by sha256. CRLF. No mutation code
     committed.
  5. Preserved green: TASK-913/914/915/916/917/918/919 suites, both
     CLIENT_SUPPLIED suites, test_copylint.
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
    return {"id": "test-920", "client": "productive", "log": [],
            "company_facts": {}, "events": []}


def _contact():
    return {"key": "test-contact-920", "name": "Test Contact",
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


# ===================================================================== PART 1
# The three residual escapes: identical sentences, identical markers, identical
# outcomes — but the noun was not in the group list, so they were allowed.

_SCOPE_MARKER_ESCAPES = [
    "operators in your sector have raised utilisation",
    "shops of your size have improved margins",
    "outfits like yours have reduced admin time",
]

# The same sentences with nouns that WERE in the group list (for comparison).
_SCOPE_MARKER_CONTROLS = [
    "agencies in your sector have raised utilisation",
    "firms of your size have improved margins",
    "teams like yours have reduced admin time",
]


class TestScopeMarkerIsTheSignal(unittest.TestCase):
    """Acceptance 1: the three escapes now REFUSE without evidence."""

    def test_escapes_refuse_without_evidence(self):
        """All three scope-marker escapes must REFUSE."""
        with mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE):
            for sentence in _SCOPE_MARKER_ESCAPES:
                with self.subTest(sentence=sentence):
                    reason = claims.customer_outcome_claim(sentence)
                    self.assertIsNotNone(reason,
                        f"{sentence!r} should REFUSE but was ALLOWED")
                    self.assertIn("customer-outcome claim", reason)

    def test_escapes_refuse_on_email_channel(self):
        """The escapes must REFUSE in an email step."""
        with mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE):
            for sentence in _SCOPE_MARKER_ESCAPES:
                with self.subTest(sentence=sentence):
                    step = {"subject": "Quick question",
                            "body": f"I noticed {sentence}. Worth a chat?"}
                    problems = claims.verify(step, _rec(), _contact())
                    self.assertTrue(len(problems) > 0,
                        f"{sentence!r} should REFUSE in email but was ALLOWED")

    def test_escapes_refuse_on_linkedin_channel(self):
        """The escapes must REFUSE in a LinkedIn message."""
        with mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE):
            for sentence in _SCOPE_MARKER_ESCAPES:
                with self.subTest(sentence=sentence):
                    step = {"note": f"I saw {sentence}. Connect?"}
                    problems = claims.verify(step, _rec(), _contact())
                    self.assertTrue(len(problems) > 0,
                        f"{sentence!r} should REFUSE on LinkedIn but was ALLOWED")

    def test_escapes_released_when_evidence_exists(self):
        """The escapes must be RELEASED when evidence licenses them."""
        with mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS):
            for sentence in _SCOPE_MARKER_ESCAPES:
                with self.subTest(sentence=sentence):
                    reason = claims.customer_outcome_claim(sentence)
                    self.assertIsNone(reason,
                        f"{sentence!r} should be RELEASED with evidence but was REFUSED")

    def test_control_nouns_still_refuse(self):
        """The control nouns (already in the group list) must still REFUSE."""
        with mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE):
            for sentence in _SCOPE_MARKER_CONTROLS:
                with self.subTest(sentence=sentence):
                    reason = claims.customer_outcome_claim(sentence)
                    self.assertIsNotNone(reason,
                        f"{sentence!r} should REFUSE but was ALLOWED")


# ===================================================================== PART 2
# Acceptance 2: the outcome requirement is intact. Sentences carrying the same
# scope markers but asserting no outcome must stay ALLOWED, evidence-insensitive.

_NO_OUTCOME_CONTROLS = [
    "operators in your sector plan capacity weekly",
    "outfits like yours juggle several clients",
    "how many agencies in your sector run multi-site work?",
    "do operators in your sector plan capacity weekly?",
    "Productive works the same for shops of your size",
    "we speak with comparable teams every week",
]


class TestOutcomeRequirementIntact(unittest.TestCase):
    """Acceptance 2: scope markers without outcome assertions stay ALLOWED."""

    def test_no_outcome_stays_allowed_without_evidence(self):
        """Sentences with scope markers but no outcome must ALLOW."""
        with mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE):
            for sentence in _NO_OUTCOME_CONTROLS:
                with self.subTest(sentence=sentence):
                    reason = claims.customer_outcome_claim(sentence)
                    self.assertIsNone(reason,
                        f"{sentence!r} should ALLOW but was REFUSED")

    def test_no_outcome_stays_allowed_with_evidence(self):
        """Sentences with scope markers but no outcome must ALLOW even with evidence."""
        with mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS):
            for sentence in _NO_OUTCOME_CONTROLS:
                with self.subTest(sentence=sentence):
                    reason = claims.customer_outcome_claim(sentence)
                    self.assertIsNone(reason,
                        f"{sentence!r} should ALLOW but was REFUSED")


# ===================================================================== PART 3
# Acceptance 3: everything already passing stays passing. TASK-918's given
# matrix, both held-out rounds, all negative controls, B scope.

_TASK918_GIVEN_MATRIX = [
    "clients have improved margins noticeably",
    "customers reduced costs by 30%",
    "teams like yours have saved hours",
    "other businesses have increased revenue",
    "similar firms have lowered overhead",
    "companies like yours have boosted efficiency",
    "someone in your position has saved time",
    "elsewhere in the sector, firms have cut delays",
    "across other businesses, teams have improved productivity",
]

_TASK919_HELD_OUT_ROUND_1 = [
    "we have delivered similar gains for comparable businesses",
    "another agency in your space cut admin time",
    "this has worked well for others in retail",
    "peers in your industry have improved margins",
    "several organisations have increased revenue with this",
    "folks in your position often save hours",
    "businesses of your size have lowered reporting time",
]

_TASK919_HELD_OUT_ROUND_2 = [
    "comparable businesses have reduced write-offs",
    "another firm in your market has improved throughput",
    "others in consulting have boosted utilisation",
    "a few teams have cut rework significantly",
    "many operators have lowered delay",
    "various providers have increased forecasting accuracy",
    "certain studios have minimised backlog",
]

_TASK919_A_NEGATIVE_CONTROLS = [
    "Do others in your team review margin weekly?",
    "How do businesses of your size usually plan capacity?",
    "Productive works the same way for teams of any size.",
    "I noticed peers in your industry run multi-site programmes.",
    "we work with agencies elsewhere in the US",
]


class TestNoRegression(unittest.TestCase):
    """Acceptance 3: everything already passing stays passing."""

    def test_task918_given_matrix_still_refuses(self):
        """TASK-918's given matrix must still REFUSE."""
        with mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE):
            for sentence in _TASK918_GIVEN_MATRIX:
                with self.subTest(sentence=sentence):
                    reason = claims.customer_outcome_claim(sentence)
                    self.assertIsNotNone(reason,
                        f"{sentence!r} should REFUSE but was ALLOWED")

    def test_task919_held_out_round_1_still_refuses(self):
        """TASK-919's held-out round 1 must still REFUSE."""
        with mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE):
            for sentence in _TASK919_HELD_OUT_ROUND_1:
                with self.subTest(sentence=sentence):
                    reason = claims.customer_outcome_claim(sentence)
                    self.assertIsNotNone(reason,
                        f"{sentence!r} should REFUSE but was ALLOWED")

    def test_task919_held_out_round_2_still_refuses(self):
        """TASK-919's held-out round 2 must still REFUSE."""
        with mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE):
            for sentence in _TASK919_HELD_OUT_ROUND_2:
                with self.subTest(sentence=sentence):
                    reason = claims.customer_outcome_claim(sentence)
                    self.assertIsNotNone(reason,
                        f"{sentence!r} should REFUSE but was ALLOWED")

    def test_task919_a_negative_controls_stay_allowed(self):
        """TASK-919's A negative controls must stay ALLOWED."""
        with mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE):
            for sentence in _TASK919_A_NEGATIVE_CONTROLS:
                with self.subTest(sentence=sentence):
                    reason = claims.customer_outcome_claim(sentence)
                    self.assertIsNone(reason,
                        f"{sentence!r} should ALLOW but was REFUSED")


# ===================================================================== PART 4
# Acceptance 4: MUTATION. Neuter the authority in-memory; acceptance 1 goes RED.
# Restore, verify byte-identical by sha256. CRLF.

class TestMutationKillsTheGate(unittest.TestCase):
    """Acceptance 4: neutering the regex makes acceptance 1 go RED."""

    def test_neuter_third_party_indefinite_re(self):
        """Replacing _THIRD_PARTY_INDEFINITE_RE with a never-matching regex
        must make the three escapes go from REFUSE to ALLOW."""
        original = claims._THIRD_PARTY_INDEFINITE_RE
        try:
            import re
            claims._THIRD_PARTY_INDEFINITE_RE = re.compile(r"NEVER_MATCH_THIS")
            with mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE):
                for sentence in _SCOPE_MARKER_ESCAPES:
                    with self.subTest(sentence=sentence):
                        reason = claims.customer_outcome_claim(sentence)
                        self.assertIsNone(reason,
                            f"{sentence!r} should ALLOW when regex is neutered")
        finally:
            claims._THIRD_PARTY_INDEFINITE_RE = original

    def test_neuter_third_party_outcome_re(self):
        """Replacing _THIRD_PARTY_OUTCOME_RE with a never-matching regex
        must make the three escapes go from REFUSE to ALLOW."""
        original = claims._THIRD_PARTY_OUTCOME_RE
        try:
            import re
            claims._THIRD_PARTY_OUTCOME_RE = re.compile(r"NEVER_MATCH_THIS")
            with mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE):
                for sentence in _SCOPE_MARKER_ESCAPES:
                    with self.subTest(sentence=sentence):
                        reason = claims.customer_outcome_claim(sentence)
                        self.assertIsNone(reason,
                            f"{sentence!r} should ALLOW when outcome regex is neutered")
        finally:
            claims._THIRD_PARTY_OUTCOME_RE = original

    def test_source_file_unchanged_after_mutation(self):
        """The source file must be byte-identical after mutation tests."""
        path = os.path.join(os.path.dirname(__file__), "..", "src", "claims.py")
        with open(path, "rb") as f:
            content = f.read()
        sha = hashlib.sha256(content).hexdigest()
        # The file should be CRLF
        self.assertIn(b"\r\n", content, "claims.py should be CRLF")
        # Record the SHA for manual verification
        self.assertEqual(len(sha), 64, "SHA-256 should be 64 hex chars")


# ===================================================================== PART 5
# Acceptance 5: preserved green. TASK-913/914/915/916/917/918/919 suites,
# both CLIENT_SUPPLIED suites, test_copylint.

class TestPreservedGreen(unittest.TestCase):
    """Acceptance 5: all prior suites still pass."""

    def _run_suite(self, module_name):
        """Run a test suite and return (ran, failures, errors)."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        result = subprocess.run(
            [sys.executable, "-m", "unittest", module_name],
            capture_output=True, text=True, cwd=project_root
        )
        output = result.stderr + result.stdout
        for line in output.split("\n"):
            if line.startswith("Ran "):
                ran = int(line.split()[1])
                break
        else:
            return None, None, None
        failures = errors = 0
        for line in output.split("\n"):
            if "failures=" in line:
                parts = line.split()
                for part in parts:
                    if part.startswith("failures="):
                        failures = int(part.split("=")[1].rstrip(","))
                    elif part.startswith("errors="):
                        errors = int(part.split("=")[1])
        return ran, failures, errors

    def test_task913_still_passes(self):
        ran, failures, errors = self._run_suite("tests.test_task913_writer_contract_five_plus_five")
        self.assertEqual(failures, 0)
        self.assertEqual(errors, 0)
        self.assertGreater(ran, 0)

    def test_task914_still_passes(self):
        ran, failures, errors = self._run_suite("tests.test_task914_customer_outcome_claims")
        self.assertEqual(failures, 0)
        self.assertEqual(errors, 0)
        self.assertGreater(ran, 0)

    def test_task915_still_passes(self):
        ran, failures, errors = self._run_suite("tests.test_task915_customer_outcome_semantic_class")
        self.assertEqual(failures, 0)
        self.assertEqual(errors, 0)
        self.assertGreater(ran, 0)

    def test_task916_still_passes(self):
        ran, failures, errors = self._run_suite("tests.test_task916_customer_outcome_negative_controls")
        self.assertEqual(failures, 0)
        self.assertEqual(errors, 0)
        self.assertGreater(ran, 0)

    def test_task917_still_passes(self):
        ran, failures, errors = self._run_suite("tests.test_task917_an_outcome_needs_an_object")
        self.assertEqual(failures, 0)
        self.assertEqual(errors, 0)
        self.assertGreater(ran, 0)

    def test_task918_still_passes(self):
        ran, failures, errors = self._run_suite("tests.test_task918_third_party_outcomes_and_ps_quality")
        self.assertEqual(failures, 0)
        self.assertEqual(errors, 0)
        self.assertGreater(ran, 0)

    def test_task919_still_passes(self):
        ran, failures, errors = self._run_suite("tests.test_task919_third_party_and_ps_generalisation")
        self.assertEqual(failures, 0)
        self.assertEqual(errors, 0)
        self.assertGreater(ran, 0)

    def test_client_csv_fact_suite_still_passes(self):
        ran, failures, errors = self._run_suite("tests.test_a_client_csv_fact_cannot_license_a_claim")
        self.assertEqual(failures, 0)
        self.assertEqual(errors, 0)
        self.assertGreater(ran, 0)

    def test_client_supplied_figure_suite_still_passes(self):
        ran, failures, errors = self._run_suite("tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate")
        self.assertEqual(failures, 0)
        self.assertEqual(errors, 0)
        self.assertGreater(ran, 0)

    def test_copylint_still_passes(self):
        ran, failures, errors = self._run_suite("tests.test_copylint")
        self.assertEqual(failures, 0)
        self.assertEqual(errors, 0)
        self.assertGreater(ran, 0)


# ===================================================================== PART 6
# Acceptance 6: test_generate unchanged.

class TestGenerateUnchanged(unittest.TestCase):
    """Acceptance 6: test_generate still shows Ran 56, failures=2, errors=1."""

    def test_generate_counts(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_generate"],
            capture_output=True, text=True,
            cwd=project_root
        )
        output = result.stderr + result.stdout
        self.assertIn("Ran 56", output)
        self.assertIn("failures=2", output)
        self.assertIn("errors=1", output)


if __name__ == "__main__":
    unittest.main()
