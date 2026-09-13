"""A personal mailbox is not evidence that somebody works somewhere else.

`same_company` short-circuited on ANY address: if the part after the @ was not
this company's domain, the person was excluded as "company name collision: not
this domain". ContactOut returns personal addresses beside work ones, so a
decision maker whose only address is a gmail was thrown away as an employee of
another firm - while the same payload's `company` field named this company
exactly.

Measured on the first eleven live exclusions kept whole on the Productive
estate: ALL ELEVEN carried a company name matching this record's own label,
and five of them were excluded purely on a webmail address. A Partner, a Head
of graphic design and a Client Director at &Partner ApS; a Vice President at
2020 Companies; a consultant at 25wat.

The second half of the same defect: the name comparison ran against
`rec["company"]`, which holds the DOMAIN STRING on 272 of the 300 records in
this estate. "academy xi" was compared against "academyxi.com", so the branch
could not match however right the person was, and every profile-only person a
search returned was excluded. `company_facts["name"]` is the label the
provider spells a payload's `company` in, and it is now consulted too.

What must NOT change, and is asserted here as hard as the above: an address at
another WORK domain still excludes even when the company name matches, and a
row carrying no address and no company name is still not merged.
"""
import unittest

from src import enrich


def record(company="Acme Ltd", facts_name=None, domain="acme.test",
           email_domain=None):
    facts = {}
    if facts_name:
        facts["name"] = facts_name
    if email_domain:
        facts["email_domain"] = email_domain
    return {"id": "r1", "client": "c", "domain": domain, "company": company,
            "company_facts": facts, "contacts": [], "excluded": []}


class AWebmailAddressIsNotAnotherEmployer(unittest.TestCase):

    def test_a_webmail_address_does_not_decide_the_employer(self):
        rec = record()
        self.assertTrue(enrich.same_company(
            {"name": "Casper", "company": "Acme Ltd",
             "email": "casper@hotmail.com"}, rec))

    def test_every_listed_provider_falls_through_rather_than_excluding(self):
        rec = record()
        for host in ("gmail.com", "outlook.com", "yahoo.co.uk", "gmx.de",
                     "icloud.com", "proton.me"):
            with self.subTest(host=host):
                self.assertTrue(enrich.same_company(
                    {"company": "Acme Ltd", "email": f"p@{host}"}, rec))

    def test_a_webmail_address_alone_still_proves_nothing(self):
        """Falling through is not accepting. With no company name on the
        payload there is nothing for the second branch to match, and the row
        leaves by the same door it always did."""
        self.assertFalse(enrich.same_company(
            {"name": "Casper", "email": "casper@hotmail.com"}, record()))

    def test_a_work_address_elsewhere_still_outranks_a_matching_name(self):
        """The guard trap 1 exists for. An address at another WORK domain is
        real evidence about where somebody works and must keep deciding."""
        self.assertFalse(enrich.same_company(
            {"name": "Luc", "company": "Acme Ltd",
             "email": "luc@samename.example"}, record()))

    def test_an_unknown_mailbox_provider_excludes_rather_than_admits(self):
        """The list is short on purpose. Missing from it means treated as a
        work domain, which excludes - the safe direction to be incomplete."""
        self.assertFalse(enrich.same_company(
            {"name": "Pat", "company": "Acme Ltd",
             "email": "pat@some-webmail-nobody-listed.test"}, record()))

    def test_the_name_is_matched_against_the_label_the_record_holds(self):
        """272 of 300 records carry the DOMAIN in `company`, so the provider's
        company name has to be compared against `company_facts.name` as well
        or it can never match."""
        rec = record(company="academyxi.com", facts_name="Academy Xi",
                     domain="academyxi.com")
        self.assertTrue(enrich.same_company({"company": "Academy Xi"}, rec))
        self.assertFalse(enrich.same_company({"company": "Academy Xii"}, rec))

    def test_neither_label_means_no_match(self):
        rec = {"id": "r", "domain": "acme.test", "company": "",
               "company_facts": {}}
        self.assertFalse(enrich.same_company({"company": "Acme Ltd"}, rec))

    def test_this_company_domain_still_decides_first(self):
        self.assertTrue(enrich.same_company(
            {"email": "a@acme.test"}, record()))
        self.assertTrue(enrich.same_company(
            {"email": "a@mail.acme-alt.test"},
            record(email_domain="mail.acme-alt.test")))


class AnExclusionSaysWhichFindingItIs(unittest.TestCase):
    """Fifty of the eighty exclusions on this estate were AI Ark rows with no
    name, no title, no address and no profile - a fallback returning rows this
    system cannot read, recorded as fifty people at the wrong company."""

    def test_a_row_that_identifies_nobody_is_not_called_a_collision(self):
        self.assertEqual(enrich.exclusion_reason({}), enrich.UNIDENTIFIED)
        self.assertEqual(enrich.exclusion_reason({"title": "CEO"}),
                         enrich.UNIDENTIFIED)

    def test_any_identifying_handle_makes_it_a_collision_again(self):
        for row in ({"name": "Pat"}, {"email": "p@other.test"},
                    {"linkedin": "https://www.linkedin.com/in/pat"}):
            with self.subTest(row=row):
                self.assertEqual(enrich.exclusion_reason(row),
                                 enrich.COLLISION)

    def test_merge_records_the_unidentified_reason_on_the_record(self):
        rec = record()
        added, excluded = enrich.merge_contacts(
            rec, [{"name": None, "title": None, "company": None,
                   "linkedin": None, "email": None}], "provider")
        self.assertEqual(added, [])
        self.assertEqual([e["why"] for e in excluded], [enrich.UNIDENTIFIED])

    def test_an_exclusion_keeps_the_payload_it_was_decided_on(self):
        """`{name, title, why}` threw away the address, the profile and the
        COMPANY NAME the decision was actually made on, so no exclusion on
        this estate could be audited without buying the search again."""
        rec = record()
        _, excluded = enrich.merge_contacts(
            rec, [{"name": "Luc Marchand", "title": "Owner",
                   "company": "Samename Industrial",
                   "linkedin": "https://www.linkedin.com/in/luc-marchand",
                   "email": "luc@samename.example",
                   "location": "Nice, France", "seniority": "Owner"}],
            "provider")
        self.assertEqual(len(excluded), 1)
        entry = excluded[0]
        self.assertEqual(entry["company"], "Samename Industrial")
        self.assertEqual(entry["email"], "luc@samename.example")
        self.assertEqual(entry["linkedin"],
                         "https://www.linkedin.com/in/luc-marchand")
        self.assertEqual(entry["location"], "Nice, France")
        self.assertEqual(entry["why"], enrich.COLLISION)
        self.assertTrue(entry.get("key"))


class TheCorrectedCheckReachesPeopleAlreadySetAside(unittest.TestCase):
    """Correcting `same_company` on its own changes nothing for anybody.

    `merge_contacts` is its only caller and runs on a fresh payload, and
    nothing else reads an exclusion - so on an estate where discovery has
    already happened the fix would apply to nobody it was made for. This is
    the consumer, and these are the tests that fail if it stops being called.
    """

    def held(self, **over):
        row = {"name": "Casper", "title": "Partner", "company": "Acme Ltd",
               "linkedin": "https://www.linkedin.com/in/casper",
               "email": "casper@hotmail.com", "key": "casper",
               "why": enrich.COLLISION}
        row.update(over)
        return row

    def test_somebody_excluded_on_a_webmail_address_comes_back(self):
        rec = record()
        rec["excluded"] = [self.held()]
        added = enrich.reconsider_exclusions(rec)
        self.assertEqual([c["name"] for c in added], ["Casper"])
        self.assertEqual([c["name"] for c in rec["contacts"]], ["Casper"])
        self.assertEqual(rec["excluded"], [])

    def test_a_readmitted_person_arrives_in_the_contact_shape(self):
        rec = record()
        rec["excluded"] = [self.held()]
        contact = enrich.reconsider_exclusions(rec)[0]
        self.assertEqual(contact["email"], "casper@hotmail.com")
        self.assertEqual(contact["email_source"], "provider")
        self.assertFalse(contact["sendable"])
        self.assertIsNone(contact["verdict"])
        self.assertIsNone(contact["persona"])
        self.assertTrue(contact.get("key"))

    def test_somebody_genuinely_elsewhere_stays_out(self):
        rec = record()
        rec["excluded"] = [self.held(name="Luc", company="Samename Industrial",
                                     email="luc@samename.example")]
        self.assertEqual(enrich.reconsider_exclusions(rec), [])
        self.assertEqual([e["why"] for e in rec["excluded"]],
                         [enrich.COLLISION])

    def test_decisions_taken_by_other_stages_are_not_touched(self):
        """`excluded` is one list shared with persona and cap decisions, which
        are not this module's to revisit."""
        rec = record()
        rec["excluded"] = [{"name": "Pat", "title": "Ops",
                            "why": "not a persona for this client"},
                           {"name": "Sam", "title": "COO",
                            "why": "over the cap of 1 for economic_buyer"},
                           {"name": None, "why": enrich.UNIDENTIFIED}]
        before = list(rec["excluded"])
        self.assertEqual(enrich.reconsider_exclusions(rec), [])
        self.assertEqual(rec["excluded"], before)
        self.assertEqual(rec["contacts"], [])

    def test_running_twice_does_not_duplicate_anybody(self):
        rec = record()
        rec["excluded"] = [self.held()]
        enrich.reconsider_exclusions(rec)
        self.assertEqual(enrich.reconsider_exclusions(rec), [])
        self.assertEqual(len(rec["contacts"]), 1)

    def test_it_runs_before_the_paid_search_so_nobody_is_re_bought(self):
        """A company whose only people are readmitted ones must not pay for
        `decision-makers` again to rediscover a payload already on the
        record."""
        rec = record()
        rec["excluded"] = [self.held()]
        budget = enrich.Budget(None)
        done = enrich.enrich_record(rec, budget, live=False)
        self.assertEqual([c["name"] for c in rec["contacts"]], ["Casper"])
        self.assertNotIn("decision-makers", [o["call"] for o in done])


if __name__ == "__main__":
    unittest.main()
