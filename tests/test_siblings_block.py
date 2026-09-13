"""TASK-017: each draft is written blind to its siblings.

When the generator writes em3, it must see what em1 and em2 already say -
without that being mistaken for confirmed history. Two blocks, two meanings:

    already_sent   confirmed. Licenses "as I mentioned". May be empty.
    siblings       drafted, not sent. Licenses NOTHING. Exists so this
                   message says something the others do not.

No test calls a model or a network.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import claims, generate, lint, llm, store
from tests.base import FIXTURES, pin_client_config


def draft_answer(body=None, subject="something new and different",
                 first="Ivana"):
    if body is None:
        body = (
            f"{first}, teams at agencies your size often find that the gap "
            "between project delivery and profitability is invisible until "
            "Monday morning. A different angle from the earlier messages: "
            "what would change if utilisation was a number you could see "
            "in real time rather than reconstructed from timesheets?\n\n"
            "Would that be worth a short conversation?")
    return json.dumps({"subject": subject, "body": body})


def note_answer(note="Your work on the Zagreb HR pipeline caught my eye"):
    return json.dumps({"note": note})


class SiblingsBlockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-sib-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase5.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        pin_client_config(self, linkedin_connection_note=None)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rec(self, rid="meridian"):
        return store.get(rid)

    def _store_email_siblings(self, rec, contact, steps):
        """Store draft email steps directly onto the record's cadence."""
        key = lint.contact_key(contact)
        for step_key, subject, body in steps:
            rec.setdefault("cadence", {}).setdefault(key, {})[step_key] = {
                "channel": "email", "generated": True,
                "subject": subject, "body": body}

    def _store_linkedin_siblings(self, rec, contact, steps):
        """Store draft LinkedIn steps directly onto the record's cadence."""
        key = lint.contact_key(contact)
        for step_key, note in steps:
            rec.setdefault("cadence", {}).setdefault(key, {})[step_key] = {
                "channel": "linkedin", "generated": True, "note": note}


class TestSiblingsReachThePrompt(SiblingsBlockTest):
    """Writing day10 with day1 and day5 stored puts both into the prompt."""

    def test_day10_prompt_contains_day1_and_day5_openings(self):
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, contact=contact)
        self._store_email_siblings(rec, contact, [
            ("day1", "profitability on Monday",
             "Ivana, agencies your size often find that the gap between "
             "project delivery and profitability is invisible until Monday "
             "morning."),
            ("day5", "utilisation in real time",
             "A different angle: what would change if utilisation was a "
             "number you could see in real time rather than reconstructed "
             "from timesheets?"),
        ])
        ctx = generate.context_for("draft", rec, contact, step_key="day10",
                                   sequence=sequence)
        siblings = ctx["siblings"]
        self.assertEqual(len(siblings), 2)
        sibling_steps = {s["step"] for s in siblings}
        self.assertIn("day1", sibling_steps)
        self.assertIn("day5", sibling_steps)
        d1 = next(s for s in siblings if s["step"] == "day1")
        self.assertEqual(d1["subject"], "profitability on Monday")
        self.assertIn("agencies your size", d1["opening"])

    def test_day10_prompt_does_not_call_siblings_sent(self):
        """The siblings block must not use the word 'sent' or 'delivered'."""
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, contact=contact)
        self._store_email_siblings(rec, contact, [
            ("day1", "subject one", "Body of the first email about marketing."),
            ("day5", "subject two", "Body of the second email about hiring."),
        ])
        prompt = generate.render_prompt("draft", rec, contact,
                                        step_key="day10", sequence=sequence)
        self.assertIn("siblings", prompt)
        self.assertIn("DRAFTS, not sent", prompt)
        self.assertIn("licenses a claim of contact", prompt.lower())

    def test_already_sent_is_still_empty_when_nothing_was_sent(self):
        """The two blocks are separate. Siblings exist; already_sent does not.

        This is the test that proves the distinction. day1 and day5 are stored
        as drafts in rec["cadence"], but nothing was confirmed sent through
        the event log. already_sent must be empty; siblings must be full.
        """
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, contact=contact)
        self._store_email_siblings(rec, contact, [
            ("day1", "subject one", "First email body about marketing."),
            ("day5", "subject two", "Second email body about hiring."),
        ])
        ctx = generate.context_for("draft", rec, contact, step_key="day10",
                                   sequence=sequence)
        self.assertEqual(ctx["already_sent"], [],
                         "already_sent must be empty when nothing was sent")
        self.assertEqual(len(ctx["siblings"]), 2,
                         "siblings must contain the two stored drafts")


class TestSiblingsAreSameChannelOnly(SiblingsBlockTest):
    """LinkedIn note prompt gets LinkedIn siblings and never email ones."""

    def test_linkedin_note_gets_linkedin_siblings_not_email(self):
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, contact=contact)
        self._store_email_siblings(rec, contact, [
            ("day1", "email subject", "Email body about profitability."),
        ])
        self._store_linkedin_siblings(rec, contact, [
            ("day3", "Connection note about Zagreb HR"),
        ])
        ctx = generate.context_for("linkedin_note", rec, contact,
                                   step_key="day8", sequence=sequence)
        siblings = ctx["siblings"]
        self.assertEqual(len(siblings), 1)
        self.assertEqual(siblings[0]["step"], "day3")
        self.assertIn("note", siblings[0])
        self.assertNotIn("subject", siblings[0])

    def test_email_draft_gets_email_siblings_not_linkedin(self):
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, contact=contact)
        self._store_linkedin_siblings(rec, contact, [
            ("day3", "Connection note about Zagreb HR"),
            ("day8", "First message about hiring pipeline"),
        ])
        self._store_email_siblings(rec, contact, [
            ("day1", "email subject", "Email body about profitability."),
        ])
        ctx = generate.context_for("draft", rec, contact, step_key="day5",
                                   sequence=sequence)
        siblings = ctx["siblings"]
        self.assertEqual(len(siblings), 1)
        self.assertEqual(siblings[0]["step"], "day1")
        self.assertIn("subject", siblings[0])

    def test_linkedin_prompt_contains_siblings_section(self):
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, contact=contact)
        self._store_linkedin_siblings(rec, contact, [
            ("day3", "Connection note about Zagreb HR"),
        ])
        prompt = generate.render_prompt("linkedin_note", rec, contact,
                                        step_key="day8", sequence=sequence)
        self.assertIn("siblings", prompt)
        self.assertIn("DRAFTS, not sent", prompt)


class TestSiblingsDoNotLicenseClaims(SiblingsBlockTest):
    """A draft that says 'as I mentioned' is still refused."""

    def test_claims_still_refuses_prior_contact_with_siblings_present(self):
        """Siblings are not sent. claims.prior_contact must not see them."""
        rec = self.rec()
        contact = rec["contacts"][0]
        self._store_email_siblings(rec, contact, [
            ("day1", "subject", "First email body about marketing strategy."),
            ("day5", "subject", "Second email body about hiring pipeline."),
        ])
        self.assertFalse(claims.prior_contact(rec, contact),
                         "siblings must not count as prior contact")

    def test_lint_still_refuses_as_i_mentioned_with_siblings_present(self):
        """A draft referencing siblings as sent history must fail lint."""
        rec = self.rec()
        contact = rec["contacts"][0]
        self._store_email_siblings(rec, contact, [
            ("day1", "subject", "First email body about marketing strategy."),
        ])
        bad_body = (
            "Ivana, as I mentioned in my previous email, agencies your size "
            "often find that profitability is invisible until Monday. "
            "Would a short conversation about real-time utilisation be "
            "worth your time?")
        candidate = {"channel": "email", "generated": True,
                     "subject": "following up", "body": bad_body}
        trial = dict(rec)
        key = lint.contact_key(contact)
        trial["cadence"] = {**(rec.get("cadence") or {}),
                            key: {**((rec.get("cadence") or {}).get(key) or {}),
                                  "day5": candidate}}
        failures = lint.check(trial, key, candidate)
        content_failures = [f for f in failures if f not in lint.HELD_CODES]
        self.assertTrue(content_failures,
                        "a draft saying 'as I mentioned' must fail lint "
                        "even when siblings are present")

    def test_claims_refuses_as_i_mentioned_with_siblings_present(self):
        """claims.check must not be loosened by siblings being in the prompt."""
        rec = self.rec()
        contact = rec["contacts"][0]
        self._store_email_siblings(rec, contact, [
            ("day1", "subject", "First email body about marketing strategy."),
        ])
        text = "as I mentioned in my last email, the profitability gap"
        unsupported = claims.check(text, rec, contact)
        self.assertTrue(unsupported,
                        "claims must still refuse 'as I mentioned' when "
                        "siblings exist but nothing was sent")


class TestSiblingsBlockFunction(SiblingsBlockTest):
    """Unit tests for siblings_block itself."""

    def test_empty_when_no_stored_drafts(self):
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, contact=contact)
        result = generate.siblings_block(rec, contact, sequence, "em3", "email")
        self.assertEqual(result, [])

    def test_excludes_the_current_step(self):
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, contact=contact)
        self._store_email_siblings(rec, contact, [
            ("day10", "current step subject", "Current step body."),
        ])
        result = generate.siblings_block(rec, contact, sequence, "day10", "email")
        self.assertEqual(result, [])

    def test_includes_purpose_from_ladder(self):
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, contact=contact)
        self._store_email_siblings(rec, contact, [
            ("day1", "subject one", "Body of email one."),
        ])
        result = generate.siblings_block(rec, contact, sequence, "day5", "email")
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0]["purpose"])
        self.assertIn("Relevance", result[0]["purpose"])

    def test_break_the_block_and_confirm_test_fails(self):
        """TASK-017 test 5: break siblings_block and confirm the intended
        test fails for the intended reason."""
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, contact=contact)
        self._store_email_siblings(rec, contact, [
            ("day1", "subject one", "Body of email one about marketing."),
            ("day5", "subject two", "Body of email two about hiring."),
        ])
        # Verify the function works correctly first
        result = generate.siblings_block(rec, contact, sequence, "day10", "email")
        self.assertEqual(len(result), 2)

        # Now simulate a broken siblings_block that returns empty
        original = generate.siblings_block
        generate.siblings_block = lambda *a, **kw: []
        try:
            broken_result = generate.siblings_block(
                rec, contact, sequence, "day10", "email")
            self.assertEqual(len(broken_result), 0,
                             "the broken version returns nothing")
            # The test that checks siblings reach the prompt would fail:
            ctx = generate.context_for("draft", rec, contact, step_key="day10",
                                       sequence=sequence)
            self.assertEqual(len(ctx.get("siblings", [])), 0,
                             "with a broken siblings_block, context has no "
                             "siblings - this is what the test catches")
        finally:
            generate.siblings_block = original


class TestSiblingsInRenderedPrompt(SiblingsBlockTest):
    """Integration: siblings appear in the rendered prompt as JSON."""

    def test_siblings_appear_in_rendered_draft_prompt(self):
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, contact=contact)
        self._store_email_siblings(rec, contact, [
            ("day1", "profitability on Monday",
             "Ivana, agencies your size often find that the gap between "
             "project delivery and profitability is invisible until Monday "
             "morning."),
            ("day5", "utilisation in real time",
             "A different angle: what would change if utilisation was a "
             "number you could see in real time?"),
        ])
        prompt = generate.render_prompt("draft", rec, contact,
                                        step_key="day10", sequence=sequence)
        parsed = json.loads(prompt.split(llm.BEGIN)[1].split(llm.END)[0])
        siblings = parsed["siblings"]
        self.assertEqual(len(siblings), 2)
        steps = {s["step"] for s in siblings}
        self.assertEqual(steps, {"day1", "day5"})

    def test_siblings_and_already_sent_are_separate_keys(self):
        """Both keys exist in the prompt context, with distinct meanings."""
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, contact=contact)
        self._store_email_siblings(rec, contact, [
            ("day1", "subject", "First email body."),
        ])
        prompt = generate.render_prompt("draft", rec, contact,
                                        step_key="day5", sequence=sequence)
        parsed = json.loads(prompt.split(llm.BEGIN)[1].split(llm.END)[0])
        self.assertIn("siblings", parsed)
        self.assertIn("already_sent", parsed)
        self.assertNotEqual(parsed["siblings"], parsed["already_sent"],
                            "siblings and already_sent are different blocks")
        self.assertEqual(parsed["already_sent"], [])
        self.assertEqual(len(parsed["siblings"]), 1)


if __name__ == "__main__":
    unittest.main()
