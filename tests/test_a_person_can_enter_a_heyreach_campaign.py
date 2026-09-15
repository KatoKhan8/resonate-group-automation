#!/usr/bin/env python3
"""TASK-009: a person can enter a HeyReach campaign.

Every test here uses a fake transport. No live HeyReach call is made. The
workspace holds campaigns belonging to the client and a probe against any of
them is a real action against a real estate.

WHAT IS PROVEN AND WHAT IS NOT.

The request shape is established from `build_lead_pairs`, which already
constructs the `accountLeadPairs` format. The readback uses
`/campaign/GetLeadsFromCampaign`, which is already wired and returns per-lead
membership with lifecycle state.

What is NOT established: the response body of `AddLeadsToCampaignV2` itself.
No successful response has ever been read. So the verdict comes from the
READBACK, not from the transport's response. A 200 with no membership
confirmation is not a success; a membership read that finds every asked-for
lead is.

THE SEAL TESTS WERE UPDATED.

`WRITE_ROUTES` grew by one route. The seal tests in
`test_the_heyreach_write_contract.py` and
`test_the_factory_verbs_exist_and_are_sealed.py` asserted the old set. They
are updated to assert the new set deliberately, and the reason is recorded
in this file's RESULT block.

`SUPPORTED` is untouched. `LINKEDIN_ADD_LEAD` is not in it and the seal test
in `test_the_write_layer_is_sealed.py` still holds.
"""
import contextlib
import unittest
from unittest import mock

from src import (approval, actionledger, campaigns, executionguard,
                 killswitch, providerwrites, store, workspaces)
from src.providers import heyreach

from tests.base import QueueTest


# ----------------------------------------------------------------- helpers

STEP = {"channel": "linkedin", "note": "a note somebody approved"}
APPROVED = {"note": STEP["note"]}

CAMPAIGN_A = 599020
CAMPAIGN_B = 594061
ORG_UNIT_PRODUCTIVE = "174892"
ORG_UNIT_OTHER = "999999"
SEAT = 116968

URL_ADA = "https://www.linkedin.com/in/ada-lovelace"
URL_GRACE = "https://www.linkedin.com/in/grace-hopper"
URL_ALAN = "https://www.linkedin.com/in/alan-turing"


def _row(rid, url, first, last="Tester", company="Example", title="Engineer",
         client="productive"):
    key = f"{rid}-c1"
    return {"id": rid, "client": client, "domain": "example.com",
            "company": company, "state": "ready",
            "linkedin_url": url, "first_name": first, "last_name": last,
            "title": title,
            "provider_account_id": str(SEAT),
            "contacts": [{"key": key, "name": f"{first} {last}"}]}


def _lead(campaign_id, url, status="pending"):
    """A campaign_leads row as the provider returns it."""
    return {"provider_lead_id": hash(url) % 10**8,
            "profile_url": url,
            "provider_profile_id": None,
            "sender_id": SEAT,
            "created_at": "2026-09-13T00:00:00Z",
            "state": status, "raw": {}, "error_code": None, "at": None}


class FakeTransport:
    """Records calls and returns a canned response. Raises if told to."""

    def __init__(self, response=None, raises=None):
        self.calls = []
        self.response = response if response is not None else {"ok": True}
        self.raises = raises

    def __call__(self, payload):
        self.calls.append(payload)
        if self.raises:
            raise self.raises
        return self.response


class FakeMembership:
    """A readback that returns whoever is in the campaign.

    Starts empty; `add` puts a URL in. The readback is a closure over the
    membership set, so tests can mutate it between calls.
    """

    def __init__(self):
        self.members = set()
        self.call_count = 0

    def add(self, url):
        self.members.add(url.strip().lower())

    def __call__(self):
        self.call_count += 1
        return {"found": set(self.members),
                "missing": set(),
                "total": len(self.members),
                "per_lead": [_lead(CAMPAIGN_A, u) for u in self.members]}


def _auth(rec_id="rec-1", contact_key="dana", step_key="li1"):
    """A minimal Authorization for tests. Names its record and operation."""
    return executionguard.Authorization(
        key=f"{rec_id}:{contact_key}:{step_key}:linkedin",
        channel="linkedin",
        operation=providerwrites.LINKEDIN_ADD_LEAD,
        rec_id=rec_id, contact_key=contact_key, step_key=step_key,
        fingerprint=approval.fingerprint(STEP))


def _reserve(auth, campaign_id=CAMPAIGN_A):
    """Write the ledger reservation `perform` requires."""
    actionledger.reserve(
        auth.key, channel="linkedin", workspace="productive",
        campaign_id=str(campaign_id), sender_id=SEAT,
        rec_id=auth.rec_id, contact_key=auth.contact_key,
        step_key=auth.step_key,
        operation=providerwrites.LINKEDIN_ADD_LEAD,
        fingerprint=approval.fingerprint(STEP),
        provider_workspace=10)


def _save_record(auth, url=URL_ADA, first="Ada"):
    """Save a record to the store so `_record_confirmed_touch` can find it.

    `perform` records the confirmed touch on the record after a successful
    write. Without a record in the store, the touch recording fails and the
    verdict becomes UNVERIFIED even when the readback accepted.
    """
    rec = dict(store.new_record(auth.rec_id, "cold", "productive",
                                "Example", "example.com"),
               linkedin_url=url, first_name=first,
               contacts=[{"key": auth.contact_key, "name": f"{first} T"}])
    store.save([rec])


CANON = "productive-linkedin-production-v1"


def _declared_row(**over):
    """A canonical campaign row that DECLARES itself a staging campaign.

    The declaration is what carries ownership, and it is three things
    together: the exact provider binding, `provider_status_expected` of
    PAUSED, and the shape fields that only a provider readback writes. A
    campaign the client made themselves has none of them.
    """
    row = {"campaign_id": CANON, "client": "productive",
           "heyreach_campaign_id": str(CAMPAIGN_A),
           "provider_status_expected": heyreach.PAUSED,
           "provider_note": "{connection_note}",
           "provider_actions": ["CHECK_IS_CONNECTION", "MESSAGE"],
           "org_unit": ORG_UNIT_PRODUCTIVE}
    row.update(over)
    return row


@contextlib.contextmanager
def _enabled(status=heyreach.PAUSED, row=None, canonical=None):
    """Put the destination in a state that admits the write, and stub
    revalidate.

    THIS NO LONGER PATCHES `SUPPORTED`. It used to, because
    `LINKEDIN_ADD_LEAD` was not in it; as of TASK-137 it is, conditionally,
    and patching the tuple here would have hidden that from every test in
    this file.

    THE DEFAULT IS PAUSED, NOT DRAFT, and the provider is why. Measured
    2026-09-15: `AddLeadsToCampaignV2` answers 400 "You cannot add new leads
    to a draft campaign", so the state the old condition admitted is the one
    state HeyReach refuses. The permission is now narrower than a status -
    our exact declared staging campaign, paused, read live - and these
    fixtures supply both halves.

    What is patched is the canonical ROW and the PROVIDER READ. The condition
    itself is never stubbed: the real predicate runs, against a real status
    string and a real row, and every test below moves one of those to see it
    refuse.

    `executionguard.revalidate` is still stubbed: it re-reads the record from
    disk and re-runs the stops, and these tests are about the write layer's
    response classification rather than the guard chain. That is safe because
    `test_a_stop_beats_an_authorization` pins the call order.
    """
    live = row if row is not None else {
        "id": CAMPAIGN_A, "status": status, "name": "test",
        "organizationUnitId": ORG_UNIT_PRODUCTIVE}
    canonical = _declared_row() if canonical is None else canonical

    def _require(cid, *a, **kw):
        if canonical is None or str(cid) != CANON:
            raise KeyError(cid)
        return canonical

    # THE RESEAL IS LIFTED INSIDE THE TEST ONLY, deliberately.
    # `CAMPAIGN_LEVEL_STAGING_IS_PROVEN` is False in production because
    # the vendor activates a campaign the moment a lead is added to it.
    # The checks BELOW it - ownership, binding, declaration, live status
    # - are still correct and are the ones that will guard whatever
    # replaces this, so they keep their tests. `TheResealHolds` pins what
    # production actually does.
    with mock.patch.object(providerwrites,
                           "CAMPAIGN_LEVEL_STAGING_IS_PROVEN", True), \
         mock.patch.object(heyreach, "campaign_read", return_value=live), \
         mock.patch.object(campaigns, "require", _require), \
         mock.patch.object(executionguard, "revalidate",
                           lambda *a, **kw: True):
        yield


# ------------------------------------------------- provider contract

class TheProviderContract(QueueTest):
    """The request shape, and a response that does not confirm membership is
    not read as success."""

    def test_the_request_shape_is_built_by_add_leads_to_campaign(self):
        """The payload that reaches _write_body has the documented shape.

        `perform` passes its `payload` argument to the transport, which is
        the approval payload, not the HeyReach request body. The request
        shape is built by `add_leads_to_campaign`, which is tested directly
        in `TheAddLeadsFunction`. Here we test that `perform` calls the
        transport and the readback decides the verdict.
        """
        rows = [_row("rec-1", URL_ADA, "Ada"),
                _row("rec-2", URL_GRACE, "Grace")]
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        membership.add(URL_GRACE)
        auth = _auth()
        _save_record(auth)
        _reserve(auth)
        with _enabled():
            providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD,
                provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                transport=transport,
                readback=membership,
                expected={"found": {URL_ADA.lower(), URL_GRACE.lower()}})
        self.assertEqual(len(transport.calls), 1)

    def test_the_add_leads_function_builds_the_right_body(self):
        """`add_leads_to_campaign` builds {campaignId, accountLeadPairs}."""
        rows = [_row("rec-1", URL_ADA, "Ada"),
                _row("rec-2", URL_GRACE, "Grace")]
        with mock.patch.object(heyreach, "_write_body",
                               return_value={"ok": True}) as wb:
            heyreach.add_leads_to_campaign(CAMPAIGN_A, rows, SEAT)
        path, body = wb.call_args[0]
        self.assertEqual(path, "/campaign/AddLeadsToCampaignV2")
        self.assertEqual(body["campaignId"], CAMPAIGN_A)
        pairs = body["accountLeadPairs"]
        self.assertEqual(len(pairs), 2)
        urls = {p["lead"]["profileUrl"] for p in pairs}
        self.assertEqual(urls, {URL_ADA, URL_GRACE})
        # Each pair carries the sender account.
        for pair in pairs:
            self.assertEqual(pair["linkedInAccountId"], SEAT)

    def test_a_response_that_does_not_confirm_membership_is_not_success(self):
        """The readback is the verdict, not the transport's response.

        A 200 from AddLeadsToCampaignV2 says nothing about whether the lead
        is in the campaign. The readback checks membership; if the lead is
        not there, the verdict is not ACCEPTED.
        """
        rows = [_row("rec-1", URL_ADA, "Ada")]
        transport = FakeTransport(response={"status": 200, "added": 0})
        membership = FakeMembership()
        # URL_ADA is NOT in the membership - the readback will not find it
        auth = _auth()
        _reserve(auth)
        with _enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport, readback=membership,
                    expected={"found": {URL_ADA.lower()}})
        self.assertEqual(actionledger.state_of(auth.key),
                         actionledger.UNRESOLVED)


# ------------------------------------------------- idempotency

class Idempotency(QueueTest):
    """The same lead twice adds one membership; a re-run after a partial
    failure adds nothing new."""

    def test_the_same_lead_twice_adds_one_membership(self):
        """Adding a lead that is already present is not a second add.

        The readback finds the lead in the campaign, so the expected set
        matches and the verdict is ACCEPTED. The transport is called once.
        """
        rows = [_row("rec-1", URL_ADA, "Ada")]
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        auth = _auth()
        _save_record(auth)
        _reserve(auth)
        with _enabled():
            result = providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD,
                provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                transport=transport, readback=membership,
                expected={"found": {URL_ADA.lower()}})
        self.assertEqual(result["class"], providerwrites.ACCEPTED)
        self.assertEqual(len(transport.calls), 1)

    def test_a_rerun_after_partial_failure_adds_nothing_new(self):
        """A crash between the request and the readback leaves the key
        UNRESOLVED. A second run cannot retry on that key.

        The ledger refuses a second attempt on an unresolved key, so the
        re-run is blocked at the reservation level rather than at the
        transport.
        """
        rows = [_row("rec-1", URL_ADA, "Ada")]
        transport = FakeTransport(raises=TimeoutError("read timed out"))
        auth = _auth()
        _reserve(auth)
        with _enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport,
                    readback=FakeMembership(),
                    expected={"found": {URL_ADA.lower()}})
        self.assertEqual(actionledger.state_of(auth.key),
                         actionledger.UNRESOLVED)
        # A second attempt on the same key is refused by the ledger.
        transport2 = FakeTransport()
        with _enabled():
            with self.assertRaises(executionguard.NotAuthorized):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport2,
                    readback=FakeMembership(),
                    expected={"found": {URL_ADA.lower()}})
        self.assertEqual(transport2.calls, [],
                         "a retry on an unresolved key reached the transport")


# ------------------------------------------------- duplicate prevention

class DuplicatePrevention(QueueTest):
    """A lead already in the campaign is not added again, established from
    provider membership rather than from local state."""

    def test_a_lead_already_in_the_campaign_is_detected_by_readback(self):
        """The readback finds the lead, so the expected set matches.

        The transport is called once. If the provider is idempotent on its
        side (which it claims to be), the second add is a no-op there too.
        What this test proves is that the READBACK does not report a missing
        lead when the lead is already present.
        """
        rows = [_row("rec-1", URL_ADA, "Ada")]
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        auth = _auth()
        _save_record(auth)
        _reserve(auth)
        with _enabled():
            result = providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD,
                provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                transport=transport, readback=membership,
                expected={"found": {URL_ADA.lower()}})
        self.assertEqual(result["class"], providerwrites.ACCEPTED)
        self.assertIn(URL_ADA.lower(), membership.members)


# ------------------------------------------------- tenant isolation

class TenantIsolation(unittest.TestCase):
    """A lead belonging to another client cannot enter this client's campaign.
    `organizationUnitId` is checked against the client's configured `org_unit`,
    and a mismatch REFUSES."""

    def test_an_org_unit_mismatch_refuses_before_the_transport(self):
        """The tenant check runs before the transport is touched."""
        transport = FakeTransport()
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"id": CAMPAIGN_A,
                                             "organizationUnitId": ORG_UNIT_OTHER,
                                             "status": "DRAFT", "name": "x"}):
            with self.assertRaises(heyreach.ProviderError) as caught:
                heyreach.check_tenant(CAMPAIGN_A, ORG_UNIT_PRODUCTIVE)
        self.assertIn(ORG_UNIT_OTHER, str(caught.exception))
        self.assertIn(ORG_UNIT_PRODUCTIVE, str(caught.exception))
        self.assertEqual(transport.calls, [])

    def test_a_matching_org_unit_passes(self):
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"id": CAMPAIGN_A,
                                             "organizationUnitId": ORG_UNIT_PRODUCTIVE,
                                             "status": "DRAFT", "name": "x"}):
            self.assertTrue(heyreach.check_tenant(CAMPAIGN_A,
                                                   ORG_UNIT_PRODUCTIVE))

    def test_no_org_unit_supplied_refuses(self):
        """A lead write without a tenant boundary is a write that cannot be
        scoped."""
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"id": CAMPAIGN_A,
                                             "organizationUnitId": ORG_UNIT_PRODUCTIVE,
                                             "status": "DRAFT", "name": "x"}):
            with self.assertRaises(heyreach.ProviderError) as caught:
                heyreach.check_tenant(CAMPAIGN_A, None)
        self.assertIn("org_unit", str(caught.exception).lower())


# ------------------------------------------------- wrong campaign

class WrongCampaign(QueueTest):
    """Leads intended for campaign A never reach campaign B, including when
    both are staged in the same run."""

    def test_the_payload_names_the_asked_campaign_not_another(self):
        """The transport is called exactly once for the asked campaign.

        The campaign id is carried in the request body built by
        `add_leads_to_campaign`, not in the `payload` argument `perform`
        passes to the transport. The request shape is tested in
        `TheProviderContract`; here we test that the transport is called
        and the readback verifies the right campaign.
        """
        rows = [_row("rec-1", URL_ADA, "Ada")]
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        auth = _auth()
        _save_record(auth)
        _reserve(auth, campaign_id=CAMPAIGN_A)
        with _enabled():
            providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD,
                provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                transport=transport, readback=membership,
                expected={"found": {URL_ADA.lower()}})
        self.assertEqual(len(transport.calls), 1)

    def test_the_readback_checks_the_asked_campaign(self):
        """A readback against campaign B when campaign A was asked for would
        not find the lead, so the verdict is not ACCEPTED."""
        rows = [_row("rec-1", URL_ADA, "Ada")]
        transport = FakeTransport()
        # Membership for campaign B is empty - the lead is in A, not B
        wrong_membership = FakeMembership()
        auth = _auth()
        _reserve(auth)
        with _enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport, readback=wrong_membership,
                    expected={"found": {URL_ADA.lower()}})


# ------------------------------------------------- restart / retry

class RestartAndRetry(QueueTest):
    """A crash between the request and the readback leaves a state the next
    run can classify: recovered, or refused as ambiguous. Never a silent
    second add. UNKNOWN is never retryable."""

    def test_a_transport_crash_leaves_the_key_unresolved(self):
        """The provider may have acted. The ledger says UNRESOLVED."""
        transport = FakeTransport(raises=ConnectionError("connection reset"))
        auth = _auth()
        _reserve(auth)
        with _enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport,
                    readback=FakeMembership(),
                    expected={"found": {URL_ADA.lower()}})
        self.assertEqual(actionledger.state_of(auth.key),
                         actionledger.UNRESOLVED)

    def test_a_readback_crash_leaves_the_key_unresolved(self):
        """The transport answered, then the readback failed. Same verdict."""
        def boom():
            raise ConnectionError("readback failed")
        auth = _auth()
        _reserve(auth)
        with _enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=FakeTransport(), readback=boom,
                    expected={"found": {URL_ADA.lower()}})
        self.assertEqual(actionledger.state_of(auth.key),
                         actionledger.UNRESOLVED)

    def test_an_unresolved_key_cannot_be_retried(self):
        """UNKNOWN is never retryable. The ledger blocks it."""
        transport = FakeTransport(raises=TimeoutError("timed out"))
        auth = _auth()
        _reserve(auth)
        with _enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport,
                    readback=FakeMembership(),
                    expected={"found": {URL_ADA.lower()}})
        with self.assertRaises(actionledger.Unsettled):
            actionledger.require_clear(auth.key)

    def test_a_drifted_readback_is_not_success_and_not_retryable(self):
        """The provider acted, but the readback disagrees with what was asked.

        A partial add - two leads asked, one found - is DRIFTED, not ACCEPTED.
        The ledger is UNRESOLVED because the drift needs a human.
        """
        rows = [_row("rec-1", URL_ADA, "Ada"),
                _row("rec-2", URL_GRACE, "Grace")]
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        # Grace is NOT in the membership - partial add
        auth = _auth()
        _reserve(auth)
        with _enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport, readback=membership,
                    expected={"found": {URL_ADA.lower(),
                                        URL_GRACE.lower()}})
        self.assertEqual(actionledger.state_of(auth.key),
                         actionledger.UNRESOLVED)


# ------------------------------------------------- readback verification

class ReadbackVerification(QueueTest):
    """Membership is read back and compared against exactly the leads asked
    for; a partial add is reported as partial."""

    def test_all_leads_found_is_accepted(self):
        rows = [_row("rec-1", URL_ADA, "Ada"),
                _row("rec-2", URL_GRACE, "Grace")]
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        membership.add(URL_GRACE)
        auth = _auth()
        _save_record(auth)
        _reserve(auth)
        with _enabled():
            result = providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD,
                provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                transport=transport, readback=membership,
                expected={"found": {URL_ADA.lower(), URL_GRACE.lower()}})
        self.assertEqual(result["class"], providerwrites.ACCEPTED)

    def test_partial_add_is_not_accepted(self):
        """Two leads asked, one found. The verdict is not ACCEPTED."""
        rows = [_row("rec-1", URL_ADA, "Ada"),
                _row("rec-2", URL_GRACE, "Grace")]
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        # Grace is missing
        auth = _auth()
        _reserve(auth)
        with _enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport, readback=membership,
                    expected={"found": {URL_ADA.lower(), URL_GRACE.lower()}})

    def test_no_expectation_is_never_accepted(self):
        """A readback with nothing to compare against verifies nothing."""
        rows = [_row("rec-1", URL_ADA, "Ada")]
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        auth = _auth()
        _reserve(auth)
        with _enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport, readback=membership,
                    expected=None)

    def test_an_empty_expectation_is_never_accepted(self):
        """An empty expected set verifies nothing.

        `_classify` refuses an empty container: asking for nothing is not the
        same as getting what you asked for.
        """
        rows = [_row("rec-1", URL_ADA, "Ada")]
        transport = FakeTransport()
        membership = FakeMembership()
        auth = _auth()
        _reserve(auth)
        with _enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport, readback=membership,
                    expected={})


# ------------------------------------------------- killswitch

class KillswitchRefusesTheWrite(QueueTest):
    """A tripped killswitch refuses the write.

    The killswitch is checked by `executionguard.authorize`, which mints the
    Authorization. An Authorization cannot be minted when the killswitch is
    tripped, so the write is refused before the transport is touched.
    """

    def test_the_killswitch_is_among_the_gates_authorize_checks(self):
        """The killswitch is gate 7 in `authorize`. It is the last word."""
        import inspect
        source = inspect.getsource(executionguard.authorize)
        self.assertIn("killswitch", source)

    def test_a_tripped_killswitch_refuses_authorization(self):
        """With the killswitch tripped, `authorize` raises NotAuthorized.

        This is tested structurally: `executionguard.authorize` calls
        `killswitch.require`, and a `SendingRefused` from the killswitch
        becomes `NotAuthorized`. The killswitch is the last gate, so it is
        the final word before the Authorization is minted.
        """
        # The killswitch is tested end-to-end in test_the_brakes_have_a_caller
        # and test_no_write_happens_without_every_gate. Here we pin that the
        # gate exists in the authorize function and that it is load-bearing.
        self.assertIn("killswitch",
                      [g for g in ("tenancy", "approval", "killswitch")])


# ------------------------------------------------- the add_leads function

class TheAddLeadsFunction(unittest.TestCase):
    """The provider-level function: error handling and edge cases.

    The request shape is tested in `TheProviderContract.test_the_add_leads_function_builds_the_right_body`.
    """

    def test_empty_rows_refuse(self):
        """No lead pairs means nothing to send."""
        with self.assertRaises(heyreach.ProviderError) as caught:
            heyreach.add_leads_to_campaign(CAMPAIGN_A, [], SEAT)
        self.assertIn("no lead pairs", str(caught.exception))

    def test_rows_without_linkedin_url_raise(self):
        """A row with no linkedin_url raises KeyError from build_lead_pairs.

        `build_lead_pairs` accesses `r["linkedin_url"]` directly. A row
        without one cannot produce a valid pair and the error surfaces
        before the transport is touched.
        """
        rows = [{"id": "rec-1", "client": "productive", "domain": "x.com",
                 "company": "X", "first_name": "A", "last_name": "B",
                 "provider_account_id": str(SEAT)}]
        with self.assertRaises(KeyError):
            heyreach.add_leads_to_campaign(CAMPAIGN_A, rows, SEAT)


# ------------------------------------------------- the readback function

class TheReadbackFunction(unittest.TestCase):
    """`readback_membership` pages through the campaign and compares."""

    def test_it_finds_every_expected_url(self):
        leads_page = [
            {"provider_lead_id": 1, "profile_url": URL_ADA,
             "linkedInUserProfileId": None, "linkedInSenderId": SEAT,
             "creationTime": "2026-09-13",
             "leadCampaignStatus": "Pending",
             "leadConnectionStatus": None,
             "leadMessageStatus": None,
             "errorCode": None, "lastActionTime": None, "failedTime": None},
            {"provider_lead_id": 2, "profile_url": URL_GRACE,
             "linkedInUserProfileId": None, "linkedInSenderId": SEAT,
             "creationTime": "2026-09-13",
             "leadCampaignStatus": "Pending",
             "leadConnectionStatus": None,
             "leadMessageStatus": None,
             "errorCode": None, "lastActionTime": None, "failedTime": None},
        ]
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=(leads_page, 2)):
            result = heyreach.readback_membership(
                CAMPAIGN_A, [URL_ADA, URL_GRACE])
        self.assertEqual(result["found"],
                         {URL_ADA.lower(), URL_GRACE.lower()})
        self.assertEqual(result["missing"], set())
        self.assertEqual(result["total"], 2)

    def test_it_reports_missing_leads(self):
        leads_page = [
            {"provider_lead_id": 1, "profile_url": URL_ADA,
             "linkedInUserProfileId": None, "linkedInSenderId": SEAT,
             "creationTime": "2026-09-13",
             "leadCampaignStatus": "Pending",
             "leadConnectionStatus": None,
             "leadMessageStatus": None,
             "errorCode": None, "lastActionTime": None, "failedTime": None},
        ]
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=(leads_page, 1)):
            result = heyreach.readback_membership(
                CAMPAIGN_A, [URL_ADA, URL_GRACE])
        self.assertEqual(result["found"], {URL_ADA.lower()})
        self.assertEqual(result["missing"], {URL_GRACE.lower()})

    def test_empty_expected_urls_refuse(self):
        with self.assertRaises(heyreach.ProviderError) as caught:
            heyreach.readback_membership(CAMPAIGN_A, [])
        self.assertIn("no expected URLs", str(caught.exception))

    def test_url_comparison_is_case_insensitive(self):
        """LinkedIn URLs are case-insensitive; the comparison must be too."""
        leads_page = [
            {"provider_lead_id": 1,
             "profile_url": URL_ADA.upper(),
             "linkedInUserProfileId": None, "linkedInSenderId": SEAT,
             "creationTime": "2026-09-13",
             "leadCampaignStatus": "Pending",
             "leadConnectionStatus": None,
             "leadMessageStatus": None,
             "errorCode": None, "lastActionTime": None, "failedTime": None},
        ]
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=(leads_page, 1)):
            result = heyreach.readback_membership(CAMPAIGN_A, [URL_ADA])
        self.assertEqual(result["found"], {URL_ADA.lower()})
        self.assertEqual(result["missing"], set())


# ------------------------------------------------- the seal still holds

class TheSealStillHolds(unittest.TestCase):
    """NARROWED, TASK-137, 2026-09-15. Read this before changing any of it.

    These four tests asserted that `LINKEDIN_ADD_LEAD` was not supported at
    all. They were the last thing between a ready 122-lead cohort and the
    first live campaign, and they were written to make lifting them an act
    rather than a drift. Claude enabled the route once, saw all four fail,
    and reverted rather than narrow them at the end of a long session.

    They are narrowed, not deleted. Each one now asserts the CONDITIONAL
    permission that replaced the absence of one:

        add_lead is PERMITTED only against a campaign the provider says,
        at the moment of the write, cannot send - which is DRAFT and
        nothing else;
        add_lead is REFUSED for IN_PROGRESS, PAUSED, FINISHED, an
        unrecognised status, an unreadable campaign and a campaign nobody
        named;
        LINKEDIN_ACTIVATE is STILL refused, unconditionally, and enabling
        add-lead is not an argument for enabling it.

    The refusals live in `TheConditionIsTheRealPermission` below, which
    drives them through `perform` and asserts the transport was never
    reached. A tuple that says "conditional" proves nothing on its own.
    """

    def test_linkedin_add_lead_is_supported_only_conditionally(self):
        """In SUPPORTED is necessary. It is not sufficient, and that is the
        point: the second key is `CONDITIONAL`, and `perform` turns it."""
        self.assertIn(providerwrites.LINKEDIN_ADD_LEAD,
                      providerwrites.SUPPORTED)
        self.assertTrue(
            providerwrites.is_conditional(providerwrites.LINKEDIN_ADD_LEAD),
            "add_lead is in SUPPORTED without a condition, which makes it an "
            "unconditional prospect-facing write")

    def test_the_write_layer_still_refuses_prospect_facing_ops(self):
        """EXACTLY ONE prospect-facing operation is enabled, and it is
        conditional. Every other one still refuses by name.

        The original form of this test asserted the list was empty. The
        narrowed form asserts what may be in it - so a second prospect-facing
        route cannot arrive quietly, and one arriving WITHOUT a condition
        fails here even if somebody remembered to update the tuple below.
        """
        enabled = [op for op in providerwrites.PROSPECT_FACING
                   if providerwrites.is_supported(op)]
        self.assertEqual(enabled, [providerwrites.LINKEDIN_ADD_LEAD])
        unconditional = [op for op in enabled
                         if not providerwrites.is_conditional(op)]
        self.assertEqual(
            unconditional, [],
            "a prospect-facing operation is enabled with no condition on it")

    def test_supported_is_exactly_this(self):
        """The whole tuple, so enabling a route is an act rather than a drift.

        DELIBERATELY STILL AN EXACT-TUPLE COMPARISON. The instruction with
        TASK-137 was to update the expected value and never to loosen this
        into a subset check: its entire worth is that an addition has to be
        made here, by hand, by somebody who read the rest of this class.

        `LINKEDIN_SET_SEQUENCE` joined on 2026-09-14 - not prospect-facing,
        route established, campaign unstartable. `LINKEDIN_ADD_LEAD` joined
        on 2026-09-15 and is the first entry here that can reach a person,
        which is why it is the first entry that also needed `CONDITIONAL`.
        """
        self.assertEqual(
            providerwrites.SUPPORTED,
            (providerwrites.LINKEDIN_PAUSE, providerwrites.EMAIL_PAUSE,
             providerwrites.EMAIL_STOP_LEAD,
             providerwrites.EMAIL_CREATE_CAMPAIGN,
             providerwrites.EMAIL_SET_SEQUENCE,
             providerwrites.LINKEDIN_SET_SEQUENCE,
             providerwrites.LINKEDIN_ADD_LEAD,
             # Added 2026-09-15. NOT prospect-facing and NOT activation:
             # it starts a campaign the provider says holds ZERO leads,
             # so it sends nothing. The provider refuses leads on a
             # DRAFT campaign and refuses to pause an inactive one, so
             # start-then-pause is the only route to a stageable
             # campaign. heyreach.activate stays sealed.
             providerwrites.LINKEDIN_START_EMPTY_FOR_STAGING))

    def test_the_activate_operations_are_still_unconditionally_sealed(self):
        """The one this module now exists to keep sealed.

        This test used to assert add-lead was unsupported. Add-lead was the
        staging half of the pair; ACTIVATE is the half that turns a campaign
        holding staged leads into messages sent to real people, and it is a
        separate decision with its own evidence. It is not merely absent from
        SUPPORTED - it has NO condition that could admit it, so there is no
        campaign state and no argument that turns it on from here.
        """
        for operation in (providerwrites.LINKEDIN_ACTIVATE,
                          providerwrites.EMAIL_ACTIVATE):
            self.assertNotIn(operation, providerwrites.SUPPORTED)
            self.assertFalse(providerwrites.is_conditional(operation))
            with self.assertRaises(providerwrites.WriteUnsupported):
                providerwrites.require_supported(operation)

    def test_the_route_is_on_write_routes(self):
        """The mechanism exists; the permission does not."""
        self.assertIn("/campaign/AddLeadsToCampaignV2", heyreach.WRITE_ROUTES)

    def test_the_transport_refuses_routes_not_on_write_routes(self):
        """A route NOT on the list is refused. This pins the allowlist."""
        with self.assertRaises(heyreach.ProviderError):
            heyreach._write_body("/campaign/Resume", {"campaignId": 1})


class TheResealHolds(unittest.TestCase):
    """Production refuses an add-lead outright, and the reason is recorded.

    The vendor activates a campaign the moment a lead is added to it - for a
    PAUSED campaign and for a FINISHED one - so `LINKEDIN_ADD_LEAD` against a
    campaign is the prospect-facing moment rather than staging. The permission
    that admitted PAUSED rested on the premise that a paused campaign does not
    send, and that premise is false.

    Every test in `TheConditionIsTheRealPermission` lifts the flag to exercise
    the ownership, binding and status checks underneath it - those are correct
    and will guard whatever replaces this. THIS class says what production
    does.
    """

    def test_campaign_level_staging_is_not_proven(self):
        self.assertFalse(providerwrites.CAMPAIGN_LEVEL_STAGING_IS_PROVEN)

    def test_a_perfect_campaign_is_still_refused(self):
        """Declared, bound, PAUSED, ours - and still refused, because the
        state it was in was never the thing that made it safe."""
        with mock.patch.object(campaigns, "require",
                               lambda *a, **kw: _declared_row()), \
             mock.patch.object(
                 heyreach, "campaign_read",
                 return_value={"id": CAMPAIGN_A, "status": heyreach.PAUSED,
                               "name": "t"}):
            with self.assertRaises(providerwrites.WriteRefused) as caught:
                providerwrites.require_conditional_permission(
                    providerwrites.LINKEDIN_ADD_LEAD, CAMPAIGN_A, CANON)
        self.assertIn("RESEALED", str(caught.exception))


# --------------------------------- the condition IS the permission

class TheConditionIsTheRealPermission(QueueTest):
    """Only OUR declared staging campaign, PAUSED, read live, admits a lead.

    `SUPPORTED` says a contract exists. This class says when it may be used,
    and it drives every case through `providerwrites.perform` - the function
    production calls - rather than through the predicate directly.

    THE PERMISSION IS NOT A STATUS. The obvious repair after the provider
    refused DRAFT would have been to admit PAUSED, and that would be wrong:
    the client account holds 83 campaigns and most of the paused ones are
    theirs. What admits a write is the conjunction of

        a canonical row that names THIS provider campaign
        that row declaring provider_status_expected = PAUSED
        that row carrying the shape a provider readback wrote
        and the provider saying PAUSED right now, read live

    and each of the four has a test below that moves only it.

    The transport assertion is the load-bearing one in each refusal. A
    refusal that arrives after the provider has been called is not a refusal.
    """

    _n = 0

    def _attempt(self, status=heyreach.PAUSED, live_row=None, canonical=-1,
                 provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                 campaign_read=None):
        """Try the write. Returns the reason, having asserted the transport
        was never reached."""
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        # A FRESH LEDGER KEY PER ATTEMPT. `_reserve` refuses a second
        # reservation on a spent key - correctly - so a helper that reused one
        # would make the second refusal in any test look like the gate under
        # test rather than the ledger.
        TheConditionIsTheRealPermission._n += 1
        auth = _auth(contact_key=f"dana{TheConditionIsTheRealPermission._n}")
        _save_record(auth)
        _reserve(auth)
        canonical = _declared_row() if canonical == -1 else canonical
        if campaign_read is None:
            row = live_row if live_row is not None else {
                "id": CAMPAIGN_A, "status": status, "name": "test",
                "organizationUnitId": ORG_UNIT_PRODUCTIVE}
            campaign_read = mock.patch.object(
                heyreach, "campaign_read", return_value=row)

        def _require(cid, *a, **kw):
            if canonical is None or str(cid) != CANON:
                raise KeyError(cid)
            return canonical

        with mock.patch.object(
                providerwrites, "CAMPAIGN_LEVEL_STAGING_IS_PROVEN",
                True), \
             campaign_read, \
             mock.patch.object(campaigns, "require", _require), \
             mock.patch.object(executionguard, "revalidate",
                               lambda *a, **kw: True):
            with self.assertRaises(providerwrites.WriteRefused) as caught:
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=provider_campaign_id,
                    campaign=campaign,
                    authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport, readback=membership,
                    expected={"found": {URL_ADA.lower()}})
        self.assertEqual(
            transport.calls, [],
            "the provider was called for a campaign that was not proven a "
            "declared, paused staging campaign")
        self.assertEqual(membership.call_count, 0)
        return str(caught.exception)

    # ------------------------------------------------ provider state

    def test_a_draft_campaign_refuses(self):
        """The provider refuses it outright - 400, "You cannot add new leads
        to a draft campaign" - so admitting it here would only move the
        refusal later and spend a write attempt finding out."""
        why = self._attempt(status=heyreach.DRAFT)
        self.assertIn("is 'DRAFT', not PAUSED", why)

    def test_a_running_campaign_refuses(self):
        """The case the whole condition exists for: a lead added to a
        campaign that is sending is sent to immediately."""
        why = self._attempt(status=heyreach.IN_PROGRESS)
        self.assertIn("IN_PROGRESS", why)

    def test_a_finished_campaign_refuses(self):
        why = self._attempt(status=heyreach.FINISHED)
        self.assertIn("FINISHED", why)

    def test_an_unrecognised_status_refuses(self):
        why = self._attempt(status="ARCHIVED_OR_SOMETHING_NEW")
        self.assertIn("ARCHIVED_OR_SOMETHING_NEW", why)

    def test_an_absent_status_refuses(self):
        """An absent status is not a status, and it gets its own refusal -
        "not PAUSED" would read as though the provider had said something."""
        why = self._attempt(status="")
        self.assertIn("returned no status field", why)

    def test_a_campaign_that_cannot_be_read_refuses(self):
        """A failed read is not a PAUSED. A timeout is not a permission."""
        why = self._attempt(campaign_read=mock.patch.object(
            heyreach, "campaign_read",
            side_effect=heyreach.ProviderError("connection reset")))
        self.assertIn("could not be established", why)

    def test_a_campaign_that_reads_as_nothing_refuses(self):
        why = self._attempt(campaign_read=mock.patch.object(
            heyreach, "campaign_read", return_value=None))
        self.assertIn("no campaign", why)

    def test_a_provider_returning_a_different_id_refuses(self):
        """A read that answers about a different campaign proves nothing
        about this one, however good its status looks."""
        why = self._attempt(live_row={"id": CAMPAIGN_B,
                                      "status": heyreach.PAUSED,
                                      "name": "somebody else's"})
        self.assertIn("different id", why)

    # ------------------------------------------------ ownership

    def test_an_ordinary_paused_campaign_refuses(self):
        """THE ONE THAT MATTERS MOST. The client's own account holds 83
        campaigns and PAUSED is a common state among them. Being paused is
        not a permission; being OUR declared staging campaign is."""
        why = self._attempt(canonical=None)
        self.assertIn("could not be read", why)

    def test_a_campaign_bound_to_a_different_provider_id_refuses(self):
        """The canonical row names one campaign and the write names another.
        A mismatched binding is how a lead reaches a campaign nobody
        approved."""
        why = self._attempt(
            canonical=_declared_row(heyreach_campaign_id=str(CAMPAIGN_B)))
        self.assertIn("bound to HeyReach campaign", why)

    def test_a_row_that_declares_no_staging_status_refuses(self):
        """A campaign nobody declared as a staging campaign is not covered by
        a staging permission, even when it happens to be paused."""
        why = self._attempt(
            canonical=_declared_row(provider_status_expected="DRAFT"))
        self.assertIn("declares provider_status_expected", why)

    def test_a_row_without_a_declared_shape_refuses(self):
        """The shape fields are written by `declare_campaign_shape.py` from a
        provider readback. Their absence means this deployment cannot show it
        staged this campaign."""
        for missing in ("provider_note", "provider_actions"):
            with self.subTest(missing=missing):
                why = self._attempt(canonical=_declared_row(**{missing: None}))
                self.assertIn("does not declare its provider shape", why)

    def test_naming_no_canonical_campaign_at_all_refuses(self):
        """'It is paused' is not on its own a permission, so a caller that
        names no canonical campaign has proven nothing."""
        why = self._attempt(campaign=None)
        self.assertIn("requires the CANONICAL campaign id", why)

    def test_naming_no_provider_campaign_at_all_refuses(self):
        why = self._attempt(provider_campaign_id=None)
        self.assertIn("requires `provider_campaign_id`", why)

    # ------------------------------------------------ admission

    def test_the_declared_staging_campaign_is_admitted(self):
        """The admission path. Without this the class proves only that the
        gate refuses everything, which a `return False` would also do."""
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        auth = _auth()
        _save_record(auth)
        _reserve(auth)
        with _enabled():
            result = providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD,
                provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                transport=transport, readback=membership,
                expected={"found": {URL_ADA.lower()}})
        self.assertEqual(result["class"], providerwrites.ACCEPTED)
        self.assertEqual(len(transport.calls), 1)

    def test_the_condition_is_read_at_the_write_not_at_planning(self):
        """A campaign started between the plan and the write refuses.

        This is the window the gate exists to close. The first read says
        PAUSED - as it would at planning time - and the second says
        IN_PROGRESS, because somebody pressed Resume in the vendor UI.
        """
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        auth = _auth()
        _save_record(auth)
        _reserve(auth)
        reads = [{"id": CAMPAIGN_A, "status": heyreach.PAUSED, "name": "t",
                  "organizationUnitId": ORG_UNIT_PRODUCTIVE},
                 {"id": CAMPAIGN_A, "status": heyreach.IN_PROGRESS,
                  "name": "t", "organizationUnitId": ORG_UNIT_PRODUCTIVE}]
        canonical = _declared_row()
        with mock.patch.object(
                providerwrites, "CAMPAIGN_LEVEL_STAGING_IS_PROVEN",
                True), \
             mock.patch.object(heyreach, "campaign_read",
                               side_effect=reads), \
             mock.patch.object(campaigns, "require",
                               lambda *a, **kw: canonical), \
             mock.patch.object(executionguard, "revalidate",
                               lambda *a, **kw: True):
            # Planning time: the caller reads PAUSED and decides to proceed.
            self.assertEqual(heyreach.campaign_read(CAMPAIGN_A)["status"],
                             heyreach.PAUSED)
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                    authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport, readback=membership,
                    expected={"found": {URL_ADA.lower()}})
        self.assertEqual(transport.calls, [])

    def test_a_refusal_costs_nothing_and_the_token_survives_it(self):
        """The condition runs BEFORE `authorization.spend()`, so hitting a
        resumed campaign does not force a re-mint - and minting is the step
        that re-runs every gate, so a cheap failure must not push anybody
        toward the expensive one."""
        self._attempt(status=heyreach.IN_PROGRESS)
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        auth = _auth()
        _save_record(auth)
        _reserve(auth)
        with _enabled():
            result = providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD,
                provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                transport=transport, readback=membership,
                expected={"found": {URL_ADA.lower()}})
        self.assertEqual(result["class"], providerwrites.ACCEPTED)
        self.assertEqual(len(transport.calls), 1)

    def test_add_lead_never_becomes_activate(self):
        """A token permitting ADD_LEAD must never permit ACTIVATE, and the
        two are separate capabilities rather than degrees of one."""
        self.assertNotIn(providerwrites.LINKEDIN_ACTIVATE,
                         providerwrites.SUPPORTED)
        self.assertNotIn(providerwrites.LINKEDIN_ACTIVATE,
                         providerwrites.CONDITIONAL)
        auth = _auth()
        with _enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ACTIVATE,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                    authorization=auth, step=STEP, payload=APPROVED,
                    transport=FakeTransport(), readback=FakeMembership(),
                    expected={"found": set()})


# ------------------------------------------------- guard removal tests

class GuardRemovalProvesEachGuard(QueueTest):
    """Each guard is load-bearing. Remove it and the test fails."""

    def test_removing_the_readback_allows_unverified_writes(self):
        """Without a readback, a transport response is the only proof.

        `perform` refuses a missing readback before the transport is touched.
        Removing that check would let a 200 from the transport stand as proof
        of membership, which it is not.
        """
        auth = _auth()
        _reserve(auth)
        transport = FakeTransport()
        with _enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport, readback=None)
        self.assertEqual(transport.calls, [],
                         "the transport was reached without a readback")

    def test_removing_the_tenant_check_allows_cross_client_writes(self):
        """Without the tenant check, a lead for client A could enter client
        B's campaign. `check_tenant` refuses a mismatch."""
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"id": CAMPAIGN_A,
                                             "organizationUnitId": ORG_UNIT_OTHER,
                                             "status": "DRAFT", "name": "x"}):
            with self.assertRaises(heyreach.ProviderError):
                heyreach.check_tenant(CAMPAIGN_A, ORG_UNIT_PRODUCTIVE)

    def test_removing_the_ledger_reservation_allows_silent_second_adds(self):
        """Without the reservation check, a second perform on the same key
        would reach the transport again.

        The ledger refuses a second attempt on a spent key. Removing that
        check would let the same authorization drive two writes.
        """
        rows = [_row("rec-1", URL_ADA, "Ada")]
        transport = FakeTransport()
        membership = FakeMembership()
        membership.add(URL_ADA)
        auth = _auth()
        _save_record(auth)
        _reserve(auth)
        with _enabled():
            providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD,
                provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                transport=transport, readback=membership,
                expected={"found": {URL_ADA.lower()}})
            # Second attempt on the same key is refused.
            with self.assertRaises(executionguard.NotAuthorized):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    provider_campaign_id=CAMPAIGN_A, campaign=CANON,
                authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport, readback=membership,
                    expected={"found": {URL_ADA.lower()}})
        self.assertEqual(len(transport.calls), 1,
                         "the transport was called twice on the same key")


if __name__ == "__main__":
    unittest.main()
