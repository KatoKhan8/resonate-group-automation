#!/usr/bin/env python3
"""A lead cannot hold a numbered variable beyond the campaign's sequence length.

TASK-217. Campaign 485 had ten leads carrying ``subject_4``, ``subject_5``,
``body_4`` and ``body_5`` from a five-step era while the campaign had shrunk
to three steps. ``_variables_for`` named only ``subject_1..3`` and
``body_1..3``; the stale comparison in ``_ensure_leads`` only checked
variables in the wanted set; so the four extras were never compared and
never cleared. Activating would have sent real prospects words from a
sequence the campaign no longer carried.

The fix: ``_stale_clearances`` returns explicit empties for every numbered
position above the sequence length up to ``MAX_SEQUENCE_STEPS``.
``_ensure_leads`` merges them into the wanted set before the stale
comparison, so the reconciliation writes "" for each one.

THE REGRESSION THIS CATCHES: delete the call to ``_stale_clearances`` in
``_ensure_leads`` and the stale-clearing test below fails. The unit test on
``_stale_clearances`` alone passes, but the lead still holds the stale
variables - which is the "existence is not function" trap from QWEN.md.
"""
import unittest

from src import bisonfactory, cadence, campaigns, store, workspaces
from src.providers.bison import MAX_SEQUENCE_STEPS
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import FakeBison
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty


CID = "camp-stale-vars"

THREE_STEP_CONFIG = {
    "cadence": "three_step_test",
    "cadences": {
        "three_step_test": [
            {"key": "em1", "day": 1, "channel": "email", "generated": True},
            {"key": "em2", "day": 4, "channel": "email", "generated": True},
            {"key": "em3", "day": 8, "channel": "email", "generated": True},
        ],
    },
    "email_sequence": {
        "title": "Resonate generated cadence",
        "steps": {
            "em1": {"order": 1, "subject": "{SUBJECT_1}",
                    "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
            "em2": {"order": 2, "subject": "{SUBJECT_1}",
                    "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
            "em3": {"order": 3, "subject": "{SUBJECT_1}",
                    "body": "<p>{BODY_3}</p>", "wait_in_days": 1},
        },
        # Threaded shape: only the opener owns a subject (TASK-219).
        "thread_reply_pattern": [False, True, True],
    },
    "sending_window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                                "friday"],
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


class StaleClearancesUnit(unittest.TestCase):
    """``_stale_clearances`` alone, no provider."""

    def test_three_step_campaign_clears_four_through_max(self):
        sequence = [{"step_key": f"em{i}", "order": i} for i in range(1, 4)]
        clearances = bisonfactory._stale_clearances(sequence)
        names = {e["name"] for e in clearances}
        for pos in range(4, MAX_SEQUENCE_STEPS + 1):
            self.assertIn(f"subject_{pos}", names)
            self.assertIn(f"body_{pos}", names)

    def test_every_clearance_value_is_empty(self):
        sequence = [{"step_key": f"em{i}", "order": i} for i in range(1, 4)]
        for entry in bisonfactory._stale_clearances(sequence):
            self.assertEqual(entry["value"], "")

    def test_no_clearance_for_positions_within_the_sequence(self):
        sequence = [{"step_key": f"em{i}", "order": i} for i in range(1, 4)]
        names = {e["name"] for e in bisonfactory._stale_clearances(sequence)}
        for pos in range(1, 4):
            self.assertNotIn(f"subject_{pos}", names)
            self.assertNotIn(f"body_{pos}", names)

    def test_single_step_campaign_has_no_clearances(self):
        sequence = [{"order": 1, "email_subject": "{SUBJECT}",
                     "email_body": "<p>{BODY}</p>"}]
        self.assertEqual(bisonfactory._stale_clearances(sequence), [])

    def test_five_step_campaign_clears_only_position_six(self):
        sequence = [{"step_key": f"em{i}", "order": i} for i in range(1, 6)]
        clearances = bisonfactory._stale_clearances(sequence)
        names = {e["name"] for e in clearances}
        self.assertIn("subject_6", names)
        self.assertIn("body_6", names)
        self.assertNotIn("subject_5", names)
        self.assertNotIn("body_5", names)

    def test_empty_sequence_has_no_clearances(self):
        self.assertEqual(bisonfactory._stale_clearances([]), [])


class StaleVariablesClearedOnReconciliation(QueueTest):
    """Drive ``stage()`` through the real entry point.

    Pre-populates leads at the fake provider with five-step variables, then
    stages a three-step campaign. The reconciliation must clear positions
    4 through MAX_SEQUENCE_STEPS.
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

    def _prepopulate_lead(self, rid, email, first):
        """Create a lead at the fake with five-step variables already on it.

        Returns the provider lead id.
        """
        self.fb.ensure_custom_variables()
        lead_data = self.fb.create_lead({
            "email": email,
            "first_name": first,
            "last_name": "Tester",
            "custom_variables": bisonfactory.bison._variables({
                "record_id": rid,
                "contact_key": f"{rid}-c1",
                "client": "productive",
                "subject_1": f"subject for em1",
                "body_1": f"<p>body for em1</p>",
                "subject_2": f"subject for em2",
                "body_2": f"<p>body for em2</p>",
                "subject_3": f"subject for em3",
                "body_3": f"<p>body for em3</p>",
                "subject_4": "OLD subject four",
                "body_4": "<p>OLD body four</p>",
                "subject_5": "OLD subject five",
                "body_5": "<p>OLD body five</p>",
            }),
        })
        return lead_data["id"]

    def _stage(self):
        return bisonfactory.stage(CID, config=THREE_STEP_CONFIG, live=True)

    def test_stale_numbered_variables_are_cleared(self):
        """The defect TASK-217 fixes: out-of-range variables survive."""
        lid1 = self._prepopulate_lead("rec-1", "one@example.com", "Ada")
        lid2 = self._prepopulate_lead("rec-2", "two@example.com", "Grace")

        recs = [_record("rec-1", "one@example.com", "Ada"),
                _record("rec-2", "two@example.com", "Grace")]
        for rec, lid in zip(recs, [lid1, lid2]):
            rec["contacts"][0]["bison_lead_id"] = lid
        store.save(recs)

        row = campaigns.new_campaign(CID, "productive", "Stale vars test")
        # DECLARED, NOT INHERITED. `bisonfactory._plan` refuses a
        # campaign carrying no `cadence_steps`: the fallback through
        # the client config is what let a live campaign be staged
        # against a cadence it never chose. This is exactly what the
        # fallback would have produced, so the behaviour under test is
        # unchanged - the campaign now SAYS what it runs.
        row["cadence_steps"] = [dict(s) for s in cadence.steps_for(
            None, config=THREE_STEP_CONFIG)]
        row["record_ids"] = ["rec-1", "rec-2"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        prov = self.fb.create_campaign(
            bisonfactory.provider_campaign_name(row))
        row["bison_campaign_id"] = prov["id"]
        campaigns.save([row])

        report = self._stage()

        for lid in [lid1, lid2]:
            held = self.fb.variables_of(self.fb.lead(lid))
            for pos in range(4, MAX_SEQUENCE_STEPS + 1):
                for prefix in ("subject", "body"):
                    name = f"{prefix}_{pos}"
                    value = held.get(name, "")
                    self.assertEqual(
                        value, "",
                        f"lead {lid} still holds non-empty {name}={value!r} "
                        f"after reconciliation on a 3-step campaign")

    def test_in_range_variables_are_preserved(self):
        """Clearing position 4+ must not touch positions 1-3."""
        lid = self._prepopulate_lead("rec-1", "one@example.com", "Ada")

        rec = _record("rec-1", "one@example.com", "Ada")
        rec["contacts"][0]["bison_lead_id"] = lid
        store.save([rec])

        row = campaigns.new_campaign(CID, "productive", "Stale vars test")
        # DECLARED, NOT INHERITED. `bisonfactory._plan` refuses a
        # campaign carrying no `cadence_steps`: the fallback through
        # the client config is what let a live campaign be staged
        # against a cadence it never chose. This is exactly what the
        # fallback would have produced, so the behaviour under test is
        # unchanged - the campaign now SAYS what it runs.
        row["cadence_steps"] = [dict(s) for s in cadence.steps_for(
            None, config=THREE_STEP_CONFIG)]
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        prov = self.fb.create_campaign(
            bisonfactory.provider_campaign_name(row))
        row["bison_campaign_id"] = prov["id"]
        campaigns.save([row])

        self._stage()

        held = self.fb.variables_of(self.fb.lead(lid))
        # Threaded shape (TASK-219): subject_1 is the opener and is preserved.
        # subject_2 and subject_3 are cleared because they are in-range
        # follow-up subjects the threaded shape does not use.
        self.assertEqual(
            held.get("subject_1"), "subject for em1",
            "subject_1 was corrupted by the stale clearing")
        for pos in (2, 3):
            self.assertEqual(
                held.get(f"subject_{pos}"), "",
                f"subject_{pos} should be cleared (threaded follow-up)")
        for pos in range(1, 4):
            key = f"em{pos}"
            self.assertEqual(
                held.get(f"body_{pos}"), f"<p>body for {key}</p>",
                f"body_{pos} was corrupted by the stale clearing")

    def test_report_names_the_cleared_variables(self):
        """The operator sees what was cleared, not just that something was."""
        lid = self._prepopulate_lead("rec-1", "one@example.com", "Ada")

        rec = _record("rec-1", "one@example.com", "Ada")
        rec["contacts"][0]["bison_lead_id"] = lid
        store.save([rec])

        row = campaigns.new_campaign(CID, "productive", "Stale vars test")
        # DECLARED, NOT INHERITED. `bisonfactory._plan` refuses a
        # campaign carrying no `cadence_steps`: the fallback through
        # the client config is what let a live campaign be staged
        # against a cadence it never chose. This is exactly what the
        # fallback would have produced, so the behaviour under test is
        # unchanged - the campaign now SAYS what it runs.
        row["cadence_steps"] = [dict(s) for s in cadence.steps_for(
            None, config=THREE_STEP_CONFIG)]
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        prov = self.fb.create_campaign(
            bisonfactory.provider_campaign_name(row))
        row["bison_campaign_id"] = prov["id"]
        campaigns.save([row])

        report = self._stage()

        refresh_lines = [line for line in report["did"]
                         if "refreshed" in line]
        self.assertTrue(refresh_lines,
                        "expected at least one 'refreshed' line in the report")
        combined = " ".join(refresh_lines)
        self.assertIn("subject_4", combined)
        self.assertIn("body_4", combined)

    def test_already_empty_variables_do_not_trigger_extra_writes(self):
        """A lead whose out-of-range and threaded-follow-up variables are
        already "" is not updated.

        The reconciliation compares held values against wanted ones. A
        variable that is already "" matches the clearance entry and does
        not appear in the stale list. Only variables that are non-empty
        or absent (None != "") trigger a write.

        With the threaded shape (TASK-219), subject_2 and subject_3 are
        also expected to be empty, so they must be pre-set to "" for this
        test to verify that no unnecessary write is triggered.
        """
        self.fb.ensure_custom_variables()
        lid = self.fb.create_lead({
            "email": "clean@example.com",
            "first_name": "Clean",
            "last_name": "Tester",
            "custom_variables": [
                {"name": "record_id", "value": "rec-1"},
                {"name": "contact_key", "value": "rec-1-c1"},
                {"name": "client", "value": "productive"},
                {"name": "subject_1", "value": "subject for em1"},
                {"name": "body_1", "value": "<p>body for em1</p>"},
                # Threaded shape: subject_2 and subject_3 are already empty.
                {"name": "subject_2", "value": ""},
                {"name": "body_2", "value": "<p>body for em2</p>"},
                {"name": "subject_3", "value": ""},
                {"name": "body_3", "value": "<p>body for em3</p>"},
                # Out-of-range variables are already empty strings.
                {"name": "subject_4", "value": ""},
                {"name": "body_4", "value": ""},
                {"name": "subject_5", "value": ""},
                {"name": "body_5", "value": ""},
                {"name": "subject_6", "value": ""},
                {"name": "body_6", "value": ""},
            ],
        })["id"]

        rec = _record("rec-1", "clean@example.com", "Clean")
        rec["contacts"][0]["bison_lead_id"] = lid
        store.save([rec])

        row = campaigns.new_campaign(CID, "productive", "Stale vars test")
        # DECLARED, NOT INHERITED. `bisonfactory._plan` refuses a
        # campaign carrying no `cadence_steps`: the fallback through
        # the client config is what let a live campaign be staged
        # against a cadence it never chose. This is exactly what the
        # fallback would have produced, so the behaviour under test is
        # unchanged - the campaign now SAYS what it runs.
        row["cadence_steps"] = [dict(s) for s in cadence.steps_for(
            None, config=THREE_STEP_CONFIG)]
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        prov = self.fb.create_campaign(
            bisonfactory.provider_campaign_name(row))
        row["bison_campaign_id"] = prov["id"]
        campaigns.save([row])

        report = self._stage()

        refresh_lines = [line for line in report["did"]
                         if "refreshed" in line and str(lid) in line]
        self.assertEqual(refresh_lines, [],
                         "a lead with all out-of-range variables already "
                         "empty should not trigger an update")


if __name__ == "__main__":
    unittest.main()
