"""Two safety modules that nothing imported.

`killswitch` had one importer, `workspaces`, and that only to describe a
setting. `workspaces.POLICY_KEYS` says so in as many words: *"NOTHING ENFORCES
THIS YET: the only reader is `killswitch.workspace_state`, and `killswitch` has
no importer outside its own tests, so setting it off stops nothing."*
`pilotcaps` had no importer at all - `require` was documented as "the gate a
runner would call" and no runner called it.

Both were safe, and both were safe by accident: `push.run(live=True)` raises in
code, which is a guarantee about this build rather than about the policy. On
the day somebody deletes that refusal, a switch nothing reads and a ceiling
nothing consults are worth exactly nothing.

What this file pins is the distinction the two now hold to:

- **Reported** by `push.run`, so an operator can see which layers would refuse
  and what the batch would consume, before anything is enabled.
- **Enforced** by `killswitch.require` and `pilotcaps.require`, which raise,
  and which the sender must call.

Enforcing either inside `push.run` was tried and is wrong, for different
reasons that are recorded here so the next person does not retry them.
"""
import unittest

from src import killswitch, pilotcaps, push
from tests.test_push import PushTest


class ThePushRunReportsBoth(PushTest):
    """The consumption half. A module reported by nothing is the defect."""

    def test_the_run_carries_the_kill_switch_verdict(self):
        self.assertIn("sending", self.run_push())

    def test_every_layer_is_reported_not_just_the_first(self):
        """An operator who turns a campaign on needs to see the account is
        still held, or they go looking for a bug in what they just fixed."""
        verdict = self.run_push()["sending"]
        self.assertGreaterEqual(len(verdict["layers"]), 2)
        self.assertIn("blocked_by", verdict)

    def test_the_global_layer_refuses_today(self):
        """It should. `push.run(live=True)` raises, and this says so rather
        than letting the report imply the build could send."""
        verdict = self.run_push()["sending"]
        self.assertFalse(verdict["sending"])
        self.assertEqual(verdict["blocked_by"], killswitch.GLOBAL)

    def test_the_run_carries_the_pilot_cap_check(self):
        self.assertIn("caps", self.run_push())

    def test_the_cap_check_names_what_it_did_not_check(self):
        """A plan naming nothing would otherwise come back clean."""
        caps = self.run_push()["caps"]
        self.assertIn("unchecked", caps)
        self.assertIn("companies", caps["unchecked"])

    def test_a_breach_is_reported_rather_than_hidden(self):
        """The fixture estate prepares more email than the pilot ceiling
        allows, which is exactly the condition worth surfacing."""
        caps = self.run_push()["caps"]
        self.assertIn("ok", caps)
        if not caps["ok"]:
            self.assertTrue(caps["breaches"][0]["over_by"] > 0)
            self.assertIn("limit", caps["breaches"][0])


class TheEnforcingFormsRefuse(unittest.TestCase):
    """Reporting is not enforcement, so the enforcing forms are pinned
    separately - otherwise "it is reported" becomes the whole answer."""

    def test_an_unswitched_workspace_is_refused(self):
        with self.assertRaises(killswitch.SendingRefused):
            killswitch.require(workspace="never-switched-on")

    def test_the_refusal_names_the_outermost_layer(self):
        with self.assertRaises(killswitch.SendingRefused) as caught:
            killswitch.require(workspace="never-switched-on")
        self.assertEqual(caught.exception.verdict["blocked_by"],
                         killswitch.GLOBAL)

    def test_the_refusal_carries_every_layer(self):
        """So an operator fixing one does not have to re-run to see the next."""
        with self.assertRaises(killswitch.SendingRefused) as caught:
            killswitch.require(workspace="never-switched-on")
        self.assertTrue(caught.exception.verdict["layers"])

    def test_a_plan_over_the_ceiling_is_refused(self):
        with self.assertRaises(pilotcaps.PilotCapExceeded):
            pilotcaps.require({"email_per_day": 10_000})

    def test_that_refusal_says_what_was_asked_and_what_is_allowed(self):
        with self.assertRaises(pilotcaps.PilotCapExceeded) as caught:
            pilotcaps.require({"email_per_day": 10_000})
        said = str(caught.exception)
        self.assertIn("10000", said.replace(",", ""))
        self.assertIn(str(pilotcaps.CEILING["email_per_day"]), said)

    def test_a_plan_inside_the_ceiling_passes(self):
        """Or the gate is a ban rather than a limit.

        The acknowledgement is new and this line is what it costs: a caller
        that checks one ceiling has to say it is not checking the others.
        That is the whole mechanism - `require({"email_per_day": 1})` used to
        answer True for SEVEN ceilings having examined one, which is how
        `new_accounts_per_day` was declared and enforced by nobody for as long
        as it existed. Passing through here rather than being hidden behind a
        helper on purpose: the cost should be visible at the call site.
        """
        self.assertTrue(pilotcaps.require(
            {"email_per_day": 1},
            not_checking=set(pilotcaps.KEYS) - {"email_per_day"}))

    def test_an_unreadable_config_does_not_raise_the_ceiling(self):
        """`{}` means pilot mode on. A config that fails to load must not
        silently buy more volume than one that loads."""
        self.assertTrue(pilotcaps.enabled({}))
        self.assertEqual(pilotcaps.effective({})["email_per_day"]["limit"],
                         pilotcaps.CEILING["email_per_day"])


class TheBoundariesThatWereTriedAndRejected(PushTest):
    """Both wrong turns cost a full test run to discover. Pinned so the next
    person does not spend it again."""

    def test_the_dry_run_still_prepares_a_batch_over_the_ceiling(self):
        """Refusing at preparation was tried and is wrong twice: `day` is a
        cadence day rather than a calendar day, so a run's count is not the
        quantity `email_per_day` limits; and a prepared payload costs nothing
        until something sends it. Enforcing on a mis-mapped quantity produces
        a refusal people learn to route around."""
        result = self.run_push()
        self.assertTrue(result["payloads"]["emailbison"]["count"])

    def test_the_dry_run_is_not_blocked_by_the_kill_switch(self):
        """Calling `killswitch.require` here would refuse every dry run -
        correctly, the build cannot send - and a preview that refuses itself
        prepares nothing for anyone to review."""
        self.assertTrue(self.run_push()["ready"])


if __name__ == "__main__":
    unittest.main()
