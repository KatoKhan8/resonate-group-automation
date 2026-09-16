"""TASK-179: The cadence and the graph must agree on step count.

THE DEFECT THIS PINS. The cadence `PRODUCTIVE_LI_HEAVY_V1` defined six
LinkedIn steps (li1-li6), but the HeyReach graph had positions for only five
(li1-li5). li6 existed on paper and never fired at the provider. A step that
silently never fires is a whole message nobody sends and no gate complains
about.

The fix was to remove li6 from the cadence. The cadence now defines five
LinkedIn steps (li1-li5), and every step has a graph position.

This test fails if the cadence and the graph ever disagree on step count
again. It checks that every LinkedIn step in the cadence has a corresponding
entry in COPY_MAPPING, and every entry in COPY_MAPPING corresponds to a
LinkedIn step in the cadence.
"""
import unittest

from src import cadencelibrary, heyreachfactory


class CadenceGraphAgreement(unittest.TestCase):
    """The cadence and the graph must agree on LinkedIn step count."""

    def test_every_cadence_step_has_a_graph_position(self):
        """Every LinkedIn step in the cadence has a COPY_MAPPING entry.

        A cadence step without a graph position is a message that never fires.
        This test fails if the cadence names a step the graph has no position
        for.
        """
        cadence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        linkedin_steps = [
            step for step in cadence
            if step.get("channel") == "linkedin"
        ]
        cadence_keys = {step["key"] for step in linkedin_steps}
        mapping_keys = set(heyreachfactory.COPY_MAPPING.keys())

        missing_from_graph = cadence_keys - mapping_keys
        self.assertEqual(
            missing_from_graph, set(),
            f"cadence steps with no graph position: {sorted(missing_from_graph)}. "
            f"Every cadence step must have a COPY_MAPPING entry, or it never fires."
        )

    def test_every_graph_position_has_a_cadence_step(self):
        """Every COPY_MAPPING entry corresponds to a cadence step.

        A graph position without a cadence step is a role that can never be
        filled. This test fails if the graph names a role the cadence does not
        define.
        """
        cadence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        linkedin_steps = [
            step for step in cadence
            if step.get("channel") == "linkedin"
        ]
        cadence_keys = {step["key"] for step in linkedin_steps}
        mapping_keys = set(heyreachfactory.COPY_MAPPING.keys())

        missing_from_cadence = mapping_keys - cadence_keys
        self.assertEqual(
            missing_from_cadence, set(),
            f"graph positions with no cadence step: {sorted(missing_from_cadence)}. "
            f"Every COPY_MAPPING entry must correspond to a cadence step."
        )

    def test_cadence_and_graph_agree_on_step_count(self):
        """The cadence and the graph define the same number of LinkedIn steps.

        This is the load-bearing check. If the cadence defines N steps and the
        graph has positions for M steps, and N != M, then either the cadence
        names steps that never fire or the graph has positions that can never
        be filled.
        """
        cadence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        linkedin_steps = [
            step for step in cadence
            if step.get("channel") == "linkedin"
        ]
        cadence_count = len(linkedin_steps)
        mapping_count = len(heyreachfactory.COPY_MAPPING)

        self.assertEqual(
            cadence_count, mapping_count,
            f"cadence defines {cadence_count} LinkedIn steps but the graph has "
            f"positions for {mapping_count}. They must agree."
        )

    def test_li6_does_not_exist(self):
        """li6 was removed from the cadence because it had no graph position.

        This test pins the fix. If somebody adds li6 back to the cadence
        without also adding a graph position, this test fails.
        """
        cadence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        linkedin_keys = {
            step["key"] for step in cadence
            if step.get("channel") == "linkedin"
        }
        self.assertNotIn(
            "li6", linkedin_keys,
            "li6 was removed from the cadence because it had no graph position. "
            "If you are adding it back, you must also add a COPY_MAPPING entry."
        )
        self.assertNotIn(
            "li6", heyreachfactory.COPY_MAPPING,
            "li6 has no graph position. If you are adding it to COPY_MAPPING, "
            "you must also add it to the cadence."
        )


if __name__ == "__main__":
    unittest.main()
