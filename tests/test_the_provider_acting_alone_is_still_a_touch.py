#!/usr/bin/env python3
"""A touch the provider made on its own is still a touch.

`providerwrites.perform` records the canonical confirmed touch when THIS
system writes to the provider. The live canary is the opposite case and it is
not an edge case - it is what is actually happening.

Campaign 594061 was staged and unpaused by hand in the vendor UI, so
`eligibility` answers `blocked:campaign_already_launched` and this system will
never authorize the action. HeyReach sends the connection request on its own
schedule. Resonate OS is not the executor; it can only observe.

Without the reconciler below, the moment that invitation goes out the provider
knows and nothing here does. `funnel` would report zero confirmed actions for
ever, `touch` would see nothing, and the duplication law would have no touch
to refuse a second action against - the repository's named recurring defect,
sitting on the single most safety-relevant fact the provider publishes.

Verified against the real campaign on 2026-09-11: provider lead 304173736
joins to exactly one contact through `linkedin.canonical`, and its state
`request_pending` is correctly outside `heyreach.REACHED`, so a dry run
records nothing. These tests cover what happens when it moves.
"""
import datetime
import unittest
from unittest import mock

from src import account, eligibility, events, fatigue, leadobserve, store
from src.providers import heyreach
from tests.base import QueueTest

PROFILE = "https://www.linkedin.com/in/dana-oyelaran"
PROVIDER_AT = "2026-09-11T09:15:00+00:00"
CAMPAIGN = 594061


def lead(state="request_sent", lead_id=304173736, profile=PROFILE,
         at=PROVIDER_AT):
    """One row in the shape `heyreach.campaign_leads` returns."""
    return {"provider_lead_id": lead_id, "provider_profile_id": "ACoAAB",
            "sender_id": 116968, "state": state, "at": at,
            "profile_url": profile, "raw": {}, "error_code": None,
            "why": None}


class ProviderTouchTest(QueueTest):

    REC = "kw-1"
    CONTACT = "dana"

    def setUp(self):
        super().setUp()
        store.save([self.record()])

    def record(self, rid=None, linkedin=PROFILE, key=None):
        return dict(store.new_record(rid or self.REC, "cold", "productive",
                                     "Kestrel Wharf Studio",
                                     "kestrelwharf.test"),
                    contacts=[{"key": key or self.CONTACT,
                               "name": "Dana Oyelaran",
                               "title": "Operations Director",
                               "linkedin": linkedin}],
                    cadence={key or self.CONTACT: {
                        "day3": {"channel": "linkedin", "day": 3}}})

    def reset(self, *recs):
        """Start an iteration from a clean estate.

        NOT `store.save`. Each loop below records a real touch and then starts
        over, and writing a fresh snapshot over a record that now holds an
        event is exactly what `refuse_history_loss` refuses - correctly. This
        is fixture construction, not a write the product performs, so it goes
        straight to the file.
        """
        store._write(list(recs) or [self.record()])

    def provider(self, *leads):
        return mock.patch.object(heyreach, "campaign_leads",
                                 lambda cid, **kw: (list(leads), len(leads)))

    def confirmed(self):
        return account.touches(store.get(self.REC), self.CONTACT,
                               confirmed_only=True)


class AReachedLeadBecomesATouch(ProviderTouchTest):

    def test_one_reached_lead_writes_one_touch(self):
        with self.provider(lead()):
            out = leadobserve.confirm_touches(CAMPAIGN, live=True)
        self.assertEqual(len(out["recorded"]), 1)
        self.assertEqual(len(self.confirmed()), 1)

    def test_every_reached_state_counts(self):
        """`heyreach.REACHED` is the provider's own vocabulary."""
        for state in heyreach.REACHED:
            with self.subTest(state=state):
                self.reset()
                with self.provider(lead(state=state)):
                    leadobserve.confirm_touches(CAMPAIGN, live=True)
                self.assertEqual(len(self.confirmed()), 1)

    def test_a_pending_lead_writes_nothing(self):
        """The live canary's exact state. Campaign ACTIVE is not a send."""
        with self.provider(lead(state="request_pending", at=None)):
            out = leadobserve.confirm_touches(CAMPAIGN, live=True)
        self.assertEqual(out["recorded"], [])
        self.assertEqual(self.confirmed(), [])

    def test_a_failed_lead_is_not_treated_as_unreached(self):
        """`REACHED` excludes FAILED deliberately - a failed lead may already
        have been accepted. So a FAILED state records nothing here, and that
        is a known gap rather than a claim that nobody was contacted."""
        with self.provider(lead(state="failed")):
            out = leadobserve.confirm_touches(CAMPAIGN, live=True)
        self.assertEqual(out["recorded"], [])


class ItIsDryUntilItIsNot(ProviderTouchTest):

    def test_dry_by_default(self):
        with self.provider(lead()):
            out = leadobserve.confirm_touches(CAMPAIGN)
        self.assertFalse(out["live"])
        self.assertEqual(self.confirmed(), [],
                         "a dry run wrote a confirmed touch")

    def test_dry_still_reports_what_it_would_do(self):
        with self.provider(lead()):
            out = leadobserve.confirm_touches(CAMPAIGN)
        self.assertEqual(len(out["already"]), 1)


class ExactlyOnce(ProviderTouchTest):

    def test_polling_again_appends_nothing(self):
        """A poller runs every minute. A week of that is one touch."""
        for _ in range(4):
            with self.provider(lead()):
                leadobserve.confirm_touches(CAMPAIGN, live=True)
        self.assertEqual(len(self.confirmed()), 1)

    def test_the_repeat_is_reported_as_already_recorded(self):
        with self.provider(lead()):
            leadobserve.confirm_touches(CAMPAIGN, live=True)
        with self.provider(lead()):
            out = leadobserve.confirm_touches(CAMPAIGN, live=True)
        self.assertEqual(out["recorded"], [])
        self.assertEqual(len(out["already"]), 1)

    def test_a_later_state_is_a_second_transition(self):
        """request_sent then accepted are two real events, not one repeated."""
        with self.provider(lead(state="request_sent")):
            leadobserve.confirm_touches(CAMPAIGN, live=True)
        with self.provider(lead(state="accepted")):
            leadobserve.confirm_touches(CAMPAIGN, live=True)
        kinds = [e for e in store.get(self.REC)["events"]
                 if e["type"] == events.PUSH_MARKED]
        self.assertEqual(len(kinds), 2)


class ItIsTheProvidersClock(ProviderTouchTest):

    def test_the_touch_carries_the_providers_timestamp(self):
        """A reconciliation run days later must not claim the invitation went
        out today. `push.mark_pushed`'s own comment records a backfill that
        stamped today's date onto every touch it recreated."""
        with self.provider(lead()):
            leadobserve.confirm_touches(CAMPAIGN, live=True)
        self.assertEqual(self.confirmed()[0]["at"], PROVIDER_AT)

    def test_a_provider_with_no_timestamp_still_records(self):
        with self.provider(lead(at=None)):
            leadobserve.confirm_touches(CAMPAIGN, live=True)
        self.assertEqual(len(self.confirmed()), 1)


class NobodyGuessesWhoItWas(ProviderTouchTest):

    def test_a_lead_matching_no_contact_is_reported_not_guessed(self):
        with self.provider(lead(profile="https://www.linkedin.com/in/nobody")):
            out = leadobserve.confirm_touches(CAMPAIGN, live=True)
        self.assertEqual(out["unmatched"], [304173736])
        self.assertEqual(self.confirmed(), [])

    def test_two_contacts_behind_one_profile_refuses(self):
        """A wrong person is the outcome this module exists to prevent."""
        self.reset(self.record(), self.record(rid="kw-2", key="dana-again"))
        with self.provider(lead()):
            with self.assertRaises(leadobserve.Ambiguous):
                leadobserve.confirm_touches(CAMPAIGN, live=True)

    def test_a_lead_with_no_profile_is_unmatched(self):
        with self.provider(lead(profile="")):
            out = leadobserve.confirm_touches(CAMPAIGN, live=True)
        self.assertEqual(out["unmatched"], [304173736])

    def test_an_alias_spelling_still_finds_them(self):
        """HeyReach returned a percent-encoded profile URL for a seat in this
        very workspace. The join is `linkedin.canonical`, so it holds."""
        for alias in ("https://www.linkedin.com/in/dana-oyelaran/",
                      "https://uk.linkedin.com/in/dana-oyelaran?trk=nav",
                      "https://www.linkedin.com/in/dana-oyelaran#experience",
                      "https://www.linkedin.com/in/dana%2Doyelaran"):
            with self.subTest(alias=alias[:46]):
                self.reset()
                with self.provider(lead(profile=alias)):
                    leadobserve.confirm_touches(CAMPAIGN, live=True)
                self.assertEqual(len(self.confirmed()), 1)


class TheRestOfTheSystemCanSeeIt(ProviderTouchTest):
    """The point of recording it at all. A touch nothing reads is the defect
    this module was written to close, not a fix for it."""

    def test_fatigue_sees_the_touch(self):
        with self.provider(lead(at=datetime.datetime.now(
                datetime.timezone.utc).isoformat())):
            leadobserve.confirm_touches(CAMPAIGN, live=True)
        verdict = fatigue.contact_check(
            store.get(self.REC), self.CONTACT,
            at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        self.assertEqual(verdict["state"], fatigue.BLOCK)

    def test_the_separation_gate_can_place_it_on_a_day(self):
        with self.provider(lead()):
            leadobserve.confirm_touches(CAMPAIGN, live=True)
        self.assertEqual(self.confirmed()[0]["day"], 3)

    def test_it_survives_a_reload(self):
        with self.provider(lead()):
            leadobserve.confirm_touches(CAMPAIGN, live=True)
        reloaded = {r["id"]: r for r in store.load()}[self.REC]
        self.assertEqual(
            len(account.touches(reloaded, self.CONTACT, confirmed_only=True)),
            1)

    def test_a_step_that_cannot_be_placed_is_still_recorded(self):
        """A touch nobody can date is worth far more than no touch."""
        rec = self.record()
        rec["cadence"] = {self.CONTACT: {
            "day3": {"channel": "linkedin", "day": 3},
            "day8": {"channel": "linkedin", "day": 8}}}
        self.reset(rec)
        with self.provider(lead()):
            leadobserve.confirm_touches(CAMPAIGN, live=True)
        self.assertEqual(len(self.confirmed()), 1)


if __name__ == "__main__":
    unittest.main()
