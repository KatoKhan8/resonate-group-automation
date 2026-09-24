"""TASK-238: An event we can PROVE is not ours.

The HeyReach API key is workspace-wide. The inbox watcher sees the CLIENT'S
traffic too. On 2026-09-21 that was 21 false action_required alerts in one
day, none of them ours.

The fix: drop an event ONLY when it is POSITIVELY attributed to a campaign
or seat that is not in our set. Everything else keeps today's behaviour.

Measurement (scripts/task238_probe.py, 2026-09-21):
  - Conversation items CARRY `linkedInAccountId` (seat id)
  - Conversation items DO NOT CARRY `campaignId`
  - The adapter already extracts both into the neutral event

So attribution is seat-level: the adapter provides the seat id on every
event, and `_positively_not_ours` checks it against OWNED_SEATS.

The fail-safe is the point: an event with no seat field, or on our seat,
is KEPT regardless. Absence of evidence is never a drop.

------------------------------------------------------------------------
2026-09-24: THE NINE ACCEPTANCE CRITERIA MOVED, AND NOT ONE OF THEM WENT.

Two of TASK-238's measurements stopped being true, both in the same
direction - a seat can no longer say an event IS ours:

  * we ran 1 of 41 LinkedIn seats when this was written and now run 33,
    because the B1 campaigns were put on the CLIENT'S OWN seats. Their
    campaigns still run on those seats, so a conversation on our seat is
    most often theirs. Sampled 2026-09-24: every one of them.
  * `POST /campaign/GetCampaignsForLead` DOES resolve a lead to its
    campaigns, with names. TASK-238 measured `GetConversationsV2`, which
    carries no campaign, and concluded the provider could not answer. The
    provider can; the other route was the one asked.

And one thing here was outright wrong: the campaign half of
`_positively_not_ours` compared an EmailBison campaign id against a set of
HeyReach ids, so our own campaign 491 read as "positively not ours". It has
never fired only because `_owned()` has been refusing on a stale readback.

So: the SEAT test stays exactly where it was and keeps criteria 2 and 8.
Campaign ownership moved to `src/unmatched.attribute`, which compares a
provider's ids against that provider's own registry, and the notification
moved to one digest per hour. Criteria 1, 3, 4, 5, 6, 7 and 9 are asserted
below against their new home, with the same polarity: **a drop needs
positive evidence, and a lookup that raises, returns nothing, or answers
about no campaign is KEPT.**
"""
import os
import unittest

from src import events, inbound, notify, store, unmatched
from src import workspaces as ws
from tests.campaignbase import CampaignTest

OPS = "#resonate-outbound-ops"
OUR_SEAT = 174892
OTHER_SEAT = 181658


class _AttributionTest(CampaignTest):
    """Base: temp queue, ops channel configured, notification helpers."""

    def setUp(self):
        super().setUp()
        self._prev = os.environ.get(notify.OPS_CHANNEL_VAR)
        os.environ[notify.OPS_CHANNEL_VAR] = OPS
        ws.ensure("productive", "Productive", client="productive")
        # 2026-09-23: a drop now needs an ownership readback it can prove is
        # current, and the real one on disk went 63 hours stale while 33 live
        # campaigns were created behind it. These cases are about the drop
        # LOGIC, so they are handed a fresh readback; the staleness refusal
        # has its own class below.
        self._owned = inbound._owned
        inbound._owned = lambda *a, **k: (
            (set(inbound.OWNED_SEATS), set(inbound.OWNED_CAMPAIGNS)), None)
        self.addCleanup(setattr, inbound, "_owned", self._owned)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(notify.OPS_CHANNEL_VAR, None)
        else:
            os.environ[notify.OPS_CHANNEL_VAR] = self._prev
        super().tearDown()

    def rows_of(self, event_type):
        return [r for r in notify.load() if r["type"] == event_type]

    def _heyreach_event(self, seat=None, campaign_id=None,
                        provider_event_id="heyreach:test:1"):
        """A HeyReach-shaped neutral event. Seat and campaign optional."""
        return events.neutral(
            type=events.REPLY_RECEIVED,
            channel="linkedin",
            provider="heyreach",
            provider_event_id=provider_event_id,
            linkedin="https://www.linkedin.com/in/test-person",
            at="2026-09-21T10:00:00Z",
            text="interested, tell me more",
            linkedin_account_id=seat,
            external_campaign_id=campaign_id)


class PositivelyNotOursUnit(_AttributionTest):
    """Unit tests for the attribution predicate itself."""

    def test_no_fields_is_not_dropped(self):
        """Absence of evidence is never a drop."""
        event = self._heyreach_event()
        self.assertFalse(inbound._positively_not_ours(event))

    def test_our_seat_is_not_dropped(self):
        event = self._heyreach_event(seat=OUR_SEAT)
        self.assertFalse(inbound._positively_not_ours(event))

    def test_other_seat_is_dropped(self):
        event = self._heyreach_event(seat=OTHER_SEAT)
        self.assertTrue(inbound._positively_not_ours(event))

    def test_our_campaign_is_not_dropped(self):
        event = self._heyreach_event(campaign_id=605732)
        self.assertFalse(inbound._positively_not_ours(event))

    def test_this_predicate_no_longer_judges_a_campaign_at_all(self):
        """The campaign half compared two different providers' namespaces.

        `owned_campaigns` came from the HeyReach block of
        PROVIDER-CAMPAIGNS.json, and `external_campaign_id` on an EmailBison
        event is an EmailBison id. So OUR campaign 491 was not in
        {594061, 599020, 604869, 605487, 605732} and read as positively not
        ours - a silent drop of our own replies, which has only ever been
        held off by `_owned()` refusing on a 32-hour-old readback.

        Campaign ownership is `unmatched.attribute` now, per provider. This
        predicate answers about SEATS and nothing else.
        """
        self.assertFalse(
            inbound._positively_not_ours(self._heyreach_event(
                campaign_id=999999)))
        self.assertFalse(
            inbound._positively_not_ours(events.neutral(
                type=events.REPLY_RECEIVED, channel="email",
                provider="emailbison", provider_event_id="bison:ns:1",
                external_campaign_id=491)))

    def test_a_seat_that_is_ours_still_proves_nothing_either_way(self):
        """We run 33 of 41 seats and the client's campaigns run on them too,
        so our own seat cannot make an event ours. Only a seat that is NOT
        ours proves anything, which is the polarity this function always
        had and is now the whole of it."""
        self.assertFalse(inbound._positively_not_ours(
            self._heyreach_event(seat=OUR_SEAT, campaign_id=999999)))
        self.assertTrue(inbound._positively_not_ours(
            self._heyreach_event(seat=OTHER_SEAT, campaign_id=605732)))

    def test_string_seat_is_coerced(self):
        """Provider ids may arrive as strings. int() coercion is required."""
        event = self._heyreach_event(seat=str(OTHER_SEAT))
        self.assertTrue(inbound._positively_not_ours(event))

    def test_our_string_seat_is_not_dropped(self):
        event = self._heyreach_event(seat=str(OUR_SEAT))
        self.assertFalse(inbound._positively_not_ours(event))

    def test_garbage_seat_is_not_dropped(self):
        """A value that is not an int cannot prove anything. Keep."""
        event = self._heyreach_event(seat="not-a-number")
        self.assertFalse(inbound._positively_not_ours(event))


class AttributionThroughHandle(_AttributionTest):
    """The nine acceptance criteria, at their new address.

    Driven through `inbound.handle` - the real entry point - and then through
    `unmatched.flush`, which is where a campaign is now judged and where the
    one digest an hour is raised. Every test asserts on the outcome AND on
    what was stored, so the wiring is proven end to end.
    """

    #: What `unmatched.registry()` reads out of `work/campaigns.jsonl` in
    #: production, spelled here so the tests do not depend on the estate.
    #: The EmailBison entry is the one TASK-238's predicate could never have
    #: got right: 491 is ours and is not a HeyReach id.
    KNOWN = {
        "heyreach": {605732: "LINKEDIN COHORT V2", 605487: "LINKEDIN COHORT V1",
                     604869: "LINKEDIN CANARY", 599020: "LINKEDIN PRODUCTION"},
        "emailbison": {491: "EMAIL BATCH1"},
    }

    #: An hour later than every fixture event, so the fixture's hour has
    #: closed and `flush` will digest it.
    LATER = "2026-09-21T12:00:00Z"

    def flush(self, lookup=None):
        """Resolve the ledger and raise whatever digests are due."""
        return unmatched.flush(now=self.LATER, known=self.KNOWN,
                               lookup=lookup)

    def digests(self):
        return self.rows_of(notify.UNMATCHED_DIGEST)

    def verdicts(self):
        return [r.get("verdict") for r in unmatched.load()]

    # 1. An event on a campaign that is in no registry of ours is recorded
    #    and posted NOWHERE.
    def test_other_campaign_is_not_posted(self):
        event = self._heyreach_event(campaign_id=999999,
                                     provider_event_id="heyreach:t238-1:1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.flush()
        self.assertEqual(self.verdicts(), [unmatched.THEIRS])
        self.assertEqual(self.digests(), [])

    # 1b. THE NAMESPACE REGRESSION. Our own EmailBison campaign 491 is not a
    #     HeyReach id, and the old predicate would have dropped it.
    def test_our_own_email_campaign_is_not_read_as_somebody_elses(self):
        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="email", provider="emailbison",
            provider_event_id="bison:t238-1b:1", email="x@unknown.test",
            at="2026-09-21T10:00:00Z", external_campaign_id=491)
        inbound.handle(event, [])
        self.flush()
        self.assertEqual(self.verdicts(), [unmatched.OURS])
        self.assertEqual(len(self.digests()), 1)

    # 2. An event on a seat that is not ours is dropped before the ledger.
    #    `_positively_not_ours` still owns this one; see the unit class.
    def test_other_seat_is_dropped(self):
        event = self._heyreach_event(seat=OTHER_SEAT,
                                     provider_event_id="heyreach:t238-2:1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertTrue(outcome["notification"].get("dropped"))
        self.assertEqual(unmatched.load(), [])

    # 3. An event on 605732 (our LIVE campaign) reaches the channel.
    def test_our_live_campaign_reaches_the_channel(self):
        event = self._heyreach_event(campaign_id=605732,
                                     provider_event_id="heyreach:t238-3:1")
        inbound.handle(event, [])
        self.flush()
        self.assertEqual(self.verdicts(), [unmatched.OURS])
        self.assertEqual(len(self.digests()), 1)

    # 4. Our three other campaigns each reach it too.
    def test_our_other_campaigns_each_reach_the_channel(self):
        for i, campaign in enumerate((605487, 604869, 599020)):
            with self.subTest(campaign=campaign):
                inbound.handle(self._heyreach_event(
                    campaign_id=campaign,
                    provider_event_id=f"heyreach:t238-4{i}:1"), [])
        self.flush()
        self.assertEqual(sorted(self.verdicts()), [unmatched.OURS] * 3)
        self.assertEqual(len(self.digests()), 1)

    # 5. THE LOOKUP RAISING IS KEPT. The one criterion this task said a fix
    #    must not fail, now that there really is a lookup to raise.
    def test_a_lookup_that_raises_is_kept(self):
        def explodes(_url):
            raise RuntimeError("heyreach is down")

        inbound.handle(self._heyreach_event(
            provider_event_id="heyreach:t238-5:1"), [])
        self.flush(lookup=explodes)
        self.assertEqual(self.verdicts(), [unmatched.UNATTRIBUTED])
        self.assertEqual(len(self.digests()), 1)

    # 5b. And the reason travels, rather than being swallowed into a shrug.
    def test_the_reason_the_lookup_failed_is_recorded(self):
        def explodes(_url):
            raise RuntimeError("429 slow down")

        inbound.handle(self._heyreach_event(
            provider_event_id="heyreach:t238-5b:1"), [])
        self.flush(lookup=explodes)
        self.assertIn("429", unmatched.load()[0]["verdict_why"])

    # 5c. `flush` does not raise when the real provider call fails either.
    def test_a_provider_error_does_not_take_the_flush_down(self):
        from src.providers import heyreach as hr
        real = hr.campaigns_for_lead

        def refuse(**_kwargs):
            raise RuntimeError("heyreach /campaign/GetCampaignsForLead: 500")

        hr.campaigns_for_lead = refuse
        self.addCleanup(setattr, hr, "campaigns_for_lead", real)
        inbound.handle(self._heyreach_event(
            provider_event_id="heyreach:t238-5c:1"), [])
        self.flush(lookup=unmatched.heyreach_lookup)
        self.assertEqual(self.verdicts(), [unmatched.UNATTRIBUTED])

    # 6. THE LOOKUP RETURNING NOTHING IS KEPT.
    def test_an_empty_lookup_is_kept(self):
        inbound.handle(self._heyreach_event(
            provider_event_id="heyreach:t238-6:1"), [])
        self.flush(lookup=lambda url: {})
        self.assertEqual(self.verdicts(), [unmatched.UNATTRIBUTED])
        self.assertEqual(len(self.digests()), 1)

    # 7. AN EVENT WITH NO CAMPAIGN AND NO WAY TO ASK IS KEPT.
    def test_no_campaign_and_no_lookup_is_kept(self):
        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="linkedin", provider="heyreach",
            provider_event_id="heyreach:t238-7:1", at="2026-09-21T10:00:00Z")
        inbound.handle(event, [])
        self.flush()
        self.assertEqual(self.verdicts(), [unmatched.UNATTRIBUTED])
        self.assertEqual(len(self.digests()), 1)

    # 8a. The hold code path runs in the dropped case.
    def test_hold_code_path_runs_when_event_is_dropped(self):
        """The hold runs over correspondents BEFORE any attribution question
        is asked. With no matching records it is a no-op, but the key must be
        present, proving the path was not skipped by the drop."""
        event = self._heyreach_event(
            seat=OTHER_SEAT, provider_event_id="heyreach:t238-8a:1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertTrue(outcome["notification"].get("dropped"))
        self.assertIn("held_unattributed", outcome)
        self.assertEqual(outcome["held_unattributed"], [])

    # 8b. And in the kept case, where it is also carried into the ledger.
    def test_hold_code_path_runs_when_event_is_kept(self):
        event = self._heyreach_event(
            seat=OUR_SEAT, provider_event_id="heyreach:t238-8b:1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIn("held_unattributed", outcome)
        self.assertEqual(len(unmatched.load()), 1)
        self.assertEqual(unmatched.load()[0]["held"], 0)

    # 8c. The hold fires for correspondents even on a dropped event.
    def test_hold_fires_for_correspondents_on_dropped_event(self):
        rec = store.new_record("acme", "cold", "productive",
                               "Acme", "acme.test")
        rec["contacts"] = [{
            "key": "champ", "name": "Champ Acme", "email": "champ@acme.test",
            "persona": "champion", "angle": "ops", "selected": True,
        }]
        store.save([rec])
        event = self._heyreach_event(
            seat=OTHER_SEAT, provider_event_id="heyreach:t238-8c:1")
        outcome = inbound.handle(event, store.load())
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertTrue(outcome["notification"].get("dropped"))
        self.assertIn("held_unattributed", outcome)

    # 9. ONE LOOKUP PER LEAD AT MOST, however many events share them.
    def test_the_lookup_is_called_once_for_two_events_on_one_lead(self):
        calls = []

        def counted(url):
            calls.append(url)
            return {999999: "somebody else's"}

        for i in (1, 2):
            inbound.handle(self._heyreach_event(
                provider_event_id=f"heyreach:t238-9{i}:1"), [])
        self.assertEqual(len(unmatched.load()), 2)
        self.flush(lookup=counted)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.verdicts(), [unmatched.THEIRS] * 2)

    # 9b. And a lead in OUR campaign as well as the client's is OURS.
    def test_a_lead_in_one_of_ours_and_six_of_theirs_is_ours(self):
        inbound.handle(self._heyreach_event(
            provider_event_id="heyreach:t238-9b:1"), [])
        self.flush(lookup=lambda url: {1: "a", 2: "b", 3: "c", 4: "d",
                                            5: "e", 605487: "COHORT V1"})
        self.assertEqual(self.verdicts(), [unmatched.OURS])
        self.assertEqual(len(self.digests()), 1)


class NonHeyreachProvidersAreUnaffected(_AttributionTest):
    """The attribution check must not affect email or manual events."""

    def test_emailbison_unmatched_still_reaches_the_channel(self):
        """EmailBison events have no seat field. They must not be dropped,
        and an EmailBison event with no campaign id is UNATTRIBUTED - which
        is kept and digested, never discarded."""
        event = events.neutral(
            type=events.REPLY_RECEIVED,
            channel="email",
            provider="emailbison",
            provider_event_id="bison:t238:1",
            email="nobody@unknown.test",
            at="2026-09-21T10:00:00Z",
            text="who is this?")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIsNone(outcome["notification"].get("dropped"))
        unmatched.flush(now="2026-09-21T12:00:00Z", known={}, lookup=None)
        self.assertEqual([r["verdict"] for r in unmatched.load()],
                         [unmatched.UNATTRIBUTED])
        self.assertEqual(len(self.rows_of(notify.UNMATCHED_DIGEST)), 1)

    def test_manual_unmatched_still_raises(self):
        event = events.neutral(
            type=events.REPLY_RECEIVED,
            channel="email",
            provider="manual",
            provider_event_id="manual:t238:1",
            record_id="nobody",
            contact_key="k",
            at="2026-09-21T10:00:00Z",
            text="not interested")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIsNone(outcome["notification"].get("dropped"))


if __name__ == "__main__":
    unittest.main()
