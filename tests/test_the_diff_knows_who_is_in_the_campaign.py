#!/usr/bin/env python3
"""The provider's lead identities are readable, and the diff now asks.

`configdiff` rested a load-bearing argument on a premise that was false. Rule 3
of its docstring said "HeyReach exposes no route for a campaign's lead
identities", so `lead_set` came back `UNVERIFIABLE`, was left out of
`REQUIRED_HEYREACH`, and a staged campaign was proven by `lead_count` plus a
verified list id - "the provider holds one lead" rather than "the provider holds
this person".

`/campaign/GetLeadsFromCampaign` returns a profile URL and a
`linkedInUserProfileId` per lead. The identities were readable the whole time.

Two consequences, both asserted here:

  * `lead_set` is diffed and required, so a campaign holding somebody nobody
    approved is `UNEXPECTED` and fails, and one missing an approved person is
    `MISSING` and fails. Previously both passed.
  * `lead_count` comes from that route's `totalCount` rather than from
    `progressStats.totalUsers`, which is a residual that absorbs bucket error -
    three live campaigns report `totalUsersInProgress` as -7, -5 and -6, and on
    the canary it counts a lead that has done nothing.

A partial read is never a lead set. If the provider reports more leads than were
enumerated, or any lead's profile yields no comparable slug, the field goes back
to `UNVERIFIABLE` - a subset would diff PASS against a campaign containing
people nobody approved, which is worse than refusing.

## The CLI crashed every time it ran

`compare_heyreach` returns a sealed `Readback`; `main` unpacked a three-tuple
and raised `TypeError: cannot unpack non-iterable Readback object`. This is the
command an operator runs to verify a provider configuration before a canary, so
it failing was not cosmetic. `executionguard.main` was fixed for exactly this
and carries the note; nothing covered this one.
"""
import unittest
from unittest import mock

from src import configdiff


def a_lead(slug="dana-reed", **over):
    row = {"provider_lead_id": 1, "profile_url":
           f"https://www.linkedin.com/in/{slug}",
           "provider_profile_id": "ACoAAB" + slug, "sender_id": 116968,
           "state": "request_pending", "raw": {}, "error_code": None,
           "at": None, "why": None, "created_at": None}
    row.update(over)
    return row


class TheLeadSetIsRead(unittest.TestCase):

    def leads(self, rows, total=None):
        total = len(rows) if total is None else total
        return mock.patch("src.providers.heyreach.campaign_leads",
                          return_value=(rows, total))

    def test_the_slugs_come_back_as_the_lead_set(self):
        with self.leads([a_lead("dana-reed")]):
            found = configdiff._provider_leads(594061)
        self.assertEqual(found["lead_set"], frozenset({"dana-reed"}))
        self.assertEqual(found["lead_count"], 1)

    def test_several_leads_are_all_enumerated(self):
        with self.leads([a_lead("dana-reed"), a_lead("tomas-brabec")]):
            found = configdiff._provider_leads(594061)
        self.assertEqual(found["lead_set"],
                         frozenset({"dana-reed", "tomas-brabec"}))

    def test_a_count_larger_than_what_was_read_is_unverifiable(self):
        """A PARTIAL READ IS NOT A LEAD SET. A subset would diff PASS against a
        campaign holding people nobody approved."""
        with self.leads([a_lead("dana-reed")], total=900):
            found = configdiff._provider_leads(594061)
        self.assertEqual(found["lead_set"], configdiff.UNVERIFIABLE)
        self.assertEqual(found["lead_count"], 900)

    def test_a_lead_with_no_readable_profile_is_unverifiable(self):
        with self.leads([a_lead("dana-reed"),
                         a_lead(profile_url=None)]):
            found = configdiff._provider_leads(594061)
        self.assertEqual(found["lead_set"], configdiff.UNVERIFIABLE)

    def test_the_count_does_not_come_from_progress_stats(self):
        """`progressStats` goes negative on live campaigns and counts a lead
        that has done nothing on the canary."""
        with self.leads([a_lead("dana-reed")], total=1):
            found = configdiff._provider_leads(594061)
        self.assertEqual(found["lead_count"], 1)


class ProviderHeyreachActuallyCallsIt(unittest.TestCase):
    """A correct reader nothing calls is the defect this repository names.

    A mutation that replaced the call with a hardcoded `UNVERIFIABLE` survived
    every other test here, because they exercise `_provider_leads` directly and
    the diff separately - neither asserts that the function assembling the
    provider side consults it.
    """

    # The root IS the node - `walk_sequence` reads `nodeType` off the object it
    # is handed. A first version wrapped it in a `nodes` list, so the walk found
    # no type, reported `truncated` and the diff refused before it ever reached
    # the leads. Shaped after the canary's real sequence: one connection
    # request, no branches.
    GRAPH = {"nodeType": "CONNECTION_REQUEST", "actionDelayUnit": "HOUR",
             "actionDelay": 0,
             "payload": {"messages": ["hi, worth a word?"],
                         "fallbackMessage": ""}}

    def test_the_provider_side_carries_a_read_lead_set(self):
        row = {"id": 594061, "name": "C", "status": "PAUSED",
               "organizationUnitId": 118832, "campaignAccountIds": [116968],
               "linkedInUserListId": 926076, "progressStats": {"totalUsers": 1}}
        with mock.patch("src.providers.heyreach.campaign_by_id",
                        return_value=row), \
             mock.patch("src.providers.heyreach.campaign_sequence",
                        return_value=self.GRAPH), \
             mock.patch("src.providers.heyreach.campaign_leads",
                        return_value=([a_lead("dana-reed")], 1)) as leads:
            found = configdiff.provider_heyreach(594061)
        self.assertTrue(leads.called, "the lead route was never read")
        self.assertEqual(found["lead_set"], frozenset({"dana-reed"}))
        self.assertNotEqual(found["lead_set"], configdiff.UNVERIFIABLE)

    def test_and_the_count_comes_from_that_route_not_progress_stats(self):
        """`progressStats.totalUsers` says 99 here and the route says 1. The
        route wins, because `progressStats` is a residual - it counts a lead
        that has done nothing on the real canary and goes negative elsewhere."""
        row = {"id": 594061, "name": "C", "status": "PAUSED",
               "organizationUnitId": 118832, "campaignAccountIds": [116968],
               "linkedInUserListId": 926076, "progressStats": {"totalUsers": 99}}
        with mock.patch("src.providers.heyreach.campaign_by_id",
                        return_value=row), \
             mock.patch("src.providers.heyreach.campaign_sequence",
                        return_value=self.GRAPH), \
             mock.patch("src.providers.heyreach.campaign_leads",
                        return_value=([a_lead("dana-reed")], 1)):
            found = configdiff.provider_heyreach(594061)
        self.assertEqual(found["lead_count"], 1)


class TheLeadSetIsRequired(unittest.TestCase):

    def test_it_is_in_the_required_tuple(self):
        self.assertIn("lead_set", configdiff.REQUIRED_HEYREACH)

    def test_and_so_is_the_count(self):
        self.assertIn("lead_count", configdiff.REQUIRED_HEYREACH)

    def test_the_limit_is_still_the_one_unverifiable_field(self):
        """`daily_limit` genuinely has no read route, so it stays out of the
        required set rather than being asserted."""
        self.assertNotIn("daily_limit", configdiff.REQUIRED_HEYREACH)


class AnUnexpectedOrMissingLeadFails(unittest.TestCase):
    """What requiring the field actually buys."""

    def diff(self, approved, provider):
        return configdiff.diff({"lead_set": frozenset(approved)},
                               {"lead_set": frozenset(provider)},
                               required=("lead_set",))

    def test_a_stranger_in_the_campaign_fails(self):
        found = self.diff({"dana-reed"}, {"dana-reed", "somebody-else"})
        self.assertEqual(found["verdict"], configdiff.FAIL)

    def test_an_approved_person_who_is_not_staged_fails(self):
        found = self.diff({"dana-reed", "tomas-brabec"}, {"dana-reed"})
        self.assertEqual(found["verdict"], configdiff.FAIL)

    def test_the_same_set_passes(self):
        found = self.diff({"dana-reed"}, {"dana-reed"})
        self.assertEqual(found["verdict"], configdiff.PASS)

    def test_an_unverifiable_set_fails_when_required(self):
        found = configdiff.diff({"lead_set": frozenset({"dana-reed"})},
                                {"lead_set": configdiff.UNVERIFIABLE},
                                required=("lead_set",))
        self.assertEqual(found["verdict"], configdiff.FAIL)


class TheCliRuns(unittest.TestCase):
    """It raised `TypeError` on every invocation. Nothing covered it."""

    def sealed(self, approved, provider):
        """A real diff dict, not a hand-rolled one: `report` reads keys a mock
        would not have, which is how the first version of this test failed for
        its own reasons rather than the code's."""
        found = mock.Mock()
        found.diff = configdiff.diff(approved, provider,
                                     required=tuple(approved))
        found.approved, found.provider = approved, provider
        return found

    def test_it_does_not_crash_unpacking_the_readback(self):
        sealed = self.sealed({"status": "PAUSED"}, {"status": "PAUSED"})
        with mock.patch.object(configdiff.campaigns_state, "get",
                               return_value={"campaign_id": "c1"}), \
             mock.patch.object(configdiff, "compare_heyreach",
                               return_value=sealed):
            code = configdiff.main(["--campaign", "c1", "--channel", "linkedin"])
        self.assertEqual(code, 0)

    def test_a_failing_diff_exits_non_zero(self):
        sealed = self.sealed({"status": "PAUSED"}, {"status": "IN_PROGRESS"})
        with mock.patch.object(configdiff.campaigns_state, "get",
                               return_value={"campaign_id": "c1"}), \
             mock.patch.object(configdiff, "compare_heyreach",
                               return_value=sealed):
            code = configdiff.main(["--campaign", "c1", "--channel", "linkedin"])
        self.assertEqual(code, 1)

    def test_a_refusal_exits_two(self):
        with mock.patch.object(configdiff.campaigns_state, "get",
                               return_value={"campaign_id": "c1"}), \
             mock.patch.object(configdiff, "compare_heyreach",
                               side_effect=configdiff.DiffRefused("no")):
            code = configdiff.main(["--campaign", "c1", "--channel", "linkedin"])
        self.assertEqual(code, 2)

    def test_an_unknown_campaign_exits_two(self):
        with mock.patch.object(configdiff.campaigns_state, "get",
                               return_value=None):
            code = configdiff.main(["--campaign", "nope", "--channel",
                                    "linkedin"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
