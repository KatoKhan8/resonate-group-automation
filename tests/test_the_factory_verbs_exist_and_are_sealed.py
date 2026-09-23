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
        # `/campaign/StartCampaign` is present too, and Resume was not the
        # verb for a DRAFT campaign after all - it answers 400 "not paused,
        # finished or failed". Resume is ACTIVATION (a paused campaign holds
        # leads); StartCampaign is what moves a never-run campaign, and it is
        # used only against one the provider says holds ZERO leads.
        #
        # What may never be writable is a route that SENDS A MESSAGE
        # directly, which no lead count can make harmless.
        forbidden = ("SendMessage",)
        reaching = [r for r in heyreach.WRITE_ROUTES
                    if any(v.lower() in r.lower() for v in forbidden)]
        self.assertEqual(reaching, [],
                         f"a route that reaches a prospect is writable: {reaching}")
        self.assertIn("/campaign/Resume", heyreach.WRITE_ROUTES)
        self.assertIn("/campaign/StartCampaign", heyreach.WRITE_ROUTES)
        # RE-POINTED 2026-09-16. This asserted `heyreach.activate` was in
        # neither SUPPORTED nor CONDITIONAL. The operator granted it, scoped
        # BY NAME to one campaign, so absence would now pin the opposite of
        # the truth. The property is unchanged - the stop exists and starting
        # a campaign that HOLDS PEOPLE is not a thing this build can do at
        # large - and it moves from the tuple to the condition: enabled,
        # conditional, and refusing every id but the named one.
        self.assertIn("heyreach.activate", providerwrites.SUPPORTED)
        self.assertIn("heyreach.activate", providerwrites.CONDITIONAL)
        self.assertTrue(providerwrites.require_conditional_permission(
            "heyreach.activate",
            providerwrites._AUTHORIZED_LINKEDIN_CANARY, None))
        # 604869 and 605487 are DEAD ENDS rather than merely un-granted -
        # one holds a contact `collision.account_policy` holds, the other a
        # contact gate 4 refused - so they are asserted refused, not dropped.
        for other in ("599020", "604869", "605487", "", None):
            with self.subTest(campaign=other):
                with self.assertRaises(providerwrites.WriteRefused):
                    providerwrites.require_conditional_permission(
                        "heyreach.activate", other, None)
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
        # RE-POINTED 2026-09-16 with the grant above: membership is not the
        # permission for LINKEDIN_ACTIVATE either, and the condition is.
        self.assertTrue(pw.is_conditional(pw.LINKEDIN_ACTIVATE))


    def test_the_write_layer_is_still_sealed(self):
        """DELIBERATELY STILL AN EXACT-TUPLE COMPARISON, and that is the seal
        this test carries: enabling a route is an act rather than a drift.

        RE-POINTED 2026-09-16. Six verbs joined on written operator
        authorization - see `OPERATOR-AUTHORIZATION-2026-09-16.md`. The
        expected value is updated by hand and the check is NOT loosened into a
        subset: its entire worth is that an addition has to be made here, by
        somebody who read why each of these is here.
        """
        from src import providerwrites as pw
        self.assertEqual(
            providerwrites.SUPPORTED,
            (pw.LINKEDIN_PAUSE, pw.EMAIL_PAUSE, pw.EMAIL_STOP_LEAD,
             # Added 2026-09-23 by operator decision, not prospect-facing:
             # it can only reduce what somebody receives. The email->LinkedIn
             # half of the cross-channel stop could not run while it was
             # sealed, which is what enrolling 33 LinkedIn seats depends on.
             pw.LINKEDIN_STOP_LEAD,
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
             # way to a stageable campaign.
             pw.LINKEDIN_START_EMPTY_FOR_STAGING,
             # Added 2026-09-16. NOT prospect-facing: a list attached to no
             # campaign reaches nobody, and the condition reads the list FROM
             # THE PROVIDER at the moment of the write to prove it is unbound.
             pw.LINKEDIN_ADD_LEAD_TO_LIST,
             # Added 2026-09-16, SCOPED TO ONE CAMPAIGN. Attaching a sender is
             # what makes sending possible at all, and activation is what
             # makes it happen, so both carry the same condition and both
             # refuse every canonical row but the one the grant names.
             pw.EMAIL_ASSIGN_SENDER,
             pw.EMAIL_ACTIVATE,
             # Added 2026-09-16. NOT prospect-facing: the provider creates in
             # DRAFT and a DRAFT sends nothing. Conditional on the LIST that
             # will be bound at creation - ours, unbound, holding only
             # approved leads, all read live.
             pw.LINKEDIN_CREATE_CAMPAIGN,
             # Added 2026-09-16, SCOPED TO ONE CAMPAIGN. PROSPECT-FACING -
             # this is the verb that starts a LinkedIn campaign. Membership
             # of this tuple alone would be a licence over all 83 campaigns
             # in the account, 12 of them the client's own and IN_PROGRESS,
             # so the permission is the condition and it is asserted above.
             pw.LINKEDIN_ACTIVATE,
             # Added 2026-09-16. NOT prospect-facing and NOT conditional: it
             # makes an EMPTY list bound to no campaign, so there is no
             # destination to read and a condition checking nothing would
             # read as a gate. What bounds it is downstream - the verb that
             # puts a lead in a list and the verb that binds one to a
             # campaign are both conditional.
             pw.LINKEDIN_CREATE_LIST))
        # `heyreach.pause` left this list on 2026-09-12: a live pause of
        # campaign 594061 returned 200 and read back PAUSED, so it is
        # live-validated and declared. It was never a campaign-BUILDING verb
        # anyway - it is the stop. Every builder below is still sealed.
        # `heyreach.set_sequence` left this list on 2026-09-14 for the same
        # kind of reason as the pause: its own stated condition was met, and
        # it is not prospect-facing - a sequence written onto a campaign
        # holding nobody reaches nobody.
        # `heyreach.create_campaign`, `heyreach.create_list` and
        # `heyreach.activate` left it on 2026-09-16 by written operator
        # authorization. The first two build and reach nobody; the third
        # reaches everybody in the campaign it names, which is why it is the
        # one that carries a condition naming ONE campaign - asserted above.
        # NOBODY GRANTED THE TWO BELOW, and they are what keeps this a list
        # rather than a formality: a seat this build can attach and a cap it
        # can raise are how a validated campaign quietly becomes a bigger one.
        for operation in ("heyreach.assign_sender", "heyreach.set_limits"):
            with self.subTest(operation=operation):
                self.assertFalse(providerwrites.is_supported(operation))
        # The three that were granted are asserted POSITIVELY rather than
        # removed, because "it is no longer on a list" says nothing about what
        # it may do. Each build verb reaches nobody, and the one that reaches
        # somebody is scoped by name.
        for operation in ("heyreach.create_campaign", "heyreach.create_list"):
            with self.subTest(operation=operation):
                _channel, facing, _why = providerwrites.OPERATIONS[operation]
                self.assertFalse(
                    facing, "a build verb that reaches a person is not a "
                            "build verb")
                self.assertTrue(providerwrites.is_supported(operation))
        self.assertTrue(providerwrites.is_supported("heyreach.activate"))
        self.assertTrue(providerwrites.is_conditional("heyreach.activate"))

    def test_the_verbs_that_reach_a_person_are_sealed_but_one(self):
        """RE-POINTED 2026-09-16. NOT ONE OF THE FOUR IS UNCONDITIONAL.

        NARROWED at TASK-137 to "three of the four are still sealed
        outright", which held until an operator granted both ACTIVATE verbs
        on 2026-09-16, each SCOPED BY NAME to a single campaign. The seal on
        two of the four is therefore gone as a tuple fact.

        The property was never the count and it is unchanged: NO verb that
        reaches a person is enabled on tuple membership alone. `add_lead`
        is scoped by the destination's STATE - it may run only against a
        campaign the provider says, at the moment of the write, cannot send.
        The two ACTIVATE verbs are scoped by NAME, because no campaign state
        makes an activation reach nobody. `bison.add_lead` is the one still
        sealed outright, and it is what keeps this a real distinction.
        """
        # Still sealed outright, and still carrying no condition that could
        # admit it. Nobody granted this one.
        _channel, facing, _why = providerwrites.OPERATIONS["bison.add_lead"]
        self.assertTrue(facing, "this test is about prospect-facing verbs")
        self.assertFalse(providerwrites.is_supported("bison.add_lead"))
        self.assertFalse(providerwrites.is_conditional("bison.add_lead"))

        # Granted, and every one of them scoped. An entry that is supported
        # and unconditional here is a channel-wide licence to reach people.
        for operation in ("heyreach.add_lead", "heyreach.activate",
                          "bison.activate"):
            with self.subTest(operation=operation):
                _channel, facing, _why = providerwrites.OPERATIONS[operation]
                self.assertTrue(facing,
                                "this test is about prospect-facing verbs")
                self.assertTrue(providerwrites.is_supported(operation))
                self.assertTrue(
                    providerwrites.is_conditional(operation),
                    f"{operation} reaches a person and is enabled with no "
                    f"condition deciding, per write, who it reaches")

        # And the scope on the LinkedIn activation is ONE campaign: the
        # named canary, with 604869 and 605487 refused as the dead ends they
        # are rather than dropped for being un-granted.
        require = providerwrites.require_conditional_permission
        self.assertTrue(require("heyreach.activate",
                                providerwrites._AUTHORIZED_LINKEDIN_CANARY,
                                None))
        for other in ("599020", "604869", "605487", "", None):
            with self.subTest(campaign=other):
                with self.assertRaises(providerwrites.WriteRefused):
                    require("heyreach.activate", other, None)

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
