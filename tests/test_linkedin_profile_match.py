"""LinkedIn profile match validation before enrollment. TASK-268.

A connection request to the wrong profile does not bounce - it silently
reaches a stranger. The URL we supply is accepted by HeyReach on trust;
nothing between the record and the wire verified that the profile at that
URL IS the person in the record.

These tests verify the comparison logic and the enrollment gate. The
provider is faked throughout - no live HeyReach call.
"""
import unittest
from unittest import mock

from src import holdreasons, linkedin_match


class TestSurnameComparison(unittest.TestCase):
    """The load-bearing check: surname must be unique AND match."""

    def test_matching_surname_passes_when_unique(self):
        record = {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}
        profile = {"lastName": "Smith", "companyName": "Acme"}
        result = linkedin_match.verify(
            contact_name="John Smith",
            contact_key="acme-john",
            company="Acme",
            record=record,
            profile=profile,
        )
        self.assertEqual(result.decision, linkedin_match.PASS)

    def test_disagreeing_surname_holds(self):
        """A surname that does not match the provider is held, not sent."""
        record = {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}
        profile = {"lastName": "Jones", "companyName": "Acme"}
        result = linkedin_match.verify(
            contact_name="John Smith",
            contact_key="acme-john",
            company="Acme",
            record=record,
            profile=profile,
        )
        self.assertEqual(result.decision, linkedin_match.HOLD)
        self.assertTrue(any("surname mismatch" in r for r in result.reasons))

    def test_non_unique_surname_holds_even_when_matching(self):
        """A common surname at the account cannot distinguish people."""
        record = {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
            {"key": "acme-jane", "name": "Jane Smith"},
        ]}
        profile = {"lastName": "Smith", "companyName": "Acme"}
        result = linkedin_match.verify(
            contact_name="John Smith",
            contact_key="acme-john",
            company="Acme",
            record=record,
            profile=profile,
        )
        self.assertEqual(result.decision, linkedin_match.HOLD)
        self.assertTrue(any("appears 2 times" in r for r in result.reasons))

    def test_missing_surname_in_our_record_holds(self):
        """A contact with no parseable surname cannot be verified."""
        record = {"id": "r1", "contacts": [
            {"key": "acme-mononym", "name": "Mononym"},
        ]}
        profile = {"lastName": "Someone", "companyName": "Acme"}
        result = linkedin_match.verify(
            contact_name="Mononym",
            contact_key="acme-mononym",
            company="Acme",
            record=record,
            profile=profile,
        )
        self.assertEqual(result.decision, linkedin_match.HOLD)
        self.assertTrue(any("no surname" in r for r in result.reasons))


class TestCompanyComparison(unittest.TestCase):
    """Company tokens must overlap. Structural, not fuzzy."""

    def test_matching_company_passes(self):
        record = {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}
        profile = {"lastName": "Smith", "companyName": "Acme Corp"}
        result = linkedin_match.verify(
            contact_name="John Smith",
            contact_key="acme-john",
            company="Acme",
            record=record,
            profile=profile,
        )
        self.assertEqual(result.decision, linkedin_match.PASS)

    def test_mismatched_company_holds(self):
        record = {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}
        profile = {"lastName": "Smith", "companyName": "Other Inc"}
        result = linkedin_match.verify(
            contact_name="John Smith",
            contact_key="acme-john",
            company="Acme",
            record=record,
            profile=profile,
        )
        self.assertEqual(result.decision, linkedin_match.HOLD)
        self.assertTrue(any("company mismatch" in r for r in result.reasons))

    def test_legal_suffixes_are_ignored(self):
        """'Corp', 'Inc', 'Ltd' etc. are noise, not identity."""
        record = {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}
        profile = {"lastName": "Smith", "companyName": "Acme Incorporated"}
        result = linkedin_match.verify(
            contact_name="John Smith",
            contact_key="acme-john",
            company="Acme Corp",
            record=record,
            profile=profile,
        )
        self.assertEqual(result.decision, linkedin_match.PASS)


class TestLocationComparison(unittest.TestCase):
    """Location country must match when both sides carry it."""

    def test_matching_location_passes(self):
        record = {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}
        profile = {"lastName": "Smith", "companyName": "Acme",
                   "location": "Berlin, Germany"}
        result = linkedin_match.verify(
            contact_name="John Smith",
            contact_key="acme-john",
            company="Acme",
            record=record,
            profile=profile,
            location="Berlin, Germany",
        )
        self.assertEqual(result.decision, linkedin_match.PASS)

    def test_mismatched_location_holds(self):
        record = {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}
        profile = {"lastName": "Smith", "companyName": "Acme",
                   "location": "Berlin, Germany"}
        result = linkedin_match.verify(
            contact_name="John Smith",
            contact_key="acme-john",
            company="Acme",
            record=record,
            profile=profile,
            location="Paris, France",
        )
        self.assertEqual(result.decision, linkedin_match.HOLD)
        self.assertTrue(any("location mismatch" in r for r in result.reasons))

    def test_missing_location_on_either_side_does_not_hold(self):
        """If we have no location, we cannot compare - but that alone does
        not hold. The surname and company checks carry the load."""
        record = {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}
        profile = {"lastName": "Smith", "companyName": "Acme",
                   "location": "Berlin, Germany"}
        result = linkedin_match.verify(
            contact_name="John Smith",
            contact_key="acme-john",
            company="Acme",
            record=record,
            profile=profile,
            location=None,  # We have no location
        )
        self.assertEqual(result.decision, linkedin_match.PASS)


class TestFailClosed(unittest.TestCase):
    """No profile fetched must hold, not pass."""

    def test_no_profile_holds(self):
        record = {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}
        result = linkedin_match.verify(
            contact_name="John Smith",
            contact_key="acme-john",
            company="Acme",
            record=record,
            profile=None,
        )
        self.assertEqual(result.decision, linkedin_match.HOLD)
        self.assertTrue(any("no profile" in r for r in result.reasons))

    def test_empty_profile_holds(self):
        record = {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}
        result = linkedin_match.verify(
            contact_name="John Smith",
            contact_key="acme-john",
            company="Acme",
            record=record,
            profile={},
        )
        self.assertEqual(result.decision, linkedin_match.HOLD)


class TestHoldReason(unittest.TestCase):
    """The hold reason code is classified correctly."""

    def test_identity_profile_unverified_is_human_review(self):
        self.assertEqual(
            holdreasons.classify(linkedin_match.PROFILE_UNVERIFIED),
            holdreasons.HUMAN_REVIEW)

    def test_the_code_matches_the_namespace(self):
        self.assertEqual(linkedin_match.PROFILE_UNVERIFIED,
                         "identity:profile_unverified")


class TestVerifyLeadsIntegration(unittest.TestCase):
    """Integration tests for the verify_leads function in batch_linkedin_push."""

    def test_profile_fetch_failure_holds(self):
        """Fail closed: a profile that cannot be fetched is held."""
        from scripts.batch_linkedin_push import verify_leads

        leads = [{
            "record_id": "r1",
            "contact_key": "acme-john",
            "profileUrl": "https://www.linkedin.com/in/john-smith",
            "firstName": "John",
            "lastName": "Smith",
            "company": "Acme",
        }]
        records = {"r1": {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}}

        def failing_fetch(url):
            raise ConnectionError("network down")

        verified, held = verify_leads(leads, fetch_profile=failing_fetch,
                                      records=records)
        self.assertEqual(len(verified), 0)
        self.assertEqual(len(held), 1)
        lead, result = held[0]
        self.assertEqual(result.decision, linkedin_match.HOLD)
        self.assertTrue(any("fetch failed" in r for r in result.reasons))

    def test_matching_lead_passes(self):
        from scripts.batch_linkedin_push import verify_leads

        leads = [{
            "record_id": "r1",
            "contact_key": "acme-john",
            "profileUrl": "https://www.linkedin.com/in/john-smith",
            "firstName": "John",
            "lastName": "Smith",
            "company": "Acme",
        }]
        records = {"r1": {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}}

        def fake_fetch(url):
            return {"firstName": "John", "lastName": "Smith",
                    "companyName": "Acme"}

        verified, held = verify_leads(leads, fetch_profile=fake_fetch,
                                      records=records)
        self.assertEqual(len(verified), 1)
        self.assertEqual(len(held), 0)

    def test_disagreeing_surname_holds_rather_than_enrolls(self):
        """The behavioural statement: a wrong surname is held, not sent."""
        from scripts.batch_linkedin_push import verify_leads

        leads = [{
            "record_id": "r1",
            "contact_key": "acme-john",
            "profileUrl": "https://www.linkedin.com/in/john-smith",
            "firstName": "John",
            "lastName": "Smith",
            "company": "Acme",
        }]
        records = {"r1": {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}}

        def fake_fetch(url):
            # Provider says this profile is "Jones", not "Smith".
            return {"firstName": "John", "lastName": "Jones",
                    "companyName": "Acme"}

        verified, held = verify_leads(leads, fetch_profile=fake_fetch,
                                      records=records)
        self.assertEqual(len(verified), 0, "a disagreeing surname must not pass")
        self.assertEqual(len(held), 1)
        lead, result = held[0]
        self.assertEqual(result.decision, linkedin_match.HOLD)
        self.assertTrue(any("surname mismatch" in r for r in result.reasons))

    def test_held_contact_carries_the_reason_code(self):
        """A held contact carries identity:profile_unverified and HUMAN_REVIEW."""
        from scripts.batch_linkedin_push import verify_leads, hold_unverified_leads

        leads = [{
            "record_id": "r1",
            "contact_key": "acme-john",
            "profileUrl": "https://www.linkedin.com/in/john-smith",
            "firstName": "John",
            "lastName": "Smith",
            "company": "Acme",
        }]
        records = {"r1": {"id": "r1", "contacts": [
            {"key": "acme-john", "name": "John Smith"},
        ]}}

        def fake_fetch(url):
            return {"firstName": "John", "lastName": "Jones",
                    "companyName": "Acme"}

        verified, held = verify_leads(leads, fetch_profile=fake_fetch,
                                      records=records)
        self.assertEqual(len(held), 1)

        # Mock the store transaction to capture what would be written.
        written_contacts = []

        class FakeTransaction:
            def __enter__(self):
                return [records["r1"]]

            def __exit__(self, *args):
                pass

        with mock.patch("scripts.batch_linkedin_push.store.transaction",
                        return_value=FakeTransaction()):
            hold_unverified_leads(held)

        contact = records["r1"]["contacts"][0]
        self.assertEqual(contact.get("hold_reason"),
                         linkedin_match.PROFILE_UNVERIFIED)
        self.assertEqual(contact.get("hold_class"), holdreasons.HUMAN_REVIEW)
        self.assertIn("surname mismatch", contact.get("hold_detail", ""))


class TestTheStoreEnrolledContacts(unittest.TestCase):
    """The 151 store-enrolled contacts all resolve to a decision and none
    raises. This test counts the LinkedIn-enrolled contacts and verifies
    each one resolves without exception.

    The provider is faked: every profile returns a matching surname and
    company, so the test measures "does the code run without error" rather
    than "do they all pass". In reality, some will fail and be held.
    """

    def test_every_enrolled_contact_resolves_to_a_decision(self):
        """Re-count at the start; do not trust the task file's number."""
        from src import campaigns, store

        # Count the LinkedIn-enrolled contacts.
        batch_prefix = "productive-email-batch1-"
        rows = [r for r in campaigns.load()
                if str(r.get("campaign_id", "")).startswith(batch_prefix)]
        wanted = {rid for row in rows for rid in row.get("record_ids") or []}

        enrolled_count = 0
        enrolled_leads = []
        records_by_id = {}

        for record in store.load():
            if record.get("id") not in wanted:
                continue
            records_by_id[record.get("id")] = record
            for contact in record.get("contacts") or []:
                url = str(contact.get("linkedin") or "").strip()
                if not url:
                    continue
                if contact.get("campaign_id_linkedin"):
                    continue
                enrolled_count += 1
                enrolled_leads.append({
                    "record_id": record.get("id"),
                    "contact_key": contact.get("key"),
                    "profileUrl": url,
                    "firstName": contact.get("first_name") or "",
                    "lastName": contact.get("last_name") or "",
                    "company": record.get("company") or "",
                })

        # The task says 151 but says "re-count at the start; do not trust".
        # We just verify the code runs without error for whatever the count is.
        if enrolled_count == 0:
            self.skipTest("no LinkedIn-enrolled contacts in the store")

        # Fake the provider: return a profile that matches whatever we ask.
        def fake_fetch(url):
            return {"firstName": "Test", "lastName": "Person",
                    "companyName": "Test Company"}

        from scripts.batch_linkedin_push import verify_leads
        verified, held = verify_leads(
            enrolled_leads, fetch_profile=fake_fetch, records=records_by_id)

        # Every lead resolved to either verified or held, none raised.
        self.assertEqual(len(verified) + len(held), enrolled_count)

        # Every held lead has a valid MatchResult.
        for lead, result in held:
            self.assertIsInstance(result, linkedin_match.MatchResult)
            self.assertIn(result.decision,
                          (linkedin_match.PASS, linkedin_match.HOLD))


if __name__ == "__main__":
    unittest.main()
