"""Tests for scripts/qa/check_lead_state.py — TASK-293.

Eight rules, eight constructed failures, each with the offending id and
the message. A rule nobody has seen fire is indistinguishable from a rule
that cannot.

The arithmetic must close: clean + |offenders ∪ unverifiable| == subjects.
subjects == 0 exits VACUOUS.

Key presence is reported per rule. A rule whose key is present on 0
subjects is VACUOUS for those subjects (ISSUE-041).

No fixtures with real PII. test_fixture_hygiene guards this.
"""
import datetime
import json
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.qa import check_lead_state
from scripts.qa import PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR
from src import collision


# ------------------------------------------------------------- helpers

def _make_rec(rec_id="rec-001", domain="acme.test", email="jane@acme.test",
              contact_key="jane", timezone=None, client="productive",
              events=None, contacts_extra=None, drop_reason=None,
              suppression=None, campaign_ids=None):
    """Build a minimal queue record for testing."""
    contact = {
        "key": contact_key,
        "email": email,
    }
    if contacts_extra:
        contact.update(contacts_extra)
    rec = {
        "id": rec_id,
        "domain": domain,
        "client": client,
        "contacts": [contact],
        "events": events or [],
    }
    if timezone:
        rec["timezone"] = timezone
    if drop_reason:
        rec["drop_reason"] = drop_reason
    if suppression:
        rec["suppression"] = suppression
    return rec


def _make_campaign(bison_id=502, record_ids=None):
    """Build a minimal campaign row."""
    return {
        "bison_campaign_id": bison_id,
        "record_ids": record_ids or [],
    }


# ------------------------------------------------------------- rule 1

class TestVerifiedByTwoProviders(unittest.TestCase):
    """Rule 1: two independent verification confirmations."""

    def test_pass_with_two_confirmations(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        contact["verification"] = {
            "evidence": [
                {"provider": "contactout", "status": "valid",
                 "email": "jane@acme.test"},
                {"provider": "deliverable", "status": "valid",
                 "email": "jane@acme.test"},
            ]
        }
        result = check_lead_state.check_verified_by_two_providers(rec, contact)
        self.assertEqual(result["verdict"], PASS)
        self.assertEqual(result["offenders"], [])

    def test_fail_with_one_confirmation(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        contact["verification"] = {
            "evidence": [
                {"provider": "contactout", "status": "valid",
                 "email": "jane@acme.test"},
            ]
        }
        result = check_lead_state.check_verified_by_two_providers(rec, contact)
        self.assertEqual(result["verdict"], FAIL)
        self.assertEqual(len(result["offenders"]), 1)
        self.assertIn("rec-001", result["offenders"][0])

    def test_fail_with_no_email(self):
        rec = _make_rec(email="")
        contact = rec["contacts"][0]
        result = check_lead_state.check_verified_by_two_providers(rec, contact)
        self.assertEqual(result["verdict"], FAIL)
        self.assertIn("no email", result["details"]["reason"])

    def test_one_provider_answering_twice_is_one_confirmation(self):
        """A set variable is not an authenticated one."""
        rec = _make_rec()
        contact = rec["contacts"][0]
        contact["verification"] = {
            "evidence": [
                {"provider": "contactout", "status": "valid",
                 "email": "jane@acme.test"},
                {"provider": "contactout", "status": "valid",
                 "email": "jane@acme.test"},
            ]
        }
        result = check_lead_state.check_verified_by_two_providers(rec, contact)
        self.assertEqual(result["verdict"], FAIL)
        self.assertEqual(result["key_presence"]["confirmation_count"], 1)


# ------------------------------------------------------------- rule 2

class TestNotSuppressed(unittest.TestCase):
    """Rule 2: not on client suppression or agency DNC."""

    def test_pass_when_clean(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        result = check_lead_state.check_not_suppressed(
            rec, contact, agency_index={})
        self.assertEqual(result["verdict"], PASS)

    def test_fail_on_client_suppression(self):
        rec = _make_rec(drop_reason="suppress:client_request")
        contact = rec["contacts"][0]
        result = check_lead_state.check_not_suppressed(
            rec, contact, agency_index={})
        self.assertEqual(result["verdict"], FAIL)
        self.assertIn("client_suppressed", result["details"]["reason"])

    def test_fail_on_unsubscribed(self):
        rec = _make_rec(suppression={"unsubscribed": True})
        contact = rec["contacts"][0]
        result = check_lead_state.check_not_suppressed(
            rec, contact, agency_index={})
        self.assertEqual(result["verdict"], FAIL)


# ------------------------------------------------------------- rule 3

class TestNotBounced(unittest.TestCase):
    """Rule 3: the address has not bounced anywhere."""

    def test_pass_when_clean(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        result = check_lead_state.check_not_bounced(rec, contact)
        self.assertEqual(result["verdict"], PASS)

    def test_fail_on_bounce_event(self):
        rec = _make_rec(events=[
            {"type": "email_bounced", "contact": "jane",
             "email": "jane@acme.test"}
        ])
        contact = rec["contacts"][0]
        result = check_lead_state.check_not_bounced(rec, contact)
        self.assertEqual(result["verdict"], FAIL)
        self.assertIn("bounced", result["details"]["reason"])

    def test_fail_on_contact_marked_bounced(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        contact["bounced"] = True
        result = check_lead_state.check_not_bounced(rec, contact)
        self.assertEqual(result["verdict"], FAIL)


# ------------------------------------------------------------- rule 4

class TestNotAReplier(unittest.TestCase):
    """Rule 4: this person has not replied."""

    def test_pass_when_clean(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        result = check_lead_state.check_not_a_replier(rec, contact)
        self.assertEqual(result["verdict"], PASS)

    def test_fail_on_reply_event(self):
        rec = _make_rec(events=[
            {"type": "reply_received", "contact": "jane",
             "email": "jane@acme.test"}
        ])
        contact = rec["contacts"][0]
        result = check_lead_state.check_not_a_replier(rec, contact)
        self.assertEqual(result["verdict"], FAIL)
        self.assertIn("replied", result["details"]["reason"])

    def test_fail_on_stopped_contact(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        contact["stopped"] = True
        result = check_lead_state.check_not_a_replier(rec, contact)
        self.assertEqual(result["verdict"], FAIL)


# ------------------------------------------------------------- rule 5

class TestNotInALiveSequence(unittest.TestCase):
    """Rule 5: not in_sequence at EITHER provider."""

    def test_pass_when_clear_at_both(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        contact["linkedin"] = "https://linkedin.com/in/jane"
        camps = [_make_campaign()]

        def fake_bison(email):
            return {"id": 100, "lead_campaign_data": [
                {"campaign_id": 999, "status": "sequence_finished"},
            ]}

        def fake_heyreach(profile_url=None, **kw):
            return ([{"campaignId": 888, "campaignStatus": "FINISHED",
                       "leadStatus": "Finished"}], 1)

        result = check_lead_state.check_not_in_a_live_sequence(
            rec, contact, camps,
            bison_find_lead=fake_bison,
            heyreach_campaigns_for_lead=fake_heyreach)
        self.assertEqual(result["verdict"], PASS)

    def test_fail_when_in_sequence_at_emailbison(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        contact["linkedin"] = "https://linkedin.com/in/jane"
        camps = [_make_campaign()]

        def fake_bison(email):
            return {"id": 100, "lead_campaign_data": [
                {"campaign_id": 491, "status": "in_sequence"},
            ]}

        def fake_heyreach(profile_url=None, **kw):
            return ([], 0)

        result = check_lead_state.check_not_in_a_live_sequence(
            rec, contact, camps,
            bison_find_lead=fake_bison,
            heyreach_campaigns_for_lead=fake_heyreach)
        self.assertEqual(result["verdict"], FAIL)
        self.assertTrue(any("emailbison" in o for o in result["offenders"]))

    def test_fail_when_in_sequence_at_heyreach(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        contact["linkedin"] = "https://linkedin.com/in/jane"
        camps = [_make_campaign()]

        def fake_bison(email):
            return None

        def fake_heyreach(profile_url=None, **kw):
            return ([{"campaignId": 605732, "campaignStatus": "IN_PROGRESS",
                       "leadStatus": "InSequence"}], 1)

        result = check_lead_state.check_not_in_a_live_sequence(
            rec, contact, camps,
            bison_find_lead=fake_bison,
            heyreach_campaigns_for_lead=fake_heyreach)
        self.assertEqual(result["verdict"], FAIL)
        self.assertTrue(any("heyreach" in o for o in result["offenders"]))

    def test_unverifiable_when_no_profile_url(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        camps = [_make_campaign()]

        def fake_bison(email):
            return None

        result = check_lead_state.check_not_in_a_live_sequence(
            rec, contact, camps,
            bison_find_lead=fake_bison)
        self.assertTrue(any("no_profile_url" in u
                           for u in result["unverifiable"]))

    def test_ours_vs_client_evidence_reported(self):
        """Say which evidence decided ours vs theirs for every row."""
        rec = _make_rec()
        contact = rec["contacts"][0]
        contact["linkedin"] = "https://linkedin.com/in/jane"
        camps = [_make_campaign(bison_id=502)]

        def fake_bison(email):
            return {"id": 100, "lead_campaign_data": [
                {"campaign_id": 502, "status": "in_sequence"},
            ]}

        def fake_heyreach(profile_url=None, **kw):
            return ([{"campaignId": 605732, "campaignStatus": "IN_PROGRESS",
                       "leadStatus": "InSequence"}], 1)

        result = check_lead_state.check_not_in_a_live_sequence(
            rec, contact, camps,
            bison_find_lead=fake_bison,
            heyreach_campaigns_for_lead=fake_heyreach)
        ovc = result["details"]["ours_vs_client"]
        self.assertTrue(len(ovc) >= 1)
        whose_values = {e["whose"] for e in ovc}
        self.assertTrue(
            "OURS" in whose_values or "CLIENT'S" in whose_values)

    def test_key_presence_reported(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        camps = [_make_campaign()]

        def fake_bison(email):
            return None

        result = check_lead_state.check_not_in_a_live_sequence(
            rec, contact, camps, bison_find_lead=fake_bison)
        kp = result["key_presence"]
        self.assertIn("email_present", kp)
        self.assertIn("profile_url_present", kp)
        self.assertIn("heyreach_lead_id_present", kp)


# ------------------------------------------------------------- rule 6

class TestAccountRuleSatisfied(unittest.TestCase):
    """Rule 6: account rule satisfied, with ISSUE-035 carve-out."""

    def test_pass_when_allow(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        camps = [_make_campaign()]

        def fake_check(domain, **kw):
            return {"domain": domain, "verdict": "clear",
                    "leads": 0, "anyone_in_sequence": False,
                    "emails_sent_total": 0, "people": []}

        def fake_policy(account):
            return collision.ALLOW, "nothing at this account"

        result = check_lead_state.check_account_rule_satisfied(
            rec, contact, camps,
            collision_check_account=fake_check,
            collision_account_policy=fake_policy)
        self.assertEqual(result["verdict"], PASS)

    def test_fail_when_stop(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        camps = [_make_campaign()]

        def fake_check(domain, **kw):
            return {"domain": domain, "verdict": "in_sequence",
                    "leads": 3, "anyone_in_sequence": True,
                    "emails_sent_total": 10,
                    "people": [{"lead_status": "in_sequence",
                                "campaigns": [{"status": "in_sequence",
                                               "emails_sent": 5}]}]}

        def fake_policy(account):
            return collision.STOP, "somebody mid-sequence"

        result = check_lead_state.check_account_rule_satisfied(
            rec, contact, camps,
            collision_check_account=fake_check,
            collision_account_policy=fake_policy)
        self.assertEqual(result["verdict"], FAIL)
        self.assertTrue(len(result["offenders"]) >= 1)

    def test_issue_035_carveout_our_deliberate_stop(self):
        """A stop carrying our own reason is NOT an account-level hold."""
        rec = _make_rec()
        contact = rec["contacts"][0]
        camps = [_make_campaign()]

        def fake_check(domain, **kw):
            return {"domain": domain, "verdict": "touched",
                    "leads": 1, "anyone_in_sequence": False,
                    "emails_sent_total": 0,
                    "people": [{"lead_status": "stopped",
                                "campaigns": [{"status": "stopped",
                                               "emails_sent": 0}]}]}

        def fake_policy(account):
            return collision.HOLD, "stopped at account"

        result = check_lead_state.check_account_rule_satisfied(
            rec, contact, camps,
            collision_check_account=fake_check,
            collision_account_policy=fake_policy)
        self.assertEqual(result["verdict"], PASS)
        self.assertTrue(result["details"].get("issue_035_carveout"))

    def test_unverifiable_when_no_domain(self):
        rec = _make_rec(domain="")
        contact = rec["contacts"][0]
        camps = [_make_campaign()]
        result = check_lead_state.check_account_rule_satisfied(
            rec, contact, camps)
        self.assertEqual(result["verdict"], UNCONFIRMED)
        self.assertTrue(len(result["unverifiable"]) >= 1)


# ------------------------------------------------------------- rule 7

class TestApprovalSnapshotCovers(unittest.TestCase):
    """Rule 7: the client approval snapshot covers this account."""

    def test_pass_when_approved(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        approval_rows = [
            {"kind": "client_approval", "client": "productive",
             "domain": "acme.test", "state": "approved",
             "who": "operator", "at": "2026-09-20T10:00:00Z",
             "snapshot": "snap-001"},
        ]
        result = check_lead_state.check_approval_snapshot_covers(
            rec, contact, approval_rows=approval_rows)
        self.assertEqual(result["verdict"], PASS)

    def test_fail_when_pending(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        result = check_lead_state.check_approval_snapshot_covers(
            rec, contact, approval_rows=[])
        self.assertEqual(result["verdict"], FAIL)
        self.assertIn("pending", result["details"]["state"])

    def test_fail_when_suppressed(self):
        rec = _make_rec()
        contact = rec["contacts"][0]
        approval_rows = [
            {"kind": "client_approval", "client": "productive",
             "domain": "acme.test", "state": "suppressed",
             "who": "client", "at": "2026-09-15T10:00:00Z"},
        ]
        result = check_lead_state.check_approval_snapshot_covers(
            rec, contact, approval_rows=approval_rows)
        self.assertEqual(result["verdict"], FAIL)
        self.assertEqual(result["details"]["state"], "suppressed")


# ------------------------------------------------------------- rule 8

class TestTimezoneCohortHasAWindow(unittest.TestCase):
    """Rule 8: the campaign can send in this lead's timezone."""

    def test_pass_when_in_window(self):
        rec = _make_rec(timezone="America/New_York")
        contact = rec["contacts"][0]
        camps = [_make_campaign(bison_id=502, record_ids=["rec-001"])]

        # Monday 10:00 ET
        now = datetime.datetime(2026, 9, 28, 14, 0, 0,
                                tzinfo=datetime.timezone.utc)

        def fake_schedule(cid):
            return {"timezone": "America/New_York",
                    "start_hour": 9, "end_hour": 17,
                    "days": ["mon", "tue", "wed", "thu", "fri"]}

        result = check_lead_state.check_timezone_cohort_has_a_window(
            rec, contact, camps,
            bison_schedule=fake_schedule, now=now)
        self.assertEqual(result["verdict"], PASS)
        self.assertTrue(result["details"]["in_window"])

    def test_fail_when_outside_window(self):
        """ISSUE-045: this check SHOULD currently fail for out-of-hours."""
        rec = _make_rec(timezone="America/New_York")
        contact = rec["contacts"][0]
        camps = [_make_campaign(bison_id=502, record_ids=["rec-001"])]

        # Saturday 10:00 ET — weekend
        now = datetime.datetime(2026, 9, 26, 14, 0, 0,
                                tzinfo=datetime.timezone.utc)

        def fake_schedule(cid):
            return {"timezone": "America/New_York",
                    "start_hour": 9, "end_hour": 17,
                    "days": ["mon", "tue", "wed", "thu", "fri"]}

        result = check_lead_state.check_timezone_cohort_has_a_window(
            rec, contact, camps,
            bison_schedule=fake_schedule, now=now)
        self.assertEqual(result["verdict"], FAIL)
        self.assertFalse(result["details"]["in_window"])

    def test_fail_when_no_timezone(self):
        """A guessed timezone is worse than a missing one."""
        rec = _make_rec()
        contact = rec["contacts"][0]
        camps = [_make_campaign(bison_id=502, record_ids=["rec-001"])]
        result = check_lead_state.check_timezone_cohort_has_a_window(
            rec, contact, camps)
        self.assertEqual(result["verdict"], FAIL)
        self.assertIn("no timezone", result["details"]["reason"])

    def test_schedule_as_provider_returned_it(self):
        """Report the actual schedule read back per campaign."""
        rec = _make_rec(timezone="Europe/London")
        contact = rec["contacts"][0]
        camps = [_make_campaign(bison_id=502, record_ids=["rec-001"])]

        now = datetime.datetime(2026, 9, 28, 14, 0, 0,
                                tzinfo=datetime.timezone.utc)

        def fake_schedule(cid):
            return {"timezone": "Europe/London",
                    "start_hour": 9, "end_hour": 17,
                    "days": ["mon", "tue", "wed", "thu", "fri"]}

        result = check_lead_state.check_timezone_cohort_has_a_window(
            rec, contact, camps,
            bison_schedule=fake_schedule, now=now)
        sched = result["details"]["schedule"]
        self.assertEqual(sched["timezone"], "Europe/London")
        self.assertEqual(sched["start_hour"], 9)
        self.assertEqual(sched["end_hour"], 17)
        self.assertIn("mon", sched["days"])


# ------------------------------------------------------------- the runner

class TestRunner(unittest.TestCase):
    """The runner aggregates rules and closes the arithmetic."""

    def test_arithmetic_closes(self):
        """clean + |offenders ∪ unverifiable| == subjects."""
        recs = [
            _make_rec("rec-001", "acme.test", "a@acme.test", "a"),
            _make_rec("rec-002", "beta.test", "b@beta.test", "b"),
        ]
        camps = [_make_campaign(502, ["rec-001", "rec-002"])]

        # Make rec-001 fail rule 1 (no verification evidence).
        # Make rec-002 clean.
        result = check_lead_state.run(
            phase="pre_push", batch="test-batch",
            campaigns=[502], recs=recs, camp_rows=camps,
            live_reads=False)

        self.assertIn(result["verdict"], (PASS, FAIL, UNCONFIRMED, VACUOUS))
        subjects = result["subjects"]
        clean = result["clean"]
        all_flagged = set()
        for rule in result["offenders"]:
            all_flagged |= set(result["offenders"][rule])
        for rule in result["unverifiable"]:
            all_flagged |= set(result["unverifiable"][rule])
        self.assertEqual(clean + len(all_flagged), subjects)

    def test_vacuous_when_zero_subjects(self):
        """subjects == 0 is VACUOUS, exit 2."""
        result = check_lead_state.run(
            phase="pre_push", recs=[], camp_rows=[])
        self.assertEqual(result["verdict"], VACUOUS)
        self.assertEqual(result["subjects"], 0)

    def test_error_when_no_workspaces(self):
        result = check_lead_state.run(
            phase="pre_push", recs=None, camp_rows=None,
            workspaces=None)
        self.assertEqual(result["verdict"], ERROR)

    def test_all_rules_present_in_output(self):
        """Every key in counts, offenders and unverifiable exists in rules."""
        recs = [_make_rec()]
        camps = [_make_campaign(502, ["rec-001"])]
        result = check_lead_state.run(
            phase="pre_push", recs=recs, camp_rows=camps,
            live_reads=False)
        for rule_name in check_lead_state.RULES:
            self.assertIn(rule_name, result["rules"])
            self.assertIn(rule_name, result["counts"])
            self.assertIn(rule_name, result["offenders"])
            self.assertIn(rule_name, result["unverifiable"])

    def test_live_reads_disabled_marks_unconfirmed(self):
        """When live reads are off, provider-dependent rules are UNCONFIRMED."""
        recs = [_make_rec()]
        camps = [_make_campaign(502, ["rec-001"])]
        result = check_lead_state.run(
            phase="pre_push", recs=recs, camp_rows=camps,
            live_reads=False)
        # not_in_a_live_sequence should have unverifiable entries
        self.assertTrue(
            len(result["unverifiable"]["not_in_a_live_sequence"]) > 0)


# ------------------------------------------------------------- constructed failures

class TestEightConstructedFailures(unittest.TestCase):
    """Eight rules, eight demonstrations, each with the offending id."""

    def _single_rec_run(self, rec, camps=None, **overrides):
        camps = camps or [_make_campaign(502, [rec["id"]])]
        defaults = dict(
            phase="pre_push", recs=[rec], camp_rows=camps,
            live_reads=False)
        defaults.update(overrides)
        return check_lead_state.run(**defaults)

    def test_rule1_verified_fires(self):
        rec = _make_rec("rec-r1")
        result = self._single_rec_run(rec)
        self.assertIn("rec-r1",
                       str(result["offenders"]["verified_by_two_providers"]))

    def test_rule2_suppressed_fires(self):
        rec = _make_rec("rec-r2", drop_reason="suppress:legal")
        result = self._single_rec_run(rec)
        self.assertIn("rec-r2",
                       str(result["offenders"]["not_suppressed"]))

    def test_rule3_bounced_fires(self):
        rec = _make_rec("rec-r3", events=[
            {"type": "email_bounced", "contact": "jane"}])
        result = self._single_rec_run(rec)
        self.assertIn("rec-r3",
                       str(result["offenders"]["not_bounced"]))

    def test_rule4_replier_fires(self):
        rec = _make_rec("rec-r4", events=[
            {"type": "reply_received", "contact": "jane"}])
        result = self._single_rec_run(rec)
        self.assertIn("rec-r4",
                       str(result["offenders"]["not_a_replier"]))

    def test_rule5_live_sequence_fires(self):
        rec = _make_rec("rec-r5")
        contact = rec["contacts"][0]
        contact["linkedin"] = "https://linkedin.com/in/jane"
        camps = [_make_campaign(502, ["rec-r5"])]

        def fake_bison(email):
            return {"id": 100, "lead_campaign_data": [
                {"campaign_id": 491, "status": "in_sequence"},
            ]}

        def fake_heyreach(profile_url=None, **kw):
            return ([], 0)

        result = check_lead_state.run(
            phase="pre_push", recs=[rec], camp_rows=camps,
            live_reads=True,
            bison_find_lead=fake_bison,
            heyreach_campaigns_for_lead=fake_heyreach)
        self.assertIn("rec-r5",
                       str(result["offenders"]["not_in_a_live_sequence"]))

    def test_rule6_account_rule_fires(self):
        rec = _make_rec("rec-r6")
        camps = [_make_campaign(502, ["rec-r6"])]

        def fake_check(domain, **kw):
            return {"domain": domain, "verdict": "in_sequence",
                    "leads": 3, "anyone_in_sequence": True,
                    "emails_sent_total": 10,
                    "people": [{"lead_status": "in_sequence",
                                "campaigns": [{"status": "in_sequence",
                                               "emails_sent": 5}]}]}

        def fake_policy(account):
            return collision.STOP, "somebody mid-sequence"

        result = check_lead_state.run(
            phase="pre_push", recs=[rec], camp_rows=camps,
            live_reads=True,
            collision_check_account=fake_check,
            collision_account_policy=fake_policy)
        self.assertIn("rec-r6",
                       str(result["offenders"]["account_rule_satisfied"]))

    def test_rule7_approval_fires(self):
        rec = _make_rec("rec-r7")
        result = self._single_rec_run(rec)
        # No approval rows -> pending -> FAIL
        self.assertIn("rec-r7",
                       str(result["offenders"]["approval_snapshot_covers"]))

    def test_rule8_timezone_fires(self):
        rec = _make_rec("rec-r8")
        # No timezone -> FAIL
        result = self._single_rec_run(rec)
        self.assertIn("rec-r8",
                       str(result["offenders"]["timezone_cohort_has_a_window"]))


if __name__ == "__main__":
    unittest.main()
