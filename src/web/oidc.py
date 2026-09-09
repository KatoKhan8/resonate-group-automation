#!/usr/bin/env python3
"""The conversation with an identity provider, and nothing else.

This module answers exactly one question - **which verified email address
is this?** - and it answers it by asking somebody qualified. It knows
nothing about workspaces, roles, memberships or sessions, and it must not
learn: `security.py` maps the answer onto canonical Resonate identity, and
keeping the two apart is what stops a provider's idea of a person becoming
this system's idea of what they may do.

## Why an identity provider and not a password

Three reasons, in the order they mattered.

**We would be inventing password security.** Storage, hashing parameters,
reset flows, rate limiting, breach response. Every one of those is a thing
somebody else already does better, and a thing this repository would then
own forever.

**There is nowhere to send an email from.** A magic link or an OTP needs a
transport, and the central safety property of this build is that it cannot
send: `push.run(live=True)` raises and `tagsync.send` refuses. Adding an
outbound mail path so that people can log in would put a sending
capability into the one system designed not to have one.

**The people who need accounts already have accounts.** Resonate operators
and the agency's clients are on Google Workspace or Microsoft 365. The
identity exists; we only need it proved.

## Why this is standard library

`DEPLOYMENT-PLAN.md` §1 calls zero third-party dependencies the
deployment's biggest advantage, and `tests/test_deployment_config.py`
asserts it against every import in `src/`. An OIDC client that needs an
SDK would trade that for code we would still have to read.

What OIDC actually requires here is a redirect, a form POST, and some
comparisons. `urllib` does the first two and `hmac.compare_digest` does
the third.

## The flow, and what guards each step

    /auth/start     mint state, nonce and a PKCE verifier; remember them
                    server-side; redirect to the provider
    provider        authenticates the person however it likes - password,
                    passkey, hardware key, SSO. None of that is our
                    business and none of it reaches this process
    /auth/callback  state must match one we minted and have not used;
                    exchange the code for tokens over TLS; check the
                    claims; return a verified email

| guard | what it stops |
| --- | --- |
| `state`, single use, server-side, constant-time compare | somebody else's callback replayed into your browser |
| `nonce`, echoed in the id_token | a token minted for a different request |
| PKCE `S256` | an intercepted authorization code being redeemed by anyone else |
| `iss` and `aud` | a token from another provider, or for another client |
| `exp` | a token that has expired |
| `email_verified` | an address the provider has not itself confirmed |
| TLS on the token endpoint | reading the client secret off the wire |

## The one deliberate simplification, and why it is sound

**The id_token's signature is not verified.** That is allowed, and it is
allowed for a specific reason: this client only ever reads an id_token
that came back in the body of its own POST to the provider's token
endpoint, over TLS, authenticated with the client secret. OpenID Connect
Core §3.1.3.7 says signature validation MAY be skipped when the token is
obtained through exactly that direct, protected channel, because TLS has
already proved who sent it.

The alternative is RSA and JWKS in the standard library, which is a
signature verifier we would be writing ourselves - and a verifier with a
bug in it is worse than one we correctly did not need.

**The precondition is enforced rather than assumed.** `require_tls()`
refuses a non-loopback endpoint that is not `https`, so the channel this
argument depends on cannot quietly stop being one. Loopback is exempt so
the tests can stand up a real provider on an ephemeral port; somebody who
can bind loopback on this machine is already inside everything this
protects.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 15

# How long an in-flight sign-in may take between /auth/start and
# /auth/callback. Long enough for a password manager, a second factor and a
# consent screen; short enough that an abandoned attempt does not sit in
# memory all afternoon.
FLOW_TTL = 10 * 60

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1", "[::1]")

# Exactly what is read, and nothing else.
#
#   openid  -> iss, aud, exp, nonce, sub
#   email   -> email, email_verified
#
# `profile` was in here and was never read: no name, no picture, no locale
# reaches this system. It is a small thing and it is on a consent screen a
# real person is asked to agree to, which makes asking for what we do not
# use a claim about ourselves that is not true.
SCOPE = "openid email"


class AuthError(RuntimeError):
    """Sign-in failed. The message is for the log, never for the browser."""


class NotConfigured(AuthError):
    """No identity provider is configured, so nothing can be proved."""


def _loopback(url):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host in ("127.0.0.1", "localhost", "::1")


def require_tls(url, what):
    """Refuse a channel the signature argument above does not hold over.

    Not decoration. The whole reason this client may skip verifying the
    id_token's signature is that the token arrives over TLS from the
    issuer itself. If that stops being true the argument collapses, so it
    is checked rather than trusted.
    """
    scheme = (urllib.parse.urlparse(url).scheme or "").lower()
    if scheme == "https":
        return url
    if scheme == "http" and _loopback(url):
        return url
    raise AuthError(
        f"{what} must be https (got {scheme or 'no scheme'}): the id_token "
        "is trusted because it arrives over TLS from the issuer, so a "
        "plaintext channel would remove the only thing making it trustworthy")


# ------------------------------------------------------------- discovery

def discovery_url(issuer):
    return issuer.rstrip("/") + "/.well-known/openid-configuration"


def discover(issuer, opener=None):
    """The provider's own description of itself.

    Fetched rather than configured: an issuer that rotates an endpoint
    should not need a redeploy, and four URLs in the environment are four
    chances to paste one of them wrong.
    """
    url = require_tls(discovery_url(issuer), "the issuer")
    document = _get_json(url, opener=opener)
    for key in ("authorization_endpoint", "token_endpoint"):
        if not document.get(key):
            raise AuthError(f"the issuer's discovery document has no {key}")
    require_tls(document["authorization_endpoint"], "the authorization endpoint")
    require_tls(document["token_endpoint"], "the token endpoint")
    # The issuer the provider claims to be, which is what an id_token's
    # `iss` will carry. Compared against the configured one rather than
    # assumed equal: a discovery document served from one host and issuing
    # for another is exactly the confusion `iss` exists to catch.
    document.setdefault("issuer", issuer)
    # A templated issuer is refused here, where it can be explained.
    #
    # Found by fetching Microsoft's real multi-tenant document: it returns
    # `https://login.microsoftonline.com/{tenantid}/v2.0` verbatim, while a
    # real `id_token` carries the tenant's GUID in that position. `verify`
    # compares the two for exact equality - correctly, since a document
    # served from one host and issuing for another is the confusion `iss`
    # exists to catch - so every sign-in against that issuer would be
    # refused with "id_token was issued by a different issuer", which
    # describes the symptom and not the cause.
    #
    # Validating it properly means substituting the token's `tid` claim
    # into the template, which is provider-specific logic this build does
    # not have. Until it does, an unsupported configuration should fail
    # when somebody configures it rather than when somebody signs in.
    # Google's issuer is literal and unaffected, as is a single-tenant
    # Entra endpoint.
    claimed = str(document.get("issuer") or "")
    if "{" in claimed and "}" in claimed:
        raise AuthError(
            f"the issuer's discovery document reports a templated issuer "
            f"({claimed}). Validating an id_token against it needs the "
            "tenant substituted in, which this build does not do - use a "
            "single-tenant issuer URL instead of a multi-tenant one")
    return document


# ------------------------------------------------------- the outbound leg

def begin(now=None):
    """The three secrets one sign-in attempt needs, minted together.

    Returned rather than stored: the caller owns the pending-flow table,
    because how long a half-finished sign-in may live is a policy question
    and this module does not make policy.
    """
    verifier = secrets.token_urlsafe(64)
    return {
        "state": secrets.token_urlsafe(32),
        "nonce": secrets.token_urlsafe(32),
        "verifier": verifier,
        "challenge": _s256(verifier),
        "started_at": now if now is not None else time.time(),
    }


def _s256(verifier):
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def authorization_url(document, client_id, redirect_url, flow, scope=None):
    """Where to send the browser. Nothing secret travels in it.

    The verifier stays here; only its SHA-256 goes out. That is the whole
    point of PKCE: an authorization code lifted from a redirect is useless
    to whoever lifted it.
    """
    # The code comes back on this URL. Over plaintext it comes back to
    # anybody on the path, and PKCE only makes a stolen code useless to
    # somebody who did not also see the verifier - it is not a licence to
    # send the code in the clear.
    require_tls(redirect_url, "the redirect URL")
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_url,
        "scope": scope or SCOPE,
        "state": flow["state"],
        "nonce": flow["nonce"],
        "code_challenge": flow["challenge"],
        "code_challenge_method": "S256",
    }
    endpoint = document["authorization_endpoint"]
    joiner = "&" if urllib.parse.urlparse(endpoint).query else "?"
    return endpoint + joiner + urllib.parse.urlencode(query)


# ------------------------------------------------------- the inbound leg

def exchange(document, client_id, client_secret, redirect_url, code, verifier,
             opener=None):
    """Trade the code for tokens. Server to server, over TLS, with the secret.

    This is the request the signature argument rests on, so its endpoint is
    re-checked here rather than only at discovery: a document cached in one
    process and an endpoint checked in another is a gap.
    """
    endpoint = require_tls(document["token_endpoint"], "the token endpoint")
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_url,
        "client_id": client_id,
        "client_secret": client_secret,
        "code_verifier": verifier,
    }).encode("ascii")
    return _post_json(endpoint, body, opener=opener)


def claims(id_token):
    """The payload of a JWT, decoded and not verified. See the module docstring.

    Structural failures are refusals, not empty dicts: a token this cannot
    parse is a token nothing should be concluded from, and returning `{}`
    here would let every check below pass vacuously.
    """
    parts = str(id_token or "").split(".")
    if len(parts) != 3:
        raise AuthError("id_token is not a three-part JWT")
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        decoded = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except Exception as e:                            # noqa: BLE001
        raise AuthError(f"id_token payload is not readable: {type(e).__name__}")
    if not isinstance(decoded, dict):
        raise AuthError("id_token payload is not an object")
    return decoded


def verified_email(document, client_id, tokens, flow, now=None,
                   allowed_domains=()):
    """Every check, then the address. Anything unmet raises.

    Returns the email and the provider's stable subject id. The subject is
    returned because it is the identifier that survives somebody changing
    their display name, and it is recorded rather than matched on: this
    system's canonical identity is the mailbox, and `ENGAGEMENT-HYGIENE.md`
    is the reason a name is never identity anywhere in it.
    """
    now = time.time() if now is None else now

    if not isinstance(tokens, dict) or not tokens.get("id_token"):
        raise AuthError("the token response carried no id_token")

    found = claims(tokens["id_token"])

    issuer = document.get("issuer")
    if issuer and found.get("iss") != issuer:
        raise AuthError("id_token was issued by a different issuer")

    audience = found.get("aud")
    audience = audience if isinstance(audience, list) else [audience]
    if client_id not in audience:
        raise AuthError("id_token was issued for a different client")

    expiry = found.get("exp")
    if not isinstance(expiry, (int, float)):
        raise AuthError("id_token has no usable exp")
    if float(expiry) <= now:
        raise AuthError("id_token has expired")

    # Constant time, and against the nonce this browser's own /auth/start
    # minted. A token that is otherwise perfect but answers a different
    # request is a replay.
    if not hmac.compare_digest(str(found.get("nonce") or ""),
                               str(flow.get("nonce") or "")):
        raise AuthError("id_token nonce does not match this sign-in")

    email = str(found.get("email") or "").strip().lower()
    if not email:
        raise AuthError("the provider returned no email address")

    # Present and false is a refusal; absent is also a refusal. An
    # unverified address is somebody's claim about a mailbox, and this
    # whole module exists to stop accepting claims.
    if found.get("email_verified") is not True:
        raise AuthError("the provider has not verified this email address")

    if allowed_domains:
        domain = email.rsplit("@", 1)[-1]
        if domain not in {d.strip().lower() for d in allowed_domains if d.strip()}:
            raise AuthError("this email domain is not allowed to sign in here")

    return {"email": email, "subject": str(found.get("sub") or "") or None,
            "issuer": found.get("iss")}


# ------------------------------------------------------------------ HTTP
#
# Deliberately not routed through `src/providers/__init__.py`. That seam
# exists to meter paid provider calls into the waterfall ledger, and an
# identity provider is infrastructure rather than a purchase - putting a
# sign-in into the spend audit would make the ledger describe something it
# is not.

def _open(url, data=None, opener=None):
    request = urllib.request.Request(
        url, data=data,
        headers={"Accept": "application/json",
                 "User-Agent": "resonate-oidc"},
        method="POST" if data is not None else "GET")
    if data is not None:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    open_it = opener.open if opener is not None else urllib.request.urlopen
    return open_it(request, timeout=TIMEOUT)


def _read_json(response):
    raw = response.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:                            # noqa: BLE001
        raise AuthError(f"the provider did not return JSON: {type(e).__name__}")


def _get_json(url, opener=None):
    try:
        with _open(url, opener=opener) as response:
            return _read_json(response)
    except AuthError:
        raise
    except urllib.error.HTTPError as e:
        raise AuthError(f"the provider answered {e.code}")
    except Exception as e:                            # noqa: BLE001
        raise AuthError(f"the provider was unreachable: {type(e).__name__}")


def _post_json(url, data, opener=None):
    try:
        with _open(url, data=data, opener=opener) as response:
            return _read_json(response)
    except AuthError:
        raise
    except urllib.error.HTTPError as e:
        # The body of a token-endpoint error carries the provider's own
        # reason. It is read for the log and never returned to the browser:
        # "invalid_client" tells an attacker which half they got wrong.
        raise AuthError(f"the token endpoint refused: {e.code}")
    except Exception as e:                            # noqa: BLE001
        raise AuthError(f"the token endpoint was unreachable: {type(e).__name__}")
