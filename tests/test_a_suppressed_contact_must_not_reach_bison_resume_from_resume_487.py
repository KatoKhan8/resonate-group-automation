"""A suppressed contact must not reach bison.resume_campaign - resume_487.

The operator's assertion, 2026-10-15 23:00, TASK 0200: "A suppressed contact
must not reach `bison.resume_campaign` by either path." This module covers
the resume_487 path. The sibling module
test_a_suppressed_contact_must_not_reach_bison_resume_from_batch_activate
covers the other one. Two sites, two tests, because a single test passing
says nothing about which site it entered.

pilotcaps/0160 measured the site: scripts/resume_487.py:269 called
bison.resume_campaign directly, importing neither killswitch nor
suppression - the other of the only two write paths of 58 that could reach
a real person ungated. The fix consults the two gates that already exist,
in this order, and builds no third gate:

1. TASK-331's suppression revalidation,
   providerwrites.CONDITIONAL[EMAIL_RESUME], against 487's canonical
   campaign row - the same callable `perform` runs for a gated resume.
2. killswitch.require(workspace="productive") - read-only, most
   restrictive layer wins, and today it ALWAYS refuses: the global layer
   refuses in code and the workspace has never been switched on.

Suppression first, on purpose. The freeze refuses everything today, so a
killswitch consulted first would mask the per-contact reason, and the
operator would read a workspace verdict where a named lead stopped the
resume. The suppressed test below enforces that ordering itself: it fails
when the per-lead reason is masked, not only when the verb is reached.

A gate refusal here is deliberately NOT routed through the script's
"PROVIDER REFUSED ... Condition 5: ONCE. Do not retry. Read provider
truth" handler: the provider was never reached, provider truth is the
wrong document to read, and the WriteRefused already says what to do
(re-read the stops). The gate gets its own wording before the window.

Born-red at 9949dc205, before the fix: both reach tests failed with the
recorder holding (487, 10) - the verb was called inside the live window
against a suppressed contact and again against a clean one, freeze
notwithstanding. The premise tests passed, so the red was reach and
nothing else.

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
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import killswitch, providerwrites, store      # noqa: E402
from src.providers import bison                        # noqa: E402
from tests.campaignbase import CampaignTest            # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import resume_487 as recover                           # noqa: E402

WORKSPACE = "productive"
CANONICAL_ID = "productive-email-control-v3"


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


class _Resume487Harness(_ResumeLedgerMixin, CampaignTest):
    """Drive the pre-existing main(["--live"]) offline, at the seam.

    The verb was inline in main behind the window, so the born-red test has
    to drive main itself: a test calling a gate function the fix adds would
    be red for the wrong reason (AttributeError, not reach). The calendar,
    truth and copy gates are patched out of the way - they belong to the
    2026-09-20 authorization and are not what this task measures. The two
    gates under test are NOT patched: suppression and the killswitch run
    for real against the fixture store, and ProviderTest's network
    tripwire stays armed behind them. _setup_data_access is neutralised
    because the real one would read config/.env, which no test may touch.
    """

    def _run_recover(self):
        reached = []

        def record_resume(provider_id, expect_leads=None):
            reached.append((provider_id, expect_leads))
            return {"status": "in_sequence"}

        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                mock.patch.object(recover, "_setup_data_access",
                                  lambda: None), \
                mock.patch.object(recover, "window_gate", lambda: True), \
                mock.patch.object(recover, "truth_gate",
                                  lambda b: ({"status": "paused"},
                                             {"sending_paused": 10},
                                             {"timezone": "Europe/Zagreb"})), \
                mock.patch.object(recover, "copy_gate", lambda: True), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: {"status": "in_sequence"}), \
                mock.patch.object(bison, "membership", lambda cid: {}), \
                mock.patch.object(bison, "resume_campaign", record_resume):
            code = recover.main(["--live"])
        return code, out.getvalue(), reached


class SuppressedContactMustNotReachTheVerb(_Resume487Harness):

    def test_a_suppressed_contact_must_not_reach_bison_resume_campaign(self):
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=CANONICAL_ID)
        # The house suppression lever TASK-331 pinned: the contact-level
        # unsubscribe, persisted through the store the gate re-reads.
        recs[0]["contacts"][0]["unsubscribed"] = True
        store.save(recs)

        # Premise, measured not assumed: the real gate refuses THIS fixture
        # and names the count. If this premise breaks, the fixture broke -
        # not the script under test.
        predicate = providerwrites.CONDITIONAL[providerwrites.EMAIL_RESUME]
        with self.assertRaises(providerwrites.WriteRefused) as raised:
            predicate(487, CANONICAL_ID)
        self.assertIn("1 contact(s) are suppressed", str(raised.exception))

        code, out, reached = self._run_recover()

        self.assertEqual(
            reached, [],
            "A suppressed contact must not reach bison.resume_campaign by "
            "either path. resume_487 reached it for provider 487 with a "
            "suppressed contact on the canonical campaign record acme.")
        self.assertEqual(code, 1)
        self.assertIn("GATE REFUSED", out)
        self.assertIn(
            "1 contact(s) are suppressed", out,
            "a refused lead is counted and named by reason. A killswitch "
            "consulted first would mask the named lead behind the workspace "
            "verdict - suppression comes first on purpose.")
        self.assertIn("acme-champ", out, "the refused lead is named")


class TheFreezeStillRefusesACleanCampaign(_Resume487Harness):
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
        self.make_campaign(recs, campaign_id=CANONICAL_ID)

        # Clean control: the gate the site consults PASSES this fixture.
        # Without it, a green refusal above could be the fixture refusing
        # everything, which would prove nothing about the killswitch.
        predicate = providerwrites.CONDITIONAL[providerwrites.EMAIL_RESUME]
        self.assertTrue(
            predicate(487, CANONICAL_ID),
            "the clean control: the suppression gate must pass a clean "
            "campaign, or the refusal proven below is vacuous")

        code, out, reached = self._run_recover()

        self.assertEqual(
            reached, [],
            "while the freeze stands, even a clean campaign's verb is not "
            "reached: killswitch.require is the second gate this site "
            "consults, and it refuses.")
        self.assertEqual(code, 1)
        self.assertIn("SendingRefused", out,
                      "the freeze's refusal is surfaced and named")
        self.assertIn("GATE REFUSED", out)


if __name__ == "__main__":
    unittest.main()
