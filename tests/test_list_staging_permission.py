"""Permission tests for LINKEDIN_ADD_LEAD_TO_LIST. TASK-172.

The verb is DEFINED but NOT ENABLED. These tests prove:

  1. The constant exists and is declared in OPERATIONS.
  2. It is NOT in SUPPORTED, so `perform` refuses it with WriteUnsupported.
  3. The predicate (`assert_list_safe`) refuses every unsafe condition.
  4. The validation (`validate_lead_row`) refuses bad data before the
     predicate runs.
  5. The full path (`stage_lead`) treats the silent-drop response as failure.
  6. The gates run in the correct order: validation, then safety, then
     transport.

Every test uses a fake transport and fake provider reads. No test reaches a
real API, spends credits, or touches a production path.
"""
import os
import tempfile
import unittest

from src import providerwrites
from src.liststaging import (
    LINKEDIN_ADD_LEAD_TO_LIST,
    ListStagingRefused,
    ListStagingUnverified,
    assert_list_safe,
    stage_lead,
    validate_lead_row,
)


# --------------------------------------------------------------- fixtures

LIST_UNBOUND = {
    "id": 940797,
    "name": "staging-list",
    "listType": "USER_LIST",
    "totalItemsCount": 0,
    "campaignIds": [],
    "creationTime": "2026-09-15T00:00:00Z",
}

LIST_BOUND = {
    "id": 933603,
    "name": "campaign-list",
    "listType": "USER_LIST",
    "totalItemsCount": 50,
    "campaignIds": [599020],
    "creationTime": "2026-09-10T00:00:00Z",
}

LIST_OTHER_TENANT = {
    "id": 888001,
    "name": "other-tenant-list",
    "listType": "USER_LIST",
    "totalItemsCount": 10,
    "campaignIds": [777777],
    "creationTime": "2026-09-14T00:00:00Z",
}

LIST_NOT_OURS = {
    "id": 555001,
    "name": "client-made-list",
    "listType": "USER_LIST",
    "totalItemsCount": 25,
    "campaignIds": [599020],
    "creationTime": "2026-09-01T00:00:00Z",
}

LEAD_OK = {
    "linkedin_url": "https://linkedin.com/in/test-profile",
    "first_name": "Test",
    "last_name": "Person",
    "company": "TestCo",
    "title": "Engineer",
}


def fake_transport(response=None):
    calls = []
    def _transport(payload):
        calls.append(payload)
        return response or {"addedLeadsCount": 1, "totalLeads": 1,
                            "duplicateLeads": 0}
    _transport.calls = calls
    return _transport


def fake_list_reader(row):
    def _read(list_id):
        return dict(row)
    return _read


def fake_members_reader(members, total=None):
    def _read(list_id, offset=0, limit=100):
        return list(members), total if total is not None else len(members)
    return _read


# ----------------------------------- 1. the constant exists and is declared


class _IsolatedStore(unittest.TestCase):
    """Isolate the store for every test in this module.

    `stage_lead` now routes its write through `providerwrites.perform`, which
    reads and writes campaign state for the action ledger and the
    staged-already check. Before that change these tests never touched the
    store, so they never needed isolation; afterwards they tripped the guard
    that refuses a test writing real client state. tests/base.py makes the
    same point: isolation a subclass has to remember is isolation a subclass
    can forget.
    """

    def setUp(self):
        super().setUp()
        from src import store
        self._store_tmp = tempfile.mkdtemp(prefix="rga-liststaging-")
        self._store_prev = getattr(store, "DIRECTORY", None)
        store.use_directory(os.path.join(self._store_tmp, "work"))

    def tearDown(self):
        from src import store
        if self._store_prev is not None:
            store.use_directory(self._store_prev)
        super().tearDown()


class TestVerbIsDeclared(_IsolatedStore):
    """The verb has a constant name, a string, and an OPERATIONS entry."""

    def test_the_constant_has_the_right_string(self):
        self.assertEqual(LINKEDIN_ADD_LEAD_TO_LIST, "heyreach.add_lead_to_list")

    def test_the_constant_is_in_providerwrites(self):
        self.assertEqual(providerwrites.LINKEDIN_ADD_LEAD_TO_LIST,
                         LINKEDIN_ADD_LEAD_TO_LIST)

    def test_the_verb_is_in_operations(self):
        self.assertIn(LINKEDIN_ADD_LEAD_TO_LIST, providerwrites.OPERATIONS)

    def test_the_verb_is_in_supported(self):
        """ENABLED 2026-09-16 by written operator authorization.

        TASK-172's trap was that defining the verb must not enable it, and
        this test asserted the absence for exactly that reason. The operator
        then took the decision in writing - see
        OPERATOR-AUTHORIZATION-2026-09-16.md - so asserting absence now would
        pin the opposite of the truth. The trap it guarded has moved to
        TestTheCampaignRouteIsStillSealed: enabling the LIST verb must not
        unseal the CAMPAIGN verb."""
        self.assertIn(LINKEDIN_ADD_LEAD_TO_LIST, providerwrites.SUPPORTED)

    def test_the_verb_is_in_conditional(self):
        """Enabled 2026-09-16 under written operator authorization, and
        CONDITIONALLY - see OPERATOR-AUTHORIZATION-2026-09-16.md.

        Membership of SUPPORTED alone would be a licence to add a lead to ANY
        list, including one attached to a campaign, which is the
        prospect-facing write this permission was carefully not asking for.
        So the two must move together, and this asserts both."""
        self.assertIn(LINKEDIN_ADD_LEAD_TO_LIST, providerwrites.SUPPORTED)
        self.assertIn(LINKEDIN_ADD_LEAD_TO_LIST,
                      providerwrites.CONDITIONAL)

    def test_the_verb_is_not_prospect_facing(self):
        _channel, facing, _why = providerwrites.OPERATIONS[
            LINKEDIN_ADD_LEAD_TO_LIST]
        self.assertFalse(facing)

    def test_describe_does_not_raise(self):
        """The verb is declared, so `describe` returns its tuple."""
        channel, facing, why = providerwrites.describe(
            LINKEDIN_ADD_LEAD_TO_LIST)
        self.assertEqual(channel, "linkedin")
        self.assertFalse(facing)
        self.assertIn("TASK-172", why)


# ----------------------------------- 2. perform refuses with WriteUnsupported

class TestPerformRefusesABoundList(_IsolatedStore):
    """The verb is enabled now, so the interesting refusal moved.

    These tests asserted WriteUnsupported while the verb was off. The operator
    enabled it on 2026-09-16, so asserting it is unsupported would now pin the
    opposite of the truth. What must still hold - and what actually protects
    anybody - is that the CONDITION refuses a list attached to a campaign, and
    refuses before the transport is touched.
    """

    def _perform_against(self, list_row):
        calls = []

        def reader(list_id):
            return list_row

        import src.liststaging as liststaging
        real = liststaging.assert_list_safe

        def patched(list_id, list_reader=None):
            return real(list_id, list_reader=reader)

        liststaging.assert_list_safe = patched
        try:
            providerwrites.perform(
                LINKEDIN_ADD_LEAD_TO_LIST,
                provider_campaign_id=940797,
                campaign=None,
                payload={"listId": 940797, "leads": []},
                transport=lambda p: calls.append(p),
                readback=lambda: {"totalCount": 0})
        finally:
            liststaging.assert_list_safe = real
        return calls

    def test_a_bound_list_is_refused(self):
        """campaignIds non-empty means adding to it adds to a campaign."""
        with self.assertRaises(providerwrites.WriteRefused):
            self._perform_against({"id": 940797, "campaignIds": [599020]})

    def test_the_transport_is_never_reached_for_a_bound_list(self):
        calls = []
        try:
            calls = self._perform_against(
                {"id": 940797, "campaignIds": [599020]})
        except providerwrites.WriteRefused:
            pass
        self.assertEqual(calls, [],
                         "a refused write must not touch the transport")


class TestTheCampaignRouteIsStillSealed(_IsolatedStore):
    """Enabling the LIST verb must not unseal the CAMPAIGN verb.

    This is the test that matters most about the 2026-09-16 authorization. The
    operator's grant was explicit: "Do NOT interpret this as permission to
    bypass gates or activate arbitrary campaigns." Adding a lead to a HeyReach
    campaign activates it, in PAUSED and FINISHED both, and that remains the
    prospect-facing moment.
    """

    def test_campaign_level_staging_is_still_not_proven(self):
        self.assertFalse(providerwrites.CAMPAIGN_LEVEL_STAGING_IS_PROVEN)

    def test_add_lead_to_a_campaign_is_still_refused(self):
        """Refused on the first line of its own condition, whatever is
        passed to it."""
        with self.assertRaises(providerwrites.WriteRefused) as ctx:
            providerwrites.require_conditional_permission(
                providerwrites.LINKEDIN_ADD_LEAD, 599020, "some-campaign")
        self.assertIn("RESEALED", str(ctx.exception))


class TestRefusalListAttachedToCampaign(_IsolatedStore):
    """A list attached to a campaign is refused. Adding to it is adding to
    the campaign, which is the prospect-facing path."""

    def test_assert_list_safe_refuses_a_bound_list(self):
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(933603, list_reader=fake_list_reader(LIST_BOUND))
        self.assertIn("attached to campaign", str(ctx.exception))
        self.assertIn("599020", str(ctx.exception))

    def test_stage_lead_refuses_a_bound_list_before_transport(self):
        transport = fake_transport()
        with self.assertRaises(ListStagingRefused):
            stage_lead(933603, LEAD_OK, transport,
                       list_reader=fake_list_reader(LIST_BOUND))
        self.assertEqual(transport.calls, [],
                         "the transport was called for a bound list")


# ----------------------------------- 4. refusal: list in another tenant

class TestRefusalListInAnotherTenant(_IsolatedStore):
    """A list whose campaignIds name campaigns in another tenant is refused.
    The predicate refuses any list with non-empty campaignIds, whatever
    tenant owns those campaigns. The HeyReach API scopes list reads to the
    tenant of the API key, so a list in another tenant is one whose
    campaignIds name campaigns we do not recognise."""

    def test_a_list_bound_to_another_tenants_campaigns_is_refused(self):
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(888001,
                             list_reader=fake_list_reader(LIST_OTHER_TENANT))
        self.assertIn("attached to campaign", str(ctx.exception))
        self.assertIn("777777", str(ctx.exception))

    def test_the_transport_is_not_reached(self):
        transport = fake_transport()
        with self.assertRaises(ListStagingRefused):
            stage_lead(888001, LEAD_OK, transport,
                       list_reader=fake_list_reader(LIST_OTHER_TENANT))
        self.assertEqual(transport.calls, [])


# ----------------------------------- 5. refusal: list not ours

class TestRefusalListNotOurs(_IsolatedStore):
    """A list the client made themselves and attached to their own campaign
    is refused. The predicate checks campaignIds, not creator: a list we
    did not create but that IS unbound would pass the predicate - and that
    is documented as a limitation in the OPERATIONS entry. A list that IS
    bound, whether we created it or not, is refused."""

    def test_a_bound_list_we_did_not_create_is_refused(self):
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(555001,
                             list_reader=fake_list_reader(LIST_NOT_OURS))
        self.assertIn("attached to campaign", str(ctx.exception))

    def test_the_transport_is_not_reached(self):
        transport = fake_transport()
        with self.assertRaises(ListStagingRefused):
            stage_lead(555001, LEAD_OK, transport,
                       list_reader=fake_list_reader(LIST_NOT_OURS))
        self.assertEqual(transport.calls, [])


# ----------------------------------- 6. refusal: missing firstName

class TestRefusalMissingFirstName(_IsolatedStore):
    def test_validate_refuses_missing_first_name(self):
        row = dict(LEAD_OK, first_name="")
        with self.assertRaises(ListStagingRefused) as ctx:
            validate_lead_row(row)
        self.assertIn("firstName", str(ctx.exception))

    def test_stage_lead_refuses_before_transport(self):
        transport = fake_transport()
        row = dict(LEAD_OK, first_name="")
        with self.assertRaises(ListStagingRefused):
            stage_lead(940797, row, transport,
                       list_reader=fake_list_reader(LIST_UNBOUND))
        self.assertEqual(transport.calls, [])


# ----------------------------------- 7. refusal: missing lastName

class TestRefusalMissingLastName(_IsolatedStore):
    def test_validate_refuses_missing_last_name(self):
        row = dict(LEAD_OK, last_name="")
        with self.assertRaises(ListStagingRefused) as ctx:
            validate_lead_row(row)
        self.assertIn("lastName", str(ctx.exception))

    def test_stage_lead_refuses_before_transport(self):
        transport = fake_transport()
        row = dict(LEAD_OK, last_name="")
        with self.assertRaises(ListStagingRefused):
            stage_lead(940797, row, transport,
                       list_reader=fake_list_reader(LIST_UNBOUND))
        self.assertEqual(transport.calls, [])


# ----------------------------------- 8. the 0/0/0 silent-drop response

class TestSilentDropResponse(_IsolatedStore):
    """The provider returns addedLeadsCount: 0 with no error for a lead it
    silently drops. A 200 is not a success. The readback finds the lead
    absent and the verdict is UNKNOWN, which raises ListStagingUnverified.
    """

    def test_the_silent_drop_is_not_accepted(self):
        """addedLeadsCount: 0, totalLeads: 0, duplicateLeads: 0 - the lead
        was not added and the list is still empty. The readback finds no
        lead, so the verdict is UNKNOWN."""
        transport = fake_transport(response={
            "addedLeadsCount": 0, "totalLeads": 0, "duplicateLeads": 0})
        with self.assertRaises(ListStagingUnverified) as ctx:
            stage_lead(
                940797, LEAD_OK, transport,
                list_reader=fake_list_reader(LIST_UNBOUND),
                members_reader=fake_members_reader([], total=0))
        self.assertIn("UNKNOWN", str(ctx.exception))

    def test_the_transport_was_called_but_readback_failed(self):
        """The transport ran (the provider got the request) but the readback
        could not confirm the lead. This is Unverified, not Refused - the
        provider may have acted."""
        transport = fake_transport(response={
            "addedLeadsCount": 0, "totalLeads": 0, "duplicateLeads": 0})
        with self.assertRaises(ListStagingUnverified):
            stage_lead(
                940797, LEAD_OK, transport,
                list_reader=fake_list_reader(LIST_UNBOUND),
                members_reader=fake_members_reader([], total=0))
        self.assertEqual(len(transport.calls), 1,
                         "the transport was called")


# ----------------------------------- 9. condition not consulted

class TestConditionNotConsulted(_IsolatedStore):
    """When validation fails, the safety predicate is not consulted. The
    operator sees the data problem, not the safety problem. This is the
    gate ordering property: validate, then assert_safe, then transport."""

    def test_validation_failure_skips_the_safety_check(self):
        safety_called = [False]
        def tracking_reader(list_id):
            safety_called[0] = True
            return dict(LIST_BOUND)
        transport = fake_transport()
        row = dict(LEAD_OK, first_name="")
        with self.assertRaises(ListStagingRefused) as ctx:
            stage_lead(933603, row, transport,
                       list_reader=tracking_reader)
        self.assertIn("firstName", str(ctx.exception))
        self.assertFalse(safety_called[0],
                         "the safety check ran before validation")
        self.assertEqual(transport.calls, [])

    def test_validation_failure_skips_the_transport(self):
        transport = fake_transport()
        row = dict(LEAD_OK, first_name="", last_name="")
        with self.assertRaises(ListStagingRefused):
            stage_lead(940797, row, transport,
                       list_reader=fake_list_reader(LIST_UNBOUND))
        self.assertEqual(transport.calls, [])


# ----------------------------------- 10. provider read unavailable

class TestProviderReadUnavailable(_IsolatedStore):
    """When the provider read fails, the predicate refuses fail-closed.
    A list whose state is unknown is not proven safe."""

    def test_an_unreadable_list_refuses_fail_closed(self):
        def _boom(list_id):
            raise RuntimeError("connection reset")
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(940797, list_reader=_boom)
        self.assertIn("could not be read", str(ctx.exception))
        self.assertIn("not proven safe", str(ctx.exception))

    def test_the_transport_is_not_reached(self):
        def _boom(list_id):
            raise RuntimeError("connection reset")
        transport = fake_transport()
        with self.assertRaises(ListStagingRefused):
            stage_lead(940797, LEAD_OK, transport, list_reader=_boom)
        self.assertEqual(transport.calls, [])

    def test_a_none_response_refuses_fail_closed(self):
        """The provider returned nothing - no row, no id. A missing list is
        not an unbound one."""
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(940797, list_reader=lambda _: None)
        self.assertIn("no row", str(ctx.exception))

    def test_a_response_with_no_id_refuses_fail_closed(self):
        """The provider returned a row with no id field. Without an id we
        cannot confirm which list we read."""
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(940797,
                             list_reader=lambda _: {"name": "orphan"})
        self.assertIn("no id", str(ctx.exception))

    def test_no_list_id_refuses_fail_closed(self):
        """No list_id supplied at all - the predicate has nothing to read."""
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(None)
        self.assertIn("no list_id", str(ctx.exception))

    def test_zero_list_id_refuses_fail_closed(self):
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(0)
        self.assertIn("no list_id", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
