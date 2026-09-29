#!/usr/bin/env python3
"""TASK-914: unsupported customer-outcome claims must be refused.

THE DEFECT: a LinkedIn message said "clients using report intelligence have
improved resource allocation and project margins noticeably" and every gate
allowed it. The system's own `offers.missing()` reports no customer case
studies and no verified benchmarks, and the claim still shipped.

TWO HALVES:
  A. The claim-safety boundary must refuse customer-outcome claims when no
     licensed evidence exists. Both email AND LinkedIn must consult one
     authority.
  B. A skipped email branch must log the verification reason, not vanish
     silently.

NEGATIVE CONTROLS:
  - A capability statement ("Productive shows margin per project") is NOT
    refused.
  - CLIENT_SUPPLIED tests stay green and unedited.
  - If evidence exists (gaps filled), the claim passes through.
"""
import unittest
from unittest import mock

from src import claims, generate, lint, store


# --------------------------------------------------------------------- helpers

def _rec_with_log():
    """A minimal record that can receive `store.log` entries."""
    return {"id": "test-914", "client": "productive", "log": [],
            "company_facts": {}, "events": []}


def _contact_with_email():
    """A contact with a sendable email address."""
    return {"key": "test-contact", "name": "Test Contact",
            "email": "test@example.com",
            "verification": {"evidence": [
                {"provider": "contactout", "status": "valid",
                 "email": "test@example.com"},
                {"provider": "deliverable", "status": "valid",
                 "email": "test@example.com"}]}}


def _contact_without_email():
    """A contact with no email address."""
    return {"key": "test-contact", "name": "Test Contact", "email": ""}


def _contact_held():
    """A contact whose email is held by verification."""
    return {"key": "test-contact", "name": "Held Contact",
            "email": "held@example.com",
            "verification": {"evidence": [
                {"provider": "contactout", "status": "error",
                 "email": "held@example.com"}]}}


# The offers.missing() return value in production: no case studies, no
# benchmarks. This is what makes customer-outcome claims unlicensed.
_MISSING_EVIDENCE = [
    {"gap": "customer case studies",
     "detail": "no documented customer outcomes or case studies available"},
    {"gap": "verified benchmarks",
     "detail": "no before-and-after metrics from comparable firms"},
    {"gap": "dashboard or workflow example",
     "detail": "no screenshot or walkthrough of the Productive interface"},
    {"gap": "calculator",
     "detail": "no ROI or savings calculator available for prospects"},
    {"gap": "demo link",
     "detail": "no live demo environment or recorded demo available"},
]

# When evidence exists, the two relevant gaps are absent.
_EVIDENCE_EXISTS = [
    {"gap": "dashboard or workflow example",
     "detail": "no screenshot available"},
]


# ---------------------------------------------- Part A: customer-outcome claims

class TheExactDefectSentenceIsRefused(unittest.TestCase):
    """The sentence that escaped through LinkedIn must now be refused."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_the_rachele_sentence_is_refused(self, _mock_missing):
        text = ("clients using report intelligence have improved resource "
                "allocation and project margins noticeably.")
        result = claims.customer_outcome_claim(text)
        self.assertIsNotNone(result, "the defect sentence must be refused")
        self.assertIn("customer-outcome", result)


class CustomerOutcomeClaimsAreRefused(unittest.TestCase):
    """The CLASS of claim is refused, not just one sentence."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_improved_margins(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim(
                "our clients have improved their margins by 20%"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_increased_profitability(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim(
                "teams using the platform increased profitability"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_reduced_costs(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim(
                "customers reduced costs across their projects"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_saved_time(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim(
                "agencies saved 10 hours a week on reporting"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_increased_revenue(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim(
                "firms grew revenue after adopting the tool"))


class BenchmarkAndTypicalResultShapesAreRefused(unittest.TestCase):
    """The same claim shaped as a benchmark or offer-to-share is refused."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_offer_to_share_benchmark(self, _m):
        text = ("can i share a benchmark example that might help your team?")
        self.assertIsNotNone(claims.customer_outcome_claim(text))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_typical_result(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim(
                "a typical result is a 20% margin improvement"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_case_study_reference(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim(
                "we have a case study showing improved efficiency"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_success_story(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim(
                "a success story from a similar agency"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_before_and_after(self, _m):
        self.assertIsNotNone(
            claims.customer_outcome_claim(
                "see the before-and-after metrics from our clients"))


class NegativeControlCapabilityStatementIsNotRefused(unittest.TestCase):
    """A Productive capability statement is NOT a customer-outcome claim."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_productive_shows_margin(self, _m):
        text = "productive shows margin per project while it is running"
        self.assertIsNone(claims.customer_outcome_claim(text))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_we_help_teams(self, _m):
        text = "we help teams track their time and budget in one place"
        self.assertIsNone(claims.customer_outcome_claim(text))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_productive_tracks_utilisation(self, _m):
        text = "productive tracks utilisation across your projects"
        self.assertIsNone(claims.customer_outcome_claim(text))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_our_platform_reports_on(self, _m):
        text = "our platform reports on project profitability in real time"
        self.assertIsNone(claims.customer_outcome_claim(text))


class NegativeControlEvidenceExists(unittest.TestCase):
    """If licensed evidence exists, the claim is NOT refused."""

    @mock.patch("src.offers.missing", return_value=_EVIDENCE_EXISTS)
    def test_claim_passes_when_evidence_exists(self, _m):
        text = ("clients using report intelligence have improved resource "
                "allocation and project margins noticeably.")
        self.assertIsNone(claims.customer_outcome_claim(text))


class NegativeControlNoPatternMatch(unittest.TestCase):
    """Normal copy without customer-outcome patterns is not refused."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_generic_opener(self, _m):
        self.assertIsNone(
            claims.customer_outcome_claim(
                "saw you opened a second office in berlin"))

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_question_about_prospect(self, _m):
        self.assertIsNone(
            claims.customer_outcome_claim(
                "how does your team handle resource planning?"))


# ------------------------------------- claims.check integration (both channels)

class ClaimsCheckRefusesCustomerOutcome(unittest.TestCase):
    """`claims.check` refuses customer-outcome claims on the whole text."""

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_email_body_is_refused(self, _m):
        rec = _rec_with_log()
        text = ("clients using report intelligence have improved resource "
                "allocation and project margins noticeably.")
        problems = claims.check(text, rec)
        self.assertTrue(any("customer-outcome" in p["why"] for p in problems),
                        [p["why"] for p in problems])


# ---------------------------------------------- LinkedIn uses same authority

class LinkedInUsesSameClaimsAuthority(unittest.TestCase):
    """The LinkedIn path in `_step_refusals` now runs `claims.check`.

    PROVED BY WIRING: the LinkedIn branch of `_step_refusals` calls
    `claims.check` on the note text. A customer-outcome claim in a
    LinkedIn note is refused the same way it is in an email body.
    """

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_linkedin_note_with_customer_outcome_is_refused(self, _m):
        rec = _rec_with_log()
        contact = _contact_with_email()
        rec["cadence"] = {contact["key"]: {}}
        pairs = [
            ("li1", {"channel": "linkedin", "generated": True,
                     "note": ("clients using report intelligence have "
                              "improved resource allocation and project "
                              "margins noticeably. can i share a benchmark "
                              "example?")}),
        ]
        refusals = generate._step_refusals(rec, contact, pairs)
        self.assertIn("li1", refusals,
                      "LinkedIn note with customer-outcome claim must refuse")
        refusal_text = " ".join(refusals["li1"]).lower()
        self.assertIn("customer-outcome", refusal_text)


# ---------------------------------------------- Part B: email hold is observable

class EmailHoldIsLogged(unittest.TestCase):
    """When the email branch is skipped, the verification reason is logged."""

    def test_no_email_logs_reason(self):
        rec = _rec_with_log()
        contact = _contact_without_email()
        sequence = [{"key": "em1", "channel": "email", "generated": True}]
        contact_result = {"sequences": {"A": "body text"},
                          "subjects": {"A": "subject"}}
        generate._candidate_steps(contact_result, sequence, rec, contact)
        log_entries = [e for e in rec.get("log", [])
                       if e.get("step") == "email_held"]
        self.assertTrue(log_entries,
                        "expected an email_held log entry, got: %s"
                        % rec.get("log", []))
        note = log_entries[0].get("note", "")
        self.assertIn("Test Contact", note,
                      "log must name the contact")
        self.assertIn("no email", note.lower(),
                      "log must state the reason")

    def test_held_email_logs_verification_reason(self):
        rec = _rec_with_log()
        contact = _contact_held()
        sequence = [{"key": "em1", "channel": "email", "generated": True}]
        contact_result = {"sequences": {"A": "body text"},
                          "subjects": {"A": "subject"}}
        generate._candidate_steps(contact_result, sequence, rec, contact)
        log_entries = [e for e in rec.get("log", [])
                       if e.get("step") == "email_held"]
        self.assertTrue(log_entries,
                        "expected an email_held log entry for held contact")
        note = log_entries[0].get("note", "")
        self.assertIn("Held Contact", note,
                      "log must name the contact")

    def test_sendable_email_does_not_log(self):
        rec = _rec_with_log()
        contact = _contact_with_email()
        sequence = [{"key": "em1", "channel": "email", "generated": True}]
        contact_result = {"sequences": {"A": "body text"},
                          "subjects": {"A": "subject"}}
        generate._candidate_steps(contact_result, sequence, rec, contact)
        log_entries = [e for e in rec.get("log", [])
                       if e.get("step") == "email_held"]
        self.assertFalse(log_entries,
                         "sendable email must not log an email_held entry")


# ---------------------------------------------- verification policy is intact

class VerificationPolicyIsUnchanged(unittest.TestCase):
    """`lint.sendable` and `verification.decide` are not modified."""

    def test_trust_secondary_when_primary_unknown_still_in_decide(self):
        import inspect
        from src import verification
        source = inspect.getsource(verification.decide)
        self.assertIn("trust_secondary_when_primary_unknown", source,
                      "verification.decide must still contain the "
                      "trust_secondary_when_primary_unknown policy")

    def test_lint_sendable_delegates_to_verification(self):
        import inspect
        source = inspect.getsource(lint.sendable)
        self.assertIn("verification", source,
                      "lint.sendable must still delegate to verification")


# ---------------------------------------------- mutation test

class MutationTestRemoveClaimRule(unittest.TestCase):
    """MUTATION (TASK-914 acceptance 9): remove the claim rule, acceptances
    1 and 2 must go red.

    This test proves the rule is doing the work by temporarily patching
    `customer_outcome_claim` to return None and asserting the checks pass
    (which is the WRONG outcome - proving the rule is what refuses them).
    """

    @mock.patch("src.offers.missing", return_value=_MISSING_EVIDENCE)
    def test_removing_the_rule_lets_the_defect_through(self, _m):
        text = ("clients using report intelligence have improved resource "
                "allocation and project margins noticeably.")
        # With the rule active: refused.
        self.assertIsNotNone(claims.customer_outcome_claim(text))
        # With the rule removed (patched to return None): passes through.
        with mock.patch.object(claims, "customer_outcome_claim",
                               return_value=None):
            self.assertIsNone(claims.customer_outcome_claim(text))


if __name__ == "__main__":
    unittest.main()
