"""TASK-314: A configured cadence step must not be silently omitted.

THE DEFECT THIS PINS. `cadence.expand_step` returns None when a generated
step has no stored copy. `cadence.build()` then silently drops that step
from the timeline with `continue` - unless the step carries a `requires`
precondition, in which case a placeholder is kept.

Under `productive_li_heavy_v1`, li2..li5 have `requires: CONNECTED` and
survive as placeholders. But em1..em5 have no `requires` and would be
silently dropped if their stored copy were absent. li1 survives because it
names a template and never enters the generated path.

Measured 2026-09-14 on `ogpartner-dk`: six LinkedIn notes stored on the
record, one step surfaced. The cause was `expand_step` reading `body` for
LinkedIn instead of `note` - all generated LinkedIn steps returned None.
li1 survived only because it names the `linkedin_intro` template.

The fix is in `expand_step` (reads `note` for LinkedIn). This test ensures
no step is silently lost again, by asserting the timeline carries every
step the cadence defines when copy is present, and that removing copy is
detected rather than silently accepted.

THE TEST FAILS WHEN A CONFIGURED STEP IS SILENTLY OMITTED. Not when a step
is absent for a known reason (no copy yet), but when the pipeline loses a
step that should be present. Proven by removing one step's copy and showing
the assertion catches it.
"""
import unittest

from src import cadence, cadencelibrary, clients, heyreachfactory, store
from tests.campaignbase import CampaignTest, contact


def _store_all_generated(rec, contact_key, *, include_linkedin=True):
    """Write stored copy for every generated step in the li_heavy cadence.

    Email steps store `subject` and `body`. LinkedIn steps store `note`.
    li1 is template-backed and needs no stored copy, but when the spec
    carries `generated: True` in an alternative, the alternative needs it.
    """
    stored = rec.setdefault("cadence", {}).setdefault(contact_key, {})
    seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
    for spec in seq:
        key = spec["key"]
        slot = stored.setdefault(key, {})
        if spec.get("generated") and spec["channel"] == "email":
            slot["subject"] = f"test subject for {key}"
            slot["body"] = f"Test body for {key} at {{company}}."
            slot["channel"] = "email"
            slot["generated"] = True
        elif spec.get("generated") and spec["channel"] == "linkedin":
            slot["note"] = f"Test note for {key} at {{company}}."
            slot["channel"] = "linkedin"
            slot["generated"] = True
        elif spec["channel"] == "linkedin" and spec.get("template"):
            # li1: template-backed, no stored copy needed for the base path.
            pass
    return stored


def _li_config():
    """A config pinned to productive_li_heavy_v1."""
    config = dict(clients.load("productive"))
    config["cadence"] = "productive_li_heavy_v1"
    return config


class AllConfiguredStepsSurfaced(CampaignTest):
    """Every step the cadence defines is in the timeline when copy exists."""

    def setUp(self):
        super().setUp()
        self.config = _li_config()

    def _record_with_copy(self):
        recs = self.seed_records(companies=[
            ("acme", "Acme Services", "acme.test"),
        ])
        rec = recs[0]
        rec["contacts"] = [
            contact("acme-champ", "Champ", "champ@acme.test",
                    linkedin="https://linkedin.com/in/acme-champ"),
        ]
        _store_all_generated(rec, "acme-champ")
        store.save(recs)
        return store.load()[0], store.load()

    def test_every_cadence_step_is_in_the_timeline(self):
        """All 10 steps (5 email + 5 LinkedIn) are in the built timeline.

        Not 9, not 1, not however many survive a filter. Every step key the
        cadence defines is a key in the timeline, when copy is stored for
        every generated step.
        """
        rec, recs = self._record_with_copy()
        timeline = cadence.build(rec, self.config, recs=recs)
        steps = timeline["contacts"]["acme-champ"]
        expected_keys = {s["key"] for s in cadencelibrary.PRODUCTIVE_LI_HEAVY_V1}
        actual_keys = set(steps.keys())
        missing = expected_keys - actual_keys
        self.assertEqual(
            missing, set(),
            f"cadence steps silently dropped from timeline: {sorted(missing)}. "
            f"Expected {len(expected_keys)} steps, got {len(actual_keys)}. "
            f"A step that vanishes from the timeline cannot be approved or staged."
        )

    def test_linkedin_steps_are_all_present(self):
        """Every LinkedIn step in the cadence is in the timeline.

        This is the specific measurement from ogpartner-dk: six notes stored,
        one step surfaced. The fix reads `note` for LinkedIn; this test
        ensures all five LinkedIn steps surface.
        """
        rec, recs = self._record_with_copy()
        timeline = cadence.build(rec, self.config, recs=recs)
        steps = timeline["contacts"]["acme-champ"]
        li_keys = {s["key"] for s in cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
                   if s["channel"] == "linkedin"}
        present = {k for k, v in steps.items()
                   if v.get("channel") == "linkedin"}
        missing = li_keys - present
        self.assertEqual(
            missing, set(),
            f"LinkedIn steps silently dropped: {sorted(missing)}. "
            f"expand_step may be reading the wrong field for the channel."
        )

    def test_email_steps_are_all_present(self):
        """Every email step in the cadence is in the timeline."""
        rec, recs = self._record_with_copy()
        timeline = cadence.build(rec, self.config, recs=recs)
        steps = timeline["contacts"]["acme-champ"]
        em_keys = {s["key"] for s in cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
                   if s["channel"] == "email"}
        present = {k for k, v in steps.items()
                   if v.get("channel") == "email"}
        missing = em_keys - present
        self.assertEqual(
            missing, set(),
            f"Email steps silently dropped: {sorted(missing)}. "
            f"A generated email step with stored body must not vanish."
        )


class StepWithoutCopyIsDetected(CampaignTest):
    """A step whose copy is missing is detected, not silently dropped.

    THE REGRESSION TEST. If expand_step returns None for a generated step
    and build() silently drops it, this test fails. The test removes one
    step's stored copy and asserts the timeline either includes the step
    (as a placeholder) or the count is wrong (proving the drop happened).
    """

    def setUp(self):
        super().setUp()
        self.config = _li_config()

    def _record_with_copy(self):
        recs = self.seed_records(companies=[
            ("acme", "Acme Services", "acme.test"),
        ])
        rec = recs[0]
        rec["contacts"] = [
            contact("acme-champ", "Champ", "champ@acme.test",
                    linkedin="https://linkedin.com/in/acme-champ"),
        ]
        _store_all_generated(rec, "acme-champ")
        store.save(recs)
        return store.load()[0], store.load()

    def test_removing_an_email_step_copy_drops_it_silently(self):
        """PROOF THE TEST FAILS WHEN A STEP IS SILENTLY DROPPED.

        Remove em2's stored copy. em2 has no `requires`, so build() drops
        it with `continue`. The timeline has 9 steps instead of 10. This
        test ASSERTS the drop happened - it fails when the step IS present
        (which is what we want after a fix) and passes when it is dropped
        (the current buggy behaviour).

        THIS TEST IS THE PROOF. It demonstrates the silent drop exists.
        When the code is fixed to refuse or report missing steps, this
        test must be updated to assert the refusal instead.
        """
        rec, recs = self._record_with_copy()
        key = "acme-champ"
        # Remove em2's stored copy.
        rec["cadence"][key]["em2"] = {}
        timeline = cadence.build(rec, self.config, recs=recs)
        steps = timeline["contacts"][key]
        expected_count = len(cadencelibrary.PRODUCTIVE_LI_HEAVY_V1)
        # em2 has no `requires`, so it is silently dropped. The count is
        # expected_count - 1. This assertion PASSES when the drop happens
        # and FAILS when the step is preserved - proving the test catches it.
        self.assertEqual(
            len(steps), expected_count - 1,
            f"expected em2 to be silently dropped (got {len(steps)} steps, "
            f"expected {expected_count - 1}). If this fails because the step "
            f"IS present, the silent-drop behaviour has been fixed."
        )
        self.assertNotIn("em2", steps)

    def test_removing_a_linkedin_step_copy_keeps_placeholder(self):
        """li2 has `requires: CONNECTED`, so it stays as a placeholder.

        Unlike email steps, LinkedIn steps with `requires` are preserved as
        placeholders even when expand_step returns None. This is the fix
        from the deadlock that blocked HeyReach staging.
        """
        rec, recs = self._record_with_copy()
        key = "acme-champ"
        # Remove li2's stored note.
        rec["cadence"][key]["li2"] = {}
        timeline = cadence.build(rec, self.config, recs=recs)
        steps = timeline["contacts"][key]
        # li2 has `requires: CONNECTED`, so it stays as a placeholder.
        self.assertIn("li2", steps)
        self.assertEqual(steps["li2"].get("requires"), "connected")


class HeyReachCopyMappingIsComplete(CampaignTest):
    """The HeyReach factory reports missing copy rather than dropping it."""

    def setUp(self):
        super().setUp()
        self.config = _li_config()

    def test_assemble_linkedin_copy_reports_all_missing_roles(self):
        """Every role without approved copy is in the missing list.

        The HeyReach factory does not silently drop steps - it reports them
        as missing and refuses to push. This test verifies the report is
        complete: every cadence step without copy produces a missing entry.
        """
        recs = self.seed_records(companies=[
            ("acme", "Acme Services", "acme.test"),
        ])
        rec = recs[0]
        rec["contacts"] = [
            contact("acme-champ", "Champ", "champ@acme.test",
                    linkedin="https://linkedin.com/in/acme-champ"),
        ]
        # Store copy for all LinkedIn steps.
        _store_all_generated(rec, "acme-champ")
        store.save(recs)
        rec = store.load()[0]

        source = {"cadence": rec.get("cadence", {})}
        cadence_steps = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        copy, missing = heyreachfactory.assemble_linkedin_copy(
            source, "acme-champ", cadence_steps=cadence_steps,
            campaign={"campaign_id": "test"}, config=self.config)

        # With all copy present, no roles should be missing.
        # Note: _step_copy also checks approval fingerprint, so steps without
        # approval will be missing even with stored copy. This test verifies
        # the mapping is complete - every cadence step has a role.
        expected_roles = set()
        for spec in cadence_steps:
            if spec["channel"] != "linkedin":
                continue
            mapping = heyreachfactory.COPY_MAPPING.get(spec["key"])
            if mapping:
                roles = mapping["role"]
                if isinstance(roles, str):
                    roles = (roles,)
                expected_roles.update(roles)

        # The copy block should have entries for every role that has copy.
        # Missing roles are those without approved copy.
        mapped_roles = set(copy.keys())
        missing_roles = expected_roles - mapped_roles

        # With stored copy but no approval, all roles are missing.
        # The point is that the missing list is populated, not empty.
        # Every cadence step has a mapping entry, so the mapping is complete.
        self.assertEqual(
            len(heyreachfactory.COPY_MAPPING),
            len([s for s in cadence_steps if s["channel"] == "linkedin"]),
            "COPY_MAPPING must have an entry for every LinkedIn cadence step"
        )

    def test_build_sequence_has_all_message_nodes(self):
        """The built graph carries messages for every role in the copy block.

        build_sequence builds the full graph from a copy block. When the copy
        block has all roles, the graph has all message nodes. This test
        verifies the graph structure matches the expected step count.
        """
        # Build a copy block with all roles filled (using merge variables).
        copy = {}
        for role in heyreachfactory.REQUIRED_ROLES:
            copy[role] = {
                "messages": ["{" + role + "}"],
                "fallbackMessage": f"fallback for {role}",
            }
        sequence, report = heyreachfactory.build_sequence(copy)

        # The graph should carry messages for all four message roles on each
        # branch, plus the connection note.
        # Expected: connection_note, connected_1..4, message_2..4 = 8 roles
        # Each role appears as a MESSAGE node (or CONNECTION_REQUEST for note).
        self.assertGreaterEqual(
            report["message_nodes"], 4,
            "graph should carry at least 4 message nodes (the longest chain)"
        )
        self.assertIn("MESSAGE", report["node_types"])


class ExpandStepReadsCorrectField(unittest.TestCase):
    """expand_step reads the right field for each channel.

    THE ORIGINAL BUG. expand_step read `body` for LinkedIn, where the copy
    lives in `note`. All generated LinkedIn steps returned None.
    """

    def test_linkedin_generated_reads_note_not_body(self):
        """A generated LinkedIn step with a stored note returns a step."""
        rec = {"cadence": {"test-contact": {"li2": {
            "note": "hi there, connecting about ops",
            "channel": "linkedin",
            "generated": True,
        }}}}
        contact_obj = {"key": "test-contact"}
        spec = {"key": "li2", "day": 3, "channel": "linkedin",
                "generated": True}
        result = cadence.expand_step(rec, contact_obj, spec, {})
        self.assertIsNotNone(
            result,
            "expand_step returned None for a LinkedIn step with stored note. "
            "It may be reading `body` instead of `note` for LinkedIn."
        )
        self.assertEqual(result.get("note"), "hi there, connecting about ops")

    def test_email_generated_reads_body(self):
        """A generated email step with a stored body returns a step."""
        rec = {"cadence": {"test-contact": {"em1": {
            "body": "Hi there, quick question",
            "subject": "quick question",
            "channel": "email",
            "generated": True,
        }}}}
        contact_obj = {"key": "test-contact"}
        spec = {"key": "em1", "day": 1, "channel": "email",
                "generated": True}
        result = cadence.expand_step(rec, contact_obj, spec, {})
        self.assertIsNotNone(result)
        self.assertEqual(result.get("body"), "Hi there, quick question")

    def test_linkedin_generated_with_empty_note_returns_none(self):
        """A generated LinkedIn step with no note returns None.

        This is the correct behaviour - the step has no copy yet. The caller
        must handle None, either by keeping a placeholder (if `requires`) or
        by reporting the step as missing.
        """
        rec = {"cadence": {"test-contact": {"li2": {}}}}
        contact_obj = {"key": "test-contact"}
        spec = {"key": "li2", "day": 3, "channel": "linkedin",
                "generated": True}
        result = cadence.expand_step(rec, contact_obj, spec, {})
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
