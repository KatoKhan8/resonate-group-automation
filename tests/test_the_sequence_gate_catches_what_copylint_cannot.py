"""The sequence gate, tested against the failures it was built from.

Every message in the 2026-09-25 batch passed `copylint`, and the sequence was
still wrong. These are those sequences.
"""
import unittest

from src import copylint, sequencegate

FACTS = [
    {"text": "Huemor is a B2B digital agency that designs websites and "
             "develops digital strategies to turn visitors into qualified leads.",
     "quote": "We develop digital strategies that make your brand stand out"},
    {"text": "The agency is hiring a senior brand designer in New York.",
     "quote": "Hiring a senior brand designer"},
    {"text": "Huemor has created hundreds of websites since 2011.",
     "quote": "Since 2011, we've created hundreds of websites"},
]


def seq(**kw):
    base = {
        "company": "Huemor",
        "hypothesis": "Agencies running many short website projects often "
                      "find margin is only visible after delivery.",
        "subjects": {"A": "huemor's website work", "B": "brand designer hire",
                     "C": "last note"},
        "emails": {
            "em1": "Jeff, Huemor designs websites and digital strategies for "
                   "B2B clients. Agencies running many short projects often "
                   "find margin only shows up after delivery. Productive puts "
                   "budget against time while the project runs. Are you "
                   "tracking that live or after the fact?",
            "em2": "Hiring a senior brand designer usually means resourcing "
                   "gets tighter before it gets easier. Who decides which "
                   "project they land on first?",
            "em3": "A quick note on how the budget view works in practice. "
                   "Hours book against a quote, and the burn is visible "
                   "daily. Useful if I sent an example?",
            "em4": "One benchmark worth knowing: most agencies discover "
                   "overruns at invoicing. Reviewing weekly changes that.",
            "em5": "Closing the loop here. Happy to leave it if the timing "
                   "is wrong.",
        },
        "linkedin": {
            "connect": "saw the senior brand designer role, nice team page",
            "msg1": "Hi Jeff, I am Bernarda at Productive. We help agencies "
                    "see project margin while work is running. When a "
                    "website project runs past its estimate, how early does "
                    "that reach whoever is resourcing?",
            "msg2": "Hi Jeff, budget against booked time in one view. I also "
                    "wrote by email about this. Worth a look?",
            "msg3": "Hi Jeff, leaving it here. Door open.",
        },
        "ps": {"em1": "P.S. the Hue-Crew naming made me smile.",
               "em3": "P.S. resource planning is the piece most agencies "
                      "bolt on last."},
        "qualification": "QUALIFIED_RICH",
    }
    base.update(kw)
    return base


class TheGateCatchesWhatCopylintCannot(unittest.TestCase):

    def _check(self, s, **kw):
        return sequencegate.check(
            s, facts=FACTS, capability="margin per project while it is running",
            qualification=s.get("qualification"), **kw)

    def test_a_good_sequence_passes(self):
        r = self._check(seq())
        self.assertTrue(r["passed"], r["failures"])

    def test_a_follow_up_that_repeats_an_earlier_argument_fails(self):
        # THE ACTUAL DEFECT: five emails, one argument, five phrasings.
        s = seq()
        s["emails"]["em4"] = (
            "Agencies running many short projects often find margin only "
            "shows up after delivery. Productive puts budget against time "
            "while the project runs. Tracking that live or after the fact?")
        r = self._check(s)
        self.assertFalse(r["passed"])
        f = [x for x in r["failures"] if x["check"] == "followup_adds_value"]
        self.assertTrue(f)
        self.assertEqual(f[0]["step"], "em4")
        self.assertIn("em1", f[0]["why"])

    def test_every_message_passes_copylint_while_the_sequence_fails(self):
        # The whole reason this module exists.
        s = seq()
        s["emails"]["em4"] = s["emails"]["em1"]
        lead = {"id": "huemor",
                "steps": [{"subject": "huemor's website work", "body": b}
                          for b in s["emails"].values()],
                "pack": {"facts": [{"snippet": f["quote"]} for f in FACTS]}}
        lint = copylint.check_batch([lead])
        self.assertFalse(lint["refused"], "copylint should be content here")
        self.assertFalse(self._check(s)["passed"],
                         "the sequence gate must not be")

    def test_linkedin_asking_the_email_question_fails(self):
        s = seq()
        s["linkedin"]["msg1"] = (
            "Hi Jeff, are you tracking that live or after the fact?")
        r = self._check(s)
        f = [x for x in r["failures"] if x["check"] == "channels_complement"]
        self.assertTrue(f)
        self.assertEqual(f[0]["step"], "msg1")

    def test_a_hypothesis_stated_as_a_finding_fails(self):
        s = seq()
        s["emails"]["em1"] = ("Jeff, you are losing margin on fixed fee work "
                              "and it shows up at invoicing.")
        r = self._check(s)
        f = [x for x in r["failures"] if x["check"] == "hypothesis_not_asserted"]
        self.assertTrue(f)
        self.assertEqual(f[0]["step"], "em1")

    def test_an_over_long_first_email_fails(self):
        s = seq()
        s["emails"]["em1"] = " ".join(["margin visibility matters here"] * 40)
        r = self._check(s)
        self.assertTrue([x for x in r["failures"] if x["check"] == "em1_concise"])

    def test_an_email_1_that_names_no_researched_fact_fails(self):
        s = seq()
        s["emails"]["em1"] = ("Hello, many organisations wrestle with "
                              "operational reporting. Open to a chat?")
        r = self._check(s)
        self.assertTrue([x for x in r["failures"]
                         if x["check"] == "reason_for_outreach"])

    def test_duplicate_thread_subjects_fail(self):
        s = seq()
        s["subjects"]["B"] = s["subjects"]["A"]
        r = self._check(s)
        self.assertTrue([x for x in r["failures"]
                         if x["check"] == "no_repetition"])

    def test_an_unqualified_lead_fails_before_anything_else(self):
        r = self._check(seq(qualification="UNQUALIFIED"))
        self.assertFalse(r["passed"])
        self.assertTrue([x for x in r["failures"] if x["check"] == "qualified"])

    def test_one_capability_across_a_whole_batch_fails(self):
        # Stage D exists because profitability was the answer every time.
        # One sequence cannot show that. A batch can.
        r = self._check(seq(), batch_capabilities=["profitability"] * 8)
        f = [x for x in r["failures"] if x["step"] == "batch"]
        self.assertTrue(f)
        self.assertIn("defaulting", f[0]["why"])

    def test_a_varied_batch_passes(self):
        r = self._check(seq(), batch_capabilities=[
            "profitability", "resource_planning", "billing",
            "budgeting", "time_tracking"])
        self.assertTrue(r["passed"], r["failures"])

    def test_a_failure_names_the_step_so_one_message_is_rewritten(self):
        s = seq()
        s["emails"]["em4"] = s["emails"]["em2"]
        r = self._check(s)
        for f in r["failures"]:
            self.assertIn("step", f)
            self.assertTrue(f["step"])
            self.assertTrue(f["why"])


if __name__ == "__main__":
    unittest.main()


class TheGateDidNotCatchTheseUntilGLMLooked(unittest.TestCase):
    """Four defects GLM found in this module on 2026-09-26.

    Every one was then reproduced against the merged code before being fixed.
    The first version of this suite missed all four because its repetition
    test used a VERBATIM copy - a case lexical overlap catches trivially. It
    was a test built to pass rather than to probe.
    """

    def test_an_empty_sequence_is_refused_not_passed(self):
        # `check({})` returned passed=True. A gate that approves an empty
        # sequence approves anything a caller forgets to hand it, and the
        # likeliest way to hand it nothing is a key mismatch upstream.
        r = sequencegate.check({})
        self.assertFalse(r["passed"])
        self.assertTrue([f for f in r["failures"] if f["check"] == "has_content"])

    def test_insufficient_data_does_not_sail_through(self):
        # The tuple was ("UNQUALIFIED", "INSUFFICIENT") and this codebase's
        # own sentinel is INSUFFICIENT_DATA, which is not equal to either.
        # The one value most likely to arrive passed the check meant to stop it.
        r = sequencegate.check({"emails": {"em1": "x"}},
                               qualification="INSUFFICIENT_DATA")
        self.assertFalse(r["passed"])
        self.assertTrue([f for f in r["failures"] if f["check"] == "qualified"])

    def test_a_missing_qualification_is_refused_rather_than_assumed(self):
        r = sequencegate.check({"emails": {"em1": "x"}}, qualification=None)
        self.assertFalse(r["passed"])

    def test_three_letter_industry_terms_are_not_dropped(self):
        # At {3,} the pattern needed four letters, so CRM, PPC, SEO and ads
        # all vanished - in a market that talks about little else.
        words = sequencegate._content_words("CRM PPC SEO ads")
        self.assertEqual(words, {"crm", "ppc", "seo", "ads"})

    def test_the_paraphrase_blind_spot_is_reported_not_silent(self):
        # The check CANNOT see two steps arguing the same thing in different
        # words: overlap 0.125 against a 0.45 threshold, measured. Lexical
        # overlap stays because it is free and deterministic, but a caller
        # must not read a pass as "these five messages make five arguments".
        a = "Your margins are thin on fixed scope work and nobody sees it."
        b = "Profit on flat fee projects gets squeezed, invisible until later."
        self.assertLess(sequencegate.overlap(a, b), 0.45)
        r = sequencegate.check({"emails": {"em1": a, "em2": b}},
                               qualification="QUALIFIED_RICH")
        self.assertTrue([w for w in r["warnings"]
                         if "Semantic repetition is NOT verified" in w["why"]])

    def test_the_batch_check_is_case_folded(self):
        # One lead tagged "Profitability" among nineteen "profitability" made
        # distinct == 2, and the check passed while stage D plainly defaulted.
        caps = ["profitability"] * 19 + ["Profitability"]
        r = sequencegate.check({"emails": {"em1": "x"}},
                               qualification="QUALIFIED_RICH",
                               batch_capabilities=caps)
        self.assertTrue([f for f in r["failures"] if f["step"] == "batch"])

    def test_an_absent_batch_check_says_so(self):
        # batch_capabilities defaults to None, which disables the check this
        # module's own comment calls the most important one.
        r = sequencegate.check({"emails": {"em1": "x"}},
                               qualification="QUALIFIED_RICH")
        self.assertTrue([w for w in r["warnings"] if "NOT checked" in w["why"]])
