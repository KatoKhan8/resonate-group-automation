"""A step that says it is the last one, while a later step still sends.

THE DEFECT THIS EXISTS FOR. Lane M, 2026-09-25: step 4 of a five-step
cadence read "so this is the last useful thing I have" on 690 of 690
leads across three cohorts. Step 5 arrives nine days later, so that
sentence was false on every send, to every prospect. It was caught by a
coordinator reading the rendered copy, not by the lint, and not by a
human sampling of fifteen drafts either - because it reads perfectly
well in isolation.

WHY IT IS MECHANICAL. What makes the sentence false is not the sentence,
it is its POSITION in a sequence whose length the caller already knows.
That is arithmetic, and a person should not be asked to hold it in their
head on every regeneration.

THE LAST STEP IS EXEMT BY DESIGN: there the same words are true, and
step 5's "no reply needed and I will stop here" must keep passing.
"""
import unittest

from src import copylint

PACK = {"facts": [{"snippet": "we build brands for challenger companies"}]}
OPENER = ("Hi Dana, I was reading the site and the line about we build "
          "brands for challenger companies is what made me write.")
FILLER = "Following up on the note below. Happy to send it over."
LAST = ("Closing the loop on this thread. If it is not a fit or not the "
        "moment, no reply needed and I will stop here.")

#: The exact sentence that shipped on 690 leads.
SHIPPED_DEFECT = ("I do not want to keep landing in your inbox, so this is "
                  "the last useful thing I have. We book qualified "
                  "conversations for agencies without adding to your team.")

#: What replaced it: same job, no claim of finality.
THE_FIX = ("Keeping this one short. We book qualified conversations for "
           "agencies without adding to your team. If the timing is wrong, "
           "tell me when to come back and I will work to that.")


def lead(step4, lead_id="L", step3=FILLER):
    return {"id": lead_id, "pack": PACK,
            "steps": [{"body": OPENER}, {"body": FILLER}, {"body": step3},
                      {"body": step4}, {"body": LAST}]}


def fired(leads):
    rep = copylint.check_batch(leads, {l["id"]: l["pack"] for l in leads})
    return rep["counts"]["finality_before_last_step"], rep["refused"]


class AStepMayNotClaimToBeTheLastOne(unittest.TestCase):

    def test_the_sentence_that_actually_shipped_is_refused(self):
        count, refused = fired([lead(SHIPPED_DEFECT)])
        self.assertEqual(count, 1)
        self.assertTrue(refused, "a false promise to the prospect must "
                                 "refuse the batch, not warn about it")

    def test_the_fix_passes(self):
        count, refused = fired([lead(THE_FIX)])
        self.assertEqual(count, 0)
        self.assertFalse(refused)

    def test_the_last_step_may_say_it_is_the_last_step(self):
        # LAST is step 5 in every lead above and says "I will stop here".
        self.assertEqual(fired([lead(THE_FIX)])[0], 0)

    def test_the_same_words_earlier_in_the_sequence_do_fire(self):
        self.assertEqual(fired([lead(THE_FIX, step3=LAST)])[0], 1)

    def test_other_phrasings_of_the_same_claim(self):
        for phrase in ("This is my last email on this.",
                       "I will leave it here if now is not the moment.",
                       "I won't email again after this.",
                       "I will not follow up again.",
                       "Final note from me.",
                       "No more emails from me after today.",
                       "I'll stop here unless you say otherwise.",
                       "I will leave you alone after this one."):
            with self.subTest(phrase=phrase):
                self.assertEqual(fired([lead(phrase)])[0], 1,
                                 "missed: %s" % phrase)

    def test_ordinary_follow_up_language_does_not_fire(self):
        for phrase in ("One more thought before the week runs out.",
                       "Following up on the note below.",
                       "Last week I sent a note about outbound.",
                       "Worth fifteen minutes?",
                       "Keeping this one short."):
            with self.subTest(phrase=phrase):
                self.assertEqual(fired([lead(phrase)])[0], 0,
                                 "false positive: %s" % phrase)

    def test_it_is_a_refusing_rule_not_a_warning(self):
        self.assertNotIn("finality_before_last_step", copylint.WARNING_RULES)
        self.assertIn("finality_before_last_step", dict(copylint.RULES))


if __name__ == "__main__":
    unittest.main()
