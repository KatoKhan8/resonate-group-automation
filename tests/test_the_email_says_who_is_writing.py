"""TASK-063: the email half of the sender-identity defect.

TASK-075 made the LinkedIn connection note say who is writing and stopped
there. TASK-063 then read all 165 generated email steps and found sender
identity in ZERO of them - the defect survived its own fix on the other
channel.

These tests assert on what `generate.context_for` RETURNS and on what the
rendered prompt CONTAINS, never on the text of the source, because a test
that greps src/ fails when somebody writes a comment.
"""
import unittest

from src import clients, generate


CLIENT = {
    "sender": {
        "name": "Zvonimir",
        "role": "founder",
        "company": "Resonate",
        "works_on": "project profitability for agencies",
    },
    "product": {
        "name": "Productive",
        "what_it_is": "one place for projects, time and budgets",
        "capabilities": ["time tracking", "resourcing", "budgets"],
    },
    "personas": {"founder": {"angles": "profitability visible on Monday"}},
}

RECORD = {"id": "acme-co", "prior_contact": False}
CONTACT = {"key": "pat", "first_name": "Pat", "persona": "founder",
           "angle": "founder"}


class TheDraftContextCarriesTheSender(unittest.TestCase):
    """The email branch of context_for must pass sender_identity."""

    def test_draft_context_carries_sender_identity(self):
        block = generate.context_for("draft", RECORD, CONTACT, CLIENT)
        self.assertIn("sender_identity", block)
        self.assertTrue(
            block["sender_identity"],
            "draft context carried an empty sender_identity for a client "
            "whose config names a sender")

    def test_the_sender_block_is_the_clients_own(self):
        block = generate.context_for("draft", RECORD, CONTACT, CLIENT)
        self.assertEqual(block["sender_identity"],
                         clients.sender_identity(CLIENT))

    def test_both_channels_carry_the_same_sender(self):
        """The defect was one channel fixed and the other left behind."""
        draft = generate.context_for("draft", RECORD, CONTACT, CLIENT)
        note = generate.context_for("linkedin_note", RECORD, CONTACT, CLIENT)
        self.assertEqual(draft["sender_identity"], note["sender_identity"])


class ItDegradesSafelyRatherThanInventing(unittest.TestCase):
    """An absent sender must not become a fabricated one."""

    def test_a_client_with_no_sender_block_does_not_raise(self):
        bare = {"product": CLIENT["product"]}
        block = generate.context_for("draft", RECORD, CONTACT, bare)
        self.assertIn("sender_identity", block)

    def test_an_absent_sender_is_falsy_not_a_placeholder(self):
        """Empty must be empty, so the prompt can take its degraded path.

        A placeholder string here would reach a prospect as literal text,
        which is the same class of defect as {{first_name}}.
        """
        bare = {"product": CLIENT["product"]}
        block = generate.context_for("draft", RECORD, CONTACT, bare)
        value = block["sender_identity"]
        self.assertFalse(
            value and any(ch in str(value) for ch in "{}"),
            f"sender_identity carried a template placeholder: {value!r}")


class TheEmailPromptAsksForIt(unittest.TestCase):
    """The rendered prompt must actually instruct the model to use it.

    Passing the value and never mentioning it in the template is exactly the
    'computed correctly, read by nobody' defect this repository keeps
    producing.
    """

    def test_the_draft_template_mentions_sender_identity(self):
        with open("prompts/draft.md", encoding="utf-8") as handle:
            template = handle.read()
        self.assertIn("sender_identity", template)

    def test_the_draft_template_forbids_inventing_a_sender(self):
        with open("prompts/draft.md", encoding="utf-8") as handle:
            template = handle.read().lower()
        self.assertIn("never invent a sender", template)

    def test_the_draft_template_forbids_claiming_to_be_their_agency(self):
        """'Our agency sees that...' was generated on a real record."""
        with open("prompts/draft.md", encoding="utf-8") as handle:
            template = handle.read().lower()
        self.assertIn("our agency", template)


if __name__ == "__main__":
    unittest.main()
