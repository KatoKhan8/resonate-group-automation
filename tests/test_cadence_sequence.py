"""The cadence a campaign runs, which until now was a module constant.

`cadence.STEPS` decided which steps every contact of every record in every
campaign in every workspace received. Seven, always, with fixed days and
fixed channels. Cadence length was not a variable in this system, which is
why no experiment could compare four steps against seven.

`steps_for` makes it a property of the campaign. The tests that matter
here are not the new capability - they are the three properties that must
survive it, because `cadence.build` is read by eligibility, push,
approval, fatigue, QA, the outreach preview and the account view.

**A campaign with no cadence behaves identically.** Not approximately. One
test builds the whole timeline both ways and compares it.

**Step keys are identity.** Approvals are fingerprinted per key, events
carry it, `push_id` is `record:contact:step:channel`. A reused key
inherits another step's history.

**Days ascend.** `_due` compares a step's day against a batch day, so a
sequence that went backwards would let a later step fire first.
"""
import unittest

from src import cadence, store
from tests.campaignbase import CampaignTest, contact

# Every step template-backed rather than `generated`. A generated step with
# no stored draft is correctly absent from the timeline - that is existing
# behaviour and not what these tests are about.
FOUR = [{"key": "s1", "day": 1, "channel": "email", "template": "persona_pain"},
        {"key": "s2", "day": 3, "channel": "email", "template": "persona_pain"},
        {"key": "s3", "day": 7, "channel": "email", "template": "comparable_proof"},
        {"key": "s4", "day": 12, "channel": "email", "template": "breakup"}]


class AbsenceMeansTheCadenceEveryCampaignRan(unittest.TestCase):

    def test_no_campaign_returns_the_constant_itself(self):
        self.assertIs(cadence.steps_for(), cadence.STEPS)

    def test_a_campaign_without_one_returns_the_constant_itself(self):
        self.assertIs(cadence.steps_for({"campaign_id": "c1"}), cadence.STEPS)

    def test_an_explicit_none_returns_the_constant(self):
        self.assertIs(cadence.steps_for({cadence.CADENCE_KEY: None}),
                      cadence.STEPS)

    def test_present_and_empty_is_refused_rather_than_replaced(self):
        """Configured zero steps and configured nothing are different
        things. Running seven instead is the silent substitution this
        function exists to refuse."""
        with self.assertRaises(cadence.BadCadence):
            cadence.steps_for({cadence.CADENCE_KEY: []})


class TheOldPathIsUnchanged(CampaignTest):
    """The property the rest of the system depends on."""

    def record(self):
        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        self.draft_everything(recs)
        store.save(recs)
        return store.load()[0], store.load()

    def test_a_campaign_with_no_cadence_builds_the_same_timeline(self):
        """Built both ways and compared whole. An assertion on the step
        count would pass while the days, channels, templates or statuses
        had all moved."""
        rec, recs = self.record()
        without = cadence.build(rec, self.config, recs=recs)
        with_empty_campaign = cadence.build(rec, self.config, recs=recs,
                                            campaign={"campaign_id": "c1"})
        self.assertEqual(without, with_empty_campaign)

    def test_it_still_has_the_seven_steps_it_always_had(self):
        rec, recs = self.record()
        steps = cadence.build(rec, self.config,
                              recs=recs)["contacts"]["acme-champ"]
        self.assertEqual(len(steps), len(cadence.STEPS))
        self.assertEqual(sorted(steps), sorted(s["key"]
                                               for s in cadence.STEPS))


class ACampaignMayCarryItsOwnSequence(CampaignTest):

    def record(self):
        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        store.save(recs)
        return store.load()[0], store.load()

    def test_a_four_step_campaign_builds_four_steps(self):
        rec, recs = self.record()
        steps = cadence.build(rec, self.config, recs=recs,
                              campaign={cadence.CADENCE_KEY: FOUR})
        self.assertEqual(sorted(steps["contacts"]["acme-champ"]),
                         ["s1", "s2", "s3", "s4"])

    def test_the_days_come_from_the_campaign(self):
        rec, recs = self.record()
        steps = cadence.build(rec, self.config, recs=recs,
                              campaign={cadence.CADENCE_KEY: FOUR})
        days = {key: step["day"]
                for key, step in steps["contacts"]["acme-champ"].items()}
        self.assertEqual(days, {"s1": 1, "s2": 3, "s3": 7, "s4": 12})

    def library(self):
        """`cadence:` has always held a name. The sequences live beside it
        under that name, so the existing key keeps its existing meaning."""
        return dict(self.config,
                    cadence="demo_default",
                    cadences={"demo_default": {"steps": FOUR}})

    def test_a_client_config_may_define_its_named_cadence(self):
        rec, recs = self.record()
        steps = cadence.build(rec, self.library(), recs=recs)
        self.assertEqual(len(steps["contacts"]["acme-champ"]), 4)

    def test_a_name_with_no_definition_falls_through_to_the_constant(self):
        """What every client file does today: names a cadence, defines
        nothing. The first version of this read the name as a dict and
        crashed on all of them."""
        self.assertIs(cadence.steps_for({}, self.config), cadence.STEPS)

    def test_a_library_with_no_matching_name_falls_through(self):
        config = dict(self.config, cadence="something_else",
                      cadences={"demo_default": {"steps": FOUR}})
        self.assertIs(cadence.steps_for({}, config), cadence.STEPS)

    def test_the_campaign_outranks_the_client_config(self):
        """One campaign testing a different sequence must not be
        overridden by the workspace default it is being compared against."""
        found = cadence.steps_for({cadence.CADENCE_KEY: FOUR[:2]},
                                  self.library())
        self.assertEqual(len(found), 2)


class ASequenceIsCheckedBeforeItIsRun(unittest.TestCase):

    def refuses(self, steps, needle=None):
        with self.assertRaises(cadence.BadCadence) as caught:
            cadence.validate_steps(steps)
        if needle:
            self.assertIn(needle, str(caught.exception))

    def test_a_repeated_step_key_is_refused(self):
        """A step key is identity. A repeat inherits the other step's
        approvals and events, which is worse than a crash."""
        self.refuses([{"key": "a", "day": 1, "channel": "email"},
                      {"key": "a", "day": 3, "channel": "email"}],
                     "identity")

    def test_days_that_go_backwards_are_refused(self):
        self.refuses([{"key": "a", "day": 5, "channel": "email"},
                      {"key": "b", "day": 1, "channel": "email"}],
                     "day 1")

    def test_the_same_day_twice_is_allowed(self):
        """Two touches on one day is a real cadence - an email and a
        LinkedIn note, say. Only going backwards is wrong."""
        found = cadence.validate_steps(
            [{"key": "a", "day": 3, "channel": "email"},
             {"key": "b", "day": 3, "channel": "linkedin"}])
        self.assertEqual(len(found), 2)

    def test_a_channel_this_build_cannot_send_on_is_refused(self):
        self.refuses([{"key": "a", "day": 1, "channel": "sms"}], "sms")

    def test_a_step_missing_a_field_is_refused(self):
        for step in ({"day": 1, "channel": "email"},
                     {"key": "a", "channel": "email"},
                     {"key": "a", "day": 1}):
            self.refuses([step])

    def test_a_day_that_is_not_a_number_is_refused(self):
        self.refuses([{"key": "a", "day": "soon", "channel": "email"}])

    def test_something_that_is_not_a_step_is_refused(self):
        self.refuses([["not", "a", "step"]])

    def test_a_valid_sequence_comes_back_as_a_tuple(self):
        found = cadence.validate_steps(FOUR)
        self.assertIsInstance(found, tuple)
        self.assertEqual(len(found), 4)

    def test_it_does_not_mutate_what_it_was_given(self):
        original = [dict(step) for step in FOUR]
        cadence.validate_steps(FOUR)
        self.assertEqual(FOUR, original)


class TheShapeReadsInOneLine(unittest.TestCase):
    """Four of these stacked read faster than four tables, which is what
    an operator comparing arms is actually doing."""

    def test_an_email_only_sequence(self):
        self.assertEqual(cadence.describe_steps(FOUR), "E -> E -> E -> E")

    def test_a_multichannel_sequence(self):
        self.assertEqual(
            cadence.describe_steps(
                [{"channel": "email"}, {"channel": "linkedin"},
                 {"channel": "email"}]),
            "E -> LI -> E")

    def test_the_cadence_every_campaign_ran(self):
        self.assertEqual(cadence.describe_steps(cadence.STEPS),
                         "E -> LI -> E -> LI -> E -> E -> E")

    def test_nothing_describes_as_nothing(self):
        self.assertEqual(cadence.describe_steps([]), "")


if __name__ == "__main__":
    unittest.main()
