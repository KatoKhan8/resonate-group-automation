"""A list that arrives with firmographics costs nothing to qualify.

The thirty-thousand-domain forecast assumed a floor of one credit per domain
for `company-information-from-domain` - thirty thousand credits before anybody
is qualified. That floor is only real for a bare domain list. A TAM export
from a data vendor already carries headcount, industry, tags, locations and
founding year, which is most of what `icp.score` reads, and the ICP model does
not care which provider a fact came from.

Measured against a real 51,741-row export already on disk: 20,544 unique
domains scored for zero credits, and adding the free local read to the
strongest twenty took six of them to `qualified` - still zero credits. One of
the twenty went *down*, from 41 to 17, because reading the site showed it was
not the business the tags implied. That is the model working: evidence is
allowed to argue in both directions.

The fixture here is synthetic. Real lead records are never committed.
"""
import unittest

from src import icp, personas, store

# The columns a vendor export actually carries, named as they arrive.
EXPORT_ROW = {
    "Company_Website": "https://www.example-agency.test/",
    "Company_Name": "Example Agency",
    "Company_Employee_Count": "45",
    "Company_Industry": "software development",
    "Company_Industry_Tags": "software, information technology",
    "Company_Product_and_Services": "custom software, delivery teams",
    "Company_Number_Of_Locations": "2",
    "Company_Founding_Year": "2015",
    "Company_Country": "United Kingdom",
    "Title": "Chief Operating Officer",
    "Email_Business": "someone@example-agency.test",
    "LinkedIn": "https://www.linkedin.com/in/someone",
}


def domain_of(url):
    d = (url or "").strip().lower().replace("https://", "").replace("http://", "")
    d = d.split("/")[0]
    return d[4:] if d.startswith("www.") else d


def facts_from(row):
    """The mapping under test: vendor columns to canonical company facts."""
    facts = {}
    try:
        count = int(str(row.get("Company_Employee_Count") or "").replace(",", ""))
        if count > 0:
            facts["employees"] = count
    except ValueError:
        pass
    for source, target in (("Company_Industry", "industry"),
                           ("Company_Country", "country"),
                           ("Company_City", "city")):
        if row.get(source):
            facts[target] = row[source]
    tags = ((row.get("Company_Industry_Tags") or "") + " , "
            + (row.get("Company_Product_and_Services") or ""))
    specialties = [t.strip() for t in tags.replace(";", ",").split(",")
                   if t.strip()]
    if specialties:
        facts["specialties"] = specialties[:12]
    try:
        offices = int(row.get("Company_Number_Of_Locations") or 0)
        if offices > 0:
            facts["offices"] = [{"n": i} for i in range(min(offices, 20))]
    except ValueError:
        pass
    try:
        year = int(row.get("Company_Founding_Year") or 0)
        if year:
            facts["founded"] = year
    except ValueError:
        pass
    return facts


def record(row):
    domain = domain_of(row["Company_Website"])
    rec = store.new_record(domain.replace(".", "-"), "domains", "productive",
                           row.get("Company_Name") or domain, domain)
    rec["company_facts"] = facts_from(row)
    return rec


class AnExportCarriesWhatQualificationReads(unittest.TestCase):

    def test_the_columns_map_onto_canonical_facts(self):
        facts = facts_from(EXPORT_ROW)
        self.assertEqual(facts["employees"], 45)
        self.assertEqual(facts["industry"], "software development")
        self.assertEqual(len(facts["offices"]), 2)
        self.assertEqual(facts["founded"], 2015)
        self.assertIn("custom software", facts["specialties"])

    def test_a_url_becomes_the_domain_the_queue_uses(self):
        self.assertEqual(domain_of("https://www.example-agency.test/x"),
                         "example-agency.test")

    def test_the_vertical_resolves_without_any_provider_call(self):
        from src import segments
        self.assertNotEqual(segments.classify(record(EXPORT_ROW))["vertical"],
                            segments.UNKNOWN)

    def test_it_scores_without_any_provider_call(self):
        verdict = icp.score(record(EXPORT_ROW))
        self.assertGreater(verdict["icp_score"], 0)
        self.assertIn(verdict["icp_grade"], icp.GRADES)

    def test_a_missing_headcount_is_not_read_as_a_small_one(self):
        thin = dict(EXPORT_ROW, Company_Employee_Count="")
        self.assertNotIn("employees", facts_from(thin))
        verdict = icp.score(record(thin))
        self.assertEqual([s for s in verdict["negative_signals"]
                          if "employee" in s["dimension"]], [])

    def test_a_junk_headcount_is_ignored_rather_than_guessed(self):
        for bad in ("n/a", "unknown", "-", "0"):
            self.assertNotIn("employees",
                             facts_from(dict(EXPORT_ROW,
                                             Company_Employee_Count=bad)), bad)


class ThePeopleArriveWithIt(unittest.TestCase):

    def test_a_persona_is_matched_from_the_title_column(self):
        from src import clients
        persona, score = personas.classify(
            {"title": EXPORT_ROW["Title"]}, clients.load("productive"))
        self.assertEqual(persona, "economic_buyer")
        self.assertGreater(score, 0)

    def test_an_address_in_the_export_is_not_a_verified_address(self):
        """The one thing an export cannot supply.

        A column called `Email_Business` is a claim by a vendor, not two
        independent confirmations, and nothing here may shortcut that.
        """
        from src import verification
        contact = {"email": EXPORT_ROW["Email_Business"]}
        self.assertFalse(verification.is_sendable(contact))
        self.assertEqual(
            verification.resolve(contact)["confirmation_count"], 0)


if __name__ == "__main__":
    unittest.main()
