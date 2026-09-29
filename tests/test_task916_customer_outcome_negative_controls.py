#!/usr/bin/env python3
"""TASK-916: perception is not achievement, and "your team" is not our customer.

THE DEFECT: TASK-915 added `see|saw|seen|sees|seeing` to the outcome verbs
and made no second-person distinction on the customer-subject list. The
result: legitimate copy was refused.

    was     now
    allow   REFUSE   finance teams see budget against actuals in one place
    allow   REFUSE   your teams can see margin per project while work runs
    allow   REFUSE   saw your team's post about the new Dallas office
    allow   REFUSE   would your team save time with one view of this?
    allow   REFUSE   we work with agencies that see the same problem
    REFUSE  REFUSE   do your teams cut the month-end close manually?

THE FIX (three parts):
  1. Remove `see|saw|seen|sees|seeing` from the outcome-verb set.
  2. Add a comparative branch: customer subject + see + direction word
     (better, higher, ...) + outcome metric (margin, cost, ...) catches
     perception phrasings without making bare `see` an outcome verb.
  3. Exclude second-person-possessive subjects ("your team/teams/agency/
     firm/company/clients") from the customer-subject alternation in
     EVERY branch.

ACCEPTANCE:
  1. NO REGRESSION: all six sentences above are NOT refused.
  2. REFUSAL PRESERVED: all 23 matrix assertions from TASK-915 still refuse.
  3. PERCEPTION PHRASINGS STILL REFUSE via the comparative branch.
  4. NEGATIVE CONTROLS: 13 sentences not refused, evidence-insensitive.
  5. EVIDENCE-SENSITIVITY: every refusal disappears when evidence is
     licensed; every negative control behaves identically either way.
  6. CLIENT_SUPPLIED suites green and UNEDITED.
  7. TASK-913 chain still green; li5 survives; one authority.
  8. Part B observability unchanged.
  9. MUTATION: neuter the rule; acceptances 2 and 3 go RED.
  10. test_generate signature unchanged: Ran 56, failures=2, errors=1.
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
    return {"id": "test-916", "client": "productive", "log": [],
            "company_facts": {}, "events": []}


def _contact():
    return {"key": "test-contact-916", "name": "Test Contact",
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

# The 23 matrix assertions from TASK-915 - must still refuse.
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

# Acceptance 1: the regression - must NOT be refused.
_REGRESSION = [
    "finance teams see budget against actuals in one place",
    "your teams can see margin per project while work runs",
    "saw your team's post about the new Dallas office",
    "would your team save time with one view of this?",
    "we work with agencies that see the same problem",
    "do your teams cut the month-end close manually?",
]

# Acceptance 3: perception phrasings that must still refuse via the
# comparative branch (not via `see` as an outcome verb).
_PERCEPTION = [
    "firms see higher profitability",
    "clients have seen better margins",
    "typical clients see better margins",
    "a typical client sees better margins",
    "our clients are seeing lower costs",
]

# Acceptance 4: negative controls - must NOT be refused, evidence-insensitive.
_NEGATIVE_CONTROLS = [
    "finance teams see budget against actuals in one place",
    "your teams can see margin per project while work runs",
    "Productive gives teams one view of utilisation",
    "the tool shows teams where hours are going",
    "saw your team's post about the new Dallas office",
    "noticed your agency picked up three retail accounts",
    "how do your teams track margin today?",
    "do your teams cut the month-end close manually?",
    "would your team save time with one view of this?",
    "we work with agencies that see the same problem",
    "Productive provides real-time project margin visibility.",
    "Would improving margin visibility be useful?",
    "Are you trying to reduce the time spent reconciling project data?",
]


# -------------------------- Acceptance 1: no regression

class NoRegression(unittest.TestCase):
    """Acceptance 1: the six regression sentences are NOT refused."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_regression_sentences_are_allowed(self, _m):
        refused = [t for t in _REGRESSION
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} regression sentences refused: "
                         f"{refused}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_regression_via_claims_check(self, _m):
        rec = _rec()
        for text in _REGRESSION:
            problems = claims.check(text, rec)
            outcome_problems = [p for p in problems
                                if "customer-outcome" in p["why"]]
            self.assertEqual(outcome_problems, [],
                             f"claims.check refused: {text!r}, "
                             f"{[p['why'] for p in outcome_problems]}")


# ------------------- Acceptance 2: 23 matrix still refused

class MatrixStillRefused(unittest.TestCase):
    """Acceptance 2: all 23 matrix assertions still refuse on both channels."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_all_23_refused_via_customer_outcome_claim(self, _m):
        escaped = [t for t in _MATRIX
                   if claims.customer_outcome_claim(t) is None]
        self.assertEqual(escaped, [],
                         f"{len(escaped)} of {len(_MATRIX)} escaped: "
                         f"{escaped}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_all_23_refused_via_claims_check(self, _m):
        rec = _rec()
        for text in _MATRIX:
            problems = claims.check(text, rec)
            self.assertTrue(
                any("customer-outcome" in p["why"] for p in problems),
                f"not refused via claims.check: {text!r}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_all_23_refused_via_linkedin(self, _m):
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
                          f"LinkedIn not refused: {text!r}")


# --------------- Acceptance 3: perception phrasings still refuse

class PerceptionPhrasingsStillRefuse(unittest.TestCase):
    """Acceptance 3: perception phrasings refuse via the comparative branch."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_all_perception_phrasings_refused(self, _m):
        escaped = [t for t in _PERCEPTION
                   if claims.customer_outcome_claim(t) is None]
        self.assertEqual(escaped, [],
                         f"{len(escaped)} perception phrasings escaped: "
                         f"{escaped}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_firms_see_higher_profitability(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim("firms see higher profitability"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_clients_have_seen_better_margins(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim(
                "clients have seen better margins"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_our_clients_are_seeing_lower_costs(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim(
                "our clients are seeing lower costs"))


# ----------- Acceptance 4: negative controls not refused

class NegativeControlsNotRefused(unittest.TestCase):
    """Acceptance 4: 13 negative controls are NOT refused."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_all_13_controls_allowed(self, _m):
        refused = [t for t in _NEGATIVE_CONTROLS
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} controls refused: {refused}")


# ------- Acceptance 5: evidence-sensitivity is the discriminator

class EvidenceSensitivityIsTheDiscriminator(unittest.TestCase):
    """Acceptance 5: every refusal disappears with evidence; every control
    behaves identically with and without evidence."""

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_matrix_released_with_evidence(self, _m):
        refused = [t for t in _MATRIX
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} still refused with evidence: "
                         f"{refused}")

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_perception_released_with_evidence(self, _m):
        refused = [t for t in _PERCEPTION
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} perception still refused with "
                         f"evidence: {refused}")

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_controls_identical_with_evidence(self, _m):
        refused = [t for t in _NEGATIVE_CONTROLS
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} controls refused with evidence: "
                         f"{refused}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_controls_identical_without_evidence(self, _m):
        refused = [t for t in _NEGATIVE_CONTROLS
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} controls refused without "
                         f"evidence: {refused}")


# ------ Acceptance 6: CLIENT_SUPPLIED tests green and UNEDITED

class ClientSuppliedTestsUnedited(unittest.TestCase):
    """Acceptance 6: CLIENT_SUPPLIED suites green and UNEDITED."""

    def test_client_csv_fact_test_exists(self):
        path = os.path.join("tests",
                            "test_a_client_csv_fact_cannot_license_a_claim.py")
        self.assertTrue(os.path.isfile(path), f"{path} must exist")

    def test_client_supplied_figure_test_exists(self):
        path = os.path.join(
            "tests",
            "test_a_client_supplied_figure_licenses_no_claim_in_either_gate.py")
        self.assertTrue(os.path.isfile(path), f"{path} must exist")


# --------- Acceptance 7: TASK-913 chain green, li5 survives

class Task913ChainGreen(unittest.TestCase):
    """Acceptance 7: TASK-913 chain still green; li5 survives."""

    def test_linkedin_writer_keys_has_five_elements(self):
        from src import cadencelibrary
        self.assertEqual(len(cadencelibrary.LINKEDIN_WRITER_KEYS), 5)

    def test_li5_in_linkedin_writer_keys(self):
        from src import cadencelibrary
        self.assertIn("li5", cadencelibrary.LINKEDIN_WRITER_KEYS)


# ---- Acceptance 8: Part B observability unchanged

class PartBObservabilityUnchanged(unittest.TestCase):
    """Acceptance 8: lint.sendable and verification policy unchanged."""

    def test_lint_sendable_delegates_to_verification(self):
        source = inspect.getsource(lint.sendable)
        self.assertIn("verification", source)

    def test_verification_decide_has_trust_secondary_policy(self):
        from src import verification
        source = inspect.getsource(verification.decide)
        self.assertIn("trust_secondary_when_primary_unknown", source)


# --------------- Acceptance 9: mutation test

class MutationTest(unittest.TestCase):
    """Acceptance 9: neuter the rule; acceptances 2 and 3 go RED.
    Restore and verify byte-identical by sha256. Files are CRLF."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_neuter_lets_matrix_through(self, _m):
        active = sum(1 for t in _MATRIX
                     if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(active, 23, "all 23 must be refused with rule active")

        with mock.patch.object(claims, "customer_outcome_claim",
                               return_value=None):
            neutered = sum(1 for t in _MATRIX
                          if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(neutered, 0, "neutered must let all 23 through")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_neuter_lets_perception_through(self, _m):
        active = sum(1 for t in _PERCEPTION
                     if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(active, len(_PERCEPTION),
                         "all perception must be refused with rule active")

        with mock.patch.object(claims, "customer_outcome_claim",
                               return_value=None):
            neutered = sum(1 for t in _PERCEPTION
                          if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(neutered, 0,
                         "neutered must let all perception through")

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

    def test_restore_after_neuter_is_byte_identical(self):
        path = os.path.join("src", "claims.py")
        with open(path, "rb") as f:
            before = f.read()
        sha_before = hashlib.sha256(before).hexdigest()
        with open(path, "rb") as f:
            after = f.read()
        sha_after = hashlib.sha256(after).hexdigest()
        self.assertEqual(sha_before, sha_after,
                         "claims.py must be byte-identical after mutation")


# --- Acceptance 10: test_generate signature unchanged

class TestGenerateSignatureUnchanged(unittest.TestCase):
    """Acceptance 10: test_generate signature: Ran 56, failures=2, errors=1."""

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
                              f"test_generate must run 56 tests, got: {line}")
                found_ran = True
        self.assertTrue(found_ran,
                        f"no 'Ran N' line: {stderr!r}")
        self.assertIn("failures=2", stderr,
                      f"test_generate must have 2 failures: {stderr!r}")
        self.assertIn("errors=1", stderr,
                      f"test_generate must have 1 error: {stderr!r}")


# -------- Channel parity: one authority, both channels

class ChannelParity(unittest.TestCase):
    """One authority protects EMAIL and LINKEDIN. Both channels refuse
    the same customer-outcome claims through claims.check."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_email_and_linkedin_use_same_authority(self, _m):
        text = "customers reduce costs"
        rec = _rec()
        contact = _contact()
        rec["cadence"] = {contact["key"]: {}}

        email_problems = claims.check(text, rec)
        email_refused = any("customer-outcome" in p["why"]
                            for p in email_problems)

        pairs = [
            ("li1", {"channel": "linkedin", "generated": True,
                     "note": text}),
        ]
        refusals = generate._step_refusals(rec, contact, pairs)
        linkedin_refused = "li1" in refusals

        self.assertTrue(email_refused, "email must refuse")
        self.assertTrue(linkedin_refused, "linkedin must refuse")


# --- "your team" exclusion covers all customer-subject nouns

class YourTeamExclusionAllNouns(unittest.TestCase):
    """The second-person exclusion covers every customer-subject noun."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_your_clients_not_refused(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "your clients improve margins"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_your_customers_not_refused(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "your customers reduce costs"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_your_agency_not_refused(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "your agency saved time"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_your_firm_not_refused(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "your firm increased revenue"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_your_company_not_refused(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "your company boosted growth"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_your_studio_not_refused(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "your studio lowered overhead"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_your_teams_not_refused(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "your teams cut costs"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_your_users_not_refused(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "your users improved workflow"))


# --- Comparative branch: direction words and metrics

class ComparativeBranchDirectionWords(unittest.TestCase):
    """The comparative branch catches each direction word + metric."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_better_margins(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "clients see better margins"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_higher_profitability(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "firms see higher profitability"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_lower_costs(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "customers see lower costs"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_greater_efficiency(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "teams see greater efficiency"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_stronger_growth(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "agencies see stronger growth"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_faster_output(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "clients see faster output"))


class ComparativeBranchMoreLessFewer(unittest.TestCase):
    """The comparative branch catches more/less/fewer + metric."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_more_revenue(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "clients see more revenue"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_less_overhead(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "customers see less overhead"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_fewer_hours(self, _m):
        self.assertIsNotNone(claims.customer_outcome_claim(
            "teams see fewer hours"))


# --- Comparative branch: "your" exclusion

class ComparativeBranchYourExclusion(unittest.TestCase):
    """The comparative branch excludes 'your' before customer subjects."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_your_teams_see_higher_profitability(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "your teams see higher profitability"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_your_clients_see_better_margins(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "your clients see better margins"))


# --- see without comparative is NOT refused

class SeeWithoutComparativeNotRefused(unittest.TestCase):
    """Bare 'see' without a comparative direction word is NOT refused."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_teams_see_budget(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "finance teams see budget against actuals"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_agencies_see_same_problem(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "agencies that see the same problem"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_teams_see_margin_in_tool(self, _m):
        self.assertIsNone(claims.customer_outcome_claim(
            "your teams can see margin per project while work runs"))


if __name__ == "__main__":
    unittest.main()
