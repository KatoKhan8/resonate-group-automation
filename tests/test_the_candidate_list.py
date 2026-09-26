"""The candidate list: accumulating, de-duplicated by domain. TASK-245.

A candidate is a company that passed sourcing -> ICP -> MX -> collision and
is waiting for the weekly export. Each row records WHEN and WHY it arrived.

ACCEPTANCE: one test proves a rejected-then-resourced domain does not
reappear as new.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import candidatelist, store


class CandidateListTestBase(unittest.TestCase):
    """Store isolation for candidate list tests."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="rga-candid-")
        self._restore_store = store.use_directory(
            os.path.join(self._tmp, "work"))
        self._candidates_env = os.environ.get("CANDIDATES")
        os.environ["CANDIDATES"] = os.path.join(
            self._tmp, "work", "candidates.jsonl")

    def tearDown(self):
        if self._candidates_env is None:
            os.environ.pop("CANDIDATES", None)
        else:
            os.environ["CANDIDATES"] = self._candidates_env
        self._restore_store()
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestAppendAndDedup(CandidateListTestBase):
    """Appending to the candidate list, de-duplicated by domain."""

    def test_append_adds_a_new_candidate(self):
        result = candidatelist.append(
            {"domain": "new.example", "company": "New Co"})
        self.assertTrue(result)
        rows = candidatelist.load()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["domain"], "new.example")

    def test_append_returns_false_for_duplicate_domain(self):
        candidatelist.append({"domain": "dup.example"})
        result = candidatelist.append({"domain": "dup.example"})
        self.assertFalse(result)
        self.assertEqual(len(candidatelist.load()), 1)

    def test_append_is_case_insensitive_on_domain(self):
        candidatelist.append({"domain": "Case.Test"})
        result = candidatelist.append({"domain": "case.test"})
        self.assertFalse(result)

    def test_append_rejects_empty_domain(self):
        self.assertFalse(candidatelist.append({"domain": ""}))
        self.assertFalse(candidatelist.append({}))

    def test_domains_already_known_returns_all_domains(self):
        candidatelist.append({"domain": "a.test"})
        candidatelist.append({"domain": "b.test"})
        known = candidatelist.domains_already_known()
        self.assertEqual(known, {"a.test", "b.test"})


class TestRejectedThenResourcedDoesNotReappear(CandidateListTestBase):
    """ACCEPTANCE: a rejected-then-resourced domain does not reappear as new.

    A domain that was once on the candidate list and was rejected by Productive
    stays on the list (as "rejected"). When the nightly sourcing runs again
    and encounters the same domain, domains_already_known() includes it, so
    the sourcing diff skips it. It does NOT reappear as "new".
    """

    def test_a_rejected_domain_is_still_known(self):
        """A rejected candidate stays on the list and is known to the diff."""
        candidatelist.append({"domain": "rejected.test", "state": "rejected"})
        known = candidatelist.domains_already_known()
        self.assertIn("rejected.test", known)

    def test_a_rejected_domain_is_not_re_added(self):
        """Sourcing the same domain again returns False (already known)."""
        candidatelist.append({"domain": "rejected.test", "state": "rejected"})
        result = candidatelist.append({"domain": "rejected.test"})
        self.assertFalse(result)

    def test_an_exported_domain_is_still_known(self):
        candidatelist.append({"domain": "exported.test", "state": "exported"})
        known = candidatelist.domains_already_known()
        self.assertIn("exported.test", known)

    def test_an_approved_domain_is_still_known(self):
        candidatelist.append({"domain": "approved.test", "state": "approved"})
        known = candidatelist.domains_already_known()
        self.assertIn("approved.test", known)

    def test_the_rejected_domain_stays_rejected_not_new(self):
        """The state is preserved. A re-source attempt does not flip it."""
        candidatelist.append({"domain": "rejected.test", "state": "rejected"})
        candidatelist.append({"domain": "rejected.test"})
        rows = candidatelist.load()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["state"], "rejected")


class TestMarkExported(CandidateListTestBase):
    """Marking candidates as exported."""

    def test_mark_exported_changes_state(self):
        candidatelist.append({"domain": "exp.test", "state": "new"})
        changed = candidatelist.mark_exported(["exp.test"])
        self.assertEqual(changed, 1)
        rows = candidatelist.load()
        self.assertEqual(rows[0]["state"], "exported")

    def test_mark_exported_skips_non_new(self):
        candidatelist.append({"domain": "already.test", "state": "exported"})
        changed = candidatelist.mark_exported(["already.test"])
        self.assertEqual(changed, 0)

    def test_mark_exported_records_when(self):
        candidatelist.append({"domain": "when.test", "state": "new"})
        candidatelist.mark_exported(["when.test"], when="2026-09-22T07:00:00Z")
        rows = candidatelist.load()
        self.assertEqual(rows[0]["exported_at"], "2026-09-22T07:00:00Z")


class TestStats(CandidateListTestBase):
    """Candidate list statistics."""

    def test_stats_counts_by_state(self):
        candidatelist.append({"domain": "a.test", "state": "new"})
        candidatelist.append({"domain": "b.test", "state": "new"})
        candidatelist.append({"domain": "c.test", "state": "exported"})
        s = candidatelist.stats()
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["by_state"]["new"], 2)
        self.assertEqual(s["by_state"]["exported"], 1)

    def test_stats_on_empty_list(self):
        s = candidatelist.stats()
        self.assertEqual(s["total"], 0)


class TestCandidateStates(CandidateListTestBase):
    """The four states a candidate can be in."""

    def test_the_four_states_are_defined(self):
        self.assertEqual(candidatelist.CANDIDATE_STATES,
                         ("new", "exported", "approved", "rejected"))

    def test_a_new_candidate_has_state_new(self):
        candidatelist.append({"domain": "fresh.test"})
        rows = candidatelist.load()
        self.assertEqual(rows[0]["state"], "new")

    def test_a_new_candidate_has_added_at(self):
        candidatelist.append({"domain": "timestamped.test"})
        rows = candidatelist.load()
        self.assertIn("added_at", rows[0])
        self.assertTrue(rows[0]["added_at"])


if __name__ == "__main__":
    unittest.main()
