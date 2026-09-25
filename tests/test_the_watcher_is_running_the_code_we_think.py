"""A watcher reported UP must be running the code we just read.

A merge is not a deploy: about fifteen loops import at start and never
reload, so the watcher module's mtime must be checked against the process
start time before believing a watcher is running what we just read.

This test verifies that:
1. The watcher check reports module mtime AND process start time, both.
2. A watcher reported UP with no such pair is a watcher nobody checked.
3. A stale module (mtime after process start) produces UNCONFIRMED.
4. A fresh module (mtime before process start) produces PASS.
"""
import datetime
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))


class WatcherRunningTheCodeWeThink(unittest.TestCase):
    """The watcher check must report mtime and process start, both."""

    def _make_check(self):
        import importlib
        import scripts.qa.check_readback as mod
        importlib.reload(mod)
        return mod

    def test_watcher_check_reports_mtime_and_process_start(self):
        """Every watcher judged must carry both module_mtime and
        process_start. A watcher reported UP with no such pair is a
        watcher nobody checked.
        """
        mod = self._make_check()

        # Create a temporary heartbeat file for campaign 491
        with tempfile.TemporaryDirectory() as tmpdir:
            hb_dir = os.path.join(tmpdir, "heartbeat")
            ev_dir = os.path.join(tmpdir, "watch-events")
            os.makedirs(hb_dir)
            os.makedirs(ev_dir)

            # Write a heartbeat
            hb_path = os.path.join(hb_dir, "bison-491.json")
            hb_data = {
                "source": "bison",
                "watcher": "bison:491",
                "at": "2026-09-25T06:05:00Z",
                "epoch": 1727244300,
                "pid": 12345,
                "campaign": 491,
            }
            with open(hb_path, "w") as f:
                json.dump(hb_data, f)

            # Write an event log
            ev_path = os.path.join(ev_dir, "bison-491.jsonl")
            with open(ev_path, "w") as f:
                f.write(json.dumps({
                    "at": "2026-09-25T06:00:00Z",
                    "source": "bison",
                    "watcher": "bison:491",
                    "kind": "WATCHING",
                    "line": "WATCHING 491 status=active leads=128",
                    "pid": 12345,
                    "campaign": 491,
                }) + "\n")

            with mock.patch.object(mod.watchsink, "heartbeat_dir",
                                   return_value=hb_dir), \
                 mock.patch.object(mod.watchsink, "events_dir",
                                   return_value=ev_dir):
                provider_reads = []
                files_read = []
                verdict, details = mod.check_watcher(
                    campaign_ids=[491],
                    provider_reads=provider_reads,
                    files_read=files_read,
                )

        per_campaign = details.get("per_campaign", {})
        self.assertIn(491, per_campaign)
        entry = per_campaign[491]

        # Both fields must be present
        self.assertIn("module_mtime", entry,
                       "module_mtime must be reported for every watcher")
        self.assertIn("process_start", entry,
                       "process_start must be reported for every watcher")
        # Neither should be None for a registered watcher
        self.assertIsNotNone(entry["module_mtime"],
                              "module_mtime must not be None for a "
                              "registered watcher")
        self.assertIsNotNone(entry["process_start"],
                              "process_start must not be None for a "
                              "registered watcher")

    def test_no_heartbeat_is_fail(self):
        """A campaign with no heartbeat registered is FAIL."""
        mod = self._make_check()

        with tempfile.TemporaryDirectory() as tmpdir:
            hb_dir = os.path.join(tmpdir, "heartbeat")
            os.makedirs(hb_dir)
            # No heartbeat files

            with mock.patch.object(mod.watchsink, "heartbeat_dir",
                                   return_value=hb_dir):
                provider_reads = []
                files_read = []
                verdict, details = mod.check_watcher(
                    campaign_ids=[491],
                    provider_reads=provider_reads,
                    files_read=files_read,
                )

        self.assertEqual(verdict, "FAIL")
        per_campaign = details.get("per_campaign", {})
        self.assertFalse(per_campaign[491].get("registered", True))

    def test_stale_module_is_unconfirmed(self):
        """Module mtime AFTER process start means the watcher may be running
        old code — UNCONFIRMED, not PASS.
        """
        mod = self._make_check()

        with tempfile.TemporaryDirectory() as tmpdir:
            hb_dir = os.path.join(tmpdir, "heartbeat")
            ev_dir = os.path.join(tmpdir, "watch-events")
            os.makedirs(hb_dir)
            os.makedirs(ev_dir)

            # Process started BEFORE the module was modified
            hb_path = os.path.join(hb_dir, "bison-491.json")
            hb_data = {
                "source": "bison",
                "watcher": "bison:491",
                "at": "2026-09-25T05:00:00Z",  # process started at 05:00
                "epoch": 1727240400,
                "pid": 12345,
                "campaign": 491,
            }
            with open(hb_path, "w") as f:
                json.dump(hb_data, f)

            # Create a fake watcher module with a LATER mtime
            fake_module = os.path.join(tmpdir, "bison_watch_loop.py")
            with open(fake_module, "w") as f:
                f.write("# fake\n")
            # Set mtime to 06:00 — after the process start
            os.utime(fake_module, (1727244000, 1727244000))

            with mock.patch.object(mod.watchsink, "heartbeat_dir",
                                   return_value=hb_dir), \
                 mock.patch.object(mod.watchsink, "events_dir",
                                   return_value=ev_dir), \
                 mock.patch.object(mod, "_file_mtime",
                                   return_value="2026-09-25T06:00:00Z"):
                provider_reads = []
                files_read = []
                verdict, details = mod.check_watcher(
                    campaign_ids=[491],
                    provider_reads=provider_reads,
                    files_read=files_read,
                )

        self.assertEqual(verdict, "UNCONFIRMED",
                         "module mtime after process start must be "
                         "UNCONFIRMED — the watcher may be running old code")
        per_campaign = details.get("per_campaign", {})
        self.assertTrue(per_campaign[491].get("code_stale"))

    def test_fresh_module_is_pass(self):
        """Module mtime BEFORE process start means the watcher is running
        current code — PASS.
        """
        mod = self._make_check()

        with tempfile.TemporaryDirectory() as tmpdir:
            hb_dir = os.path.join(tmpdir, "heartbeat")
            ev_dir = os.path.join(tmpdir, "watch-events")
            os.makedirs(hb_dir)
            os.makedirs(ev_dir)

            # Process started AFTER the module was modified
            hb_path = os.path.join(hb_dir, "bison-491.json")
            hb_data = {
                "source": "bison",
                "watcher": "bison:491",
                "at": "2026-09-25T07:00:00Z",  # process started at 07:00
                "epoch": 1727247600,
                "pid": 12345,
                "campaign": 491,
            }
            with open(hb_path, "w") as f:
                json.dump(hb_data, f)

            with mock.patch.object(mod.watchsink, "heartbeat_dir",
                                   return_value=hb_dir), \
                 mock.patch.object(mod.watchsink, "events_dir",
                                   return_value=ev_dir), \
                 mock.patch.object(mod, "_file_mtime",
                                   return_value="2026-09-25T06:00:00Z"):
                provider_reads = []
                files_read = []
                verdict, details = mod.check_watcher(
                    campaign_ids=[491],
                    provider_reads=provider_reads,
                    files_read=files_read,
                )

        self.assertEqual(verdict, "PASS",
                         "module mtime before process start must be PASS")
        per_campaign = details.get("per_campaign", {})
        self.assertFalse(per_campaign[491].get("code_stale"))


class WatcherReportsFourWitnesses(unittest.TestCase):
    """The watcher rule reports heartbeat, log last line, process start
    and module mtime — all four, per watcher.
    """

    def test_four_witnesses_present(self):
        import scripts.qa.check_readback as mod

        with tempfile.TemporaryDirectory() as tmpdir:
            hb_dir = os.path.join(tmpdir, "heartbeat")
            ev_dir = os.path.join(tmpdir, "watch-events")
            os.makedirs(hb_dir)
            os.makedirs(ev_dir)

            hb_path = os.path.join(hb_dir, "bison-491.json")
            with open(hb_path, "w") as f:
                json.dump({
                    "source": "bison",
                    "watcher": "bison:491",
                    "at": "2026-09-25T06:05:00Z",
                    "epoch": 1727244300,
                    "pid": 12345,
                    "campaign": 491,
                }, f)

            ev_path = os.path.join(ev_dir, "bison-491.jsonl")
            with open(ev_path, "w") as f:
                f.write(json.dumps({
                    "at": "2026-09-25T06:00:00Z",
                    "source": "bison",
                    "watcher": "bison:491",
                    "kind": "WATCHING",
                    "line": "WATCHING 491 status=active",
                    "pid": 12345,
                    "campaign": 491,
                }) + "\n")

            with mock.patch.object(mod.watchsink, "heartbeat_dir",
                                   return_value=hb_dir), \
                 mock.patch.object(mod.watchsink, "events_dir",
                                   return_value=ev_dir):
                provider_reads = []
                files_read = []
                verdict, details = mod.check_watcher(
                    campaign_ids=[491],
                    provider_reads=provider_reads,
                    files_read=files_read,
                )

        entry = details["per_campaign"][491]
        self.assertIsNotNone(entry.get("heartbeat"),
                              "heartbeat timestamp must be reported")
        self.assertIsNotNone(entry.get("log_last_line"),
                              "log last line must be reported")
        self.assertIsNotNone(entry.get("process_start"),
                              "process start must be reported")
        self.assertIsNotNone(entry.get("module_mtime"),
                              "module mtime must be reported")


if __name__ == "__main__":
    unittest.main()
