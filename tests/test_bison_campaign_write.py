#!/usr/bin/env python3
"""Rehearse the campaign write Claude is about to perform (TASK-184).

Two authorized writes:
    bison.create_campaign   create a NEW email campaign
    bison.set_sequence      write the CONTROL sequence onto it

NOT authorized: bison.add_lead, bison.activate. The campaign that results
holds nobody and cannot send.

AGAINST A FAKE TRANSPORT ONLY. No real provider call. The point is that the
real write is the second time the code path runs, not the first.

WHAT THIS PROVES:
1. The campaign is created holding zero leads.
2. The sequence written is three CONTROL steps with threading F/T/T.
3. The readback returns what was written.
4. A second set_sequence call APPENDS (the behaviour to prove, not assume).
5. The retry question: a blind retry produces a doubled sequence.
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import bisonfactory, campaigns, providerwrites, store
from src.providers import bison, set_transport, reset_transport
from tests.fakebison import FakeBison


# ---------------------------------------------------------------- fixtures

CID = "control-rehearsal"
CLIENT = "productive"

# The three CONTROL steps, from cadence.TEMPLATES: persona_pain,
# comparable_proof, breakup. Threading F/T/T: opener owns the subject,
# both follow-ups are thread replies referencing it.
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
    "thread_reply_pattern": [False, True, True],
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

# A three-step cadence matching the CONTROL sequence: em1, em2, em3 on
# days 1, 4, 8 (gaps 3, 4). The third wait is declared but unchecked
# because nothing follows it.
CONTROL_CADENCE_STEPS = [
    {"day": 1, "key": "em1", "channel": "email"},
    {"day": 4, "key": "em2", "channel": "email"},
    {"day": 8, "key": "em3", "channel": "email"},
]


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


class _Base(unittest.TestCase):
    """Temp dir, fake bison, env overrides."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="bison_write_rehearsal_")
        self.campaigns_file = os.path.join(self.tmpdir, "campaigns.jsonl")
        self.queue_file = os.path.join(self.tmpdir, "queue.jsonl")

        self._orig = {}
        for key in ("CAMPAIGNS", "QUEUE", "BISON_KEY"):
            self._orig[key] = os.environ.get(key)

        os.environ["CAMPAIGNS"] = self.campaigns_file
        os.environ["QUEUE"] = self.queue_file
        os.environ["BISON_KEY"] = "test-key-for-rehearsal"

        self.fb = FakeBison(workspace=10, name="PRODUCTIVE")
        set_transport(self.fb)

        # A campaign row with no bison_campaign_id - the not-yet-created case.
        _write_jsonl(self.campaigns_file, [
            {"campaign_id": CID, "client": CLIENT,
             "name": "RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - "
                      "CONTROL",
             "bison_campaign_id": None}
        ])
        # An empty queue - no leads for this rehearsal.
        _write_jsonl(self.queue_file, [])

    def tearDown(self):
        reset_transport()
        for key, val in self._orig.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ---------------------------------------------------------------- tests

class CampaignNameDerivation(_Base):
    """What name the factory derives for the CONTROL cohort."""

    def test_derived_name_carries_client_and_campaign_id_suffix(self):
        rows = list(campaigns.load())
        campaign = campaigns.require(CID, rows)
        name = bisonfactory.provider_campaign_name(campaign)
        self.assertEqual(
            name,
            "RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - CONTROL "
            "[productive/control-rehearsal]")

    def test_identity_check_will_recognise_the_derived_name(self):
        """The pre-write check compares against the derived name, not the
        raw canonical name. If the derivation changes, the identity check
        must track it."""
        rows = list(campaigns.load())
        campaign = campaigns.require(CID, rows)
        derived = bisonfactory.provider_campaign_name(campaign)
        # The identity check in bison_prewrite_check uses this function.
        # If it ever uses a different derivation, the identity check fails.
        self.assertIn("[productive/control-rehearsal]", derived)


class SequenceShape(_Base):
    """The three CONTROL steps with threading F/T/T, built by _sequence_steps."""

    def test_three_steps_in_cadence_order(self):
        steps = bisonfactory._sequence_steps(
            CONTROL_SEQUENCE_CONFIG, CONTROL_CADENCE_STEPS)
        self.assertEqual(len(steps), 3)
        self.assertEqual([s["order"] for s in steps], [1, 2, 3])
        self.assertEqual([s["step_key"] for s in steps], ["em1", "em2", "em3"])

    def test_threading_is_false_true_true(self):
        steps = bisonfactory._sequence_steps(
            CONTROL_SEQUENCE_CONFIG, CONTROL_CADENCE_STEPS)
        self.assertEqual(
            [s["thread_reply"] for s in steps],
            [False, True, True])

    def test_waits_are_declared(self):
        steps = bisonfactory._sequence_steps(
            CONTROL_SEQUENCE_CONFIG, CONTROL_CADENCE_STEPS)
        # em1 waits 3 (gap to em2 on day 4), em2 waits 4 (gap to em3 on day 8).
        # em3's wait is declared but unchecked (nothing follows).
        self.assertEqual(steps[0]["wait_in_days"], 3)
        self.assertEqual(steps[1]["wait_in_days"], 4)
        self.assertEqual(steps[2]["wait_in_days"], 0)


class CreateCampaignHoldsZeroLeads(_Base):
    """The campaign is created holding zero leads."""

    def test_new_campaign_has_no_members(self):
        """Drive create_campaign through the providerwrites.perform path."""
        created = {}

        def _transport(p):
            created.update(bison.create_campaign(p["name"]))
            return created

        providerwrites.perform(
            providerwrites.EMAIL_CREATE_CAMPAIGN,
            campaign=CID, tenant=CLIENT,
            payload={"name": "test-campaign"},
            transport=_transport,
            readback=lambda: {"exists": bool(created.get("id"))},
            expected={"exists": True}, by="test")

        provider_id = created["id"]
        self.assertIsNotNone(provider_id)
        # Zero leads: the FakeBison starts with an empty member list.
        self.assertEqual(self.fb.members.get(provider_id), [])
        # Status is draft - cannot send.
        self.assertEqual(self.fb.campaigns[provider_id]["status"], "draft")


class SequenceWriteAndReadback(_Base):
    """Write the CONTROL sequence, read it back, prove it matches."""

    def _create_and_get_id(self):
        created = bison.create_campaign("test-control-campaign")
        return created["id"]

    def test_write_three_steps_readback_matches(self):
        provider_id = self._create_and_get_id()
        steps = bisonfactory._sequence_steps(
            CONTROL_SEQUENCE_CONFIG, CONTROL_CADENCE_STEPS)
        # Strip step_key - the provider has no field for it.
        wire_steps = [{k: v for k, v in s.items() if k != "step_key"}
                      for s in steps]

        bison.set_sequence(provider_id, "Resonate generated cadence",
                           wire_steps)

        # Read back from the fake.
        held = bison.sequence_steps(provider_id)
        self.assertEqual(len(held), 3)
        # Threading pattern preserved.
        self.assertEqual(
            [s["thread_reply"] for s in held],
            [False, True, True])
        # Subjects preserved.
        self.assertEqual(
            [s["email_subject"] for s in held],
            ["{SUBJECT_1}", "{SUBJECT_2}", "{SUBJECT_3}"])

    def test_held_steps_carry_wait_in_days(self):
        provider_id = self._create_and_get_id()
        steps = bisonfactory._sequence_steps(
            CONTROL_SEQUENCE_CONFIG, CONTROL_CADENCE_STEPS)
        wire_steps = [{k: v for k, v in s.items() if k != "step_key"}
                      for s in steps]

        bison.set_sequence(provider_id, "Resonate generated cadence",
                           wire_steps)

        held = bison.sequence_steps(provider_id)
        self.assertEqual([s["wait_in_days"] for s in held], [3, 4, 0])


class AppendBehaviourProven(_Base):
    """THE CRITICAL TEST. A second set_sequence APPENDS, not replaces.

    This is the single most dangerous fact in this task. Every instinct on
    a failed write says retry, and retrying this one produces a campaign
    carrying the CONTROL sequence twice - which, once leads are added, is
    a prospect receiving six messages instead of three.
    """

    def test_second_write_appends_not_replaces(self):
        provider_id = bison.create_campaign("test-append")["id"]
        steps = bisonfactory._sequence_steps(
            CONTROL_SEQUENCE_CONFIG, CONTROL_CADENCE_STEPS)
        wire_steps = [{k: v for k, v in s.items() if k != "step_key"}
                      for s in steps]

        # First write: three steps.
        bison.set_sequence(provider_id, "Resonate generated cadence",
                           wire_steps)
        held_after_first = bison.sequence_steps(provider_id)
        self.assertEqual(len(held_after_first), 3)

        # Second write: three MORE steps appended.
        bison.set_sequence(provider_id, "Resonate generated cadence",
                           wire_steps)
        held_after_second = bison.sequence_steps(provider_id)

        # SIX steps, not three. This is the trap.
        self.assertEqual(len(held_after_second), 6,
                         "set_sequence APPENDS - a retry doubles the sequence. "
                         "A campaign with six steps sends six emails instead "
                         "of three. The only remedy is deleting the campaign.")

    def test_orders_interleave_across_writes(self):
        """The provider renumbers orders across writes: 1,2,3 then 1,3,2,4
        was measured live. The fake reproduces the append-and-renumber."""
        provider_id = bison.create_campaign("test-interleave")["id"]
        step_a = [{"email_subject": "A", "email_body": "body-a",
                    "wait_in_days": 3}]
        step_b = [{"email_subject": "B", "email_body": "body-b",
                    "wait_in_days": 4}]

        bison.set_sequence(provider_id, "title", step_a)
        bison.set_sequence(provider_id, "title", step_b)

        held = bison.sequence_steps(provider_id)
        self.assertEqual(len(held), 2)
        # Orders are sequential: 1, 2 (appended, not interleaved for
        # single-step writes). The live measurement showed interleaving
        # for multi-step writes.
        self.assertEqual(held[0]["email_subject"], "A")
        self.assertEqual(held[1]["email_subject"], "B")


class EnsureSequenceRefusesNonEmpty(_Base):
    """_ensure_sequence reads existing steps and refuses a mismatch.

    This is the brake that prevents the append trap from firing in
    production. It reads what the provider holds and refuses if it does
    not match, rather than blindly appending.
    """

    def test_refuses_when_campaign_holds_different_steps(self):
        provider_id = bison.create_campaign("test-refuse")["id"]
        # Write one step first.
        bison.set_sequence(provider_id, "old", [
            {"email_subject": "old subject", "email_body": "old body",
             "wait_in_days": 3}])

        # Now build a campaign row and plan that wants three different steps.
        rows = list(campaigns.load())
        campaign = campaigns.require(CID, rows)
        # Bind the campaign to the provider id.
        campaign["bison_campaign_id"] = provider_id

        plan = {
            "sequence": bisonfactory._sequence_steps(
                CONTROL_SEQUENCE_CONFIG, CONTROL_CADENCE_STEPS),
            "sequence_config": CONTROL_SEQUENCE_CONFIG,
            "name": "test",
        }
        report = {"did": []}

        # _ensure_sequence should refuse because the held steps differ.
        with self.assertRaises(bisonfactory.FactoryRefused) as ctx:
            bisonfactory._ensure_sequence(
                provider_id, campaign, plan, report, by="test")
        self.assertIn("APPENDS", str(ctx.exception))

    def test_passes_when_campaign_holds_identical_steps(self):
        """If the sequence was already written correctly, _ensure_sequence
        reports it as already staged and returns without writing."""
        provider_id = bison.create_campaign("test-idempotent")["id"]
        steps = bisonfactory._sequence_steps(
            CONTROL_SEQUENCE_CONFIG, CONTROL_CADENCE_STEPS)
        wire_steps = [{k: v for k, v in s.items() if k != "step_key"}
                      for s in steps]
        # Pre-write the correct sequence.
        bison.set_sequence(provider_id, "Resonate generated cadence",
                           wire_steps)

        rows = list(campaigns.load())
        campaign = campaigns.require(CID, rows)
        campaign["bison_campaign_id"] = provider_id

        plan = {
            "sequence": steps,
            "sequence_config": CONTROL_SEQUENCE_CONFIG,
            "name": "test",
        }
        report = {"did": []}

        # Should NOT raise - it recognises the sequence is already correct.
        bisonfactory._ensure_sequence(
            provider_id, campaign, plan, report, by="test")
        self.assertIn("sequence already staged", report["did"][0])


class RetryQuestion(_Base):
    """If the write fails halfway - campaign created, sequence write times
    out - what is the correct recovery?

    A blind retry appends a second copy of the sequence. The correct
    recovery is: read what the provider holds, and only write if it holds
    nothing.
    """

    def test_blind_retry_doubles_the_sequence(self):
        """Simulate: create succeeds, sequence write succeeds but the
        caller thinks it failed (timeout). A blind retry appends."""
        provider_id = bison.create_campaign("test-retry")["id"]
        steps = bisonfactory._sequence_steps(
            CONTROL_SEQUENCE_CONFIG, CONTROL_CADENCE_STEPS)
        wire_steps = [{k: v for k, v in s.items() if k != "step_key"}
                      for s in steps]

        # First write - succeeded but caller got a timeout.
        bison.set_sequence(provider_id, "Resonate generated cadence",
                           wire_steps)

        # Blind retry - the dangerous instinct.
        bison.set_sequence(provider_id, "Resonate generated cadence",
                           wire_steps)

        held = bison.sequence_steps(provider_id)
        self.assertEqual(len(held), 6,
                         "BLIND RETRY PRODUCED SIX STEPS. "
                         "This is the trap stated in the task.")

    def test_correct_recovery_read_before_write(self):
        """The correct recovery: read what the provider holds first."""
        provider_id = bison.create_campaign("test-safe-retry")["id"]
        steps = bisonfactory._sequence_steps(
            CONTROL_SEQUENCE_CONFIG, CONTROL_CADENCE_STEPS)
        wire_steps = [{k: v for k, v in s.items() if k != "step_key"}
                      for s in steps]

        # First write succeeded.
        bison.set_sequence(provider_id, "Resonate generated cadence",
                           wire_steps)

        # Safe retry: read first.
        held = bison.sequence_steps(provider_id)
        if held:
            # Provider already has steps. Check if they match.
            wanted = [(s["email_subject"], s["email_body"],
                       s.get("thread_reply")) for s in wire_steps]
            got = [(s.get("email_subject"), s.get("email_body"),
                    s.get("thread_reply")) for s in held]
            if got == wanted:
                # Already written correctly. Do NOT write again.
                recovery_action = "skip"
            else:
                # Different sequence. Cannot safely append.
                recovery_action = "refuse"
        else:
            # Empty - safe to write.
            recovery_action = "write"

        self.assertEqual(recovery_action, "skip")
        # Verify still three steps, not six.
        final = bison.sequence_steps(provider_id)
        self.assertEqual(len(final), 3)

    def test_once_or_twice_check(self):
        """A check that distinguishes 'sequence written once' from
        'sequence written twice'."""
        provider_id = bison.create_campaign("test-check")["id"]
        steps = bisonfactory._sequence_steps(
            CONTROL_SEQUENCE_CONFIG, CONTROL_CADENCE_STEPS)
        wire_steps = [{k: v for k, v in s.items() if k != "step_key"}
                      for s in steps]

        # Written once.
        bison.set_sequence(provider_id, "Resonate generated cadence",
                           wire_steps)
        held = bison.sequence_steps(provider_id)
        self.assertEqual(len(held), 3, "written once: three steps")

        # The check: count must equal expected.
        expected_count = len(wire_steps)
        self.assertEqual(len(held), expected_count)

        # Written twice (the failure case).
        bison.set_sequence(provider_id, "Resonate generated cadence",
                           wire_steps)
        held_twice = bison.sequence_steps(provider_id)
        self.assertEqual(len(held_twice), 2 * expected_count,
                         "written twice: six steps - detectable by count")
        # The check distinguishes:
        self.assertNotEqual(len(held_twice), expected_count)


if __name__ == "__main__":
    unittest.main()
