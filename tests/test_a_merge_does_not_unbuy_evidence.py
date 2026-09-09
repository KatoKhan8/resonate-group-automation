"""Re-discovering somebody already on the record does not delete what we bought.

`merge_contacts` matched a returned person against the record on a *single*
marker - the first of email, LinkedIn or name that happened to be set. A person
known by name who came back from the provider with an address did not match, so
a second contact was minted for the same human, carrying `verdict: None` and no
`verification` key at all.

That is a duplicate when the original is still in `rec["contacts"]`, and a
deletion when it is not. Both happened here. A run that emptied `contacts`
before calling discovery re-minted three people, and the evidence-bearing dicts
- three paid provider answers for one address - were dropped on the floor. The
waterfall ledger still shows the spend; the contact reads "no verification
evidence".

Filling in an existing contact instead cannot do either. The fields a payload
may fill are deliberately narrow: title, LinkedIn, name, and an address only
where none is held. Not the verdict, and not the evidence - those are bought,
and a later search result is not permission to replace them.
"""
import unittest

from src import enrich


def record(contacts):
    return {"id": "r1", "client": "c", "domain": "acme.test",
            "company": "Acme Ltd", "company_facts": {"name": "Acme Ltd"},
            "contacts": list(contacts)}


def verified(email, name="Pat Doe", linkedin=None):
    """A contact carrying paid provider answers."""
    contact = {"key": "pat", "name": name, "email": email,
               "title": "Chief Operating Officer", "verdict": "accept_all",
               "verification": {"state": "accept_all_uncleared",
                                "sendable": False,
                                "evidence": [
                                    {"provider": "contactout", "email": email,
                                     "status": "accept_all"},
                                    {"provider": "reoon", "email": email,
                                     "status": "accept_all",
                                     "is_safe_to_send": False}]}}
    if linkedin:
        contact["linkedin"] = linkedin
    return contact


class AMergeDoesNotUnbuyEvidence(unittest.TestCase):

    def evidence_of(self, rec, index=0):
        contact = rec["contacts"][index]
        return (contact.get("verification") or {}).get("evidence") or []

    # ------------------------------------------------------- the same person

    def test_the_same_address_is_filled_in_not_minted(self):
        rec = record([verified("pat@acme.test")])
        added, _ = enrich.merge_contacts(
            rec, [{"name": "Pat Doe", "email": "pat@acme.test",
                   "title": "COO", "company": "Acme Ltd"}], "provider")
        self.assertEqual(added, [])
        self.assertEqual(len(self.evidence_of(rec)), 2)

    def test_a_different_marker_still_finds_them(self):
        """Known by name, returned with an address. The defect: this minted a
        second contact, and the bare one then competed for a cap of one."""
        rec = record([verified("pat@acme.test", linkedin="pat-doe")])
        added, _ = enrich.merge_contacts(
            rec, [{"name": "Pat Doe", "linkedin": "pat-doe",
                   "company": "Acme Ltd"}], "provider")
        self.assertEqual(added, [], "a second dict was minted for one person")
        self.assertEqual(len(rec["contacts"]), 1)
        self.assertEqual(len(self.evidence_of(rec)), 2)

    def test_a_payload_may_fill_a_gap(self):
        """Merging has to be worth doing, not just safe."""
        rec = record([{"key": "pat", "name": "Pat Doe",
                       "email": "pat@acme.test"}])
        enrich.merge_contacts(
            rec, [{"name": "Pat Doe", "email": "pat@acme.test",
                   "title": "COO", "linkedin": "pat-doe",
                   "company": "Acme Ltd"}], "provider")
        self.assertEqual(rec["contacts"][0]["title"], "COO")
        self.assertEqual(rec["contacts"][0]["linkedin"], "pat-doe")

    def test_a_payload_may_not_replace_an_address(self):
        """The address is what evidence is bound to. Changing it silently
        would orphan every row bought against the old one."""
        rec = record([verified("pat@acme.test")])
        enrich.merge_contacts(
            rec, [{"name": "Pat Doe", "email": "other@acme.test",
                   "company": "Acme Ltd"}], "provider")
        self.assertEqual(rec["contacts"][0]["email"], "pat@acme.test")
        self.assertEqual(len(self.evidence_of(rec)), 2)

    def test_a_payload_may_not_clear_a_verdict(self):
        rec = record([verified("pat@acme.test")])
        enrich.merge_contacts(
            rec, [{"name": "Pat Doe", "email": "pat@acme.test",
                   "company": "Acme Ltd"}], "provider")
        self.assertEqual(rec["contacts"][0]["verdict"], "accept_all")

    # ------------------------------------------------ and a real new person

    def test_somebody_genuinely_new_is_still_added(self):
        """Otherwise the merge refuses everybody and discovery buys nothing."""
        rec = record([verified("pat@acme.test")])
        added, _ = enrich.merge_contacts(
            rec, [{"name": "Sam Roe", "email": "sam@acme.test",
                   "company": "Acme Ltd"}], "provider")
        self.assertEqual([c["email"] for c in added], ["sam@acme.test"])

    def test_a_collision_is_still_excluded(self):
        rec = record([])
        added, excluded = enrich.merge_contacts(
            rec, [{"name": "Someone Else", "email": "x@other.test",
                   "company": "A Different Company"}], "provider")
        self.assertEqual(added, [])
        self.assertEqual(len(excluded), 1)


if __name__ == "__main__":
    unittest.main()
