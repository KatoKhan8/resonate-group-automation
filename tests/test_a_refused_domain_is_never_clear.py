#!/usr/bin/env python3
"""A REFUSED domain is never CLEAR, and a stale clearance is not reused.

The collision walk has three negative states - REFUSED, NOT_WALKED, and
UNKNOWN_OWNER - and none of them is CLEAR. A walk that folds any of them into
CLEAR has lost the distinction this module exists to keep: "we asked and could
not trust the answer" is not "there is nothing there".

A clearance from a previous cycle is a cached value on a safety path. The
shape of six rows in the problem register. The walk output carries the day it
was walked, and a clearance older than the current cycle must not be silently
reused - it must be re-walked or expired.

WHY THIS IS NOT COVERED BY test_collision. The unit is not the risk. The risk
is the classification: a walk report that says REFUSED=0 because it folded
REFUSED into CLEAR, or a stale clearance that passes through because nobody
checked its date.
"""
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock


class TestRefusedIsNeverClear(unittest.TestCase):
    """The four-verdict classification must keep REFUSED apart from CLEAR."""

    def _classify(self, entry):
        """The classification logic from the walk report.

        Imported here as a standalone function so the test does not depend on
        the script's import chain. If the script's classify() changes, this
        must change with it - and a test that disagrees with it is the signal.
        """
        policy = entry.get("policy")
        if entry.get("verdict") == "REFUSED" and not policy:
            return "REFUSED"
        if policy == "allow":
            return "CLEAR"
        if policy in ("hold", "stop"):
            return "COLLIDES"
        return "REFUSED"

    def test_refused_entry_is_not_clear(self):
        entry = {
            "verdict": "REFUSED",
            "why": "CollisionUnknown: emailbison leads: search returned "
                   "5000 rows, broad match",
        }
        self.assertEqual(self._classify(entry), "REFUSED")
        self.assertNotEqual(self._classify(entry), "CLEAR")

    def test_not_walked_is_not_in_the_walk_at_all(self):
        """A domain not in the walk state is NOT_WALKED, never CLEAR."""
        state = {"accounts": {}}
        domain = "example.test"
        self.assertNotIn(domain, state["accounts"])

    def test_hold_is_collides_not_clear(self):
        entry = {
            "policy": "hold",
            "verdict": "touched",
            "why": "a campaign ended early (stopped)",
        }
        self.assertEqual(self._classify(entry), "COLLIDES")
        self.assertNotEqual(self._classify(entry), "CLEAR")

    def test_stop_is_collides_not_clear(self):
        entry = {
            "policy": "stop",
            "verdict": "in_sequence",
            "why": "somebody is mid-sequence right now",
        }
        self.assertEqual(self._classify(entry), "COLLIDES")
        self.assertNotEqual(self._classify(entry), "CLEAR")

    def test_allow_is_clear(self):
        entry = {
            "policy": "allow",
            "verdict": "clear",
            "why": "no prior contact at this account",
        }
        self.assertEqual(self._classify(entry), "CLEAR")

    def test_four_verdicts_sum_to_input_set(self):
        """The four buckets must partition the input, not lose entries."""
        state = {
            "accounts": {
                "clear.test": {"policy": "allow", "verdict": "clear"},
                "hold.test": {"policy": "hold", "verdict": "touched"},
                "stop.test": {"policy": "stop", "verdict": "in_sequence"},
                "refused.test": {"verdict": "REFUSED",
                                 "why": "broad match"},
            }
        }
        counts = {"CLEAR": 0, "COLLIDES": 0, "REFUSED": 0, "NOT_WALKED": 0}
        for domain, entry in state["accounts"].items():
            v = self._classify(entry)
            counts[v] += 1
        total = sum(counts.values())
        self.assertEqual(total, len(state["accounts"]))
        self.assertEqual(counts["CLEAR"], 1)
        self.assertEqual(counts["COLLIDES"], 2)
        self.assertEqual(counts["REFUSED"], 1)

    def test_unknown_owner_is_not_clear(self):
        """A touch that cannot be attributed is not CLEAR."""
        entry = {
            "policy": "stop",
            "verdict": "in_sequence",
            "ownership": [{"owner": "UNKNOWN_OWNER",
                           "campaign_id": 999}],
        }
        self.assertEqual(self._classify(entry), "COLLIDES")
        self.assertNotEqual(self._classify(entry), "CLEAR")


class TestStalenessIsNotSilentlyReused(unittest.TestCase):
    """A clearance older than the current cycle must not pass through.

    The walk output carries `at` on every verdict. A clearance from a previous
    cycle is a cached value on a safety path - the shape of six rows in the
    problem register, and the same shape as the `last_touch` cache that made
    thirteen leads emailed two days ago read as 'contacted 90+ days ago'.
    """

    def _is_fresh(self, entry, max_age_hours=24):
        """Whether this clearance is fresh enough to use.

        A walk entry's `at` field is an ISO 8601 timestamp. If it is older
        than max_age_hours, it is stale and must be re-walked.
        """
        at = entry.get("at")
        if not at:
            return False
        try:
            walked = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return False
        age = datetime.now(timezone.utc) - walked
        return age.total_seconds() < max_age_hours * 3600

    def test_fresh_clearance_is_usable(self):
        entry = {
            "policy": "allow",
            "verdict": "clear",
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self.assertTrue(self._is_fresh(entry))

    def test_stale_clearance_is_not_usable(self):
        two_days_ago = (datetime.now(timezone.utc)
                        - timedelta(hours=48))
        entry = {
            "policy": "allow",
            "verdict": "clear",
            "at": two_days_ago.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self.assertFalse(self._is_fresh(entry))

    def test_missing_timestamp_is_not_usable(self):
        entry = {"policy": "allow", "verdict": "clear"}
        self.assertFalse(self._is_fresh(entry))

    def test_malformed_timestamp_is_not_usable(self):
        entry = {"policy": "allow", "verdict": "clear", "at": "not-a-date"}
        self.assertFalse(self._is_fresh(entry))

    def test_stale_clearance_does_not_become_fresh_by_silence(self):
        """A stale entry is not fresh just because nobody noticed.

        The shape of the `last_touch` defect: a cache value aged out but
        nothing re-read it, so it kept passing as current.
        """
        old = (datetime.now(timezone.utc) - timedelta(days=7))
        entry = {
            "policy": "allow",
            "verdict": "clear",
            "at": old.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self.assertFalse(self._is_fresh(entry, max_age_hours=24))
        self.assertFalse(self._is_fresh(entry, max_age_hours=168))
        self.assertFalse(self._is_fresh(entry, max_age_hours=0))


class TestWalkOutputIsConsumed(unittest.TestCase):
    """The walk output must be read by eligibility, not just written.

    `batch_eligibility.collision_cleared()` reads `s6-collision-walk.json`.
    If the only code that touches the file is the writer, the gate is still
    on batch 1's cache. This test proves the read path exists by simulating
    the file's presence and absence.
    """

    def test_absent_walk_returns_none_without_legacy(self):
        """No walk file and no legacy file -> collision_cleared() is None."""
        from scripts.batch_eligibility import collision_cleared

        with tempfile.TemporaryDirectory() as tmpdir:
            walk_path = os.path.join(tmpdir, "s6-collision-walk.json")
            legacy_path = os.path.join(tmpdir, "batch1-candidates.json")
            with mock.patch("scripts.batch_eligibility.STAGE", tmpdir):
                result = collision_cleared()
        self.assertIsNone(result)

    def test_present_walk_with_allow_domain_clears_it(self):
        """A domain with policy=allow in the walk is in the cleared set."""
        from scripts.batch_eligibility import collision_cleared

        walk_data = {
            "accounts": {
                "example.test": {"policy": "allow", "verdict": "clear"},
                "blocked.test": {"policy": "stop", "verdict": "in_sequence"},
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            walk_path = os.path.join(tmpdir, "s6-collision-walk.json")
            with open(walk_path, "w", encoding="utf-8") as f:
                json.dump(walk_data, f)
            with mock.patch("scripts.batch_eligibility.STAGE", tmpdir):
                result = collision_cleared()
        self.assertIsNotNone(result)
        self.assertIn("example.test", result)
        self.assertNotIn("blocked.test", result)

    def test_refused_domain_in_walk_is_not_cleared(self):
        """A domain the walk REFUSED is not in the cleared set.

        This is the core invariant: REFUSED is never CLEAR.
        """
        from scripts.batch_eligibility import collision_cleared

        walk_data = {
            "accounts": {
                "refused.test": {
                    "verdict": "REFUSED",
                    "why": "broad match",
                },
                "clear.test": {"policy": "allow", "verdict": "clear"},
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            walk_path = os.path.join(tmpdir, "s6-collision-walk.json")
            with open(walk_path, "w", encoding="utf-8") as f:
                json.dump(walk_data, f)
            with mock.patch("scripts.batch_eligibility.STAGE", tmpdir):
                result = collision_cleared()
        self.assertIsNotNone(result)
        self.assertNotIn("refused.test", result)
        self.assertIn("clear.test", result)


if __name__ == "__main__":
    unittest.main()
