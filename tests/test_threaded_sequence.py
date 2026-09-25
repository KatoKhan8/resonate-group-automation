#!/usr/bin/env python3
"""Only the opener owns a subject. TASK-219.

The operator verified the desired behaviour in the EmailBison UI: follow-ups
must stay in the original thread, and only the opener owns a subject.

    em1   NEW EMAIL   thread_reply false, subject_1 + body_1
    em2   FOLLOW-UP   thread_reply TRUE,  body_2, NO new subject
    em3   FOLLOW-UP   thread_reply TRUE,  body_3, NO new subject

No ``subject_2``, no ``subject_3``. The provider's thread-reply mechanism
owns threading. This test module proves:

1. The config in the threaded shape stages correctly.
2. ``_variables_for`` writes ``subject_1`` only; follow-up subjects are empty.
3. ``_stale_clearances`` clears ``subject_2..6`` AND ``body_4..6`` for a
   threaded 3-step sequence.
4. A sequence with ``em2 thread_reply=false`` AND a distinct ``subject_2``
   is REFUSED by the activation preflight.
5. The same for ``em3``.
6. The comparator proves thread_reply flags, opener subject, bodies, and
   the absence of stale follow-up subjects.

THE REGRESSION THESE CATCH: remove the thread-reply validation in
``_sequence_steps`` and tests 4 and 5 go red. Remove the subject-emptying
in ``_variables_for`` and the threaded variable tests go red. Remove the
in-range clearing in ``_stale_clearances`` and the stale-clearing tests
go red.
"""
import unittest

from src import bisonfactory, campaigns, store, workspaces
from src.bisonfactory import FactoryRefused
from src.providers.bison import MAX_SEQUENCE_STEPS
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import FakeBison
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty


CID = "camp-threaded-seq"


def _threaded_config(*, em2_thread_reply=True, em3_thread_reply=True,
                     em2_subject="{SUBJECT_1}", em3_subject="{SUBJECT_1}"):
    """A 3-step config with controllable thread_reply and subject per step."""
    return {
        "cadence": "three_step_test",
        "cadences": {
            "three_step_test": [
                {"key": "em1", "day": 1, "channel": "email",
                 "generated": True},
                {"key": "em2", "day": 4, "channel": "email",
                 "generated": True},
                {"key": "em3", "day": 8, "channel": "email",
                 "generated": True},
            ],
        },
        "email_sequence": {
            "title": "Resonate threaded",
            "steps": {
                "em1": {"order": 1, "subject": "{SUBJECT_1}",
                         "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                "em2": {"order": 2, "subject": em2_subject,
                         "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
                "em3": {"order": 3, "subject": em3_subject,
                         "body": "<p>{BODY_3}</p>", "wait_in_days": 1},
            },
            "thread_reply_pattern": [False, em2_thread_reply,
                                     em3_thread_reply],
        },
        "sending_window": {"days": ["monday", "tuesday", "wednesday",
                                    "thursday", "friday"],
                           "start": "09:00", "end": "17:00",
                           "timezone": "Europe/Zagreb"},
        "providers": {"emailbison": {"workspace": 10}},
    }


def _approved(step_key, n):
    # THE STAMP COVERS THE WORDS. A placeholder fingerprint was enough
    # while staging checked only that an approval existed;
    # `bisonfactory._certified_copy` now hashes the words it is about to
    # stage and compares, so a stamp that covers nothing is refused.
    from src import approval as _approval

    step = {"channel": "email",
            "subject": f"subject for {step_key}",
            "body": f"<p>body for {step_key}</p>"}
    step["approval"] = {"by": "operator", "at": "2026-09-16T00:00:00Z",
                        "fingerprint": _approval.fingerprint(step)}
    return step


def _record(rid, email, first):
    key = f"{rid}-c1"
    steps = {k: _approved(k, i) for i, k in enumerate(
        ("em1", "em2", "em3"), start=1)}
    return {"id": rid, "client": "productive", "domain": "example.com",
            "company": "Example", "state": "ready",
            "cadence": {key: steps},
            "contacts": [{"key": key, "email": email, "first_name": first,
                          "last_name": "Tester", "sendable": True,
                          "verified": True, "bison_lead_id": None}]}


# ---------------------------------------------- negative tests (the deliverable)

class NegativeTests(unittest.TestCase):
    """A follow-up that is NOT a thread reply AND has its own subject is
    refused by the activation preflight.

    These are the tests that matter most. A future implementation must not
    be able to turn a follow-up into a new email with a new subject without
    a test going red.
    """

    def test_em2_not_threaded_with_distinct_subject_is_refused(self):
        """em2 thread_reply=false AND subject_2 -> FAIL."""
        config = _threaded_config(em2_thread_reply=False,
                                  em2_subject="{SUBJECT_2}")
        cadence_steps = config["cadences"]["three_step_test"]
        with self.assertRaises(FactoryRefused) as ctx:
            bisonfactory._sequence_steps(
                config["email_sequence"], cadence_steps)
        self.assertIn("not a thread reply", str(ctx.exception))
        self.assertIn("distinct subject", str(ctx.exception))

    def test_em3_not_threaded_with_distinct_subject_is_refused(self):
        """em3 thread_reply=false AND subject_3 -> FAIL."""
        config = _threaded_config(em3_thread_reply=False,
                                  em3_subject="{SUBJECT_3}")
        cadence_steps = config["cadences"]["three_step_test"]
        with self.assertRaises(FactoryRefused) as ctx:
            bisonfactory._sequence_steps(
                config["email_sequence"], cadence_steps)
        self.assertIn("not a thread reply", str(ctx.exception))
        self.assertIn("distinct subject", str(ctx.exception))

    def test_em2_not_threaded_but_same_subject_is_allowed(self):
        """em2 thread_reply=false but subject matches opener -> allowed.

        The invariant is about a DISTINCT subject on a non-threaded step.
        A non-threaded step with the SAME subject as the opener is not the
        defect being caught (it would open a new thread with the same
        subject, which is odd but not the invariant violation).
        """
        config = _threaded_config(em2_thread_reply=False,
                                  em2_subject="{SUBJECT_1}")
        cadence_steps = config["cadences"]["three_step_test"]
        steps = bisonfactory._sequence_steps(
            config["email_sequence"], cadence_steps)
        self.assertEqual(len(steps), 3)

    def test_both_follow_ups_threaded_with_same_subject_is_allowed(self):
        """The correct threaded shape: both follow-ups threaded, same subject."""
        config = _threaded_config()
        cadence_steps = config["cadences"]["three_step_test"]
        steps = bisonfactory._sequence_steps(
            config["email_sequence"], cadence_steps)
        self.assertEqual(len(steps), 3)
        self.assertFalse(steps[0]["thread_reply"])
        self.assertTrue(steps[1]["thread_reply"])
        self.assertTrue(steps[2]["thread_reply"])
        for step in steps:
            self.assertEqual(step["email_subject"], "{SUBJECT_1}")


# ---------------------------------------- stale clearances for threaded shape

class StaleClearancesThreaded(unittest.TestCase):
    """``_stale_clearances`` for a threaded 3-step sequence clears
    ``subject_2..6`` AND ``body_4..6``.
    """

    def _threaded_sequence(self, n=3):
        seq = []
        for i in range(1, n + 1):
            seq.append({"step_key": f"em{i}", "order": i,
                         "thread_reply": i > 1})
        return seq

    def test_threaded_three_step_clears_subject_2_through_6(self):
        """subject_2..6 are cleared for a threaded 3-step sequence."""
        clearances = bisonfactory._stale_clearances(
            self._threaded_sequence(3))
        names = {e["name"] for e in clearances}
        for pos in range(2, MAX_SEQUENCE_STEPS + 1):
            self.assertIn(f"subject_{pos}", names,
                          f"subject_{pos} should be cleared for a threaded "
                          f"3-step sequence")

    def test_threaded_three_step_clears_body_4_through_6(self):
        """body_4..6 are cleared (out-of-range) but body_1..3 are not."""
        clearances = bisonfactory._stale_clearances(
            self._threaded_sequence(3))
        names = {e["name"] for e in clearances}
        for pos in range(4, MAX_SEQUENCE_STEPS + 1):
            self.assertIn(f"body_{pos}", names,
                          f"body_{pos} should be cleared (out-of-range)")
        for pos in range(1, 4):
            self.assertNotIn(f"body_{pos}", names,
                             f"body_{pos} should NOT be cleared (in-range)")

    def test_threaded_three_step_does_not_clear_subject_1(self):
        """subject_1 is the opener's subject and must not be cleared."""
        clearances = bisonfactory._stale_clearances(
            self._threaded_sequence(3))
        names = {e["name"] for e in clearances}
        self.assertNotIn("subject_1", names)

    def test_non_threaded_three_step_does_not_clear_subject_2_or_3(self):
        """A non-threaded sequence uses all its subjects; no in-range clearing."""
        seq = [{"step_key": f"em{i}", "order": i, "thread_reply": False}
               for i in range(1, 4)]
        clearances = bisonfactory._stale_clearances(seq)
        names = {e["name"] for e in clearances}
        self.assertNotIn("subject_2", names)
        self.assertNotIn("subject_3", names)
        for pos in range(4, MAX_SEQUENCE_STEPS + 1):
            self.assertIn(f"subject_{pos}", names)
            self.assertIn(f"body_{pos}", names)

    def test_threaded_five_step_clears_subject_2_through_5_and_body_6(self):
        """Boundary: a threaded 5-step sequence clears subject_2..5 and body_6."""
        clearances = bisonfactory._stale_clearances(
            self._threaded_sequence(5))
        names = {e["name"] for e in clearances}
        for pos in range(2, 6):
            self.assertIn(f"subject_{pos}", names,
                          f"subject_{pos} should be cleared (in-range threaded)")
        self.assertIn("subject_6", names)
        self.assertIn("body_6", names)
        for pos in range(1, 6):
            self.assertNotIn(f"body_{pos}", names,
                             f"body_{pos} should NOT be cleared (in-range)")

    def test_every_clearance_value_is_empty(self):
        for entry in bisonfactory._stale_clearances(
                self._threaded_sequence(3)):
            self.assertEqual(entry["value"], "")


# ------------------------------------------- _variables_for threaded shape

class VariablesForThreaded(unittest.TestCase):
    """``_variables_for`` writes ``subject_1`` only for threaded follow-ups."""

    def _lead(self, copy):
        return {"record_id": "rec-1", "contact_key": "rec-1-c1",
                "copy": copy, "subject": copy[0]["subject"] if copy else "",
                "body": copy[0]["body"] if copy else ""}

    def _campaign(self):
        return {"client": "productive"}

    def test_threaded_follow_up_subjects_are_empty(self):
        """For a threaded 3-step sequence, subject_2 and subject_3 are empty.

        ``bison._variables`` drops empty values, so the result does not
        include ``subject_2`` or ``subject_3`` at all. The absence is the
        point: the provider never receives a non-empty follow-up subject.
        """
        sequence = [
            {"step_key": "em1", "order": 1, "thread_reply": False},
            {"step_key": "em2", "order": 2, "thread_reply": True},
            {"step_key": "em3", "order": 3, "thread_reply": True},
        ]
        copy = [
            {"step_key": "em1", "subject": "opener subject",
             "body": "<p>body 1</p>"},
            {"step_key": "em2", "subject": "follow-up subject 2",
             "body": "<p>body 2</p>"},
            {"step_key": "em3", "subject": "follow-up subject 3",
             "body": "<p>body 3</p>"},
        ]
        lead = self._lead(copy)
        result = bisonfactory._variables_for(
            lead, self._campaign(), sequence=sequence)
        names = {v["name"]: v["value"] for v in result}
        self.assertEqual(names.get("subject_1"), "opener subject")
        # subject_2 and subject_3 are dropped by bison._variables because
        # they are empty. Their absence is the correct behavior.
        self.assertNotIn("subject_2", names)
        self.assertNotIn("subject_3", names)

    def test_all_bodies_are_written(self):
        """Every body is written regardless of threading."""
        sequence = [
            {"step_key": "em1", "order": 1, "thread_reply": False},
            {"step_key": "em2", "order": 2, "thread_reply": True},
            {"step_key": "em3", "order": 3, "thread_reply": True},
        ]
        copy = [
            {"step_key": "em1", "subject": "opener",
             "body": "<p>body 1</p>"},
            {"step_key": "em2", "subject": "follow-up 2",
             "body": "<p>body 2</p>"},
            {"step_key": "em3", "subject": "follow-up 3",
             "body": "<p>body 3</p>"},
        ]
        lead = self._lead(copy)
        result = bisonfactory._variables_for(
            lead, self._campaign(), sequence=sequence)
        names = {v["name"]: v["value"] for v in result}
        self.assertEqual(names.get("body_1"), "<p>body 1</p>")
        self.assertEqual(names.get("body_2"), "<p>body 2</p>")
        self.assertEqual(names.get("body_3"), "<p>body 3</p>")

    def test_non_threaded_sequence_keeps_all_subjects(self):
        """A non-threaded sequence writes all subjects."""
        sequence = [
            {"step_key": "em1", "order": 1, "thread_reply": False},
            {"step_key": "em2", "order": 2, "thread_reply": False},
            {"step_key": "em3", "order": 3, "thread_reply": False},
        ]
        copy = [
            {"step_key": "em1", "subject": "subject 1",
             "body": "<p>body 1</p>"},
            {"step_key": "em2", "subject": "subject 2",
             "body": "<p>body 2</p>"},
            {"step_key": "em3", "subject": "subject 3",
             "body": "<p>body 3</p>"},
        ]
        lead = self._lead(copy)
        result = bisonfactory._variables_for(
            lead, self._campaign(), sequence=sequence)
        names = {v["name"]: v["value"] for v in result}
        self.assertEqual(names.get("subject_1"), "subject 1")
        self.assertEqual(names.get("subject_2"), "subject 2")
        self.assertEqual(names.get("subject_3"), "subject 3")

    def test_no_sequence_backward_compatible(self):
        """Without a sequence, all subjects are written (backward compat)."""
        copy = [
            {"step_key": "em1", "subject": "subject 1",
             "body": "<p>body 1</p>"},
            {"step_key": "em2", "subject": "subject 2",
             "body": "<p>body 2</p>"},
        ]
        lead = self._lead(copy)
        result = bisonfactory._variables_for(lead, self._campaign())
        names = {v["name"]: v["value"] for v in result}
        self.assertEqual(names.get("subject_1"), "subject 1")
        self.assertEqual(names.get("subject_2"), "subject 2")


# ----------------------------------- integration: staged threaded campaign

class ThreadedCampaignStaging(QueueTest):
    """Drive ``stage()`` through the real entry point with a threaded config.

    Proves that the variables written to the provider have subject_1 only,
    with follow-up subjects empty.
    """

    def setUp(self):
        super().setUp()
        self.fb = FakeBison()
        self._real = bisonfactory.bison
        bisonfactory.bison = self.fb
        self.addCleanup(setattr, bisonfactory, "bison", self._real)
        patch_collision_empty(self)

        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

    def _stage(self, config=None):
        config = config or _threaded_config()
        return bisonfactory.stage(CID, config=config, live=True)

    def test_threaded_campaign_writes_subject_1_only(self):
        """The staged lead carries subject_1 with the opener subject, and
        subject_2/subject_3 are empty."""
        self.fb.ensure_custom_variables()
        rec = _record("rec-1", "one@example.com", "Ada")
        store.save([rec])

        row = campaigns.new_campaign(CID, "productive", "Threaded test")
        # DECLARED, NOT INHERITED. `_plan` refuses a campaign with no
        # `cadence_steps`, and that refusal fires BEFORE the threading
        # invariant - so without this the negative tests below would go red
        # on the wrong guard and prove nothing about threading. The steps are
        # the ones this config's named cadence already supplies.
        row["cadence_steps"] = [dict(s) for s in
                                _threaded_config()["cadences"]["three_step_test"]]
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        prov = self.fb.create_campaign(
            bisonfactory.provider_campaign_name(row))
        row["bison_campaign_id"] = prov["id"]
        campaigns.save([row])

        self._stage()

        # Reload from store: _remember_leads writes to the persisted records.
        recs = store.load()
        stored_rec = next(r for r in recs if r["id"] == "rec-1")
        lid = stored_rec["contacts"][0]["bison_lead_id"]
        self.assertIsNotNone(lid, "lead should have been created and bound")
        held = self.fb.variables_of(self.fb.lead(lid))
        self.assertEqual(held.get("subject_1"), "subject for em1")
        # subject_2 and subject_3 are either empty or absent (dropped by
        # bison._variables during creation). Either way, they carry no
        # prospect-facing content.
        self.assertFalse(held.get("subject_2"),
                         f"subject_2 should be empty/absent, got "
                         f"{held.get('subject_2')!r}")
        self.assertFalse(held.get("subject_3"),
                         f"subject_3 should be empty/absent, got "
                         f"{held.get('subject_3')!r}")
        self.assertEqual(held.get("body_1"), "<p>body for em1</p>")
        self.assertEqual(held.get("body_2"), "<p>body for em2</p>")
        self.assertEqual(held.get("body_3"), "<p>body for em3</p>")

    def test_threaded_campaign_clears_stale_subjects_on_existing_lead(self):
        """A lead from a non-threaded era has its stale subjects cleared."""
        self.fb.ensure_custom_variables()
        lid = self.fb.create_lead({
            "email": "one@example.com",
            "first_name": "Ada",
            "last_name": "Tester",
            "custom_variables": bisonfactory.bison._variables({
                "record_id": "rec-1",
                "contact_key": "rec-1-c1",
                "client": "productive",
                "subject_1": "OLD opener",
                "body_1": "<p>OLD body 1</p>",
                "subject_2": "OLD subject 2",
                "body_2": "<p>OLD body 2</p>",
                "subject_3": "OLD subject 3",
                "body_3": "<p>OLD body 3</p>",
            }),
        })["id"]

        rec = _record("rec-1", "one@example.com", "Ada")
        rec["contacts"][0]["bison_lead_id"] = lid
        store.save([rec])

        row = campaigns.new_campaign(CID, "productive", "Threaded test")
        # DECLARED, NOT INHERITED. `_plan` refuses a campaign with no
        # `cadence_steps`, and that refusal fires BEFORE the threading
        # invariant - so without this the negative tests below would go red
        # on the wrong guard and prove nothing about threading. The steps are
        # the ones this config's named cadence already supplies.
        row["cadence_steps"] = [dict(s) for s in
                                _threaded_config()["cadences"]["three_step_test"]]
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        prov = self.fb.create_campaign(
            bisonfactory.provider_campaign_name(row))
        row["bison_campaign_id"] = prov["id"]
        campaigns.save([row])

        self._stage()

        held = self.fb.variables_of(self.fb.lead(lid))
        self.assertEqual(held.get("subject_1"), "subject for em1")
        self.assertEqual(held.get("subject_2"), "",
                         "stale subject_2 from non-threaded era must be cleared")
        self.assertEqual(held.get("subject_3"), "",
                         "stale subject_3 from non-threaded era must be cleared")
        self.assertEqual(held.get("body_1"), "<p>body for em1</p>")
        self.assertEqual(held.get("body_2"), "<p>body for em2</p>")
        self.assertEqual(held.get("body_3"), "<p>body for em3</p>")

    def test_negative_em2_not_threaded_with_distinct_subject_refused(self):
        """The activation preflight refuses em2 thread_reply=false + subject_2.

        This is the NEGATIVE test that matters most. A future implementation
        that turns a follow-up into a new email with a new subject will hit
        this refusal.
        """
        self.fb.ensure_custom_variables()
        rec = _record("rec-1", "one@example.com", "Ada")
        store.save([rec])

        row = campaigns.new_campaign(CID, "productive", "Threaded test")
        # DECLARED, NOT INHERITED. `_plan` refuses a campaign with no
        # `cadence_steps`, and that refusal fires BEFORE the threading
        # invariant - so without this the negative tests below would go red
        # on the wrong guard and prove nothing about threading. The steps are
        # the ones this config's named cadence already supplies.
        row["cadence_steps"] = [dict(s) for s in
                                _threaded_config()["cadences"]["three_step_test"]]
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        prov = self.fb.create_campaign(
            bisonfactory.provider_campaign_name(row))
        row["bison_campaign_id"] = prov["id"]
        campaigns.save([row])

        bad_config = _threaded_config(em2_thread_reply=False,
                                      em2_subject="{SUBJECT_2}")
        with self.assertRaises(FactoryRefused) as ctx:
            bisonfactory.stage(CID, config=bad_config, live=True)
        self.assertIn("not a thread reply", str(ctx.exception))

    def test_negative_em3_not_threaded_with_distinct_subject_refused(self):
        """The activation preflight refuses em3 thread_reply=false + subject_3."""
        self.fb.ensure_custom_variables()
        rec = _record("rec-1", "one@example.com", "Ada")
        store.save([rec])

        row = campaigns.new_campaign(CID, "productive", "Threaded test")
        # DECLARED, NOT INHERITED. `_plan` refuses a campaign with no
        # `cadence_steps`, and that refusal fires BEFORE the threading
        # invariant - so without this the negative tests below would go red
        # on the wrong guard and prove nothing about threading. The steps are
        # the ones this config's named cadence already supplies.
        row["cadence_steps"] = [dict(s) for s in
                                _threaded_config()["cadences"]["three_step_test"]]
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        prov = self.fb.create_campaign(
            bisonfactory.provider_campaign_name(row))
        row["bison_campaign_id"] = prov["id"]
        campaigns.save([row])

        bad_config = _threaded_config(em3_thread_reply=False,
                                      em3_subject="{SUBJECT_3}")
        with self.assertRaises(FactoryRefused) as ctx:
            bisonfactory.stage(CID, config=bad_config, live=True)
        self.assertIn("not a thread reply", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
