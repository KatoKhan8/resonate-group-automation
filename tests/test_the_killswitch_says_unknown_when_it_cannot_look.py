"""`sending: False` means two different things, and now the verdict says which.

TASK 0233 (pilotcaps), 2026-10-16.

THE FINDING THIS PINS, measured before it was written. `CLAUDE.md:25` - the
orientation command a fresh session is told to derive the estate's state with:

    py -3 -c "from src import killswitch as k; print(k.workspace_state('productive'))"

Run in four situations, the full output and the exit code each time:

    the real slug, from a tree with no estate
      {... 'sending': False, 'why': 'no such workspace: productive'}      exit 0
    a slug invented on the spot
      {... 'sending': False, 'why': 'no such workspace: cannot-exist...'} exit 0
    the workspace exists and sending.live is off
      {... 'sending': False, 'why': 'sending.live is off for productive'} exit 0
    the workspace exists and sending.live is on
      {... 'sending': True,  'why': 'sending.live is on for productive'}  exit 0

The first two differ **only in the spelling of the slug the operator typed**,
and the exit code is 0 in all four, so a script learns nothing from it either.
An operator reading the first line sees the word `False` beside the question
"is sending off?" and has been told the reassuring thing, when what happened is
that this process cannot see the estate at all - the store resolves `work/`
against whichever tree the process stands in, and a lane worktree's `work/`
holds lane scratch.

THAT IS INVARIANT 0 AT THE DESIGNATED AUTHORITY. `docs/OPERATING-MODE.md:510`
names `killswitch.workspace_state('productive')` as the authority for the
current value, "never this line" - correctly, a function over prose. The
function then cannot tell "we looked and it is off" from "there was nothing to
look at", and reports both as the word that reads as safe.

WHAT IS *NOT* WRONG HERE, because it would be easy to over-claim. Defaulting an
absent workspace to `sending=False` is right for a GATE: every caller does
`if not ws_state["sending"]: refuse`, so absence fails CLOSED, and
`workspace_state`'s own docstring says that is asserted rather than assumed.
The defect is in the REPORT, where the reader is a person asking "is it safe?"
instead of a caller asking "may I proceed?". So `sending` is untouched by this
change and no gate behaves differently; the verdict gained a `determined`
field, which is output, not logic.

Note in passing, because it shows the asymmetry is not inherent: the WRITE path
already refuses loudly on the same condition - `workspaces.set_policy` raises
`NotOverridable("no such workspace: productive")`. Only the read path
reassured.
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import killswitch, store, workspaces  # noqa: E402

WS = "pc0233-workspace"


class _WorkspaceCase(unittest.TestCase):
    """Builds a real workspace row in an ISOLATED store.

    The isolation is not hygiene, it is the test's own subject. The first draft
    of this module wrote into the tree's own `work/` and
    `store.refuse_production_write` stopped it by name - which is the same
    class of guard this module is about, working, and in the right direction.
    """

    def setUp(self):
        self.addCleanup(store.use_directory(
            os.path.join(tempfile.mkdtemp(prefix="pc0233-"), "work")))

    def seed(self, slug=WS, live=None):
        with workspaces.transaction() as rows:
            rows.append(workspaces.new_workspace(slug, slug.title(),
                                                 created_by="pc0233"))
        if live is not None:
            workspaces.set_policy(slug, {killswitch.WORKSPACE_KEY: live},
                                  actor="pc0233")
        return slug


class TheVerdictSaysWhetherItLooked(_WorkspaceCase):

    # --- C1 -------------------------------------------------------------
    def test_c1_the_instrument_can_say_sending_is_ON(self):
        """C1: it can print something other than False.

        An instrument only ever observed printing `False` has never been shown
        able to print anything else, and this one is consulted precisely to
        find out whether sending is on.

        TO SEE THIS FAIL: make `workspace_state` return
        `_verdict(WORKSPACE, False, ...)` unconditionally. C1 goes red and C2
        stays green, which is the asymmetry that tells you C1 is the one
        watching the positive answer.
        """
        self.seed(live="on")
        found = killswitch.workspace_state(WS)
        self.assertTrue(found["sending"])
        self.assertTrue(found["determined"],
                        "an explicit `on` is a measured answer")
        self.assertIn("is on", found["why"])

    def test_c1_an_explicit_off_is_still_a_determined_answer(self):
        """The other half of C1: `off` must not be swept in with UNKNOWN.

        If every `False` were marked undetermined, `determined` would carry no
        information and C2 would pass for free.
        """
        self.seed(live="off")
        found = killswitch.workspace_state(WS)
        self.assertFalse(found["sending"])
        self.assertTrue(found["determined"],
                        "the switch was read and it said off: that is "
                        "measured, not unknown")

    # --- C2 -------------------------------------------------------------
    def test_c2_a_missing_workspace_is_undetermined_not_merely_off(self):
        """C2: the broken case renders UNKNOWN and the healthy case does not.

        TO SEE THIS FAIL: make the `entry is None` branch fall back to the
        plain `_verdict(WORKSPACE, False, ...)` with no `determined=False` -
        i.e. let the unknown path report the same thing the off path does. C2
        goes red; C1 stays green, because C1 never asks about a workspace that
        is not there.
        """
        found = killswitch.workspace_state("no-such-workspace-pc0233")
        self.assertFalse(found["sending"],
                         "absence must still fail CLOSED for the gates")
        self.assertFalse(found["determined"],
                         "a workspace this store has no record of is UNKNOWN, "
                         "and UNKNOWN never becomes off, idle or safe")
        self.assertIn("UNKNOWN", found["why"])

    def test_c2_the_two_cases_are_distinguishable_from_the_output_alone(self):
        """The question the brief asks in one sentence, as an assertion.

        Can an operator reading only this command's output tell the difference?
        Before this change: no - the two outputs differed only in the slug.
        This test is that sentence, and it fails the moment they converge
        again.
        """
        self.seed(live="off")
        looked = killswitch.workspace_state(WS)
        could_not = killswitch.workspace_state("no-such-workspace-pc0233")

        self.assertEqual(looked["sending"], could_not["sending"],
                         "precondition: both still report False, which is why "
                         "`sending` alone cannot carry this distinction")
        self.assertNotEqual(
            looked["determined"], could_not["determined"],
            "the whole point: two situations that share a `sending` value "
            "must differ somewhere a reader can see")

    def test_c2_the_empty_slug_is_also_undetermined(self):
        found = killswitch.workspace_state("")
        self.assertFalse(found["sending"])
        self.assertFalse(found["determined"])

    def test_a_workspace_that_exists_but_was_never_switched_on_is_DETERMINED(self):
        """The fourth reason for `False`, and it is a measured one.

        The workspace is there and carries no setting. That is a fact about the
        workspace - `workspace_state`'s docstring is explicit that "No setting
        is not a setting of on" - so it is determined, and marking it UNKNOWN
        would be the error in the other direction.
        """
        self.seed()
        found = killswitch.workspace_state(WS)
        self.assertFalse(found["sending"])
        self.assertTrue(found["determined"])
        self.assertIn("never been switched on", found["why"])


class EveryLayerCarriesTheKey(_WorkspaceCase):
    """A field present on some verdicts and absent on others is a KeyError
    waiting for the first reader who trusts it."""

    def test_every_layer_in_a_report_carries_determined(self):
        self.seed(live="on")
        report = killswitch.state(workspace=WS)
        self.assertTrue(report["layers"])
        for row in report["layers"]:
            with self.subTest(layer=row["layer"]):
                self.assertIn("determined", row)
                self.assertIsInstance(row["determined"], bool)

    def test_the_report_names_which_layers_could_not_determine_themselves(self):
        report = killswitch.state(workspace="no-such-workspace-pc0233")
        self.assertIn(killswitch.WORKSPACE, report["undetermined"])
        self.assertFalse(report["sending"],
                         "an undetermined layer still blocks")

    def test_a_determined_report_names_nothing_undetermined(self):
        self.seed(live="on")
        report = killswitch.state(workspace=WS)
        self.assertEqual(report["undetermined"], [],
                         "a fully measured report must not claim doubt it "
                         "does not have")


class TheGatesBehaviourIsUNCHANGED(_WorkspaceCase):
    """This change is output, not logic. That is asserted, not asserted-to.

    If any of these moved, the change would be a gate change and outside this
    task's authority.
    """

    def test_absence_still_fails_closed(self):
        self.assertFalse(
            killswitch.workspace_state("no-such-workspace-pc0233")["sending"])

    def test_the_sending_boolean_is_unchanged_in_all_four_situations(self):
        self.assertFalse(killswitch.workspace_state("")["sending"])
        self.assertFalse(
            killswitch.workspace_state("no-such-workspace-pc0233")["sending"])
        self.seed()
        self.assertFalse(killswitch.workspace_state(WS)["sending"])
        workspaces.set_policy(WS, {killswitch.WORKSPACE_KEY: "on"},
                              actor="pc0233")
        self.assertTrue(killswitch.workspace_state(WS)["sending"])

    def test_the_why_for_the_off_case_still_names_the_key_and_the_slug(self):
        """`state`'s `why` is what the gates put in their refusal messages.

        `bisonfactory`, `executionguard` and `heyreachfactory` all interpolate
        `ws_state['why']` into the exception a human reads, so the off case's
        wording is load-bearing and this change must not have disturbed it.
        """
        self.seed(live="off")
        why = killswitch.workspace_state(WS)["why"]
        self.assertIn(killswitch.WORKSPACE_KEY, why)
        self.assertIn(WS, why)
        self.assertNotIn("UNKNOWN", why,
                         "a switch that was read and said off is not UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
