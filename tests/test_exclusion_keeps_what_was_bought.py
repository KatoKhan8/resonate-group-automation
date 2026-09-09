"""An exclusion is a decision about a person, not a reason to forget them.

`personas.select_domains` stored `{name, title, why}` for everyone it set
aside and dropped the rest: the email, the LinkedIn URL, the verification
evidence. All of it was paid for - `decision-makers` costs ten credits for the
set, each verification costs one - so a persona rule excluding somebody threw
away bought data and made the decision impossible to reverse.

Measured on the Productive pilot: two people were excluded because the
client's config listed "COO" and not "Chief Operating Officer". Correcting the
config could not bring them back, because what remained was a name and a
title. Re-adding one to `contacts` made `usable_contacts` false - it had no
address - and the next enrichment pass bought `decision-makers` again for a
company whose people were already on the record. Ten credits to rediscover
what exclusion had deleted.
"""
import unittest

from src import clients, personas, store

CONTACT = {
    "name": "A Person",
    # Deliberately not a persona for this client, and it has to STAY that way
    # for this test to be about anything. It was "Head of Production" until
    # 2026-09-09, when the operator approved that title as a champion - at
    # which point this contact was selected rather than excluded and all seven
    # assertions below failed on `len(excluded) == 0`. A title that a client
    # might plausibly adopt later is a bad fixture for "not a persona".
    "title": "Warehouse Supervisor",
    "email": "a.person@agency.test",
    "linkedin": "https://www.linkedin.com/in/a-person",
    "key": "a-person",
    "verification": {"state": "held", "sendable": False},
    "verification_evidence": [{"provider": "reoon", "status": "valid"}],
}


def record(*contacts):
    rec = store.new_record("x1", "domains", "demo", "Agency", "agency.test")
    rec["contacts"] = [dict(c) for c in contacts]
    return rec


class WhatWasBoughtSurvivesTheDecision(unittest.TestCase):

    def setUp(self):
        self.config = clients.load("productive")

    def excluded_entry(self, contact=None):
        rec = record(contact or CONTACT)
        _, excluded = personas.select_domains(rec, self.config)
        self.assertEqual(len(excluded), 1)
        return excluded[0]

    def test_the_reason_is_recorded(self):
        self.assertEqual(self.excluded_entry()["why"],
                         "not a persona for this client")

    def test_the_address_survives(self):
        """The expensive part. Without it, re-including costs ten credits."""
        self.assertEqual(self.excluded_entry()["email"], CONTACT["email"])

    def test_the_linkedin_url_survives(self):
        self.assertEqual(self.excluded_entry()["linkedin"], CONTACT["linkedin"])

    def test_the_verification_evidence_survives(self):
        entry = self.excluded_entry()
        self.assertEqual(entry["verification_evidence"],
                         CONTACT["verification_evidence"])

    def test_the_contact_key_survives(self):
        """Identity has to be stable across an exclusion, or a later
        re-inclusion is a different person as far as history is concerned."""
        self.assertEqual(self.excluded_entry()["key"], CONTACT["key"])

    def test_nothing_the_contact_carried_is_dropped(self):
        entry = self.excluded_entry()
        missing = [k for k in CONTACT if k not in entry]
        self.assertEqual(missing, [], "exclusion dropped: %s" % missing)

    def test_a_capped_contact_is_kept_whole_too(self):
        """The other exclusion path. Productive caps economic_buyer at one."""
        first = dict(CONTACT, title="CEO", key="one", email="one@agency.test")
        second = dict(CONTACT, title="Chief Executive Officer", key="two",
                      email="two@agency.test")
        rec = record(first, second)
        keep, excluded = personas.select_domains(rec, self.config)
        self.assertEqual(len(keep), 1)
        self.assertEqual(len(excluded), 1)
        self.assertTrue(excluded[0]["email"], "the capped one lost its address")
        self.assertIn("over the cap", excluded[0]["why"])

    def test_restoring_an_excluded_contact_needs_no_new_purchase(self):
        """The property that matters: put them back and they are usable.

        `enrich.usable_contacts` is what decides whether discovery runs again,
        and it asks for an address. A restored stub has none, which is how a
        corrected config turned into a repeat purchase.
        """
        from src import enrich
        entry = dict(self.excluded_entry())
        entry.pop("why", None)
        rec = record()
        rec["contacts"] = [entry]
        self.assertTrue(enrich.usable_contacts(rec),
                        "a restored contact still looks unusable, so "
                        "enrichment would buy this person again")


if __name__ == "__main__":
    unittest.main()
