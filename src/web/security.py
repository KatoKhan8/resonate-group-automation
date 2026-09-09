#!/usr/bin/env python3
"""Sessions, CSRF, escaping and the safety state the whole UI is told about.

Everything here is about a browser being an untrusted place. The four things
this module refuses to let happen:

**A secret reaching the page.** `SAFE_ENV` is an allowlist, not a denylist: the
UI is told the *names* of the credentials that are configured and never a
value. A denylist here would be one new environment variable away from a leak.

**A verdict arriving from the client.** Nothing in a request body is trusted as
a decision. `sendable`, `approved`, `eligible` and `verified` are recomputed
server-side on every read, and `REFUSED_FIELDS` makes a request carrying one an
error rather than something silently ignored - because silently ignored is how
a caller comes to believe it worked.

**A cross-site write.** Every mutating request needs the session's CSRF token,
compared in constant time.

**Untrusted text rendering as markup.** `esc()` is the only way text reaches a
page, and prospect names and scraped evidence are attacker-controlled.
"""
import hashlib
import hmac
import html
import os
import secrets
import time

from .. import workspaces

# How long a session lasts without activity. Short, because this is an
# operations tool that can spend money and pause campaigns.
SESSION_TTL = 8 * 3600

# Environment variables the UI may name. Values are never sent - only whether
# something is configured - so an operator can see that a provider is wired up
# without the page becoming a place to read a key from.
SAFE_ENV = ("BISON_BASE", "BISON_CAMPAIGN_ID", "HEYREACH_CAMPAIGN_ID")

# Credentials. Named here so `configured()` can report presence, and asserted
# by a test never to appear in any rendered byte.
SECRET_ENV = ("CONTACTOUT_TOKEN", "BISON_KEY", "HEYREACH_KEY", "REOON_KEY",
              "AIARK_KEY", "DELIVERABLE_KEY", "DELIVERABLE_PASSWORD",
              "APIFY_TOKEN", "SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET",
              # The identity provider's client secret. In this list and not
              # in SAFE_ENV: the sign-in screen names the provider, never
              # what authenticates us to it, and the canary sweep that walks
              # every screen reads this tuple to know what to look for.
              "AUTH_CLIENT_SECRET")

# Fields a browser must never be able to set. A request carrying one is
# refused rather than sanitised: a caller who sent `sendable=true` and got a
# 200 has learned the wrong thing about this system.
REFUSED_FIELDS = ("sendable", "approved", "eligible", "verified", "verdict",
                  "confirmation_count", "state", "live", "email_eligible",
                  "linkedin_eligible", "would_send")


class Refused(PermissionError):
    """The request was rejected before anything looked at what it wanted."""


def esc(value):
    """The only way untrusted text reaches a page."""
    return html.escape(str(value if value is not None else ""), quote=True)


def attr(value):
    """Escaped for an HTML attribute, quotes included."""
    return html.escape(str(value if value is not None else ""), quote=True)


def safe_url(url):
    """A URL fit to put in an href.

    Evidence carries source URLs that came off the public web, so a `javascript:`
    or `data:` scheme is a real possibility rather than a hypothetical one.
    Anything that is not plainly http(s) renders as text instead of a link.
    """
    text = str(url or "").strip()
    lowered = text.lower()
    if lowered.startswith(("http://", "https://")):
        return text
    return None


def configured(name):
    """Is this credential present? Never what it is."""
    return bool(os.environ.get(name))


def credential_status():
    """Which providers are wired up, by name only."""
    return {name: configured(name) for name in SECRET_ENV}


# --------------------------------------------------- what signing in proves
#
# Two mechanisms, and exactly one of them is in force at a time.
#
#   DEMO_SIGN_IN  pick an email out of a list. No password, no provider.
#                 Right for a demonstration and for an operator on
#                 loopback, where the person at the keyboard is the person.
#   OIDC_SIGN_IN  an identity provider proves the address, and this system
#                 decides what that address may do. `web/oidc.py`.
#
# The choice is made by `AUTH_PROVIDER` and by nothing else - not by
# APP_MODE, not by which interface is bound, not by a request. A single
# environment variable, read in one function, so "which is running" has one
# answer that every guard reads.

DEMO_SIGN_IN = "demo"
OIDC_SIGN_IN = "oidc"

AUTH_PROVIDER_VAR = "AUTH_PROVIDER"

# What OIDC needs before it can prove anything. All four, or none: a
# half-configured provider is the state that produces a sign-in screen
# which looks real and cannot work.
OIDC_SETTINGS = ("AUTH_ISSUER", "AUTH_CLIENT_ID", "AUTH_CLIENT_SECRET",
                 "AUTH_REDIRECT_URL")


class AuthNotConfigured(RuntimeError):
    """`AUTH_PROVIDER` asks for something this build cannot do."""


def sign_in_mode():
    """Which sign-in mechanism is in force. Raises rather than falling back.

    The refusal matters more than the answer. `AUTH_PROVIDER=okta` is a
    plausible thing to type, it names a provider nothing here implements,
    and the dangerous response is to shrug and use the demo mechanism -
    a production deployment where anyone who reaches the URL picks the
    super admin out of a list, reached by way of a variable that was *set*.
    So an unknown value raises, and a partly-filled `oidc` raises with the
    names of what is missing. Unset is the only thing that means demo.
    """
    provider = (os.environ.get(AUTH_PROVIDER_VAR) or "").strip().lower()
    if not provider:
        return DEMO_SIGN_IN
    if provider != OIDC_SIGN_IN:
        raise AuthNotConfigured(
            f"{AUTH_PROVIDER_VAR}={provider!r} is not implemented. This "
            f"build supports {OIDC_SIGN_IN!r}, or leave it unset for demo "
            "sign-in. It is refused rather than ignored: falling back to "
            "demo here would be unauthenticated access reached by way of a "
            "variable somebody set to turn authentication on.")
    missing = [name for name in OIDC_SETTINGS if not configured(name)]
    if missing:
        raise AuthNotConfigured(
            f"{AUTH_PROVIDER_VAR}={OIDC_SIGN_IN} needs " + ", ".join(missing))
    return OIDC_SIGN_IN


def auth_settings():
    """The identity provider's configuration. Values, for `oidc.py` only.

    Never rendered. `SAFE_ENV` above is the allowlist of what a page may
    even name, and `AUTH_CLIENT_SECRET` is in `SECRET_ENV` beside the
    provider keys, which is what the planted-canary sweep walks.
    """
    if sign_in_mode() != OIDC_SIGN_IN:
        return None
    return {
        "issuer": os.environ["AUTH_ISSUER"].strip().rstrip("/"),
        "client_id": os.environ["AUTH_CLIENT_ID"].strip(),
        "client_secret": os.environ["AUTH_CLIENT_SECRET"].strip(),
        "redirect_url": os.environ["AUTH_REDIRECT_URL"].strip(),
        "allowed_domains": tuple(
            d.strip().lower()
            for d in (os.environ.get("AUTH_ALLOWED_DOMAINS") or "").split(",")
            if d.strip()),
    }


def sign_in_proves_identity():
    """Does signing in prove who somebody is?

    Only with an identity provider behind it. The demo mechanism takes an
    email address and believes it, which is the right mechanism for a
    fictional estate and no mechanism at all for anything a stranger can
    reach.

    This is the seam. Two things refuse on the strength of it - production
    mode and a reachable bind, both in `app.check_configuration` - and they
    lift together the moment a provider is configured, because they read
    one fact rather than each carrying a copy of it.
    """
    return sign_in_mode() == OIDC_SIGN_IN


def cookie_is_secure():
    """Should the session cookie be `Secure`?

    Tied to the sign-in mechanism rather than to `APP_MODE`, because the
    mechanism is what implies the transport: `AUTH_REDIRECT_URL` must be
    https for anything a provider can reach, so a build doing real sign-in
    is a build behind TLS. Setting it on a plain-http loopback session
    would sign the operator out of their own machine, which is how a
    security flag gets deleted rather than fixed.
    """
    try:
        return sign_in_mode() == OIDC_SIGN_IN
    except AuthNotConfigured:
        # Misconfigured: the process will not be serving anyway. The safe
        # reading of "I do not know" is the restrictive one.
        return True


def session_cookie(token, secure=None, clearing=False):
    """The one place a session cookie is written.

    `HttpOnly` so script cannot read it, `Secure` when there is TLS to
    require it, and `SameSite=Lax`. One function, because two spellings of
    a cookie is one spelling that quietly loses a flag.

    ## Lax rather than Strict, and why that is not a weakening

    It was `Strict`, and `Strict` cannot work with a redirect-based sign-in.
    The provider sends the browser back to `/auth/callback`, which is a
    cross-site top-level navigation; the cookie set on that response is
    stored but **not sent** on the request the following redirect makes to
    `/global`. The application sees no session, bounces to `/login`, and
    the person is looking at a sign-in page having just signed in - with no
    error, because nothing failed. Three real sessions existed on the
    production server while this was happening.

    `Lax` sends the cookie on a top-level GET navigation and withholds it
    from cross-site POSTs, iframes, XHR and subresource loads. The request
    it newly permits is somebody following a link to this application,
    which is what a link is for.

    **What actually stops cross-site writes here is not this attribute.**
    `check_csrf` runs on every mutating request and compares a per-session
    token in constant time, and `refuse_client_verdicts` rejects a request
    that tries to decide something the server decides. SameSite is a second
    fence, and the case it guards - a cross-site POST - is one `Lax` still
    refuses.
    """
    secure = cookie_is_secure() if secure is None else secure
    flags = "Path=/; HttpOnly; SameSite=Lax"
    if secure:
        flags += "; Secure"
    if clearing:
        return f"rsid=; {flags}; Max-Age=0"
    return f"rsid={token}; {flags}"


# ------------------------------------------------------------- the sessions

class Sessions:
    """In-memory sessions. One process, which is what this build is.

    A restart logs everybody out. That is the correct trade for an operations
    tool with no user database: the alternative is persisting session material
    to disk, which is a new place for a secret to live.
    """

    def __init__(self):
        self._by_token = {}

    def create(self, email, workspace=None, now=None):
        """A session holds *who*, never *what they may do*.

        The role is deliberately absent: it is resolved from the workspace
        membership on every request. A role cached in a session is a role that
        keeps working after somebody removed it, and a role in a cookie is a
        role the browser can edit.
        """
        token = secrets.token_urlsafe(32)
        self._by_token[token] = {
            "email": str(email).strip().lower(),
            "workspace": workspace,
            "csrf": secrets.token_urlsafe(32),
            "created_at": now or time.time(),
            "seen_at": now or time.time(),
        }
        return token

    def get(self, token, now=None):
        session = self._by_token.get(token or "")
        if not session:
            return None
        now = now or time.time()
        if now - session["seen_at"] > SESSION_TTL:
            self._by_token.pop(token, None)
            return None
        session["seen_at"] = now
        return session

    def destroy(self, token):
        self._by_token.pop(token or "", None)

    def set_workspace(self, token, workspace):
        session = self._by_token.get(token or "")
        if session:
            session["workspace"] = workspace
        return session

    def count(self):
        return len(self._by_token)


class PendingSignIns:
    """Sign-ins that have started and not come back yet.

    Kept server-side and keyed by the `state` this process minted, rather
    than in a cookie. Two reasons, and the second is the load-bearing one:

    - a cookie carrying the PKCE verifier would put the one secret PKCE
      exists to keep off the wire onto the wire;
    - a cookie read at the callback is a cookie whose `SameSite` has to be
      permissive enough to survive a cross-site navigation, and tying the
      PKCE verifier's storage to that attribute means one cookie policy
      decision silently changes what an attacker can replay. Server-side
      state has no such coupling.

      This is also the note that should have caught the bug it did not:
      it reasons correctly about the callback *request* and says nothing
      about the redirect the callback *returns*, which is where a `Strict`
      session cookie is actually lost.

    In memory, like `Sessions`, for the same reason: this build is one
    process, and a half-finished sign-in is not worth a new place on disk
    for a secret to live.
    """

    def __init__(self, ttl=None):
        self._by_state = {}
        self._ttl = ttl

    def start(self, flow, now=None):
        """Remember a flow, and drop any that have gone stale.

        Pruning happens here rather than on the way out. It did both until
        an attack on the expiry check survived: `take` pruned first, so by
        the time its own age check ran there was nothing old left to reject
        and the line could be deleted with every test still green. One
        place decides *this is too old*, and it is the one whose answer
        anybody depends on.
        """
        now = time.time() if now is None else now
        self._prune(now)
        self._by_state[flow["state"]] = dict(flow, started_at=now)
        return flow

    def take(self, state, now=None):
        """Single use, then age. A state that comes back twice is a replay.

        Popped before it is aged, so a sign-in that sat open too long is
        both refused *and* gone - otherwise the slow attempt could be
        presented again and again.
        """
        now = time.time() if now is None else now
        found = self._by_state.pop(str(state or ""), None)
        if found is None:
            return None
        if now - found["started_at"] > self._window():
            return None
        return found

    def _window(self):
        from . import oidc

        return self._ttl if self._ttl is not None else oidc.FLOW_TTL

    def _prune(self, now):
        for state, flow in list(self._by_state.items()):
            if now - flow["started_at"] > self._window():
                self._by_state.pop(state, None)

    def count(self):
        return len(self._by_state)


def check_csrf(session, supplied):
    """Constant-time, and a refusal that explains nothing to the sender."""
    expected = (session or {}).get("csrf") or ""
    if not expected or not supplied:
        raise Refused("missing CSRF token")
    if not hmac.compare_digest(str(expected), str(supplied)):
        raise Refused("bad CSRF token")
    return True


def refuse_client_verdicts(payload):
    """A request that tries to decide something the server decides."""
    for field in REFUSED_FIELDS:
        if field in (payload or {}):
            raise Refused(
                f"{field!r} is decided by the server and may not be supplied "
                "by a client; the request was refused rather than ignored")
    return True


def membership(session):
    """The membership that authorises this request, resolved fresh.

    Resolved per request rather than cached in the session: a role that was
    revoked five minutes ago must stop working now, not at the next login.
    """
    if not session or not session.get("workspace"):
        return None
    return workspaces.membership_of(session["email"], session["workspace"])


def require(session, permission):
    """Permission check at the boundary. Raises rather than returning False."""
    found = membership(session)
    if found is None:
        raise workspaces.NotAMember("not a member of this workspace")
    workspaces.require(found, permission)
    return True


def may(session, permission):
    found = membership(session)
    if found is None:
        return False
    return workspaces.may(found.get("role"), permission)


def role_of(session):
    return (membership(session) or {}).get("role")


def fingerprint(*parts):
    """A short digest for optimistic concurrency in a form."""
    blob = "|".join(str(p) for p in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
