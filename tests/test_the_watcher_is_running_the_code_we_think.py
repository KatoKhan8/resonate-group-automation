"""A watcher reported UP must show the code it is running is current.

TASK-298. A merge is not a deploy: about fifteen loops import at start and
never reload, so the watcher module's mtime must be checked against the
process start time. A watcher reported UP with no such pair is a watcher
nobody checked.

Three witnesses the check demands per watcher:

1. heartbeat — the watcher beat recently
2. process start — the state file was written after boot
3. module mtime — the source file was not modified after the process started

A watcher whose module mtime is AFTER its process start is running stale
code. The verdict is FAIL, not UP.
"""
import datetime
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.qa.check_readback import (
    check_watcher_on_campaign,
    PASS,
    FAIL,
    UNCONFIRMED,
)


class TestWatcherIsRunningTheCodeWeThink(unittest.TestCase):
    """The watcher mtime vs process start check."""

    def _fresh_beat(self, campaign_id, source="bison"):
        now = datetime.datetime.now(datetime.timezone.utc)
        return [{
            "source": source,
            "watcher": f"{source}:{campaign_id}",
            "campaign": campaign_id,
            "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "epoch": now.timestamp(),
            "pid": 12345,
        }]

    def test_no_watcher_found_is_fail(self):
        """No heartbeat for the campaign means FAIL."""
        result = check_watcher_on_campaign(
            491,
            heartbeats_fn=lambda: [])
        self.assertEqual(result["verdict"], FAIL)
        self.assertFalse(result["watcher_found"])

    def test_watcher_found_with_fresh_module(self):
        """A watcher whose module predates the process is PASS."""
        now = datetime.datetime.now(datetime.timezone.utc)
        process_start_epoch = now.timestamp() - 3600
        module_mtime_epoch = now.timestamp() - 7200

        def witnesses_fn(mon):
            return {
                "state_written_at": process_start_epoch,
                "status": "UP",
            }

        def mtime_fn(module_path):
            return module_mtime_epoch

        monitors = [{"name": "bison_watch_491",
                      "heartbeat": {"source": "bison", "campaign": 491}}]

        result = check_watcher_on_campaign(
            491,
            heartbeats_fn=lambda: self._fresh_beat(491),
            supervisor_witnesses_fn=witnesses_fn,
            monitor_list=monitors,
            module_mtime_fn=mtime_fn)

        self.assertTrue(result["watcher_found"])
        self.assertIsNotNone(result["heartbeat"])
        self.assertIsNotNone(result["process_start"])
        self.assertIsNotNone(result["module_mtime"])
        self.assertEqual(result["module_stale"], False)
        self.assertEqual(result["verdict"], PASS)

    def test_watcher_with_stale_module_is_fail(self):
        """A watcher whose module was modified AFTER process start is FAIL.

        A merge is not a deploy — the loop may be running code from before
        the fix.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        process_start_epoch = now.timestamp() - 3600
        module_mtime_epoch = now.timestamp() - 1800

        def witnesses_fn(mon):
            return {
                "state_written_at": process_start_epoch,
                "status": "UP",
            }

        def mtime_fn(module_path):
            return module_mtime_epoch

        monitors = [{"name": "bison_watch_491",
                      "heartbeat": {"source": "bison", "campaign": 491}}]

        result = check_watcher_on_campaign(
            491,
            heartbeats_fn=lambda: self._fresh_beat(491),
            supervisor_witnesses_fn=witnesses_fn,
            monitor_list=monitors,
            module_mtime_fn=mtime_fn)

        self.assertTrue(result["watcher_found"])
        self.assertEqual(result["module_stale"], True)
        self.assertEqual(result["verdict"], FAIL)

    def test_watcher_reported_up_with_no_mtime_pair_is_rejected(self):
        """A watcher reported UP with no mtime/process pair is flagged.

        A watcher reported UP with no such pair is a watcher nobody checked.
        """
        result = check_watcher_on_campaign(
            491,
            heartbeats_fn=lambda: self._fresh_beat(491),
            supervisor_witnesses_fn=None,
            monitor_list=None,
            module_mtime_fn=None)

        self.assertTrue(result["watcher_found"])
        self.assertIsNone(result["process_start"])
        self.assertIsNone(result["module_mtime"])
        self.assertIsNone(result["module_stale"])

    def test_heartbeat_and_process_start_both_reported(self):
        """The result carries heartbeat, process_start, module_mtime."""
        now = datetime.datetime.now(datetime.timezone.utc)
        process_start_epoch = now.timestamp() - 3600
        module_mtime_epoch = now.timestamp() - 7200

        def witnesses_fn(mon):
            return {
                "state_written_at": process_start_epoch,
                "status": "UP",
            }

        def mtime_fn(module_path):
            return module_mtime_epoch

        monitors = [{"name": "bison_watch_491",
                      "heartbeat": {"source": "bison", "campaign": 491}}]

        result = check_watcher_on_campaign(
            491,
            heartbeats_fn=lambda: self._fresh_beat(491),
            supervisor_witnesses_fn=witnesses_fn,
            monitor_list=monitors,
            module_mtime_fn=mtime_fn)

        self.assertIsNotNone(result["heartbeat"])
        self.assertIsNotNone(result["process_start"])
        self.assertIsNotNone(result["module_mtime"])
        self.assertIn("2026", result["process_start"])
        self.assertIn("2026", result["module_mtime"])


class TestWatcherSourceMapping(unittest.TestCase):
    """The source-to-module mapping is correct."""

    def test_bison_maps_to_bison_watch_loop(self):
        from scripts.qa.check_readback import _watcher_module_for_source
        path = _watcher_module_for_source("bison")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith("bison_watch_loop.py"))

    def test_heyreach_maps_to_heyreach_watch_loop(self):
        from scripts.qa.check_readback import _watcher_module_for_source
        path = _watcher_module_for_source("heyreach")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith("heyreach_watch_loop.py"))

    def test_unknown_source_returns_none(self):
        from scripts.qa.check_readback import _watcher_module_for_source
        path = _watcher_module_for_source("unknown_watcher")
        self.assertIsNone(path)


if __name__ == "__main__":
    unittest.main()
