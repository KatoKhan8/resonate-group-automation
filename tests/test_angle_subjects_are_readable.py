"""A subject line names the client's topic, never this system's angle key.

`comparable_proof` and `comparable_proof_short` interpolate `{angle_word}`,
and `template_vars` set it to `angle.replace("_", " ")` - the INTERNAL KEY
from the client config. Productive's keys are `finance`, `delivery`, `ops` and
`founder`, so real subjects read:

    "how teams your size handle founder"
    "how teams your size handle ops"

The client's actual words are the config VALUES, but substituting the founder
phrase gives 77 characters against `lint.MAX_SUBJECT = 60`. Widening a lint
rule to make a draft pass is forbidden, so the wording gives instead: a client
may declare a short label per angle, derived from its own positioning.

The budget is exact and is asserted rather than commented. "how teams your
size handle " is 27 characters and 59 is the longest passing subject, leaving
32. `test_the_budget_is_real` walks every template carrying `{angle_word}` and
proves 32 passes and 33 does not, so the constant cannot go stale if a third
template with a longer prefix is ever added.

The ladder never returns the key. That is the whole point: a client who
configures nothing gets their own first clause when it fits and a generic
topic when it does not, and neither is an identifier.
"""
import unittest

from src import cadence, clients, lint

PREFIX = "how teams your size handle "


class AngleSubjectsAreReadable(unittest.TestCase):

    def setUp(self):
        self.config = clients.load("productive")

    def subject_for(self, angle, clause=""):
        return PREFIX + cadence.angle_word(angle, clause, self.config)

    # ------------------------------------------------------------ the defect

    def test_no_angle_key_reaches_a_subject(self):
        for angle in ("finance", "delivery", "ops", "founder"):
            subject = self.subject_for(angle)
            self.assertNotIn(angle, subject, subject)

    def test_every_productive_angle_passes_the_subject_rule(self):
        for angle in ("finance", "delivery", "ops", "founder"):
            subject = self.subject_for(angle)
            self.assertLess(len(subject), lint.MAX_SUBJECT, subject)

    def test_the_configured_label_is_what_renders(self):
        self.assertEqual(self.subject_for("founder"),
                         PREFIX + "profitability on Monday")

    # ------------------------------------------------------------ the budget

    def _using_angle_word(self):
        using = {name: t for name, t in cadence.TEMPLATES.items()
                 if "{angle_word}" in (t.get("subject") or "")}
        self.assertTrue(using, "no template interpolates {angle_word}")
        return using

    def test_the_budget_is_real(self):
        """`ANGLE_WORD_MAX` is SAFE: every subject fits at it.

        Per template, because this is the safety half and a single template
        over the line is a subject `lint` refuses and a step that never
        ships.
        """
        for name, template in self._using_angle_word().items():
            fits = template["subject"].replace(
                "{angle_word}", "x" * cadence.ANGLE_WORD_MAX)
            self.assertLess(len(fits), lint.MAX_SUBJECT, name)

    def test_the_budget_is_tight(self):
        """`ANGLE_WORD_MAX` is the LARGEST safe value, asserted over the SET.

        WHY THIS IS NOT PER TEMPLATE, AND WHY IT USED TO BE. Until 2026-09-24
        both halves were asserted template by template, which says every
        `{angle_word}` subject sits exactly on the 60-character line. That was
        true while `comparable_proof` was the only one - its prefix is 27 and
        27 + 32 = 59 - and it is the wrong generalisation: a SHORTER prefix is
        strictly safer, and asserting it away means a safe template fails.

        The four step-4/step-5 templates approved 2026-09-24 have prefixes of
        22 and 24, so they fit with 3 to 5 characters of slack and the old
        per-template assertion went red on all four. The copy is fine; the
        assertion was over-specified.

        What is actually worth defending is that the CONSTANT is right:
        32 is safe for every template (above) and 33 is not safe for at least
        one (here). Raise `ANGLE_WORD_MAX` and the test above goes red; lower
        it and this one does. Both directions are still caught.
        """
        tight = [name for name, template in self._using_angle_word().items()
                 if len(template["subject"].replace(
                     "{angle_word}",
                     "x" * (cadence.ANGLE_WORD_MAX + 1))) >= lint.MAX_SUBJECT]
        self.assertTrue(
            tight,
            f"every {{angle_word}} subject still fits at "
            f"{cadence.ANGLE_WORD_MAX + 1} characters, so ANGLE_WORD_MAX is "
            f"{cadence.ANGLE_WORD_MAX} for no reason and is throwing away "
            f"subject length the client could be using")

    # ------------------------------------------------------------ the ladder

    def test_a_configured_label_wins(self):
        self.assertEqual(
            cadence.angle_word("ops", "a much longer clause than the label",
                               self.config),
            "utilisation and capacity")

    def test_no_label_falls_back_to_the_clients_own_clause(self):
        self.assertEqual(
            cadence.angle_word("nosuchangle", "utilisation", self.config),
            "utilisation")

    def test_an_over_long_clause_falls_back_to_the_generic_topic(self):
        self.assertEqual(
            cadence.angle_word("nosuchangle", "x" * 80, self.config),
            cadence.FALLBACK_ANGLE_WORD)

    def test_an_over_long_configured_label_is_not_used(self):
        config = dict(self.config, angle_labels={"ops": "y" * 80})
        self.assertEqual(cadence.angle_word("ops", "utilisation", config),
                         "utilisation")

    def test_no_branch_ever_returns_the_key(self):
        """The defect was the key reaching a subject. No path may restore it."""
        for clause in ("", "utilisation", "x" * 80):
            for config in (self.config, {}, {"angle_labels": {}}):
                got = cadence.angle_word("founder", clause, config)
                self.assertNotEqual(got, "founder")
                self.assertNotIn("founder", got)

    # -------------------------------------------------- backward compatible

    def test_a_client_with_no_labels_still_renders_and_lints(self):
        demo = clients.load("demo")
        self.assertEqual(clients.angle_labels(demo), {})
        for angle, phrase in (clients.angles_for(demo, "champion") or {}).items():
            subject = PREFIX + cadence.angle_word(
                angle, str(phrase).split(",")[0].strip(), demo)
            self.assertLess(len(subject), lint.MAX_SUBJECT, subject)
            self.assertNotIn(angle, subject)

    def test_angles_for_still_returns_strings(self):
        """Fails the day somebody nests labels under `angles` and quietly
        feeds a dict repr into evidence scoring."""
        angles = clients.angles_for(self.config, "champion")
        # The operator expanded the champion families on 2026-09-09: `ops` was
        # renamed `operations` so it matches the routing family name that
        # `personas.default_angle` compares against, and `resource_management`
        # was added. Asserted as a set because the guard here is that each
        # VALUE is a string - a nested label dict fed into evidence scoring is
        # what this test exists to catch - and the key set is what makes that
        # check meaningful rather than vacuous.
        self.assertEqual(set(angles),
                         {"finance", "delivery", "operations",
                          "resource_management"})
        for value in angles.values():
            self.assertIsInstance(value, str)


if __name__ == "__main__":
    unittest.main()
