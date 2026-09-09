"""Putting a cadence experiment on a campaign.

Eight modules read `campaign["cadence_experiment"]`. Until this existed
nothing wrote it, so the arms model, the assignment, the exposure
accounting and the whole report were unreachable from any campaign an
operator could create - a whole mission's work computing correctly on
something nothing could produce.

Which is the failure this repository keeps finding in itself, arriving in
the middle of the feature built to measure sequences. `src/cadencegraph.py`
has the same shape and is still open: `campaign["cadence_graph"]` is read
by `campaignqa` and written by nothing.
"""
import unittest

from src import (cadencearms as arms, campaigns, orchestrator, roles, store)
from tests.campaignbase import CampaignTest

FOUR = [{"key": "s1", "day": 1, "channel": "email",
         "template": "persona_pain"},
        {"key": "s2", "day": 3, "channel": "email",
         "template": "persona_pain"},
        {"key": "s3", "day": 7, "channel": "email",
         "template": "comparable_proof"},
        {"key": "s4", "day": 12, "channel": "email", "template": "breakup"}]

SEVEN = FOUR + [
    {"key": "s5", "day": 18, "channel": "email", "template": "persona_pain"},
    {"key": "s6", "day": 25, "channel": "email",
     "template": "comparable_proof"},
    {"key": "s7", "day": 35, "channel": "email", "template": "breakup"}]


def an_experiment(arm_ids=("four", "seven")):
    steps = {"four": FOUR, "seven": SEVEN}
    return arms.experiment(
        "cad-1", [arms.arm(a, f"{len(steps.get(a, FOUR))} steps",
                           steps.get(a, FOUR)) for a in arm_ids],
        testing="cadence length")


class ACampaignCanBeGivenAnExperiment(CampaignTest):

    def setUp(self):
        super().setUp()
        recs = self.seed_records()
        store.save(recs)
        self.recs = store.load()
        self.campaign = self.make_campaign(self.recs)

    def test_it_is_stored_where_every_reader_looks(self):
        orchestrator.set_cadence_experiment(
            self.campaign, an_experiment(), by="U0DEMOADMIN1",
            recs=self.recs)
        self.assertEqual(
            self.campaign[arms.EXPERIMENT_KEY]["experiment_id"], "cad-1")

    def test_and_the_readers_can_then_see_it(self):
        """The point of the whole exercise: the report was unreachable."""
        from src import cadencereport

        orchestrator.set_cadence_experiment(
            self.campaign, an_experiment(), by="U0DEMOADMIN1",
            recs=self.recs)
        exp = self.campaign[arms.EXPERIMENT_KEY]
        found = cadencereport.report(exp, self.recs, self.campaign,
                                     today="2026-09-30")
        self.assertEqual(sorted(a["arm_id"] for a in found["arms"]),
                         ["four", "seven"])

    def test_a_malformed_experiment_is_refused(self):
        """`cadence.steps_for` resolves an arm on every page load, so a bad
        experiment would surface as a broken timeline rather than a bad
        edit."""
        with self.assertRaises(arms.BadExperiment):
            orchestrator.set_cadence_experiment(
                self.campaign, {"experiment_id": "x", "arms": []},
                by="U0DEMOADMIN1", recs=self.recs)

    def test_it_is_written_to_the_campaign_log(self):
        orchestrator.set_cadence_experiment(
            self.campaign, an_experiment(), by="U0DEMOADMIN1",
            recs=self.recs)
        steps = [row.get("step") for row in self.campaign.get("log") or []]
        self.assertIn("cadence_experiment", steps)

    def test_a_viewer_may_not_set_one(self):
        with self.assertRaises(roles.NotPermitted):
            orchestrator.set_cadence_experiment(
                self.campaign, an_experiment(), by="U0DEMOVIEWER",
                role=roles.VIEWER, recs=self.recs)


class ItIsLaunchSensitive(CampaignTest):
    """The arms decide what each contact is sent, so setting one voids an
    approval that predates it - the same as changing the records."""

    def setUp(self):
        super().setUp()
        self.campaign, self.recs, _ = self.approved_campaign()

    def test_attaching_an_experiment_alone_does_not_void_an_approval(self):
        """And should not. With nobody assigned, no timeline moves and
        nothing about what would be sent has changed - the fingerprint is
        of what would go out, not of what is configured."""
        self.assertTrue(campaigns.is_approved(self.campaign, self.recs,
                                              self.config))
        orchestrator.set_cadence_experiment(
            self.campaign, an_experiment(), by="U0DEMOADMIN1",
            recs=self.recs, config=self.config)
        self.assertTrue(campaigns.is_approved(self.campaign, self.recs,
                                              self.config))

    def test_but_assigning_the_arms_does(self):
        """Which is the moment the timeline actually changes. Assignment
        happens in `prepare`, before approval, so an approved campaign's
        fingerprint already covers the arms - and one that gains them
        afterwards goes stale rather than sending something nobody
        approved."""
        orchestrator.set_cadence_experiment(
            self.campaign, an_experiment(), by="U0DEMOADMIN1",
            recs=self.recs, config=self.config)
        moved = orchestrator.assign_cadence_arms(self.campaign, self.recs)
        self.assertTrue(moved)
        self.assertFalse(campaigns.is_approved(self.campaign, self.recs,
                                               self.config))

    def test_a_launched_campaign_refuses_the_change(self):
        """People are part-way through an arm."""
        self.campaign["launch"] = {"state": "launched"}
        with self.assertRaises(campaigns.CampaignError) as caught:
            orchestrator.set_cadence_experiment(
                self.campaign, an_experiment(), by="U0DEMOADMIN1",
                recs=self.recs, config=self.config)
        self.assertIn("launched", str(caught.exception))


class AnArmWithPeopleInItMayNotVanish(CampaignTest):
    """A recorded assignment naming an arm that no longer exists resolves
    to nothing, and those contacts fall back to the default cadence
    without anybody being told."""

    def setUp(self):
        super().setUp()
        recs = self.seed_records()
        store.save(recs)
        self.recs = store.load()
        self.campaign = self.make_campaign(self.recs)
        orchestrator.set_cadence_experiment(
            self.campaign, an_experiment(), by="U0DEMOADMIN1",
            recs=self.recs)
        # One record only, so exactly one arm is populated and the arm to
        # remove is always the one somebody is in. Assigning everybody
        # would populate both and leave nothing to remove, which is how
        # this test came to be skipping itself rather than running.
        exp = self.campaign[arms.EXPERIMENT_KEY]
        arms.assign(exp, self.recs[0])
        store.save(self.recs)
        self.recs = store.load()

    def assigned_arms(self):
        exp = self.campaign[arms.EXPERIMENT_KEY]
        return {row["arm_id"] for row in
                (arms.recorded(exp, rec) for rec in self.recs) if row}

    def test_the_fixture_actually_assigned_somebody(self):
        """Guarding the two tests below, which would pass against nobody."""
        self.assertTrue(self.assigned_arms())

    def test_exactly_one_arm_is_populated(self):
        """The shape the two tests below depend on."""
        self.assertEqual(len(self.assigned_arms()), 1)

    def test_removing_a_populated_arm_is_refused(self):
        keep = sorted({"four", "seven"} - self.assigned_arms())
        with self.assertRaises(campaigns.CampaignError) as caught:
            orchestrator.set_cadence_experiment(
                self.campaign, an_experiment(tuple(keep) + ("extra",)),
                by="U0DEMOADMIN1", recs=self.recs)
        self.assertIn("assigned", str(caught.exception))

    def test_keeping_it_is_allowed(self):
        """So the refusal is about the arm disappearing, not about editing
        an experiment that has people in it at all."""
        orchestrator.set_cadence_experiment(
            self.campaign, an_experiment(), by="U0DEMOADMIN1",
            recs=self.recs)

    def test_clearing_the_experiment_is_refused(self):
        with self.assertRaises(campaigns.CampaignError) as caught:
            orchestrator.clear_cadence_experiment(
                self.campaign, by="U0DEMOADMIN1", recs=self.recs)
        self.assertIn("pointing at nothing", str(caught.exception))

    def test_a_different_experiment_entirely_is_allowed(self):
        """Assignments are recorded against an experiment id and will not
        be read by a new one, so nobody is left pointing at a missing arm -
        they are simply no longer in an experiment."""
        other = arms.experiment("cad-2", [arms.arm("a", "4 steps", FOUR),
                                          arms.arm("b", "7 steps", SEVEN)])
        orchestrator.set_cadence_experiment(
            self.campaign, other, by="U0DEMOADMIN1", recs=self.recs)
        self.assertEqual(
            self.campaign[arms.EXPERIMENT_KEY]["experiment_id"], "cad-2")


class ClearingIsAllowedWhenNobodyIsIn(CampaignTest):

    def setUp(self):
        super().setUp()
        recs = self.seed_records()
        store.save(recs)
        self.recs = store.load()
        self.campaign = self.make_campaign(self.recs)
        orchestrator.set_cadence_experiment(
            self.campaign, an_experiment(), by="U0DEMOADMIN1",
            recs=self.recs)

    def test_it_comes_off(self):
        orchestrator.clear_cadence_experiment(
            self.campaign, by="U0DEMOADMIN1", recs=self.recs)
        self.assertIsNone(self.campaign[arms.EXPERIMENT_KEY])

    def test_clearing_a_campaign_that_has_none_is_not_an_error(self):
        orchestrator.clear_cadence_experiment(
            self.campaign, by="U0DEMOADMIN1", recs=self.recs)
        orchestrator.clear_cadence_experiment(
            self.campaign, by="U0DEMOADMIN1", recs=self.recs)

    def test_a_viewer_may_not_clear_one(self):
        with self.assertRaises(roles.NotPermitted):
            orchestrator.clear_cadence_experiment(
                self.campaign, by="U0DEMOVIEWER", role=roles.VIEWER,
                recs=self.recs)


class TheChainIsWholeFromAuthoringToReport(CampaignTest):
    """input -> canonical state -> decision -> consumer -> execution.

    Not a summary of the tests above: this walks the links in order and
    fails at whichever one is not connected.
    """

    def test_an_experiment_set_by_an_operator_changes_what_is_built(self):
        from src import cadence

        recs = self.seed_records()
        self.draft_everything(recs)
        store.save(recs)
        recs = store.load()
        campaign = self.make_campaign(recs)

        orchestrator.set_cadence_experiment(
            campaign, an_experiment(), by="U0DEMOADMIN1", recs=recs)
        self.save_campaign(campaign)

        # Preparing is what assigns the arms - not building a timeline,
        # which happens on every page load.
        moved = orchestrator.prepare(campaign, recs, self.config)
        self.assertTrue(moved["cadence_arms_assigned"])
        store.save(recs)
        recs = store.load()

        exp = campaign[arms.EXPERIMENT_KEY]
        rec = recs[0]
        arm_id = arms.recorded(exp, rec)["arm_id"]
        expected = {"four": ["s1", "s2", "s3", "s4"],
                    "seven": ["s1", "s2", "s3", "s4", "s5", "s6", "s7"]}

        timeline = cadence.build(rec, self.config, recs=recs,
                                 campaign=campaign)
        steps = timeline["contacts"][rec["contacts"][0]["key"]]
        self.assertEqual(sorted(steps), expected[arm_id])

    def test_and_without_the_experiment_it_builds_the_default(self):
        """So the assertion above is about the arm rather than about the
        fixture only ever producing four steps."""
        from src import cadence

        recs = self.seed_records()
        self.draft_everything(recs)
        store.save(recs)
        recs = store.load()
        campaign = self.make_campaign(recs)
        timeline = cadence.build(recs[0], self.config, recs=recs,
                                 campaign=campaign)
        steps = sorted(timeline["contacts"][recs[0]["contacts"][0]["key"]])
        self.assertNotIn("s1", steps)


if __name__ == "__main__":
    unittest.main()


class AssigningIsOnceAndOnlyForThisCampaign(CampaignTest):
    """Assignment happens in `prepare`, which an operator may run more than
    once. It has to be safe to."""

    def setUp(self):
        super().setUp()
        recs = self.seed_records()
        store.save(recs)
        self.recs = store.load()
        self.campaign = self.make_campaign([self.recs[0]])
        orchestrator.set_cadence_experiment(
            self.campaign, an_experiment(), by="U0DEMOADMIN1",
            recs=self.recs)

    def exp(self):
        return self.campaign[arms.EXPERIMENT_KEY]

    def test_a_record_outside_the_campaign_is_not_assigned(self):
        """`make_campaign` was given one of the two seeded records. The
        other one is somebody else's."""
        orchestrator.assign_cadence_arms(self.campaign, self.recs)
        self.assertIsNotNone(arms.recorded(self.exp(), self.recs[0]))
        self.assertIsNone(arms.recorded(self.exp(), self.recs[1]))

    def test_a_second_prepare_does_not_move_anybody(self):
        orchestrator.assign_cadence_arms(self.campaign, self.recs)
        first = dict(arms.recorded(self.exp(), self.recs[0]))
        orchestrator.assign_cadence_arms(self.campaign, self.recs)
        self.assertEqual(arms.recorded(self.exp(), self.recs[0]), first)

    def test_nor_change_when_they_were_assigned(self):
        """Maturity counts time from each contact's own assignment. A
        rewritten timestamp resets the clock on an arm that has been
        running for weeks, and the experiment never matures.

        Backdated on purpose: two calls a millisecond apart produce the
        same timestamp to the second, so comparing before and after would
        pass whether the assignment was rewritten or not.
        """
        orchestrator.assign_cadence_arms(self.campaign, self.recs)
        entry = self.recs[0][arms.ASSIGNMENT_KEY]
        entry["at"] = "2026-01-01T00:00:00+00:00"
        entry["why"] = "assigned in January"

        orchestrator.assign_cadence_arms(self.campaign, self.recs)
        after = arms.recorded(self.exp(), self.recs[0])
        self.assertEqual(after["at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(after["why"], "assigned in January")

    def test_it_reports_only_the_new_assignments(self):
        self.assertEqual(
            orchestrator.assign_cadence_arms(self.campaign, self.recs), 1)
        self.assertEqual(
            orchestrator.assign_cadence_arms(self.campaign, self.recs), 0)

    def test_a_campaign_with_no_experiment_assigns_nobody(self):
        plain = self.make_campaign(self.recs, campaign_id="camp-2")
        self.assertEqual(
            orchestrator.assign_cadence_arms(plain, self.recs), 0)
        for rec in self.recs:
            self.assertNotIn(arms.ASSIGNMENT_KEY, rec)
