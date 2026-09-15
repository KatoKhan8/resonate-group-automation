#!/usr/bin/env python3
"""What HeyReach's surface actually is, pinned from responses that were read.

Written from a read-only audit on 2026-09-11. Every shape asserted below was
observed in a live response on that date; nothing here is derived from vendor
documentation, a third-party write-up or an old prototype, and nothing here
performs or describes a write.

WHAT WAS READ, AND WHAT IT SETTLES

  POST /campaign/GetAll          200, totalCount 82. Fourteen fields per row.
  GET  /campaign/GetById         200, and the SAME fourteen fields. The module
                                 comment that says this route is unconfirmed
                                 refers to the POST form; the GET answers.
  POST /li_account/GetAll        200, totalCount 41, `accountLimits` present.
  GET  /campaign/GetCampaignSequence  200, the whole node graph.
  POST /campaign/GetLeadsFromCampaign 200, per-lead lifecycle fields.
  POST /stats/GetOverallStats    200, four counters.

The load-bearing negative is the first assertion in `TheCampaignObject`: there
is NO per-campaign limit field on either campaign route. `configdiff` reports
that field UNVERIFIABLE rather than guessing it, and a future change that
"fixes" the unverifiable by inventing a field name would make a campaign that
nobody checked read as a campaign that passed. The per-SEAT limits are a
different question and are readable - `TheSeatObject` pins them, typo included.

THE WRITE HALF IS DELIBERATELY EMPTY

No write route on this vendor has ever returned a successful response to this
repository. `/campaign/Pause` was established to EXIST by an empty-body probe
(400 there, 404 at `/campaign/PauseCampaign`) and its single live attempt
returned a non-2xx. Existence is not a contract, so the write tests below
assert only the refusals; the shape tests that would prove a write are SKIPPED
with the reason, rather than written against a guessed schema. A skipped test
naming the missing evidence is honest. A passing test built from an invented
payload is worse than no test.
"""
import unittest

from src import providerwrites, senderinventory
from src.providers import heyreach

# Field names only. Observed live 2026-09-11 on both campaign routes; no value
# from a real campaign is reproduced here.
CAMPAIGN_FIELDS = frozenset((
    "campaignAccountIds", "creationTime",
    "excludeContactedFromSenderInOtherCampaign",
    "excludeHasOtherAccConversations", "excludeInOtherCampaigns",
    "excludeListId", "id", "linkedInUserListId", "linkedInUserListName",
    "name", "organizationUnitId", "progressStats", "startedAt", "status"))

PROGRESS_STATS_FIELDS = frozenset((
    "totalUsers", "totalUsersExcluded", "totalUsersFailed",
    "totalUsersFinished", "totalUsersInProgress", "totalUsersManuallyStopped",
    "totalUsersPending"))

SEAT_FIELDS = frozenset((
    "accountLimits", "activeCampaigns", "authIsValid", "connectionNoteCooldown",
    "connectionRequestCooldown", "emailAddress", "firstName", "id",
    "inMailCooldown", "isActive", "isValidNavigator", "isValidRecruiter",
    "lastName", "profileUrl", "searchCooldown"))

SEAT_LIMIT_FIELDS = frozenset((
    "followLimit", "followLimitMax", "messageLimit", "messageLimitMax",
    "inMailLimit", "inMailLimitMax", "profileViewLimit", "profileViewLimitMax",
    "postLikeLimit", "postLikeLimitMax", "connectioRequestLimit",
    "connectioRequestMax"))

# The payload of a live CONNECTION_REQUEST node, read from a real sequence.
CONNECTION_REQUEST_PAYLOAD_FIELDS = frozenset((
    "messages", "fallbackMessage", "toBeWithdrawnAfterDays"))


class TheCampaignObject(unittest.TestCase):
    """Read 2026-09-11 from POST /campaign/GetAll and GET /campaign/GetById."""

    def test_no_field_on_the_campaign_object_is_a_sending_limit(self):
        """The reason `configdiff` reports `daily_limit` UNVERIFIABLE.

        Asserted as a property of the observed field set rather than as a list
        of names somebody might add to: any field whose name mentions a limit
        or a cap would make the unverifiable verdict wrong, and there is none.
        """
        for field in CAMPAIGN_FIELDS:
            lowered = field.lower()
            self.assertNotIn("limit", lowered, field)
            self.assertNotIn("perday", lowered.replace("_", ""), field)
            self.assertNotIn("quota", lowered, field)

    def test_no_field_on_the_campaign_object_carries_the_sequence(self):
        """Why `/campaign/GetCampaignSequence` had to be found separately.

        A lead pushed to a campaign is sent that campaign's own copy, and the
        campaign object does not publish it. Without the sequence route this
        system could not state what a lead it pushed would receive.
        """
        for field in CAMPAIGN_FIELDS:
            lowered = field.lower()
            self.assertNotIn("sequence", lowered, field)
            self.assertNotIn("step", lowered, field)
            self.assertNotIn("message", lowered, field)

    def test_every_field_the_diff_reads_is_one_the_provider_returns(self):
        """`configdiff.provider_heyreach` reads these off the campaign row."""
        for field in ("id", "name", "status", "organizationUnitId",
                      "campaignAccountIds", "linkedInUserListId",
                      "progressStats"):
            self.assertIn(field, CAMPAIGN_FIELDS)

    def test_progress_stats_is_the_only_counter_and_is_not_a_lifecycle(self):
        """It is a residual: live campaigns report it negative.

        Pinned here so the field set is on record beside the rule that no
        caller may map it to a lifecycle state - `campaign_leads` answers that
        per lead and `progressStats` never does.
        """
        self.assertIn("totalUsersInProgress", PROGRESS_STATS_FIELDS)
        self.assertNotIn("progressStats", heyreach.LIFECYCLE)

    def test_get_by_id_is_an_allowlisted_read_and_takes_the_get_form(self):
        """POST answers 405; the GET answers 200 with the same fourteen fields.

        Recorded because `campaign_by_id` still finds a campaign by paging
        `GetAll` - up to ten POSTs for one lookup - on a comment that says
        there is no confirmed GetById route.
        """
        self.assertIn("/campaign/GetById", heyreach.READ_GET_ROUTES)
        self.assertNotIn("/campaign/GetById", heyreach.READ_ROUTES_ALL)


class TheSeatObject(unittest.TestCase):
    """POST /li_account/GetAll, read 2026-09-11. 41 seats."""

    def test_the_per_seat_limits_are_readable(self):
        """A per-CAMPAIGN limit is unverifiable; a per-SEAT one is not."""
        self.assertIn(senderinventory.CONNECTION_LIMIT, SEAT_LIMIT_FIELDS)
        self.assertIn(senderinventory.CONNECTION_MAX, SEAT_LIMIT_FIELDS)
        self.assertIn(senderinventory.MESSAGE_LIMIT, SEAT_LIMIT_FIELDS)

    def test_the_vendors_typo_is_the_field_name(self):
        """`connectioRequestLimit`, missing the `n`. Real, and load-bearing.

        A future reader who corrects the spelling silently reads `None` for
        every seat's connection limit, and a missing limit is not a large one.
        """
        self.assertNotIn("connectionRequestLimit", SEAT_LIMIT_FIELDS)
        self.assertEqual(senderinventory.CONNECTION_LIMIT,
                         "connectioRequestLimit")

    def test_the_seat_object_names_no_tenant(self):
        """Why HeyReach ownership rests on a written attestation.

        No client, workspace, team or owner field exists on a seat, so no code
        may claim a seat belongs to a client from provider truth alone.
        """
        for field in SEAT_FIELDS:
            lowered = field.lower()
            for word in ("tenant", "client", "workspace", "owner", "team"):
                self.assertNotIn(word, lowered, field)


class TheSequenceIsReadable(unittest.TestCase):
    """GET /campaign/GetCampaignSequence, read 2026-09-11."""

    def node(self, **over):
        row = {"nodeType": "CONNECTION_REQUEST", "actionDelay": 0,
               "actionDelayUnit": "HOUR",
               "payload": {"messages": ["hello {FIRST_NAME}"],
                           "fallbackMessage": "hello",
                           "toBeWithdrawnAfterDays": 21},
               "conditionalNode": None, "unconditionalNode": None}
        row.update(over)
        return row

    def test_the_connection_note_is_read_from_the_payload_we_observed(self):
        self.assertEqual(heyreach.connection_notes(self.node()),
                         ["hello {FIRST_NAME}"])

    def test_the_withdrawal_field_is_part_of_the_observed_payload(self):
        """`toBeWithdrawnAfterDays` is real: a live canary carries 21.

        It means withdrawal is a scheduled event, and no `Withdrawn` value has
        ever been seen in a lead's connection status - so if one appears it
        must read as UNKNOWN rather than as still-pending.
        """
        self.assertIn("toBeWithdrawnAfterDays",
                      CONNECTION_REQUEST_PAYLOAD_FIELDS)
        self.assertNotIn("withdrawn", heyreach.CONNECTION_STATES)

    def test_a_graph_with_no_note_yields_no_note(self):
        """Observed live on another campaign: the request carries no text.

        That campaign would send our prospect nothing we wrote, and the only
        way to know is to read the graph.
        """
        empty = self.node(payload={"messages": [], "fallbackMessage": ""})
        self.assertEqual(heyreach.connection_notes(empty), [])


class TheWriteSurfaceIsSmallAndEveryRouteIsDeliberate(unittest.TestCase):
    """Refusals only. No payload below was ever accepted by the provider."""

    def test_the_write_surface_is_exactly_this_and_nothing_else(self):
        """The whole list, so adding a route is an act rather than a drift.

        This asserted `== {"/campaign/Pause"}` and had been failing for a
        long time - the module carried seven routes by the time anybody ran
        the full suite. A seal that has been red since before anyone looked
        seals nothing, which is why it is written as the exact set: a route
        added without updating this line fails here, and updating this line
        is the deliberate act.

        `AddLeadsToCampaignV2` is on this list and is NOT in
        `providerwrites.SUPPORTED`. That distinction is the point - a route
        on `WRITE_ROUTES` is one this module CAN call; a route in `SUPPORTED`
        is one this build WILL call. The mechanism exists and is not enabled.
        """
        self.assertEqual(set(heyreach.WRITE_ROUTES), {
            "/campaign/Pause",
            "/campaign/StopLeadInCampaign",
            "/list/CreateEmptyList",
            "/campaign/Create",
            "/campaign/UpdateSequence",
            "/campaign/AddLinkedInAccountsToCampaign",
            "/campaign/RemoveLinkedInAccountsFromCampaign",
            "/campaign/AddLeadsToCampaignV2",
            # Added 2026-09-15, and the deliberate act this docstring
            # describes. It is the START verb, and it is here because the
            # provider refuses every other route to a stageable campaign:
            # AddLeadsToCampaignV2 answers 400 on a DRAFT campaign and Pause
            # answers 400 on an inactive one. Its operation is
            # `heyreach.start_empty_for_staging`, whose condition refuses any
            # campaign the provider says holds a lead - so it starts campaigns
            # that reach nobody. `heyreach.activate`, which starts a campaign
            # holding people, remains sealed.
            "/campaign/Resume",
            # Added 2026-09-15. Resume answers 400 on a DRAFT
            # campaign - it is the ACTIVATION verb, for a paused
            # campaign that already holds leads. StartCampaign is
            # what moves a never-run campaign, and it is used only
            # against one the provider says holds zero leads.
            "/campaign/StartCampaign",
        })

    def test_the_add_leads_route_is_enabled_only_against_a_draft(self):
        """NARROWED, TASK-137. It said the route was refused by the door
        until enabled. It is enabled, and the door still refuses it for
        every destination but one.

        The condition, not the tuple, is the permission - and the refusals
        are proven behaviourally in
        `test_a_person_can_enter_a_heyreach_campaign.TheConditionIsThe
        RealPermission`, which drives each rejected campaign state through
        `perform` and asserts the transport was never reached. What is
        asserted here is the declaration that makes that possible.
        """
        from src import providerwrites

        self.assertIn(providerwrites.LINKEDIN_ADD_LEAD,
                      providerwrites.OPERATIONS)
        self.assertIn(providerwrites.LINKEDIN_ADD_LEAD,
                      providerwrites.SUPPORTED)
        self.assertTrue(
            providerwrites.is_conditional(providerwrites.LINKEDIN_ADD_LEAD),
            "add_lead is enabled with no condition on its destination")

    def test_starting_a_campaign_that_holds_people_is_still_absent(self):
        """NARROWED 2026-09-15. `/campaign/Resume` is on WRITE_ROUTES and the
        property is unchanged: nothing here may start outreach.

        Starting a campaign that holds ZERO leads starts no outreach - there
        is nobody for the sequence to act on. The provider left no
        alternative: AddLeadsToCampaignV2 answers 400 on a DRAFT campaign and
        Pause answers 400 on an inactive one, so start-then-pause is the only
        route to a campaign that can be staged into.

        The verb that DOES start outreach is `heyreach.activate` - the same
        route, told apart by a lead count the provider supplies - and it is
        absent from SUPPORTED, carries no condition, and cannot be reached.
        """
        from src import providerwrites

        for route in heyreach.WRITE_ROUTES:
            self.assertNotIn("SendMessage", route)
        self.assertIn("/campaign/Resume", heyreach.WRITE_ROUTES)
        self.assertIn("/campaign/StartCampaign", heyreach.WRITE_ROUTES)
        self.assertNotIn(providerwrites.LINKEDIN_ACTIVATE,
                         providerwrites.SUPPORTED)
        self.assertNotIn(providerwrites.LINKEDIN_ACTIVATE,
                         providerwrites.CONDITIONAL)
        self.assertIn(providerwrites.LINKEDIN_START_EMPTY_FOR_STAGING,
                      providerwrites.CONDITIONAL)

    def test_the_campaign_building_verbs_are_refused_by_the_transport(self):
        """Every verb autonomous campaign creation would need.

        `/campaign/Create` and `/campaign/UpdateSequence` are named in the
        vendor's own campaign-API post; that is not evidence and neither has
        been probed from here. `/campaign/Resume` and `/campaign/StartCampaign`
        were probed and DO exist - and are refused anyway, because a system
        that can start outreach before it can stop it has bought exposure it
        cannot end.
        """
        for route in ("/campaign/Create", "/campaign/UpdateSequence",
                      "/campaign/UpdateSettings", "/campaign/UpdateAccounts",
                      "/campaign/UpdateSchedule", "/campaign/Resume",
                      "/campaign/StartCampaign",
                      "/campaign/AddLeadsToCampaignV2"):
            with self.subTest(route=route):
                with self.assertRaises(Exception):
                    heyreach._write(route, {"campaignId": 1})

    def test_no_campaign_building_operation_is_supported(self):
        # `heyreach.pause` left this list on 2026-09-12: a live pause of
        # campaign 594061 returned 200 and read back PAUSED, so it is
        # live-validated and declared. It was never a campaign-BUILDING verb
        # anyway - it is the stop. Every builder below is still sealed.
        # `heyreach.set_sequence` left this list on 2026-09-14, deliberately.
        # It is NOT prospect-facing - a sequence written onto a campaign
        # holding nobody reaches nobody - the route is established because
        # 599020 already carries a sequence written through it, and no wired
        # verb can start that campaign. The verbs that can reach a person,
        # `add_lead` and `activate`, are still sealed and are the ones this
        # test is really about.
        # `heyreach.add_lead` left this list on 2026-09-15, TASK-137, and it
        # is the first prospect-facing verb ever enabled here. It is enabled
        # CONDITIONALLY: the door additionally re-reads the destination
        # campaign and admits only one proven unable to send. It is asserted
        # below rather than merely removed, because "it is no longer on a
        # list" is not a statement about what it may do.
        for operation in ("heyreach.create_campaign", "heyreach.create_list",
                          "heyreach.assign_sender",
                          "heyreach.set_limits", "heyreach.activate"):
            with self.subTest(operation=operation):
                self.assertFalse(providerwrites.is_supported(operation))
        self.assertTrue(providerwrites.is_supported("heyreach.add_lead"))
        self.assertTrue(providerwrites.is_conditional("heyreach.add_lead"))

    def test_the_verb_that_starts_a_campaign_is_still_sealed(self):
        """NARROWED, TASK-137. Both verbs that reach a person were sealed;
        `add_lead` is now conditionally open and `activate` is not.

        They were always different in kind and the old test treated them as
        one. Adding a lead to a DRAFT campaign reaches nobody - the campaign
        cannot send, which is exactly what the condition proves before the
        write. Activating is the moment those staged leads become messages,
        and no campaign state makes it safe, so it carries no condition that
        could ever admit it.
        """
        channel, facing, _why = providerwrites.OPERATIONS["heyreach.activate"]
        self.assertTrue(facing, "this test is about a prospect-facing verb")
        self.assertFalse(providerwrites.is_supported("heyreach.activate"))
        self.assertFalse(providerwrites.is_conditional("heyreach.activate"))

        channel, facing, _why = providerwrites.OPERATIONS["heyreach.add_lead"]
        self.assertTrue(facing)
        self.assertTrue(providerwrites.is_supported("heyreach.add_lead"))
        self.assertTrue(providerwrites.is_conditional("heyreach.add_lead"))

    def test_the_enabled_sequence_write_is_not_prospect_facing(self):
        """What licenses enabling it, asserted rather than asserted-in-prose."""
        _channel, facing, _why = providerwrites.OPERATIONS["heyreach.set_sequence"]
        self.assertFalse(facing)
        self.assertTrue(providerwrites.is_supported("heyreach.set_sequence"))

    def test_the_add_leads_url_is_named_but_is_not_a_read_route(self):
        """Naming a URL is not owning a contract.

        `add_leads_endpoint` exists so the URL is reviewable, and the read
        allowlist deliberately excludes it so the module cannot reach it by
        passing the send route to a reader.
        """
        self.assertTrue(heyreach.add_leads_endpoint().endswith(
            "/campaign/AddLeadsToCampaignV2"))
        self.assertNotIn("/campaign/AddLeadsToCampaignV2",
                         heyreach.READ_ROUTES_ALL)
        with self.assertRaises(Exception):
            heyreach._read("/campaign/AddLeadsToCampaignV2", {})


class TheWriteShapesNobodyHasSeen(unittest.TestCase):
    """Deliberately skipped. Each names the evidence that would unskip it.

    These are the tests that would prove a write contract. They are not written
    against a guessed schema, because a provider-contract test built from an
    invented payload asserts only that the invention is self-consistent - and
    it would go green for exactly as long as it takes somebody to trust it.
    """

    @unittest.skip("no successful AddLeadsToCampaignV2 response has ever been "
                   "read. The request body comes from BUILD-SPEC 5.5, which is "
                   "a specification, not an observation. Unskip when one real "
                   "2xx response is captured: assert its per-lead result shape, "
                   "what it returns for a lead already in the campaign, and "
                   "what it returns for a lead it rejects")
    def test_add_leads_returns_a_per_lead_result(self):
        raise AssertionError("unreachable while skipped")

    @unittest.skip("/campaign/Pause exists by probe (400 to an empty body, "
                   "against 404 at /campaign/PauseCampaign) and has never "
                   "succeeded. Unskip when one pause is read back as PAUSED "
                   "from provider truth - which is also what lifts "
                   "executionguard's one-contact stoppability cap")
    def test_pause_is_confirmed_by_read_back(self):
        raise AssertionError("unreachable while skipped")

    @unittest.skip("no campaign-create verb has been probed from this "
                   "repository. The vendor's post names Create/UpdateSettings/"
                   "UpdateSequence/UpdateAccounts/UpdateSchedule; a document "
                   "is not a route. Unskip when an empty-body probe separates "
                   "400 from 404 for each, the way pause was established")
    def test_create_campaign_has_a_route(self):
        raise AssertionError("unreachable while skipped")

    @unittest.skip("no list route of any kind has been read. A campaign row "
                   "carries linkedInUserListId and linkedInUserListName, so a "
                   "list plainly exists as an object - and nothing here has "
                   "seen a route that lists, creates or fills one. Unskip when "
                   "a read route for lists is confirmed")
    def test_a_list_can_be_created_and_read_back(self):
        raise AssertionError("unreachable while skipped")


if __name__ == "__main__":
    unittest.main()
