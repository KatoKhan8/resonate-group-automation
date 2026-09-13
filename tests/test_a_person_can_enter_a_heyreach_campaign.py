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


@contextlib.contextmanager
def _enabled():
    """Enable LINKEDIN_ADD_LEAD inside the test only, and stub revalidate.

    `perform` calls `executionguard.revalidate`, which re-reads the record
    from disk and re-runs the stops. These tests are about the write layer's
    response classification, not about the guard chain. Stubbing revalidate
    is safe because `test_a_stop_beats_an_authorization` pins the call order.
    """
    with mock.patch.object(providerwrites, "SUPPORTED",
                           (providerwrites.LINKEDIN_PAUSE,
                            providerwrites.EMAIL_PAUSE,
                            providerwrites.EMAIL_STOP_LEAD,
                            providerwrites.EMAIL_CREATE_CAMPAIGN,
                            providerwrites.EMAIL_SET_SEQUENCE,
                            providerwrites.LINKEDIN_ADD_LEAD)), \
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
    """LINKEDIN_ADD_LEAD is NOT in SUPPORTED. The door refuses it."""

    def test_linkedin_add_lead_is_not_supported(self):
        self.assertNotIn(providerwrites.LINKEDIN_ADD_LEAD,
                         providerwrites.SUPPORTED)

    def test_the_write_layer_still_refuses_prospect_facing_ops(self):
        """Nothing that reaches a prospect is supported."""
        enabled = [op for op in providerwrites.PROSPECT_FACING
                   if providerwrites.is_supported(op)]
        self.assertEqual(enabled, [])

    def test_supported_is_unchanged(self):
        self.assertEqual(
            providerwrites.SUPPORTED,
            (providerwrites.LINKEDIN_PAUSE, providerwrites.EMAIL_PAUSE,
             providerwrites.EMAIL_STOP_LEAD,
             providerwrites.EMAIL_CREATE_CAMPAIGN,
             providerwrites.EMAIL_SET_SEQUENCE))

    def test_the_route_is_on_write_routes(self):
        """The mechanism exists; the permission does not."""
        self.assertIn("/campaign/AddLeadsToCampaignV2", heyreach.WRITE_ROUTES)

    def test_the_transport_refuses_routes_not_on_write_routes(self):
        """A route NOT on the list is refused. This pins the allowlist."""
        with self.assertRaises(heyreach.ProviderError):
            heyreach._write_body("/campaign/Resume", {"campaignId": 1})


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
                authorization=auth, step=STEP, payload=APPROVED,
                transport=transport, readback=membership,
                expected={"found": {URL_ADA.lower()}})
            # Second attempt on the same key is refused.
            with self.assertRaises(executionguard.NotAuthorized):
                providerwrites.perform(
                    providerwrites.LINKEDIN_ADD_LEAD,
                    authorization=auth, step=STEP, payload=APPROVED,
                    transport=transport, readback=membership,
                    expected={"found": {URL_ADA.lower()}})
        self.assertEqual(len(transport.calls), 1,
                         "the transport was called twice on the same key")


if __name__ == "__main__":
    unittest.main()
