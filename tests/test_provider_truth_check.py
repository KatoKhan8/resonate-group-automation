#!/usr/bin/env python3
"""TASK-935: prove the canary person is in NO campaign, from the PROVIDERS.

Five test classes, each covering one acceptance criterion:

1. A person in one of our campaigns -> COLLISION naming it
2. A person in a CLIENT campaign -> COLLISION naming it
3. A person in neither, complete walk -> CLEAR
4. An INCOMPLETE walk (timeout, partial page) -> UNKNOWN, never CLEAR
5. No write is issued: assert on the transport, with the booby-trap pattern

All tests drive through the real entry point (`provider_truth_check.check`)
and stub the transport layer, not the inner functions. The seam was never
the risk; the wiring is.
"""
import os
import unittest
from unittest import mock

from src import providers
from src.providers import bison, heyreach, ProviderError, HttpTimeout
from src import provider_truth_check
from src.provider_truth_check import (
    CollisionCheckResult, check, check_emailbison, check_heyreach,
    CLEAR, COLLISION, UNKNOWN, CLIENT_BISON_CAMPAIGNS,
    CLIENT_HEYREACH_CAMPAIGN_NAME,
)


class AProviderRequestWasMade(AssertionError):
    """The transport was reached with a write. On a read-only check that
    is always a failure."""


# --------------------------------------------------------- helpers

def _bison_lead(email, campaign_id, status="in_sequence"):
    """A minimal EmailBison lead row for testing."""
    return {
        "id": 12345,
        "email": email,
        "status": "valid",
        "overall_stats": {"emails_sent": 3, "replies": 0, "opens": 1},
        "lead_campaign_data": [{
            "campaign_id": campaign_id,
            "status": status,
            "emails_sent": 3,
            "replies": 0,
            "opens": 1,
            "interested": 0,
        }],
        "created_at": "2026-09-01T00:00:00Z",
    }


def _bison_campaign_row(cid, name, status="active"):
    return {"id": cid, "name": name, "status": status,
            "created_at": "2026-08-01T00:00:00Z"}


def _heyreach_campaign(cid, name, status="InSequence"):
    return {"id": cid, "name": name, "status": status}


def _heyreach_lead(profile_url="https://linkedin.com/in/testperson",
                   company_name="BrightPath Solutions",
                   linkedin_id="123456"):
    """A minimal HeyReach lead row for testing."""
    return {
        "id": 99001,
        "linkedInUserProfile": {
            "profileUrl": profile_url,
            "linkedin_id": linkedin_id,
            "companyName": company_name,
        },
        "linkedInUserProfileId": 88001,
        "linkedInSenderId": 77001,
        "creationTime": "2026-09-01T00:00:00Z",
        "leadCampaignStatus": "InSequence",
        "leadConnectionStatus": "ConnectionSent",
        "leadMessageStatus": "None",
        "errorCode": None,
        "lastActionTime": "2026-09-15T00:00:00Z",
        "failedTime": None,
    }


def _url_path(url):
    import urllib.parse
    return urllib.parse.urlparse(url).path


def _url_host(url):
    import urllib.parse
    return urllib.parse.urlparse(url).hostname or ""


def _url_params(url):
    import urllib.parse
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)


def _stub_bison_transport(leads_by_domain=None, campaigns=None):
    """Stub the EmailBison transport to return canned data."""
    leads_by_domain = leads_by_domain or {}
    campaigns = campaigns or []

    def handler(method, url, headers, body, timeout):
        path = _url_path(url)
        # Campaign listing: GET /campaigns?page=N
        if path.endswith("/campaigns"):
            total = len(campaigns)
            return 200, {
                "data": campaigns,
                "meta": {"total": total, "last_page": 1, "per_page": 100},
            }
        # Lead search: GET /leads?search=TERM&page=N
        if "/leads" in path:
            params = _url_params(url)
            term = params.get("search", [""])[0].lower()
            matching = []
            for domain_label, leads in leads_by_domain.items():
                if term == domain_label.lower():
                    matching.extend(leads)
            total = len(matching)
            return 200, {
                "data": matching,
                "meta": {"total": total, "last_page": 1, "per_page": 15},
            }
        # /users for workspace check
        if path.endswith("/users"):
            return 200, {"data": {"workspace": {"id": 10, "name": "Productive"}}}
        return 200, {}

    return handler


def _parse_body(body):
    """Parse a request body that may be a dict, str, bytes, or None."""
    if body is None:
        return {}
    if isinstance(body, dict):
        return body
    if isinstance(body, (bytes, bytearray)):
        import json
        return json.loads(body.decode("utf-8"))
    import json
    return json.loads(body)


def _stub_heyreach_transport(campaigns=None, leads_by_campaign=None):
    """Stub the HeyReach transport to return canned data."""
    campaigns = campaigns or []
    leads_by_campaign = leads_by_campaign or {}

    def handler(method, url, headers, body, timeout):
        path = _url_path(url)
        body_data = _parse_body(body)

        if path == "/api/public/campaign/GetAll":
            offset = body_data.get("offset", 0)
            limit = body_data.get("limit", 100)
            page = campaigns[offset:offset + limit]
            return 200, {"items": page, "totalCount": len(campaigns)}

        if path == "/api/public/campaign/GetLeadsFromCampaign":
            cid = body_data.get("campaignId")
            leads = leads_by_campaign.get(cid, [])
            offset = body_data.get("offset", 0)
            limit = body_data.get("limit", 100)
            page = leads[offset:offset + limit]
            return 200, {"items": page, "totalCount": len(leads)}

        if path == "/api/public/auth/CheckApiKey":
            return 200, {"isValid": True}

        return 200, {}

    return handler


def _combined_transport(bison_handler, heyreach_handler):
    """Route requests to the right handler based on host."""
    def handler(method, url, headers, body, timeout):
        host = _url_host(url)
        if "heyreach" in host:
            return heyreach_handler(method, url, headers, body, timeout)
        return bison_handler(method, url, headers, body, timeout)
    return handler


# The fake credential names, never values.
_FAKE_ENV = {"BISON_KEY": "test-bison-key-not-real",
             "HEYREACH_KEY": "test-heyreach-key-not-real"}


class _ProviderTransportTest(unittest.TestCase):
    """Base class that installs a fake credential env and a transport stub.

    Subclasses set `self._bison_handler` and `self._heyreach_handler` in
    setUp, then call `_install()`. The transport routes by host.
    """

    _bison_handler = None
    _heyreach_handler = None

    def _install(self):
        env = mock.patch.dict(os.environ, _FAKE_ENV)
        env.start()
        self.addCleanup(env.stop)

        bison_h = self._bison_handler or _stub_bison_transport()
        heyreach_h = self._heyreach_handler or _stub_heyreach_transport()
        providers.set_transport(_combined_transport(bison_h, heyreach_h))
        self.addCleanup(providers.reset_transport)


# --------------------------------------------------------- 1. Our campaigns

class PersonInOurCampaign(_ProviderTransportTest):
    """A person in one of our campaigns -> COLLISION naming it."""

    def setUp(self):
        leads = {"brightpath": [
            _bison_lead("alex@brightpath.test", 491),
        ]}
        campaigns = [_bison_campaign_row(491, "RESONATE [productive/491]")]
        self._bison_handler = _stub_bison_transport(
            leads_by_domain=leads, campaigns=campaigns)
        self._heyreach_handler = _stub_heyreach_transport()
        self._install()

    def test_emailbison_collision_names_the_campaign(self):
        result = check_emailbison(
            "alex@brightpath.test", "brightpath.test",
            expect_workspace=10)
        self.assertEqual(result.disposition, COLLISION)
        self.assertEqual(result.provider, "emailbison")
        self.assertEqual(result.campaign_id, 491)
        self.assertEqual(result.matched_on, "email")
        self.assertTrue(result.complete)


# --------------------------------------------------------- 2. Client campaigns

class PersonInClientCampaign(_ProviderTransportTest):
    """A person in a CLIENT campaign -> COLLISION naming it."""

    def test_emailbison_client_campaign_327(self):
        """EmailBison campaign 327 is the client's. A person there is a
        collision."""
        leads = {"acme": [
            _bison_lead("vendor@acme.test", 327, status="in_sequence"),
        ]}
        campaigns = [_bison_campaign_row(327, "Q3 Outreach Wave 1")]
        self._bison_handler = _stub_bison_transport(
            leads_by_domain=leads, campaigns=campaigns)
        self._heyreach_handler = _stub_heyreach_transport()
        self._install()

        result = check_emailbison(
            "vendor@acme.test", "acme.test",
            expect_workspace=10)
        self.assertEqual(result.disposition, COLLISION)
        self.assertEqual(result.campaign_id, 327)
        self.assertEqual(result.campaign_name, "Q3 Outreach Wave 1")
        self.assertEqual(result.matched_on, "email")

    def test_heyreach_client_campaign_fixed_productive(self):
        """HeyReach campaign named 'FIXED - PRODUCTIVE' is the client's.
        A company match there is a collision."""
        campaigns = [_heyreach_campaign(50001, "FIXED - PRODUCTIVE")]
        leads = {50001: [
            _heyreach_lead(company_name="northbeam.test"),
        ]}
        self._bison_handler = _stub_bison_transport()
        self._heyreach_handler = _stub_heyreach_transport(
            campaigns=campaigns, leads_by_campaign=leads)
        self._install()

        result = check_heyreach(
            "", "northbeam.test", _sleep=lambda x: None)
        self.assertEqual(result.disposition, COLLISION)
        self.assertEqual(result.provider, "heyreach")
        self.assertEqual(result.campaign_id, 50001)
        self.assertEqual(result.campaign_name, "FIXED - PRODUCTIVE")
        self.assertEqual(result.matched_on, "domain")


# --------------------------------------------------------- 3. Clear

class PersonInNeitherCompleteWalk(_ProviderTransportTest):
    """A person in neither estate, complete walk -> CLEAR."""

    def test_both_providers_clear(self):
        """Both providers return empty results for this person/domain."""
        self._bison_handler = _stub_bison_transport(
            leads_by_domain={}, campaigns=[])
        self._heyreach_handler = _stub_heyreach_transport(
            campaigns=[], leads_by_campaign={})
        self._install()

        result = check("nobody@clean.test", "clean.test",
                       bison_workspace=10, _sleep=lambda x: None)
        self.assertEqual(result.disposition, CLEAR)
        self.assertTrue(result.complete)

    def test_emailbison_clear_alone(self):
        """EmailBison alone returns CLEAR for a domain with no leads."""
        self._bison_handler = _stub_bison_transport(
            leads_by_domain={}, campaigns=[])
        self._heyreach_handler = _stub_heyreach_transport()
        self._install()

        result = check_emailbison(
            "nobody@clean.test", "clean.test", expect_workspace=10)
        self.assertEqual(result.disposition, CLEAR)
        self.assertTrue(result.complete)

    def test_heyreach_clear_alone(self):
        """HeyReach alone returns CLEAR when no campaign has a match."""
        campaigns = [_heyreach_campaign(60001, "Other Campaign")]
        leads = {60001: [
            _heyreach_lead(company_name="Different Corp"),
        ]}
        self._bison_handler = _stub_bison_transport()
        self._heyreach_handler = _stub_heyreach_transport(
            campaigns=campaigns, leads_by_campaign=leads)
        self._install()

        result = check_heyreach(
            "nobody@clean.test", "clean.test",
            _sleep=lambda x: None)
        self.assertEqual(result.disposition, CLEAR)
        self.assertTrue(result.complete)


# --------------------------------------------------------- 4. Incomplete walk

class IncompleteWalkIsUnknown(unittest.TestCase):
    """An INCOMPLETE walk (timeout, partial page) -> UNKNOWN, never CLEAR."""

    def setUp(self):
        self._env = mock.patch.dict(os.environ, _FAKE_ENV)
        self._env.start()

    def tearDown(self):
        self._env.stop()
        providers.reset_transport()

    def test_heyreach_timeout_is_unknown_not_clear(self):
        """HeyReach campaign/GetAll times out. The result is UNKNOWN,
        not CLEAR."""
        def timeout_handler(method, url, headers, body, timeout):
            raise HttpTimeout("heyreach campaign/GetAll: timed out at 25s")

        providers.set_transport(timeout_handler)

        result = check_heyreach(
            "test@example.test", "example.test",
            retry_delays=(0.001, 0.001),
            _sleep=lambda x: None)
        self.assertEqual(result.disposition, UNKNOWN)
        self.assertFalse(result.complete)
        self.assertIn("timed out", (result.reason or "").lower())
        self.assertEqual(result.provider, "heyreach")

    def test_emailbison_partial_page_is_unknown(self):
        """EmailBison returns data without a readable last_page. The result
        is UNKNOWN, not CLEAR."""
        def bad_meta_handler(method, url, headers, body, timeout):
            path = _url_path(url)
            if "/leads" in path:
                return 200, {
                    "data": [_bison_lead("x@test.com", 491)],
                    "meta": {"total": 100},
                }
            if path.endswith("/users"):
                return 200, {"data": {"workspace": {"id": 10, "name": "P"}}}
            if path.endswith("/campaigns"):
                return 200, {"data": [], "meta": {"total": 0, "last_page": 1}}
            return 200, {}

        providers.set_transport(bad_meta_handler)

        result = check_emailbison(
            "somebody@test.com", "test.com", expect_workspace=10)
        self.assertEqual(result.disposition, UNKNOWN)
        self.assertFalse(result.complete)

    def test_heyreach_partial_lead_walk_is_unknown(self):
        """HeyReach campaign listing succeeds but a campaign's lead listing
        returns fewer rows than totalCount claims. UNKNOWN, not CLEAR."""
        campaigns = [_heyreach_campaign(70001, "Big Campaign")]
        # Create the leads ONCE so the stub slices a fixed list.
        all_leads = [_heyreach_lead() for _ in range(10)]

        def partial_handler(method, url, headers, body, timeout):
            path = _url_path(url)
            body_data = _parse_body(body)

            if path == "/api/public/campaign/GetAll":
                return 200, {"items": campaigns, "totalCount": 1}
            if path == "/api/public/campaign/GetLeadsFromCampaign":
                offset = body_data.get("offset", 0)
                limit = body_data.get("limit", 100)
                page = all_leads[offset:offset + limit]
                return 200, {"items": page, "totalCount": 100}
            return 200, {}

        providers.set_transport(partial_handler)

        result = check_heyreach(
            "", "nomatch.test", _sleep=lambda x: None)
        self.assertEqual(result.disposition, UNKNOWN)
        self.assertFalse(result.complete)
        self.assertEqual(result.provider, "heyreach")

    def test_emailbison_listing_failure_does_not_block_lead_check(self):
        """When the EmailBison campaign listing fails, the campaign index
        is None but the lead search still works. A CLEAR from the lead
        search is still valid."""
        def failing_handler(method, url, headers, body, timeout):
            path = _url_path(url)
            if path.endswith("/campaigns"):
                return 500, {"error": "internal server error"}
            if "/leads" in path:
                return 200, {
                    "data": [],
                    "meta": {"total": 0, "last_page": 1},
                }
            if path.endswith("/users"):
                return 200, {"data": {"workspace": {"id": 10, "name": "P"}}}
            return 200, {}

        providers.set_transport(failing_handler)

        result = check_emailbison(
            "nobody@clean.test", "clean.test", expect_workspace=10)
        self.assertEqual(result.disposition, CLEAR)


# --------------------------------------------------------- 5. No write issued

class NoWriteIsIssued(_ProviderTransportTest):
    """The booby-trap pattern: assert on the transport that no write is
    issued."""

    def setUp(self):
        self.writes = []
        self.all_requests = []

        bison_h = _stub_bison_transport(leads_by_domain={}, campaigns=[])
        heyreach_h = _stub_heyreach_transport(campaigns=[], leads_by_campaign={})

        def trap(method, url, headers, body, timeout):
            from src.providers import normalise_method
            verb = normalise_method(method)
            self.all_requests.append((verb, url))
            if verb in ("PUT", "PATCH", "DELETE"):
                self.writes.append((verb, url))
                raise AProviderRequestWasMade(
                    f"write issued: {verb} {url}")
            if verb == "POST":
                path = _url_path(url)
                # HeyReach POSTs that are reads have paths like
                # /api/public/campaign/GetAll. Strip the base prefix
                # to match against READ_ROUTES_ALL.
                route_path = path
                if path.startswith("/api/public"):
                    route_path = path[len("/api/public"):]
                if route_path not in heyreach.READ_ROUTES_ALL:
                    self.writes.append((verb, url))
                    raise AProviderRequestWasMade(
                        f"write issued: {verb} {url}")
            host = _url_host(url)
            if "heyreach" in host:
                return heyreach_h(method, url, headers, body, timeout)
            return bison_h(method, url, headers, body, timeout)

        self._bison_handler = None
        self._heyreach_handler = None

        env = mock.patch.dict(os.environ, _FAKE_ENV)
        env.start()
        self.addCleanup(env.stop)
        providers.set_transport(trap)
        self.addCleanup(providers.reset_transport)

    def test_the_booby_trap_actually_fires(self):
        """Every zero-write claim in this class rests on this one."""
        with self.assertRaises(AProviderRequestWasMade):
            providers.request("POST", "https://api.heyreach.io/api/public/"
                              "campaign/AddLeadsToCampaignV2",
                              headers={}, body="{}", timeout=1)
        self.assertEqual(1, len(self.writes))

    def test_check_issues_no_write(self):
        """The full check runs to completion and no write reaches the
        transport."""
        result = check("nobody@clean.test", "clean.test",
                       bison_workspace=10, _sleep=lambda x: None)
        self.assertEqual([], self.writes,
                         "a read-only collision check issued a write")
        self.assertEqual(result.disposition, CLEAR)

    def test_check_emailbison_issues_no_write(self):
        """check_emailbison alone issues no write."""
        result = check_emailbison(
            "nobody@clean.test", "clean.test", expect_workspace=10)
        self.assertEqual([], self.writes)
        self.assertEqual(result.disposition, CLEAR)

    def test_check_heyreach_issues_no_write(self):
        """check_heyreach alone issues no write."""
        result = check_heyreach(
            "nobody@clean.test", "clean.test",
            _sleep=lambda x: None)
        self.assertEqual([], self.writes)
        self.assertEqual(result.disposition, CLEAR)


# --------------------------------------------------------- edge cases

class EdgeCases(unittest.TestCase):
    """Edge cases and boundary conditions."""

    def test_no_email_no_domain_is_unknown(self):
        """An empty check with no email and no domain is UNKNOWN."""
        result = check("", "")
        self.assertEqual(result.disposition, UNKNOWN)
        self.assertFalse(result.complete)

    def test_collision_result_equality(self):
        """CollisionCheckResult supports equality comparison."""
        a = CollisionCheckResult(COLLISION, provider="emailbison",
                                 campaign_id=491)
        b = CollisionCheckResult(COLLISION, provider="emailbison",
                                 campaign_id=491)
        self.assertEqual(a, b)

    def test_collision_result_repr(self):
        """CollisionCheckResult has a useful repr."""
        r = CollisionCheckResult(COLLISION, provider="emailbison",
                                 campaign_id=491, campaign_name="Test")
        text = repr(r)
        self.assertIn("collision", text)
        self.assertIn("emailbison", text)
        self.assertIn("491", text)

    def test_client_bison_campaigns_are_named(self):
        """The client's EmailBison campaign ids are documented."""
        self.assertIn(327, CLIENT_BISON_CAMPAIGNS)
        self.assertIn(328, CLIENT_BISON_CAMPAIGNS)
        self.assertIn(352, CLIENT_BISON_CAMPAIGNS)
        self.assertIn(418, CLIENT_BISON_CAMPAIGNS)

    def test_client_heyreach_campaign_name_is_documented(self):
        """The client's HeyReach campaign name is documented."""
        self.assertEqual(CLIENT_HEYREACH_CAMPAIGN_NAME, "FIXED - PRODUCTIVE")


if __name__ == "__main__":
    unittest.main()
