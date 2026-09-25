"""GATE 3, against the chrome that actually shipped.

Every CHROME fixture below has the shape of a span read off the real
400-character research-pack cache or off the sixty-four emails that went to
real prospects on 2026-09-25. Nothing is invented: a fixture somebody wrote
to match the gate proves only that they can write one.

WHERE A CRAWLED COMPANY'S NAME APPEARED IT HAS BEEN REPLACED with a
same-shaped placeholder, and only the name. These files are committed;
`work/` is not, and the crawl cache is a client's prospect pool. The rules
under test are about the SHAPE of a span - terminator, subject, verb,
capitalisation run - so swapping one proper noun for another of the same
shape costs the fixture nothing and keeps a prospect list out of git.

The last class in this file is what makes the rest mean anything:
`SINGLE_RULE` holds, for every rule, a real span that THAT RULE ALONE
refuses. Remove the rule and the span walks through. A guard nobody has
watched fail may already be inert.
"""
import unittest

from src import packfact


#: REAL NAVIGATION CHROME, whole.
CHROME = (
    # The exact span that shipped, in an email a real person received.
    "check out a few of our case studies",
    "request a demo error: contact form not found",
    "please allow me to introduce myself, the agency and our mission",
    "how we build and grow beauty brands",
    "three ways we create momentum for healthcare brands",
    "because that is what makes good video",
    "smart marketing, strategic events, and",
    # Menus, whole, as the crawler returns them.
    "Skip to content Main Menu Online Digital Retail Video Conference",
    "Services Engagements Domains About Contact us",
    "Home Solutions Expenses Invoices Presentations Sign-Up & Pricing",
    "Meet us in Cologne August 26-30, 2026 Book a Meeting For Business For CEO",
    "Problems We Solve Into Through Out Who We Are Our Company Our Team",
    "Products Swap API EVM Embed swaps in your app Solana Powerful swaps",
    # The language switcher that shipped inside a quoted line.
    "content back to homepage investors/shareholders en fr",
    # A call to action with a verb, which is the case "has a verb" misses.
    "Book a Meeting For Startup Founders",
    "Get started with a free trial today",
    # The truncation the 400-character cap produces, mid-word.
    "Sidera is a specialist IT services company focused on Oracl",
    "The platform for compliant wor",
    # A menu running straight into a sentence.
    "The Coca-Cola Company Coca-Cola is a global brand with a presence in "
    "over 200 countries.",
    "Platform Meeting Operations Where governance moves from discussion to "
    "decisive action.",
)

#: REAL BODY PROSE from the same cache. These must pass, or the gate holds
#: everything and nothing ever sends - which is a different way of being
#: useless, and the way a gate gets deleted.
PROSE = (
    "We believe in a world where everyone gets the good seats.",
    "We take the pain of R&M off the menu so operators can focus on their "
    "businesses and serving guests.",
    "Advent turns your selling process from hours to minutes.",
    "Agilis was built by and for chemical industry leaders.",
    "Airia gives enterprises complete visibility, real-time enforcement, "
    "and continuous governance across every model, agent, and tool in your "
    "environment.",
    "The buyer journey used to unfold across touchpoints you could "
    "optimize one by one.",
    # Two the first draft of this module refused, and must not.
    "We're one flat, integrated team of product professionals in nine "
    "countries.",
    "Since 2006, we have helped ambitious organizations find the right "
    "thing to build, and then build it.",
    "Each one is real software in production, told through the problem it "
    "solved and the numbers it moved.",
)

#: ONE REAL SPAN PER RULE, refused by THAT RULE AND NOTHING ELSE. Found by
#: walking the 16,743-row cache and keeping spans where exactly one rule
#: fired, so these are evidence rather than construction.
SINGLE_RULE = {
    "terminator":
        "Our pioneering platform is built around providers, powered",
    "length":
        "The hype is loud.",
    "subordinator":
        "So the next generation of technicians can outperform the last.",
    "declarative":
        "see more Maintenance coordination that answers to you.",
    "nav_marker":
        "Skip to main content Skip to footer Autotarget is live!",
    "nav_glyph":
        "Details → Watch this space — an announcement is coming.",
    "language_switcher":
        "en es an international TEAM Working to take programmatic DOOH "
        "advertising into a new era.",
    "title_case":
        "We Have the Highest in the Industry.",
    "capitalised_run":
        "The Coca-Cola Company Coca-Cola is a global brand with a presence "
        "in over 200 countries.",
}

#: A whole cached fact, at the 400-character cap, exactly as the crawler
#: stores one: menu first, one real sentence in the middle, cut mid-word.
CACHED_FACT = {
    "fact_id": "deadbeefdeadbeef",
    "kind": "site_page",
    "source_url": "https://example.test/",
    "snippet": (
        "Services Engagements Domains About Contact us OVER TWO DECADES OF "
        "ORACLE DNA Evolving with Technology. We solve the complexities of "
        "enterprise Oracle environments. Request a 2-Week AI Pilot Analyze "
        "My OCI Costs Trusted by Leading Brands Across Industries Build "
        "Modern Oracle Solutions with Confidence Sidera is a specialist "
        "IT services company focused on Oracl"),
}


class NavigationIsNotAFact(unittest.TestCase):

    def test_every_piece_of_real_chrome_is_refused(self):
        for span in CHROME:
            with self.subTest(span=span[:50]):
                self.assertFalse(
                    packfact.is_body_sentence(span),
                    "this is navigation chrome and the gate accepted it")

    def test_real_body_prose_is_accepted(self):
        for span in PROSE:
            with self.subTest(span=span[:50]):
                self.assertTrue(
                    packfact.is_body_sentence(span),
                    "real prose was refused: %s"
                    % packfact.reasons_against(span))

    def test_a_verb_alone_does_not_make_a_sentence(self):
        # The distinction the whole module turns on. Both have a verb.
        self.assertFalse(packfact.is_body_sentence(
            "Check out a few of our case studies."))
        self.assertTrue(packfact.is_body_sentence(
            "We check every one of our case studies before we publish it."))

    def test_the_cap_truncation_is_refused_even_when_it_reads_like_prose(self):
        cut = "Sidera is a specialist IT services company focused on Oracl"
        self.assertIn("no terminal punctuation",
                      " ".join(packfact.reasons_against(cut)))

    def test_one_real_sentence_is_found_inside_a_whole_cached_fact(self):
        self.assertEqual(
            packfact.quotable(CACHED_FACT),
            ["We solve the complexities of enterprise Oracle environments."],
            "the gate should find the one body sentence and no menu item")


class AbsenceIsNotAPass(unittest.TestCase):
    """The shape lane S found an hour before this was written: a gate that
    passes because the field it reads is absent."""

    def test_a_span_with_no_fact_is_refused_not_excused(self):
        verdict = packfact.check_span("We solve the complexities of "
                                      "enterprise Oracle environments.", None)
        self.assertFalse(verdict["ok"])
        self.assertIn("names no pack fact", " ".join(verdict["reasons"]))

    def test_a_fact_with_no_source_url_yields_nothing_quotable(self):
        self.assertEqual(packfact.quotable(dict(CACHED_FACT, source_url="")), [])

    def test_a_span_not_in_the_snippet_is_refused(self):
        verdict = packfact.check_span(
            "We have been building software since 1998.", CACHED_FACT)
        self.assertFalse(verdict["ok"])
        self.assertIn("not read off that page", " ".join(verdict["reasons"]))

    def test_a_count_of_facts_is_not_a_list_of_facts(self):
        # `work/researchpack-us-cohort-2026-09-25.jsonl` carries
        # `"facts": 3` and sits beside three files that carry the real list.
        self.assertEqual(packfact.facts_of({"facts": 3}), [])
        with self.assertRaises(packfact.Held):
            packfact.choose({"facts": 3})

    def test_a_pack_with_nothing_quotable_is_held_never_made_generic(self):
        pack = {"facts": [dict(CACHED_FACT,
                               snippet="Home About Services Contact us")]}
        with self.assertRaises(packfact.Held):
            packfact.choose(pack)


class EveryRuleIsLoadBearing(unittest.TestCase):
    """Remove each guard and prove real chrome walks through the hole.

    CLAUDE.md: "when you break a guard deliberately, confirm that the
    intended test failed, that it failed for the intended reason, and that a
    different guard did not fire first." `SINGLE_RULE` is what makes the
    second half checkable - each span is refused by ONE named rule and by no
    other, so removing that rule is the only thing that can let it through.
    """

    def test_the_table_covers_every_rule(self):
        self.assertEqual(sorted(SINGLE_RULE),
                         sorted(name for name, _r in packfact.RULES),
                         "a rule was added or renamed and nothing proves it "
                         "does anything")

    def test_each_span_is_refused_by_its_own_rule_and_no_other(self):
        for name, span in sorted(SINGLE_RULE.items()):
            with self.subTest(rule=name):
                fired = [n for n, rule in packfact.RULES
                         if rule(span, packfact._words(span))]
                self.assertEqual(
                    fired, [name],
                    "this span is meant to isolate %r and %s fired"
                    % (name, fired))

    def test_removing_a_rule_lets_its_own_chrome_through(self):
        for name, span in sorted(SINGLE_RULE.items()):
            with self.subTest(rule=name):
                self.assertFalse(packfact.is_body_sentence(span))
                self.assertTrue(
                    packfact.is_body_sentence(span, skip=(name,)),
                    "rule %r can be removed and this span is still refused: "
                    "the rule is not the thing refusing it" % name)

    def test_no_rule_is_what_makes_real_prose_pass(self):
        # The other half. Prose passes with every rule on, so removing one
        # must not make it fail - if it does, a rule is inverted.
        for name, _rule in packfact.RULES:
            for span in PROSE:
                with self.subTest(rule=name, span=span[:40]):
                    self.assertTrue(
                        packfact.is_body_sentence(span, skip=(name,)))


if __name__ == "__main__":
    unittest.main()
