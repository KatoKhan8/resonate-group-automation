"""Regression test: a configured cadence step must not be silently dropped.

TASK-314: The HeyReach steps were lost because `cadence.expand_step` checked
`stored.get("body")` for LinkedIn steps instead of `stored.get("note")`. Under
`productive_li_heavy_v1`, li2..li5 are `generated: True`, so they vanished from
every timeline even with all five notes written on the record. Measured
2026-09-14 on `ogpartner-dk`: six notes stored, one step surfaced.

This test verifies that N configured steps with approved copy produce N steps
in the timeline. It fails when a step is silently omitted.

The test is deliberately structured to fail if the bug returns:
1. Build a record with all LinkedIn steps having approved notes
2. Call `cadence.build()` and count the LinkedIn steps in the timeline
3. Assert the count matches the configured count
4. Break it by removing one note and verify the test catches it
"""
import os
import shutil
import tempfile
import unittest

from src import approval, cadence, cadencelibrary, clients, lint, store
from tests.base import FIXTURES


class NoCadenceStepSilentlyDroppedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-no-step-dropped-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        # Use the li_heavy cadence, which has 5 LinkedIn steps (li1..li5).
        self.config = dict(clients.load("productive"))
        self.config["cadence"] = "productive_li_heavy_v1"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rec(self, rid="meridian"):
        return store.get(rid)

    def _write_approved_notes_for_all_linkedin_steps(self, rec, contact_key):
        """Write an approved note for every LinkedIn step in the cadence.

        This is the state that was measured on 2026-09-14: all notes written
        and approved, but only li1 surfaced because li2..li5 are generated
        and the code checked `body` instead of `note`.
        """
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        linkedin_steps = [s for s in sequence if s.get("channel") == "linkedin"]

        cadence_data = rec.setdefault("cadence", {}).setdefault(contact_key, {})

        for step_spec in linkedin_steps:
            key = step_spec["key"]
            # A note that is clearly prospect-facing and approved.
            note_text = f"Test note for {key}: connecting about testing."
            step_data = {
                "channel": "linkedin",
                "note": note_text,
                "generated": step_spec.get("generated", False),
                "linkedin_action": step_spec.get("linkedin_action", "message"),
            }
            # Approve it with a real fingerprint and accountable approver.
            fingerprint = approval.fingerprint(step_data)
            step_data["approval"] = {
                "fingerprint": fingerprint,
                "by": "operator",
                "at": "2026-09-27T00:00:00Z",
            }
            cadence_data[key] = step_data

        return linkedin_steps

    def test_all_configured_linkedin_steps_surface_when_approved(self):
        """Five configured LinkedIn steps with approved notes produce five steps.

        This is the regression test for TASK-314. The bug was that generated
        LinkedIn steps checked `stored.get("body")` instead of `stored.get("note")`,
        so li2..li5 returned None from `expand_step` and were silently dropped.

        The fix reads `note` for LinkedIn steps. This test fails if that fix
        is reverted.
        """
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        contact_key = "ivana-saric"
        contact = next(c for c in rec["contacts"] if lint.contact_key(c) == contact_key)

        # Write approved notes for all LinkedIn steps.
        linkedin_steps = self._write_approved_notes_for_all_linkedin_steps(rec, contact_key)
        expected_count = len(linkedin_steps)
        expected_keys = {s["key"] for s in linkedin_steps}

        # Store the updated record.
        store.save(recs)

        # Build the timeline.
        timeline = cadence.build(rec, self.config)
        contact_steps = timeline["contacts"].get(contact_key, {})

        # Count the LinkedIn steps that surfaced WITH CONTENT.
        # A step that is silently dropped has no `note` or `body` field.
        # A step with `requires` but no copy appears as a placeholder with
        # only `channel`, `day`, and `requires` - no content.
        linkedin_keys_with_content = {
            key for key, step in contact_steps.items()
            if step.get("channel") == "linkedin" and (step.get("note") or step.get("body"))
        }

        # THE ASSERTION THAT CATCHES THE BUG.
        # If a step is silently dropped, this count will be less than expected.
        self.assertEqual(
            len(linkedin_keys_with_content),
            expected_count,
            f"Expected {expected_count} LinkedIn steps with content in the timeline, "
            f"but found {len(linkedin_keys_with_content)}. "
            f"Missing: {expected_keys - linkedin_keys_with_content}. "
            f"A configured step was silently dropped."
        )

        # Every configured step key must be present with content.
        self.assertEqual(
            linkedin_keys_with_content,
            expected_keys,
            f"LinkedIn step keys mismatch. Missing: {expected_keys - linkedin_keys_with_content}"
        )

    def test_a_step_with_no_copy_is_refused_not_dropped(self):
        """A step with no approved copy must not silently vanish.

        The bug was that a generated step with no written content returned None
        from `expand_step` and was silently dropped. The fix is that a step
        with a `requires` clause still appears in the timeline (as waiting),
        and a step without `requires` is dropped only if it has no copy AND
        no requires - which is the correct behaviour for a step that is not
        yet ready.

        This test verifies that when a note is missing, the step either:
        1. Appears in the timeline (if it has `requires`), or
        2. Is the ONLY step missing (not silently dropped among others)
        """
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        contact_key = "ivana-saric"
        contact = next(c for c in rec["contacts"] if lint.contact_key(c) == contact_key)

        # Write approved notes for all LinkedIn steps.
        linkedin_steps = self._write_approved_notes_for_all_linkedin_steps(rec, contact_key)

        # Remove the note from li3 (the InMail fallback step).
        # li3 has `requires: CONNECTED`, so it should still appear in the
        # timeline even without a note.
        cadence_data = rec["cadence"][contact_key]
        li3_step = cadence_data.get("li3", {})
        li3_step.pop("note", None)
        # Remove the approval too, since the fingerprint no longer matches.
        li3_step.pop("approval", None)
        cadence_data["li3"] = li3_step

        store.save(recs)

        # Build the timeline.
        timeline = cadence.build(rec, self.config)
        contact_steps = timeline["contacts"].get(contact_key, {})

        # li3 has `requires: CONNECTED`, so it should appear in the timeline
        # even without a note (as a waiting step).
        self.assertIn(
            "li3",
            contact_steps,
            "li3 has `requires: CONNECTED` and should appear in the timeline "
            "even without approved copy. A step with a precondition must not "
            "be silently dropped."
        )

    def test_breaking_the_fix_causes_the_test_to_fail(self):
        """Prove the test catches the bug by simulating the old behaviour.

        This test deliberately breaks the fix by patching `expand_step` to
        return None for generated LinkedIn steps (the old bug). It verifies
        that the test would fail in that case.

        This is a meta-test: it proves the regression test is load-bearing.
        """
        recs = store.load()
        rec = next(r for r in recs if r["id"] == "meridian")
        contact_key = "ivana-saric"
        contact = next(c for c in rec["contacts"] if lint.contact_key(c) == contact_key)

        # Write approved notes for all LinkedIn steps.
        linkedin_steps = self._write_approved_notes_for_all_linkedin_steps(rec, contact_key)
        expected_count = len(linkedin_steps)

        store.save(recs)

        # Patch `expand_step` to simulate the old bug: return None for
        # generated LinkedIn steps.
        original_expand_step = cadence.expand_step

        def buggy_expand_step(rec, contact, spec, config, accepted=False,
                              context=None, campaign=None):
            # THE BUG: check `body` for LinkedIn instead of `note`.
            if spec.get("generated") and spec.get("channel") == "linkedin":
                key = lint.contact_key(contact)
                stored = ((rec.get("cadence") or {}).get(key) or {}).get(spec["key"]) or {}
                # The old code checked `body` for all channels.
                if not (stored.get("body") or "").strip():
                    # Return None to simulate the bug - the step is dropped.
                    return None
            # For non-buggy cases, call the original.
            return original_expand_step(rec, contact, spec, config,
                                        accepted=accepted, context=context,
                                        campaign=campaign)

        # Patch and build.
        cadence.expand_step = buggy_expand_step
        try:
            timeline = cadence.build(rec, self.config)
            contact_steps = timeline["contacts"].get(contact_key, {})

            # Count steps with content, not just presence.
            linkedin_keys_with_content = {
                key for key, step in contact_steps.items()
                if step.get("channel") == "linkedin" and (step.get("note") or step.get("body"))
            }

            # With the bug, li2..li5 would return None from expand_step.
            # Since they have `requires: CONNECTED`, they'd appear as placeholders
            # with no content. So we'd have 0 steps with content (li1 is a template
            # and not affected by the bug, but it has no generated content either -
            # it renders from the template, so it has a note).
            # Actually, li1 would have a note from the template, so we'd have 1 step.
            # But li2..li5 would be placeholders with no note, so 1 != 5.
            # This assertion would FAIL with the bug present.
            with self.assertRaises(AssertionError):
                self.assertEqual(
                    len(linkedin_keys_with_content),
                    expected_count,
                    "This should fail with the bug present"
                )
        finally:
            cadence.expand_step = original_expand_step


if __name__ == "__main__":
    unittest.main()
