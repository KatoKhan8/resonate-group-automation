"""The sender attach passes the door, or it does not happen.

TASK 0240. `_ensure_senders` called `bison.attach_senders` directly: the
only thing standing between an existing campaign and a pool attach was
the accident that campaign creation happens first in `stage()` and the
door refuses THAT. On a campaign that already exists - the canary's own
shape - nothing refused the attach.

The invariant under test, from the brief:

    with provider writes unauthorised, an attach may not reach
    `bison.attach_senders`.

`bison.assign_sender` is a SUPPORTED operation whose CONDITIONAL is the
ten-pair operator allowlist at `providerwrites._AUTHORIZED_EMAIL_CAMPAIGNS`
(the same condition `EMAIL_ACTIVATE` runs). A campaign whose canonical id
is not one of the ten pairs - every new staging campaign, the client's
327/328/352, the historical 481/485 - is refused before the transport.

Every test patches at the bison seam only: `attach_senders` and
`campaign_senders` are replaced with in-memory fakes, and the campaign
store, the write ledger and the STOP-SENDING path are pointed at temp
files. No provider call, no network call, no live anything; the real
brake path is never touched (`haltfile.STOP_SENDING_PATH` is patched at
a temp path, the seam TASK 0210 built for exactly this).

Born-red at HEAD (pre-0240): the unauthorised and mismatched tests fail
because the DIRECT call reaches the fake transport, which is the finding.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import bisonfactory, haltfile, providerwrites  # noqa: E402


AUTHORISED = "productive-email-control-v3"   # pinned to provider 487
UNAUTHORISED = "productive-email-batch2-nobody-v2"   # on no allowlist


def _campaign(canonical, provider_id, sender=2736):
    return {
        "campaign_id": canonical,
        "client": "productive",
        "bison_campaign_id": provider_id,
        "senders": {"email": [{"provider_account_id": sender}]},
    }


class _AttachSite(unittest.TestCase):
    """A throwaway campaign store, write ledger and brake, and a bison
    seam that records every call. Never the real `work/`, never the real
    STOP-SENDING path, never a provider."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-attach-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.campaigns = os.path.join(self.tmp, "campaigns.jsonl")
        self.ledger = os.path.join(self.tmp, "provider-writes.jsonl")
        self.brake = os.path.join(self.tmp, "STOP-SENDING")

        self._old = {name: os.environ.get(name) for name in
                     ("CAMPAIGNS", "PROVIDER_WRITES_LEDGER")}
        os.environ["CAMPAIGNS"] = self.campaigns
        os.environ["PROVIDER_WRITES_LEDGER"] = self.ledger
        self.addCleanup(self._restore)

        # The bison seam: the module object the factory itself holds.
        self.bison = bisonfactory.bison
        self.attached = []

        def fake_attach(provider_id, wanted):
            self.attached.append((provider_id, list(wanted)))
            return {"senders": list(wanted)}

        self.membership = []
        patcher = mock.patch.object(self.bison, "attach_senders",
                                    side_effect=fake_attach)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.patch_membership([])

    def _restore(self):
        for name, value in self._old.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def patch_membership(self, sequence):
        """What `campaign_senders` answers, call by call. The first call
        is `_ensure_senders`'s own pre-check; a second one, on the routed
        path, is the door's read-back."""
        self.membership = list(sequence)
        reads = []

        def fake_senders(_provider_id):
            reads.append(True)
            if not self.membership:
                return []
            return self.membership[min(len(reads) - 1,
                                       len(self.membership) - 1)]

        patcher = mock.patch.object(self.bison, "campaign_senders",
                                    side_effect=fake_senders)
        patcher.start()
        self.addCleanup(patcher.stop)

    def plant_campaign(self, row):
        with io.open(self.campaigns, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    def ledger_rows(self):
        if not os.path.exists(self.ledger):
            return []
        with io.open(self.ledger, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def run_site(self, row):
        report = {"did": [], "provider": {}}
        bisonfactory._ensure_senders(str(row["bison_campaign_id"]), row,
                                     report)
        return report


class AnUnauthorisedAttachNeverReachesTheTransport(_AttachSite):

    def test_a_campaign_on_no_allowlist_is_refused_before_bison(self):
        """The canary shape: a campaign that ALREADY EXISTS, so nothing
        upstream refuses for it. Its canonical id is on no operator
        allowlist, so the attach is unauthorised - and it may not reach
        `bison.attach_senders`."""
        self.plant_campaign(_campaign(UNAUTHORISED, 555))
        with self.assertRaises(providerwrites.WriteRefused) as raised:
            self.run_site(_campaign(UNAUTHORISED, 555))
        self.assertIn("The transport was not reached", str(raised.exception))
        self.assertEqual(
            [], self.attached,
            "an attach the operator never authorised reached the bison "
            "transport")
        # The refusal is ledgered - through the door means visible in the
        # door's own audit trail, refusal included (step UNKNOWN: a
        # staging write carries no Authorization to name one, TASK 0230).
        rows = [r for r in self.ledger_rows()
                if r.get("operation") == providerwrites.EMAIL_ASSIGN_SENDER]
        self.assertEqual(1, len(rows), "the refused attach was not ledgered")
        self.assertEqual("refused", rows[0]["outcome"])
        self.assertEqual(UNAUTHORISED, rows[0]["campaign"])

    def test_a_mismatched_binding_is_refused_before_bison(self):
        """The canonical row is allowlisted and pinned to 487, but the
        caller offers a different provider campaign. A mismatched binding
        is how a send reaches a campaign nobody approved."""
        self.plant_campaign(_campaign(AUTHORISED, 487))
        offered = _campaign(AUTHORISED, 499)
        with self.assertRaises(providerwrites.WriteRefused) as raised:
            self.run_site(offered)
        self.assertIn("The transport was not reached", str(raised.exception))
        self.assertEqual([], self.attached)


class AnAuthorisedAttachStillLands(_AttachSite):

    def test_the_allowlisted_campaign_attaches_through_the_door(self):
        """Routing through the door must not break the one shape the
        operator authorised: the control campaign, bound and pinned. The
        attach still happens - and now it is ledgered and staged-recorded,
        which is what 'through the door' means."""
        row = _campaign(AUTHORISED, 487)
        self.plant_campaign(row)
        self.patch_membership([[], [2736]])    # pre-check empty, read-back bound
        report = self.run_site(row)
        self.assertEqual([("487", [2736])], self.attached)
        self.assertEqual([2736], report["provider"]["senders"])
        self.assertTrue(any("bound 1 sender inbox" in d for d in report["did"]),
                        report["did"])
        rows = [r for r in self.ledger_rows()
                if r.get("operation") == providerwrites.EMAIL_ASSIGN_SENDER]
        self.assertEqual(1, len(rows),
                         "the performed attach was not ledgered")
        # "accepted" is the door's own class for a staging write whose
        # read-back agreed (`providerwrites.ACCEPTED`), not "performed",
        # which is the fallback for a write nothing classified.
        self.assertEqual("accepted", rows[0]["outcome"])
        # The door records the staged material on the campaign row, so a
        # crash between attach and finish cannot silently re-attach.
        with io.open(self.campaigns, encoding="utf-8") as fh:
            stored = json.loads(fh.read())
        self.assertIn(providerwrites.EMAIL_ASSIGN_SENDER,
                      (stored.get("provider_staged") or {}))


class TheNoOpPathsStayNoOps(_AttachSite):

    def test_already_bound_senders_do_not_knock_on_the_door(self):
        """Every asked-for inbox is already bound: the site's own early
        return. It must stay a no-op - not become a door refusal - or
        restaging a fully-bound campaign on an unauthorised canonical
        would start failing mid-flight."""
        row = _campaign(UNAUTHORISED, 555)
        self.plant_campaign(row)
        self.patch_membership([[2736]])
        report = self.run_site(row)
        self.assertEqual([], self.attached)
        self.assertTrue(any("already bound" in d for d in report["did"]),
                        report["did"])
        self.assertEqual([], self.ledger_rows())

    def test_the_stop_sending_brake_stops_the_attach(self):
        """Attaching a sender is the step that makes a campaign ABLE to
        send, so STOP-SENDING stops it: a halt that leaves campaigns
        armable is not a halt. The site consults the brake before the
        door; the door consults it again immediately before the transport
        (pinned behaviourally by the TASK 0210 door test)."""
        row = _campaign(AUTHORISED, 487)
        self.plant_campaign(row)
        self.patch_membership([[], [2736]])
        with io.open(self.brake, "wb"):
            pass                       # the zero-byte file, at a temp path
        with mock.patch.object(haltfile, "STOP_SENDING_PATH", self.brake):
            with self.assertRaises(haltfile.OperatorStop):
                self.run_site(row)
        self.assertEqual([], self.attached,
                         "the operator's brake was pulled and the attach "
                         "reached the transport anyway")


if __name__ == "__main__":
    unittest.main()
