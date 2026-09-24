"""The LinkedIn stop read a contact field that has never existed.

MEASURED 2026-09-23, the evening `LINKEDIN_STOP_LEAD` was enabled by operator
decision. `leadstop.stop_linkedin_contact` built its `profile_url` from
`contact["linkedin_url"]`. Across the live store:

    contacts carrying `linkedin`      1,014
    contacts carrying `linkedin_url`      0

So `profile_url` was ALWAYS `""`, and `heyreach.stop_lead_in_campaign`
refuses an empty `leadUrl` - correctly, in its own words, because "the
provider matches on them and a partial body is a call that stops nobody while
returning success".

The email->LinkedIn stop could therefore never have succeeded. Not
intermittently: never.

WHY NOBODY SAW IT. The verb was sealed, so `providerwrites.perform` refused
before the transport ran and the empty URL never reached the provider.
Enabling the verb is precisely what would have made it live. This is the
register's "existence is not function": wired, unit-tested, sealed, and
incapable.

The failure direction was safe - a refusal, not a wrong stop - and that is
the only reason this is a bug report rather than an incident.
"""
import unittest

from src import leadstop, store


CAMPAIGN = {"campaign_id": "productive-linkedin-cohort-v2",
            "client": "productive", "heyreach_campaign_id": 605732}


def _contact(**over):
    contact = {"key": "ck-1", "name": "A Person",
               "linkedin": "https://www.linkedin.com/in/someone",
               "heyreach_lead_id": 313146141}
    contact.update(over)
    return contact


class TestTheFieldNameMatchesTheData(unittest.TestCase):

    def test_the_store_uses_linkedin_and_not_linkedin_url(self):
        """The measurement this fix rests on, asserted against real state so
        it cannot quietly stop being true."""
        plain = wrong = 0
        for rec in store.load():
            for contact in rec.get("contacts") or []:
                if contact.get("linkedin"):
                    plain += 1
                if contact.get("linkedin_url"):
                    wrong += 1
        self.assertGreater(plain, 0, "no contact carries `linkedin` at all")
        self.assertEqual(
            wrong, 0,
            "a contact now carries `linkedin_url`; this fix assumed none did")

    def test_a_dry_run_carries_the_profile_url_from_linkedin(self):
        report = leadstop.stop_linkedin_contact(
            {"id": "rec-1", "client": "productive"}, _contact(),
            "reply_received", campaign=CAMPAIGN, rows=[], live=False)
        self.assertEqual(report["lead_id"], 313146141)
        self.assertEqual(report["channel"], "linkedin")

    def test_the_transport_receives_a_non_empty_url(self):
        """THE DEFECT, in one assertion. The provider refuses an empty
        `leadUrl`, so an empty one here is a stop that can never happen."""
        seen = {}

        def transport(campaign_id, member_id, profile_url):
            seen["url"] = profile_url
            return {"campaign_id": campaign_id, "lead_status": "Finished"}

        real = leadstop.heyreach.stop_lead_in_campaign
        leadstop.heyreach.stop_lead_in_campaign = transport
        self.addCleanup(setattr, leadstop.heyreach,
                        "stop_lead_in_campaign", real)
        try:
            leadstop.stop_linkedin_contact(
                {"id": "rec-1", "client": "productive"}, _contact(),
                "reply_received", campaign=CAMPAIGN, rows=[], live=True)
        except Exception:
            pass                      # the ledger/guard path is not the point
        self.assertEqual(seen.get("url"),
                         "https://www.linkedin.com/in/someone",
                         "the profile url reaching the provider was not the "
                         "contact's `linkedin`")

    def test_an_enriched_row_keyed_linkedin_url_still_works(self):
        """`heyreachfactory` builds enriched rows under `linkedin_url`. The
        fallback is kept so a caller passing one does not start failing."""
        contact = {"key": "ck-1", "heyreach_lead_id": 1,
                   "linkedin_url": "https://www.linkedin.com/in/enriched"}
        seen = {}

        def transport(campaign_id, member_id, profile_url):
            seen["url"] = profile_url
            return {"lead_status": "Finished"}

        real = leadstop.heyreach.stop_lead_in_campaign
        leadstop.heyreach.stop_lead_in_campaign = transport
        self.addCleanup(setattr, leadstop.heyreach,
                        "stop_lead_in_campaign", real)
        try:
            leadstop.stop_linkedin_contact(
                {"id": "rec-1", "client": "productive"}, contact,
                "reply_received", campaign=CAMPAIGN, rows=[], live=True)
        except Exception:
            pass
        self.assertEqual(seen.get("url"),
                         "https://www.linkedin.com/in/enriched")

    def test_a_contact_with_no_profile_at_all_still_refuses(self):
        """The fix must not turn a missing URL into something that reaches
        the provider. Fail-closed stays fail-closed."""
        contact = {"key": "ck-1", "heyreach_lead_id": 1}
        with self.assertRaises(Exception):
            leadstop.stop_linkedin_contact(
                {"id": "rec-1", "client": "productive"}, contact,
                "reply_received", campaign=CAMPAIGN, rows=[], live=True)


class TestTheCrossChannelPopulationIsEmpty(unittest.TestCase):
    """What the 2026-09-23 measurement found underneath the field-name bug.

    The cross-channel stop exists to protect a contact bound on BOTH
    providers. There is not one. Recorded as a test so that the day the 33
    LinkedIn seats are enrolled, this turns red and says what now has to work.
    """

    def test_no_contact_is_bound_on_both_providers_yet(self):
        both = [(rec["id"], c.get("key"))
                for rec in store.load()
                for c in rec.get("contacts") or []
                if c.get("bison_lead_id") and c.get("heyreach_lead_id")]
        self.assertEqual(
            both, [],
            "A contact is now bound on BOTH providers, so the cross-channel "
            "stop finally has a population. Before enrolling further: no "
            "campaign row carries both a bison_campaign_id and a "
            "heyreach_campaign_id, and leadstop._campaign_of returns the "
            "FIRST row holding the record - so one of the two directions "
            "resolves the wrong provider campaign or refuses. Fix that "
            "before this list grows.")


if __name__ == "__main__":
    unittest.main()
