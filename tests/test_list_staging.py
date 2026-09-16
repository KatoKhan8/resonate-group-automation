"""List staging: the primitive that exists because campaigns cannot. TASK-165.

Every test uses a fake transport and fake provider reads. No test reaches a
real API, spends credits, or touches a production path.

The safety property under test: a list is safe to stage into exactly when it
is unbound (campaignIds is empty). The moment a list is attached to a
campaign, adding to it is adding to a campaign, which is the prospect-facing
path. Every refusal path has a test.
"""
import unittest
from unittest import mock

from src import liststaging
from src.liststaging import (
    ListStagingRefused,
    ListStagingUnverified,
    assert_list_safe,
    classify_readback,
    list_is_unbound,
    readback_list_add,
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

LEAD_OK = {
    "linkedin_url": "https://linkedin.com/in/test-profile",
    "first_name": "Test",
    "last_name": "Person",
    "company": "TestCo",
    "title": "Engineer",
}


def fake_transport(response=None):
    """A transport that records calls and returns a fixed response."""
    calls = []
    def _transport(payload):
        calls.append(payload)
        return response or {"addedLeadsCount": 1, "totalLeads": 1,
                            "duplicateLeads": 0}
    _transport.calls = calls
    return _transport


def fake_list_reader(row):
    """Return a fixed list row regardless of list_id."""
    def _read(list_id):
        return dict(row)
    return _read


def fake_members_reader(members, total=None):
    """Return fixed members regardless of list_id."""
    def _read(list_id, offset=0, limit=100):
        return list(members), total if total is not None else len(members)
    return _read


# ------------------------------------------ validate_lead_row

class TestValidateLeadRow(unittest.TestCase):
    def test_a_complete_row_passes(self):
        self.assertTrue(validate_lead_row(LEAD_OK))

    def test_missing_first_name_refuses(self):
        row = dict(LEAD_OK, first_name="")
        with self.assertRaises(ListStagingRefused) as ctx:
            validate_lead_row(row)
        self.assertIn("firstName", str(ctx.exception))

    def test_missing_last_name_refuses(self):
        row = dict(LEAD_OK, last_name="")
        with self.assertRaises(ListStagingRefused) as ctx:
            validate_lead_row(row)
        self.assertIn("lastName", str(ctx.exception))

    def test_missing_linkedin_url_refuses(self):
        row = dict(LEAD_OK, linkedin_url="")
        with self.assertRaises(ListStagingRefused) as ctx:
            validate_lead_row(row)
        self.assertIn("linkedin_url", str(ctx.exception))

    def test_missing_both_names_reports_both(self):
        row = dict(LEAD_OK, first_name="", last_name="")
        with self.assertRaises(ListStagingRefused) as ctx:
            validate_lead_row(row)
        msg = str(ctx.exception)
        self.assertIn("firstName", msg)
        self.assertIn("lastName", msg)

    def test_none_row_refuses(self):
        with self.assertRaises(ListStagingRefused):
            validate_lead_row(None)

    def test_whitespace_only_name_refuses(self):
        row = dict(LEAD_OK, first_name="   ")
        with self.assertRaises(ListStagingRefused) as ctx:
            validate_lead_row(row)
        self.assertIn("firstName", str(ctx.exception))


# ------------------------------------------ list_is_unbound

class TestListIsUnbound(unittest.TestCase):
    def test_empty_campaign_ids_is_unbound(self):
        self.assertTrue(list_is_unbound(LIST_UNBOUND))

    def test_non_empty_campaign_ids_is_bound(self):
        self.assertFalse(list_is_unbound(LIST_BOUND))

    def test_absent_campaign_ids_is_unbound(self):
        self.assertTrue(list_is_unbound({"id": 1}))

    def test_none_campaign_ids_is_unbound(self):
        self.assertTrue(list_is_unbound({"id": 1, "campaignIds": None}))


# ------------------------------------------ assert_list_safe

class TestAssertListSafe(unittest.TestCase):
    def test_an_unbound_list_passes(self):
        row = assert_list_safe(940797, list_reader=fake_list_reader(LIST_UNBOUND))
        self.assertEqual(row["id"], 940797)

    def test_a_bound_list_refuses(self):
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(933603, list_reader=fake_list_reader(LIST_BOUND))
        self.assertIn("attached to campaign", str(ctx.exception))
        self.assertIn("599020", str(ctx.exception))

    def test_an_unreadable_list_refuses(self):
        def _boom(list_id):
            raise RuntimeError("connection reset")
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(940797, list_reader=_boom)
        self.assertIn("could not be read", str(ctx.exception))

    def test_a_missing_list_refuses(self):
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(940797, list_reader=lambda _: None)
        self.assertIn("no row", str(ctx.exception))

    def test_a_list_with_no_id_refuses(self):
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(940797, list_reader=lambda _: {"name": "x"})
        self.assertIn("no id", str(ctx.exception))

    def test_no_list_id_refuses(self):
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(None)
        self.assertIn("no list_id", str(ctx.exception))

    def test_zero_list_id_refuses(self):
        with self.assertRaises(ListStagingRefused) as ctx:
            assert_list_safe(0)
        self.assertIn("no list_id", str(ctx.exception))

    def test_the_transport_is_not_reached_for_a_bound_list(self):
        """The whole point: the refusal happens before any provider write."""
        transport = fake_transport()
        with self.assertRaises(ListStagingRefused):
            stage_lead(933603, LEAD_OK, transport,
                       list_reader=fake_list_reader(LIST_BOUND))
        self.assertEqual(transport.calls, [],
                         "the transport was called for a bound list")


# ------------------------------------------ readback_list_add

class TestReadbackListAdd(unittest.TestCase):
    def test_a_present_lead_and_unbound_list_is_accepted(self):
        url = "https://linkedin.com/in/test-profile"
        members = [{"profile_url": url}]
        rb = readback_list_add(
            940797, [url],
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(members, total=1))
        self.assertEqual(rb["found"], {url.lower()})
        self.assertEqual(rb["missing"], set())
        self.assertTrue(rb["still_unbound"])

    def test_a_missing_lead_is_reported(self):
        rb = readback_list_add(
            940797, ["https://linkedin.com/in/test-profile"],
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader([], total=0))
        self.assertEqual(rb["found"], set())
        self.assertTrue(len(rb["missing"]) > 0)

    def test_a_list_that_became_bound_is_reported(self):
        url = "https://linkedin.com/in/test-profile"
        members = [{"profile_url": url}]
        rb = readback_list_add(
            940797, [url],
            list_reader=fake_list_reader(LIST_BOUND),
            members_reader=fake_members_reader(members, total=1))
        self.assertFalse(rb["still_unbound"])

    def test_total_count_is_reported(self):
        url = "https://linkedin.com/in/test-profile"
        members = [{"profile_url": url}]
        rb = readback_list_add(
            940797, [url],
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(members, total=42))
        self.assertEqual(rb["total"], 42)

    def test_no_expected_urls_refuses(self):
        with self.assertRaises(ListStagingRefused):
            readback_list_add(940797, [])


# ------------------------------------------ classify_readback

class TestClassifyReadback(unittest.TestCase):
    def test_all_found_and_unbound_is_accepted(self):
        self.assertEqual(classify_readback({
            "found": {"u"}, "missing": set(), "still_unbound": True,
        }), "ACCEPTED")

    def test_missing_lead_is_unknown(self):
        self.assertEqual(classify_readback({
            "found": set(), "missing": {"u"}, "still_unbound": True,
        }), "UNKNOWN")

    def test_bound_list_is_drifted(self):
        self.assertEqual(classify_readback({
            "found": {"u"}, "missing": set(), "still_unbound": False,
        }), "DRIFTED")

    def test_drifted_wins_over_missing(self):
        """If the list became bound AND the lead is missing, DRIFTED wins —
        the activation defect is the more serious finding."""
        self.assertEqual(classify_readback({
            "found": set(), "missing": {"u"}, "still_unbound": False,
        }), "DRIFTED")


# ------------------------------------------ stage_lead (full path)

class TestStageLead(unittest.TestCase):
    def test_the_happy_path(self):
        url = LEAD_OK["linkedin_url"]
        transport = fake_transport()
        result = stage_lead(
            940797, LEAD_OK, transport,
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        self.assertEqual(result["class"], "ACCEPTED")
        self.assertEqual(result["list_id"], 940797)
        self.assertEqual(len(transport.calls), 1)

    def test_the_payload_shape(self):
        """The provider expects profileUrl, firstName, lastName."""
        url = LEAD_OK["linkedin_url"]
        transport = fake_transport()
        stage_lead(
            940797, LEAD_OK, transport,
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        payload = transport.calls[0]
        self.assertEqual(payload["listId"], 940797)
        self.assertEqual(len(payload["leads"]), 1)
        lead = payload["leads"][0]
        self.assertEqual(lead["profileUrl"], url)
        self.assertEqual(lead["firstName"], "Test")
        self.assertEqual(lead["lastName"], "Person")

    def test_bound_list_refuses_before_transport(self):
        transport = fake_transport()
        with self.assertRaises(ListStagingRefused):
            stage_lead(933603, LEAD_OK, transport,
                       list_reader=fake_list_reader(LIST_BOUND))
        self.assertEqual(transport.calls, [])

    def test_missing_first_name_refuses_before_transport(self):
        transport = fake_transport()
        row = dict(LEAD_OK, first_name="")
        with self.assertRaises(ListStagingRefused):
            stage_lead(940797, row, transport,
                       list_reader=fake_list_reader(LIST_UNBOUND))
        self.assertEqual(transport.calls, [])

    def test_missing_last_name_refuses_before_transport(self):
        transport = fake_transport()
        row = dict(LEAD_OK, last_name="")
        with self.assertRaises(ListStagingRefused):
            stage_lead(940797, row, transport,
                       list_reader=fake_list_reader(LIST_UNBOUND))
        self.assertEqual(transport.calls, [])

    def test_lead_already_present_is_still_accepted(self):
        """The provider is idempotent — a duplicate returns addedLeadsCount: 0
        but does not error. The readback finds the lead present. This is
        ACCEPTED, not a refusal, because the lead IS in the list."""
        url = LEAD_OK["linkedin_url"]
        transport = fake_transport(response={
            "addedLeadsCount": 0, "totalLeads": 1, "duplicateLeads": 1})
        result = stage_lead(
            940797, LEAD_OK, transport,
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        self.assertEqual(result["class"], "ACCEPTED")

    def test_gate_not_consulted_refuses(self):
        """If the list reader says the list is bound, the transport is never
        reached. This is the whole point of the gate."""
        transport = fake_transport()
        call_count = [0]
        def counting_reader(list_id):
            call_count[0] += 1
            return dict(LIST_BOUND)
        with self.assertRaises(ListStagingRefused):
            stage_lead(933603, LEAD_OK, transport,
                       list_reader=counting_reader)
        self.assertEqual(call_count[0], 1, "the gate was consulted")
        self.assertEqual(transport.calls, [],
                         "the transport was not reached")

    def test_transport_failure_is_unverified(self):
        def _boom(payload):
            raise RuntimeError("connection reset")
        with self.assertRaises(ListStagingUnverified):
            stage_lead(940797, LEAD_OK, _boom,
                       list_reader=fake_list_reader(LIST_UNBOUND))

    def test_readback_finding_no_lead_is_unverified(self):
        transport = fake_transport()
        with self.assertRaises(ListStagingUnverified) as ctx:
            stage_lead(
                940797, LEAD_OK, transport,
                list_reader=fake_list_reader(LIST_UNBOUND),
                members_reader=fake_members_reader([], total=0))
        self.assertIn("UNKNOWN", str(ctx.exception))

    def test_readback_finding_bound_list_is_unverified(self):
        """The list was unbound before the write and bound after. The write
        may have triggered a binding — the activation defect."""
        url = LEAD_OK["linkedin_url"]
        transport = fake_transport()
        reads = [dict(LIST_UNBOUND), dict(LIST_BOUND)]
        def flip_reader(list_id):
            return reads.pop(0) if reads else dict(LIST_BOUND)
        with self.assertRaises(ListStagingUnverified) as ctx:
            stage_lead(
                940797, LEAD_OK, transport,
                list_reader=flip_reader,
                members_reader=fake_members_reader(
                    [{"profile_url": url}], total=1))
        self.assertIn("DRIFTED", str(ctx.exception))

    def test_a_list_belonging_to_another_tenant_refuses(self):
        """A list whose campaignIds names a campaign in another org_unit.
        The predicate checks campaignIds, not org_unit directly — but a
        bound list is refused whatever tenant owns it."""
        other_tenant_list = {
            "id": 12345,
            "name": "other-tenant-list",
            "listType": "USER_LIST",
            "totalItemsCount": 10,
            "campaignIds": [999999],
            "creationTime": "2026-09-15T00:00:00Z",
        }
        transport = fake_transport()
        with self.assertRaises(ListStagingRefused) as ctx:
            stage_lead(12345, LEAD_OK, transport,
                       list_reader=fake_list_reader(other_tenant_list))
        self.assertIn("attached to campaign", str(ctx.exception))
        self.assertEqual(transport.calls, [])


# ------------------------------------------ integration: gate ordering

class TestGateOrdering(unittest.TestCase):
    """The gates run in order: validate, then assert_safe, then transport.

    A failure at gate N must not reach gate N+1.
    """

    def test_validation_runs_before_the_safety_check(self):
        """A lead missing firstName is refused even if the list is bound.
        The validation failure fires first — the operator sees the data
        problem, not the safety problem."""
        transport = fake_transport()
        safety_called = [False]
        def tracking_reader(list_id):
            safety_called[0] = True
            return dict(LIST_BOUND)
        row = dict(LEAD_OK, first_name="")
        with self.assertRaises(ListStagingRefused) as ctx:
            stage_lead(933603, row, transport,
                       list_reader=tracking_reader)
        self.assertIn("firstName", str(ctx.exception))
        self.assertFalse(safety_called[0],
                         "the safety check ran before validation")
        self.assertEqual(transport.calls, [])

    def test_safety_check_runs_before_the_transport(self):
        """A bound list is refused before the transport is called."""
        transport = fake_transport()
        with self.assertRaises(ListStagingRefused):
            stage_lead(933603, LEAD_OK, transport,
                       list_reader=fake_list_reader(LIST_BOUND))
        self.assertEqual(transport.calls, [])

    def test_a_200_response_is_not_treated_as_success_without_readback(self):
        """The provider returns 200 with addedLeadsCount: 0 for a lead
        missing firstName. If the readback does not find the lead, the
        result is Unverified, not Accepted."""
        transport = fake_transport(response={
            "addedLeadsCount": 0, "totalLeads": 0, "duplicateLeads": 0})
        with self.assertRaises(ListStagingUnverified):
            stage_lead(
                940797, LEAD_OK, transport,
                list_reader=fake_list_reader(LIST_UNBOUND),
                members_reader=fake_members_reader([], total=0))


if __name__ == "__main__":
    unittest.main()
