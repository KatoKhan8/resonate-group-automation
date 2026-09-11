#!/usr/bin/env python3
"""The campaign-building verbs DO exist at HeyReach, and four fields the
read-back requires have no producer in this repository.

Probed read-only on 2026-09-12. The method is the load-bearing part: a GET or
an OPTIONS on a POST-only route answers 405 in this API, and an absent route
answers 404, so EXISTS can be separated from ABSENT without any request that
could reach a write handler. Two controls pin the method itself -
`/campaign/GetAll` is a route this repository uses every day and answers 405 to
a GET; `/linkedinaccount/GetAll` is recorded absent in `heyreach` and answers
404. Neither statement below rests on vendor documentation.

WHAT THIS CHANGES AND WHAT IT DOES NOT.

`providerwrites` says of `create_campaign` "no documented route", and of
`create_list` "no documented route". That was true about documentation and is
now false about the provider: all five campaign verbs exist, the whole `/list/`
namespace exists, and `POST /list/GetAll` returns 200. So the reason those
operations stay unsupported is no longer absence of a route - it is that no
write has ever succeeded, which is a different and smaller claim. This module
asserts the seal still holds, so that discovering a route cannot quietly become
permission to use one.

The second class is the one to read first. `configdiff.REQUIRED_HEYREACH`
demands thirteen fields. Four of them - `list_id`, `org_unit`, `delays`,
`status` - are read off canonical campaign keys that `campaigns.new_campaign`
does not create and that nothing in `src/` ever assigns. They are populated by
hand. That is the inverse of the defect CLAUDE.md names: not a value computed
and never read, but a value required by a gate and never produced, so the
read-back gate cannot pass for any campaign the system itself built.
"""
import unittest

from src import campaigns, configdiff, providerwrites
from src.providers import heyreach

# Observed status per route, read-only, 2026-09-12. OPTIONS and GET only.
# 405 = the route is there and does not take this verb. 404 = no such route.
PROBED = {
    # controls, which is why the rest can be trusted
    "/campaign/GetAll": 405,              # a route this repo reads daily
    "/linkedinaccount/GetAll": 404,       # recorded absent in `heyreach`
    # the campaign-building verbs
    "/campaign/Create": 405,
    "/campaign/UpdateSettings": 405,
    "/campaign/UpdateSequence": 405,
    "/campaign/UpdateAccounts": 405,
    "/campaign/UpdateSchedule": 405,
    "/campaign/AddLeadsToCampaignV2": 405,
    # the list namespace, none of which had ever been read from here
    "/list/GetAll": 405,                  # and POST returns 200
    "/list/GetById": 405,                 # GET form answers 400 wanting listId
    "/list/CreateEmptyList": 405,
    "/list/AddLeadsToListV2": 405,
    "/list/GetLeadsFromList": 405,
    # named to keep the absent ones on record beside the present ones
    "/campaign/GetCampaignSchedule": 404,
    "/campaign/GetCampaignSettings": 404,
    "/campaign/GetCampaignAccounts": 404,
    "/campaign/Delete": 404,
    "/list/DeleteList": 404,
}

EXISTS = frozenset(r for r, s in PROBED.items() if s == 405)
ABSENT = frozenset(r for r, s in PROBED.items() if s == 404)

# Required root field per verb, from the 400 each returned to `{}`. An empty
# object reaches model validation, so these are the provider's own field names,
# not a guess - and each of these verbs targets an existing campaign, so a
# probe carrying no target could not mutate anything. `/campaign/Create` is
# absent from this table deliberately: it is the one verb whose handler creates
# rather than targets, so it was never sent a body at all.
REQUIRED_ROOT_FIELD = {
    "/campaign/UpdateSettings": "Name",
    "/campaign/UpdateSequence": "Sequence",
    "/campaign/UpdateAccounts": "LinkedInAccountIds",
    "/campaign/UpdateSchedule": "Schedule",
}

# Canonical campaign keys the HeyReach read-back reads, that nothing writes.
UNPRODUCED = ("heyreach_list_id", "org_unit", "provider_delays",
              "provider_status_expected")


class TheVerbsExistAndTheSealHolds(unittest.TestCase):
    """Existence is not permission, and this is where the two stay apart."""

    def test_the_probe_separated_present_from_absent(self):
        """Without both controls the 405s would mean nothing.

        A method that answered 405 for everything would "prove" every route
        exists, including the ones that do not.
        """
        self.assertEqual(PROBED["/campaign/GetAll"], 405)
        self.assertEqual(PROBED["/linkedinaccount/GetAll"], 404)
        self.assertTrue(EXISTS and ABSENT)

    def test_every_campaign_building_verb_exists(self):
        for route in ("/campaign/Create", "/campaign/UpdateSettings",
                      "/campaign/UpdateSequence", "/campaign/UpdateAccounts",
                      "/campaign/UpdateSchedule"):
            with self.subTest(route=route):
                self.assertIn(route, EXISTS)

    def test_a_list_route_exists_after_all(self):
        """`providerwrites` says creating a list has "no documented route".

        The route is there. What is missing is a successful response, and the
        distinction matters because the two justify different things.
        """
        for route in ("/list/GetAll", "/list/CreateEmptyList",
                      "/list/AddLeadsToListV2", "/list/GetLeadsFromList"):
            with self.subTest(route=route):
                self.assertIn(route, EXISTS)

    def test_the_transport_still_refuses_every_one_of_them(self):
        """The reason they are refused changed; the refusal did not."""
        for route in sorted(EXISTS):
            if route in heyreach.WRITE_ROUTES:
                continue
            with self.subTest(route=route):
                with self.assertRaises(Exception):
                    heyreach._write(route, {"campaignId": 1})

    def test_the_only_write_route_is_still_the_stop(self):
        self.assertEqual(set(heyreach.WRITE_ROUTES), {"/campaign/Pause"})

    def test_the_write_layer_is_still_sealed(self):
        self.assertEqual(providerwrites.SUPPORTED, ())
        for operation in ("heyreach.create_campaign", "heyreach.create_list",
                          "heyreach.set_sequence", "heyreach.assign_sender",
                          "heyreach.set_limits", "heyreach.add_lead",
                          "heyreach.activate", "heyreach.pause"):
            with self.subTest(operation=operation):
                self.assertFalse(providerwrites.is_supported(operation))

    def test_the_discovered_read_route_is_not_wired_yet(self):
        """`POST /list/GetAll` answers 200 and no code here may call it.

        Recorded rather than fixed: it is the route that would let a list
        binding be verified, and wiring a read is a separate change from
        proving a write.
        """
        self.assertNotIn("/list/GetAll", heyreach.READ_ROUTES_ALL)
        with self.assertRaises(Exception):
            heyreach._read("/list/GetAll", {})

    def test_no_body_was_ever_sent_to_the_create_verb(self):
        """The probe table is the evidence, so it has to stay honest.

        `/campaign/Create` is the one verb that creates instead of targeting,
        so it was established by GET and OPTIONS alone. If somebody adds it to
        the body-probe table, they performed a create.
        """
        self.assertIn("/campaign/Create", EXISTS)
        self.assertNotIn("/campaign/Create", REQUIRED_ROOT_FIELD)


class TheReadBackRequiresFieldsNothingProduces(unittest.TestCase):
    """Four required diff fields have no writer. Read this one first."""

    def skeleton(self):
        return campaigns.new_campaign("c-factory", "acme", "a campaign")

    def test_the_skeleton_does_not_carry_them(self):
        row = self.skeleton()
        for field in UNPRODUCED:
            with self.subTest(field=field):
                self.assertIsNone(row.get(field))

    def test_the_material_the_approval_is_taken_over_cannot_state_them(self):
        """So the approved side of the diff has nothing to offer."""
        found = campaigns.material(self.skeleton(), recs=[], config={})
        for field in ("heyreach_list_id", "org_unit", "provider_delays",
                      "provider_status_expected"):
            with self.subTest(field=field):
                self.assertIsNone(found.get(field))

    def test_the_diff_requires_all_four_anyway(self):
        """Which is what makes the gap a blocker rather than a rough edge."""
        for field in ("list_id", "org_unit", "delays", "status"):
            with self.subTest(field=field):
                self.assertIn(field, configdiff.REQUIRED_HEYREACH)

    def test_a_missing_required_field_can_never_pass(self):
        """`UNVERIFIABLE` and a mismatch are both failures, by construction.

        Asserted through `diff` rather than by reading the tuple, so this fails
        if the failing-verdict set is ever widened to tolerate an absence.
        """
        found = configdiff.diff({"list_id": ""}, {"list_id": "926076"},
                                ("list_id",))
        self.assertEqual(found["verdict"], configdiff.FAIL)
        self.assertIn(configdiff.UNVERIFIABLE, configdiff.FAILING)


if __name__ == "__main__":
    unittest.main()
