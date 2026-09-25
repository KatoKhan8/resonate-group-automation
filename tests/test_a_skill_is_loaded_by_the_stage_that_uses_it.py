"""A skill with no consumer is documentation, not a stage.

The audit found five disconnected modules. This test makes a sixth
impossible: every registered skill must name the pipeline stage that loads
it, and ``registry()`` refuses to return a skill whose consumer is empty.
"""
import sys
import unittest

sys.path.insert(0, ".")
from src import skills


class TestEverySkillHasAConsumer(unittest.TestCase):

    def test_registry_has_exactly_five_skills(self):
        reg = skills.registry()
        self.assertEqual(len(reg), 5, "expected 5 skills, got %d: %s"
                         % (len(reg), sorted(reg)))

    def test_every_skill_has_a_consumer(self):
        reg = skills.registry()
        without = [name for name, skill in reg.items() if not skill.consumer]
        self.assertFalse(
            without,
            "skills with no consumer: %s — a skill with no consumer is "
            "documentation, not a stage" % ", ".join(sorted(without))
        )

    def test_load_returns_a_skill_with_all_required_fields(self):
        s = skills.load("cold_email_writing")
        self.assertTrue(s.output_schema, "output_schema is empty")
        self.assertTrue(s.validation, "validation is empty")
        self.assertTrue(s.examples_bad, "examples_bad is empty")
        self.assertTrue(s.consumer, "consumer is empty")
        self.assertTrue(s.procedure, "procedure is empty")
        self.assertTrue(s.purpose, "purpose is empty")

    def test_consumer_names_a_real_stage(self):
        reg = skills.registry()
        expected_consumers = {"stage_a", "stage_b", "stage_e", "stage_f"}
        actual = {s.consumer for s in reg.values()}
        self.assertTrue(
            actual <= expected_consumers,
            "unknown consumer(s): %s; expected subset of %s"
            % (sorted(actual - expected_consumers), sorted(expected_consumers))
        )

    def test_two_skills_share_stage_f(self):
        reg = skills.registry()
        stage_f_skills = [n for n, s in reg.items() if s.consumer == "stage_f"]
        self.assertEqual(
            sorted(stage_f_skills),
            ["cold_email_writing", "linkedin_writing"],
            "stage_f should serve cold_email_writing and linkedin_writing"
        )

    def test_load_unknown_skill_raises(self):
        with self.assertRaises(KeyError):
            skills.load("nonexistent_skill")


if __name__ == "__main__":
    unittest.main()
