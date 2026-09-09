"""How old the evidence behind an address is, and why that is not a rule.

There is no expiry in this build. Two independent PASS results satisfy the
two-vendor rule whether they were obtained this morning or two years ago,
while every other freshness question here - research evidence, MX, account
signals - has an ageing rule and reports it.

Choosing a number is not a parser change. It is a claim about how fast a
mailbox goes away and it costs re-verification credits to honour, so
`MANUAL-REVIEW.md` 9b asks a person for it. What was missing was any way
to answer: the question there is "open the contact whose evidence is
oldest and say whether you would send to that address today", and nothing
could tell you which contact that was.

The one thing this must not do is invent a date. A verdict carried over
from before this module existed has no timestamp, and `result()` stamps
`store.now()` when it is not given one - which is right for a call that
just happened and would report a two-year-old verification as today's.
Undated is the answer, and it is said out loud.
"""
import unittest

from tests.campaignbase import CampaignTest

from src import verification as v

NOW = "2026-09-07T00:00:00+00:00"
OLD = "2024-01-01T00:00:00+00:00"
RECENT = "2026-09-01T00:00:00+00:00"


def verified(email="a@x.test", stamps=(OLD, RECENT)):
    contact = {"email": email}
    evidence = [v.result("contactout", v.S_VALID, email, at=stamps[0]),
                v.result("deliverable", v.S_VALID, email, at=stamps[1])]
    v.apply(contact, v.decide(evidence), evidence)
    return contact


class TheAge(unittest.TestCase):

    def test_the_oldest_and_the_newest_are_both_reported(self):
        found = v.age_of(verified(), now=NOW)
        self.assertEqual(found["oldest_at"], OLD)
        self.assertEqual(found["newest_at"], RECENT)
        self.assertEqual(found["oldest_days"], 980)
        self.assertEqual(found["newest_days"], 6)

    def test_every_dated_result_is_counted(self):
        self.assertEqual(v.age_of(verified(), now=NOW)["dated"], 2)

    def test_an_address_nobody_asked_about_has_no_age(self):
        found = v.age_of({"email": "nobody@x.test"}, now=NOW)
        self.assertIsNone(found["oldest_days"])
        self.assertEqual(found["dated"], 0)

    def test_a_legacy_verdict_is_undated_rather_than_new(self):
        """The whole point. `result()` stamps the moment it was read when
        it is not told one, and reading a two-year-old record today would
        otherwise report it as verified today."""
        legacy = {"email": "b@x.test", "verdict": "valid",
                  "reoon": {"is_safe_to_send": True}}
        found = v.age_of(legacy, now=NOW)
        self.assertEqual(found["dated"], 0)
        self.assertEqual(found["undated"], 2)
        self.assertIsNone(found["oldest_days"])

    def test_a_legacy_verdict_still_verifies(self):
        """Undating it must not change what it decides. The age is a
        report; the two-vendor rule is unchanged."""
        legacy = {"email": "b@x.test", "verdict": "valid",
                  "reoon": {"is_safe_to_send": True}}
        decision = v.resolve(legacy)
        self.assertEqual(decision["confirmation_count"], 2)

    def test_a_naive_timestamp_is_unreadable_rather_than_utc(self):
        contact = verified(stamps=("2024-01-01T00:00:00", RECENT))
        found = v.age_of(contact, now=NOW)
        self.assertEqual(found["dated"], 1)
        self.assertEqual(found["undated"], 1)
        self.assertEqual(found["oldest_at"], RECENT)

    def test_it_reads_the_same_evidence_the_decision_reads(self):
        """If these could diverge, the age would describe evidence that is
        not what the address was cleared on."""
        contact = verified()
        self.assertEqual(v.age_of(contact, now=NOW)["dated"],
                         len(v.all_evidence(contact)))


class OnTheScreen(unittest.TestCase):

    def block(self, contact):
        from src.web import pages

        decision = v.resolve(contact)
        return pages.verification_block({
            "address": contact.get("email"),
            "confirmations": decision["confirmation_count"],
            "required": decision["required_confirmations"],
            "confirmed_by": decision["confirmed_by"],
            "state": decision["state"], "why": decision["reason"],
            "sendable": True, "results": {}, "providers": [],
            "age": v.age_of(contact, now=NOW)})

    def test_it_says_how_old_and_that_there_is_no_rule(self):
        html = self.block(verified())
        self.assertIn("980 day(s) old", html)
        self.assertIn("no expiry rule", html)

    def test_an_undated_verdict_says_why_it_cannot_say(self):
        legacy = {"email": "b@x.test", "verdict": "valid",
                  "reoon": {"is_safe_to_send": True}}
        html = self.block(legacy)
        self.assertIn("undated", html)
        self.assertIn("confident wrong answer", html)


class InTheExport(CampaignTest):
    """The manual-review question is "which contact is oldest", and a
    spreadsheet is how somebody answers it across a whole workspace."""

    def exported(self, contact):
        from src import repo as repo_module, store
        from src.web import api

        rec = store.new_record("x", "domains", "demo", "X Ltd", "x.test")
        rec["contacts"] = [dict(contact, key="x-person", name="A Person")]
        store.save([rec])
        return api.export_contacts(repo_module.Repo.for_client("demo"))

    def test_the_column_carries_the_number(self):
        csv_text = self.exported(verified())
        header, row = csv_text.splitlines()[0], csv_text.splitlines()[1]
        self.assertIn("oldest_evidence_days", header.split(","))
        column = header.split(",").index("oldest_evidence_days")
        self.assertTrue(row.split(",")[column].strip(),
                        "the column is there and empty, which sorts to the "
                        "same place as new")

    def test_an_undated_contact_leaves_it_blank_rather_than_zero(self):
        """Blank sorts nowhere. Zero sorts to "verified today"."""
        csv_text = self.exported({"email": "b@x.test", "verdict": "valid",
                                  "reoon": {"is_safe_to_send": True}})
        header, row = csv_text.splitlines()[0], csv_text.splitlines()[1]
        column = header.split(",").index("oldest_evidence_days")
        self.assertEqual(row.split(",")[column].strip(), "")


if __name__ == "__main__":
    unittest.main()
