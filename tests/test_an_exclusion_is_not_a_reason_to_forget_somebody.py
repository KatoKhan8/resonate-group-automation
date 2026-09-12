#!/usr/bin/env python3
"""A persona list that is corrected has to be able to reach the people it lost.

## The defect

`personas.set_aside` keeps an excluded contact WHOLE - address, LinkedIn URL,
verification evidence, all of it already paid for - and its docstring says
exactly why:

    Two people at this pilot were excluded because the client's config listed
    "COO" and not "Chief Operating Officer"; correcting the config could not
    restore them... An exclusion is a decision about a person, not a reason to
    forget them.

It still could not. `select_domains` iterates `rec["contacts"]`, and a contact
set aside is no longer in it, so nothing in this module ever looked at an
exclusion again. The data was kept and nothing could read it - the defect
CLAUDE.md names, one module over.

Measured on the 300-record Productive estate: 26 already-paid contacts sat in
`excluded` with `persona: None` under "not a persona for this client" while
`classify` places every one of them, including the estate's only
resource-management contact - a Design Studio Manager, a title the client's
config gained on 2026-09-09 and nothing re-read.

## Only in the safe direction

Nothing here excludes anybody, a contact already on the record is not
duplicated, an entry set aside for any OTHER reason is untouched, and a
re-admitted contact competes for the persona cap rather than being appended
past it. The last of those is the one worth pinning: a recovery that ignored
the cap would spend the client's copy budget on a third champion nobody
approved.
"""
import unittest

from src import clients, personas, store

CLIENT = {
    "name": "Test Client",
    "personas": {
        "champion": {
            "titles": ["Studio Manager", "Resource Manager",
                       "Operations Manager"],
            "cap_per_domain": 2,
            "angles": {"operations": "capacity planning"},
        },
    },
}

# The same client before anybody noticed resourcing was a role.
BEFORE = {"name": "Test Client", "personas": {"champion": {
    "titles": ["Operations Manager"], "cap_per_domain": 2,
    "angles": {"operations": "capacity planning"}}}}


def a_contact(name, title, **over):
    return dict({"name": name, "title": title, "email": f"{name}@acme.test",
                 "sendable": True, "verification": {"state": "sendable"}},
                **over)


def a_record(*contacts):
    rec = store.new_record("acct", "domains", "test", "Acme", "acme.test")
    rec["contacts"] = [dict(c) for c in contacts]
    return rec


class ACorrectedPersonaListReachesThePeopleItLost(unittest.TestCase):

    def excluded_under_the_old_list(self):
        """Run the old config first, so the exclusion is a real one."""
        rec = a_record(a_contact("ciara", "Studio Manager"),
                       a_contact("owen", "Operations Manager"))
        personas.select(rec, BEFORE)
        return rec

    def test_the_old_list_sets_her_aside(self):
        rec = self.excluded_under_the_old_list()
        self.assertEqual([c["name"] for c in rec["contacts"]], ["owen"])
        self.assertEqual([e["why"] for e in rec["excluded"]],
                         [personas.NOT_A_PERSONA])

    def test_the_corrected_list_returns_her(self):
        rec = self.excluded_under_the_old_list()
        personas.select(rec, CLIENT)
        self.assertIn("ciara", [c["name"] for c in rec["contacts"]])

    def test_she_comes_back_with_a_persona_and_an_angle(self):
        rec = self.excluded_under_the_old_list()
        personas.select(rec, CLIENT)
        her = next(c for c in rec["contacts"] if c["name"] == "ciara")
        self.assertEqual(her["persona"], "champion")
        self.assertTrue(her["angle"])

    def test_the_paid_data_comes_back_with_her(self):
        """The whole reason `set_aside` keeps the record intact."""
        rec = self.excluded_under_the_old_list()
        personas.select(rec, CLIENT)
        her = next(c for c in rec["contacts"] if c["name"] == "ciara")
        self.assertEqual(her["email"], "ciara@acme.test")
        self.assertEqual(her["verification"], {"state": "sendable"})

    def test_she_is_no_longer_listed_as_excluded(self):
        rec = self.excluded_under_the_old_list()
        personas.select(rec, CLIENT)
        self.assertNotIn("ciara", [e["name"] for e in rec["excluded"] or []])

    def test_nothing_was_re_bought_to_get_her_back(self):
        rec = self.excluded_under_the_old_list()
        personas.select(rec, CLIENT)
        self.assertEqual(rec.get("waterfall") or [], [])


class NobodyIsAdmittedWhoShouldNotBe(unittest.TestCase):

    def test_a_title_that_still_matches_nothing_stays_out(self):
        rec = a_record(a_contact("gita", "Graphic Designer"))
        personas.select(rec, CLIENT)
        personas.select(rec, CLIENT)
        self.assertEqual(rec["contacts"], [])
        self.assertEqual(len(rec["excluded"]), 1)

    def test_an_exclusion_for_any_other_reason_is_untouched(self):
        rec = a_record(a_contact("a", "Studio Manager"),
                       a_contact("b", "Operations Manager"),
                       a_contact("c", "Resource Manager"))
        personas.select(rec, CLIENT)
        over_cap = [e for e in rec["excluded"]
                    if e["why"] != personas.NOT_A_PERSONA]
        self.assertTrue(over_cap)
        personas.select(rec, CLIENT)
        self.assertEqual(
            [e["why"] for e in rec["excluded"]
             if e["why"] != personas.NOT_A_PERSONA],
            [e["why"] for e in over_cap])

    def test_a_re_admitted_contact_competes_for_the_cap(self):
        """Three champions, a cap of two: the recovery does not make it three."""
        rec = a_record(a_contact("ciara", "Studio Manager"),
                       a_contact("owen", "Operations Manager"),
                       a_contact("rina", "Resource Manager"))
        personas.select(rec, BEFORE)
        personas.select(rec, CLIENT)
        self.assertEqual(len(rec["contacts"]),
                         clients.cap_for(CLIENT, "champion"))

    def test_somebody_already_on_the_record_is_not_duplicated(self):
        """The estate really does carry a person in both lists at once."""
        rec = a_record(a_contact("owen", "Operations Manager"))
        rec["excluded"] = [dict(a_contact("owen", "Operations Manager"),
                                why=personas.NOT_A_PERSONA)]
        personas.select(rec, CLIENT)
        self.assertEqual([c["name"] for c in rec["contacts"]], ["owen"])

    def test_a_record_with_nothing_set_aside_is_unchanged(self):
        rec = a_record(a_contact("owen", "Operations Manager"))
        personas.select(rec, CLIENT)
        before = [c["name"] for c in rec["contacts"]]
        self.assertEqual(personas.readmit(rec, CLIENT), [])
        self.assertEqual([c["name"] for c in rec["contacts"]], before)


class TheTwoListsThatSayWhoWeTargetAgreeAboutResourcing(unittest.TestCase):
    """`routing.strategies` says who a paid search looks for. `personas` says
    who is kept when they come back. Where they disagree, the client pays to
    find somebody and the engine throws them away.

    This asserts the agreement for the resource-management family only,
    because that is the family the client's own config declares a target and
    `personas.classify` could not place. The other families' gaps are recorded
    in PRODUCT-GAPS.md: which angle a VP Delivery should receive is a
    go-to-market decision, not an oversight to fix in a test.
    """

    def setUp(self):
        self.config = clients.load("productive")

    def test_every_resource_management_title_reaches_a_persona(self):
        from src import routing

        unreachable = []
        for spec in routing.settings(self.config)["strategies"].values():
            for title in spec["personas"].get("resource_management") or []:
                if not personas.classify({"title": title}, self.config)[0]:
                    unreachable.append(title)
        self.assertEqual(sorted(set(unreachable)), [])

    def test_the_family_is_not_empty(self):
        """So the test above cannot pass by the family disappearing."""
        from src import routing

        found = {t for spec in routing.settings(self.config)
                 ["strategies"].values()
                 for t in spec["personas"].get("resource_management") or []}
        self.assertGreaterEqual(len(found), 6)


if __name__ == "__main__":
    unittest.main()
