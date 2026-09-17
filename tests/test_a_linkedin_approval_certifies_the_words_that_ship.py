"""The LinkedIn half of D1: an approval certifies the words that SHIP.

`bisonfactory._certified_copy` was hardened first, because the email lane is
where the defect was measured. `heyreachfactory._step_copy` carried the same
one: it asked whether a step had an `approval` key and never whether that
approval's fingerprint covered the step's own words. A step approved and then
edited kept its stamp, and the EDITED note went to the wire.

The invariant, stated on the channel where a stamp is the only thing between
generated text and a real person's LinkedIn inbox:

    approved fingerprint + different stored note  ->  NO COPY, and the step
    lands in `assemble_linkedin_copy`'s `missing` list rather than on a lead.

These tests build a step, stamp it over its own final words, and then edit it -
the sequence a human actually performs. They are deliberately pure: no store,
no provider, no campaign row. The unit under test is the gate.
"""
import copy as _copy
import unittest

from src import approval, heyreachfactory


def _step(key, action, note):
    """A LinkedIn step stamped over the words it actually carries."""
    step = {"key": key, "day": 1, "channel": "linkedin",
            "linkedin_action": action, "generated": True, "note": note}
    step["approval"] = {"by": "operator", "at": "2026-09-17T00:00:00",
                        "fingerprint": approval.fingerprint(step)}
    return step


# Every role the graph requires, so a `missing` list can be read as "this one
# step failed" rather than "the fixture was never complete".
NOTES = {
    "li1": ("connect", "Hi - would value comparing notes on delivery margin."),
    "li2": ("message", "Thanks for connecting. One thing I keep seeing."),
    "li3": ("message", "Agencies your size usually find this out late."),
    "li4": ("message", "A short walkthrough is the fastest way to judge it."),
    "li5": ("message", "Last note from me either way."),
}


def _source(contact_key="pat"):
    return {"id": "acme", "cadence": {
        contact_key: {key: _step(key, action, note)
                      for key, (action, note) in NOTES.items()}}}


class TheStampIsCheckedAgainstTheWords(unittest.TestCase):

    def setUp(self):
        self.source = _source()
        self.steps = self.source["cadence"]["pat"]

    # ------------------------------------------------------------- positive

    def test_a_step_stamped_over_its_own_words_yields_them(self):
        """Without this the negative tests below would be vacuous: a gate that
        refuses everything proves nothing about edits."""
        step = self.steps["li1"]
        self.assertEqual(heyreachfactory._step_copy(step), step["note"])
        copy, missing = heyreachfactory.assemble_linkedin_copy(
            self.source, "pat")
        self.assertEqual(missing, [])
        self.assertEqual(copy["connection_note"]["messages"], [step["note"]])

    # ------------------------------------------------------------- negative

    def test_a_note_edited_after_approval_yields_no_copy(self):
        """THE HARDENED BEHAVIOUR. The stamp still sits on the step; the words
        underneath it are not the ones it was taken over."""
        step = self.steps["li1"]
        stamp = _copy.deepcopy(step["approval"])
        step["note"] = step["note"] + " P.S. one more thing."
        self.assertEqual(step["approval"], stamp,
                         "the edit must leave the stamp in place - a step "
                         "that loses its approval would refuse for the "
                         "wrong reason")
        self.assertIsNone(heyreachfactory._step_copy(step))

    def test_the_edited_step_reaches_missing_rather_than_a_prospect(self):
        """`_step_copy` returning None is only useful if the assembler reports
        it. The edited step must appear in `missing` for every role it fills,
        and its words must appear nowhere in the copy block."""
        edited = " ".join([self.steps["li2"]["note"], "and another thought."])
        self.steps["li2"]["note"] = edited
        copy, missing = heyreachfactory.assemble_linkedin_copy(
            self.source, "pat")
        self.assertEqual(sorted(missing),
                         [("pat", "li2", "connected_1"),
                          ("pat", "li2", "message_2")])
        self.assertNotIn("connected_1", copy)
        self.assertNotIn("message_2", copy)
        for block in copy.values():
            self.assertNotIn(edited, block["messages"])
            self.assertNotEqual(block["fallbackMessage"], edited)
        # The other steps are untouched and still stage.
        self.assertEqual(copy["connection_note"]["messages"],
                         [self.steps["li1"]["note"]])

    def test_the_refusal_names_the_contact_the_step_and_the_role(self):
        """`_refuse_missing` is what the live path raises on, so the report
        `assemble_linkedin_copy` produces has to be usable."""
        self.steps["li1"]["note"] = "an entirely different connection note"
        _copy_block, missing = heyreachfactory.assemble_linkedin_copy(
            self.source, "pat")
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            heyreachfactory._refuse_missing(missing)
        text = str(caught.exception)
        self.assertIn("'pat'", text)
        self.assertIn("'li1'", text)
        self.assertIn("'connection_note'", text)

    def test_a_stamp_moved_from_another_step_yields_no_copy(self):
        """An approval is not a token. li2's stamp on li3 certifies li2's
        words, and li3 is the step being shipped."""
        self.assertNotEqual(self.steps["li2"]["note"],
                            self.steps["li3"]["note"])
        self.steps["li3"]["approval"] = _copy.deepcopy(
            self.steps["li2"]["approval"])
        self.assertIsNone(heyreachfactory._step_copy(self.steps["li3"]))

    def test_an_approval_with_no_fingerprint_yields_no_copy(self):
        self.steps["li1"]["approval"] = {"by": "operator",
                                         "at": "2026-09-17T00:00:00"}
        self.assertIsNone(heyreachfactory._step_copy(self.steps["li1"]))

    def test_no_approval_at_all_yields_no_copy(self):
        self.steps["li1"].pop("approval", None)
        self.assertIsNone(heyreachfactory._step_copy(self.steps["li1"]))


if __name__ == "__main__":
    unittest.main()
