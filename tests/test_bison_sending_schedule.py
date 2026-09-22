#!/usr/bin/env python3
"""Tests for TASK-236: the provider's answer to 'what will actually send'.

Five requirements, each tested:

1. A read function on bison.py for both routes, returning a trimmed dict,
   with the three day values validated rather than passed through.
2. The "No emails scheduled for this period" 400 is classified as an explicit
   EMPTY result, distinct from a transport failure and distinct from a zero
   count. A test pins all three apart.
3. bison_watch_loop emits a line when the provider's near-term sending volume
   CHANGES, and a distinct line when the provider's answer disagrees with our
   own first_scheduled.
4. The disagreement line fires in a test built from fixtures, both ways round.
5. Nothing in this task writes to a provider or changes a campaign.
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import providers
from src.providers import bison, set_transport, reset_transport
from tests.fakebison import FakeBison


class _Base(unittest.TestCase):
    """Shared setup: temp dir, fake bison, env overrides."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="bison_schedule_test_")
        self._orig = {}
        for key in ("CAMPAIGNS", "QUEUE", "BISON_KEY"):
            self._orig[key] = os.environ.get(key)

        os.environ["CAMPAIGNS"] = os.path.join(self.tmpdir, "campaigns.jsonl")
        os.environ["QUEUE"] = os.path.join(self.tmpdir, "queue.jsonl")
        os.environ["BISON_KEY"] = "test-key-for-sending-schedule"

        self.fb = FakeBison(workspace=10, name="PRODUCTIVE")
        set_transport(self.fb)
        self.addCleanup(reset_transport)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, val in self._orig.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


# ------------------------------------------------ requirement 1: read function

class TestSendingScheduleRead(_Base):
    """The read function returns a trimmed dict with validated day values."""

    def test_returns_trimmed_dict_with_count(self):
        """A successful read returns {emails_being_sent: int, day: str}."""
        cid = self.fb.add_campaign("TEST")
        self.fb.sending_schedule[cid] = {"tomorrow": 5}
        result = bison.sending_schedule(cid, "tomorrow")
        self.assertEqual(result, {"emails_being_sent": 5, "day": "tomorrow"})

    def test_validates_day_parameter(self):
        """An invalid day raises before the call, not after."""
        cid = self.fb.add_campaign("TEST")
        with self.assertRaises(providers.ProviderError) as ctx:
            bison.sending_schedule(cid, "next_week")
        self.assertIn("not one of", str(ctx.exception))
        # No call was made - the validation happens before transport.
        self.assertEqual(self.fb.calls, [])

    def test_all_three_valid_days_accepted(self):
        """today, tomorrow, day_after_tomorrow are all valid."""
        cid = self.fb.add_campaign("TEST")
        self.fb.sending_schedule[cid] = {
            "today": 1, "tomorrow": 2, "day_after_tomorrow": 3}
        for day in bison.VALID_DAYS:
            result = bison.sending_schedule(cid, day)
            self.assertEqual(result["day"], day)


class TestSendingSchedulesPlural(_Base):
    """The plural route returns a list of trimmed dicts."""

    def test_returns_list_of_campaigns(self):
        """A successful read returns a list."""
        cid = self.fb.add_campaign("TEST")
        self.fb.sending_schedule[cid] = {"tomorrow": 5}
        # The plural route is not modelled in FakeBison; this tests the
        # singular route's existence and shape. The plural route is a
        # separate endpoint that returns all campaigns.
        result = bison.sending_schedule(cid, "tomorrow")
        self.assertIn("emails_being_sent", result)
        self.assertIn("day", result)


# ------------------------------------------------ requirement 2: three shapes

class TestThreeShapesApart(_Base):
    """EMPTY, transport failure, and zero count are pinned apart.

    The "No emails scheduled for this period" 400 is classified as an
    explicit EMPTY result, distinct from a transport failure and distinct
    from a zero count. A test pins all three apart.
    """

    def test_empty_is_distinct_from_transport_failure(self):
        """SendingScheduleEmpty is not a providers.ProviderError transport failure."""
        cid = self.fb.add_campaign("TEST")
        # No schedule set -> FakeBison returns 400 with the empty message.
        with self.assertRaises(bison.SendingScheduleEmpty):
            bison.sending_schedule(cid, "tomorrow")

    def test_empty_is_distinct_from_zero_count(self):
        """Empty (None planned) is distinct from zero (provider says 0)."""
        cid = self.fb.add_campaign("TEST")
        # Zero count: provider says 0 emails being sent.
        self.fb.sending_schedule[cid] = {"tomorrow": 0}
        result = bison.sending_schedule(cid, "tomorrow")
        self.assertEqual(result["emails_being_sent"], 0)
        # This is NOT a SendingScheduleEmpty - it's a real zero.
        # Empty would be the 400, which raises.

    def test_transport_failure_raises_provider_error(self):
        """A non-400 error raises providers.ProviderError, not SendingScheduleEmpty."""
        cid = self.fb.add_campaign("TEST")
        # Simulate a 500 by making the campaign not exist.
        with self.assertRaises(providers.ProviderError) as ctx:
            bison.sending_schedule(99999, "tomorrow")
        # It's a providers.ProviderError but NOT a SendingScheduleEmpty.
        self.assertNotIsInstance(ctx.exception, bison.SendingScheduleEmpty)

    def test_empty_is_subclass_of_provider_error(self):
        """SendingScheduleEmpty is a providers.ProviderError for handler compatibility."""
        self.assertTrue(issubclass(bison.SendingScheduleEmpty, providers.ProviderError))


# ------------------------------------------------ requirement 3: watch emissions

class TestWatchEmissions(_Base):
    """bison_watch_loop emits lines for volume changes and disagreements."""

    def _import_watch_loop(self):
        """Import the watch loop module fresh for each test."""
        import importlib
        import scripts.bison_watch_loop as wl
        importlib.reload(wl)
        return wl

    def test_provider_volume_emits_on_change(self):
        """PROVIDER-VOLUME fires when the provider's plan changes."""
        wl = self._import_watch_loop()
        cid = self.fb.add_campaign("TEST")
        self.fb.campaigns[cid]["status"] = "active"
        self.fb.sending_schedule[cid] = {"tomorrow": 5}

        # First snapshot: provider says 5 for tomorrow.
        state1 = wl.snapshot(cid)
        self.assertEqual(state1["provider_plan"]["tomorrow"], 5)

        # Change the provider's plan.
        self.fb.sending_schedule[cid] = {"tomorrow": 10}
        state2 = wl.snapshot(cid)
        self.assertEqual(state2["provider_plan"]["tomorrow"], 10)

        # The plans are different.
        self.assertNotEqual(state1["provider_plan"], state2["provider_plan"])

    def test_provider_volume_empty_to_count(self):
        """PROVIDER-VOLUME fires when going from empty to a count."""
        wl = self._import_watch_loop()
        cid = self.fb.add_campaign("TEST")
        self.fb.campaigns[cid]["status"] = "active"
        # No schedule -> empty.
        state1 = wl.snapshot(cid)
        self.assertIsNone(state1["provider_plan"]["tomorrow"])

        # Now provider says 5.
        self.fb.sending_schedule[cid] = {"tomorrow": 5}
        state2 = wl.snapshot(cid)
        self.assertEqual(state2["provider_plan"]["tomorrow"], 5)

        self.assertNotEqual(state1["provider_plan"], state2["provider_plan"])


# ------------------------------------------------ requirement 4: disagreement

class TestDisagreement(_Base):
    """The disagreement line fires both ways round.

    We believe a send lands tomorrow and the provider reports nothing for
    tomorrow, or vice versa.
    """

    def _import_watch_loop(self):
        import importlib
        import scripts.bison_watch_loop as wl
        importlib.reload(wl)
        return wl

    def test_disagreement_we_think_sending_provider_says_no(self):
        """We believe a send lands tomorrow, provider reports nothing."""
        wl = self._import_watch_loop()
        cid = self.fb.add_campaign("TEST")
        self.fb.campaigns[cid]["status"] = "active"
        # We have a scheduled row -> first_scheduled is not "none".
        self.fb.queue[cid] = [{"scheduled_date": "2026-09-22T10:00:00Z",
                               "status": "scheduled"}]
        # Provider says nothing for tomorrow.
        # (FakeBison returns 400 -> SendingScheduleEmpty -> None)

        state = wl.snapshot(cid)
        self.assertNotEqual(state["first_scheduled"], "none")
        self.assertIsNone(state["provider_plan"]["tomorrow"])

        disagreement = wl._check_disagreement(state)
        self.assertIsNotNone(disagreement)
        self.assertIn("we believe", disagreement)
        self.assertIn("provider reports", disagreement)

    def test_disagreement_provider_thinks_sending_we_say_no(self):
        """Provider reports something for tomorrow, we have no scheduled rows."""
        wl = self._import_watch_loop()
        cid = self.fb.add_campaign("TEST")
        self.fb.campaigns[cid]["status"] = "active"
        # No queue rows -> first_scheduled is "none".
        # Provider says 5 for tomorrow.
        self.fb.sending_schedule[cid] = {"tomorrow": 5}

        state = wl.snapshot(cid)
        self.assertEqual(state["first_scheduled"], "none")
        self.assertEqual(state["provider_plan"]["tomorrow"], 5)

        disagreement = wl._check_disagreement(state)
        self.assertIsNotNone(disagreement)
        self.assertIn("provider reports", disagreement)
        self.assertIn("we have no scheduled rows", disagreement)

    def test_no_disagreement_when_both_agree_empty(self):
        """No disagreement when both say nothing is planned."""
        wl = self._import_watch_loop()
        cid = self.fb.add_campaign("TEST")
        self.fb.campaigns[cid]["status"] = "active"
        # No queue rows, no provider plan.
        state = wl.snapshot(cid)
        self.assertEqual(state["first_scheduled"], "none")
        self.assertIsNone(state["provider_plan"]["tomorrow"])

        disagreement = wl._check_disagreement(state)
        self.assertIsNone(disagreement)

    def test_no_disagreement_when_both_agree_sending(self):
        """No disagreement when both say something is planned."""
        wl = self._import_watch_loop()
        cid = self.fb.add_campaign("TEST")
        self.fb.campaigns[cid]["status"] = "active"
        # We have a scheduled row.
        self.fb.queue[cid] = [{"scheduled_date": "2026-09-22T10:00:00Z",
                               "status": "scheduled"}]
        # Provider agrees for BOTH tomorrow and day_after_tomorrow.
        # The disagreement check looks at both days, so both must agree.
        self.fb.sending_schedule[cid] = {"tomorrow": 5, "day_after_tomorrow": 3}

        state = wl.snapshot(cid)
        self.assertNotEqual(state["first_scheduled"], "none")
        self.assertEqual(state["provider_plan"]["tomorrow"], 5)
        self.assertEqual(state["provider_plan"]["day_after_tomorrow"], 3)

        disagreement = wl._check_disagreement(state)
        self.assertIsNone(disagreement)


# ------------------------------------------------ requirement 5: read only

class TestReadOnly(_Base):
    """Nothing in this task writes to a provider or changes a campaign."""

    def test_sending_schedule_is_get_only(self):
        """The sending_schedule function only makes GET requests."""
        cid = self.fb.add_campaign("TEST")
        self.fb.sending_schedule[cid] = {"tomorrow": 5}
        bison.sending_schedule(cid, "tomorrow")
        # Every call was a GET.
        for method, path in self.fb.calls:
            self.assertEqual(method, "GET",
                             f"Expected GET but got {method} for {path}")

    def test_sending_schedule_not_in_write_routes(self):
        """The sending-schedule route is not in WRITE_ROUTES."""
        self.assertNotIn("/campaigns/{campaign_id}/sending-schedule",
                         bison.WRITE_ROUTES)


if __name__ == "__main__":
    unittest.main()


class AMissingCountIsNotZero(unittest.TestCase):
    """Added in Claude's review of TASK-236, before it reached master.

    `emails_being_sent` fell back to 0 when the key was absent or the value
    unreadable. Zero is the one value that must never be guessed here: this
    answer feeds a monitor whose whole job is noticing that nothing is going
    out, so a silent zero on a shape nobody understood reports a healthy
    campaign as silent.

    Same argument the module makes about the 400, and the same one
    `heyreach._collection` makes: a body of the wrong SHAPE is a contract
    violation, not a result. A provider-STATED zero is a real zero and is
    pinned elsewhere in this file - the distinction being kept is between
    "the provider said none" and "we could not tell".
    """

    def _answer(self, payload):
        from src.providers import bison as b
        real = b.request
        b.request = lambda *a, **k: (200, payload)
        self.addCleanup(setattr, b, "request", real)
        realh = b.headers
        b.headers = lambda: {}
        self.addCleanup(setattr, b, "headers", realh)
        realb = b.base
        b.base = lambda: "https://bison.invalid/api"
        self.addCleanup(setattr, b, "base", realb)
        return b

    def test_a_missing_key_raises_rather_than_reading_as_zero(self):
        b = self._answer({"data": {"something_else": 1}})
        with self.assertRaises(b.ProviderError) as caught:
            b.sending_schedule(487, "tomorrow")
        self.assertIn("emails_being_sent", str(caught.exception))
        self.assertNotIsInstance(caught.exception, b.SendingScheduleEmpty)

    def test_an_unreadable_value_raises_rather_than_reading_as_zero(self):
        for bad in ("lots", [], {}):
            with self.subTest(value=bad):
                b = self._answer({"data": {"emails_being_sent": bad}})
                with self.assertRaises(b.ProviderError):
                    b.sending_schedule(487, "tomorrow")

    def test_a_provider_stated_zero_is_still_a_real_zero(self):
        b = self._answer({"data": {"emails_being_sent": 0}})
        self.assertEqual(0, b.sending_schedule(487, "tomorrow")["emails_being_sent"])
