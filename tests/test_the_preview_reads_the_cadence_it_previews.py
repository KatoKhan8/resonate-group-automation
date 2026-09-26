"""TASK-343: The preview reads the cadence it previews.

The old preview in `work/v2_pages.py` hardcoded the LinkedIn days (1, 3, 8, 14)
and omitted li5 entirely. Days 8 and 14 were invented - 8 is em3's day and 14
is nothing's. The real LinkedIn days from the graph are 1, 3, 6, 10, 15.

These tests prove the preview reads from `src/cadencelibrary.py` and not from
a local table. The load-bearing test is `test_monkeypatching_a_day_changes_the
_preview`: it mutates the graph, re-renders, and asserts the preview's day
CHANGES. A preview that still shows the old number is still hardcoded.
"""
import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts import preview_cadence  # noqa: E402
from src import cadencelibrary  # noqa: E402


class PreviewReadsTheGraph(unittest.TestCase):
    """The preview renders what the graph says, not what it says locally."""

    def _li_days_from_output(self, text):
        """Extract LinkedIn step days from the text output.

        Parses lines like '  li3  day 6  message  [connected]' and returns
        {key: day}.
        """
        result = {}
        for line in text.splitlines():
            line = line.strip()
            for key in ("li1", "li2", "li3", "li4", "li5"):
                if line.startswith(key + "  day "):
                    parts = line.split()
                    day = int(parts[2])
                    result[key] = day
        return result

    def test_all_five_linkedin_steps_appear(self):
        """All five LinkedIn steps are rendered, not four.

        The old preview omitted li5. This test fails if any of the five
        LinkedIn steps is missing from the output.
        """
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        rows = preview_cadence.render_steps(sequence)
        li_keys = [r["key"] for r in rows if r["channel"] == "linkedin"]
        self.assertEqual(
            li_keys, ["li1", "li2", "li3", "li4", "li5"],
            "Expected all five LinkedIn steps. Got: %s" % li_keys)

    def test_days_match_the_graph_exactly(self):
        """Every step's day in the preview matches the graph.

        This is the basic correctness check. The old preview had li3=8 and
        li4=14, which are not LinkedIn step days in this system at all.
        """
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        graph_days = {s["key"]: s["day"] for s in sequence}
        rows = preview_cadence.render_steps(sequence)
        preview_days = {r["key"]: r["day"] for r in rows}

        for key in graph_days:
            self.assertEqual(
                preview_days[key], graph_days[key],
                "Step %s: preview says day %d but the graph says day %d. "
                "The preview must read from the graph, not restate it." % (
                    key, preview_days[key], graph_days[key]))

    def test_monkeypatching_a_day_changes_the_preview(self):
        """THE LOAD-BEARING TEST. Mutate the graph, re-render, confirm the
        preview's day CHANGES with it.

        A preview that still shows the old number after the graph changes is
        still hardcoded. This is the assertion that actually closes TASK-343.
        """
        original = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1

        # Deep-copy the sequence so we can mutate it without affecting the
        # module-level constant for other tests.
        mutated = tuple(
            dict(s, day=99) if s["key"] == "li3" else dict(s)
            for s in original
        )

        rows = preview_cadence.render_steps(mutated)
        li3_row = [r for r in rows if r["key"] == "li3"][0]

        self.assertEqual(
            li3_row["day"], 99,
            "li3's day in the preview is %d, not 99. The preview is still "
            "hardcoded and does not read from the graph." % li3_row["day"])

        # Also verify the other steps were NOT affected.
        li1_row = [r for r in rows if r["key"] == "li1"][0]
        self.assertEqual(li1_row["day"], 1)

    def test_monkeypatching_via_module_constant(self):
        """Mutate the module-level constant and confirm the preview follows.

        This is the stronger form: patch both the module constant AND the
        SEQUENCES registry (which `named()` reads from), then re-render
        through the same path the script uses. A preview that imported its
        own copy of the days would pass the tuple-level test above but fail
        this one.
        """
        original = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        original_seq = cadencelibrary.SEQUENCES["productive_li_heavy_v1"]
        mutated = tuple(
            dict(s, day=42) if s["key"] == "li4" else dict(s)
            for s in original
        )

        cadencelibrary.PRODUCTIVE_LI_HEAVY_V1 = mutated
        cadencelibrary.SEQUENCES["productive_li_heavy_v1"] = mutated
        try:
            seq = cadencelibrary.named("productive_li_heavy_v1")
            rows = preview_cadence.render_steps(seq)
            li4_row = [r for r in rows if r["key"] == "li4"][0]
            self.assertEqual(
                li4_row["day"], 42,
                "li4's day is %d after patching the graph to 42. "
                "The preview does not read from the live graph." % li4_row["day"])
        finally:
            cadencelibrary.PRODUCTIVE_LI_HEAVY_V1 = original
            cadencelibrary.SEQUENCES["productive_li_heavy_v1"] = original_seq

    def test_branch_labels_are_present(self):
        """Every LinkedIn step carries a branch label.

        The task requires showing which branch each LinkedIn message sits on,
        so a reader can see the connected vs not-connected split.
        """
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        rows = preview_cadence.render_steps(sequence)
        li_rows = [r for r in rows if r["channel"] == "linkedin"]
        for row in li_rows:
            self.assertIn(
                "branch", row,
                "Step %s has no branch label. The preview must show which "
                "branch each LinkedIn step sits on." % row["key"])
            self.assertTrue(
                row["branch"],
                "Step %s has an empty branch label." % row["key"])

    def test_connected_branch_is_labelled(self):
        """Steps requiring CONNECTED are labelled 'connected'."""
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        rows = preview_cadence.render_steps(sequence)
        for row in rows:
            if row["key"] in ("li2", "li3", "li4", "li5"):
                self.assertEqual(
                    row["branch"], "connected",
                    "Step %s requires CONNECTED but branch is %r" % (
                        row["key"], row["branch"]))

    def test_li3_carries_inmail_alternative(self):
        """li3's InMail fallback is shown in the preview."""
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        rows = preview_cadence.render_steps(sequence)
        li3 = [r for r in rows if r["key"] == "li3"][0]
        self.assertIn("alternative", li3)
        self.assertEqual(li3["alternative"]["action"], "InMail")

    def test_text_output_contains_real_days(self):
        """The text output contains the real graph days, not invented ones."""
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        text = preview_cadence.format_text(
            preview_cadence.render_steps(sequence))
        days = self._li_days_from_output(text)
        expected = {"li1": 1, "li2": 3, "li3": 6, "li4": 10, "li5": 15}
        self.assertEqual(
            days, expected,
            "Text output days %s do not match graph days %s" % (days, expected))

    def test_no_invented_days_in_output(self):
        """The old invented days (8, 14) do not appear as LinkedIn days.

        The old preview showed li3=8 and li4=14. Neither is a LinkedIn step
        day in this system. This test pins that those specific wrong numbers
        do not appear.
        """
        sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        rows = preview_cadence.render_steps(sequence)
        li_days = {r["key"]: r["day"] for r in rows
                   if r["channel"] == "linkedin"}
        # Day 8 is em3's day, not any LinkedIn step's.
        self.assertNotEqual(
            li_days.get("li3"), 8,
            "li3 is shown as day 8 - that is em3's day, not li3's. "
            "The preview is still hardcoded with the old wrong value.")
        # Day 14 is nobody's day.
        self.assertNotEqual(
            li_days.get("li4"), 14,
            "li4 is shown as day 14 - that is nobody's day. "
            "The preview is still hardcoded with the old wrong value.")


if __name__ == "__main__":
    unittest.main()
