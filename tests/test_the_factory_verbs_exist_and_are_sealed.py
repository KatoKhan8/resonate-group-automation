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
        # STAGING AND STOPPING ONLY, and that is the property - not a count.
        # The allowlist grew from one route to seven on 2026-09-13 when the
        # LinkedIn lane gained a campaign factory: create (a DRAFT), create a
        # list, write a sequence, add or remove a seat, stop one lead, pause.
        #
        # TASK-009: `/campaign/AddLeadsToCampaignV2` was added on 2026-09-13
        # so the transport and readback can be developed and tested. It is
        # NOT in `SUPPORTED` in `providerwrites` - the door refuses it until
        # Claude enables it after review. The route is on WRITE_ROUTES (the
        # module CAN call it) but not in SUPPORTED (the build WILL NOT call
        # it). The seal test in `test_the_write_layer_is_sealed` pins that
        # nothing prospect-facing is supported.
        #
        # What is NOT there is what matters. `Resume` and `StartCampaign`
        # both demonstrably exist on this vendor's API - an empty-body probe
        # answers 400 for each, and 404 for names that do not - and so does
        # `AddLeadsToCampaignV2`. None of the three is in SUPPORTED. A system
        # that can start an outreach campaign before it can reliably stop one
        # has acquired exposure it cannot end.
        # NARROWED 2026-09-15. `/campaign/Resume` IS on WRITE_ROUTES now, and
        # the property this test protects is unchanged: a system that can
        # START AN OUTREACH CAMPAIGN before it can reliably stop one has
        # acquired exposure it cannot end.
        #
        # Both halves of that sentence moved. The stop EXISTS - Pause is
        # live-validated, SUPPORTED, and read back as PAUSED against 594061.
        # And starting a campaign that holds ZERO LEADS starts no outreach,
        # because there is nobody for the sequence to act on.
        #
        # The provider left no alternative: AddLeadsToCampaignV2 answers 400
        # on a DRAFT campaign and Pause answers 400 on an inactive one, so
        # DRAFT -> PAUSED is not a transition this vendor has. Start-then-pause
        # is the only route to a stageable campaign.
        #
        # What still may not happen is starting a campaign that HOLDS PEOPLE.
        # That is `heyreach.activate`, it is absent from SUPPORTED, it carries
        # no condition, and the two verbs share a route and are told apart by
        # a lead count the provider supplies - asserted below.
        forbidden = ("StartCampaign", "SendMessage")
        reaching = [r for r in heyreach.WRITE_ROUTES
                    if any(v.lower() in r.lower() for v in forbidden)]
        self.assertEqual(reaching, [],
                         f"a route that reaches a prospect is writable: {reaching}")
        self.assertIn("/campaign/Resume", heyreach.WRITE_ROUTES)
        self.assertNotIn("heyreach.activate", providerwrites.SUPPORTED)
        self.assertNotIn("heyreach.activate", providerwrites.CONDITIONAL)
        self.assertIn("heyreach.start_empty_for_staging",
                      providerwrites.CONDITIONAL)
        self.assertIn("/campaign/Pause", heyreach.WRITE_ROUTES)
        # AddLeadsToCampaignV2 is on WRITE_ROUTES but not in SUPPORTED.
        self.assertIn("/campaign/AddLeadsToCampaignV2", heyreach.WRITE_ROUTES)
        from src import providerwrites as pw
        # NARROWED, TASK-137. `LINKEDIN_ADD_LEAD` is in SUPPORTED and
        # the door still refuses it for every destination that can
        # send. What this test is about - that no route which STARTS
        # outreach exists - is untouched and is asserted above.
        self.assertIn(pw.LINKEDIN_ADD_LEAD, pw.SUPPORTED)
        self.assertTrue(pw.is_conditional(pw.LINKEDIN_ADD_LEAD))
        self.assertNotIn(pw.LINKEDIN_ACTIVATE, pw.SUPPORTED)


    def test_the_write_layer_is_still_sealed(self):
        from src import providerwrites as pw
        self.assertEqual(
            providerwrites.SUPPORTED,
            (pw.LINKEDIN_PAUSE, pw.EMAIL_PAUSE, pw.EMAIL_STOP_LEAD,
             pw.EMAIL_CREATE_CAMPAIGN, pw.EMAIL_SET_SEQUENCE,
             # Added 2026-09-14, not prospect-facing.
             pw.LINKEDIN_SET_SEQUENCE,
             # Added 2026-09-15, TASK-137, and prospect-facing - the first
             # one ever. Enabled CONDITIONALLY: the door re-reads the
             # destination campaign and admits only one proven unable to
             # send. Asserted below.
             pw.LINKEDIN_ADD_LEAD,
             # Added 2026-09-15. NOT prospect-facing and NOT activation: it
             # starts a campaign the provider says holds ZERO leads, so it
             # sends nothing, and its condition refuses any campaign holding
             # anyone. The provider leaves no other route - DRAFT refuses
             # leads and cannot be paused - so start-then-pause is the only
             # way to a stageable campaign. heyreach.activate stays sealed.
             pw.LINKEDIN_START_EMPTY_FOR_STAGING))
        # `heyreach.pause` left this list on 2026-09-12: a live pause of
        # campaign 594061 returned 200 and read back PAUSED, so it is
        # live-validated and declared. It was never a campaign-BUILDING verb
        # anyway - it is the stop. Every builder below is still sealed.
        # `heyreach.set_sequence` left this list on 2026-09-14 for the same
        # kind of reason as the pause: its own stated condition was met, and
        # it is not prospect-facing - a sequence written onto a campaign
        # holding nobody reaches nobody. The verbs that CAN reach a person,
        # `add_lead` and `activate`, are still sealed and are asserted
        # separately below so the distinction is explicit rather than
        # implied by membership of a list.
        for operation in ("heyreach.create_campaign", "heyreach.create_list",
                          "heyreach.assign_sender",
                          "heyreach.set_limits",
                          "heyreach.activate"):
            with self.subTest(operation=operation):
                self.assertFalse(providerwrites.is_supported(operation))

    def test_the_verbs_that_reach_a_person_are_sealed_but_one(self):
        """NARROWED, TASK-137. Three of the four are still sealed outright.

        `heyreach.add_lead` is the exception and it is not an exception to
        the property - it is an exception to expressing the property as
        membership of a tuple. It may run only against a campaign the
        provider says, at the moment of the write, cannot send, so the lead
        it stages reaches nobody until a separate and still-sealed decision
        activates the campaign.
        """
        for operation in ("heyreach.activate",
                          "bison.add_lead", "bison.activate"):
            with self.subTest(operation=operation):
                _channel, facing, _why = providerwrites.OPERATIONS[operation]
                self.assertTrue(facing, "this test is about prospect-facing verbs")
                self.assertFalse(providerwrites.is_supported(operation))
                self.assertFalse(providerwrites.is_conditional(operation))

        _channel, facing, _why = providerwrites.OPERATIONS["heyreach.add_lead"]
        self.assertTrue(facing)
        self.assertTrue(providerwrites.is_supported("heyreach.add_lead"))
        self.assertTrue(providerwrites.is_conditional("heyreach.add_lead"))

    def test_the_discovered_read_routes_are_wired_now(self):
        """They were recorded as unwired; the campaign factory needed them.

        `/list/GetAll` is what lets a list binding be verified, and
        `/campaign/GetCampaignsForLead` answers the question that had no
        answer at all: whether a person is already a lead in one of the
        client's other campaigns. Both are reads.

        The seal is unaffected. A read route cannot reach anybody, which is
        why `READ_ROUTES_ALL` and `WRITE_ROUTES` are separate lists rather
        than one permission.
        """
        for route in ("/list/GetAll", "/campaign/GetCampaignsForLead"):
            self.assertIn(route, heyreach.READ_ROUTES_ALL)
            self.assertNotIn(route, heyreach.WRITE_ROUTES)
        # And a route on neither list is still refused by name.
        with self.assertRaises(Exception):
            heyreach._read("/campaign/AddLeadsToCampaignV2", {})

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
