"""Six layers, the most restrictive wins, and every one defaults to off.

Nothing in this build can send, so today this is a switch on a machine
with no engine. It is tested now anyway, because of the order of events on
the day sending is enabled: somebody removes one refusal in `push`, and if
the layers below it do not already exist with a default of off, the day the
engine arrives is the day somebody invents the brakes.

The assertion that matters most is the dull one. A workspace with no
setting does not send - not because a value was missing and something
defaulted, but because absence *means* off here.
"""
import unittest

from src import campaigns, killswitch, store, workspaces
from tests.campaignbase import CLIENT, CampaignTest, contact

WS = "productive"
OTHER = "contactout"


class TheBuildCannotSend(unittest.TestCase):

    def test_the_global_layer_refuses(self):
        found = killswitch.global_state()
        self.assertFalse(found["sending"])
        self.assertTrue(found["refused_in_code"])

    def test_it_says_the_refusal_is_not_a_flag(self):
        """Somebody looking for the switch must not go looking for an
        environment variable that does not exist."""
        self.assertIn("not a flag", killswitch.global_state()["why"])

    def test_the_refusal_it_cites_is_real(self):
        """The claim is derived from `push`, so this asserts the thing it
        is derived from actually refuses."""
        from src import push, tagsync

        with self.assertRaises(push.LiveSendNotEnabled):
            push.run(live=True)
        with self.assertRaises(tagsync.TagSyncRefused):
            tagsync.send({"workspace": WS, "provider": tagsync.EMAILBISON},
                         live=True)

    def test_nothing_here_can_turn_anything_on(self):
        """This module reads. A setter would be a second way to enable
        sending, next to the one that is a code review."""
        import inspect

        source = inspect.getsource(killswitch)
        for banned in ("def set_", "def enable", "os.environ[",
                       "set_policy", "store.save"):
            self.assertNotIn(banned, source, banned)


class AWorkspaceIsOffUntilSomebodySaysOtherwise(CampaignTest):

    def setUp(self):
        super().setUp()
        workspaces.ensure(WS, "Productive", client=CLIENT)

    def test_a_new_workspace_does_not_send(self):
        """The failure this prevents: a workspace created for a demo, and
        nobody remembers whether the switch was ever set."""
        found = killswitch.workspace_state(WS)
        self.assertFalse(found["sending"])

    def test_absence_is_reported_as_absence_not_as_off(self):
        """"Never switched on" and "switched off" are the same outcome and
        different facts. An operator needs to know which."""
        self.assertIn("never been switched on",
                      killswitch.workspace_state(WS)["why"])

    def test_an_unknown_workspace_does_not_send(self):
        found = killswitch.workspace_state("no-such-tenant")
        self.assertFalse(found["sending"])

    def test_naming_no_workspace_does_not_send(self):
        self.assertFalse(killswitch.workspace_state(None)["sending"])

    def test_switching_it_on_is_a_real_recorded_setting(self):
        workspaces.set_policy(WS, {killswitch.WORKSPACE_KEY: "on"},
                              actor="op@x.test")
        self.assertTrue(killswitch.workspace_state(WS)["sending"])

    def test_switching_it_off_again_stops_it(self):
        workspaces.set_policy(WS, {killswitch.WORKSPACE_KEY: "on"})
        workspaces.set_policy(WS, {killswitch.WORKSPACE_KEY: "off"})
        self.assertFalse(killswitch.workspace_state(WS)["sending"])

    def test_only_on_and_off_are_accepted(self):
        with self.assertRaises(workspaces.NotOverridable):
            workspaces.set_policy(WS, {killswitch.WORKSPACE_KEY: "yes"})

    def test_one_workspace_being_on_does_not_switch_another_on(self):
        # Its own client, not `productive`'s. Two workspaces sharing
        # one client share every record in it, and this test wants two
        # workspaces rather than one workspace named twice.
        workspaces.ensure(OTHER, "ContactOut", client=OTHER)
        workspaces.set_policy(WS, {killswitch.WORKSPACE_KEY: "on"})
        self.assertTrue(killswitch.workspace_state(WS)["sending"])
        self.assertFalse(killswitch.workspace_state(OTHER)["sending"])


class TheInnerLayers(CampaignTest):

    def test_only_a_running_campaign_sends(self):
        """`LAUNCH_READY` means every check passed and a human has not
        pressed the button. Treating that as running makes the button
        decorative."""
        for status in (campaigns.DRAFT, campaigns.READY_FOR_REVIEW,
                       campaigns.AWAITING_APPROVAL, campaigns.APPROVED,
                       campaigns.LAUNCH_READY, campaigns.PAUSED,
                       campaigns.COMPLETED):
            found = killswitch.campaign_state({"status": status})
            self.assertFalse(found["sending"], status)
        self.assertTrue(
            killswitch.campaign_state({"status": campaigns.RUNNING})["sending"])

    def test_a_paused_campaign_says_it_is_paused(self):
        found = killswitch.campaign_state({"status": campaigns.PAUSED})
        self.assertIn("paused", found["why"])

    def test_a_held_company_stops(self):
        rec = {"id": "a1", "paused": {"since": "x", "reason": "reply"}}
        self.assertFalse(killswitch.account_state(rec)["sending"])

    def test_a_company_that_asked_us_to_stop_stops(self):
        rec = {"id": "a1", "suppression": {"unsubscribed": True}}
        found = killswitch.account_state(rec)
        self.assertFalse(found["sending"])
        self.assertIn("asked us to stop", found["why"])

    def test_a_dropped_record_stops(self):
        rec = {"id": "a1", "state": "dropped", "drop_reason": "out of geo"}
        found = killswitch.account_state(rec)
        self.assertFalse(found["sending"])
        self.assertEqual(found["why"], "out of geo")

    def test_an_ordinary_company_does_not_stop_at_this_layer(self):
        self.assertTrue(killswitch.account_state({"id": "a1"})["sending"])

    def test_a_suppressed_person_stops(self):
        person = contact("a", "A Person", "a@acme.test")
        person["unsubscribed"] = True
        self.assertFalse(killswitch.contact_state(person)["sending"])

    def test_an_ordinary_person_does_not_stop_at_this_layer(self):
        self.assertTrue(killswitch.contact_state(
            contact("a", "A Person", "a@acme.test"))["sending"])


class TheMostRestrictiveWins(CampaignTest):

    def setUp(self):
        super().setUp()
        workspaces.ensure(WS, "Productive", client=CLIENT)

    def test_nothing_sends_with_everything_switched_on_below_the_global(self):
        """The global layer outranks every setting under it. Turning a
        workspace on is the second lock, not the first."""
        workspaces.set_policy(WS, {killswitch.WORKSPACE_KEY: "on"})
        found = killswitch.state(
            workspace=WS,
            campaign={"status": campaigns.RUNNING},
            rec={"id": "a1"},
            contact=contact("a", "A Person", "a@acme.test"))
        self.assertFalse(found["sending"])
        self.assertEqual(found["blocked_by"], killswitch.GLOBAL)

    def test_every_layer_is_reported_not_just_the_first_refusal(self):
        """An operator who turns a campaign back on needs to see the
        account is still held. Reporting one refusal sends them looking
        for a bug in the thing they just fixed."""
        found = killswitch.state(
            workspace=WS,
            campaign={"status": campaigns.PAUSED},
            rec={"id": "a1", "paused": {"since": "x", "reason": "reply"}},
            contact=contact("a", "A Person", "a@acme.test"))
        layers = {row["layer"] for row in found["layers"]}
        self.assertEqual(layers, {killswitch.GLOBAL, killswitch.WORKSPACE,
                                  killswitch.CAMPAIGN, killswitch.ACCOUNT,
                                  killswitch.CONTACT})
        self.assertGreaterEqual(found["blocked_count"], 4)

    def test_the_outermost_refusal_is_the_one_to_fix_first(self):
        found = killswitch.state(workspace=WS,
                                 campaign={"status": campaigns.PAUSED})
        self.assertEqual(found["blocked_by"], killswitch.GLOBAL)

    def test_every_layer_carries_a_reason(self):
        found = killswitch.state(
            workspace=WS, campaign={"status": campaigns.RUNNING},
            rec={"id": "a1"},
            contact=contact("a", "A Person", "a@acme.test"))
        for row in found["layers"]:
            self.assertTrue(row["why"], row["layer"])
            self.assertTrue(row["label"], row["layer"])

    def test_the_layer_order_is_outermost_first(self):
        self.assertEqual(
            killswitch.LAYERS,
            (killswitch.GLOBAL, killswitch.WORKSPACE, killswitch.CAMPAIGN,
             killswitch.ACCOUNT, killswitch.CONTACT, killswitch.STEP))

    def test_the_summary_explains_the_rule(self):
        found = killswitch.state(workspace=WS)
        self.assertIn("most restrictive", found["note"])

    def test_the_step_layer_asks_eligibility(self):
        """The pre-send recheck is the innermost layer and is not
        reimplemented here: a second copy of "may this go out" is a second
        thing to get wrong."""
        from src import mx

        recs = self.seed_records()
        rec = recs[0]
        rec["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        rec["contacts"][0]["mx"] = mx.decide(
            ["aspmx.l.google.com"], mx.settings(self.config),
            domain="acme.test")
        self.draft_everything(recs)
        self.approve_drafts(recs)
        store.save(recs)
        recs = store.load()

        found = killswitch.step_state(recs[0], recs[0]["contacts"][0],
                                      "day1", recs=recs, config=self.config)
        self.assertTrue(found["sending"], found["why"])

        recs[0]["contacts"][0]["unsubscribed"] = True
        stopped = killswitch.step_state(recs[0], recs[0]["contacts"][0],
                                        "day1", recs=recs, config=self.config)
        self.assertFalse(stopped["sending"])
        self.assertTrue(stopped["reasons"])


if __name__ == "__main__":
    unittest.main()
