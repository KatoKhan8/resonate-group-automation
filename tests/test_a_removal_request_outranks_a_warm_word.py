"""Three measured safety defects in `src/replies.classify`, 2026-10-01.

Measured against live EmailBison reply rows on internal campaigns
274/327/328/352 - 432 audited rows, 899 readable tracked replies. Every
fixture below is the REAL SHAPE of a row in that corpus with the person
redacted out of it: names, addresses, phone numbers and domains are
replaced, the structure is not. A fixture invented to match a new regex
proves nothing, which is why the shapes come from the corpus and the
corpus rows stay out of git.

The three defects, each one a way for somebody who asked to be left
alone to be classified as interested:

  1. `UNSUBSCRIBE_PATTERNS` was first-person-SINGULAR only. "remove us
     from your mailing list" matched nothing, and because that sentence
     contains the word "interested", `classify` returned POSITIVE at
     0.75 on a removal request. A removal signal must DOMINATE a warm
     one, and not by luck of table order: it is decided first.

  2. `_find_quote_start` did not know the bare Outlook `From:` header
     block - no `-----Original Message-----`, no `>` prefixes, just
     `From:` / `Sent:` / `To:` / `Subject:`. 44 readable rows are in
     that shape. Reply 1538458's entire human content was "Stop" and it
     came back POSITIVE at 0.75 citing "that would be useful" - OUR OWN
     COPY, quoted back at us. No verdict may rest on evidence that only
     appears in the quoted region.

  3. Of 23 replies a human flagged `interested`, five were called
     positive and FOUR a refusal; two of those scored `unsubscribe` at
     0.95. Reply 1541331 said "If you want to set up a phone call to
     chat, we can certainly do that" and scored unsubscribe 0.95 off
     its own employer's footer - "please click here to unsubscribe" -
     plus a bare `GDPR` in the legal block. Boilerplate is not the
     human's sentence and must not drive the verdict.

The positive controls matter as much as the three failures: a genuine
unsubscribe must still be an unsubscribe and a genuine positive must
still be positive. Fixing a bias by inverting it is not a fix.
"""
import unittest

from src.replies import (ACCOUNT_DNC, NEGATIVE, POSITIVE, UNSUBSCRIBE,
                         classify, extract_prospect_text)

REMOVALS = (UNSUBSCRIBE, ACCOUNT_DNC)


# --------------------------------------------------------------- defect 1
#
# Shape of the live rows: a plural removal request. The corpus carries
# "remove us", "take us off", "our details", "no further contact" and
# "we do not wish to receive" - none of which the singular patterns read.

class TestAPluralRemovalRequestIsARemovalRequest(unittest.TestCase):

    def test_remove_us_from_your_mailing_list_beside_the_word_interested(self):
        """THE defect: the warm word won against the removal request.

        Before the fix this returned `positive` 0.75 with evidence
        ['interested'] - a removal request announced to the client as a
        buying signal.
        """
        body = ("Hi, could you remove us from your distribution list? "
                "Not something we are interested in.")
        verdict = classify(body)
        self.assertIn(verdict["classification"], REMOVALS)
        self.assertNotEqual(verdict["classification"], POSITIVE)

    def test_the_bare_plural_request_matches_at_all(self):
        """Before the fix this matched no pattern and was `unknown` 0.0."""
        verdict = classify("remove us from your mailing list")
        self.assertIn(verdict["classification"], REMOVALS)

    def test_plural_phrasings_from_the_corpus(self):
        for body in (
            "Please remove us from your mailing list.",
            "Please remove us from your database.",
            "Kindly remove our details from your records.",
            "Please unsubscribe us.",
            "Opt us out please.",
            "Stop emailing us.",
            "No further contact please.",
            "We do not wish to receive any further communication.",
            "Please delete our data.",
        ):
            with self.subTest(body=body):
                verdict = classify(body)
                self.assertIn(verdict["classification"], REMOVALS,
                              "%r read as %s" % (body,
                                                 verdict["classification"]))

    def test_the_two_shapes_found_by_regenerating_the_suppression_list(self):
        """Found 2026-10-01 by re-deriving the DNC list under the fix, not
        by reading the patterns again. Both were still `unknown` or
        `negative` after the first pass, and both are people demanding
        removal in the plainest words the corpus contains."""
        for body in (
            # The company named in brackets between the pronoun and the
            # preposition. Read as `negative` on "not interested" before.
            "Sorry, but we are not interested.\n"
            "Please remove us (Example Agency) from your contact list.",
            # Three rows whose whole human content was a demand to stop.
            "Stop the stupid spamming. Learn your systems better.",
            "Stop spam idiot",
            "Stop spamming me, that person is no longer with the company",
        ):
            with self.subTest(body=body):
                found = classify(body)["classification"]
                self.assertIn(found, REMOVALS, "%r read as %s" % (body, found))

    def test_a_sharp_question_is_still_not_a_removal_request(self):
        """The negative control for the stop-spamming pattern. The module
        removed a bare "stop" on purpose because "please stop asking" is a
        refusal, not a removal, and that must still hold."""
        self.assertEqual(classify("Please stop asking, I already said no.")
                         ["classification"], NEGATIVE)
        # "stopped" is a different word, and a sentence about spam filters
        # is a sentence about a product.
        self.assertNotIn(
            classify("We stopped using spam filters last year - how does "
                     "your tool handle that?")["classification"], REMOVALS)

    def test_removal_dominates_every_warm_sentence_bolted_onto_it(self):
        """Precedence, asserted as an effect rather than read off a table.

        A removal request keeps its verdict no matter how warm the rest
        of the message reads. This is the property that failed: the
        removal lost to a positive pattern instead of outranking it.
        """
        warm = (
            "Sounds interesting, let's talk next week.",
            "That would be useful - can we schedule a call?",
            "I'd love to hear more, send me pricing.",
            "Happy to chat, here is my calendar.",
        )
        for sentence in warm:
            body = "Please remove us from your mailing list. " + sentence
            with self.subTest(sentence=sentence):
                verdict = classify(body)
                self.assertIn(verdict["classification"], REMOVALS,
                              "%r read as %s" % (body,
                                                 verdict["classification"]))


# --------------------------------------------------------------- defect 2
#
# Shape of 44 live rows: a bare Outlook header block introducing the
# quoted thread. Reply 1538458 is this exact shape with "Stop" above it.

OUTLOOK_STOP = """Stop


[signatureImage]

A Person / Chairman and CEO

+44 20 7946 0000<tel:%20004420794600000>

1 Example Street, Suite 100, Example City, EX 00000

[LinkedIn]<https://www.linkedin.test/in/example/>

________________________________
From: Our Sender <sender@example-sending.test>
Sent: Monday, May 11, 2026 1:02:35 PM
To: A Person <person@example-prospect.test>
Subject: closing the loop

Hey,

This is my last note. I do not want to keep landing in your inbox if the
timing is not right.

I thought that would be useful for your team - still interested in a quick
chat? Can we schedule a call next week?
"""


class TestTheBareOutlookHeaderBlockIsAQuote(unittest.TestCase):

    def test_the_quote_is_recognised_as_a_quote(self):
        """Before the fix: method "no_quote", had_quote False, and the
        whole thread handed to the classifier as the prospect's words."""
        extracted = extract_prospect_text(OUTLOOK_STOP)
        self.assertTrue(extracted["had_quote"])
        self.assertNotIn("that would be useful", extracted["text"])
        self.assertNotIn("Can we schedule", extracted["text"])
        self.assertNotIn("sender@example-sending.test", extracted["text"])

    def test_a_bare_stop_under_the_header_block_is_a_stop(self):
        """Reply 1538458: human content "Stop", verdict POSITIVE 0.75."""
        verdict = classify(OUTLOOK_STOP)
        self.assertIn(verdict["classification"], REMOVALS)
        self.assertNotEqual(verdict["classification"], POSITIVE)

    def test_no_verdict_rests_on_evidence_from_the_quoted_region(self):
        """The assertion the brief asks for, stated as an invariant.

        "that would be useful" is OUR copy. Whatever this message is
        classified as, no cited evidence may come from the quoted part.
        """
        verdict = classify(OUTLOOK_STOP)
        extracted = extract_prospect_text(OUTLOOK_STOP)
        quoted = extracted["quoted"].lower()
        self.assertTrue(quoted, "nothing was identified as quoted")
        for item in verdict["evidence"]:
            self.assertNotIn(item.lower(), quoted,
                             "evidence %r came from the quoted thread" % item)
        self.assertEqual(verdict.get("evidence_from_quote"), [])

    def test_a_refusal_under_the_header_block_survives(self):
        """The other live shape: a refusal plus a removal, same block."""
        body = ("Sorry, not interested and I will not be anytime soon. "
                "Please take me off your list.\n"
                "\n"
                "A Person\n"
                "VP of Engineering\n"
                "\n"
                "From: Our Sender <sender@example-sending.test>\n"
                "Date: Thursday, May 14, 2026 at 12:07 PM\n"
                "To: A Person <person@example-prospect.test>\n"
                "Subject: how many tools are you running?\n"
                "\n"
                "Hey, interested in a quick chat? That would be useful.\n")
        verdict = classify(body)
        self.assertIn(verdict["classification"], REMOVALS)

    def test_a_human_writing_the_word_from_is_not_a_quote(self):
        """The negative control for the header shape. One `From:` with no
        header block under it is a sentence, not a quoted thread."""
        body = ("Thanks - from: your last note I gather you want a call. "
                "Happy to chat, send me some times.")
        extracted = extract_prospect_text(body)
        self.assertFalse(extracted["had_quote"])
        self.assertEqual(classify(body)["classification"], POSITIVE)


# --------------------------------------------------------------- defect 3
#
# Shape of reply 1541331: a plain acceptance, then the employer's
# signature, legal block and marketing opt-out link.

FOOTER_TEMPLATE = """Hey,

I apologize for the delay in a response. I get a relatively large volume of
emails and sometimes things slip through. {human}

[cid:image001.png@01DCE382.B59EF760]
A Person
Operations Manager
1 Example Street Suite 100 | Example City, EX 00000
C 555.000.0000
example-prospect.test<http://www.example-prospect.test/>

Unless expressly stated otherwise, the information contained in this e-mail
and any attachments is confidential and may be privileged. It is intended
for the sole use of the addressee(s). If you are not the intended recipient,
any dissemination, distribution or copying of the contents of this e-mail is
strictly prohibited. If you have received this e-mail in error, please
inform the sender immediately and delete it from your computer. Personal
data is processed in line with GDPR.

If you prefer not to receive email messages like this from Example Corp,
please click here to unsubscribe.<https://example-prospect.test/unsubscribe>
"""

#: Reply 1541331's own sentence, which is what the footer drowned out.
ACCEPTANCE = ("If you want to set up a phone call to chat, we can "
              "certainly do that.")
FOOTER_ACCEPTANCE = FOOTER_TEMPLATE.format(human=ACCEPTANCE)


class TestAFooterDoesNotClassifyTheHuman(unittest.TestCase):

    def test_a_meeting_acceptance_under_an_unsubscribe_footer_is_positive(self):
        """Reply 1541331: `unsubscribe` 0.95 off the employer's footer,
        on a reply a human had flagged interested."""
        verdict = classify(FOOTER_ACCEPTANCE)
        self.assertNotIn(verdict["classification"], REMOVALS)
        self.assertEqual(verdict["classification"], POSITIVE)

    def test_the_boilerplate_is_separated_from_the_human_content(self):
        extracted = extract_prospect_text(FOOTER_ACCEPTANCE)
        self.assertTrue(extracted["had_footer"])
        self.assertIn("set up a phone call", extracted["text"])
        self.assertNotIn("unsubscribe", extracted["text"].lower())
        self.assertNotIn("gdpr", extracted["text"].lower())
        self.assertNotIn("confidential", extracted["text"].lower())

    def test_a_refusal_under_the_same_footer_is_still_a_refusal(self):
        """Boilerplate removal must not soften a stop."""
        body = FOOTER_TEMPLATE.format(human="We are not interested, thanks.")
        self.assertEqual(classify(body)["classification"], NEGATIVE)

    def test_a_removal_request_above_the_same_footer_is_still_a_removal(self):
        body = FOOTER_TEMPLATE.format(
            human="Please remove us from your mailing list.")
        self.assertIn(classify(body)["classification"], REMOVALS)

    def test_the_footer_alone_is_not_a_removal_request(self):
        """The footer with no human sentence at all. It must not be read as
        the human asking for removal - and it must not be read as anything
        else either: nothing is left to classify, so a person looks."""
        body = FOOTER_TEMPLATE.format(human="")
        verdict = classify(body)
        self.assertNotIn(verdict["classification"], REMOVALS)


# ------------------------------------------------------- positive controls
#
# The bias must not simply be inverted. Every one of these was correct
# before the fix and has to stay correct after it.

class TestTheBiasWasNotInverted(unittest.TestCase):

    def test_a_genuine_unsubscribe_is_still_an_unsubscribe(self):
        for body in ("Please remove me from your list.",
                     "Unsubscribe.",
                     "Please unsubscribe me.",
                     "Stop",
                     "Take me off your list please.",
                     "Opt me out.",
                     "Stop emailing me.",
                     "Please do not email me again.",
                     "No more emails please."):
            with self.subTest(body=body):
                found = classify(body)["classification"]
                self.assertIn(found, REMOVALS, "%r read as %s" % (body, found))

    def test_a_genuine_positive_is_still_a_positive(self):
        for body in ("I'm interested - what does it cost?",
                     "Sounds interesting, happy to chat next week.",
                     "Yes please, send me the details.",
                     "Let's talk. Send me some times.",
                     "That would be useful, can we schedule a call?",
                     "Sure, happy to connect. Send me a deck."):
            with self.subTest(body=body):
                found = classify(body)["classification"]
                self.assertEqual(found, POSITIVE,
                                 "%r read as %s" % (body, found))

    def test_a_genuine_positive_with_a_quoted_thread_is_still_a_positive(self):
        body = ("Sounds interesting - happy to chat. Send me some times.\n"
                "\n"
                "From: Our Sender <sender@example-sending.test>\n"
                "Sent: Monday, May 11, 2026 1:02 PM\n"
                "To: A Person <person@example-prospect.test>\n"
                "Subject: quick question\n"
                "\n"
                "Hey, not interested? Please remove me if so.\n")
        verdict = classify(body)
        self.assertEqual(verdict["classification"], POSITIVE)
        self.assertEqual(verdict.get("evidence_from_quote"), [])

    def test_a_refusal_is_still_a_refusal(self):
        for body in ("Not interested, thanks.",
                     "No thanks.",
                     "We are all set.",
                     "Not a fit for us."):
            with self.subTest(body=body):
                self.assertEqual(classify(body)["classification"], NEGATIVE)

    def test_an_out_of_office_is_still_an_out_of_office(self):
        body = ("Automatic reply: I am out of office until the 14th and have "
                "limited access to email.")
        self.assertEqual(classify(body)["classification"], "out_of_office")


if __name__ == "__main__":
    unittest.main()
