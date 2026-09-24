"""The batch copy lint, each rule proved to fire AND proved to pass.

Operator, 2026-09-24, lane 1: refuse a batch when a step 1 opens without a
pack fact, when two leads share a first line, when a company claim is not
traceable, when any of the five steps is empty, or when a dash or a
buzzword appears - and report counts rather than a bare refusal.

## BOTH WAYS, FOR EVERY RULE

A lint is two claims, and the second is the one that gets skipped: it
refuses what it should, AND it passes what it should. A rule that refuses
everything satisfies the first half perfectly and makes the lint
unusable - copy would be regenerated forever and nobody would learn why.
So every rule below has a negative case beside it, and several have the
specific near-miss that would make a careless pattern over-fire:
`follow-up` is not a dash, and `we work with 40 agencies` is a claim about
US and not about them.
"""
import unittest

from src import copylint, lint


PACK = {"facts": [
    {"kind": "company_post",
     "source_url": "https://li.test/1",
     "published_at": "2026-09-02",
     "snippet": "We have opened a second delivery team in Berlin and are "
                "taking on platform work through Q4."},
    {"kind": "open_role",
     "source_url": "https://careers.acme.test/1",
     "published_at": "2026-09-10",
     "snippet": "Senior Platform Engineer - own our deploy pipeline."},
]}

OPENER = "Saw you opened a second delivery team in Berlin."


def lead(ident="lead-1", opener=OPENER, tail=None, steps=5):
    bodies = [opener + (" " + tail if tail else "")]
    bodies += ["Step %d body, long enough to be real." % n
               for n in range(2, steps + 1)]
    return {"id": ident, "steps": [{"body": b} for b in bodies]}


def run(leads, packs=None):
    packs = packs or {l["id"]: PACK for l in leads}
    return copylint.check_batch(leads, packs)


class ACleanBatchPasses(unittest.TestCase):
    """FIRST, because every refusal below is only meaningful if this holds."""

    def test_it_is_not_refused(self):
        report = run([lead("lead-1"),
                      lead("lead-2", opener="Your Senior Platform Engineer "
                                            "role caught my eye.")])
        self.assertFalse(report["refused"], report["offenders"])
        self.assertEqual(report["clean"], 2)
        self.assertEqual(sum(report["counts"].values()), 0)

    def test_the_report_says_so_in_words(self):
        report = run([lead()])
        self.assertIn("PASSED", copylint.report_lines(report)[0])


class StepOneOpensOnAPackFact(unittest.TestCase):

    def test_an_opener_with_nothing_behind_it_is_refused(self):
        report = run([lead(opener="I wanted to reach out about your growth.")])
        self.assertIn("lead-1",
                      report["offenders"]["step1_without_pack_fact"])

    def test_an_opener_drawn_from_the_pack_is_not(self):
        report = run([lead(opener="Noticed the platform work through Q4.")])
        self.assertEqual(report["offenders"]["step1_without_pack_fact"], [])

    def test_a_lead_with_no_pack_at_all_is_refused_not_excused(self):
        """A batch generated before the packs were built is exactly the
        batch this rule is for."""
        report = copylint.check_batch([lead()], packs={})
        self.assertIn("lead-1",
                      report["offenders"]["step1_without_pack_fact"])


class NoTwoLeadsOpenTheSameWay(unittest.TestCase):

    def test_a_shared_first_line_refuses_both(self):
        report = run([lead("lead-1"), lead("lead-2")])
        self.assertEqual(report["offenders"]["duplicate_first_line"],
                         ["lead-1", "lead-2"],
                         "a duplicate must name BOTH leads; naming only "
                         "the second reads as though the first was fine")

    def test_different_openers_pass(self):
        report = run([lead("lead-1"),
                      lead("lead-2", opener="Your Senior Platform Engineer "
                                            "role caught my eye.")])
        self.assertEqual(report["offenders"]["duplicate_first_line"], [])

    def test_it_compares_on_words_not_punctuation(self):
        """Two lines that differ only by a comma are the same line to a
        reader, and personalisation that survives only in punctuation is
        not personalisation."""
        report = run([lead("lead-1", opener="Saw you opened a Berlin team"),
                      lead("lead-2", opener="Saw you opened a Berlin team.")])
        self.assertEqual(len(report["offenders"]["duplicate_first_line"]), 2)


class AClaimAboutThemHasToTrace(unittest.TestCase):

    def test_an_invented_date_is_refused(self):
        report = run([lead(tail="You opened it in March 2026.")])
        self.assertIn("lead-1",
                      report["offenders"]["untraceable_company_claim"])

    def test_a_figure_that_is_in_the_pack_passes(self):
        report = run([lead(tail="Your Q4 platform work is the interesting "
                                "part.")])
        self.assertEqual(report["offenders"]["untraceable_company_claim"], [])

    def test_a_claim_about_US_is_not_this_lints_business(self):
        """THE OVER-FIRE THAT MATTERS. "we work with 40 agencies" carries a
        specific and is a claim about us; requiring it to appear in THEIR
        research pack would refuse every honest sentence we write."""
        report = run([lead(tail="We work with 40 agencies on exactly this.")])
        self.assertEqual(report["offenders"]["untraceable_company_claim"], [],
                         report["offenders"])

    def test_the_docstring_promise_about_vague_claims_is_kept(self):
        """A wrong sentence with no specific in it PASSES, and the module
        says so. Asserted so nobody later believes the lint reads meaning."""
        report = run([lead(tail="You must be struggling with scale.")])
        self.assertEqual(report["offenders"]["untraceable_company_claim"], [])


class EveryStepHasToExist(unittest.TestCase):

    def test_four_steps_is_refused(self):
        report = run([lead(steps=4)])
        self.assertIn("lead-1", report["offenders"]["empty_step"])

    def test_an_empty_body_among_five_is_refused(self):
        rows = lead()
        rows["steps"][3]["body"] = "   "
        report = run([rows])
        self.assertIn("lead-1", report["offenders"]["empty_step"])

    def test_five_real_steps_pass(self):
        self.assertEqual(run([lead()])["offenders"]["empty_step"], [])

    def test_steps_as_a_mapping_are_read_in_order(self):
        rows = {"id": "lead-1",
                "steps": {"1": {"body": OPENER}, "2": {"body": "b"},
                          "3": {"body": "c"}, "4": {"body": "d"},
                          "5": {"body": "e"}}}
        self.assertEqual(run([rows])["offenders"]["empty_step"], [])


class DashesAndBuzzwords(unittest.TestCase):

    def test_an_em_dash_is_refused(self):
        report = run([lead(tail="It is working — clearly.")])
        self.assertIn("lead-1", report["offenders"]["dash"])

    def test_a_spaced_hyphen_is_refused_too(self):
        """That is what an em dash becomes once anything normalises it, so
        the tell survives the substitution."""
        report = run([lead(tail="It is working - clearly.")])
        self.assertIn("lead-1", report["offenders"]["dash"])

    def test_a_hyphen_inside_a_word_is_not_a_dash(self):
        """THE OVER-FIRE. `follow-up` and `data-driven` are not the thing
        being refused and a careless pattern takes both."""
        report = run([lead(tail="Happy to follow-up with a data-driven "
                                "view.")])
        self.assertEqual(report["offenders"]["dash"], [], report["offenders"])

    def test_a_buzzword_is_refused(self):
        report = run([lead(tail="We can unlock seamless synergy.")])
        self.assertIn("lead-1", report["offenders"]["buzzword"])

    def test_the_existing_banned_phrases_still_fire(self):
        """They are IMPORTED from `lint` rather than copied, so this also
        asserts the two modules cannot drift apart."""
        report = run([lead(tail=lint.BANNED_PHRASES[0].capitalize() + ".")])
        self.assertIn("lead-1", report["offenders"]["buzzword"])

    def test_ordinary_copy_carries_none_of_them(self):
        report = run([lead(tail="Worth a short call next week?")])
        self.assertEqual(report["offenders"]["buzzword"], [])


class ItReportsCountsAndNotJustARefusal(unittest.TestCase):

    def test_the_counts_name_every_rule_that_fired(self):
        batch = [lead("lead-1"), lead("lead-2"),
                 lead("lead-3", opener="I wanted to reach out."),
                 lead("lead-4", tail="It is working — clearly.")]
        report = run(batch)
        self.assertTrue(report["refused"])
        self.assertEqual(report["counts"]["duplicate_first_line"], 2)
        self.assertEqual(report["counts"]["dash"], 1)
        self.assertGreaterEqual(report["counts"]["step1_without_pack_fact"], 1)

    def test_clean_plus_dirty_is_the_whole_batch(self):
        """A count that does not reconcile is a count nobody can act on."""
        batch = [lead("lead-1"),
                 lead("lead-2", opener="I wanted to reach out.")]
        report = run(batch)
        dirty = {i for ids in report["offenders"].values() for i in ids}
        self.assertEqual(report["clean"] + len(dirty), report["leads"])

    def test_the_lines_name_the_leads_to_fix(self):
        report = run([lead("lead-1", opener="I wanted to reach out.")])
        text = "\n".join(copylint.report_lines(report))
        self.assertIn("REFUSED", text)
        self.assertIn("lead-1", text)
        self.assertIn("step1_without_pack_fact", text)

    def test_every_rule_has_a_sentence_a_person_can_read(self):
        report = run([lead()])
        for name, _why in copylint.RULES:
            self.assertTrue(report["rules"][name].strip(), name)


class ItSharesOneSourceOfTruthWithTheDraftLint(unittest.TestCase):

    def test_the_banned_phrases_are_the_same_object(self):
        self.assertIs(copylint.BANNED_PHRASES, lint.BANNED_PHRASES)

    def test_the_dash_rule_is_built_from_lints_punctuation(self):
        for dash in ("—", "–", "‑"):
            with self.subTest(dash=dash):
                self.assertIn(dash, lint.SUBSTITUTED_PUNCTUATION)
                self.assertTrue(copylint.DASH_RE.search("a %s b" % dash))


if __name__ == "__main__":
    unittest.main()


class TheSentenceInitialCapitalDoesNotBecomeAName(unittest.TestCase):
    """The proper-noun pattern cannot tell a name from the capitalised
    first word of a sentence, so "Your Senior Platform Engineer" is
    extracted whole. Found by this file's own clean-batch test, which is
    what a negative case is for."""

    def test_a_role_named_in_the_pack_traces_despite_the_leading_word(self):
        report = run([lead(opener="Your Senior Platform Engineer role "
                                  "caught my eye.")])
        self.assertEqual(report["offenders"]["untraceable_company_claim"], [])

    def test_and_an_invented_name_is_still_caught(self):
        """THE CONTROL. Dropping a leading token must not turn the rule
        off - an invention does not become traceable by losing a word."""
        report = run([lead(tail="Your Chief Revenue Officer Dana Meyer "
                                "mentioned it.")])
        self.assertIn("lead-1",
                      report["offenders"]["untraceable_company_claim"])
