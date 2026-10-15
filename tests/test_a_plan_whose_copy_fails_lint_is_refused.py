"""A plan whose copy fails the lint is refused, not staged.

`bisonfactory._refuse_copylint` is the hinge between the copy lint and the
push: it runs the batch lint over what the stage is ABOUT to write and
refuses the whole stage when the lint refuses - rather than skipping the
offenders, because a campaign meant for fifty that quietly stages
forty-one is a campaign whose reach nobody stated. It runs before any
provider call, so a refusal costs nothing and a pass that should have
refused costs the estate.

The fixture is the smallest plan the lint can refuse: one lead, two steps
of copy, and no research behind either - `pack_for` admits no facts for a
record that does not exist, so the lead's opener names nothing the pack
supports and `step1_without_pack_fact` fires. That is the 09-23 shape in
miniature: fluent words with no admitted fact under them.

The property is the refusal itself, and that it travels: the exception
names the lead and the rule, and the structured verdict lands in the
report the caller holds, so a refusal is never just a string to be caught
and dropped.
"""
import unittest

from src import bisonfactory

PLAN = {
    "client": "productive",
    "provider_sequence": [
        {"order": 1, "wait_in_days": 3},
        {"order": 2, "wait_in_days": 4},
    ],
    "leads": [{
        "record_id": "rec-1", "contact_key": "ck-1", "persona": None,
        "copy": [
            {"body": "<p>Hi Anna, just following up on my note from last "
                     "week.</p>"},
            {"body": "<p>Did any of that land, or is this the wrong thread "
                     "for it?</p>"},
        ],
    }],
}


class APlanWhoseCopyFailsLintIsRefused(unittest.TestCase):

    def test_the_stage_is_refused_naming_the_lead_and_the_rule(self):
        report = {}
        with self.assertRaises(bisonfactory.FactoryRefused) as raised:
            bisonfactory._refuse_copylint(PLAN, [], report)
        text = str(raised.exception)
        self.assertIn(
            "rec-1/ck-1", text,
            "the refusal must name the offending lead: "
            f"{text[:300]}")
        self.assertIn(
            "step1_without_pack_fact", text,
            "the refusal must name the rule that fired: "
            f"{text[:300]}")

        found = report.get("copylint") or {}
        self.assertTrue(
            found.get("refused"),
            "the structured verdict did not travel with the refusal: the "
            f"report holds {found}")


if __name__ == "__main__":
    unittest.main()
