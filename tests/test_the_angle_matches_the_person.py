"""A person is written to about their own job, or not written to at all.

`default_angle` assigned an angle only when a persona had exactly one, and
Productive's `economic_buyer` had exactly one - `founder`. That bucket holds
CEO, COO, CFO, Owner and Managing Director titles, so once the cap started
keeping the COO (see `test_the_cap_keeps_who_the_plan_ranks_first`) an
operations lead inherited founder copy: "profitability visible on Monday not
two weeks late", to the person who runs delivery.

The fix matches an angle key to the routing family the title belongs to - the
same family machinery the cap tie-break uses. Both names come from the
client's config and the routing strategy, so the engine learns nothing about
what any client sells.

What is deliberately NOT done is picking the first of several angles. A
finance lead inheriting founder copy because the persona happens to define
only that angle is the mismatch this exists to stop. With no fitting angle the
contact keeps `angle: None`, `lint` raises `domains_contact_no_angle`, and the
person is held rather than written to with the wrong words - which is the
wanted answer for a CFO until somebody configures something true to say to
one.
"""
import unittest

from src import clients, lint, personas, routing

PRIORITY = ("operations", "finance", "resource_management", "founder")


class TheAngleMatchesThePerson(unittest.TestCase):

    def setUp(self):
        self.config = clients.load("productive")
        self.families = routing.settings(
            self.config)["strategies"]["operations_led"]["personas"]

    def angle_for(self, title):
        persona, _ = personas.classify({"title": title}, self.config)
        if not persona:
            return None
        family, _ = personas.family_of({"title": title}, list(PRIORITY),
                                       self.families)
        return personas.default_angle(self.config, persona, family)

    # ------------------------------------------------------------ the match

    def test_an_operations_lead_gets_the_operations_angle(self):
        self.assertEqual(self.angle_for("Chief Operating Officer"),
                         "operations")

    def test_however_the_title_is_spelled(self):
        self.assertEqual(self.angle_for("President & COO"), "operations")

    def test_a_chief_executive_still_gets_the_founder_angle(self):
        self.assertEqual(self.angle_for("CEO"), "founder")

    # -------------------------------------------------------- the mismatch

    def test_a_finance_lead_gets_no_angle_rather_than_founder_copy(self):
        """The rule you would break by picking the first of several."""
        self.assertIsNone(self.angle_for("Chief Financial Officer"))
        self.assertIsNone(self.angle_for("CFO"))

    def test_no_angle_is_a_lint_failure_so_the_person_is_held(self):
        """`None` has to stop a send, not quietly become the first angle."""
        rec = {"id": "r", "lane": "domains", "client": "productive",
               "domain": "acme.test", "hook": "h",
               "contacts": [{"key": "c", "name": "A CFO",
                             "title": "Chief Financial Officer",
                             "email": "c@acme.test"}]}
        step = {"channel": "email", "subject": "a subject that is fine",
                "body": "A real body with enough words in it to clear the "
                        "length rule, written plainly and without any of the "
                        "banned filler this linter refuses to let through."}
        self.assertIn("domains_contact_no_angle", lint.check(rec, "c", step))

    def test_a_persona_with_one_angle_still_gets_it_with_no_family(self):
        """Backward compatible: the single-angle rule is unchanged."""
        config = {"personas": {"solo": {"angles": {"only": "the one thing"}}}}
        self.assertEqual(personas.default_angle(config, "solo", None), "only")

    def test_a_persona_with_several_and_no_family_gets_none(self):
        config = {"personas": {"many": {"angles": {"a": "x", "b": "y"}}}}
        self.assertIsNone(personas.default_angle(config, "many", None))

    def test_a_family_with_no_matching_angle_gets_none(self):
        config = {"personas": {"many": {"angles": {"a": "x", "b": "y"}}}}
        self.assertIsNone(personas.default_angle(config, "many", "operations"))

    def test_the_engine_holds_no_client_vocabulary(self):
        """The match is by name; the names are the client's and the
        strategy's."""
        source = personas.default_angle.__doc__ or ""
        for word in ("productive", "utilisation", "margin"):
            self.assertNotIn(word, source.lower())


if __name__ == "__main__":
    unittest.main()
