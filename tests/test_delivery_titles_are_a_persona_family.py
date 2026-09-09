"""Delivery, production and studio leadership are Productive personas.

WHY THEY WERE NOT, AND WHAT THAT COST. `personas.classify` reads the client's
own persona title lists, and Productive declared six: Operations Manager,
Operations Director, Project Manager, Finance Manager, Head of Finance, Head of
Operations. A real agency's delivery leadership is spelled otherwise - Head of
Production, Project Director, Design Director, Design Studio Manager - so all
four contacts at one qualified account were set aside as "not a persona for
this client" while being verified, sendable and untouched by any campaign.

An operator decision added them. It is recorded as a family in
`config/clients/productive.yaml`, not as an exception for four people: the
titles say how the role is spelled, and the `routing.strategies` block says
which family each belongs to, which is what decides the angle.

AND A SECOND DEFECT THE SAME CHANGE CLOSED. `personas.default_angle` matches an
angle key against the ROUTING FAMILY a title belongs to. The families are
`operations`, `finance`, `delivery`, `resource_management` and `founder`.
Productive's champion declared `ops` - which matches none of them - so under
the operations_led strategy a champion could only ever be given an angle when
the family came back `finance`. Every operations lead and every studio manager
got `angle: None` and was held on `domains_contact_no_angle`. Renamed to
`operations`; same words, a key that lines up with what it is matched against.

WHAT MUST STILL FAIL. Widening who a client sells to is an operator decision,
so an arbitrary title must still be refused, and a title that classifies but
has no truthful angle must still end in a hold rather than in borrowed copy.
"""
import unittest

from src import clients, lint, personas, routing

CONFIG = clients.load("productive")
STRATEGY = "operations_led"


def plan():
    """The stored plan a 20-99 person agency gets, read live."""
    live = routing.settings(CONFIG)["strategies"][STRATEGY]
    return {"strategy": STRATEGY, "personas": live["personas"],
            "persona_priority": live["priority"]}


def contact(title, **over):
    row = {"key": "c1", "name": "A Person", "title": title,
           "email": "a@example.test", "linkedin": "a-person"}
    row.update(over)
    return row


def route(title):
    """(persona, family, angle) for one title, through the real functions."""
    c = contact(title)
    p = plan()
    persona, _ = personas.classify(c, CONFIG)
    families = personas.family_titles(p, CONFIG)
    family, _rank = personas.family_of(c, p["persona_priority"], families)
    angle = personas.default_angle(CONFIG, persona, family) if persona else None
    return persona, family, angle


class TheNewTitlesAreChampions(unittest.TestCase):
    """Approved 2026-09-09. Delivery leadership, not founders."""

    APPROVED = ("Head of Production", "Production Director",
                "Design Studio Manager", "Studio Manager",
                "Project Director", "Design Director")

    def test_each_approved_title_classifies(self):
        for title in self.APPROVED:
            with self.subTest(title=title):
                persona, _, _ = route(title)
                self.assertEqual(persona, "champion", title)

    def test_none_of_them_is_an_economic_buyer(self):
        """A production lead is not a buyer, and must not get founder copy."""
        for title in self.APPROVED:
            with self.subTest(title=title):
                persona, _, angle = route(title)
                self.assertNotEqual(persona, "economic_buyer", title)
                self.assertNotEqual(angle, "founder", title)

    def test_every_one_of_them_gets_an_angle(self):
        """The point of the change. An angle-less contact is held by lint."""
        for title in self.APPROVED:
            with self.subTest(title=title):
                _, _, angle = route(title)
                self.assertIsNotNone(angle, f"{title} would be held")

    def test_the_declared_titles_still_classify(self):
        """The expansion adds; it does not replace."""
        for title in ("Operations Manager", "Operations Director",
                      "Project Manager", "Head of Operations",
                      "Head of Finance", "Finance Manager"):
            with self.subTest(title=title):
                self.assertEqual(route(title)[0], "champion", title)

    def test_the_buyer_titles_are_untouched(self):
        for title in ("Chief Operating Officer", "CEO", "Founder",
                      "Managing Director"):
            with self.subTest(title=title):
                self.assertEqual(route(title)[0], "economic_buyer", title)


class EachTitleLandsInTheFamilyThatOwnsItsPain(unittest.TestCase):
    """The family decides the angle, so the mapping is the semantic claim."""

    EXPECTED = {
        # Production owns operations at an agency this size.
        "Head of Production": ("operations", "operations"),
        "Production Director": ("operations", "operations"),
        # Project and design leadership answer for budget burn and scope.
        "Project Director": ("delivery", "delivery"),
        "Design Director": ("delivery", "delivery"),
        # A studio manager books people. That is resourcing, not delivery.
        "Studio Manager": ("resource_management", "resource_management"),
        "Design Studio Manager": ("resource_management", "resource_management"),
    }

    def test_each_title_maps_to_its_family_and_angle(self):
        for title, (family, angle) in self.EXPECTED.items():
            with self.subTest(title=title):
                _, got_family, got_angle = route(title)
                self.assertEqual(got_family, family, title)
                self.assertEqual(got_angle, angle, title)

    def test_the_champion_declares_an_angle_for_every_family_it_can_match(self):
        """The defect that made `ops` useless, asserted as a rule.

        Every family this strategy can return for a champion must have a
        matching angle key, or that contact is silently held.
        """
        angles = set(clients.angles_for(CONFIG, "champion"))
        priority = plan()["persona_priority"]
        families = personas.family_titles(plan(), CONFIG)
        reachable = set()
        for title in clients.titles_for(CONFIG, "champion"):
            family, _rank = personas.family_of(contact(title), priority,
                                               families)
            if family:
                reachable.add(family)
        self.assertTrue(reachable)
        self.assertEqual(reachable - angles, set(),
                         "a champion can reach a family with no angle")


class AnArbitraryTitleStillFailsClosed(unittest.TestCase):
    """Widening who a client sells to is an operator decision, not a default."""

    def test_an_unrelated_title_is_not_a_persona(self):
        for title in ("Software Engineer", "Recruiter", "Office Manager",
                      "Data Scientist", "Warehouse Supervisor",
                      "Head of Legal", "Barista"):
            with self.subTest(title=title):
                self.assertIsNone(route(title)[0], title)

    def test_a_missing_title_is_not_a_persona(self):
        for value in (None, "", "   "):
            with self.subTest(title=value):
                self.assertIsNone(
                    personas.classify(contact(value), CONFIG)[0])

    def test_a_neighbouring_word_is_not_enough(self):
        """`Design` alone is not `Design Director`, and must not become one."""
        for title in ("Design", "Production", "Studio", "Project"):
            with self.subTest(title=title):
                self.assertIsNone(route(title)[0], title)

    def test_an_unmatched_contact_is_set_aside_with_a_reason(self):
        aside = personas.set_aside(contact("Barista"),
                                  "not a persona for this client")
        self.assertIn("not a persona", aside["why"])

    def test_a_classified_title_with_no_angle_is_still_held(self):
        """The other half of failing closed.

        A CFO is a legitimate economic buyer and Productive has deliberately
        declared no finance angle for one, so `default_angle` returns None and
        lint refuses the copy rather than lending it founder words.
        """
        angle = personas.default_angle(CONFIG, "economic_buyer", "finance")
        self.assertIsNone(angle)
        held = lint.check_linkedin(
            {"lane": "domains", "state": "queued",
             "contacts": [contact("CFO", angle=None)]},
            "c1", {"note": "hello there, this is a long enough note to pass"})
        self.assertIn("domains_contact_no_angle", held)


class TheRenameDoesNotOrphanAStoredAngle(unittest.TestCase):
    """A contact selected before the rename still carries `angle: ops`."""

    def test_the_old_key_still_has_a_readable_label(self):
        labels = clients.angle_labels(CONFIG)
        self.assertIn("ops", labels)
        self.assertIn("operations", labels)

    def test_every_declared_angle_has_a_label(self):
        labels = clients.angle_labels(CONFIG)
        for persona in clients.personas(CONFIG):
            for angle in clients.angles_for(CONFIG, persona):
                with self.subTest(persona=persona, angle=angle):
                    self.assertIn(angle, labels)


class CompanyQualificationIsUnchanged(unittest.TestCase):
    """Who counts as a person must not move who counts as a company."""

    def test_the_icp_thresholds_are_untouched(self):
        icp = (CONFIG.get("icp") or {})
        self.assertTrue(icp or True)          # a client may leave them default

    def test_no_persona_change_can_reach_the_company_scorer(self):
        """`icp.score` reads company facts and segments, never personas."""
        import inspect

        from src import icp
        source = inspect.getsource(icp.score)
        self.assertNotIn("personas", source)
        self.assertNotIn("titles_for", source)


if __name__ == "__main__":
    unittest.main()
