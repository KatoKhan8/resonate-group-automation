"""The pilot ceiling has an ENFORCER, and removing it breaks these tests.

WHY THIS FILE EXISTS. `test_invariants.py:274` taught this repository that a
test which still passes with the control stubbed out is not a test. The pilot
ceiling is a declaration - `pilotcaps.CEILING` - and a declaration with no
enforcer is the shape that produced campaign 504 and the 280/665 overrun. So
the question these tests answer is not "does the ceiling hold a number" but
"does REMOVING THE ENFORCEMENT CALL make a test go red".

THE MUTATION IS IN-PROCESS, NOT A FILE EDIT. `pilotcaps.require` is replaced on
the module object for the duration of one test. Editing `src/executionguard.py`
to delete the call would be the more literal reading of "removing it", and it
is the wrong instrument here for two measured reasons from this repository's own
history: an equal-length source mutation leaves Python serving a stale `.pyc`
so the mutant keeps running after the restore, and mutated source has been
committed once. A monkeypatch cannot be left behind in a commit.

EVERY MUTATION IS PROVEN TO HAVE APPLIED. A patch that silently no-ops gives a
green suite and a false conclusion, so each mutation test asserts the stub was
actually CALLED before it draws any conclusion from the outcome.

WHAT IS DELIBERATELY NOT ASSERTED HERE. Nothing in this file says the ceiling's
NUMBERS are right, and nothing proposes new ones. `pilotcaps.CEILING` is the
operator's to set.
"""
import unittest
from unittest import mock

from src import actionledger, executionguard, pilotcaps

from tests.test_no_write_happens_without_every_gate import GuardTest


class TheCeilingIsEnforcedByExactlyOneCall(unittest.TestCase):
    """Where the enforcement lives, asserted so a change has to be deliberate.

    `pilotcaps.require` is the enforcer and `executionguard.authorize` is its
    only production caller. Both halves matter: a second caller appearing is a
    second place the ceiling could be got wrong, and the caller DISAPPEARING is
    the ceiling becoming a declaration again.
    """

    def test_require_raises_rather_than_returning_a_verdict(self):
        """An enforcer refuses. A function that returns False is an opinion."""
        with self.assertRaises(pilotcaps.PilotCapExceeded):
            pilotcaps.require({"new_accounts_per_day": 10_000},
                              not_checking=set(pilotcaps.KEYS)
                              - {"new_accounts_per_day"})

    def test_an_unacknowledged_ceiling_is_itself_a_refusal(self):
        """The property that makes the mapping load-bearing rather than prose.

        `require` refuses a plan that is SILENT about a ceiling, which is why
        `executionguard.CAPS_ENFORCED_ELSEWHERE` is an argument and not a
        comment: deleting it would make gate 5 refuse every action.
        """
        with self.assertRaises(Exception) as caught:
            pilotcaps.require({"new_accounts_per_day": 1})     # names nothing
        self.assertNotIsInstance(caught.exception, pilotcaps.PilotCapExceeded)

    def test_caps_enforced_elsewhere_is_consumed_not_merely_declared(self):
        """It is passed INTO `require`, so it cannot be deleted as dead prose.

        Asserted on behaviour rather than on the text of the source: every key
        it names must be one `require` accepts as an acknowledgement.
        """
        acknowledged = dict(executionguard.CAPS_ENFORCED_ELSEWHERE)
        self.assertTrue(acknowledged, "the mapping is empty")
        for key in acknowledged:
            self.assertIn(key, pilotcaps.KEYS)
        plan = {k: 1 for k in pilotcaps.KEYS if k not in acknowledged}
        self.assertTrue(pilotcaps.require(plan, not_checking=acknowledged))


class RemovingTheEnforcerTurnsTheseRed(GuardTest):
    """The mutation controls. Each one stubs the enforcer and requires the
    refusal to DISAPPEAR - which is the only evidence that the refusal was
    coming from the enforcer and not from some other gate firing first."""

    def setUp(self):
        super().setUp()
        self.config = dict(self.config,
                           daily_volume={"linkedin": 10, "email": 10})

    def open_accounts(self, n):
        """Open `n` other accounts today, on the other channel.

        Email rather than LinkedIn so the ACCOUNT ceiling is what trips, not a
        per-channel one - `accounts_opened_on` ignores the channel and
        `count_on(channel=...)` does not.
        """
        for i in range(n):
            actionledger.reserve(
                f"mut-{i}:p:em1:email", channel="email",
                workspace="productive", campaign_id="c1", sender_id=900,
                rec_id=f"mut-{i}", contact_key="p", step_key="em1",
                operation="op", fingerprint="fp")

    # ---------------------------------------------------- the baseline, first
    def test_baseline_the_sixth_account_is_refused_at_pilot_cap(self):
        """Without this passing, the mutation control below proves nothing."""
        self.open_accounts(5)
        refusal = self.refused_at("pilot_cap", config=self.config)
        self.assertIn("6", refusal.why)

    # ------------------------------------------------- the mutation control
    def test_stubbing_gate_5_moves_the_refusal_it_does_not_remove_it(self):
        """MEASURED 2026-10-14, and the opposite of what was expected.

        Stubbing `pilotcaps.require` does NOT authorize the sixth account. The
        refusal moves from gate `pilot_cap` to gate `ledger`, because
        `actionledger.reserve` is given `cap_new_accounts` and re-checks it
        INSIDE THE LOCK (`executionguard.py:976-982`, whose comment says this
        is deliberate: between gate 5 and the reservation another worker may
        have opened the last account of the day).

        So `new_accounts_per_day` has TWO independent enforcers, and this test
        is the regression guard for the second one. If this ever starts
        returning an authorization, the backstop has been removed and gate 5 is
        the only thing standing between a pilot and an overrun.
        """
        self.open_accounts(5)
        stub = mock.Mock(return_value=True)
        with mock.patch.object(pilotcaps, "require", stub):
            refusal = self.refused_at("ledger", config=self.config)

        # The mutation applied. Asserted BEFORE anything is concluded from the
        # outcome, because a patch that no-ops looks exactly like a pass.
        self.assertTrue(stub.called,
                        "the stub was never called, so this test mutated "
                        "nothing and its result means nothing")
        self.assertIn("5 new account(s) a day", refusal.why)

    def test_the_baseline_refusal_really_came_from_gate_5(self):
        """Which gate fired FIRST, which the moved refusal above cannot show.

        With gate 5 live the refusal is `pilot_cap`; with it stubbed the
        refusal is `ledger`. Both measured on the same fixture, so the
        difference is attributable to the stub and nothing else.
        """
        self.open_accounts(5)
        live = self.refused_at("pilot_cap", config=self.config)
        self.assertIn("6", live.why)

        stub = mock.Mock(return_value=True)
        with mock.patch.object(pilotcaps, "require", stub):
            stubbed = self.refused_at("ledger", config=self.config)
        self.assertTrue(stub.called)
        self.assertNotEqual(live.gate, stubbed.gate)


if __name__ == "__main__":
    unittest.main()
