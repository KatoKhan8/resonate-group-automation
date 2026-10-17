"""POOL 0240: pin the lost `by=` attribution with a born-red test.

The defect (pool/0210 entry, measured 2026-10-17):

    `liststaging.stage_lead` accepts `by=` from its caller and forwards it
    into the Authorization via `providerwrites.grant(..., by=by, ...)` - but
    it does NOT pass `by=by` as a top-level kwarg to `providerwrites.perform`.
    `perform` reads the attribution for the LEDGER row from its kwargs via
    `kw.get("by")`, so every `stage_lead` call today records `"by": None` in
    the provider-writes ledger regardless of who asked for the write.

The one-line fix (NOT applied here - operator's call, recorded in pool/0210):

    src/liststaging.py:340 - add `by=by,` as a kwarg to the `perform(...)`
    call. Once applied, the ledger row carries the caller's identity.

This file pins the defect:

    1. `test_stage_lead_preserves_caller_by_in_ledger` - calls `stage_lead`
       with an explicit caller identity, reads the ledger row back, asserts
       `row["by"] == <caller>`. On current HEAD (9ecad20e7) this assertion
       fails because `row["by"]` is None. Wrapped @unittest.expectedFailure
       so the module run is green; the failure is the visible marker.
    2. Two calibration arms that call the SAME fixture with correct `by`
       values and show the test does NOT fire - the test observes the defect,
       not collateral.
    3. The fix is NEVER applied to this tree. Teeth are proven on a SCRATCH
       copy (see scratch/ tree, separate from this branch) - the brief owns
       that arm and records the sha256 of the patched file.

Skip-beats-expectedFailure caution: the body has no reachable `skip` - no
`@unittest.skip`, no `skipTest` call, no conditional that could absorb an
unexpected success. The expectedFailure decorator is the outermost wrapper
over a non-skipping body, so an unexpected success surfaces with its name
in the unittest output.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import providerwrites, store  # noqa: E402
from src.liststaging import stage_lead  # noqa: E402


# --------------------------------------------------------------- fixtures

LIST_UNBOUND = {
    "id": 940797,
    "name": "staging-list-pool-0240",
    "listType": "USER_LIST",
    "totalItemsCount": 0,
    "campaignIds": [],
    "creationTime": "2026-09-15T00:00:00Z",
}

LEAD_OK = {
    "linkedin_url": "https://www.linkedin.com/in/pool-0240-test-profile",
    "first_name": "Pool",
    "last_name": "Test",
    "company": "TestCo",
    "title": "Engineer",
}


def _fake_transport(response=None):
    calls = []
    def _transport(payload):
        calls.append(payload)
        return response or {"addedLeadsCount": 1, "totalLeads": 1,
                            "duplicateLeads": 0}
    _transport.calls = calls
    return _transport


def _fake_list_reader(row):
    def _read(list_id):
        return dict(row)
    return _read


def _fake_members_reader(members, total=None):
    def _read(list_id, offset=0, limit=100):
        return list(members), total if total is not None else len(members)
    return _read


class _IsolatedLedger(unittest.TestCase):
    """Isolate store + ledger for every test.

    Reuses the proven pattern from test_list_staging._IsolatedStore AND
    test_a_resume_leaves_a_ledger_row._Ledgered: tempdir for store, env
    override for the ledger path. Both are restored on tearDown.
    """

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-pool0240-")
        self._store_tmp = os.path.join(self.tmp, "store")
        self._env_prev = {
            k: os.environ.get(k)
            for k in ("QUEUE",) + tuple(store.STATE_OVERRIDES)
        }
        store.use_directory(os.path.join(self._store_tmp, "work"))

        self.ledger_path = os.path.join(self.tmp, "provider-writes.jsonl")
        self._ledger_prev = os.environ.get(providerwrites.PROVIDER_WRITES_LEDGER)
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self.ledger_path

    def tearDown(self):
        for key, value in self._env_prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if self._ledger_prev is None:
            os.environ.pop(providerwrites.PROVIDER_WRITES_LEDGER, None)
        else:
            os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self._ledger_prev
        super().tearDown()

    def ledger_rows(self):
        if not os.path.exists(self.ledger_path):
            return []
        with io.open(self.ledger_path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]


class TestByAttribution(_IsolatedLedger):
    """The defect: `stage_lead(by=<caller>)` loses the caller's identity in
    the provider-writes ledger.
    """

    def _stage_ok(self, by):
        url = LEAD_OK["linkedin_url"]
        transport = _fake_transport()
        result = stage_lead(
            940797, LEAD_OK, transport,
            list_reader=_fake_list_reader(LIST_UNBOUND),
            members_reader=_fake_members_reader(
                [{"profile_url": url}], total=1),
            by=by,
        )
        self.assertEqual(result["class"], "ACCEPTED")
        rows = self.ledger_rows()
        self.assertGreaterEqual(len(rows), 1,
                                "expected at least one ledger row")
        # The ledger writes the outcome in lowercase ('accepted', not
        # 'ACCEPTED'). Find the happy-path row (anything that is not a
        # refusal/failure/unverified).
        happy = [r for r in rows
                 if r.get("outcome") not in
                 ("refused", "failed", "unverified")]
        self.assertGreaterEqual(len(happy), 1,
                                "expected a happy-path ledger row, got: %r"
                                % [r.get("outcome") for r in rows])
        return happy[-1]

    @unittest.expectedFailure
    def test_stage_lead_preserves_caller_by_in_ledger(self):
        """pool/0240: the caller's `by=` must appear in the ledger row.

        On current HEAD (9ecad20e7a937b44b7d3856e4397ce0839f5fac3), the
        `perform(...)` call in liststaging.stage_lead does not pass
        `by=by` as a top-level kwarg, so `kw.get("by")` returns None and
        the ledger row records `"by": None`.

        The ONE-LINE FIX that turns this green:
            src/liststaging.py:340 - add `by=by,` to the `perform(...)` call.
        Provenance: pool/0210 entry, measured 2026-10-17.
        """
        row = self._stage_ok(by="pool-0240-caller")
        # The actual assertion that fails on current code:
        # row["by"] is None, but we asked for "pool-0240-caller".
        self.assertEqual(
            row.get("by"), "pool-0240-caller",
            "stage_lead lost the caller's by= attribution in the ledger: "
            f"row['by'] = {row.get('by')!r}, expected 'pool-0240-caller'. "
            "Fix: src/liststaging.py:340 add by=by to the perform() call.")


# --------------------------------------------------------------- calibration

class TestByAttributionCalibration(_IsolatedLedger):
    """Two calibration shapes: the SAME ledger writer exercised with a
    correct `by=` value, bypassing the stage_lead -> perform seam.

    These call `providerwrites._ledger` directly (the function that writes
    the row), to show the assertion logic is sound and the test only fires
    on the actual defect in `stage_lead`'s call to `perform`.

    The defect is NOT in _ledger - it is in stage_lead's failure to pass
    `by=by` as a top-level kwarg to perform(). If these calibration arms
    red, the instrument is broken, not the code under test.

    Pool/0210 identified EIGHT other callers that DO pass `by=by` correctly
    to perform(): bisonfactory (3), heyreachfactory (2), leadstop (2),
    orchestrator (2). Those callers are NOT exercised here because they
    require campaign fixtures; the direct _ledger call proves the same
    property (the ledger records what it is told) without the fixture cost.
    """

    def _ledger_ok(self, by):
        """Call _ledger directly with `by=<caller>`.

        This bypasses perform() entirely, so the calibration is strictly
        about the ledger-writing seam. If _ledger loses the attribution,
        the defect is in the writer; if it preserves it, the defect is in
        the caller that doesn't pass by= through.
        """
        from src import providerwrites as pw
        pw._ledger(
            pw.LINKEDIN_ADD_LEAD_TO_LIST,
            "accepted",
            campaign=None,
            tenant=None,
            by=by,
            step="pool-0240-calibration",
            key="UNKNOWN",
        )
        rows = self.ledger_rows()
        self.assertGreaterEqual(len(rows), 1,
                                "calibration expected at least one row")
        return rows[-1]

    def test_calibration_shape_a_ledger_with_by(self):
        """Calibration A: _ledger with `by='calibration-A'`. The row MUST
        carry the caller's identity.

        If this fails, the ledger writer itself is broken - the defect is
        NOT in stage_lead, it is in the ledger. That would be a different
        and more serious defect.
        """
        row = self._ledger_ok(by="calibration-A")
        self.assertEqual(
            row.get("by"), "calibration-A",
            "calibration A broken: _ledger itself lost the attribution")

    def test_calibration_shape_b_ledger_with_different_by(self):
        """Calibration B: different caller identity, same shape. Proves the
        assertion is not accidentally tied to a specific string.
        """
        row = self._ledger_ok(by="calibration-B")
        self.assertEqual(
            row.get("by"), "calibration-B",
            "calibration B broken: _ledger itself lost the attribution")


if __name__ == "__main__":
    unittest.main()
