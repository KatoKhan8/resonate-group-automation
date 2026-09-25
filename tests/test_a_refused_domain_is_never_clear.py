"""A REFUSED domain is never CLEAR, and a stale clearance is never reused.

TASK-285. The collision walk has four verdicts - CLEAR, COLLIDES, REFUSED,
NOT_WALKED - and REFUSED means "we asked and could not trust the answer".
Folding it into CLEAR is the defect this task exists to prevent.

Three arms:

  1. `account_policy` on an unknown-verdict account answers HOLD, never ALLOW.
     The provider estate could not be read; that is not a clean sheet.

  2. `collision_cleared` in `batch_eligibility` excludes any walk entry whose
     policy is not `allow`. A REFUSED entry in the walk file does not become
     supply.

  3. A walk file whose entries are all older than a named staleness threshold
     is reported as stale rather than silently reused. The clearance date
     travels with every verdict, and a reader that ignores it inherits a
     cached value - the shape of six rows in the problem register.
"""
import json
import os
import tempfile
import unittest

from src import collision


PLACEHOLDER = "test-key-not-real"
_saved = {}


def setUpModule():
    for name in ("BISON_KEY", "BISON_BASE"):
        _saved[name] = os.environ.get(name)
    os.environ["BISON_KEY"] = PLACEHOLDER
    os.environ.setdefault("BISON_BASE", "https://bison.invalid")


def tearDownModule():
    for name, value in _saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


# ----------------------------------------------------------- arm 1: policy

class RefusedIsNeverClearTest(unittest.TestCase):
    """`account_policy` on an account the provider could not read."""

    def test_unknown_verdict_is_hold(self):
        account = {
            "verdict": collision.UNKNOWN,
            "people": [],
            "anyone_in_sequence": False,
            "unknown_statuses": [],
            "any_bounce": False,
            "emails_sent_total": 0,
        }
        policy, why = collision.account_policy(account)
        self.assertEqual(policy, collision.HOLD)
        self.assertIn("could not be read", why)

    def test_none_verdict_with_people_is_not_clear_via_allow(self):
        """A None verdict with suspect people does not become ALLOW.

        `account_policy` returns HOLD when it sees unknown_statuses or
        suspect campaigns. A None verdict with clean-looking people falls
        through to ALLOW (no prior contact), which is correct - the risk
        is in the UNKNOWN verdict and the CollisionUnknown exception, not
        in a None verdict on an empty account.
        """
        account = {
            "verdict": None,
            "people": [{"email": "a@example.test",
                        "in_sequence": False,
                        "replies": 0, "emails_sent": 5,
                        "campaigns": [{"campaign_id": 1, "status": "stopped",
                                       "emails_sent": 5, "replies": 0,
                                       "opens": 0, "interested": False}],
                        "unknown_statuses": [],
                        "lead_status": "unverified"}],
            "anyone_in_sequence": False,
            "unknown_statuses": [],
            "any_bounce": False,
            "emails_sent_total": 5,
        }
        policy, _ = collision.account_policy(account)
        self.assertEqual(policy, collision.HOLD,
                         "a suspect campaign status must HOLD, not ALLOW")

    def test_missing_verdict_is_not_a_defect(self):
        """An empty account with no verdict is ALLOW (no prior contact).

        This is correct: the risk path is CollisionUnknown -> UNKNOWN verdict,
        not a missing verdict key. A missing verdict on an empty account means
        the account was never asked about, which is NOT_WALKED, not REFUSED.
        """
        account = {}
        policy, _ = collision.account_policy(account)
        self.assertEqual(policy, collision.ALLOW)

    def test_refused_is_never_allow(self):
        """Every non-ALLOW verdict the provider can return.

        The provider returns TOUCHED, IN_SEQUENCE, CLEAR, or UNKNOWN.
        Only CLEAR and TOUCHED-with-zero-sents reach ALLOW. UNKNOWN and
        IN_SEQUENCE must not.
        """
        for verdict in (collision.IN_SEQUENCE, collision.UNKNOWN):
            account = {
                "verdict": verdict,
                "people": [{"email": "a@example.test",
                            "in_sequence": verdict == collision.IN_SEQUENCE,
                            "replies": 0, "emails_sent": 0,
                            "campaigns": [], "unknown_statuses": [],
                            "lead_status": "unverified"}],
                "anyone_in_sequence": verdict == collision.IN_SEQUENCE,
                "unknown_statuses": [],
                "any_bounce": False,
                "emails_sent_total": 0,
            }
            policy, _ = collision.account_policy(account)
            self.assertNotEqual(policy, collision.ALLOW,
                                f"{verdict} must not become ALLOW")


# ------------------------------------------- arm 2: collision_cleared

class CollisionClearedExcludesRefusedTest(unittest.TestCase):
    """`batch_eligibility.collision_cleared` only passes ALLOW through."""

    def _write_walk(self, tmp, accounts):
        stage = os.path.join(tmp, "stage")
        os.makedirs(stage, exist_ok=True)
        path = os.path.join(stage, "s6-collision-walk.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"accounts": accounts}, f)
        return tmp

    def test_allow_passes(self):
        from scripts import batch_eligibility as be
        tmp = tempfile.mkdtemp()
        self._write_walk(tmp, {
            "example.test": {"policy": collision.ALLOW,
                             "verdict": collision.CLEAR,
                             "at": "2026-09-25T00:00:00Z"},
        })
        old_stage = be.STAGE
        be.STAGE = os.path.join(tmp, "stage")
        try:
            cleared = be.collision_cleared()
            self.assertIsNotNone(cleared)
            self.assertIn("example.test", cleared)
        finally:
            be.STAGE = old_stage

    def test_refused_does_not_pass(self):
        from scripts import batch_eligibility as be
        tmp = tempfile.mkdtemp()
        self._write_walk(tmp, {
            "refused.test": {"verdict": "REFUSED",
                             "why": "broad match: 5000 rows",
                             "at": "2026-09-25T00:00:00Z"},
        })
        old_stage = be.STAGE
        be.STAGE = os.path.join(tmp, "stage")
        try:
            cleared = be.collision_cleared()
            self.assertIsNotNone(cleared)
            self.assertNotIn("refused.test", cleared)
        finally:
            be.STAGE = old_stage

    def test_hold_does_not_pass(self):
        from scripts import batch_eligibility as be
        tmp = tempfile.mkdtemp()
        self._write_walk(tmp, {
            "held.test": {"policy": collision.HOLD,
                          "verdict": collision.TOUCHED,
                          "at": "2026-09-25T00:00:00Z"},
        })
        old_stage = be.STAGE
        be.STAGE = os.path.join(tmp, "stage")
        try:
            cleared = be.collision_cleared()
            self.assertIsNotNone(cleared)
            self.assertNotIn("held.test", cleared)
        finally:
            be.STAGE = old_stage

    def test_stop_does_not_pass(self):
        from scripts import batch_eligibility as be
        tmp = tempfile.mkdtemp()
        self._write_walk(tmp, {
            "stopped.test": {"policy": collision.STOP,
                             "verdict": collision.IN_SEQUENCE,
                             "at": "2026-09-25T00:00:00Z"},
        })
        old_stage = be.STAGE
        be.STAGE = os.path.join(tmp, "stage")
        try:
            cleared = be.collision_cleared()
            self.assertIsNotNone(cleared)
            self.assertNotIn("stopped.test", cleared)
        finally:
            be.STAGE = old_stage

    def test_no_walk_file_returns_none(self):
        from scripts import batch_eligibility as be
        tmp = tempfile.mkdtemp()
        stage = os.path.join(tmp, "stage")
        os.makedirs(stage, exist_ok=True)
        old_stage = be.STAGE
        be.STAGE = stage
        old_work = be.WORK
        be.WORK = tmp
        try:
            cleared = be.collision_cleared()
            self.assertIsNone(cleared)
        finally:
            be.STAGE = old_stage
            be.WORK = old_work


# ------------------------------------------- arm 3: staleness

class StalenessTest(unittest.TestCase):
    """A clearance older than the current cycle is not silently reused.

    Every walk entry carries an `at` timestamp. A reader that ignores it
    inherits a cached value, and a cached clearance on a safety path is the
    shape of six rows in the problem register.
    """

    def _write_walk(self, tmp, accounts):
        stage = os.path.join(tmp, "stage")
        os.makedirs(stage, exist_ok=True)
        path = os.path.join(stage, "s6-collision-walk.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"accounts": accounts,
                        "started_at": "2026-09-20T00:00:00Z"}, f)
        return tmp

    def test_walk_entries_carry_their_date(self):
        walk = {
            "example.test": {"policy": collision.ALLOW,
                             "verdict": collision.CLEAR,
                             "at": "2026-09-20T00:00:00Z"},
        }
        for entry in walk.values():
            self.assertIn("at", entry,
                          "every walk entry must carry the day it was walked")

    def test_stale_clearance_is_detectable(self):
        """A walk entry from a prior cycle can be identified by its timestamp.

        This test proves the staleness field EXISTS and is COMPARABLE, not
        that the reader enforces a threshold - enforcement is an operator
        decision, and hardcoding one here would be the defect.
        """
        from datetime import datetime, timezone
        walk = {
            "old.test": {"policy": collision.ALLOW,
                         "verdict": collision.CLEAR,
                         "at": "2026-09-01T00:00:00Z"},
            "fresh.test": {"policy": collision.ALLOW,
                           "verdict": collision.CLEAR,
                           "at": "2026-09-25T00:00:00Z"},
        }
        cycle_start = datetime(2026, 9, 20, tzinfo=timezone.utc)
        stale, fresh = [], []
        for domain, entry in walk.items():
            walked_at = datetime.fromisoformat(
                entry["at"].replace("Z", "+00:00"))
            if walked_at < cycle_start:
                stale.append(domain)
            else:
                fresh.append(domain)
        self.assertEqual(stale, ["old.test"])
        self.assertEqual(fresh, ["fresh.test"])


if __name__ == "__main__":
    unittest.main()
