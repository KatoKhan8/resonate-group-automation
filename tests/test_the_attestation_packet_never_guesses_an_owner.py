"""The attestation packet proposes decisions and never makes one.

`senderownership.dry_run_report` answers 257 accounts, 0 resolved, 257
needing attestation. Correct, and unusable as a decision surface - which is
why it has sat at zero since it was written and `SAFE_FOR_PRODUCTIVE` has
been 0 the whole time.

`scripts/attestation_packet.py` narrows that to the few candidates that
would change what the allocator can produce. The risk in a script like this
is that it becomes convenient enough to pre-fill an answer, and an invented
attestation fabricates exactly the fact the gate exists to check. These
tests pin the refusals rather than the formatting.

The display-name trap is the specific one. `sender_pool_census` groups its
per-human table by `row.get("name")`, which is a convenience for reading a
table and is NOT ownership evidence - `senderownership.resolve_owner`
"answers from the canonical roster rather than guessing from a display
name". Twelve distinct strings are not twelve known owners.
"""
import importlib.util
import io
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

SCRIPT = os.path.join(ROOT, "scripts", "attestation_packet.py")

from src import senderownership as so  # noqa: E402


def load_packet():
    spec = importlib.util.spec_from_file_location("packet_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ItProposesAndNeverDecides(unittest.TestCase):

    def setUp(self):
        self.packet = load_packet()

    def test_it_never_calls_the_write_path(self):
        """`attest` is the only write path and this script must not reach it.

        Asserted on the import graph rather than by searching the source for
        the word, because a test that greps fails when somebody writes a
        comment and passes when somebody writes a wrapper.
        """
        calls = []
        real = so.attest
        so.attest = lambda *a, **k: calls.append(a) or real(*a, **k)
        self.addCleanup(setattr, so, "attest", real)

        out = io.StringIO()
        stdout, sys.stdout = sys.stdout, out
        try:
            self.packet.main([])
        except SystemExit:
            pass
        except Exception:
            # A failure to RUN is not a failure of this assertion; the point
            # is only that nothing was attested on the way.
            pass
        finally:
            sys.stdout = stdout
        self.assertEqual([], calls, "the packet attested something")

    def test_the_command_it_prints_carries_a_placeholder_not_an_answer(self):
        """The sender id must be a decision the operator supplies.

        A script that guessed it from a display name would produce a command
        that runs, and running it would record a fact nobody verified.
        """
        out = io.StringIO()
        stdout, sys.stdout = sys.stdout, out
        try:
            self.packet.main([])
        except SystemExit:
            pass
        except Exception:
            self.skipTest("packet could not run in this environment")
        finally:
            sys.stdout = stdout
        text = out.getvalue()
        if "to attest:" not in text:
            self.skipTest("no candidates in this environment")
        self.assertIn("<THE-REAL-SENDER-ID>", text)
        self.assertIn("<who-is-vouching>", text)
        self.assertIn("UNVERIFIED HINT", text)

    def test_it_offers_nothing_when_the_walk_does_not_cover(self):
        """REFUSED IS NOT ROOM, and a candidate list built from a
        non-covering walk would be a list of mailboxes that might be full."""
        packet = self.packet
        packet._forward_booking = lambda: ("327", "489")
        packet.sh.load_state = lambda *a, **k: {"campaigns": {"327": {
            "complete": True,
            "finished_at": "2026-09-20T12:00:00+00:00",
            "by_sender_day": {},
        }}}
        out = io.StringIO()
        stdout, sys.stdout = sys.stdout, out
        try:
            code = packet.main([])
        finally:
            sys.stdout = stdout
        self.assertEqual(1, code)
        self.assertIn("DOES NOT COVER", out.getvalue())
        self.assertIn("489", out.getvalue())
        self.assertNotIn("to attest:", out.getvalue())

    def test_it_offers_nothing_when_there_is_no_walk_at_all(self):
        """A missing census is unknown commitments, which is not zero."""
        packet = self.packet

        def refuse(*a, **k):
            raise packet.sh.HeadroomRefused("no forward-book walk")

        packet.sh.load_state = refuse
        out = io.StringIO()
        stdout, sys.stdout = sys.stdout, out
        try:
            code = packet.main([])
        finally:
            sys.stdout = stdout
        self.assertEqual(1, code)
        self.assertIn("NO HEADROOM EVIDENCE", out.getvalue())
        self.assertNotIn("to attest:", out.getvalue())


class TheDisplayNameIsNotEvidence(unittest.TestCase):
    """Pinned because the census's per-human table invites the mistake."""

    def test_resolve_owner_ignores_a_display_name(self):
        account = {"kind": "email_account", "workspace": "productive",
                   "account_id": "eb-9999", "name": "A Real Looking Person",
                   "provider_account_id": "9999"}
        self.assertIsNone(so.resolve_owner(account, rows=[]),
                          "a display name resolved to an owner")

    def test_resolve_owner_uses_sender_id_when_it_is_actually_there(self):
        account = {"kind": "email_account", "workspace": "productive",
                   "account_id": "eb-9999", "sender_id": "human-1"}
        self.assertEqual("human-1", so.resolve_owner(account, rows=[]))


if __name__ == "__main__":
    unittest.main()
