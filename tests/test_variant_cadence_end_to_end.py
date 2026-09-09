"""Two dimensions at once: which sequence, and which wording.

`src/cadencearms.py` tests what a sequence *is* - four steps against
seven. `src/variants.py` tests what a message *says* - five wordings of one
step. They are separate experiments and must stay separately reported, but
they run on the same contact at the same time, and until now the second one
did not run at all: `variants.apply_to_step` had no caller in `src/`, so no
step carried a `variant_id`, so no confirmed touch could carry one, so
every copy experiment reported INSUFFICIENT_DATA for ever - which is
indistinguishable from an evaluator waiting for volume.

The chain this file walks, one link per class:

    campaign -> arm -> step -> variant -> approval -> payload ->
    confirmed event -> attribution

Variants live on the step spec, beside `template` and
`variant_if_accepted`, which is where a sequence already keeps the question
of which words a step uses.
"""
import unittest

from src import (approval, cadence, campaigns, events, push, store,
                 variants)
from tests.campaignbase import CLIENT, CampaignTest

STYLES = ("short_direct", "casual", "professional", "consultative",
          "problem_led")


def five(step_key):
    """Five wordings of one step, distinguishable in the copy itself."""
    return [variants.variant(f"{step_key}-{style}", style,
                             subject=f"{style} subject",
                             body=f"This is the {style} wording.\n\nBest,\nZ",
                             status=variants.ACTIVE)
            for style in STYLES]


def sequence(keys_and_days, with_variants_on=()):
    steps = []
    for key, day in keys_and_days:
        step = {"key": key, "day": day, "channel": "email",
                "template": "persona_pain"}
        if key in with_variants_on:
            step[cadence.VARIANTS_KEY] = five(key)
        steps.append(step)
    return steps


FOUR = sequence((("day1", 1), ("day3", 3), ("day5", 5), ("day8", 8)),
                with_variants_on=("day5",))
SEVEN = sequence((("day1", 1), ("day3", 3), ("day5", 5), ("day8", 8),
                  ("day10", 10), ("day15", 15), ("day21", 21)),
                 with_variants_on=("day5",))


class TwoDimensions(CampaignTest):

    def setUp(self):
        super().setUp()
        recs = self.seed_records()
        store.save(recs)
        self.recs = store.load()
        self.campaign = self.make_campaign(self.recs)
        self.campaign[cadence.CADENCE_KEY] = list(FOUR)
        self.save_campaign(self.campaign)
        self.rec = self.recs[0]
        self.key = self.rec["contacts"][0]["key"]

    def build(self, campaign=None):
        timeline = cadence.build(self.rec, self.config, recs=self.recs,
                                 campaign=campaign or self.campaign)
        return (timeline["contacts"] or {}).get(self.key) or {}


class TheStepCarriesAVariant(TwoDimensions):

    def test_the_experiment_step_gets_one(self):
        step = self.build()["day5"]
        self.assertIn(step["variant_id"], {v["variant_id"] for v in five("day5")})
        self.assertIn(step["variant_style"], STYLES)

    def test_its_copy_is_the_variants_copy_and_not_the_template(self):
        step = self.build()["day5"]
        self.assertEqual(step["subject"], f"{step['variant_style']} subject")
        self.assertIn(step["variant_style"], step["body"])

    def test_a_step_with_no_experiment_carries_nothing(self):
        """Absence of a variant is not variant None: a step outside the
        experiment must be indistinguishable from one in a campaign that
        has no experiment at all."""
        self.assertNotIn("variant_id", self.build()["day1"])

    def test_the_same_contact_resolves_the_same_way_every_time(self):
        first = self.build()["day5"]["variant_id"]
        for _ in range(5):
            self.assertEqual(self.build()["day5"]["variant_id"], first)

    def test_different_contacts_do_not_all_land_on_one(self):
        """Deterministic is not constant. If every contact bucketed the
        same way the experiment would have one arm and look healthy."""
        seen = set()
        for index in range(40):
            rec = dict(self.rec, id=f"r{index}",
                       contacts=[dict(self.rec["contacts"][0],
                                      key=f"c{index}")])
            timeline = cadence.build(rec, self.config, campaign=self.campaign)
            seen.add(timeline["contacts"][f"c{index}"]["day5"]["variant_id"])
        self.assertGreater(len(seen), 1)


class TheTwoExperimentsDoNotContaminateEachOther(TwoDimensions):
    """A cadence arm decides how many steps; a copy variant decides the
    words of one of them. Reported together they would be one experiment
    with twenty cells and no power."""

    def test_the_arm_changes_the_step_count_and_not_the_wording(self):
        seven = dict(self.campaign, campaign_id="camp-1")
        seven[cadence.CADENCE_KEY] = list(SEVEN)
        four_steps, seven_steps = self.build(), self.build(seven)

        self.assertEqual(len(four_steps), 4)
        self.assertEqual(len(seven_steps), 7)
        # Same campaign id, same contact, same step: the sequence around it
        # got longer and the wording did not move.
        self.assertEqual(four_steps["day5"]["variant_id"],
                         seven_steps["day5"]["variant_id"])

    def test_the_variant_does_not_change_the_step_count(self):
        without = [dict(s) for s in FOUR]
        for step in without:
            step.pop(cadence.VARIANTS_KEY, None)
        plain = dict(self.campaign)
        plain[cadence.CADENCE_KEY] = without
        self.assertEqual(sorted(self.build(plain)), sorted(self.build()))


class TheApprovalCoversTheWordsThatWereChosen(TwoDimensions):

    def test_the_fingerprint_moves_between_variants(self):
        """An approval is of words. Two variants are different words, so
        approving one may never carry over to another."""
        step = self.build()["day5"]
        other = next(v for v in five("day5")
                     if v["variant_id"] != step["variant_id"])
        self.assertNotEqual(approval.fingerprint(step),
                            approval.fingerprint(
                                variants.apply_to_step(step, other)))

    def test_the_fingerprint_is_stable_across_rebuilds(self):
        """And it has to be, or every rebuild would invalidate its own
        approval - the assignment is deterministic precisely so this
        holds."""
        self.assertEqual(approval.fingerprint(self.build()["day5"]),
                         approval.fingerprint(self.build()["day5"]))

    def test_a_recorded_variant_outranks_a_reallocation(self):
        """Once somebody has been put in a cell the experiment has to
        remember it, or shifting traffic tomorrow rewrites who was in which
        cell yesterday and every rate computed from it is wrong."""
        first = self.build()["day5"]["variant_id"]
        other = next(v["variant_id"] for v in five("day5")
                     if v["variant_id"] != first)
        self.rec.setdefault("cadence", {}).setdefault(self.key, {})["day5"] = {
            "variant_id": other}
        self.assertEqual(self.build()["day5"]["variant_id"], other)


class TheConfirmedTouchCarriesIt(TwoDimensions):
    """The other half of the wire, which was already connected and had
    nothing to carry."""

    def test_a_pushed_step_records_the_variant_on_its_event(self):
        step = self.build()["day5"]
        self.rec.setdefault("cadence", {}).setdefault(self.key, {})["day5"] = \
            dict(step)
        push.mark_pushed(self.rec, self.key, "day5",
                         f"{self.rec['id']}:{self.key}:day5:email", sent=step)
        entry = next(e for e in self.rec["events"]
                     if e["type"] == events.PUSH_MARKED)
        self.assertEqual(entry["variant_id"], step["variant_id"])
        self.assertEqual(entry["variant_style"], step["variant_style"])

    def test_the_evaluator_can_finally_see_a_denominator(self):
        """`results_from` reads exposures off confirmed touches. With
        nothing writing `variant_id` it counted zero for every variant,
        for ever."""
        for index in range(12):
            rec = dict(self.rec, id=f"r{index}", events=[], cadence={},
                       contacts=[dict(self.rec["contacts"][0],
                                      key=f"c{index}")])
            step = (cadence.build(rec, self.config, campaign=self.campaign)
                    ["contacts"][f"c{index}"]["day5"])
            rec.setdefault("cadence", {}).setdefault(f"c{index}", {})["day5"] \
                = dict(step)
            push.mark_pushed(rec, f"c{index}", "day5",
                             f"{rec['id']}:c{index}:day5:email", sent=step)
            self.recs.append(rec)

        found = variants.results_from(self.recs, "day5")
        self.assertTrue(found)
        self.assertEqual(sum(row["exposures"] for row in found.values()), 12)


class ABadExperimentIsRefusedRatherThanRun(CampaignTest):

    def refuses(self, step):
        with self.assertRaises(cadence.BadCadence) as caught:
            cadence.validate_steps([step])
        return str(caught.exception)

    def test_a_generated_step_may_not_carry_variants(self):
        """Its copy was written for this contact. A variant would replace
        it wholesale, which is not a variant of anything."""
        why = self.refuses({"key": "day1", "day": 1, "channel": "email",
                            "generated": True,
                            cadence.VARIANTS_KEY: five("day1")})
        self.assertIn("generated", why)

    def test_two_variants_may_not_share_an_id(self):
        entries = five("day5")
        entries[1] = dict(entries[1], variant_id=entries[0]["variant_id"])
        self.assertIn("share the id",
                      self.refuses({"key": "day5", "day": 5,
                                    "channel": "email",
                                    "template": "persona_pain",
                                    cadence.VARIANTS_KEY: entries}))

    def test_a_variant_with_no_copy_is_refused(self):
        entries = five("day5")
        entries[2] = dict(entries[2], subject=None, body=None, note=None)
        self.assertIn("no copy",
                      self.refuses({"key": "day5", "day": 5,
                                    "channel": "email",
                                    "template": "persona_pain",
                                    cadence.VARIANTS_KEY: entries}))

    def test_a_valid_experiment_is_accepted(self):
        """So the refusals above are refusals and not a blanket ban."""
        found = cadence.validate_steps(
            [{"key": "day5", "day": 5, "channel": "email",
              "template": "persona_pain", cadence.VARIANTS_KEY: five("day5")}])
        self.assertEqual(len(found), 1)


class WithoutACampaignNothingIsAssigned(TwoDimensions):
    """An assignment that cannot say which experiment it belongs to cannot
    be reported, and an unreportable assignment is worse than none."""

    def test_a_step_carrying_variants_is_still_not_assigned_one(self):
        """The guard, asked directly.

        Building without a campaign falls back to a sequence that has no
        variants at all, so a timeline assertion would pass whether the
        guard existed or not. A sequence named in a client config *can*
        carry variants and be read with no campaign, and that is the case
        this refuses.
        """
        spec = dict(FOUR[2])
        self.assertTrue(spec[cadence.VARIANTS_KEY])
        self.assertIsNone(cadence.variant_for(spec, None, "c1"))
        self.assertIsNone(cadence.variant_for(spec, {}, "c1"))
        self.assertIsNone(
            cadence.variant_for(spec, {"campaign_id": ""}, "c1"))

    def test_and_is_assigned_one_the_moment_there_is_a_campaign(self):
        """So the refusal above is about the campaign and not about the
        step."""
        self.assertIsNotNone(
            cadence.variant_for(dict(FOUR[2]), {"campaign_id": "c-1"}, "c1"))

    def test_a_sequence_read_without_a_campaign_assigns_no_variant(self):
        timeline = cadence.build(self.rec, self.config, recs=self.recs)
        for step in timeline["contacts"][self.key].values():
            self.assertNotIn("variant_id", step)


if __name__ == "__main__":
    unittest.main()
