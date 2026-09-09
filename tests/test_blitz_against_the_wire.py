"""Blitz parsing, asserted against a response the server actually sent.

Every other Blitz test in this repository asserts against a dict written by
the same author as the code, in the same file. That proves the code parses its
own fiction, which is worth something and is not worth what it looks like:
`tests/fixtures/cassettes/blitz.json` says so about itself - "Hand written
from the capability matrix; no live call has been made."

On 2026-09-09 one authorised metered call was made - `POST
/v2/enrichment/company`, one Blitz record - and the raw exchange is stored at
`work/validation/blitz-company.json`, which is where this project already
keeps recorded provider evidence.

The bodies below are that response with **every key name, type, nesting and
null verbatim** and only the identifying values substituted for reserved-domain
equivalents. `tests/test_fixture_hygiene.py` forbids real domains in anything
under `tests/`, deliberately including Resonate's own, because fixtures live in
git for ever - and nothing here asserts on *which* company answered. What is
under test is the spelling and shape of the fields, and that is unaltered:
`employees_on_linkedin: 19` against an absent `employees`, `size` as a band,
`hq` as an object of nulls, and the exact `fair_usage` block.

It found three defects, every one of them silent:

  - the request field is `company_linkedin_url`, not `linkedin_url`. Sending
    the wrong one returns 422 and bills nothing, so every call would have
    failed while the ledger showed no spend at all.
  - the headcount is `employees_on_linkedin`. Not one of `employees`,
    `employee_count` or `headcount` appears, so the trim read None where the
    wire said 19.
  - the location is a nested `hq` object. The trim looked for a scalar under
    `location` / `headquarter` / `country` and found none - and had any
    matching key held that object, `_text` would have stringified the whole
    dict into a trimmed field.

The `records_used: 1` in the fair_usage block below is the receipt.
"""
import unittest

from src import providers
from src.providers import blitz

LINKEDIN = "https://www.linkedin.com/company/example-group"

# Verbatim from work/validation/blitz-company.json, the 200.
LIVE = {
    "company": {
        "about": None,
        "domain": "example.test",
        "employees_on_linkedin": 19,
        "followers": 96,
        "founded_year": None,
        "hq": {"city": None, "continent": None, "country_code": None,
               "country_name": None, "region": None, "state": None},
        "industry": "IT Services and IT Consulting",
        "linkedin_id": 106141832,
        "linkedin_url": LINKEDIN,
        "name": "Example Group",
        "size": "1-10",
        "specialties": None,
        "type": "Public Company",
        "website": "https://www.example.test",
    },
    "fair_usage": {
        "next_reset_at": "2026-10-08T16:02:17.574Z",
        "rate_limit": {"remaining_this_second": 49, "requests_per_second": 50},
        "records_remaining": 29999999,
        "records_used": 1,
        "request_id": "01a085a4-2947-7304-bf05-7ebe03ab41f8",
    },
    "found": True,
}

# Verbatim from the same file, the 422 that cost nothing.
REFUSED = {
    "errors": [{"code": "invalid_type", "expected": "string",
                "message": "Invalid input: expected string, received undefined",
                "path": ["company_linkedin_url"]}],
    "found": {"linkedin_url": LINKEDIN},
    "message": "Invalid input: expected string, received undefined",
    "on": "body",
    "property": "company_linkedin_url",
    "type": "validation",
}


def parsed():
    """The shipped trim, over the recorded body."""
    got = blitz._outcome(200, LIVE, "company")
    raw = blitz._payload(got["body"], "company")
    return got, raw


class TheEnvelopeIsWhatWeThoughtItWas(unittest.TestCase):
    def test_found_is_a_real_boolean_at_the_top_level(self):
        got, _ = parsed()
        self.assertIs(got["found"], True)

    def test_the_subject_sits_under_the_company_key(self):
        got, raw = parsed()
        self.assertIsNot(raw, got["body"])
        self.assertEqual(raw["name"], "Example Group")

    def test_the_cost_block_carries_what_the_ledger_needs(self):
        got, _ = parsed()
        self.assertEqual(got["fair_usage"]["records_used"], 1)
        self.assertEqual(got["fair_usage"]["records_remaining"], 29999999)
        self.assertTrue(got["fair_usage"]["request_id"])


class TheFieldSpellingsTheSpecGotWrong(unittest.TestCase):
    def test_the_headcount_is_employees_on_linkedin(self):
        _, raw = parsed()
        self.assertEqual(blitz._count(blitz.first(
            raw, "employees_on_linkedin", "employees", "employee_count",
            "headcount")), 19)

    def test_the_old_spellings_are_simply_absent(self):
        """Anchors the defect: the old trim could only ever have read None."""
        _, raw = parsed()
        for name in ("employees", "employee_count", "headcount"):
            self.assertNotIn(name, raw)
        self.assertIsNone(blitz._count(blitz.first(
            raw, "employees", "employee_count", "headcount")))

    def test_a_band_is_not_read_as_a_count(self):
        """`size` is "1-10" while the measured number is 19.

        Reading the band into `employees` would have understated a company by
        half its people and looked like a plausible answer.
        """
        _, raw = parsed()
        self.assertEqual(raw["size"], "1-10")
        self.assertEqual(blitz._text(blitz.first(raw, "size",
                                                 "employee_range")), "1-10")

    def test_founded_year_is_the_right_spelling_and_is_null_here(self):
        _, raw = parsed()
        self.assertIn("founded_year", raw)
        self.assertIsNone(blitz._count(blitz.first(raw, "founded_year",
                                                   "founded")))


class ANestedObjectNeverBecomesAString(unittest.TestCase):
    def test_the_location_is_an_object_on_the_wire(self):
        _, raw = parsed()
        self.assertIsInstance(raw["hq"], dict)

    def test_text_refuses_to_stringify_it(self):
        _, raw = parsed()
        self.assertIsNone(blitz._text(raw["hq"]))

    def test_an_all_null_place_is_nothing_rather_than_empty(self):
        _, raw = parsed()
        self.assertIsNone(blitz._place(raw["hq"]))

    def test_a_populated_place_reads_as_prose(self):
        self.assertEqual(
            blitz._place({"city": "Zagreb", "state": None, "region": None,
                          "country_name": "Croatia"}),
            "Zagreb, Croatia")

    def test_a_repeated_name_is_not_said_twice(self):
        self.assertEqual(
            blitz._place({"city": "Singapore", "state": None,
                          "region": "Singapore", "country_name": "Singapore"}),
            "Singapore")


class TheRequestFieldName(unittest.TestCase):
    """The defect that would have made every call fail."""

    def test_the_accessor_sends_company_linkedin_url(self):
        sent = {}

        def spy(name, params=None):
            sent.update({"name": name, "params": params})
            return 200, LIVE

        real = blitz.call
        blitz.call = spy
        self.addCleanup(setattr, blitz, "call", real)
        blitz.company(LINKEDIN)
        self.assertEqual(sent["params"], {"company_linkedin_url": LINKEDIN})

    def test_a_422_is_refused_rather_than_read(self):
        """And it must be refused on the status, before `found` is inspected.

        The 422 body carries `found` as an OBJECT. `_outcome` asserts `found`
        is a boolean, so without the status check first this would raise the
        wrong error - or, if the type check were ever relaxed, be read as a
        miss.
        """
        with self.assertRaises(providers.ProviderError) as caught:
            blitz._outcome(422, REFUSED, "company")
        self.assertIn("422", str(caught.exception))

    def test_the_422_body_is_why_found_needs_the_status_check(self):
        self.assertIsInstance(REFUSED["found"], dict)


class TheWholeTrimOverTheRecordedBody(unittest.TestCase):
    def test_it_reads_what_the_server_sent(self):
        def spy(name, params=None):
            return 200, LIVE

        real = blitz.call
        blitz.call = spy
        self.addCleanup(setattr, blitz, "call", real)
        out = blitz.company(LINKEDIN)
        self.assertEqual(out["name"], "Example Group")
        self.assertEqual(out["domain"], "example.test")
        self.assertEqual(out["employees"], 19)
        self.assertEqual(out["employee_range"], "1-10")
        self.assertEqual(out["industry"], "IT Services and IT Consulting")
        self.assertIsNone(out["location"])
        self.assertIsNone(out["founded"])
        self.assertEqual(out["fair_usage"]["records_used"], 1)

    def test_no_raw_field_escapes_the_trim(self):
        def spy(name, params=None):
            return 200, LIVE

        real = blitz.call
        blitz.call = spy
        self.addCleanup(setattr, blitz, "call", real)
        out = blitz.company(LINKEDIN)
        for noise in ("followers", "linkedin_id", "type", "about",
                      "specialties", "hq", "size"):
            self.assertNotIn(noise, out, f"{noise} escaped the trim")


if __name__ == "__main__":
    unittest.main()
