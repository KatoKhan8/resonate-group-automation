#!/usr/bin/env python3
"""Rehearse the HeyReach list staging path against a fake. TASK-186.

The LinkedIn counterpart of TASK-184's Bison campaign write rehearsal.
Every test uses a fake transport and fake provider reads. No test reaches
a real API, spends credits, or touches a production path.

WHAT THIS PROVES:

1. The entry point: `liststaging.stage_lead` is the function, but it bypasses
   `providerwrites.perform`. No higher-level entry point exists yet. When the
   verb is enabled, a wrapper must carry the gates through `perform`.

2. The refusal while the verb is off: `heyreach.add_lead_to_list` is NOT in
   SUPPORTED, so `perform` refuses with WriteUnsupported. This is the most
   important test: it proves the OFF switch works.

3. Idempotency: `AddLeadsToListV2` returns `{addedLeadsCount, totalLeads,
   duplicateLeads}`. A duplicate returns `addedLeadsCount: 0, duplicateLeads: 1`
   and the readback finds the lead present — ACCEPTED, not a refusal.

4. The readback: `readback_list_add` checks presence AND unboundness. It
   fails if either half is false.

5. The LIST → CAMPAIGN gap: nothing in the staging path can attach a list to
   a campaign. The attachment step is where the full activation gate belongs.

6. The 0/0/0 trap: the silent-drop response is treated as failure, not
   success. This is the difference between the path being safe and losing
   leads invisibly.
"""
import unittest

from src import providerwrites
from src.liststaging import (
    LINKEDIN_ADD_LEAD_TO_LIST,
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


# =====================================================================
# 1. THE ENTRY POINT
# =====================================================================

class TestEntryPoint(unittest.TestCase):
    """Which function should Claude call to stage a lead into a list?

    `liststaging.stage_lead` exists and takes a transport callable. It
    validates, gates, transports, and reads back — the same four-step shape
    `providerwrites.perform` uses. But it bypasses `perform` entirely.

    When the verb is enabled, a wrapper must carry the gates through
    `perform` — not a hand-rolled call. This is the same pattern as
    `bisonfactory.stage(campaign_id, live=True)`.

    THE ANSWER: no such entry point exists yet. `stage_lead` is the function,
    but it is not wired through `perform`. The wrapper belongs in
    `liststaging.py` or a new `listfactory.py`, and it must call
    `providerwrites.perform(LINKEDIN_ADD_LEAD_TO_LIST, transport=...,
    readback=...)`.
    """

    def test_stage_lead_exists_and_is_callable(self):
        """The low-level primitive exists."""
        self.assertTrue(callable(stage_lead))

    def test_stage_lead_bypasses_perform(self):
        """`stage_lead` takes a transport directly. It does NOT go through
        `providerwrites.perform`. This is documented in the module docstring:
        'the same four-step shape providerwrites.perform uses for every other
        write, applied to a route that is not yet in SUPPORTED'."""
        # If stage_lead went through perform, it would refuse because the
        # verb is not in SUPPORTED. But it succeeds with a fake transport.
        url = LEAD_OK["linkedin_url"]
        transport = fake_transport()
        result = stage_lead(
            940797, LEAD_OK, transport,
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        self.assertEqual(result["class"], "ACCEPTED")

    def test_perform_refuses_the_same_write(self):
        """The same write through `perform` refuses because the verb is not
        in SUPPORTED. This proves `stage_lead` and `perform` are different
        paths, and the wrapper that unifies them does not exist yet."""
        with self.assertRaises(providerwrites.WriteUnsupported):
            providerwrites.perform(
                LINKEDIN_ADD_LEAD_TO_LIST,
                transport=lambda p: None,
                readback=lambda: None)


# =====================================================================
# 2. THE REFUSAL WHILE THE VERB IS OFF
# =====================================================================

class TestRefusalWhileVerbOff(unittest.TestCase):
    """The most important test in the task: it proves the OFF switch works.

    With `heyreach.add_lead_to_list` absent from SUPPORTED, calling the path
    through `perform` must fail closed, loudly, naming the missing permission.
    """

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

    def test_the_verb_is_defined_but_not_enabled(self):
        """The constant exists, is in OPERATIONS, but is NOT in SUPPORTED."""
        self.assertIn(LINKEDIN_ADD_LEAD_TO_LIST, providerwrites.OPERATIONS)
        self.assertNotIn(LINKEDIN_ADD_LEAD_TO_LIST, providerwrites.SUPPORTED)

    def test_the_verb_is_not_in_conditional(self):
        """The predicate exists but is not wired into CONDITIONAL."""
        self.assertNotIn(LINKEDIN_ADD_LEAD_TO_LIST,
                         providerwrites.CONDITIONAL)


# =====================================================================
# 3. IDEMPOTENCY
# =====================================================================

class TestIdempotency(unittest.TestCase):
    """Is the write idempotent?

    `AddLeadsToListV2` returns `{addedLeadsCount, totalLeads, duplicateLeads}`.
    The response shape distinguishes:
      - addedLeadsCount: 1 → new lead added
      - addedLeadsCount: 0, duplicateLeads: 1 → lead was already there
      - addedLeadsCount: 0, totalLeads: 0, duplicateLeads: 0 → silent drop

    The provider IS idempotent for duplicates: a lead already in the list
    returns `duplicateLeads: 1` and the readback finds it present.
    """

    def test_a_new_lead_returns_added_count_one(self):
        transport = fake_transport(response={
            "addedLeadsCount": 1, "totalLeads": 1, "duplicateLeads": 0})
        url = LEAD_OK["linkedin_url"]
        result = stage_lead(
            940797, LEAD_OK, transport,
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        self.assertEqual(result["class"], "ACCEPTED")
        self.assertEqual(result["response"]["addedLeadsCount"], 1)

    def test_a_duplicate_lead_returns_duplicate_count_one(self):
        """The provider is idempotent: a lead already in the list returns
        addedLeadsCount: 0, duplicateLeads: 1. The readback finds the lead
        present. This is ACCEPTED, not a refusal."""
        transport = fake_transport(response={
            "addedLeadsCount": 0, "totalLeads": 1, "duplicateLeads": 1})
        url = LEAD_OK["linkedin_url"]
        result = stage_lead(
            940797, LEAD_OK, transport,
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        self.assertEqual(result["class"], "ACCEPTED")
        self.assertEqual(result["response"]["duplicateLeads"], 1)

    def test_the_response_shape_distinguishes_added_from_duplicate(self):
        """The provider's response has three fields. The readback does not
        trust addedLeadsCount alone — it reads the list membership."""
        transport = fake_transport(response={
            "addedLeadsCount": 0, "totalLeads": 1, "duplicateLeads": 1})
        url = LEAD_OK["linkedin_url"]
        result = stage_lead(
            940797, LEAD_OK, transport,
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        self.assertEqual(result["response"]["addedLeadsCount"], 0)
        self.assertEqual(result["response"]["duplicateLeads"], 1)
        self.assertEqual(result["class"], "ACCEPTED")


# =====================================================================
# 4. THE READBACK
# =====================================================================

class TestReadback(unittest.TestCase):
    """`addedLeadsCount: 1` is the provider's claim about its own write.
    What proves the lead is present AND the list is still unbound?

    `readback_list_add` performs two reads:
      1. `members_reader` — is the lead there?
      2. `list_reader` — is the list still unbound?

    It fails if either half is false.
    """

    def test_present_lead_and_unbound_list_is_accepted(self):
        url = LEAD_OK["linkedin_url"]
        rb = readback_list_add(
            940797, [url],
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        self.assertEqual(classify_readback(rb), "ACCEPTED")
        self.assertIn(url.lower(), rb["found"])
        self.assertTrue(rb["still_unbound"])

    def test_missing_lead_is_not_accepted(self):
        """The lead is not in the list. The readback fails the presence check."""
        rb = readback_list_add(
            940797, [LEAD_OK["linkedin_url"]],
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader([], total=0))
        self.assertEqual(classify_readback(rb), "UNKNOWN")
        self.assertEqual(rb["found"], set())

    def test_bound_list_is_not_accepted(self):
        """The list became bound after the write. The readback fails the
        unboundness check. This is the activation defect."""
        url = LEAD_OK["linkedin_url"]
        rb = readback_list_add(
            940797, [url],
            list_reader=fake_list_reader(LIST_BOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        self.assertEqual(classify_readback(rb), "DRIFTED")
        self.assertFalse(rb["still_unbound"])

    def test_both_halves_must_be_true(self):
        """The readback fails if EITHER the lead is missing OR the list is
        bound. Both checks are necessary."""
        url = LEAD_OK["linkedin_url"]
        # Missing lead, unbound list → UNKNOWN
        rb1 = readback_list_add(
            940797, [url],
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader([], total=0))
        self.assertNotEqual(classify_readback(rb1), "ACCEPTED")

        # Present lead, bound list → DRIFTED
        rb2 = readback_list_add(
            940797, [url],
            list_reader=fake_list_reader(LIST_BOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        self.assertNotEqual(classify_readback(rb2), "ACCEPTED")


# =====================================================================
# 5. THE LIST → CAMPAIGN GAP
# =====================================================================

class TestListToCampaignGap(unittest.TestCase):
    """What happens between LIST and CAMPAIGN?

    The staging path adds a lead to a LIST. The list is unbound — attached
    to no campaign. The moment the list is attached to a campaign, adding
    to it is adding to a campaign, and the campaign-level gate is the only
    path through.

    The attachment step is where the full activation gate belongs. Nothing
    in the staging path can reach it by accident.
    """

    def test_an_unbound_list_is_safe(self):
        """A list with campaignIds: [] is safe to stage into."""
        self.assertTrue(list_is_unbound(LIST_UNBOUND))

    def test_a_bound_list_is_refused(self):
        """A list with campaignIds: [599020] is refused."""
        self.assertFalse(list_is_unbound(LIST_BOUND))
        with self.assertRaises(ListStagingRefused):
            assert_list_safe(933603, list_reader=fake_list_reader(LIST_BOUND))

    def test_the_staging_path_cannot_attach_a_list_to_a_campaign(self):
        """`stage_lead` adds a lead to a list. It does not attach the list
        to a campaign. The attachment step is a separate operation — one
        that is not in SUPPORTED and not wired anywhere."""
        # The staging path takes a list_id and a lead row. It does not take
        # a campaign_id. There is no parameter that could attach the list.
        url = LEAD_OK["linkedin_url"]
        transport = fake_transport()
        result = stage_lead(
            940797, LEAD_OK, transport,
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        # The payload has listId and leads. No campaignId.
        payload = transport.calls[0]
        self.assertIn("listId", payload)
        self.assertNotIn("campaignId", payload)
        self.assertNotIn("campaign_id", payload)

    def test_the_readback_detects_if_the_list_became_bound(self):
        """If the list was unbound before the write and bound after, the
        readback classifies it as DRIFTED. This is the activation defect."""
        url = LEAD_OK["linkedin_url"]
        reads = [dict(LIST_UNBOUND), dict(LIST_BOUND)]
        def flip_reader(list_id):
            return reads.pop(0) if reads else dict(LIST_BOUND)
        transport = fake_transport()
        with self.assertRaises(ListStagingUnverified) as ctx:
            stage_lead(
                940797, LEAD_OK, transport,
                list_reader=flip_reader,
                members_reader=fake_members_reader(
                    [{"profile_url": url}], total=1))
        self.assertIn("DRIFTED", str(ctx.exception))


# =====================================================================
# 6. THE 0/0/0 TRAP
# =====================================================================

class TestSilentDropTrap(unittest.TestCase):
    """THE TRAP: a rehearsal that mocks the provider into agreeing is
    worthless. Make the fake return the 0/0/0 silent-drop response and
    assert the path treats it as a failure, not a success.

    The provider returns `addedLeadsCount: 0` with no error for a lead
    missing firstName or lastName. A 200 response is not a success. A code
    path that treats a 200 as a staged lead is the defect this function
    exists to prevent.

    This single behaviour is the difference between this path being safe
    and losing leads invisibly.
    """

    def test_the_silent_drop_is_not_accepted(self):
        """addedLeadsCount: 0, totalLeads: 0, duplicateLeads: 0 — the lead
        was not added and the list is still empty. The readback finds no
        lead, so the verdict is UNKNOWN, which raises ListStagingUnverified.
        """
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
        could not confirm the lead. This is Unverified, not Refused — the
        provider may have acted."""
        transport = fake_transport(response={
            "addedLeadsCount": 0, "totalLeads": 0, "duplicateLeads": 0})
        with self.assertRaises(ListStagingUnverified):
            stage_lead(
                940797, LEAD_OK, transport,
                list_reader=fake_list_reader(LIST_UNBOUND),
                members_reader=fake_members_reader([], total=0))
        self.assertEqual(len(transport.calls), 1)

    def test_validation_prevents_the_silent_drop_before_transport(self):
        """The provider silently drops a lead missing firstName. The local
        validation catches it BEFORE the transport is touched."""
        transport = fake_transport()
        row = dict(LEAD_OK, first_name="")
        with self.assertRaises(ListStagingRefused):
            stage_lead(940797, row, transport,
                       list_reader=fake_list_reader(LIST_UNBOUND))
        self.assertEqual(transport.calls, [])

    def test_a_200_with_zero_added_is_not_success(self):
        """The provider returns HTTP 200 with addedLeadsCount: 0. A code
        path that treats the 200 as success is the defect. The readback
        finds the lead absent and raises Unverified."""
        transport = fake_transport(response={
            "addedLeadsCount": 0, "totalLeads": 0, "duplicateLeads": 0})
        with self.assertRaises(ListStagingUnverified):
            stage_lead(
                940797, LEAD_OK, transport,
                list_reader=fake_list_reader(LIST_UNBOUND),
                members_reader=fake_members_reader([], total=0))


# =====================================================================
# 7. THE FULL SEQUENCE: QUALIFIED → LIST → READBACK → FINAL ELIGIBILITY
# =====================================================================

class TestFullSequence(unittest.TestCase):
    """The sequence to rehearse: QUALIFIED → LIST → READBACK → FINAL
    ELIGIBILITY → CAMPAIGN → SEND.

    The rehearsal stops where authorization stops: at LIST. The path from
    LIST to CAMPAIGN is the attachment step, which is not in SUPPORTED and
    not wired anywhere. The path from CAMPAIGN to SEND is the activation
    step, which is sealed.
    """

    def test_the_happy_path_qualified_to_list(self):
        """A qualified lead is staged into an unbound list. The readback
        confirms the lead is present and the list is still unbound."""
        url = LEAD_OK["linkedin_url"]
        transport = fake_transport(response={
            "addedLeadsCount": 1, "totalLeads": 1, "duplicateLeads": 0})
        result = stage_lead(
            940797, LEAD_OK, transport,
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        self.assertEqual(result["class"], "ACCEPTED")
        self.assertEqual(result["list_id"], 940797)
        self.assertEqual(result["profile_url"], url.lower())

    def test_the_path_stops_at_list(self):
        """The staging path adds a lead to a list. It does not attach the
        list to a campaign, activate a campaign, or send anything. The
        rehearsal stops where authorization stops."""
        url = LEAD_OK["linkedin_url"]
        transport = fake_transport()
        result = stage_lead(
            940797, LEAD_OK, transport,
            list_reader=fake_list_reader(LIST_UNBOUND),
            members_reader=fake_members_reader(
                [{"profile_url": url}], total=1))
        # The result has no campaign_id, no activation, no send.
        self.assertNotIn("campaign_id", result)
        self.assertNotIn("activated", result)
        self.assertNotIn("sent", result)

    def test_the_path_refuses_a_bound_list(self):
        """A list attached to a campaign is refused. The path cannot reach
        the campaign-level gate by accident."""
        transport = fake_transport()
        with self.assertRaises(ListStagingRefused):
            stage_lead(933603, LEAD_OK, transport,
                       list_reader=fake_list_reader(LIST_BOUND))
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
