"""The knowledge pack is built, dated and traceable - never remembered.

OPERATOR, 2026-09-21: "KNOWLEDGE PACK, rebuilt hourly and on demand."

The register's own summary of six separate defects is "a value that was true
when it was written, cached somewhere that had no way to notice it had gone
stale". The pack is the obvious place for that failure to happen again, so
these tests assert the three properties that prevent it:

1. Every section names the file it was built from, and a missing file is
   recorded as missing rather than skipped.
2. Every milestone is a sentence that is still present in the document it
   claims to come from. A milestone whose sentence has gone produces no
   milestone.
3. A stale cache is rebuilt on read, not served with a disclaimer.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackknowledge as knowledge                      # noqa: E402
from tests.slackbase import IsolatedState                        # noqa: E402


class TheSourcesAreNamed(unittest.TestCase):

    def test_every_source_file_is_reported_present_or_missing(self):
        rows = knowledge.sources()
        self.assertTrue(rows)
        for label, row in rows.items():
            self.assertIn("path", row, label)
            self.assertIn("present", row, label)
            if row["present"]:
                self.assertTrue(row["modified"], label)

    def test_the_documents_this_pack_is_built_from_exist(self):
        """A missing source is a real finding, not a test to skip."""
        rows = knowledge.sources()
        missing = [row["path"] for row in rows.values()
                   if not row["present"]]
        self.assertFalse(missing,
                         "the knowledge pack names source files that are "
                         "not in the tree: %s" % missing)

    def test_identity_names_its_source(self):
        self.assertEqual(knowledge.identity()["source"], "PRODUCT-GOAL.md")

    def test_identity_carries_what_this_is_not(self):
        rows = knowledge.identity()["what_it_is_not"]
        self.assertTrue(rows)
        self.assertTrue(any("SaaS" in row for row in rows))

    def test_identity_carries_the_hierarchy(self):
        hierarchy = knowledge.identity()["hierarchy"]
        self.assertIn("RESONATE", hierarchy)
        self.assertTrue(any("CLIENT WORKSPACE" in row for row in hierarchy))


class TheTimelineComesFromGitAndFromNamedSentences(unittest.TestCase):

    def setUp(self):
        self.timeline = knowledge.timeline()

    def test_the_start_date_comes_from_the_first_commit(self):
        self.assertRegex(self.timeline["started_on"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertGreater(self.timeline["commits_total"], 0)

    def test_every_milestone_names_a_file_that_exists(self):
        for row in self.timeline["milestones"]:
            path = os.path.join(ROOT, row["source"])
            self.assertTrue(os.path.isfile(path), row["source"])

    def test_the_first_send_milestone_is_present_and_dated(self):
        first = [row for row in self.timeline["milestones"]
                 if row["id"] == "first-send"]
        self.assertEqual(len(first), 1,
                         "the first provider-confirmed send is the one fact "
                         "this project is organised around; it must be in "
                         "the pack or the pattern that produced it has "
                         "changed")
        self.assertIn("2026-09-21T13:34:48Z", first[0]["fact"])

    def test_a_pattern_that_no_longer_matches_produces_no_milestone(self):
        """Absent, not remembered. This is the whole contract."""
        original = knowledge.MILESTONE_PATTERNS
        knowledge.MILESTONE_PATTERNS = (
            ("fictional", "docs/state/PROBLEM-REGISTER.md",
             r"THIS SENTENCE IS NOT IN THE REGISTER (\d+)", "never {0}"),)
        try:
            rows = knowledge.timeline()["milestones"]
            self.assertEqual(rows, [])
        finally:
            knowledge.MILESTONE_PATTERNS = original


class ThePoliciesAreParsedNotTranscribed(unittest.TestCase):

    def setUp(self):
        self.rows = knowledge.policies()

    def test_the_standing_decisions_are_all_present(self):
        ids = {row["id"] for row in self.rows}
        for wanted in ("provider-order", "verification", "credit-spend",
                       "collision-recency", "pipeline-order", "batches",
                       "pacing"):
            self.assertIn(wanted, ids)

    def test_each_decision_carries_a_date_and_a_decider(self):
        for row in self.rows:
            self.assertRegex(row["decided_on"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertTrue(row["decided_by"])
            self.assertTrue(row["source"])

    def test_each_decision_explains_itself_in_plain_language(self):
        for row in self.rows:
            self.assertTrue(row.get("why"),
                            "%s has no plain-language reason. The operator "
                            "asked for the WHY, and a rule with no reason is "
                            "the thing somebody argues with later."
                            % row["id"])

    def test_the_rule_text_does_not_keep_the_table_label(self):
        """A parser that left "ORDER" on the front of the provider order was
        the first version of this, and it read as a typo in every answer."""
        by_id = {row["id"]: row for row in self.rows}
        self.assertTrue(by_id["provider-order"]["rule"].startswith(
            "ContactOut"))
        self.assertTrue(by_id["credit-spend"]["rule"].startswith("reported"))

    def test_an_editorial_row_says_it_is_editorial(self):
        editorial = [row for row in self.rows if row.get("editorial")]
        self.assertTrue(editorial)
        for row in editorial:
            self.assertNotIn(".md", row["source"])


class TheCacheIsRebuiltWhenItIsStale(unittest.TestCase):

    def setUp(self):
        """Pin the cache through its ENV OVERRIDE, not the module constant.

        This set the constant alone and passed in isolation and failed after
        `tests.test_invariants`, which calls `store.use_directory` and leaves
        `KNOWLEDGE_PACK` pointing at a temp tree it has since deleted.
        `cache_path()` reads the override first - deliberately, it is the
        canonical one now that the pack is in `store.STATE_OVERRIDES` - so a
        test that pins only the constant is pinning the thing that loses.
        """
        self.tmp = tempfile.mkdtemp(prefix="rga-pack-")
        self.path = os.path.join(self.tmp, "work", "pack.json")
        self._cache = knowledge.CACHE
        self._env = os.environ.get(knowledge.CACHE_VAR)
        knowledge.CACHE = self.path
        os.environ[knowledge.CACHE_VAR] = self.path

    def tearDown(self):
        knowledge.CACHE = self._cache
        if self._env is None:
            os.environ.pop(knowledge.CACHE_VAR, None)
        else:
            os.environ[knowledge.CACHE_VAR] = self._env
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_fresh_cache_is_served(self):
        first = knowledge.pack()
        second = knowledge.pack()
        self.assertEqual(first["built_at"], second["built_at"])

    def test_a_stale_cache_is_rebuilt_rather_than_disclaimed(self):
        built = knowledge.write(knowledge.build())
        stale = dict(built, built_epoch=int(time.time()) - 7200)
        with open(knowledge.cache_path(), "w", encoding="utf-8") as handle:
            json.dump(stale, handle, default=str)
        fresh = knowledge.pack()
        self.assertGreater(fresh["built_epoch"], stale["built_epoch"])

    def test_an_unreadable_cache_is_rebuilt_not_raised(self):
        os.makedirs(os.path.dirname(knowledge.cache_path()), exist_ok=True)
        with open(knowledge.cache_path(), "w", encoding="utf-8") as handle:
            handle.write("not json")
        self.assertIn("built_at", knowledge.pack())

    def test_the_cache_lives_under_work(self):
        self.assertIn("work", knowledge.cache_path())


class ThePackCarriesNoAddress(IsolatedState, unittest.TestCase):
    """Counts and domains, the rule `notify._status_payload` enforces."""

    def setUp(self):
        self.isolate()

    def tearDown(self):
        self.restore()

    def test_no_section_of_the_pack_contains_an_email_address(self):
        from src import slackscope
        body = json.dumps(knowledge.pack(force=True), default=str)
        cleaned = slackscope.redact_addresses(body)
        self.assertEqual(
            body, cleaned,
            "the knowledge pack contains something shaped like a mailbox "
            "address. It carries counts and domains only.")


class EveryNumberIsIndexed(IsolatedState, unittest.TestCase):

    def setUp(self):
        self.isolate()

    def tearDown(self):
        self.restore()

    def test_the_pack_reports_its_own_numbers(self):
        data = knowledge.pack()
        found = knowledge.numbers(data)
        self.assertTrue(found)
        self.assertIn(str(data["timeline"]["commits_total"]), found)


if __name__ == "__main__":
    unittest.main()
