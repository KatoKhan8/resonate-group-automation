"""A non-facing provider write may not be anonymous.

WHAT THIS GUARDS. `providerwrites._perform` step 2 has always refused a
PROSPECT-FACING write that cannot present an `executionguard.Authorization`.
The non-facing branch presented nothing at all until 2026-10-14: create a
campaign, install a sequence, assign a sender, pause, create a list and both
stop-leads reached the transport with no token of any kind. Measured: twelve
scripts under `scripts/` did exactly that
(`pilotcaps-enforcement-2026-10-14/SINK-TOKEN-SPLIT.json`).

The refusal is at the SINK, so a script that never learned about it is refused
anyway. These are the two tests that refusal needs:

  1. `AScriptThatMintsNoGrantCannotWrite` - the shape of a real ungated call is
     refused BEFORE the transport, so nothing reaches a provider.
  2. `TheRefusalIsWhatStopsIt` - removing the check makes the write reach the
     transport again. Without this, (1) could be passing because of some other
     guard and nobody would know which.

WHY `LINKEDIN_CREATE_LIST`. It is non-facing, in `SUPPORTED`, and carries no
`CONDITIONAL` entry, so the gate token is the only thing between the call and
the transport - which is what makes the mutation attributable. `GuardTest` is
reused from `test_an_internal_campaign_is_never_touched` rather than
reimplemented, because it already supplies the ledger and declaration fixtures
a provider write needs, and a hand-rolled fixture here failed for an unrelated
reason (`bison.assign_sender`'s conditional campaign allowlist) before this
note was written.

HOW THE MUTATION IS DONE. The check is `isinstance(gate, GateToken)`, inline in
`_perform`. "Removing it" is simulated by replacing `GateToken` with a class
whose metaclass answers `__instancecheck__` True for anything - precisely the
behaviour of that line not refusing - and passing an object that is not a
GateToken. A source edit was the alternative and is the wrong instrument: an
equal-length mutation in this repository leaves Python serving a stale `.pyc`,
so the mutant keeps running after the restore.

Every mutation test asserts the mutation APPLIED before concluding anything
from the outcome, because a patch that silently no-ops looks exactly like a
pass.
"""
import unittest
from unittest import mock

from src import providerwrites as pw

from tests.test_an_internal_campaign_is_never_touched import GuardTest


class _AnythingIsAToken(type):
    """Metaclass whose instances accept any object at all."""

    def __instancecheck__(cls, other):
        return True


class _PermissiveToken(object, metaclass=_AnythingIsAToken):
    """Stands in for `GateToken` with the refusal effectively deleted.

    It accepts `GateToken`'s constructor arguments so that `grant()` still
    works while this is patched in - otherwise the mutation would fail inside
    the mint and never reach the sink, which is the line it is testing.
    """

    def __init__(self, *args, **kw):
        self.operation = args[0] if args else kw.get("operation")
        self.by = args[1] if len(args) > 1 else kw.get("by")
        self.why = args[2] if len(args) > 2 else kw.get("why")


OPERATION = pw.LINKEDIN_CREATE_LIST


class AScriptThatMintsNoGrantCannotWrite(GuardTest):
    """The deliverable: no grant, no provider contact."""

    def test_the_operation_is_non_facing_or_this_tests_nothing(self):
        """If this ever becomes facing, these tests are about the wrong branch."""
        _channel, facing, _why = pw.describe(OPERATION)
        self.assertFalse(facing)
        self.assertIn(OPERATION, pw.SUPPORTED)

    def test_no_gate_is_refused_before_the_transport(self):
        self.ours()
        self.assertRefusedBeforeTheNetwork(OPERATION, gate=None)

    def test_the_refusal_says_what_to_do_about_it(self):
        self.ours()
        with self.assertRaises(pw.WriteRefused) as caught:
            self.perform(OPERATION, gate=None)
        self.assertIn("requires a GateToken", str(caught.exception))
        self.assertIn("providerwrites.grant", str(caught.exception))

    def test_a_dict_shaped_like_a_grant_is_not_a_grant(self):
        """The same property the facing branch has: proof, not resemblance."""
        self.ours()
        self.assertRefusedBeforeTheNetwork(
            OPERATION, gate={"operation": OPERATION, "by": "me",
                             "why": "because"})

    def test_a_grant_for_a_different_operation_is_refused(self):
        self.ours()
        other = pw.grant(pw.LINKEDIN_PAUSE, by="zvonimir",
                         why="a grant minted for the wrong verb")
        with self.assertRaises(pw.WriteRefused) as caught:
            self.perform(OPERATION, gate=other)
        self.assertIn("the grant is for", str(caught.exception))
        self.assertEqual(self.reached, [])

    def test_a_real_grant_lets_it_through_to_the_transport(self):
        """Or the refusal is a ban rather than a gate."""
        self.ours()
        good = pw.grant(OPERATION, by="zvonimir",
                        why="creating the staging list for cohort B")
        self.assertReachedTheTransport(OPERATION, gate=good)


class TheRefusalIsWhatStopsIt(GuardTest):
    """The mutation control. Delete the check and the write gets through."""

    def test_removing_the_gatetoken_check_reaches_the_transport_again(self):
        self.ours()
        # Not a GateToken. Under the real check this is refused; with the
        # check removed it is indistinguishable from one.
        impostor = mock.Mock(operation=OPERATION, by="nobody", why="nothing")
        with mock.patch.object(pw, "GateToken", _PermissiveToken):
            # THE MUTATION APPLIED. Asserted before any conclusion is drawn
            # from the call below, because a patch that no-ops looks like a
            # pass.
            self.assertIsInstance(impostor, pw.GateToken)
            self.assertReachedTheTransport(OPERATION, gate=impostor)

    def test_the_same_impostor_is_refused_with_the_check_in_place(self):
        """The other half of the attribution: same input, check restored."""
        self.ours()
        impostor = mock.Mock(operation=OPERATION, by="nobody", why="nothing")
        self.assertNotIsInstance(impostor, pw.GateToken)
        self.assertRefusedBeforeTheNetwork(OPERATION, gate=impostor)


class TheGrantItselfRefusesTheWrongThing(unittest.TestCase):
    """`grant` is a gate too, not a constructor with a nicer name."""

    def test_a_facing_operation_cannot_be_granted(self):
        with self.assertRaises(pw.WriteRefused) as caught:
            pw.grant(pw.EMAIL_ACTIVATE, by="zvonimir", why="activating 485")
        self.assertIn("Authorization", str(caught.exception))

    def test_an_unsupported_operation_cannot_be_granted(self):
        unsupported = [o for o in pw.OPERATIONS if o not in pw.SUPPORTED]
        self.assertTrue(unsupported, "every operation is supported")
        with self.assertRaises(pw.WriteRefused):
            pw.grant(unsupported[0], by="zvonimir", why="should not mint")

    def test_an_anonymous_grant_is_refused(self):
        for bad in ("", "   ", None):
            with self.assertRaises(pw.WriteRefused):
                pw.grant(pw.LINKEDIN_PAUSE, by=bad, why="a reason")

    def test_a_grant_with_no_reason_is_refused(self):
        for bad in ("", "   ", None):
            with self.assertRaises(pw.WriteRefused):
                pw.grant(pw.LINKEDIN_PAUSE, by="zvonimir", why=bad)

    def test_a_good_grant_carries_who_and_why(self):
        token = pw.grant(pw.LINKEDIN_PAUSE, by="  zvonimir  ",
                         why="  pausing the canary  ")
        self.assertEqual(token.operation, pw.LINKEDIN_PAUSE)
        self.assertEqual(token.by, "zvonimir")
        self.assertEqual(token.why, "pausing the canary")


if __name__ == "__main__":
    unittest.main()
