#!/usr/bin/env python3
"""TASK-215: compare_bison compares like for like.

Two tests:
1. PASS when the provider's sequence holds the expected placeholders and each
   lead's custom variables match the approved resolved copy.
2. FAIL when one contact's custom variable differs from its approved copy,
   naming that contact by hashed email.

THE DEFECT THIS REPLACES. The old approved_bison compared resolved per-contact
subjects/bodies against the provider's sequence placeholders ({SUBJECT_1},
<p>{BODY_1}</p>) - two different quantities that can never agree. It compared
cadence DAY positions against provider wait_in_days - a schedule position
against a graph property. Both mismatches were by design, not by drift.

THE FIX. The approved side now states:
- Sequence subjects/bodies: the EXPECTED PLACEHOLDERS from the config
- Delays: the declared wait_in_days from the config
- Actions: step1, step2, step3 (matching provider naming)
- Per-lead copy: the resolved custom variables each lead should carry

The provider side reads:
- Sequence subjects/bodies: the placeholders the template holds
- Delays: the wait_in_days from the sequence steps
- Per-lead custom variables: read via GET /leads/{id} per lead
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import approval as approval_mod
from src import bisonfactory, campaigns, cadence, configdiff, store
from src.providers import bison, set_transport, reset_transport
from tests.fakebison import FakeBison


def _fp(step):
    """Compute the real approval fingerprint for a step dict."""
    return approval_mod.fingerprint(step)


CID = "compare-bison-test"
CLIENT = "productive"

CONTROL_SEQUENCE_CONFIG = {
    "title": "Resonate generated cadence",
    "steps": {
        "em1": {"order": 1, "subject": "{SUBJECT_1}",
                "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
        "em2": {"order": 2, "subject": "{SUBJECT_2}",
                "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
        "em3": {"order": 3, "subject": "{SUBJECT_3}",
                "body": "<p>{BODY_3}</p>", "wait_in_days": 0},
    },
    "thread_reply_pattern": [False, True, False],
}

CONFIG = {
    "cadence": "productive_li_heavy_v1",
    "email_sequence": CONTROL_SEQUENCE_CONFIG,
    "sending_window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                                "friday"],
                       "start": "09:00", "end": "17:00",
                       "timezone": "Europe/Zagreb"},
    "providers": {"emailbison": {"workspace": 10}},
}

CONTROL_CADENCE_STEPS = [
    {"day": 1, "key": "em1", "channel": "email", "generated": True},
    {"day": 4, "key": "em2", "channel": "email", "generated": True},
    {"day": 8, "key": "em3", "channel": "email", "generated": True},
]

# Two contacts with approved copy for all three steps.
# Fingerprints are computed in _build_records() because they depend on the
# step content.

def _build_records():
    """Build record fixtures with real approval fingerprints."""
    def _step(key, day, subject, body):
        s = {"channel": "email", "key": key, "day": day,
             "subject": subject, "body": body, "generated": True}
        s["approval"] = {"action": "approve", "fingerprint": _fp(s)}
        return s

    rec_a = {
        "id": "rec-a",
        "client": CLIENT,
        "domain": "example.com",
        "contacts": [
            {"key": "alice", "email": "alice@example.com", "sendable": True,
             "name": "Alice Smith", "first_name": "Alice", "last_name": "Smith",
             "linkedin": "https://linkedin.com/in/alice-smith"},
        ],
        "cadence": {
            "alice": {
                "em1": _step("em1", 1, "Pain point subject",
                             "<p>Hi Alice, pain point body</p>"),
                "em2": _step("em2", 4, "Proof subject",
                             "<p>Hi Alice, proof body</p>"),
                "em3": _step("em3", 8, "Breakup subject",
                             "<p>Hi Alice, breakup body</p>"),
            },
        },
    }

    rec_b = {
        "id": "rec-b",
        "client": CLIENT,
        "domain": "other.com",
        "contacts": [
            {"key": "bob", "email": "bob@example.org", "sendable": True,
             "name": "Bob Jones", "first_name": "Bob", "last_name": "Jones",
             "linkedin": "https://linkedin.com/in/bob-jones"},
        ],
        "cadence": {
            "bob": {
                "em1": _step("em1", 1, "Pain point subject",
                             "<p>Hi Bob, pain point body</p>"),
                "em2": _step("em2", 4, "Proof subject",
                             "<p>Hi Bob, proof body</p>"),
                "em3": _step("em3", 8, "Breakup subject",
                             "<p>Hi Bob, breakup body</p>"),
            },
        },
    }
    return rec_a, rec_b

CAMPAIGN_ROW = {
    "campaign_id": CID,
    "client": CLIENT,
    "name": "RESONATE - PRODUCTIVE - EMAIL - CONTROL",
    "bison_campaign_id": 501,
    "record_ids": ["rec-a", "rec-b"],
    "senders": {"email": [{"provider_account_id": 2736}]},
    "daily_volume": {"email": 20},
    "provider_status_expected": "paused",
    "cadence_steps": CONTROL_CADENCE_STEPS,
}


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _lead_vars(contact_copy, multi_step=True):
    """Build the custom variables a lead should carry."""
    if not multi_step:
        return [{"name": "subject", "value": contact_copy[0]["subject"]},
                {"name": "body", "value": contact_copy[0]["body"]}]
    out = []
    for i, entry in enumerate(contact_copy, start=1):
        out.append({"name": f"subject_{i}", "value": entry["subject"]})
        out.append({"name": f"body_{i}", "value": entry["body"]})
    return out


class _Base(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="compare_bison_test_")
        self.campaigns_file = os.path.join(self.tmpdir, "campaigns.jsonl")
        self.queue_file = os.path.join(self.tmpdir, "queue.jsonl")

        self._orig = {}
        for key in ("CAMPAIGNS", "QUEUE", "BISON_KEY"):
            self._orig[key] = os.environ.get(key)

        os.environ["CAMPAIGNS"] = self.campaigns_file
        os.environ["QUEUE"] = self.queue_file
        os.environ["BISON_KEY"] = "test-key-for-compare"

        self.fb = FakeBison(workspace=10, name="PRODUCTIVE")
        set_transport(self.fb)

        self.rec_a, self.rec_b = _build_records()
        _write_jsonl(self.campaigns_file, [CAMPAIGN_ROW])
        _write_jsonl(self.queue_file, [self.rec_a, self.rec_b])

    def tearDown(self):
        reset_transport()
        for key, val in self._orig.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _setup_provider_match(self):
        """Set up the fake provider so everything matches."""
        derived_name = bisonfactory.provider_campaign_name(CAMPAIGN_ROW)
        self.fb.campaigns[501] = {
            "id": 501, "name": derived_name, "status": "paused",
            "max_emails_per_day": 20, "max_new_leads_per_day": 20,
        }
        self.fb.senders[501] = [2736]
        self.fb.members[501] = []

        # Sequence: placeholders, not resolved copy.
        self.fb.sequences[501] = [
            {"id": 4001, "active": True, "order": 1,
             "email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_1}</p>",
             "wait_in_days": 3, "variant": False,
             "thread_reply": False},
            {"id": 4002, "active": True, "order": 2,
             "email_subject": "Re: {SUBJECT_2}",
             "email_body": "<p>{BODY_2}</p>",
             "wait_in_days": 4, "variant": False,
             "thread_reply": True},
            {"id": 4003, "active": True, "order": 3,
             "email_subject": "{SUBJECT_3}",
             "email_body": "<p>{BODY_3}</p>",
             "wait_in_days": 0, "variant": False,
             "thread_reply": False},
        ]

        # Leads with custom variables matching the approved copy.
        alice_copy = [
            {"subject": "Pain point subject",
             "body": "<p>Hi Alice, pain point body</p>"},
            {"subject": "Proof subject",
             "body": "<p>Hi Alice, proof body</p>"},
            {"subject": "Breakup subject",
             "body": "<p>Hi Alice, breakup body</p>"},
        ]
        bob_copy = [
            {"subject": "Pain point subject",
             "body": "<p>Hi Bob, pain point body</p>"},
            {"subject": "Proof subject",
             "body": "<p>Hi Bob, proof body</p>"},
            {"subject": "Breakup subject",
             "body": "<p>Hi Bob, breakup body</p>"},
        ]

        alice_id = self.fb.add_lead("alice@example.com",
                                     first_name="Alice", last_name="Smith")
        bob_id = self.fb.add_lead("bob@example.org",
                                   first_name="Bob", last_name="Jones")
        self.fb.leads[alice_id]["custom_variables"] = _lead_vars(alice_copy)
        self.fb.leads[bob_id]["custom_variables"] = _lead_vars(bob_copy)
        self.fb.members[501] = [alice_id, bob_id]


class CompareBisonPass(_Base):
    """The provider matches: verdict is PASS."""

    def test_verdict_pass_when_everything_matches(self):
        self._setup_provider_match()
        rows = list(campaigns.load())
        campaign = campaigns.require(CID, rows)
        recs = list(store.load())

        readback = configdiff.compare_bison(
            campaign, recs=recs, config=CONFIG, expect_workspace=10)

        self.assertEqual(readback.verdict, configdiff.PASS,
                         f"expected PASS but got {readback.verdict}: "
                         f"{readback.failures}")

    def test_sequence_fields_match_placeholders_not_resolved_copy(self):
        """The approved subjects are placeholders, not resolved text."""
        self._setup_provider_match()
        rows = list(campaigns.load())
        campaign = campaigns.require(CID, rows)
        recs = list(store.load())

        approved = configdiff.approved_bison(campaign, recs, CONFIG)
        # Subjects should be the placeholders from the config.
        self.assertEqual(approved["subjects"],
                         ("{SUBJECT_1}", "{SUBJECT_2}", "{SUBJECT_3}"))
        # Delays should be the declared wait_in_days, not cadence days.
        self.assertEqual(approved["delays"], (3, 4, 0))
        # Actions should use provider naming.
        self.assertEqual(approved["actions"], ("step1", "step2", "step3"))

    def test_campaign_name_is_derived(self):
        """The approved name is the derived name, not the human name."""
        self._setup_provider_match()
        rows = list(campaigns.load())
        campaign = campaigns.require(CID, rows)
        recs = list(store.load())

        approved = configdiff.approved_bison(campaign, recs, CONFIG)
        expected = bisonfactory.provider_campaign_name(CAMPAIGN_ROW)
        self.assertEqual(approved["campaign_name"], expected)
        self.assertIn("[productive/compare-bison-test]", expected)

    def test_workspace_derived_from_config(self):
        """The approved workspace comes from the config, not the row."""
        self._setup_provider_match()
        rows = list(campaigns.load())
        campaign = campaigns.require(CID, rows)
        recs = list(store.load())

        approved = configdiff.approved_bison(campaign, recs, CONFIG)
        self.assertEqual(approved["workspace"], "10")


class CompareBisonFailLeadCopy(_Base):
    """One contact's custom variable differs: verdict is FAIL naming that
    contact."""

    def test_verdict_fail_when_one_lead_differs(self):
        self._setup_provider_match()
        # Tamper with Bob's body_1 - change the resolved copy.
        bob_lead_id = [lid for lid in self.fb.members[501]
                       if self.fb.leads[lid]["email"] == "bob@example.org"][0]
        bob_vars = self.fb.leads[bob_lead_id]["custom_variables"]
        for v in bob_vars:
            if v["name"] == "body_1":
                v["value"] = "<p>WRONG BODY for Bob</p>"
                break

        rows = list(campaigns.load())
        campaign = campaigns.require(CID, rows)
        recs = list(store.load())

        readback = configdiff.compare_bison(
            campaign, recs=recs, config=CONFIG, expect_workspace=10)

        self.assertEqual(readback.verdict, configdiff.FAIL)
        # The failure should name the contact by hashed email.
        bob_hash = configdiff._hash_email("bob@example.org")
        failure_text = " ".join(readback.failures)
        self.assertIn(bob_hash, failure_text,
                      f"expected hashed email {bob_hash} in failures: "
                      f"{failure_text}")
        self.assertIn("body_1", failure_text)

    def test_alice_passes_when_only_bob_differs(self):
        """Alice's copy is correct; only Bob's is wrong."""
        self._setup_provider_match()
        bob_lead_id = [lid for lid in self.fb.members[501]
                       if self.fb.leads[lid]["email"] == "bob@example.org"][0]
        bob_vars = self.fb.leads[bob_lead_id]["custom_variables"]
        for v in bob_vars:
            if v["name"] == "subject_2":
                v["value"] = "WRONG SUBJECT"
                break

        rows = list(campaigns.load())
        campaign = campaigns.require(CID, rows)
        recs = list(store.load())

        readback = configdiff.compare_bison(
            campaign, recs=recs, config=CONFIG, expect_workspace=10)

        self.assertEqual(readback.verdict, configdiff.FAIL)
        alice_hash = configdiff._hash_email("alice@example.com")
        bob_hash = configdiff._hash_email("bob@example.org")
        failure_text = " ".join(readback.failures)
        # Bob should be in the failures.
        self.assertIn(bob_hash, failure_text)
        # Alice should NOT be in the failures.
        self.assertNotIn(alice_hash, failure_text)


class CompareBisonSequenceMismatch(_Base):
    """A sequence-level mismatch still fails correctly."""

    def test_wrong_placeholder_in_sequence_fails(self):
        self._setup_provider_match()
        # Change a sequence placeholder at the provider.
        self.fb.sequences[501][0]["email_subject"] = "{WRONG_PLACEHOLDER}"

        rows = list(campaigns.load())
        campaign = campaigns.require(CID, rows)
        recs = list(store.load())

        readback = configdiff.compare_bison(
            campaign, recs=recs, config=CONFIG, expect_workspace=10)

        self.assertEqual(readback.verdict, configdiff.FAIL)
        failure_text = " ".join(readback.failures)
        self.assertIn("subjects", failure_text)


if __name__ == "__main__":
    unittest.main()
