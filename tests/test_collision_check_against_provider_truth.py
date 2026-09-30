"""TASK-935: collision check against provider truth, not the local ledger.

Five test arms, each required by the task:

  1. a person in one of OUR campaigns -> COLLISION naming it
  2. a person in a CLIENT campaign     -> COLLISION naming it
  3. a person in neither, complete walk -> CLEAR
  4. an INCOMPLETE walk (timeout)       -> UNKNOWN, never CLEAR
  5. no write is issued                 -> booby-trap on the transport

Every test drives the real provider modules through the transport seam.
Nothing reaches a network. The booby-trap test proves the trap fires,
because assertEqual([], requests) is satisfied just as well by a trap
that was never installed.
"""
import json
import os
import unittest

from src import providers
from src.providers import HttpTimeout
from src import collisioncheck


class _BoobyTrap(AssertionError):
    """Fired when any provider request is made. The trap, not a result."""


class _Wire:
    """A transport mock that answers specific URLs with specific bodies.

    Routes are matched by URL substring. Unmatched URLs raise, so a test
    that triggers an unexpected call fails loudly rather than silently.
    """

    def __init__(self):
        self.routes = {}
        self.calls = []

    def on(self, substring, status, body):
        self.routes[substring] = (status, body)
        return self

    def __call__(self, method, url, headers, body=None, timeout=None):
        self.calls.append({"method": method, "url": url, "body": body})
        for substring, (status, response) in self.routes.items():
            if substring in url:
                return status, json.dumps(response)
        raise _BoobyTrap(f"no route for {method} {url}")


class _TimeoutWire:
    """A transport mock that times out on specific URLs."""

    def __init__(self, timeout_substrings, fallback=None):
        self.timeout_substrings = timeout_substrings
        self.fallback = fallback or _Wire()
        self.calls = []

    def on(self, substring, status, body):
        self.fallback.on(substring, status, body)
        return self

    def __call__(self, method, url, headers, body=None, timeout=None):
        self.calls.append({"method": method, "url": url, "body": body})
        for s in self.timeout_substrings:
            if s in url:
                raise HttpTimeout(f"simulated timeout on {url}")
        return self.fallback(method, url, headers, body, timeout)


def _install(wire):
    providers.set_transport(wire)
    # Ensure BISON_KEY is set so bison.headers() does not raise.
    os.environ.setdefault("BISON_KEY", "test-key-not-real")
    os.environ.setdefault("HEYREACH_KEY", "test-key-not-real")


def _bison_lead(email, campaign_entries):
    """A EmailBison lead row with lead_campaign_data."""
    return {
        "id": 99999,
        "email": email,
        "status": "active",
        "lead_campaign_data": campaign_entries,
    }


def _bison_campaign(cid, name, status="active"):
    return {"id": cid, "name": name, "status": status}


def _heyreach_campaign(cid, name):
    return {"id": cid, "name": name, "organizationUnitId": 118832}


def _heyreach_lead(profile_url, company_name):
    return {
        "id": 1001,
        "linkedInUserProfile": {
            "profileUrl": profile_url,
            "linkedin_id": "slug-1",
            "companyName": company_name,
        },
        "linkedInUserProfileId": "prof-1",
        "linkedInSenderId": None,
        "creationTime": "2026-01-01T00:00:00Z",
        "leadCampaignStatus": "Pending",
        "leadConnectionStatus": "None",
        "leadMessageStatus": "None",
        "lastActionTime": None,
        "failedTime": None,
        "errorCode": None,
    }


class TestPersonInOurCampaign(unittest.TestCase):
    """Arm 1: a person in one of OUR campaigns -> COLLISION naming it."""

    def setUp(self):
        self.wire = _Wire()
        _install(self.wire)
        self.addCleanup(providers.reset_transport)
        # Short-circuit retries so tests are fast.
        self._orig_attempts = collisioncheck.RETRY_ATTEMPTS
        collisioncheck.RETRY_ATTEMPTS = 1
        self.addCleanup(setattr, collisioncheck, "RETRY_ATTEMPTS",
                        self._orig_attempts)

    def test_person_in_our_campaign_is_collision(self):
        email = "prospect@acme.test"
        self.wire.on(
            "/leads?search=",
            200,
            {"data": [_bison_lead(email, [
                {"campaign_id": 491, "status": "in_sequence",
                 "emails_sent": 2, "replies": 0, "opens": 1},
            ])],
             "meta": {"total": 1, "last_page": 1, "per_page": 15}})
        self.wire.on(
            "/campaigns/491",
            200,
            {"data": _bison_campaign(491, "Ironvault [resonate/491]")})

        result = collisioncheck.check_email_bison(email)

        self.assertEqual(collisioncheck.COLLISION, result["verdict"])
        self.assertTrue(result["complete"])
        self.assertEqual(1, len(result["collisions"]))
        self.assertEqual(491, result["collisions"][0]["campaign_id"])
        self.assertEqual("Ironvault [resonate/491]",
                         result["collisions"][0]["campaign_name"])


class TestPersonInClientCampaign(unittest.TestCase):
    """Arm 2: a person in a CLIENT campaign -> COLLISION naming it."""

    def setUp(self):
        self.wire = _Wire()
        _install(self.wire)
        self.addCleanup(providers.reset_transport)
        self._orig_attempts = collisioncheck.RETRY_ATTEMPTS
        collisioncheck.RETRY_ATTEMPTS = 1
        self.addCleanup(setattr, collisioncheck, "RETRY_ATTEMPTS",
                        self._orig_attempts)

    def test_person_in_client_campaign_is_collision(self):
        email = "colleague@brightpath.test"
        self.wire.on(
            "/leads?search=",
            200,
            {"data": [_bison_lead(email, [
                {"campaign_id": 352, "status": "sequence_finished",
                 "emails_sent": 5, "replies": 1, "opens": 3},
            ])],
             "meta": {"total": 1, "last_page": 1, "per_page": 15}})
        self.wire.on(
            "/campaigns/352",
            200,
            {"data": _bison_campaign(352, "Productive Outreach")})

        result = collisioncheck.check_email_bison(email)

        self.assertEqual(collisioncheck.COLLISION, result["verdict"])
        self.assertEqual(1, len(result["collisions"]))
        self.assertEqual(352, result["collisions"][0]["campaign_id"])
        self.assertEqual("Productive Outreach",
                         result["collisions"][0]["campaign_name"])


class TestClearAfterCompleteWalk(unittest.TestCase):
    """Arm 3: a person in neither estate, complete walk -> CLEAR."""

    def setUp(self):
        self.wire = _Wire()
        _install(self.wire)
        self.addCleanup(providers.reset_transport)
        self._orig_attempts = collisioncheck.RETRY_ATTEMPTS
        collisioncheck.RETRY_ATTEMPTS = 1
        self.addCleanup(setattr, collisioncheck, "RETRY_ATTEMPTS",
                        self._orig_attempts)

    def test_emailbison_clear_when_lead_not_found(self):
        self.wire.on(
            "/leads?search=",
            200,
            {"data": [],
             "meta": {"total": 0, "last_page": 1, "per_page": 15}})

        result = collisioncheck.check_email_bison("nobody@acme.test")

        self.assertEqual(collisioncheck.CLEAR, result["verdict"])
        self.assertTrue(result["complete"])
        self.assertEqual([], result["collisions"])

    def test_heyreach_clear_after_full_walk(self):
        """No lead in any campaign matches the domain."""
        # One campaign, two leads, neither matching.
        self.wire.on(
            "/campaign/GetAll",
            200,
            {"items": [_heyreach_campaign(100, "Our Campaign")],
             "totalCount": 1})
        self.wire.on(
            "/campaign/GetLeadsFromCampaign",
            200,
            {"items": [
                _heyreach_lead("https://linkedin.com/in/alice",
                               "OtherCorp"),
                _heyreach_lead("https://linkedin.com/in/bob",
                               "DifferentInc"),
            ],
             "totalCount": 2})

        result = collisioncheck.check_heyreach_company("acme.test")

        self.assertEqual(collisioncheck.CLEAR, result["verdict"])
        self.assertTrue(result["complete"])
        self.assertEqual([], result["collisions"])
        self.assertEqual(1, result["campaigns_walked"])
        self.assertEqual(2, result["leads_walked"])

    def test_combined_clear_when_both_clear(self):
        self.wire.on(
            "/leads?search=",
            200,
            {"data": [],
             "meta": {"total": 0, "last_page": 1, "per_page": 15}})
        self.wire.on(
            "/campaign/GetAll",
            200,
            {"items": [_heyreach_campaign(100, "Campaign")],
             "totalCount": 1})
        self.wire.on(
            "/campaign/GetLeadsFromCampaign",
            200,
            {"items": [_heyreach_lead("https://linkedin.com/in/x",
                                     "OtherCorp")],
             "totalCount": 1})

        result = collisioncheck.check(
            email="nobody@acme.test", company_domain="acme.test")

        self.assertEqual(collisioncheck.CLEAR, result["verdict"])


class TestIncompleteWalkIsUnknown(unittest.TestCase):
    """Arm 4: an INCOMPLETE walk -> UNKNOWN, never CLEAR."""

    def setUp(self):
        self._orig_attempts = collisioncheck.RETRY_ATTEMPTS
        self._orig_delay = collisioncheck.RETRY_BASE_DELAY
        collisioncheck.RETRY_ATTEMPTS = 1
        collisioncheck.RETRY_BASE_DELAY = 0
        self.addCleanup(setattr, collisioncheck, "RETRY_ATTEMPTS",
                        self._orig_attempts)
        self.addCleanup(setattr, collisioncheck, "RETRY_BASE_DELAY",
                        self._orig_delay)

    def test_emailbison_timeout_is_unknown(self):
        wire = _TimeoutWire(["/leads?search="])
        _install(wire)
        self.addCleanup(providers.reset_transport)

        result = collisioncheck.check_email_bison("somebody@acme.test")

        self.assertEqual(collisioncheck.UNKNOWN, result["verdict"])
        self.assertFalse(result["complete"])
        self.assertNotEqual(collisioncheck.CLEAR, result["verdict"])

    def test_heyreach_campaign_list_timeout_is_unknown(self):
        wire = _TimeoutWire(["/campaign/GetAll"])
        _install(wire)
        self.addCleanup(providers.reset_transport)

        result = collisioncheck.check_heyreach_company("acme.test")

        self.assertEqual(collisioncheck.UNKNOWN, result["verdict"])
        self.assertFalse(result["complete"])

    def test_heyreach_lead_page_timeout_mid_walk_is_unknown(self):
        """A timeout on the SECOND campaign's leads is UNKNOWN, not CLEAR."""
        wire = _TimeoutWire([])
        _install(wire)
        self.addCleanup(providers.reset_transport)

        call_count = {"n": 0}
        original_call = wire.fallback.__call__

        def timeout_on_second_campaign(method, url, headers, body=None,
                                       timeout=None):
            wire.calls.append({"method": method, "url": url, "body": body})
            if "/campaign/GetLeadsFromCampaign" in url:
                call_count["n"] += 1
                if call_count["n"] > 1:
                    raise HttpTimeout("simulated timeout on leads page 2")
            return original_call(method, url, headers, body, timeout)

        wire.fallback.on(
            "/campaign/GetAll",
            200,
            {"items": [_heyreach_campaign(1, "Camp A"),
                        _heyreach_campaign(2, "Camp B")],
             "totalCount": 2})
        wire.fallback.on(
            "/campaign/GetLeadsFromCampaign",
            200,
            {"items": [_heyreach_lead("https://linkedin.com/in/x",
                                     "OtherCorp")],
             "totalCount": 1})

        # Replace the wire's __call__ to inject the timeout.
        transport = timeout_on_second_campaign
        providers.set_transport(transport)

        result = collisioncheck.check_heyreach_company("acme.test")

        self.assertEqual(collisioncheck.UNKNOWN, result["verdict"])
        self.assertFalse(result["complete"])

    def test_combined_unknown_when_either_provider_unknown(self):
        wire = _TimeoutWire(["/leads?search="])
        wire.on(
            "/campaign/GetAll",
            200,
            {"items": [], "totalCount": 0})
        _install(wire)
        self.addCleanup(providers.reset_transport)

        result = collisioncheck.check(
            email="somebody@acme.test", company_domain="acme.test")

        self.assertEqual(collisioncheck.UNKNOWN, result["verdict"])


class TestNoWriteIsIssued(unittest.TestCase):
    """Arm 5: no write is issued. Booby-trap on the transport."""

    def setUp(self):
        self.requests = []
        self._orig_attempts = collisioncheck.RETRY_ATTEMPTS
        self._orig_delay = collisioncheck.RETRY_BASE_DELAY
        collisioncheck.RETRY_ATTEMPTS = 1
        collisioncheck.RETRY_BASE_DELAY = 0
        self.addCleanup(setattr, collisioncheck, "RETRY_ATTEMPTS",
                        self._orig_attempts)
        self.addCleanup(setattr, collisioncheck, "RETRY_BASE_DELAY",
                        self._orig_delay)

        def refuse_every_request(method, url, headers, body=None,
                                 timeout=None):
            self.requests.append((method, url))
            raise _BoobyTrap(
                "a provider request was made: %s %s" % (method, url))

        providers.set_transport(refuse_every_request)
        os.environ.setdefault("BISON_KEY", "test-key-not-real")
        os.environ.setdefault("HEYREACH_KEY", "test-key-not-real")
        self.addCleanup(providers.reset_transport)

    def test_the_booby_trap_actually_fires(self):
        """Every zero-write claim in this class rests on this one."""
        with self.assertRaises(_BoobyTrap):
            providers.request("GET", "http://example.invalid/armed",
                              headers={}, body=None, timeout=1)
        self.assertEqual([("GET", "http://example.invalid/armed")],
                         self.requests)
        self.requests.clear()

    def test_check_issues_no_writes_even_on_empty_input(self):
        """check() with no email and no domain makes no provider calls."""
        result = collisioncheck.check()
        self.assertEqual(collisioncheck.CLEAR, result["verdict"])
        self.assertEqual([], self.requests,
                         "a collision check with no inputs made provider "
                         "requests")

    def test_check_email_bison_refuses_invalid_email_without_request(self):
        result = collisioncheck.check_email_bison("")
        self.assertEqual(collisioncheck.UNKNOWN, result["verdict"])
        self.assertEqual([], self.requests,
                         "an invalid email triggered a provider request")


class TestHeyReachCompanyMatch(unittest.TestCase):
    """The company domain matches against lead companyName."""

    def setUp(self):
        self.wire = _Wire()
        _install(self.wire)
        self.addCleanup(providers.reset_transport)
        self._orig_attempts = collisioncheck.RETRY_ATTEMPTS
        collisioncheck.RETRY_ATTEMPTS = 1
        self.addCleanup(setattr, collisioncheck, "RETRY_ATTEMPTS",
                        self._orig_attempts)

    def test_domain_label_matches_company_name(self):
        self.wire.on(
            "/campaign/GetAll",
            200,
            {"items": [_heyreach_campaign(200, "Client Campaign")],
             "totalCount": 1})
        self.wire.on(
            "/campaign/GetLeadsFromCampaign",
            200,
            {"items": [
                _heyreach_lead("https://linkedin.com/in/jane",
                               "Acme Corporation"),
            ],
             "totalCount": 1})

        result = collisioncheck.check_heyreach_company("acme.com")

        self.assertEqual(collisioncheck.COLLISION, result["verdict"])
        self.assertEqual(1, len(result["collisions"]))
        self.assertEqual(200, result["collisions"][0]["campaign_id"])
        self.assertEqual("Client Campaign",
                         result["collisions"][0]["campaign_name"])
        self.assertEqual("Acme Corporation",
                         result["collisions"][0]["company_name"])

    def test_non_matching_company_is_clear(self):
        self.wire.on(
            "/campaign/GetAll",
            200,
            {"items": [_heyreach_campaign(200, "Campaign")],
             "totalCount": 1})
        self.wire.on(
            "/campaign/GetLeadsFromCampaign",
            200,
            {"items": [
                _heyreach_lead("https://linkedin.com/in/jane",
                               "TotallyDifferentCorp"),
            ],
             "totalCount": 1})

        result = collisioncheck.check_heyreach_company("acme.com")

        self.assertEqual(collisioncheck.CLEAR, result["verdict"])


class TestPaginationToExhaustion(unittest.TestCase):
    """Multiple pages of campaigns and leads are all walked."""

    def setUp(self):
        self.wire = _Wire()
        _install(self.wire)
        self.addCleanup(providers.reset_transport)
        self._orig_attempts = collisioncheck.RETRY_ATTEMPTS
        collisioncheck.RETRY_ATTEMPTS = 1
        self.addCleanup(setattr, collisioncheck, "RETRY_ATTEMPTS",
                        self._orig_attempts)

    def test_multiple_campaign_pages_are_walked(self):
        """Two pages of campaigns, both walked."""
        call_count = {"campaigns": 0}
        original_call = self.wire.__call__

        def counting_call(method, url, headers, body=None, timeout=None):
            if "/campaign/GetAll" in url:
                call_count["campaigns"] += 1
                if call_count["campaigns"] == 1:
                    return 200, json.dumps({
                        "items": [_heyreach_campaign(1, "Camp A")],
                        "totalCount": 2})
                else:
                    return 200, json.dumps({
                        "items": [_heyreach_campaign(2, "Camp B")],
                        "totalCount": 2})
            return original_call(method, url, headers, body, timeout)

        self.wire.on(
            "/campaign/GetLeadsFromCampaign",
            200,
            {"items": [], "totalCount": 0})

        providers.set_transport(counting_call)

        result = collisioncheck.check_heyreach_company("acme.test")

        self.assertEqual(collisioncheck.CLEAR, result["verdict"])
        self.assertTrue(result["complete"])
        self.assertEqual(2, result["campaigns_walked"])
        self.assertEqual(2, call_count["campaigns"])


if __name__ == "__main__":
    unittest.main()
