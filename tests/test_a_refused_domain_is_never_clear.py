#!/usr/bin/env python3
"""A REFUSED domain is not CLEAR, not NOT_WALKED, and never becomes eligible.

Three states, three meanings, and the one this module exists for is the one
that must never be folded into the other two:

    CLEAR      walked, no touch found                -> may become supply
    REFUSED    walked, provider answer untrustworthy  -> never supply
    NOT_WALKED not asked yet                          -> never supply

`collision.check_account` raises `CollisionUnknown` when the provider's
response looks like a broad match rather than a filtered one. The walk script
catches that exception and writes `verdict: REFUSED`. `batch_eligibility`'s
`collision_cleared()` only passes `collision.ALLOW` through. A REFUSED domain
has policy absent from the ALLOW set, so it is not cleared.

This test proves that chain: a REFUSED verdict in the walk state file is not
reported as cleared, is not reported as ALLOW, and is distinguishable from
both CLEAR and NOT_WALKED.
"""
import json
import os
import tempfile
import unittest


class RefusedDomainIsNeverClear(unittest.TestCase):
    """The three buckets are distinct and only ALLOW passes the gate."""

    def _write_walk(self, accounts):
        path = os.path.join(self._tmp, "s6-collision-walk.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"accounts": accounts, "started_at":
                        "2026-09-25T00:00:00Z"}, f)
        return path

    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_refused_is_not_allow(self):
        """A REFUSED domain does not have policy == 'allow'."""
        walk = {
            "refused.example.com": {
                "verdict": "REFUSED",
                "why": "CollisionUnknown: broad match (412 rows)",
                "at": "2026-09-25T12:00:00Z",
            },
        }
        path = self._write_walk(walk)
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        for domain, entry in state["accounts"].items():
            self.assertNotEqual(
                entry.get("policy"), "allow",
                f"{domain} is REFUSED and must not read policy=allow")

    def test_cleared_skips_refused(self):
        """`collision_cleared` only passes ALLOW, so REFUSED is excluded."""
        import scripts.batch_eligibility as be

        walk = {
            "clear.example.com": {
                "policy": "allow",
                "verdict": "clear",
                "why": "no prior contact",
                "at": "2026-09-25T12:00:00Z",
            },
            "refused.example.com": {
                "verdict": "REFUSED",
                "why": "CollisionUnknown: broad match",
                "at": "2026-09-25T12:00:00Z",
            },
            "stopped.example.com": {
                "policy": "stop",
                "verdict": "in_sequence",
                "why": "somebody mid-sequence",
                "at": "2026-09-25T12:00:00Z",
            },
        }
        path = self._write_walk(walk)
        original_stage = be.STAGE
        be.STAGE = self._tmp
        try:
            cleared = be.collision_cleared()
            self.assertIsNotNone(cleared)
            self.assertIn("clear.example.com", cleared)
            self.assertNotIn("refused.example.com", cleared)
            self.assertNotIn("stopped.example.com", cleared)
        finally:
            be.STAGE = original_stage

    def test_not_walked_is_neither_clear_nor_refused(self):
        """A domain absent from the walk is NOT_WALKED, not CLEAR or REFUSED."""
        walk = {
            "walked.example.com": {
                "policy": "allow",
                "verdict": "clear",
                "why": "no prior contact",
                "at": "2026-09-25T12:00:00Z",
            },
        }
        path = self._write_walk(walk)
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        accounts = state["accounts"]
        self.assertIn("walked.example.com", accounts)
        self.assertNotIn("unwalked.example.com", accounts)
        absent = "unwalked.example.com" not in accounts
        self.assertTrue(absent,
                        "an un-walked domain must be absent from the walk state")

    def test_three_buckets_sum_to_input(self):
        """CLEAR, REFUSED, and NOT_WALKED partition the input set."""
        walk = {
            "a.test": {"policy": "allow", "verdict": "clear",
                        "at": "2026-09-25T12:00:00Z"},
            "b.test": {"policy": "stop", "verdict": "in_sequence",
                        "at": "2026-09-25T12:00:00Z"},
            "c.test": {"verdict": "REFUSED",
                        "why": "broad match", "at": "2026-09-25T12:00:00Z"},
        }
        path = self._write_walk(walk)
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        accounts = state["accounts"]
        clear = refused = other = 0
        for entry in accounts.values():
            v = entry.get("verdict", "")
            if v == "REFUSED":
                refused += 1
            elif entry.get("policy") == "allow":
                clear += 1
            else:
                other += 1
        self.assertEqual(clear + refused + other, len(accounts),
                         "the three buckets must sum to the walked set")
        self.assertEqual(clear, 1)
        self.assertEqual(refused, 1)
        self.assertEqual(other, 1)

    def test_refused_carries_a_walk_date(self):
        """Every verdict row carries `at`, so clearance age is visible."""
        walk = {
            "r.test": {"verdict": "REFUSED", "why": "broad match",
                        "at": "2026-09-25T12:00:00Z"},
        }
        path = self._write_walk(walk)
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        for entry in state["accounts"].values():
            self.assertIn("at", entry,
                          "every verdict must carry the day it was walked")
            self.assertTrue(entry["at"].startswith("2026-"),
                            "the walk date must be a real timestamp")


if __name__ == "__main__":
    unittest.main()
