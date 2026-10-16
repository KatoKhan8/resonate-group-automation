#!/usr/bin/env python3
"""A mailbox the bounce hard stop cannot judge BLOCKS the send - TASK 0398.

CANARY EXIT BLOCKER 3 OF 4, and the only one of the four that was a missing
verdict rather than an unlanded fix (`CONTINUITY.md` §6). The hard stop that
is meant to halt a live send on bounces had never produced an answer for any
mailbox, so it had never been shown capable of halting anything.

THE DEFECT, measured at `f1552d4ec` before this module existed. The stop had
two answers and a third meaning crammed into `None`:

    scripts/batch_activate.py:72   rate = (bounced / sent) if sent else None
    scripts/batch_activate.py:83   rate, sent, bounced = health.get(seat,
                                                                   (None,0,0))
    scripts/batch_activate.py:84   if rate is not None and rate >= STOP:

so a seat with no sends, a seat missing from the provider read, a read that
returned nothing at all, and a campaign naming no mailbox each appended NO
reason - and `main` printed `ready`. Six of seven reachable cases printed
`ready`, including a mailbox carrying 9 bounces against 0 sends. That is this
estate's sixth failure family in one line: a result the instrument has no
name for, reported as the nearest name it has.

THE FIX. `UNKNOWN` is a first-class verdict, `MailboxVerdict.blocks` is true
for FAILING and for UNKNOWN, and `check` returns the two lists APART so the
three states stay distinguishable where a human reads them. Not a warning,
not a log line, not a default of healthy.

THE CONTROLS, and the fourth is what makes the others mean anything:

    C1  a mailbox with sent == 0 returns UNKNOWN, and UNKNOWN blocks
    C2  a mailbox over the threshold blocks the send THROUGH main(["--live"])
    C3  a mailbox with sends and no bounces is NOT blocked
    C4  with the threshold inverted, C2's send gets through - so C2 was
        measuring the stop and not the fixture
    C5  no caller is left reading the old falsy contract: `check` returns
        four values, `main` consumes the fourth, and an old-shape health
        read raises rather than passing

NO PROVIDER CALL, NO NETWORK, NO REAL STOP-SENDING FILE. Every test patches
at the bison seam, points the campaign store and the write ledger at temp
files, and patches `haltfile.STOP_SENDING_PATH` to a throwaway.

WHY `killswitch.require` IS PATCHED PERMISSIVE. The same reason the TASK
0210 and TASK 0395 modules give: the freeze refuses everything in this
build, so without the patch every test here would be refused by the freeze
before the bounce stop was consulted - green for the wrong reason.
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
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import campaigns, haltfile, providerwrites            # noqa: E402
from src.providers import bison                                # noqa: E402
from tests.campaignbase import CampaignTest                    # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import batch_activate as activate                              # noqa: E402

PREFIX = "productive-email-batch1-"
BATCH_PROVIDER_ID = "9001"

#: One of the canary pool's real EmailBison sender ids. Used as a label
#: only - no provider is called and no mailbox is touched.
SEAT = "3437"

UNKNOWN_WORDS = "UNKNOWN is not a pass"
STOP_WORDS = "at or over the 2% stop"


class _BounceStop(CampaignTest):
    """A batch-1 campaign fixture, driven through `main(["--live"])`.

    The stop is the ONLY guard left able to refuse: the brake is released,
    the killswitch is patched permissive, nothing is declared internal and
    the fixture's contacts are clean. So a verb that is not reached was
    stopped by the bounce stop, and a verb that IS reached proves the stop
    let it through.
    """

    def setUp(self):
        super().setUp()
        self.scratch = tempfile.mkdtemp(prefix="rga-0398-")
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)

        self.ledger_path = os.path.join(self.scratch, "provider-writes.jsonl")
        self._old_ledger = os.environ.get(
            providerwrites.PROVIDER_WRITES_LEDGER)
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self.ledger_path
        self.addCleanup(self._restore_ledger)

        # A path that does not exist, so the brake reads RELEASED. Nothing
        # here ever creates the real file.
        self.brake_path = os.path.join(self.scratch, "STOP-SENDING")
        self.declared_path = os.path.join(self.scratch,
                                          "internal-campaigns.txt")

    def _restore_ledger(self):
        if self._old_ledger is None:
            os.environ.pop(providerwrites.PROVIDER_WRITES_LEDGER, None)
        else:
            os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = \
                self._old_ledger

    # ------------------------------------------------------------ fixtures

    def seat_campaign(self, senders):
        """A batch-1 campaign whose email senders are exactly `senders`."""
        recs = self.seed_records()
        campaign = self.make_campaign(recs, campaign_id=PREFIX + "alpha")
        campaign["senders"] = {"email": list(senders), "linkedin": []}
        campaigns.save([campaign])
        return campaign

    def read(self, pairs):
        """`{seat: (sent, bounced)}` -> what `mailbox_health` would return.

        Built with the production classifier rather than hand-rolled, so a
        test can never assert against a verdict shape the script does not
        actually produce.
        """
        return {seat: activate.classify(sent, bounced, seat=seat)
                for seat, (sent, bounced) in pairs.items()}

    def drive(self, senders=({"provider_account_id": SEAT},), pairs=None):
        """Run main(["--live"]). Returns (stdout, reached)."""
        self.seat_campaign(senders)
        reached = []

        def record(provider_id, expect_leads=None):
            reached.append((provider_id, expect_leads))
            return {"status": "in_sequence"}

        provider_row = {"status": "paused", "total_leads": 2,
                        "emails_sent": 0, "bounced": 0, "unsubscribed": 0}
        health = self.read(pairs or {})
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                mock.patch.object(haltfile, "STOP_SENDING_PATH",
                                  self.brake_path), \
                mock.patch.object(providerwrites, "internal_campaigns_path",
                                  lambda: self.declared_path), \
                mock.patch("src.killswitch.require", lambda **kw: None), \
                mock.patch.object(activate, "load_env", lambda: None), \
                mock.patch.object(activate, "mailbox_health",
                                  lambda: health), \
                mock.patch.object(activate, "ROOT", self.tmp), \
                mock.patch.object(activate.time, "sleep", lambda s: None), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: dict(provider_row)), \
                mock.patch.object(bison, "scheduled_emails", lambda pid: []), \
                mock.patch.object(bison, "resume_campaign", record):
            activate.main(["--live"])
        return out.getvalue(), reached


# --------------------------------------------------------------------- C1


class UnknownIsReachable(_BounceStop):
    """C1. A mailbox the stop cannot judge returns UNKNOWN, not nothing."""

    def test_a_mailbox_with_no_sends_is_unknown(self):
        verdict = activate.classify(0, 0, seat=SEAT)
        self.assertEqual(verdict.verdict, activate.UNKNOWN)
        self.assertIsNone(verdict.rate,
                          "the rate is genuinely unavailable; the verdict "
                          "is what carries the meaning")
        self.assertTrue(verdict.blocks,
                        "UNKNOWN must block. A mailbox we cannot judge is "
                        "not a mailbox we judged clean.")

    def test_bounces_against_zero_sends_is_unknown_and_not_zero_percent(self):
        """The case that printed `ready` before this task: 9 of 0."""
        verdict = activate.classify(0, 9, seat=SEAT)
        self.assertEqual(verdict.verdict, activate.UNKNOWN)
        self.assertIn("UNDEFINED is not 0%", verdict.why)

    def test_a_seat_absent_from_the_provider_read_is_unknown(self):
        verdict = activate.classify(0, 0, seat=SEAT, seen=False)
        self.assertEqual(verdict.verdict, activate.UNKNOWN)
        self.assertIn("not in the provider's sender read", verdict.why)

    def test_mailbox_health_itself_yields_unknown_for_a_zero_send_row(self):
        """Through the real reader, at its own provider seam."""
        with mock.patch.object(bison, "sender_emails",
                               lambda: [{"id": 3437, "emails_sent_count": 0,
                                         "bounced_count": 0}]):
            got = activate.mailbox_health()
        self.assertEqual(got[SEAT].verdict, activate.UNKNOWN)

    def test_a_provider_read_that_carries_nothing_leaves_no_seat_healthy(self):
        """An empty read is not an estate with no bounces."""
        for answer in (None, [], ([], 0)):
            with mock.patch.object(bison, "sender_emails",
                                   lambda answer=answer: answer):
                self.assertEqual(activate.mailbox_health(), {})


# --------------------------------------------------------------------- C2


class TheStopActuallyStops(_BounceStop):
    """C2. Through `main(["--live"])`, the real call path."""

    def test_a_mailbox_over_the_stop_blocks_the_send(self):
        out, reached = self.drive(pairs={SEAT: (8947, 191)})
        self.assertEqual(reached, [],
                         "a mailbox at 2.13%% bounce is over the 2%% hard "
                         "stop and bison.resume_campaign was still called: "
                         "%s" % out)
        self.assertIn(STOP_WORDS, out,
                      "the refusal must be the BOUNCE stop's own words. Any "
                      "other wording means a different guard answered first "
                      "and this test is not watching what it claims to")
        self.assertIn("REFUSED", out)

    def test_an_unjudgeable_mailbox_blocks_the_send(self):
        """The whole point of the task: cannot-judge halts the send."""
        out, reached = self.drive(pairs={SEAT: (0, 0)})
        self.assertEqual(reached, [],
                         "the stop could not judge the only mailbox this "
                         "campaign would send from and the send went "
                         "anyway: %s" % out)
        self.assertIn(UNKNOWN_WORDS, out)
        self.assertIn("HALTED: UNKNOWN", out,
                      "UNKNOWN and FAILING both block and must still read "
                      "differently; a reader cannot act on a verdict that "
                      "prints as the other one")

    def test_a_seat_missing_from_the_read_blocks_the_send(self):
        out, reached = self.drive(pairs={})
        self.assertEqual(reached, [], out)
        self.assertIn("not in the provider's sender read", out)

    def test_a_sender_with_no_provider_account_id_blocks_the_send(self):
        """The shape every pre-0398 test of this script drove it with.

        `{"id": "bison-1"}` has no `provider_account_id`, so the old
        `check` turned it into the literal string "None", which is in no
        provider read and therefore passed.
        """
        out, reached = self.drive(
            senders=({"id": "bison-1", "daily_limit": 40},),
            pairs={SEAT: (1877, 8)})
        self.assertEqual(reached, [], out)
        self.assertIn("carry no provider_account_id", out)
        self.assertNotIn("'None'", out)

    def test_a_campaign_naming_no_email_sender_blocks_the_send(self):
        out, reached = self.drive(senders=(), pairs={SEAT: (1877, 8)})
        self.assertEqual(reached, [], out)
        self.assertIn("names no email sender", out)


# --------------------------------------------------------------------- C3


class HealthyStillPasses(_BounceStop):
    """C3. An instrument that blocks everything sees nothing."""

    def test_a_mailbox_with_sends_and_few_bounces_reaches_the_verb(self):
        """0.43% - the canary pool's own best mailbox, by its own figures."""
        out, reached = self.drive(pairs={SEAT: (1877, 8)})
        self.assertEqual(reached, [(BATCH_PROVIDER_ID, 2)],
                         "a healthy mailbox must not be blocked. If this "
                         "fails, every refusal in this module proves "
                         "nothing: %s" % out)
        self.assertIn("ready", out)
        self.assertNotIn(UNKNOWN_WORDS, out)

    def test_the_whole_pool_healthy_reaches_the_verb_once(self):
        senders = [{"provider_account_id": str(3430 + n)} for n in range(10)]
        pairs = {str(3430 + n): (1800 + n, 8 + n) for n in range(10)}
        out, reached = self.drive(senders=senders, pairs=pairs)
        self.assertEqual(reached, [(BATCH_PROVIDER_ID, 2)], out)


# --------------------------------------------------------------------- C4


class TheControlCanFail(_BounceStop):
    """C4. Invert the threshold and C2's send gets through."""

    def test_with_the_threshold_raised_the_same_send_is_not_blocked(self):
        with mock.patch.object(activate, "BOUNCE_HARD_STOP", 0.9):
            out, reached = self.drive(pairs={SEAT: (8947, 191)})
        self.assertEqual(reached, [(BATCH_PROVIDER_ID, 2)],
                         "with the stop moved to 90%% a 2.13%% mailbox must "
                         "pass. It did not, so C2 was not measuring the "
                         "threshold: %s" % out)
        self.assertNotIn(STOP_WORDS, out)

    def test_raising_the_threshold_does_NOT_let_an_unknown_through(self):
        """UNKNOWN is not a number, so no threshold can clear it.

        This is the half of the control that must NOT flip. If a knob can
        turn cannot-judge into a pass, the fix is cosmetic.
        """
        with mock.patch.object(activate, "BOUNCE_HARD_STOP", 1.0):
            out, reached = self.drive(pairs={SEAT: (0, 0)})
        self.assertEqual(reached, [], out)
        self.assertIn(UNKNOWN_WORDS, out)


# --------------------------------------------------------------------- C5


class NoCallerReadsTheOldContract(_BounceStop):
    """C5. The old falsy contract is gone, and gone loudly."""

    def test_check_returns_the_unknowns_as_their_own_list(self):
        row = {"bison_campaign_id": BATCH_PROVIDER_ID,
               "campaign_id": PREFIX + "alpha",
               "senders": {"email": [{"provider_account_id": SEAT}]}}
        with mock.patch.object(bison, "campaign", lambda pid: {}):
            failing = activate.check(row, self.read({SEAT: (8947, 191)}))
            unjudgeable = activate.check(row, self.read({SEAT: (0, 0)}))
            healthy = activate.check(row, self.read({SEAT: (1877, 8)}))

        self.assertEqual(len(failing), 4,
                         "check must return (reasons, unknowns, campaign, "
                         "named); a three-value caller is reading the old "
                         "contract")
        self.assertEqual((len(failing[0]), len(failing[1])), (1, 0))
        self.assertEqual((len(unjudgeable[0]), len(unjudgeable[1])), (0, 1))
        self.assertEqual((len(healthy[0]), len(healthy[1])), (0, 0))

    def test_an_old_shape_health_read_is_not_silently_accepted(self):
        """`(rate, sent, bounced)` was the old value. It must not pass.

        A tuple is truthy, so a `health.get(seat)` returning one would sail
        through a `blocks` test that did not exist on it. Failing closed
        here means loudly: the only producer of this dict is
        `mailbox_health`, and it was changed with `check`.
        """
        row = {"bison_campaign_id": BATCH_PROVIDER_ID,
               "campaign_id": PREFIX + "alpha",
               "senders": {"email": [{"provider_account_id": SEAT}]}}
        with mock.patch.object(bison, "campaign", lambda pid: {}):
            with self.assertRaises(AttributeError):
                activate.check(row, {SEAT: (0.0213, 8947, 191)})

    def test_the_verdict_is_not_a_boolean_with_a_third_value(self):
        verdicts = {activate.classify(1877, 8).verdict,
                    activate.classify(8947, 191).verdict,
                    activate.classify(0, 0).verdict}
        self.assertEqual(verdicts, {activate.HEALTHY, activate.FAILING,
                                    activate.UNKNOWN},
                         "three states, three distinct values at the call "
                         "site")
        self.assertEqual(
            [activate.classify(1877, 8).blocks,
             activate.classify(8947, 191).blocks,
             activate.classify(0, 0).blocks],
            [False, True, True],
            "only HEALTHY passes")


if __name__ == "__main__":
    unittest.main()
