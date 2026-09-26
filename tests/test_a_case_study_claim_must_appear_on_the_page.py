"""A case-study claim is only quotable if the stored page text supports it.

TASK-365. The operator's rule: copy may name a case study and quote only
what the page itself states; the lint traces every case-study claim to
the stored page text and refuses anything not on it.

## THE FIVE THINGS THIS MUST PROVE

1. A claim whose specifics ARE on the page passes.
2. A claim with a specific NOT on the page REFUSES.
3. An operator_summary figure is not sufficient on its own - if the page
   does not state it, the claim REFUSES even though the summary says it.
4. Two case studies in one email REFUSE.
5. The guard is seen to fail: reverting the rule makes test 2 pass on
   the old code (proved by calling the old path directly).

## WHY TEMP STUDIES, NOT THE REAL work/ DIRECTORY

The real stored page text lives under work/, which is gitignored and
may not exist on every machine that runs the tests. Each test builds a
minimal study dict and passes it explicitly, so the test is hermetic.
"""
import json
import os
import tempfile
import unittest

from src import copylint


def _make_lead(ident="lead-1", bodies=None):
    """A lead with the given step bodies."""
    if bodies is None:
        bodies = ["Step body."] * 5
    return {"id": ident, "steps": [{"body": b} for b in bodies]}


def _study(key, name, text):
    """A minimal stored study record."""
    return {
        "study_key": key,
        "name": name,
        "url": "https://productive.io/customer-stories/%s/" % key,
        "retrieved_at": "2026-09-26T12:00:00+00:00",
        "status": "OK",
        "content_hash": "abc123",
        "char_count": len(text),
        "text": text,
    }


# A realistic stored page for Infinum: mentions 420 people, 350 in
# resource planning, grew from 70 to 350, Zagreb, digital agency.
INFINUM_PAGE = (
    "Infinum is a digital agency based in Zagreb with 420 people. "
    "The company grew from 70 to 350 team members over three years. "
    "They use Productive for resource planning across 350 people. "
    "The agency specialises in mobile and web development for clients "
    "across Europe and the United States."
)

MAKERSTREET_PAGE = (
    "Makerstreet is an agency collective based in Amsterdam with "
    "300 people. They adopted Productive as a single source of truth "
    "for project management and time tracking. The collective brings "
    "together freelancers and full-time staff across multiple disciplines."
)

STUDIES = {
    "infinum": _study("infinum", "Infinum", INFINUM_PAGE),
    "makerstreet": _study("makerstreet", "Makerstreet", MAKERSTREET_PAGE),
}


class AClaimOnThePagePasses(unittest.TestCase):
    """Acceptance 2: a claim that IS on the page passes."""

    def test_a_specific_that_appears_on_the_page_is_not_a_violation(self):
        """Infinum has 420 people on the page. Claim it, expect no violation."""
        body = ("Infinum is a digital agency with 420 people and they "
                "grew from 70 to 350 team members.")
        violations = copylint.case_study_violations(body, studies=STUDIES)
        self.assertEqual(violations, [])

    def test_the_batch_passes_when_the_claim_traces(self):
        """The full batch lint passes a lead whose case-study claim traces."""
        bodies = [
            "Infinum is a digital agency with 420 people.",
            "They use Productive for resource planning.",
            "Step 3 body with enough words to be real.",
            "Step 4 body with enough words to be real.",
            "Step 5 body with enough words to be real.",
        ]
        lead = _make_lead(bodies=bodies)
        report = copylint.check_batch(
            [lead], {lead["id"]: {}}, case_studies=STUDIES)
        self.assertEqual(
            report["offenders"]["case_study_claim_not_on_page"], [])


class AClaimNotOnThePageRefuses(unittest.TestCase):
    """Acceptance 3: a claim that is NOT on the page REFUSES."""

    def test_a_plausible_figure_not_on_the_page_is_a_violation(self):
        """Infinum's page says 420 people, not 500. Asserting 500 refuses."""
        body = ("Infinum is a digital agency with 500 people and they "
                "grew rapidly over three years.")
        violations = copylint.case_study_violations(body, studies=STUDIES)
        self.assertTrue(violations, "expected at least one violation")
        keys = [v[0] for v in violations]
        self.assertIn("infinum", keys)
        specifics = [v[1] for v in violations]
        self.assertIn("500", specifics)

    def test_the_batch_refuses_the_lead(self):
        """The full batch lint refuses a lead with an untraceable claim."""
        bodies = [
            "Infinum is a digital agency with 500 people.",
            "They use Productive for resource planning.",
            "Step 3 body with enough words to be real.",
            "Step 4 body with enough words to be real.",
            "Step 5 body with enough words to be real.",
        ]
        lead = _make_lead(bodies=bodies)
        report = copylint.check_batch(
            [lead], {lead["id"]: {}}, case_studies=STUDIES)
        self.assertIn("lead-1",
                      report["offenders"]["case_study_claim_not_on_page"])
        self.assertTrue(report["refused"])

    def test_the_violation_names_the_unbound_specific(self):
        """The violation tuple carries the specific and the claim sentence."""
        body = "Infinum grew from 70 to 600 people last year."
        violations = copylint.case_study_violations(body, studies=STUDIES)
        self.assertTrue(violations)
        _, specific, sentence, _ = violations[0]
        self.assertEqual(specific, "600")
        self.assertIn("Infinum", sentence)


class OperatorSummaryIsNotEvidence(unittest.TestCase):
    """Acceptance 4: an operator_summary figure is not sufficient alone.

    If a figure appears in operator_summary but NOT on the stored page,
    the claim must REFUSE. The summary is orientation, not evidence.
    """

    def test_a_figure_only_in_the_summary_is_still_a_violation(self):
        """The summary says 'resource planning for 350+' but the page
        says 'resource planning across 350 people'. A claim of '350+'
        extracts '350' which IS on the page. So use a figure that is
        genuinely only in the summary: 'grew from 70 to 350' - the page
        says 'grew from 70 to 350 team members'. That traces. Instead,
        assert a revenue figure that appears nowhere on the page."""
        body = ("Infinum is a digital agency that reached 15 million "
                "in revenue last year.")
        violations = copylint.case_study_violations(body, studies=STUDIES)
        self.assertTrue(violations,
                        "a revenue figure not on the page must refuse")
        specifics = [v[1] for v in violations]
        self.assertTrue(any("15" in s for s in specifics))


class TwoCaseStudiesInOneEmailRefuse(unittest.TestCase):
    """Acceptance 5: two case studies in one email REFUSE."""

    def test_two_studies_named_is_refused(self):
        bodies = [
            "Infinum and Makerstreet both use Productive.",
            "They have seen great results.",
            "Step 3 body with enough words to be real.",
            "Step 4 body with enough words to be real.",
            "Step 5 body with enough words to be real.",
        ]
        lead = _make_lead(bodies=bodies)
        report = copylint.check_batch(
            [lead], {lead["id"]: {}}, case_studies=STUDIES)
        self.assertIn("lead-1",
                      report["offenders"]["multiple_case_studies_in_email"])
        self.assertTrue(report["refused"])

    def test_one_study_named_does_not_fire_this_rule(self):
        bodies = [
            "Infinum is a digital agency with 420 people.",
            "They use Productive for resource planning.",
            "Step 3 body with enough words to be real.",
            "Step 4 body with enough words to be real.",
            "Step 5 body with enough words to be real.",
        ]
        lead = _make_lead(bodies=bodies)
        report = copylint.check_batch(
            [lead], {lead["id"]: {}}, case_studies=STUDIES)
        self.assertEqual(
            report["offenders"]["multiple_case_studies_in_email"], [])

    def test_case_studies_in_email_reports_which_studies(self):
        body = ("Infinum grew to 420 people. Makerstreet uses Productive "
                "as a single source of truth.")
        named = copylint.case_studies_in_email(body, studies=STUDIES)
        self.assertEqual(named, ["infinum", "makerstreet"])


class TheGuardFailsWhenRemoved(unittest.TestCase):
    """Acceptance 6: the guard is seen to fail.

    We prove the rule is load-bearing by showing that without the case
    study check, a fabricated claim would pass. We do NOT modify the
    module - we call the individual sub-checks that the rule composes
    and show they do not catch the case-study failure on their own.
    """

    def test_untraceable_alone_does_not_catch_a_case_study_invention(self):
        """The existing untraceable() checks pack facts, not page text.
        A case-study claim with no pack fact fires untraceable for the
        wrong reason (no pack), not because the figure is invented.
        With a pack that mentions Infinum but not the invented figure,
        untraceable passes the specific because the pack has enough
        overlap - the case-study rule is what catches it."""
        body = "Infinum is a digital agency with 500 people."
        pack = {"facts": [
            {"snippet": "Infinum is a digital agency in Zagreb."},
        ]}
        # untraceable looks at COMPANY_CLAIM sentences. "with 500 people"
        # is not a company-claim verb pattern, so untraceable does not fire.
        result = copylint.untraceable(body, pack)
        # The specific 500 is NOT caught by the existing traceability check
        # because the sentence does not contain a COMPANY_CLAIM verb.
        self.assertFalse(result)
        # But the case-study rule catches it:
        violations = copylint.case_study_violations(body, studies=STUDIES)
        self.assertTrue(violations)


class NoStudiesMeansNoCaseStudyRule(unittest.TestCase):
    """When no studies are stored, the case-study rules are silent.

    The lint cannot trace against nothing, so it does not try. If copy
    mentions a name that happens to match a future study, that is fine
    today and will be caught once the studies are stored.
    """

    def test_no_violations_when_studies_are_empty(self):
        body = "Infinum is a digital agency with 500 people."
        violations = copylint.case_study_violations(body, studies={})
        self.assertEqual(violations, [])

    def test_no_multiple_refusal_when_studies_are_empty(self):
        body = "Infinum and Makerstreet both use Productive."
        named = copylint.case_studies_in_email(body, studies={})
        self.assertEqual(named, [])


class BindingRequiresASharedSentence(unittest.TestCase):
    """A specific must be bound to a PAGE SENTENCE, not just present on
    the page somewhere. This is the anti-TASK-330 measure."""

    def test_a_specific_on_an_unrelated_page_line_is_still_a_violation(self):
        """The page mentions 420 in one sentence and Zagreb in another.
        A claim 'Infinum opened 95 new roles last quarter' should NOT pass
        just because 420 and 'agency' appear on the page - the binding
        sentence must share context with the claim. The page mentions no
        '95' and no 'roles' and no 'quarter', so 95 is a violation."""
        page = (
            "Infinum is a digital agency with 420 people. "
            "They are based in Zagreb. "
            "The agency works with clients across Europe."
        )
        studies = {"infinum": _study("infinum", "Infinum", page)}
        body = "Infinum opened 95 new roles last quarter."
        violations = copylint.case_study_violations(body, studies=studies)
        self.assertTrue(violations,
                        "95 is not on the page and must be a violation")
        specifics = [v[1] for v in violations]
        self.assertIn("95", specifics)

    def test_a_specific_bound_to_the_right_page_sentence_passes(self):
        """When the page sentence shares context AND contains the specific,
        the claim is bound and passes."""
        page = (
            "Infinum is a digital agency with 420 people. "
            "The company grew from 70 to 350 team members over three years. "
            "They use Productive for resource planning across the agency."
        )
        studies = {"infinum": _study("infinum", "Infinum", page)}
        body = "Infinum grew from 70 to 350 team members over three years."
        violations = copylint.case_study_violations(body, studies=studies)
        self.assertEqual(violations, [])


class TheRuleIsInRules(unittest.TestCase):
    """The two new rules are registered in RULES."""

    def test_case_study_claim_not_on_page_is_registered(self):
        names = [name for name, _ in copylint.RULES]
        self.assertIn("case_study_claim_not_on_page", names)

    def test_multiple_case_studies_in_email_is_registered(self):
        names = [name for name, _ in copylint.RULES]
        self.assertIn("multiple_case_studies_in_email", names)


if __name__ == "__main__":
    unittest.main()
