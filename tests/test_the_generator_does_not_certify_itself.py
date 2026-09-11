#!/usr/bin/env python3
"""A model may not write the evidence its own claims are checked against.

REPRODUCED on 2026-09-11, the day a real model was wired in - which is what
turned this from dormant into live.

`check_hook` asked whether ANY single five-letter word of a hook appeared
anywhere in the record's facts. The company name is always one of those facts,
so every hook that mentioned the company was "checkable". All three of these
were ACCEPTED against a record holding an industry and a headcount and nothing
else:

    "<Company> raised a Series B and opened a Vienna office."
    "<Company> lost its largest retainer last month."
    "The design agency has stopped tracking time entirely."

Then the loop closed. `generate.hook` stores the hook on the record, and
`claims.support_text` read `rec["hook"]` back as support:

    claim "You are rebuilding utilisation reporting by hand."
      without the hook   REFUSED
      with the hook      PASS

The model invented it, a no-op check certified it, and the certification was
what the claim checker consulted.

`llm.traceable`'s own docstring describes this exact defect, names that same
Series B example, and says it was closed. It WAS closed - for `check_evidence`,
one function over, while `check_hook` kept the old shape. A fix applied to one
of two callers is the thing this file exists to stop happening again.

Both halves are cut: `check_hook` uses `traceable`, and `support_text` no longer
reads the hook. The rule is not how trustworthy the text reads - it is who wrote
it. Providers and research write support; generators do not.
"""
import unittest

from src import claims, llm


def a_record(**over):
    rec = {"id": "kw", "client": "productive", "lane": "cold",
           "company": "Kestrel Wharf Studio", "domain": "kestrelwharf.test",
           "company_facts": {"industry": "design agency", "employees": 48},
           "contacts": [{"key": "c1", "name": "Dana Oyelaran",
                         "title": "Operations Director"}]}
    rec.update(over)
    return rec


class AnInventedHookIsRefused(unittest.TestCase):

    INVENTED = (
        "Kestrel Wharf Studio raised a Series B and opened a Vienna office.",
        "Kestrel Wharf Studio lost its largest retainer last month.",
        "They are rebuilding their utilisation reporting after the expansion.",
        "The design agency has stopped tracking time entirely.",
        "Packaging design revenue has doubled since the merger.",
    )

    def test_each_one(self):
        for hook in self.INVENTED:
            with self.subTest(hook=hook[:40]):
                with self.assertRaises(llm.SchemaError):
                    llm.check_hook(hook, a_record())

    def test_naming_the_company_is_not_a_fact_about_them(self):
        """The whole mechanism of the old hole, in one assertion."""
        with self.assertRaises(llm.SchemaError):
            llm.check_hook("Kestrel Wharf Studio is hiring four delivery leads",
                           a_record())

    def test_the_refusal_says_why(self):
        with self.assertRaises(llm.SchemaError) as caught:
            llm.check_hook("Kestrel Wharf Studio raised a Series B", a_record())
        self.assertIn("traceable", str(caught.exception))

    def test_an_empty_hook_is_still_refused_for_its_own_reason(self):
        with self.assertRaises(llm.SchemaError) as caught:
            llm.check_hook("a b c", a_record())
        self.assertIn("nothing specific", str(caught.exception))


class AGroundedHookStillPasses(unittest.TestCase):
    """A guard that refuses every hook is an outage, not a guard."""

    def test_a_hook_the_research_supports(self):
        rec = a_record(research=[
            {"fact": "Kestrel Wharf Studio runs delivery across three studios "
                     "and publishes its resourcing model"}])
        hook = "Kestrel Wharf Studio runs delivery across three studios"
        self.assertEqual(llm.check_hook(hook, rec), hook)

    def test_a_hook_from_a_stored_signal(self):
        rec = a_record(signal="they published a resourcing playbook in June")
        hook = "they published a resourcing playbook in June"
        self.assertEqual(llm.check_hook(hook, rec), hook)


class TheHookIsNotSupport(unittest.TestCase):

    SENTENCE = "You are rebuilding utilisation reporting by hand."

    def test_a_hook_cannot_license_a_claim(self):
        rec = a_record(hook="Kestrel Wharf Studio lost its largest retainer "
                            "and is rebuilding utilisation reporting by hand.")
        self.assertTrue(claims.check(self.SENTENCE, rec, rec["contacts"][0]),
                        "a generated hook was read as evidence")

    def test_it_is_refused_with_or_without_the_hook(self):
        """The point: the verdict must not depend on generated prose."""
        bare = claims.check(self.SENTENCE, a_record(), a_record()["contacts"][0])
        rec = a_record(hook="rebuilding utilisation reporting by hand")
        withit = claims.check(self.SENTENCE, rec, rec["contacts"][0])
        self.assertTrue(bare)
        self.assertTrue(withit)

    def test_the_hook_is_absent_from_the_support_blob(self):
        rec = a_record(hook="something the model wrote about utilisation")
        support = claims.support_text(rec, rec["contacts"][0])
        self.assertNotIn("something the model wrote", support)

    def test_research_is_still_support(self):
        """The line is who wrote it, not how it reads. A provider fact and a
        researched page still license what they actually say."""
        rec = a_record(research=[
            {"fact": "Kestrel Wharf Studio opened an office in Vienna"}])
        support = claims.support_text(rec, rec["contacts"][0])
        self.assertIn("vienna", support)
        self.assertEqual(
            claims.check("You opened an office in Vienna.", rec,
                         rec["contacts"][0]), [])


class TheTwoCheckersAgree(unittest.TestCase):
    """`check_hook` and `check_evidence` answer the same question about the
    same record, so they must not answer it differently. They did."""

    INVENTED = "Kestrel Wharf Studio raised a Series B in March"

    def test_neither_accepts_the_same_invention(self):
        rec = a_record()
        with self.assertRaises(llm.SchemaError):
            llm.check_hook(self.INVENTED, rec)
        with self.assertRaises(llm.SchemaError):
            llm.check_evidence([self.INVENTED], rec)


class ARetryCannotLaunderTheFirstAttempt(unittest.TestCase):
    """`llm.fact_strings` listed `hook` among the record's facts, so once the
    first hook was stored the record "held" it and the second attempt was
    checked against the first attempt's invention. Measured on 2026-09-11:

        "Kestrel Wharf Studio opened a Vienna office"
          against a fresh record                        REFUSED
          against a record holding the earlier hook     ACCEPTED

    Which is the whole defect wearing a different hat: regeneration is the
    ordinary path, not an edge case, because a refused hook is retried."""

    FIRST = ("Kestrel Wharf Studio raised a Series B and opened a "
             "Vienna office.")
    RETRY = "Kestrel Wharf Studio opened a Vienna office"

    def test_the_stored_hook_is_not_a_fact(self):
        with self.assertRaises(llm.SchemaError):
            llm.check_hook(self.RETRY, a_record(hook=self.FIRST))

    def test_the_verdict_does_not_move_when_a_hook_is_stored(self):
        for hook in (None, self.FIRST, "anything at all about utilisation"):
            with self.subTest(stored=str(hook)[:30]):
                rec = a_record() if hook is None else a_record(hook=hook)
                with self.assertRaises(llm.SchemaError):
                    llm.check_hook(self.RETRY, rec)

    def test_research_is_still_reachable_from_the_hook_checker(self):
        """Removing the hook must not take the real evidence with it."""
        rec = a_record(hook=self.FIRST, research=[
            {"fact": "Kestrel Wharf Studio opened a Vienna office in June",
             "url": "https://kw.test/news", "source_type": "news"}])
        self.assertEqual(llm.check_hook(self.RETRY, rec), self.RETRY)

    def test_the_bookkeeping_on_a_research_entry_is_not_a_fact(self):
        rec = a_record(research=[
            {"fact": "Kestrel Wharf Studio publishes its resourcing model",
             "url": "https://kw.test/news", "source_type": "news",
             "provider": "apify", "persona": "operations"}])
        for hook in ("Kestrel Wharf Studio is in the news",
                     "Kestrel Wharf Studio hired an operations lead"):
            with self.subTest(hook=hook[:40]):
                with self.assertRaises(llm.SchemaError):
                    llm.check_hook(hook, rec)


class AFactLicensesOnlyWhatItSays(unittest.TestCase):
    """`traceable` measured CHARACTERS: `len(fact) >= 0.5 * len(claim)`, so a
    fact licensed an invention up to its own length and the longer a company's
    name the more room it bought. Measured on 2026-09-11 with a twenty-
    character name: "<Company> raised a Series B" (38 chars) was TRACEABLE,
    while the longer spelling of the same invention was refused. The rule is
    now every content word, which does not care how long anything is."""

    FACTS = ("kestrel wharf studio", "design agency", "48")

    def test_length_does_not_buy_licence(self):
        for claim in ("Kestrel Wharf Studio raised a Series B",
                      "Kestrel Wharf Studio raised a Series B in March",
                      "Kestrel Wharf Studio hired"):
            with self.subTest(claim=claim[:40]):
                self.assertFalse(llm.traceable(claim, self.FACTS))

    def test_a_longer_company_name_buys_no_more_room(self):
        short = ("kw", "design agency")
        longer = ("kestrel wharf studio and partners limited", "design agency")
        self.assertFalse(llm.traceable("kw raised a Series B", short))
        self.assertFalse(llm.traceable(
            "Kestrel Wharf Studio and Partners Limited raised a Series B",
            longer))

    def test_what_the_facts_do_say_is_still_traceable(self):
        self.assertTrue(llm.traceable("a design agency", self.FACTS))
        self.assertTrue(llm.traceable("Kestrel Wharf Studio", self.FACTS))

    def test_a_number_nobody_recorded_is_refused(self):
        self.assertFalse(llm.traceable("a design agency of 120", self.FACTS))


class APageIsNotAVocabulary(unittest.TestCase):
    """Scraped research is support, and it is also 12,000 characters of words.

    Adding `research` to `fact_strings` made the checkers able to see the
    record's real evidence - and made every word on a scraped page available
    for reassembly. Measured on 2026-09-11 against a real record, before this
    was closed, all of these were ACCEPTED, and the second is the shape that
    `cadence.template_vars` prints verbatim as the first line of the day-5
    email. A fact must account for how the claim is WORDED, not merely donate
    vocabulary to it."""

    PAGE = ("we are a design studio in dublin. our project management and "
            "production teams work across brand, digital and packaging. we "
            "are hiring a senior designer. the design team ships work for "
            "clients across europe every year.")

    def rec(self):
        return a_record(research=[{"fact": self.PAGE}])

    def test_words_cannot_be_recombined_into_a_new_claim(self):
        for hook in (
                "Kestrel Wharf Studio has been hiring project managers "
                "across the design team this year",
                "Kestrel Wharf Studio is hiring for project management and "
                "production roles right now",
                "the design team is hiring across production and project "
                "management"):
            with self.subTest(hook=hook[:44]):
                with self.assertRaises(llm.SchemaError):
                    llm.check_hook(hook, self.rec())

    def test_what_the_page_actually_says_is_still_traceable(self):
        """The page is evidence. It licenses what it says, in its words."""
        hook = "our project management and production teams work across brand"
        self.assertEqual(llm.check_hook(hook, self.rec()), hook)

    def test_two_facts_cannot_be_stitched_together(self):
        facts = ("kestrel wharf studio opened an office in dublin",
                 "the studio is hiring a senior designer")
        self.assertFalse(llm.traceable(
            "kestrel wharf studio is hiring in dublin", facts))
        self.assertTrue(llm.traceable(
            "the studio is hiring a senior designer", facts))

    def test_the_evidence_checker_refuses_it_too(self):
        """`check_evidence` is the path that writes onto the record, and what
        it certifies is printed to a person. Same rule, same answer."""
        with self.assertRaises(llm.SchemaError):
            llm.check_evidence(
                ["Kestrel Wharf Studio is hiring for project management and "
                 "production roles right now"], self.rec())


if __name__ == "__main__":
    unittest.main()
