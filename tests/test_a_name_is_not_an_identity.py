#!/usr/bin/env python3
"""Two people who share a name are two people.

REPRODUCED on 2026-09-11, and it needs no reply from anybody - it happens
during ordinary enrichment. `merge_contacts` built ONE index keyed by every
handle a contact is known by - address, profile and NAME alike, from a helper
called `markers()` - so all three were interchangeable when looking somebody
up. A provider payload naming somebody who shares a full name with an
existing contact is therefore treated as that contact, and `FILLABLE` fills
in whatever that contact is missing.

The reachable shape, and it is the ordinary one. Both call sites run only
when `usable_contacts(rec)` is empty - no contact here has an address - so
the contact being merged into is somebody known by name and profile:

    on the record   Jan Novak, /in/jan-novak, no address
    provider says   Jan Novak, j.novak2@acme.test, /in/jan-novak-studio

    after merge     /in/jan-novak  +  j.novak2@acme.test
                    added: []   excluded: []

The profile is correctly left alone - that field was already set - but the
ADDRESS is written, because that field was empty. One contact now holds one
person's profile and another person's mailbox. `usable_contacts` then returns
it, so verification buys a check on the second person's address, and a valid
answer marks the row sendable: the email goes to one human and the connection
request to another.

The second person also disappears: not added, not excluded, no reason
recorded anywhere. A real decision maker is silently lost.

A contact added from a referral arrives as exactly this shape - a name and a
profile with no address - so the two paths chain.

`referral.py` already states the rule this breaks, in its own module
docstring: "An address or a canonical profile URL is identity. A name is not
- two people share one and one person has three." Two modules, one question,
two answers. This is the other answer being wrong.

The fix is NOT to drop the name from the index. The name index exists for a
reason recorded in `merge_contacts`'s own docstring: a person known only by
name who later arrives with an address was being minted twice, and re-minting
destroys paid verification evidence. So the name still matches - it just
cannot stand when the two records DISAGREE on a handle they both carry.
"""
import unittest

from src import enrich


def a_record(*contacts):
    return {"id": "acme", "domain": "acme.test", "company": "Acme",
            "company_facts": {"name": "Acme"}, "contacts": list(contacts)}


def known_by_profile(**over):
    """The shape the pipeline reaches: no address, so no usable contact."""
    contact = {"key": "acme-1", "name": "Jan Novak",
               "title": "Head of Delivery", "email": None,
               "linkedin": "https://www.linkedin.com/in/jan-novak",
               "verdict": None, "sendable": False}
    contact.update(over)
    return contact


class ASharedNameDoesNotMergeTwoPeople(unittest.TestCase):

    def test_the_exact_reproduction(self):
        rec = a_record(known_by_profile())
        self.assertEqual(enrich.usable_contacts(rec), [],
                         "the fixture no longer matches the reachable state")
        added, _ = enrich.merge_contacts(rec, [{
            "name": "Jan Novak", "title": "Studio Manager",
            "email": "j.novak2@acme.test",
            "linkedin": "https://www.linkedin.com/in/jan-novak-studio"}],
            "provider")
        held = rec["contacts"][0]
        self.assertIn("in/jan-novak", held["linkedin"])
        self.assertIsNone(held["email"],
                          "another person's mailbox was welded on")

    def test_the_second_person_is_not_lost(self):
        """`added: []` and `excluded: []` is a decision maker deleted with no
        record that they were ever seen."""
        rec = a_record(known_by_profile())
        added, _ = enrich.merge_contacts(rec, [{
            "name": "Jan Novak", "email": "j.novak2@acme.test",
            "linkedin": "https://www.linkedin.com/in/jan-novak-studio"}],
            "provider")
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["email"], "j.novak2@acme.test")
        self.assertIn("jan-novak-studio", added[0]["linkedin"])

    def test_a_conflicting_address_separates_them_too(self):
        """The mirror, defended at the function rather than at the caller.

        `merge_contacts` is reached today only with no addressed contact on
        the record, but that is the caller's condition and not this
        function's contract - and a second caller would inherit the weld.
        """
        rec = a_record(known_by_profile(email="jan.novak@acme.test",
                                        linkedin=None, verdict="valid",
                                        sendable=True))
        added, _ = enrich.merge_contacts(rec, [{
            "name": "Jan Novak", "email": "j.novak2@acme.test",
            "linkedin": "https://www.linkedin.com/in/jan-novak-studio"}],
            "provider")
        self.assertIsNone(rec["contacts"][0]["linkedin"],
                          "another person's profile was welded on")
        self.assertEqual(len(added), 1)

    def test_the_first_person_keeps_their_paid_evidence(self):
        """A fresh dict carries `verdict: None`, so a wrong merge that
        replaced somebody would delete a bought answer."""
        rec = a_record(known_by_profile(verdict="valid", sendable=True))
        enrich.merge_contacts(rec, [{"name": "Jan Novak",
                                     "email": "j.novak2@acme.test",
                                     "linkedin": "https://www.linkedin.com/"
                                                 "in/jan-novak-studio"}],
                              "provider")
        self.assertEqual(rec["contacts"][0]["verdict"], "valid")
        self.assertTrue(rec["contacts"][0]["sendable"])


class TheNameStillFillsInSomebodyKnownOnlyByName(unittest.TestCase):
    """The control, and the reason the name is in the index at all.

    `merge_contacts` says it in its own docstring: re-minting somebody who is
    already here is destructive, because a fresh dict carries `verdict: None`
    and no `verification` key - which is how three paid verifications for one
    address became "no verification evidence" while the ledger still showed
    the spend. A guard that stopped the name matching AT ALL would bring that
    back, so this class fails if the fix is a blunt one.
    """

    def test_a_name_only_contact_is_filled_in_not_duplicated(self):
        rec = a_record(known_by_profile(linkedin=None, title=None))
        added, _ = enrich.merge_contacts(rec, [{
            "name": "Jan Novak", "title": "Head of Delivery",
            "email": "jan.novak@acme.test",
            "linkedin": "https://www.linkedin.com/in/jan-novak"}], "provider")
        self.assertEqual(added, [], "the same person was minted twice")
        held = rec["contacts"][0]
        self.assertEqual(held["email"], "jan.novak@acme.test")
        self.assertIn("jan-novak", held["linkedin"])
        self.assertEqual(held["title"], "Head of Delivery")

    def test_the_filled_in_address_records_where_it_came_from(self):
        rec = a_record(known_by_profile(linkedin=None))
        enrich.merge_contacts(rec, [{"name": "Jan Novak",
                                     "email": "jan.novak@acme.test"}],
                              "provider")
        self.assertEqual(rec["contacts"][0]["email_source"], "provider")

    def test_an_agreeing_profile_still_matches(self):
        """Same name, same profile, an address to add. One person, filled in.

        This is the case the whole name index exists to serve, and the one a
        conflict check must not break: they agree on everything they both
        carry.
        """
        rec = a_record(known_by_profile())
        added, _ = enrich.merge_contacts(rec, [{
            "name": "Jan Novak", "email": "jan.novak@acme.test",
            "linkedin": "https://www.linkedin.com/in/jan-novak"}], "provider")
        self.assertEqual(added, [])
        self.assertEqual(rec["contacts"][0]["email"], "jan.novak@acme.test")


class AStrongHandleDecidesBeforeTheNameDoes(unittest.TestCase):

    def test_the_profile_wins_over_a_different_persons_name(self):
        """The old index was iterated as a SET, so which handle matched first
        was not defined. Precedence is now stated rather than emergent."""
        rec = a_record(
            known_by_profile(key="acme-1", name="Jan Novak"),
            known_by_profile(key="acme-2", name="Petra Svoboda",
                             linkedin="https://www.linkedin.com/in/petra-s",
                             title=None))
        added, _ = enrich.merge_contacts(rec, [{
            "name": "Petra Svoboda",
            "linkedin": "https://www.linkedin.com/in/jan-novak",
            "title": "Producer"}], "provider")
        self.assertEqual(added, [])
        self.assertEqual(rec["contacts"][0]["title"], "Head of Delivery",
                         "the name matched before the profile did")
        self.assertIsNone(rec["contacts"][1]["title"])

    def test_a_strong_handle_outranks_a_name_with_nothing_to_contradict_it(self):
        """The case precedence is actually load-bearing for.

        The second contact here is known ONLY by name - no address, no profile
        - so nothing about her contradicts anything and `disagree` has nothing
        to compare. Consult the name first and the incoming profile is filled
        onto her; but that profile is somebody else's, and the strong index
        already holds it. The conflict check cannot save this one, which is
        why the order is the guard.
        """
        rec = a_record(
            known_by_profile(key="acme-1", name="Jan Novak",
                             linkedin="jan-novak", title=None),
            known_by_profile(key="acme-2", name="Petra Svoboda",
                             linkedin=None, title=None))
        added, _ = enrich.merge_contacts(rec, [{
            "name": "Petra Svoboda", "title": "Producer", "company": "Acme",
            "linkedin": "https://www.linkedin.com/in/jan-novak"}], "provider")
        self.assertEqual(added, [])
        self.assertIsNone(rec["contacts"][1]["linkedin"],
                          "another person's profile was filled onto her")
        self.assertEqual(rec["contacts"][0]["title"], "Producer",
                         "the profile did not decide the match")

    def test_a_bare_slug_is_the_same_person_as_the_full_url(self):
        """Every profile in the estate is stored as a bare vanity slug and
        every provider returns a URL. Compared raw those are two people, and
        minting the second discards the verification bought for the first -
        so a normalisation gap here spends money twice and loses evidence.

        The names differ deliberately, so only the profile can match.
        """
        rec = a_record(known_by_profile(name="Jan Novak", linkedin="jan-novak",
                                        verdict="valid"))
        added, _ = enrich.merge_contacts(rec, [{
            "name": "J. Novak",
            "linkedin": "https://www.linkedin.com/in/jan-novak/?trk=x",
            "email": "jan.novak@acme.test"}], "provider")
        self.assertEqual(added, [], "one person was minted twice")
        self.assertEqual(rec["contacts"][0]["email"], "jan.novak@acme.test")
        self.assertEqual(rec["contacts"][0]["verdict"], "valid")

    def test_a_placeholder_in_the_address_field_is_not_a_handle(self):
        """Two records both carrying "N/A" are not one person.

        `dedupe.normalise_email` answers None for anything without an `@`, so
        a placeholder never becomes a handle. Lowercasing the raw value
        instead makes every contact a provider left a placeholder on match
        every other one - two strangers merged, and one of them deleted.
        """
        rec = a_record(known_by_profile(name="Jan Novak", linkedin=None,
                                        email="N/A"))
        added, _ = enrich.merge_contacts(rec, [{
            "name": "Petra Svoboda", "company": "Acme", "email": "n/a",
            "linkedin": "https://www.linkedin.com/in/petra-s"}], "provider")
        self.assertEqual(len(added), 1,
                         "a placeholder merged two strangers")

    def test_merging_is_stable_across_runs(self):
        """Ten identical merges, one answer. A set-ordered index can differ
        between interpreter runs and build a different estate from the same
        provider payload."""
        seen = set()
        for _ in range(10):
            rec = a_record(known_by_profile())
            added, _ = enrich.merge_contacts(rec, [{
                "name": "Jan Novak", "email": "j.novak2@acme.test",
                "linkedin": "https://www.linkedin.com/in/jan-novak-studio"}],
                "provider")
            seen.add((len(added), rec["contacts"][0].get("email")))
        self.assertEqual(len(seen), 1, f"unstable: {seen}")


if __name__ == "__main__":
    unittest.main()
