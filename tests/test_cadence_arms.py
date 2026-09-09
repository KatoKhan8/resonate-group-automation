"""Comparing four steps against seven, and the link that makes it real.

The failure this file exists to prevent is the one this codebase keeps
finding in itself: an experiment that assigns, reports, and changes
nothing about what was sent. So the test that matters most is not that
assignment is deterministic - it is that a contact in the four-step arm
receives four steps and a contact in the seven-step arm receives seven,
built by the same `cadence.build` every campaign runs through.

The second thing this guards is independence. Two people at one company
are not two observations: `accountpolicy` couples them, a reply from one
pauses the other, and fatigue counts them together. The default unit is
the account for that reason, and a test holds it.
"""
import unittest

from src import cadence, cadencearms as arms, store
from tests.campaignbase import CampaignTest, contact

FOUR = [{"key": "s1", "day": 1, "channel": "email", "template": "persona_pain"},
        {"key": "s2", "day": 3, "channel": "email", "template": "persona_pain"},
        {"key": "s3", "day": 7, "channel": "email",
         "template": "comparable_proof"},
        {"key": "s4", "day": 12, "channel": "email", "template": "breakup"}]

SEVEN = FOUR + [
    {"key": "s5", "day": 18, "channel": "email", "template": "persona_pain"},
    {"key": "s6", "day": 25, "channel": "email", "template": "comparable_proof"},
    {"key": "s7", "day": 35, "channel": "email", "template": "breakup"}]

MULTI = [{"key": "m1", "day": 1, "channel": "email", "template": "persona_pain"},
         {"key": "m2", "day": 3, "channel": "linkedin",
          "template": "linkedin_intro"},
         {"key": "m3", "day": 7, "channel": "email",
          "template": "comparable_proof"}]


def four_vs_seven(**kw):
    return arms.experiment(
        "cad-1",
        [arms.arm("four", "4 steps", FOUR, approach="direct"),
         arms.arm("seven", "7 steps", SEVEN, approach="direct")],
        testing="cadence length", **kw)


def a_record(rec_id="acme", contacts=None):
    return {"id": rec_id, "company": "Acme", "domain": "acme.test",
            "client": "demo",
            "contacts": contacts if contacts is not None
                        else [{"key": "a", "name": "A Person",
                               "email": "a@acme.test"}]}


class AnArmChangesWhatIsSent(CampaignTest):
    """The link the whole thing rests on."""

    def built(self, rec, exp):
        arms.assign(exp, rec)
        return cadence.build(rec, self.config, recs=[rec],
                             campaign={arms.EXPERIMENT_KEY: exp})

    def test_a_four_step_arm_builds_four_steps(self):
        exp = arms.experiment("only-four",
                              [arms.arm("four", "4", FOUR),
                               arms.arm("four-b", "4 again", FOUR)])
        rec = a_record()
        steps = self.built(rec, exp)["contacts"]["a"]
        self.assertEqual(sorted(steps), ["s1", "s2", "s3", "s4"])

    def test_a_seven_step_arm_builds_seven_steps(self):
        exp = arms.experiment("only-seven",
                              [arms.arm("seven", "7", SEVEN),
                               arms.arm("seven-b", "7 again", SEVEN)])
        rec = a_record()
        steps = self.built(rec, exp)["contacts"]["a"]
        self.assertEqual(len(steps), 7)

    def test_two_accounts_in_different_arms_get_different_sequences(self):
        """The comparison itself. Both records go through the same
        `cadence.build`; only the assignment differs."""
        exp = four_vs_seven()
        lengths = {}
        for i in range(40):
            rec = a_record(f"acme-{i}")
            arms.assign(exp, rec)
            timeline = cadence.build(rec, self.config, recs=[rec],
                                     campaign={arms.EXPERIMENT_KEY: exp})
            lengths.setdefault(rec[arms.ASSIGNMENT_KEY]["arm_id"], set()).add(
                len(timeline["contacts"]["a"]))
        self.assertEqual(lengths, {"four": {4}, "seven": {7}})

    def test_a_campaign_with_no_experiment_runs_the_cadence_it_always_ran(self):
        """Asserted on which sequence was used rather than on how many
        steps expanded. The fixture contact has no LinkedIn profile, so two
        of the constant's steps correctly do not expand - counting them
        would be measuring the contact, not the cadence."""
        rec = a_record()
        timeline = cadence.build(rec, self.config, recs=[rec])
        keys = set(timeline["contacts"]["a"])
        self.assertTrue(keys)
        self.assertTrue(keys <= {s["key"] for s in cadence.STEPS})
        self.assertEqual(keys & {s["key"] for s in SEVEN}, set())

    def test_an_unassigned_unit_falls_back_rather_than_guessing(self):
        """Expansion happens on every page load. An assignment written
        there would be an assignment made by whoever happened to look."""
        exp = four_vs_seven()
        rec = a_record()
        self.assertIsNone(arms.steps_for({arms.EXPERIMENT_KEY: exp}, rec,
                                         rec["contacts"][0]))
        timeline = cadence.build(rec, self.config, recs=[rec],
                                 campaign={arms.EXPERIMENT_KEY: exp})
        keys = set(timeline["contacts"]["a"])
        self.assertTrue(keys <= {s["key"] for s in cadence.STEPS},
                        "an unassigned unit runs the cadence it always ran")
        self.assertEqual(keys & {s["key"] for s in SEVEN}, set())
        self.assertNotIn(arms.ASSIGNMENT_KEY, rec)


class TheAccountIsTheUnit(unittest.TestCase):
    """Two people at one company are not two observations."""

    def test_the_default_unit_is_the_account(self):
        self.assertEqual(four_vs_seven()["unit"], arms.ACCOUNT)

    def test_everybody_at_one_account_gets_the_same_arm(self):
        exp = four_vs_seven()
        rec = a_record(contacts=[{"key": "john", "email": "j@acme.test"},
                                 {"key": "sarah", "email": "s@acme.test"},
                                 {"key": "mike", "email": "m@acme.test"}])
        arms.assign(exp, rec)
        seen = {arms.steps_for({arms.EXPERIMENT_KEY: exp}, rec, person)[0]["key"]
                for person in rec["contacts"]}
        self.assertEqual(len(seen), 1)

    def test_the_contact_unit_can_split_them(self):
        """Available, and wrong for anything account-based. It exists
        because a single-contact audience is a real shape."""
        exp = four_vs_seven(unit=arms.CONTACT)
        rec = a_record(contacts=[{"key": f"c{i}", "email": f"c{i}@acme.test"}
                                 for i in range(30)])
        for person in rec["contacts"]:
            arms.assign(exp, rec, person)
        seen = {person[arms.ASSIGNMENT_KEY]["arm_id"]
                for person in rec["contacts"]}
        self.assertEqual(seen, {"four", "seven"})

    def test_the_unit_key_is_the_record_for_an_account_experiment(self):
        exp = four_vs_seven()
        rec = a_record()
        self.assertEqual(arms.unit_key(exp, rec, rec["contacts"][0]), "acme")

    def test_a_unit_with_no_key_is_refused_rather_than_pooled(self):
        """Assigning on a missing key would put every such contact in one
        arm, which looks like a result."""
        exp = four_vs_seven()
        entry, why = arms.choose(exp, {"contacts": []})
        self.assertIsNone(entry)
        self.assertIn("randomise", why)


class AssignmentIsStickyAndDeterministic(unittest.TestCase):

    def test_the_same_account_always_lands_in_the_same_arm(self):
        exp = four_vs_seven()
        first = arms.choose(exp, a_record())[0]["arm_id"]
        for _ in range(5):
            self.assertEqual(arms.choose(exp, a_record())[0]["arm_id"], first)

    def test_a_recorded_assignment_outranks_a_changed_allocation(self):
        """A contact three steps into a four-step arm may not move because
        somebody edited the split."""
        exp = four_vs_seven()
        rec = a_record()
        arms.assign(exp, rec)
        original = rec[arms.ASSIGNMENT_KEY]["arm_id"]

        shifted = four_vs_seven(allocation={"four": 0.0, "seven": 1.0},
                                allocation_version=2)
        self.assertEqual(arms.choose(shifted, rec)[0]["arm_id"], original)

    def test_assigning_twice_writes_once(self):
        exp = four_vs_seven()
        rec = a_record()
        first = arms.assign(exp, rec)
        second = arms.assign(exp, rec)
        self.assertEqual(first["at"], second["at"])

    def test_an_assignment_from_another_experiment_is_not_this_one(self):
        rec = a_record()
        arms.assign(four_vs_seven(), rec)
        other = arms.experiment("cad-2", [arms.arm("a", "A", FOUR),
                                          arms.arm("b", "B", SEVEN)])
        self.assertIsNone(arms.recorded(other, rec))

    def test_the_split_is_roughly_even_by_default(self):
        exp = four_vs_seven()
        counts = {"four": 0, "seven": 0}
        for i in range(400):
            counts[arms.choose(exp, a_record(f"co-{i}"))[0]["arm_id"]] += 1
        self.assertGreater(min(counts.values()), 120)

    def test_the_allocation_is_honoured_when_stated(self):
        exp = four_vs_seven(allocation={"four": 0.9, "seven": 0.1})
        counts = {"four": 0, "seven": 0}
        for i in range(400):
            counts[arms.choose(exp, a_record(f"co-{i}"))[0]["arm_id"]] += 1
        self.assertGreater(counts["four"], counts["seven"] * 3)

    def test_the_record_carries_what_it_was_assigned_and_when(self):
        exp = four_vs_seven()
        rec = a_record()
        found = arms.assign(exp, rec)
        for field in ("experiment_id", "arm_id", "unit", "unit_key",
                      "allocation_version", "at", "why"):
            self.assertIn(field, found)


class AnArmCannotForceAChannel(unittest.TestCase):

    def email_only(self):
        return {"key": "a", "email": "a@acme.test"}

    def both(self):
        return {"key": "b", "email": "b@acme.test",
                "linkedin": "https://www.linkedin.com/in/b"}

    def test_a_strict_multichannel_arm_refuses_an_email_only_contact(self):
        entry = arms.arm("multi", "multichannel", MULTI)
        ok, why = arms.eligible_for(entry, self.email_only())
        self.assertFalse(ok)
        self.assertIn("linkedin", why)
        # The strict reason specifically. Both modes refuse this contact and
        # both messages mention the channel, so an assertion on the channel
        # alone cannot tell which rule acted.
        self.assertIn("strict arm", why)

    def test_a_strict_arm_ignores_a_fallback_it_was_given(self):
        """Strict means every channel, and a fallback on a strict arm is a
        contradiction rather than a permission. Silently honouring it would
        make the mode decorative."""
        entry = arms.arm("multi", "multichannel", MULTI,
                         fallback={"linkedin": "email"})
        ok, why = arms.eligible_for(entry, self.email_only())
        self.assertFalse(ok)
        self.assertIn("strict arm", why)

    def test_it_accepts_somebody_with_both(self):
        entry = arms.arm("multi", "multichannel", MULTI)
        self.assertTrue(arms.eligible_for(entry, self.both())[0])

    def test_an_email_only_arm_is_open_to_everybody(self):
        entry = arms.arm("four", "4 steps", FOUR)
        self.assertTrue(arms.eligible_for(entry, self.email_only())[0])

    def test_an_adaptive_arm_needs_a_usable_fallback(self):
        entry = arms.arm("multi", "multichannel", MULTI, mode=arms.ADAPTIVE)
        self.assertFalse(arms.eligible_for(entry, self.email_only())[0])

        stated = arms.arm("multi", "multichannel", MULTI,
                          mode=arms.ADAPTIVE,
                          fallback={"linkedin": "email"})
        ok, why = arms.eligible_for(stated, self.email_only())
        self.assertTrue(ok)
        self.assertIn("falling back", why)

    def test_an_ineligible_contact_is_never_assigned_to_that_arm(self):
        exp = arms.experiment("mix", [arms.arm("email", "email", FOUR),
                                      arms.arm("multi", "multi", MULTI)])
        for i in range(60):
            rec = a_record(f"co-{i}", contacts=[self.email_only()])
            entry, _ = arms.choose(exp, rec, rec["contacts"][0])
            self.assertEqual(entry["arm_id"], "email")

    def test_a_contact_no_arm_can_run_is_refused(self):
        exp = arms.experiment("mix", [arms.arm("multi", "multi", MULTI),
                                      arms.arm("multi-b", "multi", MULTI)])
        rec = a_record(contacts=[self.email_only()])
        entry, why = arms.choose(exp, rec, rec["contacts"][0])
        self.assertIsNone(entry)
        self.assertIn("no arm", why)


class AnExperimentIsCheckedBeforeItRuns(unittest.TestCase):

    def test_one_arm_is_not_a_comparison(self):
        exp = arms.experiment("solo", [arms.arm("a", "A", FOUR)])
        self.assertTrue(any("two arms" in p for p in arms.validate(exp)))

    def test_two_arms_sharing_an_id_are_refused(self):
        exp = arms.experiment("dup", [arms.arm("a", "A", FOUR),
                                      arms.arm("a", "A again", SEVEN)])
        self.assertTrue(any("share the id" in p for p in arms.validate(exp)))

    def test_an_arm_with_an_unrunnable_sequence_is_refused(self):
        exp = arms.experiment(
            "bad", [arms.arm("a", "A", FOUR),
                    arms.arm("b", "B", [{"key": "x", "day": 1,
                                         "channel": "carrier pigeon"}])])
        self.assertTrue(arms.validate(exp))

    def test_an_allocation_that_does_not_sum_to_one_is_refused(self):
        exp = four_vs_seven(allocation={"four": 0.5, "seven": 0.2})
        self.assertTrue(any("sums to" in p for p in arms.validate(exp)))

    def test_an_allocation_naming_an_unknown_arm_is_refused(self):
        exp = four_vs_seven(allocation={"four": 0.5, "ghost": 0.5})
        self.assertTrue(any("ghost" in p for p in arms.validate(exp)))

    def test_an_unknown_unit_is_refused(self):
        exp = four_vs_seven(unit="planet")
        self.assertTrue(any("unit must be" in p for p in arms.validate(exp)))

    def test_a_valid_experiment_has_nothing_to_say(self):
        self.assertEqual(arms.validate(four_vs_seven()), [])

    def test_require_raises_on_a_bad_one(self):
        with self.assertRaises(arms.BadExperiment):
            arms.require(arms.experiment("solo", [arms.arm("a", "A", FOUR)]))


class TheSummaryShowsConfiguredAgainstObserved(unittest.TestCase):

    def test_it_reports_both_numbers(self):
        exp = four_vs_seven()
        recs = [a_record(f"co-{i}") for i in range(50)]
        for rec in recs:
            arms.assign(exp, rec)
        found = arms.summarise(exp, recs=recs)
        self.assertEqual(found["assigned"], 50)
        for row in found["arms"]:
            self.assertIn("configured", row)
            self.assertIn("observed", row)

    def test_it_counts_units_that_were_never_assigned(self):
        exp = four_vs_seven()
        recs = [a_record(f"co-{i}") for i in range(10)]
        for rec in recs[:4]:
            arms.assign(exp, rec)
        found = arms.summarise(exp, recs=recs)
        self.assertEqual(found["assigned"], 4)
        self.assertEqual(found["unassigned"], 6)

    def test_it_carries_the_shape_of_each_arm(self):
        found = arms.summarise(four_vs_seven(), recs=[])
        shapes = {row["arm_id"]: row["shape"] for row in found["arms"]}
        self.assertEqual(shapes["four"], "E -> E -> E -> E")

    def test_it_says_the_two_numbers_are_different_questions(self):
        self.assertIn("different numbers",
                      arms.summarise(four_vs_seven(), recs=[])["note"])


if __name__ == "__main__":
    unittest.main()


class TheBucketRemembersWhichExperimentAndWhichAllocation(unittest.TestCase):
    """Written after a mutation run found nothing guarding either.

    Both are stated in `_bucket`'s docstring as the reason the material has
    three parts, and neither had a test - so either could have been dropped
    and the suite would have stayed green.
    """

    def spread(self, exp, units=200):
        """Which arm each of many accounts lands in."""
        return [arms.choose(exp, a_record(f"r{i}"))[0]["arm_id"]
                for i in range(units)]

    def test_bumping_the_allocation_version_moves_somebody(self):
        """A version exists so a recorded assignment can say which regime
        produced it. If the bucket ignored it, two regimes would produce
        the same split and the version would record nothing."""
        first = self.spread(four_vs_seven(allocation_version=1))
        second = self.spread(four_vs_seven(allocation_version=2))
        self.assertNotEqual(first, second)

    def test_two_experiments_do_not_place_an_account_identically(self):
        """One account in the same relative position in every experiment
        would quietly correlate the results of unrelated tests."""
        one = self.spread(four_vs_seven())
        other = arms.experiment(
            "cad-2",
            [arms.arm("four", "4 steps", FOUR),
             arms.arm("seven", "7 steps", SEVEN)])
        self.assertNotEqual(one, self.spread(other))

    def test_the_same_experiment_places_them_the_same_way_twice(self):
        """So the two differences above are the material changing rather
        than the function being unstable."""
        exp = four_vs_seven()
        self.assertEqual(self.spread(exp), self.spread(exp))


class SharesAreRenormalisedAcrossTheArmsAContactCanBeIn(unittest.TestCase):
    """`choose` says this is why it divides by the eligible total: without
    it, a contact ineligible for the early arms lands on the last one
    purely because the buckets above it are unreachable."""

    def experiment(self):
        """Four arms of a quarter each; the first two need LinkedIn."""
        return arms.experiment(
            "cad-1",
            [arms.arm("a", "email and LinkedIn", MULTI),
             arms.arm("b", "email and LinkedIn too", MULTI),
             arms.arm("c", "4 steps", FOUR),
             arms.arm("d", "7 steps", SEVEN)],
            allocation={"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25})

    def test_an_email_only_contact_is_spread_across_the_arms_it_can_run(self):
        exp = self.experiment()
        person = {"key": "a", "name": "A Person", "email": "a@acme.test"}
        landed = {}
        for index in range(200):
            rec = a_record(f"r{index}", contacts=[dict(person)])
            entry, _why = arms.choose(exp, rec, rec["contacts"][0])
            landed[entry["arm_id"]] = landed.get(entry["arm_id"], 0) + 1

        self.assertEqual(sorted(landed), ["c", "d"])
        # Roughly half each. Without renormalising, everything above the
        # reachable share falls through to the last arm.
        for arm_id in ("c", "d"):
            self.assertGreater(landed[arm_id], 60, landed)


class AnArmThatNoLongerExistsRunsNothing(unittest.TestCase):
    """A recorded assignment naming a removed arm must fall back to the
    campaign's own sequence, never to whichever arm happens to be first.
    Silently running a different arm would report that arm's results
    against people who never saw it."""

    def test_steps_for_returns_nothing(self):
        exp = four_vs_seven()
        rec = a_record()
        rec[arms.ASSIGNMENT_KEY] = {
            "experiment_id": "cad-1", "arm_id": "deleted", "unit": "account",
            "unit_key": "acme", "allocation_version": 1,
            "at": "2026-06-01T09:00:00+00:00", "why": "assigned"}
        self.assertIsNone(
            arms.steps_for({arms.EXPERIMENT_KEY: exp}, rec))

    def test_and_a_known_arm_still_resolves(self):
        """So the refusal above is about the missing arm."""
        exp = four_vs_seven()
        rec = a_record()
        arms.assign(exp, rec)
        self.assertIsNotNone(
            arms.steps_for({arms.EXPERIMENT_KEY: exp}, rec))
