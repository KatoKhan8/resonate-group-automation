#!/usr/bin/env python3
"""TASK-919: both TASK-918 rules are keyword lists again.

TASK-918 passed its own matrix but failed a held-out set. Same failure
mode as TASK-915's verb list: the rule was fitted to the examples
instead of the class.

A — _THIRD_PARTY_INDEFINITE_RE was a fixed phrase list. Seven held-out
counterexamples escaped. Fix: model the class — [modifier] + [group
noun] (+ [scope]) — instead of listing phrases. Keep the outcome
requirement that stops negative controls firing.

B — _SERVICE_ENUM_VERBS was a closed verb list. Two held-out counter-
examples escaped because "span" and "do" were not in it. Fix: make the
verb optional; key on (prospect-referring subject OR enum verb) +
(list of 2+ generic service terms) + (not a descriptor modifying a
head noun).

ACCEPTANCE:
  1. All seven A counterexamples REFUSE on email AND LinkedIn without
     licensed evidence, and are RELEASED when evidence licenses them.
  2. All A lines from TASK-918's matrix still refuse (no regression).
  3. Both B counterexamples make copylint.check_batch REFUSE the lead.
  4. All B lines from TASK-918's matrix still refuse.
  5. A NEGATIVE CONTROLS — none may overblock, and A controls stay
     evidence-INSENSITIVE.
  6. B NEGATIVE CONTROLS — must stay allowed.
  7. B SCOPE: LinkedIn note and email body service lists untouched.
  8. MUTATION: neuter each authority; matrix goes RED. Restore,
     verify byte-identical by sha256. CRLF files.
  9. Preserved green: TASK-913/914/915/916/917 suites, both
     CLIENT_SUPPLIED suites, test_copylint, channel parity.
  10. test_generate unchanged: Ran 56, failures=2, errors=1.
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
    return {"id": "test-919", "client": "productive", "log": [],
            "company_facts": {}, "events": []}


def _contact():
    return {"key": "test-contact-919", "name": "Test Contact",
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
# Held-out counterexamples: seven lines that TASK-918 allowed but must refuse.

_A_HELD_OUT_COUNTEREXAMPLES = [
    "we have delivered similar gains for comparable businesses",
    "another agency in your space cut admin time",
    "this has worked well for others in retail",
    "peers in your industry have improved margins",
    "several organisations have increased revenue with this",
    "folks in your position often save hours",
    "businesses of your size have lowered reporting time",
]

# Held-out negative controls: carry the SAME third-party phrases but
# assert no outcome. Must NOT refuse, evidence-insensitive.
_A_HELD_OUT_NEGATIVE_CONTROLS = [
    "Do others in your team review margin weekly?",
    "How do businesses of your size usually plan capacity?",
    "Productive works the same way for teams of any size.",
    "I noticed peers in your industry run multi-site programmes.",
    "we work with agencies elsewhere in the US",
]

# TASK-918 negative controls (must remain allowed).
_A_TASK918_NEGATIVE_CONTROLS = [
    "Would improving margin visibility be useful?",
    "Productive provides real-time margin visibility.",
    "How do teams like yours currently track project margin?",
    "I noticed companies like yours often manage multiple projects.",
    "Can I show you how Productive tracks budget burn?",
]


class AHeldOutCounterexamplesRefuse(unittest.TestCase):
    """Acceptance 1: all seven A counterexamples REFUSE without evidence."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_indefinite_pattern_matches_all(self, _m):
        missed = [t for t in _A_HELD_OUT_COUNTEREXAMPLES
                  if not claims._THIRD_PARTY_INDEFINITE_RE.search(t)]
        self.assertEqual(missed, [],
                         f"{len(missed)} missed indefinite: {missed}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_outcome_pattern_matches_all(self, _m):
        missed = [t for t in _A_HELD_OUT_COUNTEREXAMPLES
                  if not claims._THIRD_PARTY_OUTCOME_RE.search(t)]
        self.assertEqual(missed, [],
                         f"{len(missed)} missed outcome: {missed}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_customer_outcome_claim_refuses_all(self, _m):
        escaped = [t for t in _A_HELD_OUT_COUNTEREXAMPLES
                   if claims.customer_outcome_claim(t) is None]
        self.assertEqual(escaped, [],
                         f"{len(escaped)} escaped: {escaped}")

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_email_channel_refuses(self, _m):
        rec = _rec()
        contact = _contact()
        rec["cadence"] = {contact["key"]: {}}
        for text in _A_HELD_OUT_COUNTEREXAMPLES:
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
        for text in _A_HELD_OUT_COUNTEREXAMPLES:
            pairs = [("li1", {"channel": "linkedin", "generated": True,
                              "note": text})]
            refusals = generate._step_refusals(rec, contact, pairs)
            self.assertIn("li1", refusals,
                          f"LinkedIn should refuse: {text!r}")


class AHeldOutCounterexamplesReleased(unittest.TestCase):
    """Acceptance 1b: released when evidence fixture licenses them."""

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_all_released_with_evidence(self, _m):
        refused = [t for t in _A_HELD_OUT_COUNTEREXAMPLES
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} still refused: {refused}")


class AHeldOutNegativeControls(unittest.TestCase):
    """Acceptance 5: held-out negative controls unrefused, evidence-insens."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_allowed_without_evidence(self, _m):
        refused = [t for t in _A_HELD_OUT_NEGATIVE_CONTROLS
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} overblocked: {refused}")

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_allowed_with_evidence(self, _m):
        refused = [t for t in _A_HELD_OUT_NEGATIVE_CONTROLS
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} overblocked with evidence: {refused}")


class ATask918NegativeControlsStillGreen(unittest.TestCase):
    """Acceptance 5: TASK-918 negative controls still allowed."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_task918_negcontrols_allowed(self, _m):
        refused = [t for t in _A_TASK918_NEGATIVE_CONTROLS
                   if claims.customer_outcome_claim(t) is not None]
        self.assertEqual(refused, [],
                         f"{len(refused)} overblocked: {refused}")


# ===================================================================== PART B
# Held-out counterexamples: two lines that TASK-918 allowed but must refuse.

_B_HELD_OUT_COUNTEREXAMPLES = [
    "Your offerings span merchandising, training and installation.",
    "You do merchandising, product training and display installation.",
]

# TASK-919 B negative controls (must stay allowed).
_B_HELD_OUT_NEGATIVE_CONTROLS = [
    "Since 2022, 2020 Companies has supported Christ's Haven through "
    "donations and volunteerism.",
    "Your work with Christ's Haven For Children stood out while I was "
    "reading your people pages.",
    "Your people page describes a culture built around normalcy, "
    "dignity and hope.",
    "You describe yourselves as a premier sales and marketing agency, "
    "which is a wide remit.",
]


def _make_lead(ps_text=None, li_text=None, body_text=None):
    lead = {
        "id": "test-lead-919",
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


class BHeldOutCounterexamplesRefuse(unittest.TestCase):
    """Acceptance 3: both B counterexamples make check_batch REFUSE."""

    def test_all_counterexamples_refused(self):
        for ps_text in _B_HELD_OUT_COUNTEREXAMPLES:
            lead = _make_lead(ps_text=ps_text)
            report = copylint.check_batch([lead], {"test-lead-919": _PACK})
            self.assertIn("test-lead-919",
                          report["offenders"]["service_list_ps"],
                          f"should refuse: {ps_text!r}")

    def test_service_list_in_ps_detects_all(self):
        for ps_text in _B_HELD_OUT_COUNTEREXAMPLES:
            lead = {"ps": {"line1": ps_text}}
            self.assertTrue(copylint.service_list_in_ps(lead),
                            f"should detect: {ps_text!r}")


class BHeldOutNegativeControls(unittest.TestCase):
    """Acceptance 6: B negative controls must stay allowed."""

    def test_all_negative_controls_allowed(self):
        for ps_text in _B_HELD_OUT_NEGATIVE_CONTROLS:
            lead = _make_lead(ps_text=ps_text)
            report = copylint.check_batch([lead], {"test-lead-919": _PACK})
            self.assertEqual(report["offenders"]["service_list_ps"], [],
                             f"should allow: {ps_text!r}")


class BScopeUnchanged(unittest.TestCase):
    """Acceptance 7: LinkedIn note and email body service lists untouched."""

    def test_linkedin_note_not_refused(self):
        lead = _make_lead(
            li_text="Your services include merchandising, training, "
                    "and installation.")
        report = copylint.check_batch([lead], {"test-lead-919": _PACK})
        self.assertEqual(report["offenders"]["service_list_ps"], [],
                         "LinkedIn note should not trigger service_list_ps")

    def test_email_body_not_refused(self):
        lead = _make_lead(
            body_text="Your services include merchandising, training, "
                      "and installation.")
        report = copylint.check_batch([lead], {"test-lead-919": _PACK})
        self.assertEqual(report["offenders"]["service_list_ps"], [],
                         "Email body should not trigger service_list_ps")


# ===================================================================== PART 8
# Mutation tests

class AMutationTest(unittest.TestCase):
    """Acceptance 8a: neuter A authority; matrix goes RED."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_neuter_lets_held_out_through(self, _m):
        active = sum(1 for t in _A_HELD_OUT_COUNTEREXAMPLES
                     if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(active, len(_A_HELD_OUT_COUNTEREXAMPLES),
                         "all held-out must be refused with rule active")

        with mock.patch.object(claims, "customer_outcome_claim",
                               return_value=None):
            neutered = sum(1 for t in _A_HELD_OUT_COUNTEREXAMPLES
                           if claims.customer_outcome_claim(t) is not None)
        self.assertEqual(neutered, 0, "neutered must let held-out through")

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
    """Acceptance 8b: neuter B authority; matrix goes RED."""

    def test_neuter_lets_held_out_through(self):
        all_ps = (_B_HELD_OUT_COUNTEREXAMPLES +
                  ["Their services include retail merchandising, "
                   "product training, and display installation."])
        active = sum(
            1 for ps in all_ps
            if copylint.service_list_in_ps({"ps": {"line1": ps}}))
        self.assertEqual(active, len(all_ps),
                         "all matrix must be refused with rule active")

        with mock.patch.object(copylint, "service_list_in_ps",
                               return_value=False):
            neutered = sum(
                1 for ps in all_ps
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


# ===================================================================== PART 9
# Preserved green

class PreservedGreen(unittest.TestCase):
    """Acceptance 9: preserved green suites."""

    def test_task918_still_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_task918_third_party_outcomes_and_ps_quality"],
            capture_output=True, text=True, timeout=120)
        self.assertIn("OK", result.stderr,
                      f"TASK-918 should pass: {result.stderr}")

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


# ===================================================================== PART 10
# test_generate signature unchanged

class TestGenerateSignatureUnchanged(unittest.TestCase):
    """Acceptance 10: test_generate: Ran 56, failures=2, errors=1."""

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
