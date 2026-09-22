#!/usr/bin/env python3
"""The client-approval gate: unknown is pending, pending refuses, no is forever.

The operator placed this in the same class as verification and collision on
2026-09-21, which means the tests that matter are the ones about what it
REFUSES. A gate is only worth its name when the default is closed and there
is no parameter that opens it.
"""
import os
import tempfile
import unittest

from src import clientapproval as ca, store


class ApprovalCase(unittest.TestCase):

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self._previous = os.environ.get("CLIENT_APPROVAL")
        os.environ["CLIENT_APPROVAL"] = os.path.join(self._dir.name,
                                                     "client-approval.jsonl")
        self.addCleanup(self._restore)

    def _restore(self):
        if self._previous is None:
            os.environ.pop("CLIENT_APPROVAL", None)
        else:
            os.environ["CLIENT_APPROVAL"] = self._previous
        self._dir.cleanup()


class TheDefaultIsClosed(ApprovalCase):

    def test_an_account_nobody_has_decided_about_is_refused(self):
        with self.assertRaises(ca.ClientApprovalRequired):
            ca.require_approved("never-heard-of.example")

    def test_the_refusal_names_the_state_it_found(self):
        try:
            ca.require_approved("never-heard-of.example")
        except ca.ClientApprovalRequired as exc:
            self.assertEqual(exc.state, ca.PENDING)
            self.assertEqual(exc.domain, "never-heard-of.example")
        else:
            self.fail("an unknown account must refuse")

    def test_explicit_pending_is_refused_too(self):
        ca.record("waiting.example", state=ca.PENDING, who="zvonimir",
                  source="test")
        self.assertFalse(ca.is_approved("waiting.example"))

    def test_approved_passes(self):
        ca.record("yes.example", state=ca.APPROVED, who="zvonimir",
                  source="test")
        self.assertEqual(ca.require_approved("yes.example")["state"],
                         ca.APPROVED)

    def test_there_is_no_parameter_that_opens_the_gate(self):
        """Hard stop 8 covers a weakened rule, and a kill switch IS the
        weakening. This asserts the absence of the thing, which is the only
        way to keep it absent."""
        import inspect
        names = set()
        for func in (ca.require_approved, ca.is_approved, ca.state_of):
            names |= set(inspect.signature(func).parameters)
        for forbidden in ("enforce", "skip", "skip_approval", "force",
                          "allow_pending", "bypass", "override"):
            self.assertNotIn(forbidden, names)


class OneAccountManySpellings(ApprovalCase):

    def test_an_address_resolves_to_its_domain(self):
        ca.record("Example-Agency.example.test", state=ca.APPROVED, who="z",
                  source="test")
        self.assertTrue(ca.is_approved("A.Hobson@Example-Agency.example.test"))

    def test_www_and_a_url_are_the_same_account(self):
        ca.record("example.com", state=ca.APPROVED, who="z", source="test")
        for spelling in ("www.example.com", "https://example.com/pricing",
                         "EXAMPLE.com", "example.com."):
            self.assertTrue(ca.is_approved(spelling), spelling)


class NoIsForever(ApprovalCase):

    def test_an_approval_over_a_rejection_raises(self):
        ca.record("no.example", state=ca.REJECTED, who="client",
                  source="email 2026-09-01")
        with self.assertRaises(ca.PermanentDecision):
            ca.record("no.example", state=ca.APPROVED, who="z", source="test")

    def test_an_approval_over_a_suppression_raises(self):
        ca.record("gone.example", state=ca.SUPPRESSED, who="client",
                  source="snapshot S1", reason="removed by client")
        with self.assertRaises(ca.PermanentDecision):
            ca.record("gone.example", state=ca.APPROVED, who="z", source="test")

    def test_a_written_reversal_lifts_it_and_nothing_else_does(self):
        ca.record("back.example", state=ca.SUPPRESSED, who="client",
                  source="snapshot S1")
        ca.record("back.example", state=ca.APPROVED, who="client",
                  source="email 2026-09-20", reverses="snapshot S1",
                  evidence="mail thread 2026-09-20 from the client")
        self.assertTrue(ca.is_approved("back.example"))

    def test_bulk_never_lifts_a_permanent_decision_silently(self):
        ca.record("gone.example", state=ca.SUPPRESSED, who="client",
                  source="snapshot S1")
        written, blocked = ca.record_many(
            ["gone.example", "fresh.example"], state=ca.APPROVED,
            who="z", source="test")
        self.assertEqual(written, ["fresh.example"])
        self.assertEqual(blocked, ["gone.example"])
        self.assertFalse(ca.is_approved("gone.example"))


class SuppressionIsPerClient(ApprovalCase):

    def test_one_clients_suppression_does_not_touch_another(self):
        ca.record("shared.example", client="productive",
                  state=ca.SUPPRESSED, who="client", source="snapshot S1")
        ca.record("shared.example", client="contactout",
                  state=ca.APPROVED, who="client", source="snapshot C1")
        self.assertTrue(ca.is_suppressed("shared.example", "productive"))
        self.assertFalse(ca.is_suppressed("shared.example", "contactout"))
        self.assertTrue(ca.is_approved("shared.example", "contactout"))
        self.assertFalse(ca.is_approved("shared.example", "productive"))

    def test_approved_domains_are_scoped_to_their_client(self):
        ca.record("a.example", client="productive", state=ca.APPROVED,
                  who="z", source="test")
        ca.record("b.example", client="contactout", state=ca.APPROVED,
                  who="z", source="test")
        self.assertEqual(ca.approved_domains("productive"), {"a.example"})
        self.assertEqual(ca.approved_domains("contactout"), {"b.example"})


class EveryDecisionIsAccountable(ApprovalCase):

    def test_a_decision_without_an_actor_is_refused(self):
        with self.assertRaises(ValueError):
            ca.record("x.example", state=ca.APPROVED, who="", source="test")

    def test_a_decision_without_a_source_is_refused(self):
        with self.assertRaises(ValueError):
            ca.record("x.example", state=ca.APPROVED, who="z", source="")

    def test_a_state_outside_the_four_is_refused(self):
        with self.assertRaises(ValueError):
            ca.record("x.example", state="probably", who="z", source="test")


class ThePartitionCountsWhatItRefuses(ApprovalCase):

    def test_refused_contacts_come_back_grouped_by_reason(self):
        ca.record("yes.example", state=ca.APPROVED, who="z", source="t")
        ca.record("no.example", state=ca.SUPPRESSED, who="z", source="t")
        allowed, refused = ca.partition(
            ["a@yes.example", "b@no.example", "c@unknown.example"])
        self.assertEqual(allowed, ["a@yes.example"])
        self.assertEqual(refused[ca.SUPPRESSED], ["b@no.example"])
        self.assertEqual(refused[ca.PENDING], ["c@unknown.example"])

    def test_counts_are_per_account_not_per_row(self):
        ca.record("one.example", state=ca.PENDING, who="z", source="t")
        ca.record("one.example", state=ca.APPROVED, who="z", source="t")
        self.assertEqual(ca.counts()["approved"], 1)
        self.assertEqual(ca.counts()["pending"], 0)


class TheSnapshotDiff(ApprovalCase):

    def setUp(self):
        super().setUp()
        self.sent = ["a.example", "b.example", "c.example"]
        ca.record_snapshot("SNAP-1", self.sent)

    def test_what_came_back_is_approved(self):
        verdict = ca.diff_return("SNAP-1", ["a.example", "b.example"])
        self.assertEqual(verdict["approved"], ["a.example", "b.example"])

    def test_what_the_client_deleted_is_suppressed(self):
        verdict = ca.diff_return("SNAP-1", ["a.example", "b.example"])
        self.assertEqual(verdict["suppressed"], ["c.example"])

    def test_a_domain_we_never_sent_is_an_anomaly_and_is_not_approved(self):
        verdict = ca.diff_return("SNAP-1", ["a.example", "surprise.example"])
        self.assertEqual(verdict["anomalies"], ["surprise.example"])
        ca.apply_return("SNAP-1", ["a.example", "surprise.example"], who="z")
        self.assertFalse(ca.is_approved("surprise.example"))

    def test_applying_a_return_writes_both_halves(self):
        report = ca.apply_return("SNAP-1", ["a.example"], who="z")
        self.assertTrue(ca.is_approved("a.example"))
        self.assertTrue(ca.is_suppressed("b.example"))
        self.assertTrue(ca.is_suppressed("c.example"))
        self.assertEqual(report["sent"], 3)
        self.assertEqual(sorted(report["written_suppressed"]),
                         ["b.example", "c.example"])

    def test_the_suppression_records_which_snapshot_removed_it(self):
        ca.apply_return("SNAP-1", ["a.example"], who="z")
        row = ca.state_of("c.example")
        self.assertEqual(row["reason"],
                         "removed by client in snapshot SNAP-1")
        self.assertEqual(row["snapshot"], "SNAP-1")

    def test_a_return_with_no_recorded_snapshot_refuses(self):
        with self.assertRaises(ValueError):
            ca.diff_return("SNAP-NOPE", ["a.example"])

    def test_a_snapshot_id_is_recorded_once(self):
        with self.assertRaises(ValueError):
            ca.record_snapshot("SNAP-1", ["z.example"])

    def test_a_resaved_file_still_matches_by_content(self):
        found = ca.snapshot_matching(["C.EXAMPLE", "b.example",
                                      "www.a.example", "b.example"])
        self.assertIsNotNone(found)
        self.assertEqual(found["snapshot"], "SNAP-1")

    def test_an_empty_snapshot_is_not_a_snapshot(self):
        with self.assertRaises(ValueError):
            ca.record_snapshot("SNAP-EMPTY", [])


if __name__ == "__main__":
    unittest.main()
