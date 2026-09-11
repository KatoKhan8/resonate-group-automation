"""Does a campaign's own cadence reach anything that sends?

`cadence.build` takes `campaign=`, and `steps_for` resolves both the
campaign's own sequence and the contact's assigned cadence arm from it.
Of thirty-five call sites in `src/`, exactly one passed it: the preview
screen.

So an operator previewed four steps, the approval fingerprint covered the
seven-step module constant, and a launch would have pushed the constant.
The campaign's cadence - and therefore every cadence arm - reached one
screen and nothing else.

The root cause is not thirty-four forgotten keyword arguments. Membership
is one-directional: a campaign lists its records and a record knows
nothing, so most callers had no campaign to pass even where they wanted
one. `campaigns.by_record` is that missing direction.

Threading it also closed something worse, which has its own class below:
`eligibility._campaign` returns None when there is no campaign, so the
last gate before a payload was skipping the freeze, the rejection, the
already-launched check, the approval and the provider mapping - every
campaign-level guard - because nothing ever handed it a campaign.

These tests are about consumption. The model was already right.
"""
import unittest

from src import cadence, campaigns, orchestrator, push, store
from tests.campaignbase import CLIENT, CampaignTest

# Four steps against the module constant's seven. day10, day15 and day21
# are the ones that must disappear; day1 stays generated so the fixture's
# drafted body still applies to it. day8 is deliberately an email here and
# a LinkedIn follow-up in the constant, because that difference is what
# the last gate gets wrong when it judges against the wrong sequence.
FOUR = [
    {"key": "day1", "day": 1, "channel": "email", "generated": True},
    {"key": "day3", "day": 3, "channel": "linkedin",
     "template": "linkedin_intro"},
    {"key": "day5", "day": 5, "channel": "email", "template": "persona_pain"},
    {"key": "day8", "day": 8, "channel": "email", "template": "breakup"},
]

DROPPED = ("day10", "day15", "day21")


class FourStepCampaign(CampaignTest):
    """A campaign carrying its own four steps, approved and able to send.

    Approved *after* the cadence is set, because the fingerprint now covers
    the cadence - which is one of the things asserted below.
    """

    def setUp(self):
        super().setUp()
        recs = self.seed_records()
        self.draft_everything(recs)
        store.save(recs)
        recs = store.load()

        campaign = self.make_campaign(recs)
        campaign[cadence.CADENCE_KEY] = list(FOUR)
        self.save_campaign(campaign)

        self.approve_drafts(recs, campaign=campaign)
        store.save(recs)
        recs = store.load()

        orchestrator.prepare(campaign, recs, self.config)
        orchestrator.request_approval(campaign, recs, self.config)
        orchestrator.decide(campaign, "U0DEMOADMIN1", "approve",
                            fingerprint=campaigns.fingerprint(
                                campaign, recs, self.config),
                            interaction_id="i-1", config=self.config,
                            recs=recs)
        self.save_campaign(campaign)

        self.campaign = campaign
        self.recs = store.load()

    def step_keys(self, campaign=None):
        timeline = cadence.build(self.recs[0], self.config, recs=self.recs,
                                 campaign=campaign)
        return sorted((timeline["contacts"] or {}).get(
            self.recs[0]["contacts"][0]["key"]) or {})

    def collected(self, rows=None):
        rows = [self.campaign] if rows is None else rows
        ready, _ = push.collect(self.recs, day=30, client=CLIENT,
                                campaign_rows=rows)
        return ready


class TheApprovalFingerprintCoversTheCampaignsCadence(FourStepCampaign):
    """The worst of it: an operator approves what the preview showed, and
    the fingerprint is taken of something else."""

    def material_keys(self, campaign=None):
        found = campaigns.material(campaign or self.campaign, recs=self.recs,
                                   config=self.config)
        return sorted({row["step"]
                       for record in found["records"]
                       for row in record.get("steps") or []})

    def test_the_material_covers_the_campaigns_steps(self):
        self.assertEqual(self.material_keys(), self.step_keys(self.campaign))

    def test_it_does_not_cover_a_step_the_campaign_removed(self):
        covered = self.material_keys()
        self.assertTrue(covered)
        for key in DROPPED:
            self.assertNotIn(key, covered)

    def test_the_fingerprint_moves_when_the_cadence_does(self):
        """If it does not, the cadence is not a launch-sensitive fact, and
        a campaign could be relaunched with a different sequence under an
        approval given for the old one. Before this change the digests of a
        four-step and a three-step campaign were identical."""
        before = campaigns.fingerprint(self.campaign, recs=self.recs,
                                       config=self.config)
        shorter = dict(self.campaign)
        shorter[cadence.CADENCE_KEY] = FOUR[:3]
        after = campaigns.fingerprint(shorter, recs=self.recs,
                                      config=self.config)
        self.assertNotEqual(before, after)

    def test_a_campaign_with_no_cadence_of_its_own_is_unchanged(self):
        """The sweep has to be invisible to every campaign that exists
        today, none of which carries a sequence."""
        plain = dict(self.campaign)
        plain.pop(cadence.CADENCE_KEY, None)
        self.assertEqual(self.material_keys(plain), self.step_keys(None))


class WhatWouldBePushedIsWhatTheCampaignSays(FourStepCampaign):

    def keys_of(self, rows=None):
        return sorted({item["step_key"] for item in self.collected(rows)})

    def test_something_is_actually_collected(self):
        """Guarding the tests below, which would pass against an empty
        list."""
        self.assertTrue(self.keys_of())

    def test_collect_offers_only_the_campaigns_steps(self):
        collected = self.keys_of()
        self.assertTrue(collected)
        for key in DROPPED:
            self.assertNotIn(key, collected)

    def test_a_record_in_no_campaign_still_gets_the_default(self):
        """Nothing here may change what happens to a record that is in no
        campaign at all, which is most of them most of the time.

        day21 is planned but not ready: this fixture only approved the
        drafts of the campaign's own four steps, so the constant's later
        ones are held on a missing approval. Planned-and-held is the proof
        that the default timeline was built - ready would additionally be
        proof that the fixture approved it.
        """
        ready, skipped = push.collect(self.recs, day=30, client=CLIENT,
                                      campaign_rows=[])
        planned = ({item["step_key"] for item in ready}
                   | {row.get("step") for row in skipped})
        self.assertIn("day21", planned)

    def test_the_item_carries_the_campaign_it_came_from(self):
        """So the last gate can re-check against the right sequence
        without a second lookup."""
        item = self.collected()[0]
        self.assertEqual((item.get("campaign") or {}).get("campaign_id"),
                         self.campaign["campaign_id"])


class TheLastGateJudgesAgainstTheRightSequence(FourStepCampaign):
    """`verify_before_payload` rebuilds the timeline rather than trusting
    the caller. Rebuilding it without the campaign judges a four-step
    campaign's day 8 against the constant's day 8, which is a LinkedIn
    follow-up waiting on a connection request."""

    def day8(self):
        found = [i for i in self.collected() if i["step_key"] == "day8"]
        self.assertTrue(found, "day8 was not collected; the fixture is hollow")
        return found[0]

    def test_the_step_passes_the_gate(self):
        push.verify_before_payload(self.day8(), recs=self.recs,
                                   config=self.config)

    def test_the_same_step_is_refused_when_the_campaign_is_taken_away(self):
        """The defect, stated as a difference. Judged against the constant
        this step is held awaiting a dependency that does not exist in its
        own sequence."""
        item = dict(self.day8())
        item.pop("campaign", None)
        with self.assertRaises(AssertionError) as caught:
            push.verify_before_payload(item, recs=self.recs,
                                       config=self.config)
        self.assertIn("awaiting_dependency", str(caught.exception))


class TheLastGateNowSeesTheCampaignAtAll(FourStepCampaign):
    """Threading the campaign closed a bigger hole than the cadence one.

    `eligibility._campaign` and `_mapping` both return None when there is
    no campaign in play. Nothing on the payload path ever passed one, so
    the freeze, the rejection, the already-launched check, the approval and
    the provider mapping were all skipped at the last gate - the one whose
    docstring calls itself the last moment anything is cheap to stop.
    """

    def gate(self, campaign):
        item = dict(self.collected()[0], campaign=campaign)
        with self.assertRaises(AssertionError) as caught:
            push.verify_before_payload(item, recs=self.recs,
                                       config=self.config)
        return str(caught.exception)

    def test_a_frozen_campaign_stops_a_payload(self):
        """The kill switch. It did not reach here."""
        frozen = dict(self.campaign)
        campaigns.freeze(frozen, "stop everything", by="U0DEMOADMIN1")
        self.assertIn("frozen", self.gate(frozen))

    def test_an_already_launched_campaign_stops_a_payload(self):
        launched = dict(self.campaign, launch={"state": "launched"})
        self.assertIn("launched", self.gate(launched))

    def test_an_unapproved_campaign_stops_a_payload(self):
        unapproved = dict(self.campaign)
        unapproved.pop("approval", None)
        self.assertIn("not_approved", self.gate(unapproved))

    def test_a_campaign_edited_since_approval_stops_a_payload(self):
        """Unmapping the provider is one edit of many; what matters is
        that the approval it invalidates is now checked here. Staleness
        fires before the mapping check does, and both were skipped."""
        edited = dict(self.campaign, bison_campaign_id=None)
        self.assertIn("approval_stale", self.gate(edited))


class TheCampaignCheckJudgesTheWholeCampaign(FourStepCampaign):
    """Found by wiring the gate up: switching the campaign-level guards on
    made every dry run refuse with `campaign_approval_stale`.

    `decide` defaults `recs` to the single record it was handed, so that
    the per-record questions - pausing, duplication, separation - can be
    answered without loading the world. But a campaign's approval
    fingerprints every record the campaign names. Judged against a
    one-record list the other records look missing, the digest differs,
    and a live approval reads as stale.

    The fixture seeds two records, so a truncated world is visible here.
    """

    def test_a_live_approval_is_not_stale_at_the_payload_gate(self):
        for item in self.collected():
            push.verify_before_payload(item, recs=None, config=self.config)

    def test_it_still_refuses_when_the_approval_really_is_stale(self):
        """The fix must not have turned the check off."""
        edited = dict(self.campaign, daily_volume={"email": 1})
        item = dict(self.collected()[0], campaign=edited)
        with self.assertRaises(AssertionError) as caught:
            push.verify_before_payload(item, recs=None, config=self.config)
        self.assertIn("approval_stale", str(caught.exception))


class ARecordFindsItsCampaign(FourStepCampaign):
    """The missing direction of the relationship."""

    def test_it_maps_a_record_to_its_campaign(self):
        index = campaigns.by_record([self.campaign])
        self.assertEqual(index[self.recs[0]["id"]]["campaign_id"],
                         self.campaign["campaign_id"])

    def test_a_finished_campaign_does_not_claim_its_records(self):
        """A record whose only campaign is completed runs the default
        rather than inheriting a sequence that has stopped."""
        done = dict(self.campaign, status=campaigns.COMPLETED)
        self.assertEqual(campaigns.by_record([done]), {})

    def test_a_record_in_two_live_campaigns_resolves_to_ambiguous(self):
        """Ambiguity is not a licence to guess an arm - and it is not a
        licence to forget the campaign either.

        This asserted `None`, and falling back to the default was called the
        conservative answer. It is the opposite: `None` means NO CAMPAIGN to
        `eligibility._campaign`, which returns immediately, so the freeze,
        the pause, the rejection, the launch state and the approval staleness
        check all stopped applying. Duplicating an intent detached the stop
        button on the original. The refusal to guess an arm is unchanged; the
        ambiguity is now a value that blocks rather than an absence that
        permits.
        """
        other = dict(self.campaign, campaign_id="camp-2")
        index = campaigns.by_record([self.campaign, other])
        self.assertTrue(index.get(self.recs[0]["id"], {}).get("ambiguous"))
        self.assertIsNone(
            index[self.recs[0]["id"]].get("campaign_id"),
            "the ambiguous marker must not name one of the campaigns")

    def test_a_third_campaign_does_not_undo_the_ambiguity(self):
        third = dict(self.campaign, campaign_id="camp-3")
        index = campaigns.by_record([self.campaign,
                                     dict(self.campaign, campaign_id="camp-2"),
                                     third])
        self.assertTrue(index.get(self.recs[0]["id"], {}).get("ambiguous"))

    def test_a_record_in_no_campaign_is_absent(self):
        self.assertNotIn("nobody", campaigns.by_record([self.campaign]))


class EveryTimelineBuiltForACampaignIsGivenIt(unittest.TestCase):
    """The regression guard for the defect itself.

    Structural rather than behavioural because the failure is an omitted
    keyword argument at a call site, and no single behavioural test reaches
    all of them - the model's own tests all passed `campaign=` by hand,
    which is exactly why the defect survived two missions.
    """

    def build_calls(self, module):
        import ast
        import inspect

        for node in ast.walk(ast.parse(inspect.getsource(module))):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "build"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "cadence"):
                yield node

    def assert_all_pass_the_campaign(self, module):
        calls = list(self.build_calls(module))
        self.assertTrue(calls, f"{module.__name__} builds no timelines")
        for node in calls:
            self.assertIn(
                "campaign", [kw.arg for kw in node.keywords],
                f"cadence.build at {module.__name__} line {node.lineno} does "
                "not pass the campaign it has in scope")

    def test_campaigns_never_builds_a_timeline_without_its_campaign(self):
        self.assert_all_pass_the_campaign(campaigns)

    def test_eligibility_never_builds_a_timeline_without_its_campaign(self):
        from src import eligibility

        self.assert_all_pass_the_campaign(eligibility)

    def test_push_never_builds_a_timeline_without_its_campaign(self):
        self.assert_all_pass_the_campaign(push)


if __name__ == "__main__":
    unittest.main()
