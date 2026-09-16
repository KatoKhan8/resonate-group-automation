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

class TestVerbIsDeclared(unittest.TestCase):
    """The verb has a constant name, a string, and an OPERATIONS entry."""

    def test_the_constant_has_the_right_string(self):
        self.assertEqual(LINKEDIN_ADD_LEAD_TO_LIST, "heyreach.add_lead_to_list")

    def test_the_constant_is_in_providerwrites(self):
        self.assertEqual(providerwrites.LINKEDIN_ADD_LEAD_TO_LIST,
                         LINKEDIN_ADD_LEAD_TO_LIST)

    def test_the_verb_is_in_operations(self):
        self.assertIn(LINKEDIN_ADD_LEAD_TO_LIST, providerwrites.OPERATIONS)

    def test_the_verb_is_not_in_supported(self):
        """The trap: defining the verb must not enable it."""
        self.assertNotIn(LINKEDIN_ADD_LEAD_TO_LIST, providerwrites.SUPPORTED)

    def test_the_verb_is_not_in_conditional(self):
        """The condition predicate exists but is not wired into CONDITIONAL.
        Enabling is an operator decision and this task does not have it."""
        self.assertNotIn(LINKEDIN_ADD_LEAD_TO_LIST,
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

class TestPerformRefuses(unittest.TestCase):
    """A verb that exists and is unsupported must FAIL CLOSED, loudly, with
    a message naming the missing permission."""

    def test_perform_raises_write_unsupported(self):
        with self.assertRaises(providerwrites.WriteUnsupported) as ctx:
            providerwrites.perform(
                LINKEDIN_ADD_LEAD_TO_LIST,
                transport=lambda p: None,
                readback=lambda: None)
        self.assertIn("not supported", str(ctx.exception))

    def test_the_refusal_names_the_operation(self):
        with self.assertRaises(providerwrites.WriteUnsupported) as ctx:
            providerwrites.perform(
                LINKEDIN_ADD_LEAD_TO_LIST,
                transport=lambda p: None,
                readback=lambda: None)
        self.assertIn("heyreach.add_lead_to_list", str(ctx.exception))

    def test_the_refusal_names_the_channel(self):
        with self.assertRaises(providerwrites.WriteUnsupported) as ctx:
            providerwrites.perform(
                LINKEDIN_ADD_LEAD_TO_LIST,
                transport=lambda p: None,
                readback=lambda: None)
        self.assertIn("linkedin", str(ctx.exception))

    def test_the_transport_is_never_reached(self):
        """A refused verb must not touch the transport."""
        calls = []
        with self.assertRaises(providerwrites.WriteUnsupported):
            providerwrites.perform(
                LINKEDIN_ADD_LEAD_TO_LIST,
                transport=lambda p: calls.append(p),
                readback=lambda: None)
        self.assertEqual(calls, [])


# ----------------------------------- 3. refusal: list attached to a campaign

class TestRefusalListAttachedToCampaign(unittest.TestCase):
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

class TestRefusalListInAnotherTenant(unittest.TestCase):
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

class TestRefusalListNotOurs(unittest.TestCase):
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

class TestRefusalMissingFirstName(unittest.TestCase):
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

class TestRefusalMissingLastName(unittest.TestCase):
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

class TestSilentDropResponse(unittest.TestCase):
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

class TestConditionNotConsulted(unittest.TestCase):
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

class TestProviderReadUnavailable(unittest.TestCase):
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
