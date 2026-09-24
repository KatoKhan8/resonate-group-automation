"""The replay harness's own two defects, and a control for each.

Written 2026-09-24 against `scripts/slack_agent_replay.py`, after the
2026-09-23 audit reported a scorecard whose harness had two holes in it:

  1. `--catalogue` parsed `- "quoted line"`. The catalogue has never used
     that shape, so the flag added ZERO questions to every run and the run
     printed a plausible count either way.

  2. The six checks could not catch the right number answering the wrong
     question. `what is running` was answered with MONITOR HEALTH and
     scored clean on all six, because every figure in it was real.

**Both were invisible for the same reason: nothing here was ever asked to
fail.** So each fix below gets a test that fails when the fix is removed
AND a control proving the check can still pass - a subject check that
refused every answer would catch the monitor-health case and be useless.
"""
import importlib.util
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def harness():
    spec = importlib.util.spec_from_file_location(
        "slack_agent_replay",
        os.path.join(ROOT, "scripts", "slack_agent_replay.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CATALOGUE = os.path.join(ROOT, "docs", "SLACK-AGENT-QUESTION-CATALOGUE.md")


class TestTheCatalogueIsActuallyParsed(unittest.TestCase):

    def test_it_finds_the_phrasings(self):
        """The number is not the point; a non-zero count is."""
        rows = harness().catalogue_questions(ROOT)
        self.assertGreater(
            len(rows), 20,
            "the catalogue parser found almost nothing again. It reads "
            "blockquotes in emphasis - `> *phrasing*` - and the document "
            "is the authority on that shape, not this test.")
        for row in rows:
            self.assertEqual(row["source"], "catalogue")
            self.assertGreater(len(row["text"]), 8)

    def test_the_old_pattern_would_still_find_nothing(self):
        """THE CONTROL, AND THE WHOLE ARGUMENT FOR THE FIX.

        If `- "quoted"` matched even a few lines, the old parser was merely
        incomplete and the zero in the audit would need another explanation.
        It matches none, which is why `--catalogue` contributed nothing.
        """
        old = re.compile(r'^\s*[-*]\s+"(.+?)"\s*$')
        with open(CATALOGUE, encoding="utf-8") as handle:
            hits = [line for line in handle if old.match(line)]
        self.assertEqual(
            hits, [],
            "the catalogue now uses the bullet shape the OLD parser wanted. "
            "That is fine, but this test's premise is gone - reread it.")

    def test_a_phrasing_split_across_two_lines_is_one_question(self):
        """The emphasis spans both lines; joining them is the only way."""
        rows = harness().catalogue_questions(ROOT)
        joined = [r["text"] for r in rows if "add/review" in r["text"]]
        self.assertEqual(len(joined), 1, "the two-line phrasing was lost or "
                                        "split: %r" % (joined,))
        self.assertIn("I haven't received your content", joined[0])
        self.assertNotIn("*", joined[0])

    def test_consecutive_phrasings_do_not_merge_into_one(self):
        """They are listed back to back with no blank line between."""
        rows = [r["text"] for r in harness().catalogue_questions(ROOT)]
        self.assertIn("jesu puštene kampanje sada?", rows)
        self.assertIn("jesmo im ovo bili poslali?", rows)


class TestTheRightNumberCanAnswerTheWrongQuestion(unittest.TestCase):
    """`subject`: does the answer name the thing that was asked about?"""

    def setUp(self):
        self.h = harness()

    def mark(self, question, reply):
        result = {"reply": reply, "scope": "internal", "guard": ""}
        return self.h.score({"text": question}, result)["subject"], result

    def test_the_case_that_scored_clean_on_all_six_checks(self):
        """THE DEFECT, VERBATIM. Row one of the 2026-09-23 replay.

        Every figure in this reply is real, it leaked nothing, it is in the
        right language and it is three sentences. Six checks, six passes,
        and it does not answer the question.
        """
        mark, result = self.mark(
            "what is running",
            "All four monitors are healthy. The last heartbeat was 40 "
            "seconds ago and nothing has restarted since 08:12.")
        self.assertEqual(mark, self.h.FAIL)
        self.assertIn("campaign", result.get("subject_missed") or [])

    def test_the_control_an_answer_about_campaigns_passes(self):
        """WITHOUT THIS THE CHECK IS WORTHLESS.

        A `subject` that refused everything would catch the monitor-health
        case and every correct answer with it, and it would look exactly
        as green in the fail column.
        """
        mark, _ = self.mark(
            "what is running",
            "Campaigns 491 through 498 are active. 487 is paused.")
        self.assertEqual(mark, self.h.PASS)

    def test_a_question_naming_nothing_is_n_a_and_not_a_pass(self):
        """`n/a` is the honest mark for a check that did not run."""
        mark, _ = self.mark("what's the status on that?", "Everything is on.")
        self.assertEqual(mark, self.h.NA)

    def test_the_wrong_campaign_id_fails_however_right_its_numbers(self):
        mark, result = self.mark(
            "how many did 487 send yesterday?",
            "Campaign 489 sent 14 emails yesterday.")
        self.assertEqual(mark, self.h.FAIL)
        self.assertIn("id:487", result.get("subject_missed") or [])

    def test_it_reads_croatian_because_most_of_the_corpus_is(self):
        """A check that only works in English scores the smaller half."""
        mark, _ = self.mark(
            "jel imamo koji meeting još?",
            "Sve četiri kampanje su aktivne i šalju po planu.")
        self.assertEqual(mark, self.h.FAIL)

    def test_an_unanswered_question_is_n_a_rather_than_a_failure(self):
        """A gagged turn has no answer to score. 11 of 32 were this."""
        mark, _ = self.mark("what is running", "")
        self.assertEqual(mark, self.h.NA)


class TestTheCheckListCarriesIt(unittest.TestCase):
    """A check nothing tallies is a check nobody sees."""

    def test_subject_is_in_CHECKS(self):
        self.assertIn("subject", harness().CHECKS)


if __name__ == "__main__":
    unittest.main()
