"""A suppressed contact must not reach bison.resume_campaign - batch_activate.

The operator's assertion, 2026-10-15 23:00, TASK 0200: "A suppressed contact
must not reach `bison.resume_campaign` by either path." This module covers
the batch_activate path. The sibling module
test_a_suppressed_contact_must_not_reach_bison_resume_from_resume_487
covers the other one. Two sites, two tests, because a single test passing
says nothing about which site it entered.

pilotcaps/0160 measured the site: scripts/batch_activate.py:144 called
bison.resume_campaign directly, importing neither killswitch nor
suppression - one of only two write paths of 58 that could reach a real
person ungated. The fix consults the two gates that already exist, in this
order, and builds no third gate:

1. TASK-331's suppression revalidation,
   providerwrites.CONDITIONAL[EMAIL_RESUME] - the same callable `perform`
   runs for a gated resume.
2. killswitch.require(workspace="productive") - read-only, most
   restrictive layer wins, and today it ALWAYS refuses: the global layer
   refuses in code and the workspace has never been switched on.

Suppression first, on purpose. The freeze refuses everything today, so a
killswitch consulted first would mask the per-contact reason, and the
operator would read a workspace verdict where a named lead stopped the
resume. The suppressed test below enforces that ordering itself: it fails
when the per-lead reason is masked, not only when the verb is reached.

Born-red at 9949dc205, before the fix: both reach tests failed with the
recorder holding ('9001', 2) - the verb was called against a suppressed
contact and again against a clean one, freeze notwithstanding. The
premise tests passed, so the red was reach and nothing else.

Mutation map, proven per state with byte-exact restores:
- suppression consult removed -> the suppressed test fails on the reason
  assertion, not on reach. The killswitch still blocks the verb, but only
  as a freeze; what the mutation loses is the named lead, and that is what
  the test holds.
- killswitch consult removed -> the freeze test fails on reach: a clean
  campaign's verb is called.
- both removed (the original ungated code) -> both tests fail on reach:
  the born-red state reproduced.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import killswitch, providerwrites, store              # noqa: E402
from src.providers import bison                                # noqa: E402
from tests.campaignbase import CampaignTest                    # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import batch_activate as activate                              # noqa: E402

WORKSPACE = "productive"
PREFIX = "productive-email-batch1-"


class _ResumeLedgerMixin:
    """Point the action ledger at a throwaway file. Never the real work/."""

    def _setup_ledger(self):
        self.ledger_tmp = tempfile.mkdtemp(prefix="rga-resume-ledger-")
        self.ledger_path = os.path.join(self.ledger_tmp,
                                        "provider-writes.jsonl")
        self._old_ledger = os.environ.get(
            providerwrites.PROVIDER_WRITES_LEDGER)
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self.ledger_path
        self.addCleanup(self._restore_ledger)
        self.addCleanup(shutil.rmtree, self.ledger_tmp, ignore_errors=True)

    def _restore_ledger(self):
        if self._old_ledger is None:
            os.environ.pop(providerwrites.PROVIDER_WRITES_LEDGER, None)
        else:
            os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = (
                self._old_ledger)


class _BatchActivateHarness(_ResumeLedgerMixin, CampaignTest):
    """Drive the pre-existing main(["--live"]) offline, at the seam.

    The verb was inline in main, so the born-red test has to drive main
    itself: a test calling a gate function the fix adds would be red for
    the wrong reason (AttributeError, not reach). Everything provider-facing
    is patched; the two gates under test are NOT patched - suppression and
    the killswitch run for real against the fixture store, and
    ProviderTest's network tripwire stays armed behind them.
    """

    def _run_activate(self):
        reached = []

        def record_resume(provider_id, expect_leads=None):
            reached.append((provider_id, expect_leads))
            return {"status": "in_sequence"}

        provider_row = {"status": "paused", "total_leads": 2,
                        "emails_sent": 0, "bounced": 0, "unsubscribed": 0}
        # TASK 0398: the bounce hard stop now refuses a mailbox it cannot
        # judge, so `mailbox_health` returning `{}` would halt this run
        # BEFORE the two gates under test were consulted - and the halt
        # also prints "REFUSED", so the module would have stayed green
        # while watching nothing. The seats are named and healthy here on
        # purpose: the bounce stop must PASS so that a verb not reached is
        # attributable to suppression or to the killswitch.
        seats = self.make_senders_nameable(PREFIX + "alpha")
        healthy = {seat: activate.classify(1877, 8, seat=seat)
                   for seat in seats}
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                mock.patch.object(activate, "load_env", lambda: None), \
                mock.patch.object(activate, "mailbox_health",
                                  lambda: healthy), \
                mock.patch.object(activate, "ROOT", self.tmp), \
                mock.patch.object(activate.time, "sleep",
                                  lambda seconds: None), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: dict(provider_row)), \
                mock.patch.object(bison, "scheduled_emails",
                                  lambda pid: []), \
                mock.patch.object(bison, "resume_campaign", record_resume):
            code = activate.main(["--live"])
        return code, out.getvalue(), reached


class SuppressedContactMustNotReachTheVerb(_BatchActivateHarness):

    def test_a_suppressed_contact_must_not_reach_bison_resume_campaign(self):
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=PREFIX + "alpha")
        # The house suppression lever TASK-331 pinned: the contact-level
        # unsubscribe, persisted through the store the gate re-reads.
        recs[0]["contacts"][0]["unsubscribed"] = True
        store.save(recs)

        # Premise, measured not assumed: the real gate refuses THIS fixture
        # and names the count. If this premise breaks, the fixture broke -
        # not the script under test.
        predicate = providerwrites.CONDITIONAL[providerwrites.EMAIL_RESUME]
        with self.assertRaises(providerwrites.WriteRefused) as raised:
            predicate("9001", PREFIX + "alpha")
        self.assertIn("1 contact(s) are suppressed", str(raised.exception))

        _code, out, reached = self._run_activate()

        self.assertEqual(
            reached, [],
            "A suppressed contact must not reach bison.resume_campaign by "
            f"either path. batch_activate reached it for {PREFIX}alpha "
            "(provider 9001) with a suppressed contact on record acme.")
        self.assertIn("REFUSED", out)
        self.assertIn(
            "1 contact(s) are suppressed", out,
            "a refused lead is counted and named by reason. A killswitch "
            "consulted first would mask the named lead behind the workspace "
            "verdict - suppression comes first on purpose.")
        self.assertIn("acme-champ", out, "the refused lead is named")


class TheFreezeStillRefusesACleanCampaign(_BatchActivateHarness):
    """A clean campaign is not a permitted campaign while the freeze stands.

    No test in this suite fabricates a permitting killswitch world; none has
    ever existed. The clean control is decomposed the way TASK-331 and 0130
    decomposed theirs: the premises are measured, the same predicate the
    site consults passes the clean fixture, and the verb still does not
    happen - because the freeze refuses it, named.
    """

    def test_premises_measured_not_assumed(self):
        from src import push
        self.assertTrue(
            hasattr(push, "LiveSendNotEnabled"),
            "the global layer refuses IN CODE. If this premise breaks, "
            "sending was enabled in push and this module must be re-read "
            "in that new world, not deleted.")
        state = killswitch.workspace_state(WORKSPACE)
        self.assertFalse(
            state["sending"],
            f"workspace {WORKSPACE!r} must read off in this build; it "
            f"reads {state!r}")

    def test_the_verb_is_not_reached_while_the_freeze_stands(self):
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=PREFIX + "alpha")

        # Clean control: the gate the site consults PASSES this fixture.
        # Without it, a green refusal above could be the fixture refusing
        # everything, which would prove nothing about the killswitch.
        predicate = providerwrites.CONDITIONAL[providerwrites.EMAIL_RESUME]
        self.assertTrue(
            predicate("9001", PREFIX + "alpha"),
            "the clean control: the suppression gate must pass a clean "
            "campaign, or the refusal proven below is vacuous")

        _code, out, reached = self._run_activate()

        self.assertEqual(
            reached, [],
            "while the freeze stands, even a clean campaign's verb is not "
            "reached: killswitch.require is the second gate this site "
            "consults, and it refuses.")
        self.assertIn("SendingRefused", out,
                      "the freeze's refusal is surfaced and named")


if __name__ == "__main__":
    unittest.main()
