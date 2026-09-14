"""TASK-029: extract the prospect's own words from a raw email body.

85% of email replies carry the quoted original message below the reply.
The classifier was matching patterns in our own outreach copy and calling
it the prospect's sentiment. These tests pin the input-fixing function
that strips the quote and signature before classification runs.

Every fixture below is invented. No corpus row enters this file.
"""
import unittest

from src.replies import extract_prospect_text, classify, REFERRAL, UNKNOWN


class TestTopPostedReply(unittest.TestCase):
    """A reply above the quoted thread: the 85% case."""

    def test_keeps_reply_drops_quote(self):
        body = (
            "Thanks for the note, not interested right now.\n"
            "\n"
            "On Mon, Sep 8, 2026 at 3:00 PM, Sender <sender@example.com> wrote:\n"
            "> Hey Prospect,\n"
            ">\n"
            "> still curious though: profitability and resourcing, solved or duct-taped?\n"
        )
        result = extract_prospect_text(body)
        self.assertIn("not interested", result["text"])
        self.assertNotIn("profitability", result["text"])
        self.assertNotIn("sender@example.com", result["text"])
        self.assertTrue(result["had_quote"])
        self.assertEqual(result["method"], "top_post")

    def test_keeps_reply_drops_gt_quoted_lines(self):
        body = (
            "We are all set thanks.\n"
            "\n"
            "> Hey,\n"
            ">\n"
            "> reaching out about your outreach tooling.\n"
            ">\n"
            "> interested in a quick chat?\n"
        )
        result = extract_prospect_text(body)
        self.assertIn("all set", result["text"])
        self.assertNotIn("reaching out", result["text"])
        self.assertNotIn("quick chat", result["text"])

    def test_outlook_separator(self):
        body = (
            "Please remove me from your list.\n"
            "\n"
            "-----Original Message-----\n"
            "From: Sender <sender@example.com>\n"
            "Sent: Thursday, September 3, 2026 6:38 PM\n"
            "To: Prospect <prospect@example.com>\n"
            "Subject: Re: Quick question\n"
            "\n"
            "Hey, still curious about this one.\n"
        )
        result = extract_prospect_text(body)
        self.assertIn("remove me", result["text"])
        self.assertNotIn("still curious", result["text"])
        self.assertNotIn("Original Message", result["text"])


class TestBottomPostedReply(unittest.TestCase):
    """A reply below the quoted thread: rare but must not be discarded."""

    def test_recovers_reply_below_quote(self):
        body = (
            "> Hey, are you still looking at this?\n"
            ">\n"
            "> reaching out about your outreach tooling.\n"
            "\n"
            "Yes, let's talk next week. Send me some times."
        )
        result = extract_prospect_text(body)
        self.assertIn("let's talk", result["text"])
        self.assertNotIn("reaching out", result["text"])
        self.assertEqual(result["method"], "bottom_post")

    def test_greeting_above_quote_does_not_block_bottom_detection(self):
        body = (
            "Hi,\n"
            "\n"
            "> Hey, circling back one more time.\n"
            ">\n"
            "> is operational visibility something you are working on?\n"
            "\n"
            "No thanks, we already have a solution."
        )
        result = extract_prospect_text(body)
        self.assertIn("already have", result["text"])
        self.assertNotIn("circling back", result["text"])
        self.assertEqual(result["method"], "bottom_post")


class TestInlineReply(unittest.TestCase):
    """An inline reply interleaved with quoted lines."""

    def test_does_not_lose_the_interleaved_answer(self):
        body = (
            "Sure, happy to chat. How about Thursday?\n"
            "\n"
            "> On Sep 5, 2026, at 10:00 AM, Sender wrote:\n"
            ">\n"
            "> Would next week work for a call?\n"
        )
        result = extract_prospect_text(body)
        self.assertIn("happy to chat", result["text"])
        self.assertIn("Thursday", result["text"])
        self.assertNotIn("Would next week", result["text"])


class TestNoQuote(unittest.TestCase):
    """A reply with no quoted thread at all."""

    def test_unchanged_byte_for_byte(self):
        body = "Not interested, thanks. Please remove me."
        result = extract_prospect_text(body)
        self.assertEqual(result["text"], body)
        self.assertFalse(result["had_quote"])
        self.assertEqual(result["method"], "no_quote")
        self.assertEqual(result["original"], body)

    def test_short_linkedin_style_reply(self):
        body = "Sure, send me some info."
        result = extract_prospect_text(body)
        self.assertEqual(result["text"], body)
        self.assertEqual(result["original_length"], len(body))
        self.assertEqual(result["stripped_length"], len(body))


class TestSignatureStripping(unittest.TestCase):
    """A signature block must not contribute to a referral verdict.

    This is the test that would have caught the 94 false referrals:
    names in the sender's signature were being read as referral targets.
    """

    def test_dash_separator_signature_removed(self):
        body = (
            "Not interested, sorry.\n"
            "-- \n"
            "Alba Kenji\n"
            "Account & Project Manager\n"
            "+44 20 7946 0000\n"
        )
        result = extract_prospect_text(body)
        self.assertIn("Not interested", result["text"])
        self.assertNotIn("Alba Kenji", result["text"])
        self.assertNotIn("Project Manager", result["text"])
        self.assertTrue(result["had_signature"])

    def test_underscore_separator_signature_removed(self):
        body = (
            "Thanks but we are all set.\n"
            "______________________________________________\n"
            "Jonas Fernhill\n"
            "Project Manager\n"
            "dana@example.com\n"
        )
        result = extract_prospect_text(body)
        self.assertIn("all set", result["text"])
        self.assertNotIn("Jonas Fernhill", result["text"])
        self.assertTrue(result["had_signature"])

    def test_signature_name_does_not_trigger_referral(self):
        """The 94 false referrals: a name in the signature matched a
        referral cue in the quoted thread. After stripping, the signature
        name is gone and the quoted cue is gone, so no referral fires."""
        body = (
            "Sorry, no opportunity for you.\n"
            "\n"
            "On Mon, Sep 1, 2026 at 9:00 AM, Sender wrote:\n"
            "> Hey, please talk to our procurement team about this.\n"
            ">\n"
            "> reach out to Alba Kenji for details.\n"
            "\n"
            "-- \n"
            "Alba Kenji\n"
            "Account Manager\n"
        )
        result = extract_prospect_text(body)
        verdict = classify(result["text"])
        self.assertNotEqual(verdict["classification"], REFERRAL)

    def test_signature_without_separator_is_left_in_place(self):
        """No reliable delimiter means no safe stripping. A missed
        signature is safer than a clipped reply."""
        body = (
            "Not interested.\n"
            "\n"
            "Best,\n"
            "Alba Kenji\n"
            "Account Manager\n"
        )
        result = extract_prospect_text(body)
        self.assertIn("Not interested", result["text"])


class TestOriginalPreserved(unittest.TestCase):
    """The caller can still reach the untouched original."""

    def test_original_field_has_full_body(self):
        body = (
            "Thanks but no.\n"
            "\n"
            "> Hey, reaching out about your tooling.\n"
            ">\n"
            "> talk to me?\n"
            "\n"
            "-- \n"
            "Prospect Name\n"
            "Title\n"
        )
        result = extract_prospect_text(body)
        self.assertEqual(result["original"], body)
        self.assertIn("talk to me", result["original"])
        self.assertIn("Prospect Name", result["original"])

    def test_lengths_reported(self):
        body = (
            "Not interested.\n"
            "\n"
            "> Original message here with lots of text.\n"
        )
        result = extract_prospect_text(body)
        self.assertEqual(result["original_length"], len(body))
        self.assertLess(result["stripped_length"], result["original_length"])


class TestEmptyAndEdgeCases(unittest.TestCase):

    def test_empty_body(self):
        result = extract_prospect_text("")
        self.assertEqual(result["text"], "")
        self.assertEqual(result["method"], "empty")

    def test_none_body(self):
        result = extract_prospect_text(None)
        self.assertEqual(result["text"], "")
        self.assertEqual(result["method"], "empty")

    def test_only_quote_no_reply(self):
        body = (
            "> Hey, are you interested?\n"
            ">\n"
            "> Let me know.\n"
        )
        result = extract_prospect_text(body)
        self.assertEqual(result["text"], "")
        self.assertTrue(result["had_quote"])
        self.assertEqual(result["method"], "empty")


if __name__ == "__main__":
    unittest.main()
