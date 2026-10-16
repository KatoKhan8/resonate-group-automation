"""TASK-0248: a missing agency index must refuse, not read as cleared.

`hygiene.check(candidate, history, agency=None)` guarded the agency-wide
do-not-contact lookup with `if agency is not None:`, which has two exits and
needs three. A caller that supplied no index fell straight through to the
account rules and the row came back `fresh` / `eligible` - a verdict that is
indistinguishable from "we checked the agency list and she is not on it".

The two facts a suppression check may never render identically:

    asked, answer was no    ->  not suppressed, and the row may proceed
    never asked             ->  UNDETERMINED, and the row may not

Compare `agencydnc.lookup(candidate, index=None)`, which loads the roster
rather than skipping it. That is the fail-safe shape and it is why the send
path never carried this hole; `hygiene.check` is the import path, where the
index argument exists precisely to avoid a disk read per row, so it refuses
instead of loading.

Every index here is built in memory - `agencydnc.Index(index={...})` - so no
test in this module reads or writes the real roster.
"""
import unittest

from src import agencydnc, hygiene

from . import base


def _index(*rows):
    """An in-memory agency index holding exactly these identifiers."""
    held = {}
    for kind, value in rows:
        held[agencydnc.fingerprint(kind, value)] = {
            "reason": agencydnc.REQUESTED, "at": "2026-10-16T00:00:00Z"}
    return agencydnc.Index(index=held)


class ANoneAgencyIndexRefuses(base.QueueTest):
    """The defect, and the two controls that prove what reddened it."""

    def setUp(self):
        super().setUp()
        self.history = hygiene.index([])
        self.candidate = {"email": "sarah@acme.test", "domain": "acme.test",
                          "company": "Acme"}

    # ------------------------------------------------------------ the defect

    def test_a_none_index_is_not_cold_eligible(self):
        """The row must not come back eligible when nothing was checked."""
        verdict = hygiene.check(self.candidate, self.history, agency=None)
        self.assertNotEqual(
            hygiene.ELIGIBLE, verdict["action"],
            "a row whose agency-list status was never looked up came back "
            "cold-eligible: " + verdict["why"])
        self.assertEqual(hygiene.AGENCY_UNDETERMINED, verdict["verdict"])

    def test_the_default_is_the_refusing_one(self):
        """Forgetting the argument fails closed, not open.

        The signature default IS the reachable path: `upload.parse` and
        `referral.promotable` both default `agency` to None and forward it,
        so whatever the default does is what a forgetful caller gets.
        """
        verdict = hygiene.check(self.candidate, self.history)
        self.assertNotEqual(hygiene.ELIGIBLE, verdict["action"])

    def test_the_row_says_the_list_was_not_checked(self):
        """An operator must be able to tell this from a clean answer."""
        verdict = hygiene.check(self.candidate, self.history, agency=None)
        self.assertIn("not", verdict["why"].lower())
        self.assertIn("agency", verdict["why"].lower())
        self.assertNotIn("no prior history", verdict["why"].lower())

    def test_not_asking_is_deliberate_and_different_from_forgetting(self):
        """`AGENCY_NOT_ASKED` is a token somebody has to type.

        Without it the only way to get a clean verdict is to build a real
        `agencydnc.Index()`, which opens the roster on disk - so a benchmark
        or a test about the account rules would be forced into a production
        read to say something it does not care about.
        """
        asked_not = hygiene.check(self.candidate, self.history,
                                  agency=hygiene.AGENCY_NOT_ASKED)
        forgot = hygiene.check(self.candidate, self.history, agency=None)
        self.assertEqual(hygiene.ELIGIBLE, asked_not["action"])
        self.assertNotEqual(asked_not["action"], forgot["action"])

    def test_undetermined_never_outranks_a_verdict_that_knows_something(self):
        """`worst` must still prefer a real finding to a shrug."""
        self.assertEqual(
            hygiene.AGENCY_SUPPRESSED,
            hygiene.worst([hygiene.AGENCY_UNDETERMINED,
                           hygiene.AGENCY_SUPPRESSED]))
        self.assertEqual(
            hygiene.AGENCY_UNDETERMINED,
            hygiene.worst([hygiene.FRESH, hygiene.AGENCY_UNDETERMINED]))

    # ------------------------------------------------------- the controls
    #
    # Both of these pass BEFORE the repair as well as after. They are here
    # so that a red run above cannot be explained by "the agency branch is
    # broken in general" or by the test reaching a different guard: the
    # supplied-index paths are observed working in the same run.

    def test_control_a_supplied_empty_index_still_clears_the_row(self):
        """An index that was opened and held nobody is a CLEAN answer."""
        verdict = hygiene.check(self.candidate, self.history,
                                agency=_index())
        self.assertEqual(hygiene.FRESH, verdict["verdict"])
        self.assertEqual(hygiene.ELIGIBLE, verdict["action"])

    def test_control_b_a_supplied_index_still_suppresses(self):
        """And one that holds her still refuses her, unchanged."""
        verdict = hygiene.check(self.candidate, self.history,
                                agency=_index(("email", "sarah@acme.test")))
        self.assertEqual(hygiene.AGENCY_SUPPRESSED, verdict["verdict"])
        self.assertEqual(hygiene.SUPPRESS, verdict["action"])


if __name__ == "__main__":
    unittest.main()
