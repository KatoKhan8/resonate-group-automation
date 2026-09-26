"""TASK-330: a specific must bind to the CLAIM it supports, not just the pack.

Buggie finding H3: `untraceable()` extracted specifics and asked only
whether the string appeared ANYWHERE in the pack. A pack containing
"raised $50M in 2019" made "grew revenue by $50M last quarter" pass,
because "$50M" appeared verbatim. The anti-fabrication gate could be
satisfied by coincidence.

The fix: `_traces` now carries the pack sentence that contained the
specific and requires the draft sentence to share at least two content
words with it (excluding the specific itself and stopwords). Where the
draft says a different thing with the same number, the content overlap
is too thin and the gate refuses.

Both ways, for every case: the laundering REFUSES, and a genuinely
supported claim still PASSES. A rule that refuses everything is not a
fix.
"""
import unittest

from src import copylint


def _lead(body, ident="lead-1"):
    steps = [{"body": body}]
    steps += [{"body": "Step %d filler text." % n} for n in range(2, 6)]
    return {"id": ident, "steps": steps}


class ANewClaimCannotBorrowAnOldNumber(unittest.TestCase):
    """THE DEFECT. The pack says one thing about a figure; the draft says
    another thing with the same figure. Under the old code this passed."""

    def test_revenue_laundered_from_funding_is_refused(self):
        """Pack: raised $50M. Draft: grew revenue by $50M. Different claims,
        same number - the exact case from the Buggie finding."""
        pack = {"facts": [{"snippet": "Acme raised $50M in their Series B "
                                       "round last year."}]}
        draft = "They grew revenue by $50M last quarter."
        result = copylint.untraceable(draft, pack)
        self.assertTrue(result,
                        "a figure reused in a different claim must be "
                        "refused; got empty (passed): draft=%r pack=%r"
                        % (draft, pack))

    def test_the_refusal_names_the_specific(self):
        """The refusal must say WHAT was untraceable, not just that
        something was."""
        pack = {"facts": [{"snippet": "Acme raised $50M in their Series B "
                                       "round last year."}]}
        draft = "They grew revenue by $50M last quarter."
        result = copylint.untraceable(draft, pack)
        self.assertIn("$50M", result)

    def test_headcount_laundered_from_revenue_is_refused(self):
        """Different scenario, same defect pattern."""
        pack = {"facts": [{"snippet": "Company revenue reached $10M in Q3."}]}
        draft = "They expanded headcount by $10M this year."
        result = copylint.untraceable(draft, pack)
        self.assertTrue(result)

    def test_a_percentage_reused_in_a_different_context_is_refused(self):
        """Pack: 42% improvement in deployment speed. Draft: 42% revenue
        growth. Same number, completely different claim."""
        pack = {"facts": [{"snippet": "Their deployment speed improved by "
                                       "42% after the migration."}]}
        draft = "They achieved 42% revenue growth last quarter."
        result = copylint.untraceable(draft, pack)
        self.assertTrue(result)


class AGenuinelySupportedClaimStillPasses(unittest.TestCase):
    """A tightened rule that refuses everything is not a fix."""

    def test_a_faithful_restatement_passes(self):
        """Draft restates the pack sentence with the same verb and context."""
        pack = {"facts": [{"snippet": "Acme raised $50M in their Series B "
                                       "round last year."}]}
        draft = "Acme raised $50M in their Series B funding round."
        result = copylint.untraceable(draft, pack)
        self.assertEqual(result, [],
                         "a faithful restatement must pass; got %r" % result)

    def test_a_close_paraphrase_passes(self):
        """Same claim, different wording - but enough shared content."""
        pack = {"facts": [{"snippet": "Acme raised $50M for their Series B "
                                       "expansion last year."}]}
        draft = "They raised $50M for the Series B expansion."
        result = copylint.untraceable(draft, pack)
        self.assertEqual(result, [],
                         "a close paraphrase must pass; got %r" % result)

    def test_a_sentence_with_no_specifics_still_passes(self):
        """A vague claim with no checkable detail is not this lint's
        business - the module has always said so."""
        pack = {"facts": [{"snippet": "Acme raised $50M in their Series B "
                                       "round."}]}
        draft = "You must be growing quickly."
        result = copylint.untraceable(draft, pack)
        self.assertEqual(result, [])


class TheGuardIsSeenToFail(unittest.TestCase):
    """Acceptance 3: the test must FAIL on the old code. These prove the
    laundering case is the one being caught, not some unrelated rule."""

    def test_the_laundering_case_has_a_company_claim_and_a_specific(self):
        """If the draft sentence had no COMPANY_CLAIM verb, the lint would
        skip it entirely. Assert the verb is present."""
        draft = "They grew revenue by $50M last quarter."
        self.assertTrue(copylint.COMPANY_CLAIM.search(draft),
                         "the test draft must contain a company-claim verb")
        self.assertTrue(copylint.specifics_in(draft),
                         "the test draft must contain at least one specific")

    def test_the_pack_contains_the_specific(self):
        """If the pack did NOT contain $50M, the old code would also refuse.
        The defect is that the old code refuses for the WRONG reason (not
        in pack at all) vs the RIGHT reason (in pack but wrong context).
        Assert the specific IS in the pack text."""
        pack = {"facts": [{"snippet": "Acme raised $50M in their Series B "
                                       "round last year."}]}
        normalised = copylint.pack_text(pack)
        self.assertIn("50m", normalised,
                       "the pack must contain the specific for this to be "
                       "a laundering test rather than a not-in-pack test")


class TheBatchLevelGateRefusesLaunderedCopy(unittest.TestCase):
    """The fix must work through check_batch, not just untraceable directly.
    This is the real entry point in production."""

    def test_a_batch_with_laundered_copy_is_refused(self):
        pack = {"facts": [{"snippet": "Acme raised $50M in their Series B "
                                       "round last year."}]}
        lead = _lead("They grew revenue by $50M last quarter.")
        report = copylint.check_batch([lead], {lead["id"]: pack})
        self.assertTrue(report["refused"])
        self.assertIn(lead["id"],
                      report["offenders"]["untraceable_company_claim"])

    def test_a_batch_with_genuine_copy_passes(self):
        pack = {"facts": [{"snippet": "Acme raised $50M in their Series B "
                                       "round last year."}]}
        lead = _lead("Acme raised $50M in their Series B funding round.")
        report = copylint.check_batch([lead], {lead["id"]: pack})
        self.assertEqual(report["offenders"]["untraceable_company_claim"], [])


if __name__ == "__main__":
    unittest.main()
