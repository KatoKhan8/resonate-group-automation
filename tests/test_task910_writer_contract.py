"""TASK-910: five useful steps or a generation failure, and the normaliser
on the canonical path.

Operator ruling, 2026-09-28. Two minimal corrections:

1. The writer contract in `src/copystages.py` told the model to set steps
   null when no credible angle existed, while `copylint.empty_step` refused
   any empty step. Three attempts could not converge because the two
   contracts disagreed. The contradictory instruction is replaced with the
   operator's exact text: five steps, each useful, or a generation failure.

2. `lint.normalise_punctuation` was called on the legacy path in five places
   but had ZERO callers in `src/generate_campaign.py`, the canonical
   entrypoint. U+2019 (curly apostrophe) survived into `copylint` and
   refused LinkedIn notes. The fix: call the existing function on every
   prospect-facing string after parsing the writer output and before
   `copylint.check_batch`.

NEITHER change weakens a gate. `STEPS_EXPECTED` stays 5. `empty_step` still
refuses. An em dash still fails after normalisation because the tell
survives the substitution.
"""
import json
import sys
import os
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (campaignstrategy, copystages, copylint, generate_campaign,
                 lint)
from tests.base import (CampaignModel, pin_approved_offer, writer_answer)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _client_config():
    return {
        "name": "productive",
        "domain": "productive.test",
        "cadence": "default",
        "product": {"capabilities": {
            "profitability": "see project margin while it runs",
            "project_management": "every project and its delivery in one place",
        }},
        "sender": {"name": "Ivan", "role": "founder", "company": "Productive"},
    }


def _account(persona="champion"):
    return {
        "company": "TestCorp",
        "domain": "testcorp.test",
        "persona": persona,
        "segment": "test",
        "sources": [{"label": "site", "url": "https://testcorp.test/about",
                     "text": "TestCorp is a digital marketing agency with 40 "
                             "people and offices in Zagreb HR"}],
    }


def _contacts():
    return [{"email": "jane@testcorp.test", "first_name": "Jane",
             "last_name": "Doe", "title": "CEO", "contact_key": "jane-doe",
             "linkedin": "https://linkedin.com/in/janedoe"}]


#: Five clean bodies that pass every gate. Each is addressed to Jane,
#: distinct in vocabulary, and over 45 words.
_CLEAN_SUBJECTS = {"A": "the question we never answered",
                   "B": "the developer we never contacted",
                   "C": "closing the file"}

# INSIDE THE WORD CONTRACT AT EVERY STEP. Measured 2026-10-02: em1 43, em2 41 and
# em3 46 words, under the declared floors of 60, 45 and 60. A sequence this file
# calls CLEAN cannot be three steps short of the contract `lint` enforces. Now em1
# 75, em2 61, em3 72; em4 and em5 were already inside. Lengthened with questions
# and hedges, never with assertions, so `claims.check` stays out of it.
_CLEAN_SEQUENCES = {
    "em1": (
        "Jane, your scheduling runs through one spreadsheet that three "
        "people edit across offices, and nobody can say on Tuesday whether "
        "Friday is already full. What decides today whether a new project can "
        "start next week without pushing something else out of the queue? "
        "When two of those three people write a different answer into the "
        "same cell, who do you ask for the one that is right rather than "
        "the one that is most recent?"),
    "em2": (
        "Jane, month end reconciliation takes four days here and most of it "
        "is chasing which hours belong to which client project. The hours "
        "themselves are recorded; what takes the four days is deciding which "
        "of them were billable and against what. How long after the last "
        "working day do you actually know what each account earned, and who "
        "assembles that answer?"),
    "em3": (
        "Jane, a studio your size usually discovers a budget overrun when "
        "the invoice is drafted rather than while the work is happening on "
        "the ground. By then the hours are spent and the only lever left is "
        "deciding who absorbs it, which is a reporting delay rather than a "
        "spending problem. What would have to change for an overrun to "
        "surface in week two instead of week six on your active projects?"),
    "em4": (
        "Jane, when a project slips you hear about it on Friday instead of "
        "Tuesday because the weekly status report is assembled by hand not "
        "observed in real time. What would change for your team if project "
        "status were visible while the work was actually running?"),
    "em5": (
        "Jane, if none of this is a priority right now, say so and I will "
        "close the file and stop writing. If it is, the single question still "
        "open is the one from last autumn: does the key work against a list "
        "you care about? Everything else follows from the answer to that."),
    "li1": ("Jane, reading about how finance and delivery are split "
            "across the offices. No pitch, happy to follow along."),
    "li2": ("Jane, the question I keep asking heads of finance is when a "
            "project overrun becomes visible. Is it while the work runs, or "
            "once the invoice is drafted?"),
    "li3": ("Jane, the part that costs the most is usually reconstructing "
            "which hours belong to which client after the month has closed."),
    "li4": ("Jane, no pressure at all. If this is not a priority I will "
            "leave it with you."),
    "li5": ("Jane, your approach to addressable ads across platforms stands "
            "out. Would love to hear about your biggest operational challenge."),
}


# ---------------------------------------------------------------------------
# CORRECTION 1: the writer contract
# ---------------------------------------------------------------------------

class TestWriterContract(unittest.TestCase):
    """The prompt no longer contains the contradictory instruction."""

    def test_strategy_prompt_no_longer_says_set_it_null(self):
        """The instruction that told the model to leave steps null is gone."""
        self.assertNotIn("SET IT null", copystages.STRATEGY_SYSTEM)

    def test_strategy_prompt_no_longer_says_beats_five(self):
        """The exact phrase the acceptance command greps for."""
        self.assertNotIn("beats five where one is filler",
                         copystages.STRATEGY_SYSTEM)

    def test_strategy_prompt_carries_the_operator_text(self):
        """The replacement text is present, verbatim."""
        self.assertIn("You must return all five sequence steps",
                      copystages.STRATEGY_SYSTEM)
        self.assertIn("return a generation failure rather",
                      copystages.STRATEGY_SYSTEM)

    def test_strategy_prompt_says_do_not_return_null(self):
        """The operator's explicit prohibition on null steps."""
        self.assertIn("Do not return null or omit a required step",
                      copystages.STRATEGY_SYSTEM)


# ---------------------------------------------------------------------------
# CORRECTION 1 side-constraint: copylint is untouched
# ---------------------------------------------------------------------------

class TestCopylintUntouched(unittest.TestCase):
    """`STEPS_EXPECTED` is still 5 and `empty_step` still refuses."""

    def test_steps_expected_is_still_five(self):
        self.assertEqual(copylint.STEPS_EXPECTED, 5)

    def test_empty_step_still_refuses(self):
        """A lead with an empty body fires `empty_step`."""
        lead = {
            "id": "test-lead",
            "steps": [
                {"subject": "subject", "body": "A body that is long enough " * 5},
                {"subject": "subject", "body": "Another body that is long " * 5},
                {"subject": "subject", "body": ""},
                {"subject": "subject", "body": "Yet another body " * 5},
                {"subject": "subject", "body": "Final body that is long " * 5},
            ],
            "ps": {},
            "linkedin": {},
            "pack": {"facts": [{"snippet": "body"}]},
        }
        report = copylint.check_batch([lead])
        self.assertIn("test-lead",
                      report.get("offenders", {}).get("empty_step", []))


# ---------------------------------------------------------------------------
# CORRECTION 2: the normaliser on the canonical path
# ---------------------------------------------------------------------------

class TestNormaliserOnCanonicalPath(unittest.TestCase):
    """`lint.normalise_punctuation` is called before `copylint.check_batch`."""

    def setUp(self):
        campaignstrategy.clear_cache()
        self.addCleanup(campaignstrategy.clear_cache)
        pin_approved_offer(self)

    def test_curly_apostrophe_passes_after_normalisation(self):
        """Acceptance 3: U+2019 is normalised to ASCII and NOT refused.

        The writer output contains a curly apostrophe in em1. After
        normalisation, it becomes a straight ASCII apostrophe and the
        dash rule does not fire (apostrophes are not dashes).
        """
        curly_body = (
            "Jane, your scheduling runs through one spreadsheet that three "
            "people edit across offices, and nobody can say on Tuesday whether "
            "Friday is already full. What decides today whether a new project "
            "can start next week without pushing something else out\u2019s "
            "queue?")
        sequences = dict(_CLEAN_SEQUENCES)
        sequences["em1"] = curly_body
        model = CampaignModel((sequences, _CLEAN_SUBJECTS))

        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(),
            model=model, live=False, allow_pending_offers=True)

        contact = plan["contacts"][0]
        # The curly apostrophe was normalised to a straight one.
        self.assertNotIn("\u2019", contact["sequences"].get("em1", ""))
        self.assertIn("'", contact["sequences"].get("em1", ""))
        # The draft was NOT refused for a dash or punctuation issue.
        # `hold_kind` is None when the contact succeeded.
        self.assertNotEqual(contact.get("hold_kind"), "copy_refused")

    def test_em_dash_still_fails_after_normalisation(self):
        """Acceptance 4: an em dash normalises to ' - ' and DASH_RE catches it.

        The normaliser maps U+2014 to ' - ' (space-hyphen-space). The dash
        rule's regex matches spaced hyphens. The tell survives the
        substitution. A draft whose only defect is an em dash is STILL
        refused by copylint after normalisation.
        """
        em_dash_body = (
            "Jane, your scheduling runs through one spreadsheet that three "
            "people edit across offices \u2014 and nobody can say on Tuesday "
            "whether Friday is already full. What decides today whether a new "
            "project can start next week without pushing something else out "
            "of the queue?")
        sequences = dict(_CLEAN_SEQUENCES)
        sequences["em1"] = em_dash_body
        # All three attempts return the same em-dash body, so lint refuses
        # every time and the contact ends up held.
        model = CampaignModel(
            (sequences, _CLEAN_SUBJECTS),
            (sequences, _CLEAN_SUBJECTS),
            (sequences, _CLEAN_SUBJECTS))

        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(),
            model=model, live=False, allow_pending_offers=True)

        contact = plan["contacts"][0]
        # The em dash was normalised to ' - '.
        # After 3 failed attempts, the sequences are emptied.
        self.assertEqual(contact.get("hold_kind"), "copy_refused")
        self.assertEqual(contact.get("sequences"), {})

    def test_normaliser_is_actually_called_on_the_canonical_path(self):
        """Acceptance 7: MUTATION. Revert the normaliser call; acceptance 3
        must go red for that reason with no other guard firing first.

        This test patches `lint.normalise_punctuation` to be a no-op (identity)
        and verifies that a curly apostrophe SURVIVES into the sequences,
        proving the normaliser is what rescues it.
        """
        curly_body = (
            "Jane, your scheduling runs through one spreadsheet that three "
            "people edit across offices, and nobody can say on Tuesday whether "
            "Friday is already full. What decides today whether a new project "
            "can start next week without pushing something else out\u2019s "
            "queue?")
        sequences = dict(_CLEAN_SEQUENCES)
        sequences["em1"] = curly_body
        model = CampaignModel((sequences, _CLEAN_SUBJECTS))

        # Patch normalise_punctuation to be identity (no-op).
        with mock.patch.object(lint, "normalise_punctuation",
                               side_effect=lambda t: t):
            plan = generate_campaign.generate(
                _client_config(), _account(), _contacts(),
                model=model, live=False, allow_pending_offers=True)

        contact = plan["contacts"][0]
        em1 = contact["sequences"].get("em1", "")
        # With the normaliser disabled, the curly apostrophe SURVIVES.
        self.assertIn("\u2019", em1,
                      "MUTATION FAILED: the curly apostrophe was still "
                      "normalised even though normalise_punctuation was "
                      "patched to identity. The call site is not reached "
                      "through the patched function.")


# ---------------------------------------------------------------------------
# Acceptance 5: regression tests pin both directions
# ---------------------------------------------------------------------------

class TestPunctuationRegression(unittest.TestCase):
    """Acceptance 5: both cases pinned by regression tests."""

    def test_curly_apostrophe_normalised_and_not_refused(self):
        """U+2019 -> U+0027, and DASH_RE does not fire on the result."""
        text = "we\u2019re here\u2019"
        normalised = lint.normalise_punctuation(text)
        self.assertNotIn("\u2019", normalised)
        self.assertIn("'", normalised)
        self.assertFalse(copylint.DASH_RE.search(normalised))

    def test_em_dash_normalised_but_still_caught(self):
        """U+2014 -> ' - ', and DASH_RE still fires on the spaced hyphen."""
        text = "clauses\u2014like this"
        normalised = lint.normalise_punctuation(text)
        self.assertNotIn("\u2014", normalised)
        self.assertIn(" - ", normalised)
        self.assertTrue(copylint.DASH_RE.search(normalised))

    def test_left_curly_quote_also_normalised(self):
        """U+2018 -> U+0027 as well."""
        text = "\u2018hello\u2019"
        normalised = lint.normalise_punctuation(text)
        self.assertNotIn("\u2018", normalised)
        self.assertNotIn("\u2019", normalised)
        self.assertEqual(normalised, "'hello'")


# ---------------------------------------------------------------------------
# Acceptance 6: the retry feedback is semantically actionable
# ---------------------------------------------------------------------------

class TestRetryFeedback(unittest.TestCase):
    """The rejection string fed back through RETRY_BLOCK is actionable
    under the new contract."""

    def setUp(self):
        campaignstrategy.clear_cache()
        self.addCleanup(campaignstrategy.clear_cache)
        pin_approved_offer(self)

    def test_retry_feedback_does_not_contradict_the_new_contract(self):
        """When copylint refuses for empty_step, the retry feedback tells the
        model what failed. Under the new contract, the model is told to
        produce five complete steps, so the rejection string must not tell
        it to leave a step null.

        The rejection string is built by `copylint_failures()` from the
        rule descriptions in `copylint.RULES`. The `empty_step` rule says
        "one of the 5 steps is empty", which is actionable: the model
        knows it must fill all five.
        """
        report = {
            "refused": True,
            "leads": 1,
            "clean": 0,
            "counts": {"empty_step": 1},
            "offenders": {"empty_step": ["jane-doe"]},
            "rules": dict(copylint.RULES),
        }
        failures = generate_campaign.copylint_failures(report, "jane-doe")
        self.assertTrue(failures, "expected at least one failure string")
        failure_text = "; ".join(failures)
        # The failure text must NOT tell the model to set a step null.
        self.assertNotIn("null", failure_text.lower())
        # The failure text must mention the step count or emptiness.
        self.assertTrue(
            "empty" in failure_text.lower() or "step" in failure_text.lower(),
            "the retry feedback should mention what went wrong: %r"
            % failure_text)

    def test_retry_block_carries_the_lint_reason(self):
        """The RETRY_BLOCK template includes the lint failure reason,
        so the model knows what to fix."""
        retry = generate_campaign.RETRY_BLOCK % "one of the 5 steps is empty"
        self.assertIn("previous draft failed lint", retry)
        self.assertIn("one of the 5 steps is empty", retry)
        self.assertIn("Do not patch the old one", retry)


# ---------------------------------------------------------------------------
# The normaliser covers ALL prospect-facing text
# ---------------------------------------------------------------------------

class TestNormaliserCoversAllText(unittest.TestCase):
    """The normaliser is applied to subjects, bodies, PS and LinkedIn."""

    def setUp(self):
        campaignstrategy.clear_cache()
        self.addCleanup(campaignstrategy.clear_cache)
        pin_approved_offer(self)

    def test_subjects_are_normalised(self):
        """A curly apostrophe in a subject is normalised."""
        subjects = dict(_CLEAN_SUBJECTS)
        subjects["A"] = "the question\u2019s answer"
        model = CampaignModel((_CLEAN_SEQUENCES, subjects))

        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(),
            model=model, live=False, allow_pending_offers=True)

        contact = plan["contacts"][0]
        self.assertNotIn("\u2019", contact["subjects"].get("A", ""))

    def test_linkedin_notes_are_normalised(self):
        """A curly apostrophe in a LinkedIn note is normalised."""
        sequences = dict(_CLEAN_SEQUENCES)
        sequences["connect"] = (
            "Jane, reading about how finance\u2019s split across offices. "
            "No pitch, happy to follow along.")
        model = CampaignModel((sequences, _CLEAN_SUBJECTS))

        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(),
            model=model, live=False, allow_pending_offers=True)

        contact = plan["contacts"][0]
        connect = contact["sequences"].get("connect", "")
        self.assertNotIn("\u2019", connect)


if __name__ == "__main__":
    unittest.main()
