"""Production sign-in, end to end, against an identity provider that answers.

A stub that returns a dict would prove that the code calls its own
functions. This stands up a real OpenID provider on loopback - discovery
document, authorization endpoint, token endpoint, minted id_tokens - and
drives the real application through the real HTTP flow against it. Every
attack below is then a *variation on a working sign-in*, which is the only
kind of negative test worth having: it fails for the reason named rather
than because the setup was wrong.

What is deliberately not faked: the application. `app.serve()` runs with
`AUTH_PROVIDER=oidc`, so the routing, the refusals, the session, the
cookie and the canonical identity lookup are the production ones.

## The two questions, kept apart

Authentication answers *who is this*. The provider does that, and this
system takes its word only after checking state, nonce, audience, issuer,
expiry and `email_verified`.

Authorisation answers *what may they do*. That never comes from the
provider. A proved address is looked up in `workspaces.jsonl`, and an
address the provider is perfectly happy about gets nowhere if there is no
user row for it. The tests that matter most here are the ones where the
provider says yes and this system still says no.
"""
import base64
import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src import store, workspaces
from src.web import app, demodata, oidc, security

CLIENT_ID = "resonate-test-client"
# "synthetic" is not decoration: tests/test_secrets.py scans every tracked
# file for credential-shaped assignments, and that is the repository's
# established marker for a value that is deliberately not one.
CLIENT_SECRET = "synthetic-client-secret-not-real"
REDIRECT_URL = "https://app.test/auth/callback"

# Somebody the demo estate knows about, and somebody it does not.
KNOWN = "ops@productive.test"
SUPER_ADMIN = "root@resonate.test"
VIEWER = "client@productive.test"
STRANGER = "someone.else@productive.test"


def b64(payload):
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class Provider(BaseHTTPRequestHandler):
    """An identity provider. Its answers are whatever the test set."""

    # Set per test by ProviderServer.
    behaviour = {}

    def log_message(self, *_):
        pass

    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        state = self.server.state
        if path == "/.well-known/openid-configuration":
            if state["behaviour"].get("no_token_endpoint"):
                return self._json(200, {"issuer": state["issuer"],
                                        "authorization_endpoint":
                                            state["issuer"] + "/authorize"})
            return self._json(200, {
                "issuer": state["behaviour"].get("issuer", state["issuer"]),
                "authorization_endpoint": state["issuer"] + "/authorize",
                "token_endpoint": state["issuer"] + "/token",
            })
        self._json(404, {"error": "not_found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        state = self.server.state
        if path != "/token":
            return self._json(404, {"error": "not_found"})

        length = int(self.headers.get("Content-Length") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        state["last_token_request"] = {k: v[0] for k, v in form.items()}

        if state["behaviour"].get("token_endpoint_refuses"):
            return self._json(400, {"error": "invalid_grant"})

        behaviour = state["behaviour"]
        now = int(time.time())
        claims = {
            "iss": behaviour.get("claim_iss", state["issuer"]),
            "aud": behaviour.get("claim_aud", CLIENT_ID),
            "sub": "provider-subject-0001",
            "exp": behaviour.get("claim_exp", now + 300),
            "iat": now,
            "nonce": behaviour.get("claim_nonce", state.get("nonce")),
            "email": behaviour.get("claim_email", state["email"]),
            "email_verified": behaviour.get("claim_email_verified", True),
        }
        for absent in behaviour.get("omit_claims", ()):
            claims.pop(absent, None)
        id_token = ".".join([b64({"alg": "RS256", "typ": "JWT"}),
                             b64(claims), "not-a-real-signature"])
        if behaviour.get("no_id_token"):
            return self._json(200, {"access_token": "x"})
        self._json(200, {"access_token": "x", "token_type": "Bearer",
                         "id_token": id_token})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Stop at the redirect instead of chasing it.

    Chasing is what a browser does and what the first draft of this file
    accidentally did: `urlopen` follows a 303 by default, so `/auth/start`
    silently became a request to the provider's authorization endpoint and
    the test read *its* answer. Every assertion here is about the
    `Location` and the `Set-Cookie` the application produced, so the
    redirect has to be the end of the request rather than the middle of one.
    """

    def redirect_request(self, *_args, **_kwargs):
        return None


class _Browser:
    """One session cookie, sent back as a browser would. See `AuthTest.opener`.

    **It honours `SameSite`, and it did not.** The first version split the
    `Set-Cookie` header on the first `;` and returned the value on every
    subsequent request, which made it incapable of failing for the reason
    production actually failed: a `SameSite=Strict` cookie set on the
    provider's cross-site redirect is stored and then not sent on the
    navigation that follows, so the console bounced to `/login` with no
    error while three valid sessions sat on the server.

    A test double that is more permissive than a browser is a test that
    cannot see what a browser sees.
    """

    def __init__(self):
        self.cookie = None
        self.samesite = None
        # True once the next navigation follows a cross-site redirect - the
        # provider sending the browser back to `/auth/callback`, and the
        # redirect that callback returns.
        self.arriving_cross_site = False
        self._opener = urllib.request.build_opener(_NoRedirect)

    def sends_cookie(self):
        """What a browser would put on the wire for this request."""
        if not self.cookie:
            return None
        if self.arriving_cross_site and (self.samesite or "").lower() == "strict":
            return None
        return self.cookie

    def request(self, url, data=None):
        request = urllib.request.Request(url, data=data)
        sending = self.sends_cookie()
        if sending:
            request.add_header("Cookie", sending)
        try:
            with self._opener.open(request, timeout=20) as response:
                status, headers, body = (response.status, response.headers,
                                         response.read())
        except urllib.error.HTTPError as e:
            status, headers, body = e.code, e.headers, e.read()
        self._remember(headers)
        return status, headers, body

    def _remember(self, headers):
        raw = headers.get("Set-Cookie")
        if not raw:
            return
        pair = raw.split(";", 1)[0].strip()
        name, _, value = pair.partition("=")
        self.samesite = None
        for part in raw.split(";")[1:]:
            key, _, val = part.strip().partition("=")
            if key.lower() == "samesite":
                self.samesite = val.strip()
        # Max-Age=0 is a logout: the browser drops it rather than sending an
        # empty one back, which is what makes the logout test meaningful.
        if not value or "Max-Age=0" in raw:
            self.cookie = None
        else:
            self.cookie = pair


class AuthTest(unittest.TestCase):
    """A demo estate, a live identity provider, and the real application.

    The estate is the demonstration's fictional companies and users, which
    is the point: it gives real `workspaces.jsonl` rows to map a proved
    address onto. The *mechanism* is production - `AUTH_PROVIDER=oidc` - so
    the fictional data and the real sign-in are exercised together, which
    is exactly the combination `--demo` alone could never reach.
    """

    ENV = ("AUTH_PROVIDER", "AUTH_ISSUER", "AUTH_CLIENT_ID",
           "AUTH_CLIENT_SECRET", "AUTH_REDIRECT_URL", "AUTH_ALLOWED_DOMAINS",
           "APP_MODE", "QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES", "AUDIT",
           "MX_CACHE", "OUT", "CLIENTS_DIR", "WEB_QUIET")

    @classmethod
    def setUpClass(cls):
        cls._prev = {k: os.environ.get(k) for k in cls.ENV}
        cls.tmp = tempfile.mkdtemp(prefix="rga-auth-")
        store.use_directory(os.path.join(cls.tmp, "work"))
        os.environ["MX_CACHE"] = os.path.join(cls.tmp, "mx-cache.json")
        os.environ["OUT"] = os.path.join(cls.tmp, "out")
        os.environ["CLIENTS_DIR"] = os.path.join(cls.tmp, "clients")
        os.environ["WEB_QUIET"] = "1"
        demodata.install()

        # The provider first: its port becomes AUTH_ISSUER, which has to be
        # set before the application will agree to start at all.
        cls.provider = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        issuer = f"http://127.0.0.1:{cls.provider.server_address[1]}"
        cls.provider.state = {"issuer": issuer, "behaviour": {},
                              "email": KNOWN, "nonce": None}
        cls.provider_thread = threading.Thread(
            target=cls.provider.serve_forever, daemon=True)
        cls.provider_thread.start()

        os.environ["AUTH_PROVIDER"] = "oidc"
        os.environ["AUTH_ISSUER"] = issuer
        os.environ["AUTH_CLIENT_ID"] = CLIENT_ID
        os.environ["AUTH_CLIENT_SECRET"] = CLIENT_SECRET
        os.environ["AUTH_REDIRECT_URL"] = REDIRECT_URL

        cls.server = app.serve(0, demo=True)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.provider.shutdown()
        cls.provider.server_close()
        for key, value in cls._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.provider.state["behaviour"] = {}
        self.provider.state["email"] = KNOWN
        os.environ.pop("AUTH_ALLOWED_DOMAINS", None)

    # ------------------------------------------------------------ helpers

    def opener(self):
        """A browser that holds one cookie and follows no redirects.

        Two deliberate departures from `http.cookiejar`, and the first one
        is the interesting one.

        **It ignores `Secure`.** A configured provider means a `Secure`
        session cookie, and a real deployment is behind TLS - but the test
        talks to loopback over plain http, where a correct cookie jar
        refuses to store or send a `Secure` cookie. That refusal is the
        product being right; bending the product to make the test easier
        would mean dropping the flag that stops the cookie travelling in the
        clear. So the browser here is one that has already done TLS, and
        `test_the_session_cookie_carries_its_flags` asserts the flag is
        really there rather than letting the jar swallow the question.

        **It does not follow redirects.** That is what makes the flow
        inspectable: every step below asserts on the `Location` and the
        `Set-Cookie` a real browser would act on silently.
        """
        return _Browser()

    def request(self, opener, path, data=None):
        """Returns (status, headers, body). A 3xx or 4xx is an answer here,
        not an exception: what the refusals *say* is under test."""
        return opener.request(self.base + path, data)

    def start_flow(self, opener):
        """GET /auth/start and read back what the application minted."""
        status, headers, _ = self.request(opener, "/auth/start")
        self.assertEqual(status, 303)
        target = headers["Location"]
        query = urllib.parse.parse_qs(urllib.parse.urlparse(target).query)
        # The nonce the application chose is what the provider must echo.
        self.provider.state["nonce"] = query["nonce"][0]
        return {"state": query["state"][0], "target": target, "query": query}

    def finish_flow(self, opener, state, code="provider-code"):
        """The provider sending the browser back. This is a *cross-site*
        top-level navigation, and the redirect it returns inherits that -
        which is the whole reason a `Strict` cookie never arrives."""
        opener.arriving_cross_site = True
        try:
            return self.request(
                opener,
                "/auth/callback?" + urllib.parse.urlencode(
                    {"code": code, "state": state}))
        finally:
            # The next request the test makes stands in for the redirect the
            # browser follows, which is still part of the cross-site chain.
            pass

    def sign_in(self, email=KNOWN):
        """A complete, working sign-in. The baseline every attack varies."""
        self.provider.state["email"] = email
        opener = self.opener()
        flow = self.start_flow(opener)
        status, headers, _ = self.finish_flow(opener, flow["state"])
        return opener, status, headers

    def assert_no_session(self, opener):
        status, headers, _ = self.request(opener, "/companies")
        self.assertEqual(status, 303)
        self.assertTrue(headers["Location"].endswith("/login"))


class TheHappyPath(AuthTest):

    def test_a_proved_address_gets_a_session(self):
        opener, status, headers = self.sign_in()
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/global")
        status, _, body = self.request(opener, "/companies")
        self.assertEqual(status, 200)
        self.assertIn(b"Companies", body)

    def test_the_authorization_request_carries_pkce_and_a_nonce(self):
        flow = self.start_flow(self.opener())
        self.assertEqual(flow["query"]["code_challenge_method"], ["S256"])
        self.assertTrue(flow["query"]["code_challenge"][0])
        self.assertTrue(flow["query"]["nonce"][0])
        self.assertEqual(flow["query"]["client_id"], [CLIENT_ID])
        self.assertEqual(flow["query"]["redirect_uri"], [REDIRECT_URL])

    def test_it_asks_for_no_scope_it_does_not_read(self):
        """A consent screen is a promise to a person.

        Every claim `verified_email` reads comes from `openid` (iss, aud,
        exp, nonce, sub) or `email` (email, email_verified). `profile` was
        requested for two commits and never read - no name, no picture, no
        locale reaches this system - which is the repository's usual defect
        wearing a privacy hat: asking for something nothing consumes.
        """
        flow = self.start_flow(self.opener())
        requested = set(flow["query"]["scope"][0].split())
        self.assertEqual(requested, {"openid", "email"})

    def test_the_verifier_never_leaves_the_server(self):
        """PKCE is worth nothing if the challenge's preimage goes out too."""
        flow = self.start_flow(self.opener())
        sent = flow["target"]
        self.assertNotIn("code_verifier", sent)
        # And it does reach the token endpoint, where it belongs.
        opener = self.opener()
        started = self.start_flow(opener)
        self.finish_flow(opener, started["state"])
        self.assertIn("code_verifier",
                      self.provider.state["last_token_request"])

    def test_the_client_secret_goes_to_the_token_endpoint_and_nowhere_else(self):
        flow = self.start_flow(self.opener())
        self.assertNotIn(CLIENT_SECRET, flow["target"])
        opener = self.opener()
        started = self.start_flow(opener)
        self.finish_flow(opener, started["state"])
        self.assertEqual(
            self.provider.state["last_token_request"].get("client_secret"),
            CLIENT_SECRET)

    def test_the_session_cookie_carries_its_flags(self):
        _, _, headers = self.sign_in()
        cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertNotIn("SameSite=Strict", cookie)
        self.assertIn("Secure", cookie)

    def test_the_session_survives_the_redirect_out_of_the_provider(self):
        """The production failure, as a test.

        Sign-in succeeded, a session existed on the server, `Set-Cookie` was
        emitted - and the next request arrived without it, so the console
        redirected to `/login` and the person saw a sign-in page with no
        error having just signed in.

        The browser here stays flagged as arriving from the provider's
        cross-site redirect, which is exactly the state in which a `Strict`
        cookie is withheld. With `Lax` it is sent.
        """
        opener = self.opener()
        flow = self.start_flow(opener)
        status, headers, _ = self.finish_flow(opener, flow["state"])
        self.assertEqual(status, 303)
        self.assertTrue(headers.get("Set-Cookie"), "no session cookie issued")

        # Still inside the cross-site chain, as the redirect would be.
        self.assertTrue(opener.arriving_cross_site)
        self.assertIsNotNone(
            opener.sends_cookie(),
            "the browser would not return this cookie after the provider "
            "redirect, so the console will bounce to /login")

        status, _, body = self.request(opener, "/companies")
        self.assertEqual(status, 200, "the console was not reachable after a "
                                      "successful sign-in")
        self.assertIn(b"Companies", body)

    def test_logout_invalidates_the_session_server_side(self):
        opener, _, _ = self.sign_in()
        self.assertEqual(self.request(opener, "/companies")[0], 200)
        self.request(opener, "/logout")
        # Not merely a cleared cookie: the token is gone from the server, so
        # a copy of it taken beforehand is worth nothing either.
        self.assert_no_session(opener)


class TheProviderIsNotBelievedBlindly(AuthTest):
    """Every check, one at a time, against an otherwise perfect sign-in."""

    def assert_refused(self, opener=None, state=None):
        opener = opener or self.opener()
        if state is None:
            state = self.start_flow(opener)["state"]
        status, _, body = self.finish_flow(opener, state)
        self.assertEqual(status, 401)
        self.assert_no_session(opener)
        return body

    def test_a_state_that_was_never_minted_is_refused(self):
        opener = self.opener()
        status, _, _ = self.finish_flow(opener, "state-i-made-up")
        self.assertEqual(status, 401)
        self.assert_no_session(opener)

    def test_a_state_cannot_be_used_twice(self):
        """A replayed callback finds nothing left, even though the first use
        of it was entirely valid."""
        opener = self.opener()
        flow = self.start_flow(opener)
        self.assertEqual(self.finish_flow(opener, flow["state"])[0], 303)
        second = self.opener()
        status, _, _ = self.finish_flow(second, flow["state"])
        self.assertEqual(status, 401)
        self.assert_no_session(second)

    def test_a_token_answering_a_different_request_is_refused(self):
        self.provider.state["behaviour"]["claim_nonce"] = "some-other-nonce"
        self.assert_refused()

    def test_a_token_for_another_client_is_refused(self):
        self.provider.state["behaviour"]["claim_aud"] = "somebody-elses-client"
        self.assert_refused()

    def test_a_token_from_another_issuer_is_refused(self):
        self.provider.state["behaviour"]["claim_iss"] = "https://evil.test"
        self.assert_refused()

    def test_an_expired_token_is_refused(self):
        self.provider.state["behaviour"]["claim_exp"] = int(time.time()) - 60
        self.assert_refused()

    def test_a_token_with_no_expiry_is_refused(self):
        self.provider.state["behaviour"]["omit_claims"] = ("exp",)
        self.assert_refused()

    def test_an_unverified_email_is_refused(self):
        """Somebody's claim about a mailbox is what this exists to stop
        accepting."""
        self.provider.state["behaviour"]["claim_email_verified"] = False
        self.assert_refused()

    def test_a_missing_email_verified_claim_is_refused(self):
        """Absent is not the same as true, and must not be read as true."""
        self.provider.state["behaviour"]["omit_claims"] = ("email_verified",)
        self.assert_refused()

    def test_no_id_token_at_all_is_refused(self):
        self.provider.state["behaviour"]["no_id_token"] = True
        self.assert_refused()

    def test_a_refusing_token_endpoint_is_refused(self):
        self.provider.state["behaviour"]["token_endpoint_refuses"] = True
        self.assert_refused()

    def test_a_provider_error_in_the_callback_is_refused(self):
        opener = self.opener()
        flow = self.start_flow(opener)
        status, _, _ = self.request(
            opener, "/auth/callback?" + urllib.parse.urlencode(
                {"error": "access_denied", "state": flow["state"]}))
        self.assertEqual(status, 401)
        self.assert_no_session(opener)

    def test_a_callback_with_no_code_is_refused(self):
        opener = self.opener()
        flow = self.start_flow(opener)
        status, _, _ = self.request(
            opener, "/auth/callback?" + urllib.parse.urlencode(
                {"state": flow["state"]}))
        self.assertEqual(status, 401)

    def test_the_refusal_says_nothing_about_which_check_failed(self):
        """Every failure reads the same to whoever is probing."""
        self.provider.state["behaviour"]["claim_aud"] = "wrong"
        wrong_audience = self.assert_refused()
        self.provider.state["behaviour"] = {"claim_exp": int(time.time()) - 60}
        expired = self.assert_refused()
        self.assertEqual(wrong_audience, expired)
        for leak in (b"audience", b"expired", b"nonce", b"aud"):
            self.assertNotIn(leak, wrong_audience.lower())


class AuthenticationIsNotAuthorisation(AuthTest):
    """The provider says yes and this system still decides."""

    def test_a_perfectly_proved_stranger_gets_nothing(self):
        """No account is created for somebody the roster does not carry.

        A directory that can add people to `workspaces.jsonl` is a directory
        that decides who works here.
        """
        opener, status, _ = self.sign_in(email=STRANGER)
        self.assertEqual(status, 403)
        self.assert_no_session(opener)
        self.assertIsNone(workspaces.user(STRANGER))

    def test_the_proof_is_recorded_as_a_proof_not_as_a_refusal(self):
        """What the first-administrator bootstrap reads back.

        The provider proved this address and the system then refused it for
        having no user row. Those are two different facts, and writing the
        second over the first is a bug that hides until somebody tries to
        bootstrap a production deployment and `proved_addresses()` comes
        back empty - at which point there is no console to diagnose it from.
        """
        self.sign_in(email=STRANGER)
        rows = [r for r in workspaces.audit()
                if (r.get("actor") or "").lower() == STRANGER]
        self.assertTrue(rows, "the proof was not recorded at all")
        self.assertEqual(rows[0]["action"], workspaces.IDENTITY_PROVED)
        self.assertIn(STRANGER, workspaces.proved_addresses())

    def test_a_failed_proof_is_not_recorded_as_one(self):
        """The other direction, so the test above cannot pass by writing
        IDENTITY_PROVED to everything."""
        self.provider.state["behaviour"]["claim_email_verified"] = False
        opener = self.opener()
        flow = self.start_flow(opener)
        self.finish_flow(opener, flow["state"])
        self.assertNotIn(KNOWN, workspaces.proved_addresses())

    def test_the_stranger_is_not_told_who_does_have_access(self):
        _, _, headers = self.sign_in(email=STRANGER)
        opener = self.opener()
        _, _, body = self.request(opener, "/login")
        for email in (KNOWN, SUPER_ADMIN, VIEWER):
            self.assertNotIn(email.encode(), body)

    def test_the_domain_fence_is_not_a_substitute_for_the_roster(self):
        """An allowed domain with no user row still gets nowhere."""
        os.environ["AUTH_ALLOWED_DOMAINS"] = "productive.test"
        opener, status, _ = self.sign_in(email=STRANGER)
        self.assertEqual(status, 403)
        self.assert_no_session(opener)

    def test_a_disallowed_domain_never_reaches_the_roster(self):
        os.environ["AUTH_ALLOWED_DOMAINS"] = "resonate.test"
        opener = self.opener()
        flow = self.start_flow(opener)
        self.provider.state["email"] = KNOWN     # a real user, wrong domain
        status, _, _ = self.finish_flow(opener, flow["state"])
        self.assertEqual(status, 401)
        self.assert_no_session(opener)

    def test_a_proved_viewer_is_still_only_a_viewer(self):
        """Authentication does not grant a role, and never has."""
        opener, status, _ = self.sign_in(email=VIEWER)
        self.assertEqual(status, 303)
        self.assertEqual(self.request(opener, "/reporting")[0], 200)
        self.assertEqual(self.request(opener, "/settings")[0], 403)
        self.assertEqual(self.request(opener, "/admin")[0], 404)

    def test_super_admin_cannot_be_reached_by_signing_in_as_anybody(self):
        for email in (KNOWN, VIEWER):
            with self.subTest(email=email):
                opener, _, _ = self.sign_in(email=email)
                self.assertEqual(self.request(opener, "/admin")[0], 404)
        opener, _, _ = self.sign_in(email=SUPER_ADMIN)
        self.assertEqual(self.request(opener, "/admin")[0], 200)

    def test_a_revoked_membership_stops_working_without_a_new_sign_in(self):
        """The session holds who, never what they may do."""
        opener, _, _ = self.sign_in(email=VIEWER)
        self.assertEqual(self.request(opener, "/reporting")[0], 200)
        rows = workspaces.load()
        kept = [r for r in rows
                if not (r.get("kind") == "membership"
                        and r.get("email") == VIEWER)]
        workspaces.save(kept)
        try:
            status, headers, _ = self.request(opener, "/reporting")
            self.assertNotEqual(status, 200)
        finally:
            workspaces.save(rows)

    def test_a_workspace_slug_in_a_url_reaches_a_membership_check(self):
        opener, _, _ = self.sign_in(email=VIEWER)
        status, _, _ = self.request(opener, "/select-workspace?to=contactout")
        self.assertNotEqual(status, 303)
        self.assertEqual(self.request(opener, "/companies")[0], 403)


class InviteTest(AuthTest):
    """Every test here writes to `workspaces.jsonl`, and the estate is built
    once per class - so without this, an invitation created by one test is
    still sitting there for the next, and a user it let in is still a user.

    Snapshot and restore rather than delete-what-I-made: the second is a
    list that goes stale the moment a test writes something new.
    """

    def setUp(self):
        super().setUp()
        self._rows = [dict(r) for r in workspaces.load()]

    def tearDown(self):
        workspaces.save(self._rows)
        super().tearDown()

    def session_workspace(self, opener):
        """Which workspace this session is actually in.

        A super admin may enter every workspace and lands in the first one
        `workspaces_for` returns, which is alphabetical - not necessarily
        the one a test had in mind.
        """
        _, _, body = self.request(opener, "/users")
        found = re.search(rb'class="crumb">([^<]+)<', body)
        return found.group(1).decode() if found else None


class AnInvitationBecomesAccessOnlyThroughGoogle(InviteTest):
    """The whole invitation flow, over HTTP, against a real provider.

    An administrator pre-authorises an address; the person signs in through
    Google; the membership an administrator chose - not the person, not the
    callback, not a query string - becomes real.
    """

    def invite(self, email, role="operator", workspace="productive"):
        return workspaces.invite(email, workspace, role,
                                 actor="ops@productive.test")

    def test_an_invited_stranger_gets_in_with_the_intended_role(self):
        self.invite(STRANGER, role="viewer")
        opener, status, headers = self.sign_in(email=STRANGER)
        self.assertEqual(status, 303, "the invited address was refused")
        self.assertEqual(headers["Location"], "/global")

        person = workspaces.user(STRANGER)
        self.assertIsNotNone(person)
        self.assertFalse(person["super_admin"])
        self.assertEqual(
            workspaces.membership_of(STRANGER, "productive")["role"],
            "viewer")

        # And the role is real: a viewer cannot reach settings.
        self.assertEqual(self.request(opener, "/reporting")[0], 200)
        self.assertEqual(self.request(opener, "/settings")[0], 403)
        self.assertEqual(self.request(opener, "/admin")[0], 404)

    def test_an_uninvited_stranger_still_gets_nothing(self):
        """The other half. Sign-in alone is not access."""
        opener, status, _ = self.sign_in(email=STRANGER)
        self.assertEqual(status, 403)
        self.assert_no_session(opener)
        self.assertIsNone(workspaces.user(STRANGER))

    def test_an_invitation_for_somebody_else_is_not_claimable(self):
        """Same domain, different mailbox."""
        self.invite("expected.person@productive.test", role="operator")
        opener, status, _ = self.sign_in(email=STRANGER)
        self.assertEqual(status, 403)
        self.assert_no_session(opener)
        self.assertIsNone(workspaces.user(STRANGER))
        # Still pending, not spent by the wrong person.
        self.assertEqual(
            len(workspaces.invitations(
                email="expected.person@productive.test",
                status=workspaces.PENDING)), 1)

    def test_a_revoked_invitation_is_not_claimable(self):
        self.invite(STRANGER, role="operator")
        workspaces.revoke_invitation(STRANGER, "productive",
                                     actor="ops@productive.test")
        opener, status, _ = self.sign_in(email=STRANGER)
        self.assertEqual(status, 403)
        self.assert_no_session(opener)
        self.assertIsNone(workspaces.membership_of(STRANGER, "productive"))

    def test_the_role_cannot_be_chosen_by_the_person_signing_in(self):
        """Nothing on the request decides it - not the callback query, not a
        form. The administrator wrote it down before this person appeared."""
        self.invite(STRANGER, role="viewer")
        opener = self.opener()
        flow = self.start_flow(opener)
        self.provider.state["email"] = STRANGER
        self.request(
            opener,
            "/auth/callback?" + urllib.parse.urlencode(
                {"code": "c", "state": flow["state"],
                 "role": "workspace_admin", "workspace": "contactout",
                 "super_admin": "true"}))
        self.assertEqual(
            workspaces.membership_of(STRANGER, "productive")["role"], "viewer")
        self.assertFalse(workspaces.user(STRANGER)["super_admin"])
        self.assertIsNone(workspaces.membership_of(STRANGER, "contactout"))

    def test_an_invitation_to_one_workspace_does_not_open_another(self):
        self.invite(STRANGER, role="operator", workspace="productive")
        self.sign_in(email=STRANGER)
        self.assertIsNotNone(
            workspaces.membership_of(STRANGER, "productive"))
        for other in workspaces.workspaces():
            if other["slug"] != "productive":
                self.assertIsNone(
                    workspaces.membership_of(STRANGER, other["slug"]),
                    f"the invitation reached {other['slug']}")
        self.assertEqual(
            [w["slug"] for w in workspaces.workspaces_for(STRANGER)],
            ["productive"])

    def test_the_demo_form_cannot_consume_an_invitation(self):
        """Typing an address is what invitations exist not to be.

        The demo mechanism is unreachable while a provider is configured,
        which this asserts over HTTP - but the guard that matters is that
        `_establish` only consumes when the caller says the address was
        proved.
        """
        self.invite(STRANGER, role="workspace_admin")
        opener = self.opener()
        status, headers, _ = self.request(
            opener, "/login",
            data=urllib.parse.urlencode({"email": STRANGER}).encode())
        self.assertEqual(status, 405)
        self.assertIsNone(headers.get("Set-Cookie"))
        self.assertIsNone(workspaces.user(STRANGER))
        self.assertEqual(
            len(workspaces.invitations(email=STRANGER,
                                       status=workspaces.PENDING)), 1)


class TheInviteFormIsGuarded(InviteTest):
    """RBAC, tenancy and CSRF on the endpoint that creates invitations."""

    def signed_in(self, email):
        opener, status, _ = self.sign_in(email=email)
        self.assertEqual(status, 303, f"{email} could not sign in")
        return opener

    def csrf_of(self, opener, path="/users"):
        _, _, body = self.request(opener, path)
        found = re.search(rb'name="csrf" value="([^"]+)"', body)
        return found.group(1).decode() if found else None

    def test_an_operator_cannot_invite(self):
        """`users.manage` is a workspace-admin permission.

        With a **valid** CSRF token, so the permission check is what
        refuses. The first version of this posted `csrf="x"` and passed on
        the CSRF failure instead - which the mutation audit found by
        deleting the permission check and watching this test stay green.
        A different guard firing first is not the guard under test.
        """
        opener = self.signed_in(KNOWN)              # ops@productive.test
        self.assertEqual(self.request(opener, "/users")[0], 403)

        # An operator cannot load /users, but the CSRF token belongs to the
        # session rather than the page, so any page they may read carries a
        # usable one.
        token = self.csrf_of(opener, "/companies")
        self.assertTrue(token, "no csrf token available to the operator")

        status, _, _ = self.request(
            opener, "/users/add",
            data=urllib.parse.urlencode(
                {"csrf": token, "email": "new@productive.test",
                 "role": "viewer"}).encode())
        self.assertEqual(status, 403)
        self.assertEqual(workspaces.invitations(email="new@productive.test"),
                         [])

    def test_a_viewer_cannot_invite(self):
        opener = self.signed_in(VIEWER)
        self.assertEqual(self.request(opener, "/users")[0], 403)

    def test_without_a_csrf_token_nothing_is_created(self):
        opener = self.signed_in(SUPER_ADMIN)
        status, _, _ = self.request(
            opener, "/users/add",
            data=urllib.parse.urlencode(
                {"email": "nocsrf@productive.test",
                 "role": "viewer"}).encode())
        self.assertEqual(status, 403)
        self.assertEqual(
            workspaces.invitations(email="nocsrf@productive.test"), [])

    def test_unauthenticated_cannot_reach_it(self):
        opener = self.opener()
        status, headers, _ = self.request(
            opener, "/users/add",
            data=urllib.parse.urlencode(
                {"csrf": "x", "email": "anon@productive.test",
                 "role": "viewer"}).encode())
        self.assertEqual(status, 303)
        self.assertTrue(headers["Location"].endswith("/login"))
        self.assertEqual(
            workspaces.invitations(email="anon@productive.test"), [])

    def test_super_admin_cannot_be_granted_from_the_form(self):
        opener = self.signed_in(SUPER_ADMIN)
        token = self.csrf_of(opener)
        self.assertTrue(token, "no csrf token on the users page")
        status, _, _ = self.request(
            opener, "/users/add",
            data=urllib.parse.urlencode(
                {"csrf": token, "email": "escalate@productive.test",
                 "role": "super_admin"}).encode())
        self.assertEqual(status, 403)
        self.assertEqual(
            workspaces.invitations(email="escalate@productive.test"), [])

    def test_an_admin_can_invite_into_their_own_workspace(self):
        opener = self.signed_in(SUPER_ADMIN)
        token = self.csrf_of(opener)
        here = self.session_workspace(opener)
        status, headers, _ = self.request(
            opener, "/users/add",
            data=urllib.parse.urlencode(
                {"csrf": token, "email": "invited@productive.test",
                 "role": "operator"}).encode())
        self.assertEqual(status, 303)
        pending = workspaces.invitations(email="invited@productive.test",
                                         status=workspaces.PENDING)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["role"], "operator")
        # Wherever the session is, that is where it landed.
        self.assertTrue(here)
        self.assertEqual(
            workspaces.workspace(pending[0]["workspace"])["name"], here)

    def test_the_invitation_lands_in_the_session_workspace_only(self):
        """A workspace named in the form decides nothing: the handler uses
        `repo.workspace`, which is resolved from the session."""
        opener = self.signed_in(SUPER_ADMIN)
        token = self.csrf_of(opener)
        here = self.session_workspace(opener)

        # Name a *different* workspace in the form than the session is in,
        # so the two cannot be confused for one another.
        elsewhere = next(
            w["slug"] for w in workspaces.workspaces()
            if w["name"] != here)

        self.request(
            opener, "/users/add",
            data=urllib.parse.urlencode(
                {"csrf": token, "email": "elsewhere@productive.test",
                 "role": "operator", "workspace": elsewhere}).encode())
        pending = workspaces.invitations(email="elsewhere@productive.test",
                                         status=workspaces.PENDING)
        self.assertEqual(len(pending), 1)
        self.assertNotEqual(pending[0]["workspace"], elsewhere,
                            "a workspace named in the form decided the target")
        self.assertEqual(
            workspaces.workspace(pending[0]["workspace"])["name"], here)

    def test_the_screen_shows_pending_invitations(self):
        opener = self.signed_in(SUPER_ADMIN)
        token = self.csrf_of(opener)
        self.request(
            opener, "/users/add",
            data=urllib.parse.urlencode(
                {"csrf": token, "email": "shown@productive.test",
                 "role": "reviewer"}).encode())
        _, _, body = self.request(opener, "/users")
        self.assertIn(b"Pending invitations", body)
        self.assertIn(b"shown@productive.test", body)


class DemoSignInCannotBeReached(AuthTest):
    """Production must never fall back to the mechanism it replaced."""

    def test_the_sign_in_page_offers_no_user_list(self):
        _, _, body = self.request(self.opener(), "/login")
        self.assertNotIn(b"<select", body)
        self.assertNotIn(KNOWN.encode(), body)
        self.assertIn(b"/auth/start", body)

    def test_posting_an_email_to_login_does_not_sign_anybody_in(self):
        """The impersonation attack, tried directly."""
        opener = self.opener()
        status, headers, _ = self.request(
            opener, "/login",
            data=urllib.parse.urlencode({"email": SUPER_ADMIN}).encode())
        self.assertEqual(status, 405)
        self.assertIsNone(headers.get("Set-Cookie"))
        self.assert_no_session(opener)

    def test_a_forged_session_cookie_is_worth_nothing(self):
        """Session tokens are 32 random bytes held in this process. A cookie
        that was not issued here matches nothing, and matching nothing is
        indistinguishable from having no cookie at all."""
        opener = self.opener()
        opener.cookie = "rsid=" + ("a" * 43)
        status, headers, _ = self.request(opener, "/companies")
        self.assertEqual(status, 303)
        self.assertTrue(headers["Location"].endswith("/login"))

    def test_a_write_still_needs_its_csrf_token(self):
        opener, _, _ = self.sign_in()
        status, _, _ = self.request(
            opener, "/select-workspace",
            data=urllib.parse.urlencode({"workspace": "productive"}).encode())
        self.assertEqual(status, 403)

    def test_a_client_supplied_verdict_is_refused_rather_than_ignored(self):
        opener, _, _ = self.sign_in()
        status, _, _ = self.request(
            opener, "/select-workspace",
            data=urllib.parse.urlencode({"workspace": "productive",
                                         "sendable": "true"}).encode())
        self.assertEqual(status, 403)


class SignInsExpireAndAreSingleUse(unittest.TestCase):
    """`PendingSignIns` on its own, at the boundaries the flow cannot reach.

    Ten minutes is too long to sit in a test and the clock is not something
    to sleep on, so these hand the class its own `now`. That is the whole
    reason `start` and `take` take one.
    """

    def table(self, ttl=600):
        return security.PendingSignIns(ttl=ttl)

    def test_a_flow_that_took_too_long_is_refused(self):
        pending = self.table(ttl=600)
        pending.start({"state": "s", "nonce": "n"}, now=1000)
        self.assertIsNone(pending.take("s", now=1000 + 601))

    def test_a_flow_inside_the_window_is_accepted(self):
        """The other half. An expiry that expires everything is a wall."""
        pending = self.table(ttl=600)
        pending.start({"state": "s", "nonce": "n"}, now=1000)
        self.assertIsNotNone(pending.take("s", now=1000 + 599))

    def test_a_slow_flow_is_consumed_as_well_as_refused(self):
        """Refusing without consuming would leave it there to try again."""
        pending = self.table(ttl=600)
        pending.start({"state": "s", "nonce": "n"}, now=1000)
        self.assertIsNone(pending.take("s", now=1000 + 601))
        self.assertIsNone(pending.take("s", now=1000 + 601))
        self.assertEqual(pending.count(), 0)

    def test_a_good_flow_is_consumed_too(self):
        pending = self.table(ttl=600)
        pending.start({"state": "s", "nonce": "n"}, now=1000)
        self.assertIsNotNone(pending.take("s", now=1001))
        self.assertIsNone(pending.take("s", now=1002))

    def test_abandoned_flows_do_not_accumulate(self):
        """Nobody comes back from most of them, and memory is finite."""
        pending = self.table(ttl=600)
        for index in range(5):
            pending.start({"state": f"s{index}", "nonce": "n"}, now=1000)
        self.assertEqual(pending.count(), 5)
        pending.start({"state": "later", "nonce": "n"}, now=1000 + 601)
        self.assertEqual(pending.count(), 1)


class NothingSensitiveReachesTheAccessLog(unittest.TestCase):
    """The identity provider returns the authorization code *in the URL*.

    So the default request-line log writes a live OAuth credential to
    stdout, where a platform keeps it indefinitely for anyone who can read
    the project's logs. Found in production, in Railway's log store:

        GET /auth/callback?state=jB8zcyZi...&code=4/0ATsMZq... 303

    PKCE makes that particular code useless to whoever lifts it - the
    verifier never leaves the process and the code was single-use and
    already spent - but a credential written down is a credential written
    down, and the next parameter to appear there may not be so harmless.
    """

    def test_the_authorization_code_never_reaches_a_log_line(self):
        line = ('"GET /auth/callback?state=STATEVALUE&'
                'code=4/0AcodeVALUE HTTP/1.1" 303 -')
        out = app.redact(line)
        self.assertNotIn("4/0AcodeVALUE", out)
        self.assertNotIn("STATEVALUE", out)

    def test_the_whole_query_goes_not_a_chosen_subset(self):
        """A denylist of sensitive names is one new parameter away from
        leaking again, which is the same argument `SAFE_ENV` makes."""
        out = app.redact('"GET /companies?batch=b1&secret=xyz HTTP/1.1" 200 -')
        self.assertNotIn("b1", out)
        self.assertNotIn("xyz", out)

    def test_the_part_worth_logging_survives(self):
        """Redaction that removes the diagnostic value gets switched off."""
        out = app.redact('"GET /companies?page=2 HTTP/1.1" 200 -')
        self.assertIn("/companies", out)
        self.assertIn("200", out)
        self.assertIn("GET", out)

    def test_a_line_with_no_query_is_untouched(self):
        line = '"GET /companies HTTP/1.1" 200 -'
        self.assertEqual(app.redact(line), line)


class TheChannelMustBeProtected(unittest.TestCase):
    """The id_token's signature is not verified, and TLS is why that is sound.

    `oidc.py` says so at length: the token is trusted because it arrives
    over TLS from the issuer's own endpoint. These are the tests that stop
    that precondition quietly becoming untrue - without them the whole
    argument rests on a check nothing exercises, which is worse than not
    having made the argument.
    """

    def test_a_plaintext_issuer_is_refused(self):
        with self.assertRaises(oidc.AuthError) as caught:
            oidc.require_tls("http://accounts.example.com", "the issuer")
        self.assertIn("https", str(caught.exception))

    def test_a_plaintext_token_endpoint_is_refused_at_discovery(self):
        with self.assertRaises(oidc.AuthError):
            oidc.require_tls("http://idp.example.com/token",
                             "the token endpoint")

    def test_a_plaintext_redirect_url_is_refused(self):
        """The code comes back on it, and PKCE is not a licence to send a
        code in the clear."""
        with self.assertRaises(oidc.AuthError):
            oidc.authorization_url(
                {"authorization_endpoint": "https://idp.example.com/auth"},
                "client", "http://app.example.com/auth/callback",
                oidc.begin())

    def test_https_is_accepted(self):
        self.assertTrue(oidc.require_tls("https://accounts.example.com", "x"))

    def test_loopback_http_is_the_one_exemption(self):
        """Somebody who can bind loopback here is already inside everything
        this protects, and it is what lets the tests above stand up a real
        provider."""
        for url in ("http://127.0.0.1:8080/token", "http://localhost/token"):
            with self.subTest(url=url):
                self.assertTrue(oidc.require_tls(url, "x"))

    def test_a_hostname_that_merely_contains_localhost_is_not_loopback(self):
        with self.assertRaises(oidc.AuthError):
            oidc.require_tls("http://localhost.evil.test/token", "x")

    def test_discovery_over_plaintext_never_reaches_the_network(self):
        with self.assertRaises(oidc.AuthError):
            oidc.discover("http://idp.example.com")


class ATemplatedIssuerIsRefusedWhereItCanBeExplained(unittest.TestCase):
    """Found by fetching Microsoft's real discovery document.

    A multi-tenant Entra endpoint reports its issuer as the literal
    template `https://login.microsoftonline.com/{tenantid}/v2.0`, while a
    real `id_token` carries the tenant's GUID in that position. `verify`
    compares the two for exact equality - correctly, because a document
    served from one host and issuing for another is the confusion `iss`
    exists to catch - so every sign-in against that issuer would be
    refused as "issued by a different issuer", which names the symptom and
    not the cause.

    The fake provider this file stands up reports a literal issuer, as
    Google does. That is why 71 passing tests could not find this, and it
    is the argument for reading one real document rather than one more
    fixture.

    Validating a template properly means substituting the token's `tid`
    claim, which is provider-specific work this build has not done. Until
    it has, the unsupported configuration fails when somebody configures
    it rather than at somebody's first sign-in.
    """

    class Serving:
        """Answers discovery with one document, over https."""

        def __init__(self, document):
            self.document = document

        def open(self, request, timeout=None):
            import io as _io

            body = json.dumps(self.document).encode()
            return _io.BytesIO(body)

    def document(self, issuer):
        return {
            "issuer": issuer,
            "authorization_endpoint": "https://login.example.com/auth",
            "token_endpoint": "https://login.example.com/token",
        }

    MULTI = "https://login.microsoftonline.com/{tenantid}/v2.0"

    def test_a_templated_issuer_is_refused(self):
        opener = self.Serving(self.document(self.MULTI))
        with self.assertRaises(oidc.AuthError) as caught:
            oidc.discover("https://login.microsoftonline.com/common/v2.0",
                          opener=opener)
        self.assertIn("templated", str(caught.exception))

    def test_the_refusal_says_what_to_do_instead(self):
        opener = self.Serving(self.document(self.MULTI))
        with self.assertRaises(oidc.AuthError) as caught:
            oidc.discover("https://login.microsoftonline.com/common/v2.0",
                          opener=opener)
        self.assertIn("single-tenant", str(caught.exception))

    def test_a_literal_issuer_is_accepted(self):
        """Google's shape, and a single-tenant Entra endpoint's. The guard
        must not refuse the configurations that work."""
        issuer = "https://login.microsoftonline.com/a-real-guid/v2.0"
        opener = self.Serving(self.document(issuer))
        document = oidc.discover(issuer, opener=opener)
        self.assertEqual(document["issuer"], issuer)

    def test_googles_own_shape_is_accepted(self):
        issuer = "https://accounts.google.com"
        opener = self.Serving(self.document(issuer))
        self.assertEqual(oidc.discover(issuer, opener=opener)["issuer"],
                         issuer)

    def test_a_brace_in_a_path_that_is_not_a_template_still_passes(self):
        """One brace is not a placeholder. The guard looks for both."""
        issuer = "https://idp.example.com/tenant%7Bx/v2.0"
        opener = self.Serving(self.document(issuer))
        self.assertEqual(oidc.discover(issuer, opener=opener)["issuer"],
                         issuer)


class TheTokenEndpointIsWhereverDiscoverySaysItIs(unittest.TestCase):
    """Google puts it on a different host from the issuer, and that is normal.

    `accounts.google.com` issues the tokens and `oauth2.googleapis.com`
    exchanges them - confirmed by reading Google's real discovery document.
    The fake provider in this file serves both from one port, so it could
    never have caught a client that quietly built the token URL from the
    issuer instead of using the discovered one. This can.
    """

    class Opener:
        """Records where the POST went, and answers with nothing useful."""

        def __init__(self):
            self.url = None

        def open(self, request, timeout=None):
            self.url = request.full_url
            raise urllib.error.HTTPError(request.full_url, 400, "no", None,
                                         None)

    def test_the_exchange_posts_to_the_discovered_host(self):
        opener = self.Opener()
        document = {
            "issuer": "https://accounts.example.com",
            "authorization_endpoint": "https://accounts.example.com/auth",
            "token_endpoint": "https://tokens.elsewhere.example/token",
        }
        with self.assertRaises(oidc.AuthError):
            oidc.exchange(document, "client", "secret",
                          "https://app.test/auth/callback", "code",
                          "verifier", opener=opener)
        self.assertEqual(opener.url,
                         "https://tokens.elsewhere.example/token")

    def test_a_cross_host_token_endpoint_still_has_to_be_https(self):
        document = {
            "issuer": "https://accounts.example.com",
            "authorization_endpoint": "https://accounts.example.com/auth",
            "token_endpoint": "http://tokens.elsewhere.example/token",
        }
        with self.assertRaises(oidc.AuthError):
            oidc.exchange(document, "client", "secret",
                          "https://app.test/auth/callback", "code",
                          "verifier", opener=self.Opener())


class TheModeIsNotDecidedByARequest(unittest.TestCase):
    """No header, form field or query string chooses the mechanism."""

    def test_only_the_environment_selects_it(self):
        previous = os.environ.get("AUTH_PROVIDER")
        try:
            os.environ.pop("AUTH_PROVIDER", None)
            self.assertEqual(security.sign_in_mode(), security.DEMO_SIGN_IN)
            os.environ["AUTH_PROVIDER"] = "oidc"
            with self.assertRaises(security.AuthNotConfigured):
                # Named but not configured: refused, never demoted to demo.
                security.sign_in_mode()
        finally:
            if previous is None:
                os.environ.pop("AUTH_PROVIDER", None)
            else:
                os.environ["AUTH_PROVIDER"] = previous


if __name__ == "__main__":
    unittest.main()
