"""The per-lead eligibility and state check: eight rules, each demonstrated.

TASK-293. Tests that a lead eligible in our store can still be in_sequence
at the provider — and that the check catches every reason it must not be
mailed, from either provider.

Each rule gets a constructed failure showing it firing. A rule nobody has
seen fire is indistinguishable from a rule that cannot.
"""
import datetime
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from scripts.qa import check_lead_state as cls
from src import verification


def _make_contact(key="test-contact", email="test@example.test",
                  sendable=True, linkedin=None):
    """A contact with real verification evidence."""
    person = {
        "key": key, "name": "Test Person", "email": email,
        "title": "Test Title",
        "linkedin": linkedin or "https://www.linkedin.com/in/test-person",
    }
    if sendable:
        evidence = [
            verification.result("contactout", verification.S_VALID, email),
            verification.result("deliverable", verification.S_VALID, email),
        ]
    else:
        evidence = [
            verification.result("contactout", verification.S_ACCEPT_ALL,
                                email, catch_all=True),
        ]
    verification.apply(person, verification.decide(evidence), evidence)
    return person


def _make_record(rec_id="rec-001", domain="example.test",
                 email="test@example.test", sendable=True,
                 linkedin=None, timezone=None, batch=None):
    """A record with one contact, suitable for the check."""
    contact = _make_contact(email=email, sendable=sendable, linkedin=linkedin)
    rec = {
        "id": rec_id,
        "domain": domain,
        "state": "approved",
        "contacts": [contact],
        "events": [],
    }
    if timezone:
        rec["timezone"] = timezone
    if batch:
        rec["batch"] = batch
    return rec


def _write_workspaces(records, base_dir=None):
    """Write records to a temp work/ copy and return its path."""
    if base_dir is None:
        base_dir = tempfile.mkdtemp(prefix="qa-test-")
    work_dir = os.path.join(base_dir, "work")
    os.makedirs(work_dir, exist_ok=True)
    path = os.path.join(work_dir, "queue.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    return base_dir


class TestRuleOneVerifiedByTwoProviders(unittest.TestCase):
    """Rule 1: verified_by_two_providers."""

    def test_two_confirmations_pass(self):
        rec = _make_record(sendable=True)
        contact = rec["contacts"][0]
        result = cls.check_verified(rec, contact)
        self.assertIsNone(result)

    def test_one_confirmation_fires(self):
        rec = _make_record(sendable=False)
        contact = rec["contacts"][0]
        result = cls.check_verified(rec, contact)
        self.assertIsNotNone(result)
        self.assertEqual(result["confirmation_count"], 0)

    def test_no_evidence_fires(self):
        rec = _make_record()
        contact = rec["contacts"][0]
        contact["verification"] = {"evidence": []}
        contact.pop("verdict", None)
        contact.pop("reoon", None)
        result = cls.check_verified(rec, contact)
        self.assertIsNotNone(result)
        self.assertEqual(result["confirmation_count"], 0)


class TestRuleTwoNotSuppressed(unittest.TestCase):
    """Rule 2: not_suppressed."""

    def test_clean_domain_passes(self):
        rec = _make_record()
        contact = rec["contacts"][0]
        result = cls.check_not_suppressed(rec, contact, agency_index={})
        self.assertIsNone(result)

    def test_client_suppressed_fires(self):
        rec = _make_record()
        rec["drop_reason"] = "suppress: client request"
        result = cls.check_not_suppressed(rec, rec["contacts"][0],
                                          agency_index={})
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "client_suppressed_drop")

    def test_agency_dnc_fires(self):
        from src import agencydnc
        rec = _make_record()
        contact = rec["contacts"][0]
        digest = agencydnc.fingerprint("email", contact["email"])
        fake_index = {digest: {"reason": "requested", "at": "now"}}
        result = cls.check_not_suppressed(rec, contact, agency_index=fake_index)
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "agency_dnc")


class TestRuleThreeNotBounced(unittest.TestCase):
    """Rule 3: not_bounced."""

    def test_no_bounce_passes(self):
        rec = _make_record()
        contact = rec["contacts"][0]
        result = cls.check_not_bounced(rec, contact, bison_lead=None)
        self.assertIsNone(result)

    def test_bounced_lead_fires(self):
        rec = _make_record()
        contact = rec["contacts"][0]
        fake_lead = {"status": "bounced", "id": 123}
        result = cls.check_not_bounced(rec, contact, bison_lead=fake_lead)
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "emailbison")

    def test_local_bounce_event_fires(self):
        rec = _make_record()
        rec["events"] = [{"type": "bounce", "contact": "test-contact"}]
        result = cls.check_not_bounced(rec, rec["contacts"][0], bison_lead=None)
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "local_events")


class TestRuleFourNotAReplier(unittest.TestCase):
    """Rule 4: not_a_replier.

    ISSUE-035 carve-out: a stop carrying OUR OWN reason plus an
    operator-recorded move is NOT an account-level hold.
    """

    def test_no_reply_passes(self):
        rec = _make_record()
        contact = rec["contacts"][0]
        result = cls.check_not_a_replier(rec, contact)
        self.assertIsNone(result)

    def test_reply_event_fires(self):
        rec = _make_record()
        rec["events"] = [{"type": "reply_received",
                          "contact": "test-contact",
                          "at": "2026-09-25T10:00:00Z"}]
        result = cls.check_not_a_replier(rec, rec["contacts"][0])
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "replied")

    def test_unsubscribed_contact_fires(self):
        rec = _make_record()
        rec["contacts"][0]["unsubscribed"] = True
        result = cls.check_not_a_replier(rec, rec["contacts"][0])
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "unsubscribed_or_suppressed")

    def test_our_own_stop_is_not_a_reply(self):
        """ISSUE-035: a deliberate stop by us is NOT an account-level hold.

        A stop carrying our own reason plus an operator-recorded move must
        not read to the collision gate as a reply. The contact's stopped
        flag is set by us deliberately, and this rule must not fire on it
        alone — only a reply event fires this rule.
        """
        rec = _make_record()
        rec["contacts"][0]["stopped"] = True
        rec["contacts"][0]["stop_reason"] = "operator_move"
        result = cls.check_not_a_replier(rec, rec["contacts"][0])
        self.assertIsNone(result,
                          "a deliberate stop by us must not read as a reply")


class TestRuleFiveNotInALiveSequence(unittest.TestCase):
    """Rule 5: not_in_a_live_sequence — BOTH providers.

    KEY PRESENCE: Zero contacts carry heyreach_lead_id (ISSUE-041).
    This rule keys on profile_url for HeyReach and email for EmailBison.
    """

    @mock.patch.object(cls.bison, "find_lead_by_email")
    @mock.patch.object(cls.heyreach, "campaigns_for_lead")
    def test_clean_at_both_passes(self, mock_hr, mock_bison):
        mock_bison.return_value = {
            "id": 1, "status": "normal",
            "lead_campaign_data": [
                {"campaign_id": 100, "status": "sequence_finished",
                 "emails_sent": 5},
            ],
        }
        mock_hr.return_value = ([], 0)
        rec = _make_record()
        contact = rec["contacts"][0]
        reads = []
        result = cls.check_not_in_a_live_sequence(
            rec, contact, provider_reads=reads)
        self.assertIsNone(result)
        self.assertEqual(len(reads), 2)

    @mock.patch.object(cls.bison, "find_lead_by_email")
    @mock.patch.object(cls.heyreach, "campaigns_for_lead")
    def test_bison_in_sequence_fires(self, mock_hr, mock_bison):
        mock_bison.return_value = {
            "id": 1, "status": "normal",
            "lead_campaign_data": [
                {"campaign_id": 100, "status": "in_sequence",
                 "emails_sent": 2},
            ],
        }
        mock_hr.return_value = ([], 0)
        rec = _make_record()
        contact = rec["contacts"][0]
        result = cls.check_not_in_a_live_sequence(
            rec, contact, provider_reads=[])
        self.assertIsNotNone(result)
        self.assertTrue(result["in_sequence"])

    @mock.patch.object(cls.bison, "find_lead_by_email")
    @mock.patch.object(cls.heyreach, "campaigns_for_lead")
    def test_heyreach_active_campaign_fires(self, mock_hr, mock_bison):
        mock_bison.return_value = None
        mock_hr.return_value = ([{
            "campaignId": 200,
            "campaignName": "Client Campaign",
            "campaignStatus": "active",
            "leadStatus": "InSequence",
            "creationTime": "2026-09-20",
        }], 1)
        rec = _make_record()
        contact = rec["contacts"][0]
        result = cls.check_not_in_a_live_sequence(
            rec, contact, provider_reads=[])
        self.assertIsNotNone(result)
        self.assertTrue(result["in_sequence"])

    def test_no_profile_url_is_unverifiable(self):
        """ISSUE-041: a rule whose key is absent is UNVERIFIABLE, not clean."""
        rec = _make_record()
        rec["contacts"][0]["linkedin"] = ""
        rec["contacts"][0].pop("linkedin", None)
        with mock.patch.object(cls.bison, "find_lead_by_email",
                               return_value=None):
            result = cls.check_not_in_a_live_sequence(
                rec, rec["contacts"][0], provider_reads=[])
        self.assertEqual(result, "UNVERIFIABLE")


class TestRuleSixAccountRuleSatisfied(unittest.TestCase):
    """Rule 6: account_rule_satisfied."""

    @mock.patch.object(cls.collision, "check_account")
    @mock.patch.object(cls.collision, "account_policy")
    def test_allow_passes(self, mock_policy, mock_check):
        mock_check.return_value = {"verdict": "clear", "leads": 0}
        mock_policy.return_value = (cls.collision.ALLOW, "no prior contact")
        rec = _make_record()
        result = cls.check_account_rule(rec, rec["contacts"][0],
                                        provider_reads=[])
        self.assertIsNone(result)

    @mock.patch.object(cls.collision, "check_account")
    @mock.patch.object(cls.collision, "account_policy")
    def test_stop_fires(self, mock_policy, mock_check):
        mock_check.return_value = {
            "verdict": "in_sequence", "leads": 1,
            "anyone_in_sequence": True, "people": [
                {"in_sequence": True, "emails_sent": 5, "replies": 0,
                 "campaigns": [{"status": "in_sequence"}]},
            ],
        }
        mock_policy.return_value = (
            cls.collision.STOP,
            "somebody at this account is mid-sequence right now")
        rec = _make_record()
        result = cls.check_account_rule(rec, rec["contacts"][0],
                                        provider_reads=[])
        self.assertIsNotNone(result)
        self.assertEqual(result["verdict"], "stop")


class TestRuleSevenApprovalSnapshotCovers(unittest.TestCase):
    """Rule 7: approval_snapshot_covers."""

    @mock.patch.object(cls.clientapproval, "state_of")
    def test_approved_fresh_passes(self, mock_state):
        now = datetime.datetime.now(datetime.timezone.utc)
        mock_state.return_value = {
            "state": "approved",
            "at": now.isoformat(),
            "domain": "example.test",
        }
        rec = _make_record()
        result = cls.check_approval_snapshot(rec, rec["contacts"][0])
        self.assertIsNone(result)

    @mock.patch.object(cls.clientapproval, "state_of")
    def test_no_record_fires(self, mock_state):
        mock_state.return_value = None
        rec = _make_record()
        result = cls.check_approval_snapshot(rec, rec["contacts"][0])
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "no_approval_record")

    @mock.patch.object(cls.clientapproval, "state_of")
    def test_pending_fires(self, mock_state):
        mock_state.return_value = {
            "state": "pending", "at": "2026-09-25T00:00:00Z",
            "domain": "example.test",
        }
        rec = _make_record()
        result = cls.check_approval_snapshot(rec, rec["contacts"][0])
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "state_is_pending")

    @mock.patch.object(cls.clientapproval, "state_of")
    def test_stale_approval_fires(self, mock_state):
        old = (datetime.datetime.now(datetime.timezone.utc)
               - datetime.timedelta(days=45)).isoformat()
        mock_state.return_value = {
            "state": "approved", "at": old, "domain": "example.test",
        }
        rec = _make_record()
        result = cls.check_approval_snapshot(rec, rec["contacts"][0])
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "approval_stale")


class TestRuleEightTimezoneCohortHasAWindow(unittest.TestCase):
    """Rule 8: timezone_cohort_has_a_window.

    ISSUE-045: every EmailBison campaign is 09:00-17:00 Mon-Fri in its
    own timezone. This check SHOULD FAIL for out-of-hours cohorts.
    """

    @mock.patch.object(cls.bison, "schedule")
    def test_inside_window_passes(self, mock_sched):
        now = datetime.datetime.now(datetime.timezone.utc)
        today = cls._weekday_name(now.weekday())
        mock_sched.return_value = {
            "days": [today.capitalize()],
            "start": "00:00",
            "end": "23:59",
            "timezone": "UTC",
        }
        rec = _make_record(timezone="UTC")
        result = cls.check_timezone_window(
            rec, rec["contacts"][0], campaign_ids=[502], provider_reads=[])
        self.assertIsNone(result)

    @mock.patch.object(cls.bison, "schedule")
    def test_outside_window_fires(self, mock_sched):
        mock_sched.return_value = {
            "days": ["Monday", "Tuesday", "Wednesday", "Thursday",
                     "Friday", "Saturday", "Sunday"],
            "start": "03:00",
            "end": "04:00",
            "timezone": "UTC",
        }
        rec = _make_record(timezone="UTC")
        result = cls.check_timezone_window(
            rec, rec["contacts"][0], campaign_ids=[502], provider_reads=[])
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "outside_window")

    @mock.patch.object(cls.bison, "schedule")
    def test_wrong_day_fires(self, mock_sched):
        now = datetime.datetime.now(datetime.timezone.utc)
        today = cls._weekday_name(now.weekday())
        all_days = ["monday", "tuesday", "wednesday", "thursday",
                    "friday", "saturday", "sunday"]
        other_days = [d for d in all_days if d != today][:5]
        mock_sched.return_value = {
            "days": other_days,
            "start": "00:00",
            "end": "23:59",
            "timezone": "UTC",
        }
        rec = _make_record(timezone="UTC")
        result = cls.check_timezone_window(
            rec, rec["contacts"][0], campaign_ids=[502], provider_reads=[])
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "wrong_day")

    def test_no_timezone_is_unverifiable(self):
        """A guessed timezone is worse than a missing one."""
        rec = _make_record()
        rec.pop("timezone", None)
        result = cls.check_timezone_window(
            rec, rec["contacts"][0], campaign_ids=[502], provider_reads=[])
        self.assertEqual(result, "UNVERIFIABLE")


class TestArithmeticCloses(unittest.TestCase):
    """The arithmetic: clean + |offenders ∪ unverifiable| == subjects."""

    def test_all_clean(self):
        rec = _make_record(sendable=True)
        ws = _write_workspaces([rec])
        try:
            with mock.patch.object(cls.bison, "find_lead_by_email",
                                   return_value=None), \
                 mock.patch.object(cls.heyreach, "campaigns_for_lead",
                                   return_value=([], 0)), \
                 mock.patch.object(cls.collision, "check_account",
                                   return_value={"verdict": "clear"}), \
                 mock.patch.object(cls.collision, "account_policy",
                                   return_value=(cls.collision.ALLOW, "ok")), \
                 mock.patch.object(cls.clientapproval, "state_of",
                                   return_value={
                                       "state": "approved",
                                       "at": datetime.datetime.now(
                                           datetime.timezone.utc).isoformat(),
                                       "domain": "example.test",
                                   }), \
                 mock.patch.object(cls.bison, "schedule",
                                   return_value={
                                       "days": ["Monday", "Tuesday",
                                                "Wednesday", "Thursday",
                                                "Friday", "Saturday",
                                                "Sunday"],
                                       "start": "00:00",
                                       "end": "23:59",
                                       "timezone": "UTC",
                                   }):
                result = cls.run(workspaces=os.path.join(ws, "work"),
                                 campaigns=[502])
            self.assertTrue(result["arithmetic_closes"])
            self.assertEqual(result["subjects"], 1)
            self.assertGreaterEqual(result["clean"], 0)
        finally:
            shutil.rmtree(ws, ignore_errors=True)

    def test_one_offender_arithmetic(self):
        rec = _make_record(sendable=False)
        ws = _write_workspaces([rec])
        try:
            with mock.patch.object(cls.bison, "find_lead_by_email",
                                   return_value=None), \
                 mock.patch.object(cls.heyreach, "campaigns_for_lead",
                                   return_value=([], 0)), \
                 mock.patch.object(cls.collision, "check_account",
                                   return_value={"verdict": "clear"}), \
                 mock.patch.object(cls.collision, "account_policy",
                                   return_value=(cls.collision.ALLOW, "ok")), \
                 mock.patch.object(cls.clientapproval, "state_of",
                                   return_value={
                                       "state": "approved",
                                       "at": datetime.datetime.now(
                                           datetime.timezone.utc).isoformat(),
                                       "domain": "example.test",
                                   }), \
                 mock.patch.object(cls.bison, "schedule",
                                   return_value={
                                       "days": ["Monday", "Tuesday",
                                                "Wednesday", "Thursday",
                                                "Friday", "Saturday",
                                                "Sunday"],
                                       "start": "00:00",
                                       "end": "23:59",
                                       "timezone": "UTC",
                                   }):
                result = cls.run(workspaces=os.path.join(ws, "work"),
                                 campaigns=[502])
            self.assertTrue(result["arithmetic_closes"])
            self.assertGreater(result["counts"]["verified_by_two_providers"], 0)
        finally:
            shutil.rmtree(ws, ignore_errors=True)


class TestVacuous(unittest.TestCase):
    """subjects == 0 exits 2 with a stated reason."""

    def test_empty_batch_is_vacuous(self):
        ws = _write_workspaces([])
        try:
            result = cls.run(workspaces=os.path.join(ws, "work"))
            self.assertEqual(result["verdict"], "VACUOUS")
            self.assertEqual(result["subjects"], 0)
            self.assertTrue(result["refused"])
        finally:
            shutil.rmtree(ws, ignore_errors=True)


class TestKeyPresence(unittest.TestCase):
    """Key presence per rule: how many of N carried the field it keys on."""

    def test_reports_presence_per_rule(self):
        rec = _make_record()
        contact = rec["contacts"][0]
        kp = cls._key_presence(rec, contact)
        self.assertIn("not_in_a_live_sequence", kp)
        self.assertTrue(kp["not_in_a_live_sequence"]["present"])
        self.assertTrue(kp["not_in_a_live_sequence"]["email_present"])

    def test_missing_profile_reported(self):
        rec = _make_record()
        rec["contacts"][0].pop("linkedin", None)
        contact = rec["contacts"][0]
        kp = cls._key_presence(rec, contact)
        self.assertFalse(
            kp["not_in_a_live_sequence"]["profile_present"])


class TestResultShape(unittest.TestCase):
    """The result document conforms to the contract."""

    def test_every_rule_in_rules_appears_in_counts(self):
        ws = _write_workspaces([_make_record()])
        try:
            with mock.patch.object(cls.bison, "find_lead_by_email",
                                   return_value=None), \
                 mock.patch.object(cls.heyreach, "campaigns_for_lead",
                                   return_value=([], 0)), \
                 mock.patch.object(cls.collision, "check_account",
                                   return_value={"verdict": "clear"}), \
                 mock.patch.object(cls.collision, "account_policy",
                                   return_value=(cls.collision.ALLOW, "ok")), \
                 mock.patch.object(cls.clientapproval, "state_of",
                                   return_value={
                                       "state": "approved",
                                       "at": datetime.datetime.now(
                                           datetime.timezone.utc).isoformat(),
                                       "domain": "example.test",
                                   }), \
                 mock.patch.object(cls.bison, "schedule",
                                   return_value={
                                       "days": ["Monday", "Tuesday",
                                                "Wednesday", "Thursday",
                                                "Friday", "Saturday",
                                                "Sunday"],
                                       "start": "00:00",
                                       "end": "23:59",
                                       "timezone": "UTC",
                                   }):
                result = cls.run(workspaces=os.path.join(ws, "work"),
                                 campaigns=[502])
            for rule in result["rules"]:
                self.assertIn(rule, result["counts"])
                self.assertIn(rule, result["offenders"])
                self.assertIn(rule, result["unverifiable"])
        finally:
            shutil.rmtree(ws, ignore_errors=True)

    def test_verdict_is_one_of_the_five(self):
        ws = _write_workspaces([_make_record()])
        try:
            with mock.patch.object(cls.bison, "find_lead_by_email",
                                   return_value=None), \
                 mock.patch.object(cls.heyreach, "campaigns_for_lead",
                                   return_value=([], 0)), \
                 mock.patch.object(cls.collision, "check_account",
                                   return_value={"verdict": "clear"}), \
                 mock.patch.object(cls.collision, "account_policy",
                                   return_value=(cls.collision.ALLOW, "ok")), \
                 mock.patch.object(cls.clientapproval, "state_of",
                                   return_value={
                                       "state": "approved",
                                       "at": datetime.datetime.now(
                                           datetime.timezone.utc).isoformat(),
                                       "domain": "example.test",
                                   }), \
                 mock.patch.object(cls.bison, "schedule",
                                   return_value={
                                       "days": ["Monday", "Tuesday",
                                                "Wednesday", "Thursday",
                                                "Friday", "Saturday",
                                                "Sunday"],
                                       "start": "00:00",
                                       "end": "23:59",
                                       "timezone": "UTC",
                                   }):
                result = cls.run(workspaces=os.path.join(ws, "work"),
                                 campaigns=[502])
            self.assertIn(result["verdict"],
                          ("PASS", "FAIL", "UNCONFIRMED", "VACUOUS", "ERROR"))
        finally:
            shutil.rmtree(ws, ignore_errors=True)


class TestExitCodes(unittest.TestCase):
    """Exit codes: 0=PASS, 1=FAIL, 2=UNCONFIRMED/VACUOUS, 3=ERROR."""

    def test_pass_is_zero(self):
        self.assertEqual(cls._exit_code("PASS"), 0)

    def test_fail_is_one(self):
        self.assertEqual(cls._exit_code("FAIL"), 1)

    def test_unconfirmed_is_two(self):
        self.assertEqual(cls._exit_code("UNCONFIRMED"), 2)

    def test_vacuous_is_two(self):
        self.assertEqual(cls._exit_code("VACUOUS"), 2)

    def test_error_is_three(self):
        self.assertEqual(cls._exit_code("ERROR"), 3)


if __name__ == "__main__":
    unittest.main()
