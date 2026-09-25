"""Absent within the window is UNCONFIRMED, not FAIL.

ISSUE-043: `bison.attach_leads` reads membership back 6 times over ~15s and
raises when the lead is absent. The campaign-membership index took ~30
seconds on 2026-09-24. A post-push readback that calls "absent within the
window" a PASS is wrong; one that calls it a FAIL makes a caller re-push a
good push.

This test constructs the delayed-index scenario offline against a fake
clock and verifies the retry ladder produces the correct sequence:

    t+0   initial read: lead absent -> UNCONFIRMED
    t+60  first retry:  lead absent -> UNCONFIRMED
    t+180 second retry: lead present -> PASS
    (t+600 not reached because PASS was achieved)

And separately:

    t+600 still absent -> FAIL with the lead id named.

The test patches the provider read to simulate the index catching up at
different times, and patches the clock to control when each retry fires.
"""
import contextlib
import datetime
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def _patch_all_providers(mod, campaign_lead_ids_fn=None):
    """Mock every provider call that `run()` makes so the test does not
    hit the network. Returns a context manager stacking all patches.

    `campaign_lead_ids_fn` overrides the default for rule 1; everything
    else returns safe empty defaults.
    """
    lead_ids = campaign_lead_ids_fn or (lambda cid: [])
    return contextlib.ExitStack() if False else _MultiPatch(
        mod, lead_ids)


class _MultiPatch:
    """Stack all provider mocks for a clean `run()` invocation."""

    def __init__(self, mod, lead_ids_fn):
        self._mod = mod
        self._lead_ids_fn = lead_ids_fn
        self._stack = None

    def __enter__(self):
        self._stack = contextlib.ExitStack()
        self._stack.enter_context(
            mock.patch.object(self._mod.bison_provider, "campaign_lead_ids",
                              side_effect=self._lead_ids_fn))
        self._stack.enter_context(
            mock.patch.object(self._mod.bison_provider, "scheduled_emails",
                              return_value=[]))
        self._stack.enter_context(
            mock.patch.object(self._mod.bison_provider, "schedule",
                              return_value={}))
        self._stack.enter_context(
            mock.patch.object(self._mod.watchsink, "heartbeats",
                              return_value=[]))
        self._stack.enter_context(
            mock.patch.object(self._mod.heyreach_provider, "campaign_stats",
                              side_effect=Exception("no heyreach")))
        self._stack.__enter__()
        return self

    def __exit__(self, *exc):
        return self._stack.__exit__(*exc)


class AbsentWithinWindowIsUnconfirmed(unittest.TestCase):
    """The retry ladder must produce UNCONFIRMED then PASS, not FAIL."""

    def _make_check(self):
        """Import the check module fresh."""
        import importlib
        import scripts.qa.check_readback as mod
        importlib.reload(mod)
        return mod

    def test_absent_at_initial_read_is_unconfirmed_not_fail(self):
        """A lead absent on the first read is UNCONFIRMED, never FAIL."""
        mod = self._make_check()

        with mock.patch.object(mod.bison_provider, "campaign_lead_ids",
                               return_value=[]):
            provider_reads = []
            verdict, details = mod.check_leads_attached(
                campaign_ids=[491],
                pushed_lead_ids=[205079],
                provider_reads=provider_reads,
                attempt_label="initial",
            )

        self.assertEqual(verdict, mod.VERDICT_UNCONFIRMED,
                         "absent within the window must be UNCONFIRMED, "
                         "not FAIL — ISSUE-043")
        self.assertIn(205079, details["pushed_and_absent"])
        self.assertEqual(details["attempt"], "initial")

    def test_absent_at_t60_then_present_at_t180_produces_unconfirmed_then_pass(
            self):
        """The constructed delayed-index sequence.

        This is the acceptance bar from the task: 'A lead absent at t+60
        and present at t+180 produces UNCONFIRMED then PASS, and the result
        shows both.'
        """
        mod = self._make_check()

        push_time = "2026-09-25T06:00:00Z"
        t_180 = datetime.datetime(2026, 9, 25, 6, 3, 0,
                                  tzinfo=datetime.timezone.utc)

        # The index catches up between t+60 and t+180
        call_count = [0]

        def fake_campaign_lead_ids(cid):
            call_count[0] += 1
            if call_count[0] <= 2:
                return []
            return [205079]

        with _MultiPatch(mod, fake_campaign_lead_ids):
            result = mod.run(
                phase="post_push",
                batch="test-batch",
                campaigns=[491],
                pushed_lead_ids=[205079],
                workspaces=None,
                push_time=push_time,
                now_fn=lambda: t_180,
            )

        # The retry ladder must show both attempts
        attempts = result.get("retry_attempts", [])
        self.assertGreaterEqual(len(attempts), 2,
                                "the retry ladder must record at least the "
                                "initial and one retry attempt")

        # Find the initial attempt
        initial = [a for a in attempts if a["attempt"] == "initial"]
        self.assertEqual(len(initial), 1)
        self.assertEqual(initial[0]["verdict"], "UNCONFIRMED",
                         "initial read with absent lead must be UNCONFIRMED")

        # The lead-attachment rule must resolve to PASS
        lead_rule = "exactly_the_pushed_leads_are_attached"
        # Check the last retry attempt shows PASS
        last_attempt = attempts[-1]
        self.assertEqual(last_attempt["verdict"], "PASS",
                         "lead present at t+180 after being absent at t+60 "
                         "must resolve to PASS on the retry")

    def test_absent_at_t600_becomes_fail_with_lead_id(self):
        """Still absent at t+600 becomes FAIL with the lead id named."""
        mod = self._make_check()

        push_time = "2026-09-25T06:00:00Z"
        t_600_plus = datetime.datetime(2026, 9, 25, 6, 10, 1,
                                       tzinfo=datetime.timezone.utc)

        with _MultiPatch(mod, lambda cid: []):
            result = mod.run(
                phase="post_push",
                batch="test-batch",
                campaigns=[491],
                pushed_lead_ids=[205079],
                workspaces=None,
                push_time=push_time,
                now_fn=lambda: t_600_plus,
            )

        # After all retries exhausted, the verdict must be FAIL
        self.assertEqual(result["verdict"], "FAIL",
                         "still absent at t+600 must be FAIL, not UNCONFIRMED")

        # The lead id must be named in the offenders
        offenders = result.get("offenders", {})
        lead_rule = "exactly_the_pushed_leads_are_attached"
        self.assertIn(205079, offenders.get(lead_rule, []),
                      "the absent lead id must be named in offenders")

    def test_all_four_retry_attempts_are_recorded(self):
        """The result records all retry attempts with timestamps and counts.
        The retry ladder is the deliverable as much as the verdict.
        """
        mod = self._make_check()

        push_time = "2026-09-25T06:00:00Z"
        t_600_plus = datetime.datetime(2026, 9, 25, 6, 10, 1,
                                       tzinfo=datetime.timezone.utc)

        with _MultiPatch(mod, lambda cid: []):
            result = mod.run(
                phase="post_push",
                batch="test-batch",
                campaigns=[491],
                pushed_lead_ids=[205079],
                workspaces=None,
                push_time=push_time,
                now_fn=lambda: t_600_plus,
            )

        attempts = result.get("retry_attempts", [])
        # initial + 3 retries = 4 attempts
        self.assertEqual(len(attempts), 4,
                         "the retry ladder must record initial + 3 retries")
        labels = [a["attempt"] for a in attempts]
        self.assertEqual(labels[0], "initial")
        self.assertIn("retry_t+60s", labels)
        self.assertIn("retry_t+180s", labels)
        self.assertIn("retry_t+600s", labels)

    def test_set_equality_both_directions(self):
        """Counts alone are not set equality. The diff must go BOTH ways:
        pushed-and-absent AND present-and-not-pushed.
        """
        mod = self._make_check()

        with mock.patch.object(mod.bison_provider, "campaign_lead_ids",
                               return_value=[999]):
            provider_reads = []
            verdict, details = mod.check_leads_attached(
                campaign_ids=[491],
                pushed_lead_ids=[205079],
                provider_reads=provider_reads,
            )

        self.assertEqual(verdict, mod.VERDICT_UNCONFIRMED)
        self.assertIn(205079, details["pushed_and_absent"],
                       "pushed lead absent from provider")
        self.assertIn(999, details["present_and_not_pushed"],
                       "present lead was not pushed — someone else's leads "
                       "in our campaign")

    def test_no_push_time_single_attempt(self):
        """Without a push time, there is no retry ladder — single attempt."""
        mod = self._make_check()

        with _MultiPatch(mod, lambda cid: [205079]):
            result = mod.run(
                phase="post_push",
                batch="test-batch",
                campaigns=[491],
                pushed_lead_ids=[205079],
                workspaces=None,
                push_time=None,
            )

        attempts = result.get("retry_attempts", [])
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["attempt"], "single")
        # The lead-attachment rule should be PASS
        lead_verdict = [a["verdict"] for a in attempts
                        if a["attempt"] == "single"]
        self.assertEqual(lead_verdict[0], "PASS")

    def test_wrong_phase_is_error(self):
        """This check only runs in post_push phase."""
        mod = self._make_check()

        result = mod.run(
            phase="pre_push",
            batch="test",
            campaigns=[491],
            pushed_lead_ids=[],
            workspaces=None,
        )
        self.assertEqual(result["verdict"], "ERROR")

    def test_no_campaigns_is_error(self):
        """No campaigns supplied is an ERROR, not a PASS."""
        mod = self._make_check()

        result = mod.run(
            phase="post_push",
            batch="test",
            campaigns=[],
            pushed_lead_ids=[205079],
            workspaces=None,
        )
        self.assertEqual(result["verdict"], "ERROR")


class RetryScheduleComputation(unittest.TestCase):
    """The retry ladder timestamps are computed correctly from the push."""

    def test_offsets_from_push_time(self):
        import scripts.qa.check_readback as mod
        schedule = mod._retry_schedule("2026-09-25T06:00:00Z")
        self.assertEqual(len(schedule), 3)
        self.assertEqual(schedule[0].minute, 1)   # t+60
        self.assertEqual(schedule[1].minute, 3)   # t+180
        self.assertEqual(schedule[2].minute, 10)  # t+600

    def test_all_retries_exhausted_after_t600(self):
        import scripts.qa.check_readback as mod
        t_after = datetime.datetime(2026, 9, 25, 6, 10, 1,
                                    tzinfo=datetime.timezone.utc)
        self.assertTrue(mod._all_retries_exhausted(
            "2026-09-25T06:00:00Z", now=t_after))

    def test_retries_not_exhausted_before_t600(self):
        import scripts.qa.check_readback as mod
        t_before = datetime.datetime(2026, 9, 25, 6, 5, 0,
                                     tzinfo=datetime.timezone.utc)
        self.assertFalse(mod._all_retries_exhausted(
            "2026-09-25T06:00:00Z", now=t_before))


if __name__ == "__main__":
    unittest.main()
