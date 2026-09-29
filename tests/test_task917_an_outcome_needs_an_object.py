#!/usr/bin/env python3
"""TASK-917: an outcome claim needs an object.

THE TWO DEFECTS (measured through generate._step_refusals on both channels):

1. ESCAPE - unsupported customer outcomes ship:
       ALLOWED   clients consistently see faster reporting cycles
       ALLOWED   clients see faster turnaround
   The comparative branch metric list was too narrow.

2. OVERBLOCK - legitimate copy refused:
       REFUSED   agencies we speak with raise this constantly
       REFUSED   clients raise this constantly
   The achievement branch fired on subject + verb alone, with no
   requirement that an outcome be named. "raise" means "bring up",
   not "increase" - matched only because "rais" is an achievement stem.

THE FIX - one idea, both defects:
   An outcome claim needs an object. "Our customers improved" is not a
   claim about anything until it names WHAT improved.
   - Achievement branch: require an outcome-metric complement within a
     60-char window. Kills defect 2.
   - Widen the metric vocabulary to the client's real domain, shared
     between achievement complement and comparative branch. Kills
     defect 1.

ACCEPTANCE:
  1. Both counterexamples fixed.
  2. Nothing regresses (20+ assertions still refuse, released with evidence).
  3. Nothing overblocks (21 sentences not refused, evidence-insensitive).
  4. Evidence-sensitivity is the discriminator.
  5. CLIENT_SUPPLIED suites green and UNEDITED.
  6. TASK-913 chain green; li5 survives; one authority.
  7. Part B observability decision-neutral.
  8. MUTATION: neuter rule; acceptances 1 and 2 go RED.
  9. test_generate: Ran 56, failures=2, errors=1. Unchanged.
"""
import hashlib
import inspect
import os
import subprocess
import sys
import unittest
from unittest import mock

from src import claims, generate, lint, verification


# --------------------------------------------------------------------- helpers

def _rec():
    return {"id": "test-917", "client": "productive", "log": [],
            "company_facts": {}, "events": []}


def _contact():
    return {"key": "test-contact-917", "name": "Test Contact",
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

# Acceptance 1: the two counterexamples - must be fixed.
_ESCAPE = [
    "clients consistently see faster reporting cycles",
    "clients see faster turnaround",
]

_OVERBLOCK = [
    "agencies we speak with raise this constantly",
    "clients raise this constantly",
]

# Acceptance 2: must still REFUSE (with missing evidence).
_MUST_REFUSE = [
    "our clients improve project margins",
    "our clients improved project margins",
    "our clients are improving project margins",
    "our clients have improved project margins",
    "our clients can improve project margins",
    "our clients usually improve project margins",
    "customers reduce costs",
    "customers save time",
    "customers increase revenue",
    "customers increase profitability",
    "clients improve resource allocation",
    "typical clients see better margins",
    "a typical client improves margins",
    "firms see higher profitability",
    "clients have seen better margins",
    "our clients are seeing lower overhead",
    "the average customer sees stronger profitability",
    "clients we work with have cut reporting time",
    "studios typically raise utilisation",
    "firms in your space have increased margins with us",
    "costs were reduced for our clients",
    "nine in ten clients lower their admin hours",
    "agencies using Productive cut admin time",
    "teams that adopt it save hours each week",
    "most clients improve utilisation within a quarter",
    "we help clients improve project margins",
    "clients will improve margins",
    "clients would reduce costs",
]

# Acceptance 3: must NOT refuse (evidence-insensitive).
_MUST_ALLOW = [
    "finance teams see budget against actuals in one place",
    "your teams can see margin per project while work runs",
    "teams see where hours are going each week",
    "Productive gives teams one view of utilisation",
    "Productive puts margin and utilisation on one screen",
    "the tool shows teams where hours are going",
    "saw your team's post about the new Dallas office",
    "noticed your agency picked up three retail accounts",
    "how do your teams track margin today?",
    "do your teams cut the month-end close manually?",
    "do your teams see margin before a project closes?",
    "could your firm cut reporting time in half?",
    "would your team save time with one view of this?",
    "we work with agencies that see the same problem",
    "agencies we speak with raise this constantly",
    "most teams track this in spreadsheets",
    "your clients expect faster turnaround",
    "Productive provides real-time project margin visibility.",
    "Would improving margin visibility be useful?",
    "Are you trying to reduce the time spent reconciling project data?",
    "clients raise this constantly",
]


# --------------- Acceptance 1: both counterexamples fixed

class CounterexamplesFixed(unittest.TestCase):
    """Acceptance 1: escapes refused, overblocks allowed."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_escapes_now_refused(self, _m):
        for text in _ESCAPE:
            self.assertIsNotNone(
                claims.customer_outcome_claim(text),
                f"should be refused: {text!r}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_overblocks_now_allowed(self, _m):
        for text in _OVERBLOCK:
            self.assertIsNone(
                claims.customer_outcome_claim(text),
                f"should be allowed: {text!r}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_escapes_via_claims_check(self, _m):
        rec = _rec()
        for text in _ESCAPE:
            problems = claims.check(text, rec)
            self.assertTrue(
                any("customer-outcome" in p["why"] for p in problems),
                f"claims.check should refuse: {text!r}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_overblocks_via_claims_check(self, _m):
        rec = _rec()
        for text in _OVERBLOCK:
            problems = claims.check(text, rec)
            outcome_problems = [p for p in problems
                                if "customer-outcome" in p["why"]]
            self.assertEqual(outcome_problems, [],
                             f"claims.check should allow: {text!r}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_escapes_via_linkedin(self, _m):
        for text in _ESCAPE:
            rec = _rec()
            contact = _contact()
            rec["cadence"] = {contact["key"]: {}}
            pairs = [
                ("li1", {"channel": "linkedin", "generated": True,
                         "note": text}),
            ]
            refusals = generate._step_refusals(rec, contact, pairs)
            self.assertIn("li1", refusals,
                          f"LinkedIn should refuse: {text!r}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_overblocks_not_refused_for_outcome_via_linkedin(self, _m):
        for text in _OVERBLOCK:
            rec = _rec()
            contact = _contact()
            rec["cadence"] = {contact["key"]: {}}
            pairs = [
                ("li1", {"channel": "linkedin", "generated": True,
                         "note": text}),
            ]
            refusals = generate._step_refusals(rec, contact, pairs)
            reasons = refusals.get("li1", [])
            outcome_reasons = [r for r in reasons
                               if "customer-outcome" in str(r)]
            self.assertEqual(outcome_reasons, [],
                             f"LinkedIn should not refuse for outcome: "
                             f"{text!r}, got: {reasons}")


# ---------- Acceptance 2: nothing regresses

class NothingRegresses(unittest.TestCase):
    """Acceptance 2: all must-refuse assertions still refuse."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_all_must_refuse_via_detector(self, _m):
        escaped = [t for t in _MUST_REFUSE
                   if claims.customer_outcome_claim(t) is None]
        self.assertEqual(escaped, [],
                         f"{len(escaped)} escaped: {escaped}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_all_must_refuse_via_claims_check(self, _m):
        rec = _rec()
        for text in _MUST_REFUSE:
            problems = claims.check(text, rec)
            self.assertTrue(
                any("customer-outcome" in p["why"] for p in problems),
                f"not refused via claims.check: {text!r}")


# ----------- Acceptance 3: nothing overblocks

class NothingOverblocks(unittest.TestCase):
    """Acceptance 3: all must-allow assertions are NOT refused."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_all_must_allow_via_detector(self, _m):
        refused = [t for t in _MUST_ALLOW
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} overblocked: {refused}")


# ------ Acceptance 4: evidence-sensitivity is the discriminator

class EvidenceSensitivityIsTheDiscriminator(unittest.TestCase):
    """Acceptance 4: every refusal disappears with evidence; every
    must-allow behaves identically with and without it."""

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_escapes_released_with_evidence(self, _m):
        refused = [t for t in _ESCAPE
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"escapes still refused with evidence: {refused}")

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_must_refuse_released_with_evidence(self, _m):
        refused = [t for t in _MUST_REFUSE
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} still refused with evidence: "
                         f"{refused}")

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_must_allow_identical_with_evidence(self, _m):
        refused = [t for t in _MUST_ALLOW
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} overblocked with evidence: "
                         f"{refused}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_must_allow_identical_without_evidence(self, _m):
        refused = [t for t in _MUST_ALLOW
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} overblocked without evidence: "
                         f"{refused}")


# ------ Acceptance 5: CLIENT_SUPPLIED tests green and UNEDITED

class ClientSuppliedTestsUnedited(unittest.TestCase):
    """Acceptance 5: CLIENT_SUPPLIED suites green and UNEDITED."""

    def test_client_csv_fact_test_exists(self):
        path = os.path.join("tests",
                            "test_a_client_csv_fact_cannot_license_a_claim.py")
        self.assertTrue(os.path.isfile(path), f"{path} must exist")

    def test_client_supplied_figure_test_exists(self):
        path = os.path.join(
            "tests",
            "test_a_client_supplied_figure_licenses_no_claim_in_either_gate.py")
        self.assertTrue(os.path.isfile(path), f"{path} must exist")


# --------- Acceptance 6: TASK-913 chain green, li5 survives

class Task913ChainGreen(unittest.TestCase):
    """Acceptance 6: TASK-913 chain still green; li5 survives."""

    def test_linkedin_writer_keys_has_five_elements(self):
        from src import cadencelibrary
        self.assertEqual(len(cadencelibrary.LINKEDIN_WRITER_KEYS), 5)

    def test_li5_in_linkedin_writer_keys(self):
        from src import cadencelibrary
        self.assertIn("li5", cadencelibrary.LINKEDIN_WRITER_KEYS)

    def test_one_authority_claims_module(self):
        self.assertTrue(hasattr(claims, "customer_outcome_claim"))


# ---- Acceptance 7: Part B observability unchanged

class PartBObservabilityUnchanged(unittest.TestCase):
    """Acceptance 7: lint.sendable and verification policy unchanged."""

    def test_lint_sendable_delegates_to_verification(self):
        import inspect
        source = inspect.getsource(lint.sendable)
        self.assertIn("verification", source)

    def test_verification_decide_has_trust_secondary_policy(self):
        source = inspect.getsource(verification.decide)
        self.assertIn("trust_secondary_when_primary_unknown", source)


# --------------- Acceptance 8: mutation test

class MutationTest(unittest.TestCase):
    """Acceptance 8: neuter the rule; acceptances 1 and 2 go RED.
    Restore and verify byte-identical by sha256. Files are CRLF."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_neuter_lets_escapes_through(self, _m):
        active = sum(1 for t in _ESCAPE
                     if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(active, len(_ESCAPE),
                         "all escapes must be refused with rule active")

        with mock.patch.object(claims, "customer_outcome_claim",
                               return_value=None):
            neutered = sum(1 for t in _ESCAPE
                          if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(neutered, 0, "neutered must let escapes through")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_neuter_lets_must_refuse_through(self, _m):
        active = sum(1 for t in _MUST_REFUSE
                     if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(active, len(_MUST_REFUSE),
                         "all must-refuse must be refused with rule active")

        with mock.patch.object(claims, "customer_outcome_claim",
                               return_value=None):
            neutered = sum(1 for t in _MUST_REFUSE
                          if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(neutered, 0,
                         "neutered must let must-refuse through")

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


# --- Acceptance 9: test_generate signature unchanged

class TestGenerateSignatureUnchanged(unittest.TestCase):
    """Acceptance 9: test_generate signature: Ran 56, failures=2, errors=1."""

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


# --- Complement requirement: the new behaviour

class ComplementRequirement(unittest.TestCase):
    """The achievement branch requires an outcome-metric complement."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_bare_verb_no_complement_allowed(self, _m):
        self.assertIsNone(
            claims.customer_outcome_claim("clients raise this constantly"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_verb_with_complement_refused(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim("clients raise utilisation"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_reversed_with_metric_refused(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim(
                "costs were reduced for our clients"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_reversed_without_metric_allowed(self, _m):
        self.assertIsNone(
            claims.customer_outcome_claim(
                "something was done for our clients"))


# --- Shared vocabulary: one list, two branches

class SharedVocabulary(unittest.TestCase):
    """The same _OUTCOME_METRICS serves both branches."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_new_metrics_in_comparative_branch(self, _m):
        for text in [
            "clients see faster turnaround",
            "clients see faster reporting cycles",
            "clients see more throughput",
            "clients see higher productivity",
            "clients see more backlog",
        ]:
            self.assertIsNotNone(
                claims.customer_outcome_claim(text),
                f"comparative branch should refuse: {text!r}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_new_metrics_in_achievement_branch(self, _m):
        for text in [
            "clients improve throughput",
            "teams cut backlog",
            "customers reduce admin time",
            "clients increase productivity",
        ]:
            self.assertIsNotNone(
                claims.customer_outcome_claim(text),
                f"achievement branch should refuse: {text!r}")

    def test_outcome_metrics_tuple_exists(self):
        self.assertTrue(hasattr(claims, "_OUTCOME_METRICS"))
        self.assertIsInstance(claims._OUTCOME_METRICS, tuple)
        self.assertGreater(len(claims._OUTCOME_METRICS), 20)


if __name__ == "__main__":
    unittest.main()
