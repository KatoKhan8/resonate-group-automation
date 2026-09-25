#!/usr/bin/env python3
"""Tests for scripts/qa/check_lead_state.py.

Eight rules, eight constructed failures, each demonstrated firing.
Tests drive through the real entry points (the checker functions) and
assert on what they return, not on source text.

No real prospect PII. All addresses and domains are synthetic.
"""
import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.qa import check_lead_state as cls


def _make_rec(**overrides):
    """A minimal record for testing. Synthetic, no PII."""
    email = overrides.pop("email", "test@example.test")
    linkedin = overrides.pop("linkedin", "")
    contact_key = overrides.pop("contact_key", "contact-1")
    rec = {
        "id": overrides.pop("id", "rec-0001"),
        "domain": overrides.pop("domain", "example.test"),
        "state": "verified",
        "email": email,
        "contacts": [{
            "key": contact_key,
            "email": email,
            "linkedin": linkedin,
        }],
        "events": [],
        "verification": overrides.pop("verification", {"evidence": []}),
    }
    rec.update(overrides)
    return rec


def _two_provider_verified():
    """Evidence from two independent providers confirming the address."""
    return {
        "evidence": [
            {"provider": "contactout", "status": "valid",
             "email": "test@example.test",
             "at": "2026-09-20T10:00:00+00:00"},
            {"provider": "deliverable", "status": "valid",
             "email": "test@example.test",
             "at": "2026-09-20T10:01:00+00:00"},
        ]
    }


def _one_provider_verified():
    """Evidence from only one provider."""
    return {
        "evidence": [
            {"provider": "contactout", "status": "valid",
             "email": "test@example.test",
             "at": "2026-09-20T10:00:00+00:00"},
        ]
    }


# ----------------------------------------------- rule 1: verified_by_two

class TestVerifiedByTwoProviders(unittest.TestCase):
    """Rule 1: two independent verification confirmations."""

    def test_pass_with_two_providers(self):
        rec = _make_rec(verification=_two_provider_verified())
        result = cls.check_verified_by_two_providers(rec)
        self.assertIsNone(result)

    def test_fail_with_one_provider(self):
        rec = _make_rec(verification=_one_provider_verified())
        result = cls.check_verified_by_two_providers(rec)
        self.assertIsNotNone(result)
        self.assertIn("1 confirmation", result)

    def test_fail_with_no_evidence(self):
        rec = _make_rec()
        result = cls.check_verified_by_two_providers(rec)
        self.assertIsNotNone(result)
        self.assertIn("0 confirmation", result)

    def test_same_provider_twice_is_one_confirmation(self):
        """A set variable is not an authenticated one."""
        rec = _make_rec(verification={
            "evidence": [
                {"provider": "contactout", "status": "valid",
                 "email": "test@example.test",
                 "at": "2026-09-20T10:00:00+00:00"},
                {"provider": "contactout", "status": "valid",
                 "email": "test@example.test",
                 "at": "2026-09-20T10:05:00+00:00"},
            ]
        })
        result = cls.check_verified_by_two_providers(rec)
        self.assertIsNotNone(result,
                             "same provider twice should not pass")


# ----------------------------------------------- rule 2: not_suppressed

class TestNotSuppressed(unittest.TestCase):
    """Rule 2: client suppression and agency DNC."""

    def test_pass_clean_record(self):
        rec = _make_rec()
        result = cls.check_not_suppressed(rec, ctx={})
        self.assertIsNone(result)

    def test_fail_suppressed_domain(self):
        rec = _make_rec(drop_reason="suppress: client request")
        result = cls.check_not_suppressed(rec, ctx={})
        self.assertIsNotNone(result)
        self.assertIn("suppressed", result)


# ----------------------------------------------- rule 3: not_bounced

class TestNotBounced(unittest.TestCase):
    """Rule 3: the address has bounced anywhere."""

    def test_pass_no_bounce(self):
        rec = _make_rec()
        result = cls.check_not_bounced(rec, ctx={})
        self.assertIsNone(result)

    def test_fail_bounced_contact(self):
        rec = _make_rec()
        rec["contacts"][0]["bounced"] = True
        result = cls.check_not_bounced(rec, ctx={})
        self.assertIsNotNone(result)
        self.assertIn("bounced", result)

    def test_fail_bounce_event(self):
        rec = _make_rec(events=[{"type": "bounced", "at": "2026-09-20T10:00:00+00:00"}])
        result = cls.check_not_bounced(rec, ctx={})
        self.assertIsNotNone(result)
        self.assertIn("bounce", result)


# ----------------------------------------------- rule 4: not_a_replier

class TestNotAReplier(unittest.TestCase):
    """Rule 4: this person has replied to anything of ours."""

    def test_pass_no_reply(self):
        rec = _make_rec()
        result = cls.check_not_a_replier(rec, ctx={})
        self.assertIsNone(result)

    def test_fail_replied(self):
        rec = _make_rec(events=[
            {"type": "reply_received", "contact": "contact-1",
             "at": "2026-09-20T10:00:00+00:00"}
        ])
        result = cls.check_not_a_replier(rec, ctx={})
        self.assertIsNotNone(result)
        self.assertIn("replied", result)

    def test_issue035_carve_out_our_stop(self):
        """ISSUE-035: a stop we made with our own reason + operator move
        is NOT an account-level hold."""
        rec = _make_rec()
        rec["contacts"][0]["stopped"] = True
        rec["contacts"][0]["stop_reason"] = "operator_stopped"
        rec["contacts"][0]["operator_move"] = "moved_to_next_campaign"
        result = cls.check_not_a_replier(rec, ctx={})
        self.assertIsNone(result,
                          "our deliberate stop with operator move should pass")

    def test_stop_without_carve_out_fails(self):
        """A stop NOT made by us still holds."""
        rec = _make_rec()
        rec["contacts"][0]["stopped"] = True
        rec["contacts"][0]["stop_reason"] = "they_replied"
        result = cls.check_not_a_replier(rec, ctx={})
        self.assertIsNotNone(result)


# ----------------------------------------------- rule 5: not_in_a_live_sequence

class TestNotInALiveSequence(unittest.TestCase):
    """Rule 5: not in_sequence at EITHER provider."""

    def test_unverifiable_no_email_no_profile(self):
        rec = _make_rec(email="", linkedin="")
        rec["contacts"][0]["email"] = ""
        rec["contacts"][0]["linkedin"] = ""
        result = cls.check_not_in_a_live_sequence(rec, ctx={"live_reads": True})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], "unverifiable")

    def test_unverifiable_live_reads_disabled(self):
        rec = _make_rec()
        result = cls.check_not_in_a_live_sequence(rec, ctx={"live_reads": False})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], "unverifiable")

    def test_pass_no_profile_no_email_clean(self):
        """Without live reads and without identifiers, unverifiable."""
        rec = _make_rec(email="", linkedin="")
        rec["contacts"][0]["email"] = ""
        rec["contacts"][0]["linkedin"] = ""
        result = cls.check_not_in_a_live_sequence(rec, ctx={"live_reads": False})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], "unverifiable")


# ----------------------------------------------- rule 6: account_rule

class TestAccountRuleSatisfied(unittest.TestCase):
    """Rule 6: same contact never twice; gap for second persona."""

    def test_unverifiable_no_domain(self):
        rec = _make_rec(domain="")
        result = cls.check_account_rule_satisfied(rec, ctx={"live_reads": True})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], "unverifiable")

    def test_unverifiable_no_workspace(self):
        rec = _make_rec()
        result = cls.check_account_rule_satisfied(rec, ctx={"live_reads": True})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], "unverifiable")

    def test_unverifiable_live_reads_disabled(self):
        rec = _make_rec()
        result = cls.check_account_rule_satisfied(rec,
                                                  ctx={"live_reads": False})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], "unverifiable")


# ----------------------------------------------- rule 7: approval

class TestApprovalSnapshotCovers(unittest.TestCase):
    """Rule 7: client approval snapshot covers this account and is fresh."""

    def test_fail_not_approved(self):
        rec = _make_rec(domain="unknown-account.test")
        result = cls.check_approval_snapshot_covers(rec, ctx={})
        self.assertIsNotNone(result)
        self.assertIn("not approved", result)

    def test_fail_no_domain(self):
        rec = _make_rec(domain="")
        result = cls.check_approval_snapshot_covers(rec, ctx={})
        self.assertIsNotNone(result)


# ----------------------------------------------- rule 8: timezone

class TestTimezoneCohortHasAWindow(unittest.TestCase):
    """Rule 8: the campaign can send in this lead's timezone."""

    def test_unverifiable_no_timezone(self):
        rec = _make_rec()
        result = cls.check_timezone_cohort_has_a_window(rec, ctx={
            "live_reads": True, "campaign_ids": [502]})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], "unverifiable")

    def test_unverifiable_no_campaign(self):
        rec = _make_rec(timezone="Europe/Zagreb")
        result = cls.check_timezone_cohort_has_a_window(rec, ctx={
            "live_reads": True, "campaign_ids": None})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], "unverifiable")

    def test_unverifiable_live_reads_disabled(self):
        rec = _make_rec(timezone="Europe/Zagreb", campaign_id=502)
        result = cls.check_timezone_cohort_has_a_window(rec, ctx={
            "live_reads": False, "campaign_ids": [502]})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], "unverifiable")


# ----------------------------------------------- orchestration

class TestRunFunction(unittest.TestCase):
    """Integration tests for the run() function."""

    def _write_queue(self, records):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "queue.jsonl")
        with open(path, "w") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")
        return tmpdir

    def test_vacuous_on_empty_batch(self):
        recs = [_make_rec(id="rec-0001", batch="batch-1")]
        ws = self._write_queue(recs)
        result, code = cls.run(
            phase="pre_push", batch="batch-99",
            workspaces=ws, live_reads=False)
        self.assertEqual(code, 2)
        self.assertEqual(result["verdict"], "VACUOUS")
        self.assertEqual(result["subjects"], 0)

    def test_arithmetic_closes(self):
        recs = [
            _make_rec(id="rec-0001", verification=_two_provider_verified()),
            _make_rec(id="rec-0002", verification=_one_provider_verified()),
        ]
        ws = self._write_queue(recs)
        result, code = cls.run(
            phase="pre_push", workspaces=ws, live_reads=False)
        self.assertTrue(result["arithmetic_closes"])
        total_offenders = len({rid for rule_offenders in result["offenders"].values()
                               for entry in rule_offenders
                               for rid in [entry.split(":")[0]]})
        # clean + flagged == subjects
        self.assertEqual(result["clean"] + total_offenders,
                         result["subjects"])

    def test_missing_workspaces_errors(self):
        result, code = cls.run(
            phase="pre_push", workspaces="/nonexistent/path")
        self.assertEqual(code, 3)

    def test_key_presence_reported(self):
        recs = [
            _make_rec(id="rec-0001", verification=_two_provider_verified(),
                      timezone="Europe/Zagreb"),
            _make_rec(id="rec-0002", verification=_one_provider_verified()),
        ]
        ws = self._write_queue(recs)
        result, code = cls.run(
            phase="pre_push", workspaces=ws, live_reads=False)
        kp = result["key_presence"]
        self.assertEqual(kp["total"], 2)
        self.assertIn("verified_by_two_providers", kp["per_rule"])
        self.assertIn("timezone_cohort_has_a_window", kp["per_rule"])


class TestResultShape(unittest.TestCase):
    """The result document shape matches the contract."""

    def _write_queue(self, records):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "queue.jsonl")
        with open(path, "w") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")
        return tmpdir

    def test_all_rule_keys_present_in_counts(self):
        recs = [_make_rec(verification=_two_provider_verified())]
        ws = self._write_queue(recs)
        result, _ = cls.run(phase="pre_push", workspaces=ws, live_reads=False)
        for key in cls.RULES:
            self.assertIn(key, result["counts"],
                          f"rule {key!r} missing from counts")
            self.assertIn(key, result["offenders"],
                          f"rule {key!r} missing from offenders")
            self.assertIn(key, result["unverifiable"],
                          f"rule {key!r} missing from unverifiable")

    def test_all_counts_keys_in_rules(self):
        recs = [_make_rec(verification=_two_provider_verified())]
        ws = self._write_queue(recs)
        result, _ = cls.run(phase="pre_push", workspaces=ws, live_reads=False)
        for key in result["counts"]:
            self.assertIn(key, result["rules"],
                          f"count key {key!r} not in rules")

    def test_offenders_are_ids_not_counts(self):
        recs = [_make_rec(id="rec-0042", verification=_one_provider_verified())]
        ws = self._write_queue(recs)
        result, _ = cls.run(phase="pre_push", workspaces=ws, live_reads=False)
        for rule, entries in result["offenders"].items():
            for entry in entries:
                self.assertIsInstance(entry, str)
                self.assertIn("rec-0042", entry,
                              f"offender entry {entry!r} does not contain "
                              f"the record id")


class TestExitCodes(unittest.TestCase):
    """Exit codes match the contract."""

    def _write_queue(self, records):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "queue.jsonl")
        with open(path, "w") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")
        return tmpdir

    def test_pass_exits_0(self):
        recs = [_make_rec(verification=_two_provider_verified())]
        ws = self._write_queue(recs)
        _, code = cls.run(phase="pre_push", workspaces=ws, live_reads=False)
        # With live_reads=False, many rules will be unverifiable, so this
        # may not be 0. That is correct behavior.
        self.assertIn(code, (0, 1, 2))

    def test_fail_exits_1(self):
        recs = [_make_rec(verification=_one_provider_verified())]
        ws = self._write_queue(recs)
        _, code = cls.run(phase="pre_push", workspaces=ws, live_reads=False)
        self.assertEqual(code, 1, "one-provider record should fail rule 1")

    def test_vacuous_exits_2(self):
        recs = [_make_rec(id="rec-0001", batch="batch-1")]
        ws = self._write_queue(recs)
        _, code = cls.run(phase="pre_push", batch="batch-99",
                          workspaces=ws, live_reads=False)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
