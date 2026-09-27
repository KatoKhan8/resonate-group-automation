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


# -------------------------------------------------- TASK-378: three rules blind to half the copy
#
# Finding 1: untraceable, buzzwords and finality only saw email bodies.
# A LinkedIn connect note or P.S. line fabricating a claim passed silently.
#
# Finding 2: _body didn't read email_body, so provider-shaped rows made
# every body read as "" and every lead fire empty_step.


class LinkedInAndPSTextIsCheckedByEveryRule(unittest.TestCase):
    """TASK-378 Finding 1: the three rules that only saw `whole` (email
    bodies) now see `rendered` — everything the prospect reads."""

    def _lead_with_linkedin(self, li_text):
        """A clean lead with a LinkedIn connect note."""
        return {
            "id": "li-lead",
            "steps": [{"body": OPENER},
                      {"body": "Step 2 body, long enough to be real."},
                      {"body": "Step 3 body, long enough to be real."},
                      {"body": "Step 4 body, long enough to be real."},
                      {"body": "Step 5 body, long enough to be real."}],
            "linkedin": {"connect": li_text},
        }

    def _lead_with_ps(self, ps_text):
        """A clean lead with a P.S. line."""
        return {
            "id": "ps-lead",
            "steps": [{"body": OPENER},
                      {"body": "Step 2 body, long enough to be real."},
                      {"body": "Step 3 body, long enough to be real."},
                      {"body": "Step 4 body, long enough to be real."},
                      {"body": "Step 5 body, long enough to be real."}],
            "ps": {"line1": ps_text},
        }

    def test_untraceable_sees_linkedin_claims(self):
        """A LinkedIn note fabricating a figure is refused."""
        report = run([self._lead_with_linkedin(
            "Saw your $120M raise and 40% headcount jump."
        )])
        self.assertTrue(report["refused"])
        self.assertIn("li-lead",
                      report["offenders"]["untraceable_company_claim"])

    def test_untraceable_sees_ps_claims(self):
        """A P.S. line fabricating a figure is refused."""
        report = run([self._lead_with_ps(
            "P.S. They announced a $50M round in June."
        )])
        self.assertTrue(report["refused"])
        self.assertIn("ps-lead",
                      report["offenders"]["untraceable_company_claim"])

    def test_buzzwords_see_linkedin_text(self):
        """A LinkedIn note with a buzzword is refused."""
        report = run([self._lead_with_linkedin(
            "Let's leverage our synergies together."
        )])
        self.assertTrue(report["refused"])
        self.assertIn("li-lead", report["offenders"]["buzzword"])

    def test_buzzwords_see_ps_text(self):
        """A P.S. line with a buzzword is refused."""
        report = run([self._lead_with_ps(
            "P.S. We offer a seamless, best-in-class solution."
        )])
        self.assertTrue(report["refused"])
        self.assertIn("ps-lead", report["offenders"]["buzzword"])

    def test_finality_sees_linkedin_text(self):
        """A LinkedIn message claiming finality while more follow is refused."""
        report = run([{
            "id": "fin-li",
            "steps": [{"body": OPENER},
                      {"body": "Step 2 body, long enough to be real."},
                      {"body": "Step 3 body, long enough to be real."},
                      {"body": "Step 4 body, long enough to be real."},
                      {"body": "Step 5 body, long enough to be real."}],
            "linkedin": {"follow_up_1": "This will be my last message."},
        }])
        self.assertTrue(report["refused"])
        self.assertIn("fin-li",
                      report["offenders"]["finality_before_last_step"])

    def test_finality_still_exempt_on_last_email_body(self):
        """The last email body may say it is the last. The exemption holds."""
        report = run([{
            "id": "fin-ok",
            "steps": [{"body": OPENER},
                      {"body": "Step 2 body, long enough to be real."},
                      {"body": "Step 3 body, long enough to be real."},
                      {"body": "Step 4 body, long enough to be real."},
                      {"body": "This is my last note. Best of luck."}],
        }])
        self.assertEqual(report["offenders"]["finality_before_last_step"], [])

    def test_clean_linkedin_note_does_not_refuse(self):
        """A LinkedIn note with no claims, buzzwords or finality passes."""
        report = run([self._lead_with_linkedin(
            "Hi, noticed your work in Berlin. Would love to connect."
        )])
        self.assertFalse(report["refused"])


class ProviderShapedRowsAreReadCorrectly(unittest.TestCase):
    """TASK-378 Finding 2: _body reads email_body the same way _subject
    reads email_subject. Provider sequence rows carry email_subject/email_body
    and nothing else."""

    def _provider_lead(self, ident="prov-1", opener=OPENER, tail=""):
        bodies = [opener + (" " + tail if tail else "")]
        bodies += ["Step %d body, long enough to be real." % n
                   for n in range(2, 6)]
        return {
            "id": ident,
            "steps": [
                {"email_subject": "Subject %d" % (i+1), "email_body": b}
                for i, b in enumerate(bodies)
            ],
        }

    def test_email_body_is_read_as_body(self):
        """A lead with only email_subject/email_body fields is linted."""
        report = run([self._provider_lead()])
        self.assertEqual(report["offenders"]["empty_step"], [],
                         "email_body must be read as a body, not as empty")

    def test_a_real_violation_in_email_body_still_refuses(self):
        """A buzzword in an email_body field is still caught."""
        report = run([self._provider_lead(tail="We can unlock seamless "
                                               "synergy.")])
        self.assertTrue(report["refused"])
        self.assertIn("prov-1", report["offenders"]["buzzword"])

    def test_a_clean_provider_shaped_batch_does_not_refuse_100_percent(self):
        """The gate that refuses everything is worse than no gate."""
        batch = [self._provider_lead("prov-1"),
                 self._provider_lead("prov-2",
                                     opener="Your Senior Platform Engineer "
                                            "role caught my eye.")]
        report = run(batch)
        self.assertFalse(report["refused"])
        self.assertEqual(report["clean"], 2)

    def test_empty_email_body_is_still_caught(self):
        """An actually-empty email_body fires empty_step."""
        lead = self._provider_lead()
        lead["steps"][2]["email_body"] = ""
        report = run([lead])
        self.assertIn("prov-1", report["offenders"]["empty_step"])


class CompanyClaimCatchesMoreTriggers(unittest.TestCase):
    """TASK-378: COMPANY_CLAIM missed claims with no trigger word like
    'Acme closed a $40M round'. Adding 'closed' closes that gap."""

    def test_closed_is_a_trigger_word(self):
        report = run([lead(tail="You closed a $40M round in March.")])
        self.assertIn("lead-1",
                      report["offenders"]["untraceable_company_claim"])

    def test_closed_with_a_supported_figure_passes(self):
        """If the pack mentions the figure, it traces."""
        pack = {"facts": [
            {"kind": "news", "snippet": "Acme closed a $40M round in March.",
             "source_url": "https://example.com/1",
             "published_at": "2026-03-15"},
        ]}
        report = copylint.check_batch(
            [lead(tail="You closed a $40M round in March.")],
            packs={"lead-1": pack},
        )
        self.assertEqual(report["offenders"]["untraceable_company_claim"], [])


class SingleDigitSpecificsAreExtracted(unittest.TestCase):
    """TASK-378: the specifics regex required 2+ digits, so '8 of your posts'
    was never extracted. Changing {1,} to * catches single-digit inventions."""

    def test_single_digit_in_company_claim_is_extracted(self):
        report = run([lead(tail="You posted 8 articles last month.")])
        self.assertIn("lead-1",
                      report["offenders"]["untraceable_company_claim"])

    def test_single_digit_supported_by_pack_passes(self):
        pack = {"facts": [
            {"kind": "post", "snippet": "We posted 8 articles last month.",
             "source_url": "https://example.com/1",
             "published_at": "2026-09-01"},
        ]}
        report = copylint.check_batch(
            [lead(tail="You posted 8 articles last month.")],
            packs={"lead-1": pack},
        )
        self.assertEqual(report["offenders"]["untraceable_company_claim"], [])


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
