"""Shared plumbing for the provider modules. BUILD-SPEC section 5.

Three jobs: load keys from config/.env, put every request through one seam so
tests can replay a cassette instead of paying for a call, and redact anything
key-shaped before it is printed or written to disk.

Provider modules return trimmed dicts, never raw payloads (section 9, trap 8).
"""
import contextvars
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_FILE = os.path.join(ROOT, "config", ".env")

TIMEOUT = 25

# What a call costs, so phase 4 can cap before it fans out. Section 5.
COST = {
    "people-count": "free",
    "people-search": "1 search credit per profile returned",
    "decision-makers": ("1 search credit per profile returned, "
                        "1 email credit per profile with contact info when reveal_info=true"),
    "email-verifier": "1 verifier credit on a definitive result",
    "company-information-from-domain": "1 search credit",
    "reoon-verify": "1 Reoon credit",
    "aiark-people-search": "AI Ark credits, fallback only",
    "aiark-email-finder": "AI Ark credits, fallback only",
    # Blitz bills in records. The response says what the call actually cost,
    # so these describe the shape of the charge and never stand in for
    # `fair_usage.records_used`.
    "blitz-key-info": "free: 0 records",
    "blitz-domain-to-linkedin": "1 blitz record, fallback only",
    "blitz-linkedin-to-domain": "1 blitz record, fallback only",
    "blitz-company": "1 blitz record, fallback only",
    "blitz-employee-finder": "blitz records per person returned, fallback only",
    "blitz-email": "1 blitz record, fallback only",
    "blitz-phone": "1 blitz record, US only, top plan, not wired",
    "blitz-waterfall-icp-keyword": "blitz records per company returned, not wired",
}
FREE = frozenset({"people-count", "blitz-key-info"})


class ProviderError(RuntimeError):
    """A provider refused, or was unreachable."""


class MissingKey(ProviderError):
    """No credential configured for this provider."""


class HttpTimeout(ProviderError, TimeoutError):
    """The HTTP request was ABORTED at the socket layer.

    This proves WE stopped waiting. It does NOT prove the SERVER stopped
    working: the request may have been received and processed before the
    socket closed. For a GET that distinction costs nothing; for a paid
    POST it is the whole question - a retry policy must not retry a write
    it cannot prove did not happen.

    BOTH BASES, AND THE `ProviderError` ONE IS NOT COSMETIC.
    =======================================================
    This was `HttpTimeout(TimeoutError)` alone, on the reasoning that
    inheriting from nothing else keeps it distinguishable from a transport
    error, a refusal and a 5xx. Distinguishable it was - and invisible to
    every existing handler, because before this change a timeout arrived as
    a plain `ProviderError` and **27 `except ProviderError` sites across
    `src/` catch exactly that**, in `enrich`, `bisonfactory`, `campaigns`
    and elsewhere.

    Measured: `raise HttpTimeout(...)` escaped `except ProviderError`
    entirely. So the change would have converted a timeout from "this
    provider call failed, record it and carry on with the other records"
    into an uncaught exception that ends the pass - on the one class of
    failure a long provider-bound run is most likely to hit.

    Inheriting both keeps every caller working and loses nothing:
    `except HttpTimeout` still selects it precisely, and `except
    TimeoutError` still recognises it as a timeout. Distinguishability
    comes from the type, never from the absence of a base class.
    """


class HttpTransportError(ProviderError):
    """A network-level failure: DNS, connection refused, unreachable host.

    Distinct from HttpTimeout: the connection was refused or the host was
    unreachable, not that we gave up waiting on a live connection. A retry
    policy may retry this (the request demonstrably did not arrive); it
    must NOT retry HttpTimeout on a POST (the request may have arrived).
    """


def load_env(path=None):
    """config/.env into the environment. A real env var always wins."""
    path = path or ENV_FILE
    if not os.path.exists(path):
        return {}
    loaded = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if v:
                os.environ.setdefault(k, v)
                loaded[k] = v
    return loaded


def key(name):
    """Read a credential at call time, never at import."""
    load_env()
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingKey(f"no {name} in config/.env")
    return value


SECRET_PARAMS = ("token", "key", "api_key", "apikey")
SECRET_HEADERS = ("token", "authorization", "x-api-key", "key")


def redact(value):
    """Strip anything key-shaped out of a url, a header dict, or free text.

    The free-text half exists because this runs over exception strings and
    provider error notes, and those are where a header comes back to us
    quoted. A dict is redacted by key; a URL by parameter; free text by both
    the `Name: value` header form and a bare `Bearer <token>`, which is what
    an HTTP library puts in a message when it echoes a request.
    """
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in SECRET_HEADERS and str(v).lower() != "basic" else v)
                for k, v in value.items()}
    text = str(value)
    for param in SECRET_PARAMS:
        text = _redact_param(text, param)
    return _redact_headers(text)


# `Authorization: Bearer abc`, `x-api-key: abc`, and a bare `Bearer abc`.
# Deliberately greedy about what follows the marker and stops at whitespace or
# a quote: over-redacting an error message costs nothing, under-redacting it
# writes a key into a report somebody pastes into Slack.
_HEADER_MARKERS = tuple(f"{name}:" for name in SECRET_HEADERS) + ("bearer",)
_STOPS = (" ", '"', "\'", "\n", "\r", "\t", ",", ")", "}", "]", ";")


def _redact_headers(text):
    low = text.lower()
    for marker in _HEADER_MARKERS:
        start = 0
        while True:
            i = low.find(marker, start)
            if i < 0:
                break
            j = i + len(marker)
            while j < len(text) and text[j] == " ":
                j += 1
            # "Authorization: Bearer x" - skip the scheme so the token, not the
            # word Bearer, is what gets replaced.
            if low[j:j + 7] == "bearer ":
                j += 7
            elif low[j:j + 6] == "basic ":
                j += 6
            end = len(text)
            for stop in _STOPS:
                k = text.find(stop, j)
                if 0 <= k < end:
                    end = k
            if end > j:
                text = text[:j] + "***" + text[end:]
                low = text.lower()
                start = j + 3
            else:
                start = j + 1
    return text


def _redact_param(text, param):
    out, needle = text, param + "="
    start = 0
    while True:
        i = out.lower().find(needle, start)
        if i < 0:
            return out
        j = i + len(needle)
        end = len(out)
        for stop in ("&", " ", '"', "'", "\n"):
            k = out.find(stop, j)
            if k != -1:
                end = min(end, k)
        out = out[:j] + "***" + out[end:]
        start = j + 3


# urllib announces itself as "Python-urllib/x.y", which some providers sit
# behind a WAF that rejects outright (ContactOut answers Cloudflare 1010). This
# says honestly what the client is; it does not pretend to be a browser.
USER_AGENT = "resonate-group-automation/1.0 (+https://resonategroup.co)"


# ------------------------------------------------- the provider write guard
#
# WHY THIS EXISTS, and it is not hypothetical.
#
# On 2026-09-20T12:44:45Z an audit agent's throwaway probe paused LIVE
# EmailBison campaign 487. It passed a bare dict to `orchestrator.pause`;
# `campaigns.get()` returned None, the staging-repeat guard did not fire,
# `providerwrites.perform` called the transport, `key()` read `config/.env`,
# and a real `PATCH /api/campaigns/487/pause` reached send.resonategroup.co.
# Ten approved openers stopped being scheduled to send. Nothing was
# misconfigured and no rule was broken - THERE WAS NO RULE.
#
# `store.refuse_production_write` protects STATE. Nothing protected the WIRE.
# Any process that imported `src` and reached here sent a real mutation with
# the real key, and the only barrier was a sentence in a prompt asking it not
# to. A read-only instruction is not a security boundary.
#
# ## Where the guard sits, and why here rather than in `request`
#
# In the REAL transport, not in `request`. A test that swaps a cassette in
# with `set_transport` never touches the wire and must stay unaffected -
# there are thousands of those and they exercise the write paths on purpose.
# Guarding `request` would refuse them all and force a blanket opt-in across
# the suite, which is how a guard gets switched off. Guarding the wire refuses
# exactly the calls that can reach a provider and nothing else.
#
# ## Where the opt-in belongs, and why NOT in the library
#
# The entry point, never `providerwrites.perform`. Buggie reached the
# transport THROUGH `perform`, so a library that authorises itself would have
# authorised the incident. A `--live` operator command opts in; a test, probe,
# audit agent or subagent does not, because opting in is an act rather than an
# inheritance.
#
# Two ways, both explicit, both narrow:
#
#     RESONATE_PROVIDER_WRITES=1        for the whole process
#     with providers.allow_writes("..."):   for one scoped block
#
# GET, HEAD and OPTIONS are never refused. A reader cannot change a prospect's
# state, and every diagnostic in this repository is a reader.
#
# ## AND NOT EVERY POST IS A MUTATION - the scoping that makes this usable
#
# The first version of this guard refused every non-GET on the wire. It would
# have broken the entire system, and the list is worth keeping because it is
# the argument for the scope:
#
#     glm.py       POST  a model completion        adversarial review
#     xai.py       POST  a model completion        provider research
#     contactout   POST  a people search           PAID READ
#     aiark        POST  an enrichment RPC         PAID READ
#     blitz        POST  an enrichment call        PAID READ
#     apify        POST  an actor run              PAID READ
#     slack        POST  a message                 notification
#
# Every one of those is a read, a question or an internal notice. NONE of
# them can change what a prospect experiences. Refusing them would have taken
# out the whole enrichment waterfall and the whole AI workforce to guard
# against a risk they do not carry, and a guard that breaks everything is a
# guard somebody deletes.
#
# TWO PROVIDERS CAN REACH A PROSPECT: EmailBison and HeyReach. They are
# exactly the two modules that declare `WRITE_ROUTES`, and they register
# themselves here at import. A module cannot be called without being
# imported, so registration cannot be skipped by the caller.
#
# Host-based at the transport, rather than a check inside `bison._patch`, so
# it also catches a caller that builds the URL itself and calls
# `providers.request` directly - which a naive probe is quite likely to do.

# ## WHAT THIS GUARD IS AND IS NOT - stated because overclaiming a safety
# ## property is the failure this repository has already been bitten by
#
# It is a barrier against reaching a prospect-facing mutation BY ACCIDENT:
# through a chain of library calls the caller did not intend to make. That is
# the real failure mode and the one that actually happened - Buggie did not
# authorise itself, it passed a bad dict and fell through `orchestrator.pause`
# into the transport.
#
# **It is NOT enforcement against a determined in-process actor.** Anything
# running in this process can call `allow_writes("because I said so")`, set
# the env var, or monkeypatch `writes_allowed`. GLM's adversarial review
# raised exactly this and it is conceded rather than argued with: in-process,
# the honest ceiling is "process boundary or nothing", and this is a guard
# and an audit trail, not a sandbox.
#
# The fix for THAT threat is a separate process with its own credentials -
# an agent that never holds `config/.env` at all. That is real work and it is
# not pretended to be done here. What is done here is that reaching a live
# mutation now requires an ACT rather than an accident, and every refusal is
# recorded with the pid and argv of whatever tried.

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
WRITES_ENV = "RESONATE_PROVIDER_WRITES"

# Hosts whose mutations reach a real person. Populated by the provider
# modules themselves; see `guard_prospect_facing`.
_prospect_facing_hosts = set()


def normalise_method(method):
    """The HTTP verb as the wire will see it. NEVER trusts `str()`.

    `str(b"post").upper()` is `"B'POST'"`, which is in no method set and so
    fell straight past the guard - while `requests` and `httpx` both normalise
    `b"post"` to `POST` and send it. A bytes verb was therefore an unguarded
    mutation. Found by GLM's adversarial review and reproduced before it was
    accepted.
    """
    if isinstance(method, (bytes, bytearray)):
        try:
            method = method.decode("ascii", "replace")
        except Exception:
            method = ""
    return str(method or "").strip().upper()


class _Unparseable(str):
    """A host that could not be read. Distinct from "no host", because on a
    safety path those must not be the same answer."""


def host_of(url_or_host):
    """The comparable host, or `_Unparseable`, or None. NEVER raises.

    THREE DEFECTS THIS FIXES, all found by GLM's adversarial review of the
    first version within hours of it landing, and all reproduced before being
    accepted:

    1. IT RAISED. `urlsplit("http://[tracking-link]").hostname` raises
       ValueError - "does not appear to be an IPv4 or IPv6 address" - and
       bracket placeholders are ordinary in scraped signature HTML. The
       function's own `str(url or "")` proved it was meant to be total over
       garbage and it was not.
    2. A TRAILING DOT EVADED IT. `send.resonategroup.co.` is a valid FQDN
       that DNS and HTTP resolve identically to `send.resonategroup.co`, and
       exact string comparison called it a different host. That is a real
       bypass: `BISON_BASE=https://send.resonategroup.co./api` would have
       mutated live campaigns with the guard reporting nothing to guard.
    3. PUNYCODE AND UNICODE never matched each other.

    So the host is normalised rather than compared raw: lower-cased, trailing
    dot stripped, IDNA-folded where that is possible.
    """
    text = str(url_or_host or "").strip()
    if not text:
        return None
    try:
        host = urllib.parse.urlsplit(
            text if "//" in text else "//" + text).hostname
    except Exception:
        # Unparseable is NOT "no host". A mutation whose destination cannot be
        # read must not be waved through on the strength of an exception.
        return _Unparseable(text[:200])
    if not host:
        return None
    host = host.strip().rstrip(".").lower()
    if not host:
        return None
    try:
        # Folds unicode and punycode spellings onto one another. ASCII hosts
        # pass through unchanged; a host IDNA cannot encode keeps its
        # lower-cased form rather than becoming unparseable, because it is
        # still a perfectly comparable string.
        host = host.encode("idna").decode("ascii").lower()
    except Exception:
        pass
    return host


def guard_prospect_facing(url_or_host):
    """Declare a host whose mutations reach a prospect. Called at import by
    the modules that own `WRITE_ROUTES`, and by nothing else.

    Idempotent, and tolerant of being handed a full base URL, because that is
    what the calling modules have to hand. Registration normalises through the
    SAME function as the lookup - two spellings of one host must not be able
    to disagree about whether it is guarded.
    """
    host = host_of(url_or_host)
    if host and not isinstance(host, _Unparseable):
        _prospect_facing_hosts.add(host)


def is_prospect_facing(url):
    """True when a mutation to this URL could reach a prospect.

    An UNPARSEABLE destination answers True. That is the fail-closed
    direction and it is the right one on a safety path: a URL nobody can read
    is not evidence of safety, and a mutation to one is refused rather than
    permitted. It costs nothing real - a URL this cannot parse is one urllib
    is about to reject anyway.
    """
    host = host_of(url)
    if isinstance(host, _Unparseable):
        return True
    return bool(host) and host in _prospect_facing_hosts

# Set by `allow_writes` only. A ContextVar rather than a module-level list,
# and the difference is a real leak GLM found and this reproduced: with a
# plain list, a worker THREAD running while the main thread held the block
# read `writes_allowed() -> True` and could mutate a live campaign it was
# never authorised for. `gather` runs a fixed pool of eight.
#
# A ContextVar isolates asyncio tasks AND threads in CPython, so the
# authorization now belongs to the caller that opened it. It fails CLOSED
# into any code that silently relied on the global scope - a thread spawned
# inside the block is refused - which is the safe direction and is the point.
#
# The value is a tuple so nesting is a stack: an inner block's exit must not
# switch off the outer one.
_write_scopes = contextvars.ContextVar("provider_write_scopes", default=())


class ProviderWriteRefused(RuntimeError):
    """A mutating provider call was attempted without explicit authorization.

    Raised BEFORE the socket is opened. Nothing reached the provider.
    """


def writes_allowed():
    """(allowed, why). `why` is quotable in a refusal or an audit line."""
    scopes = _write_scopes.get()
    if scopes:
        return True, "allow_writes(%s)" % scopes[-1]
    if os.environ.get(WRITES_ENV) == "1":
        return True, "%s=1" % WRITES_ENV
    return False, "no %s and no allow_writes() scope" % WRITES_ENV


class allow_writes:
    """Authorise mutating provider calls for one block. Explicit, and narrow.

        with providers.allow_writes("resume 487 per OPERATOR-AUTH 2026-09-20"):
            bison.resume_campaign(487, expect_leads=10)

    The reason is required and is recorded on the refusal log and in
    `writes_allowed()`, because "who authorised this write and for what" is
    the question an incident asks first and the one the 487 pause could not
    answer.
    """

    def __init__(self, reason):
        if not str(reason or "").strip():
            raise ValueError(
                "allow_writes needs a reason: an unattributable authorization "
                "is the thing this guard exists to prevent")
        self.reason = str(reason).strip()

    def __enter__(self):
        self._token = _write_scopes.set(_write_scopes.get() + (self.reason,))
        return self

    def __exit__(self, *exc):
        # `reset(token)` rather than popping: it restores exactly what this
        # block replaced, so an inner block that somehow outlives its own
        # exit cannot corrupt the outer one's view.
        _write_scopes.reset(self._token)
        return False


def _log_refusal(method, url, why):
    """Best effort, and never allowed to affect the refusal.

    A rogue process attempting a mutation is exactly what somebody wants to
    find afterwards, and reading another agent's report is not a detection
    mechanism. Dependency-free and wrapped, so a full disk or a read-only
    volume cannot turn a refusal into a crash - or, worse, into an exception
    that some caller catches and retries around.
    """
    try:
        import datetime
        path = os.path.abspath(
            os.environ.get("PROVIDER_WRITE_REFUSALS")
            or os.path.join(ROOT, "work", "provider-write-refusals.jsonl"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        row = {
            "at": datetime.datetime.now(
                datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "method": method,
            "url": redact(str(url))[:300],
            "why": why,
            "pid": os.getpid(),
            "argv": [os.path.basename(str(a)) for a in __import__("sys").argv[:4]],
        }
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def refuse_unauthorized_write(method, url):
    """Called before the socket, on every real-transport call."""
    if normalise_method(method) not in WRITE_METHODS:
        return
    if not is_prospect_facing(url):
        return
    allowed, why = writes_allowed()
    if allowed:
        return
    _log_refusal(method, url, why)
    raise ProviderWriteRefused(
        "REFUSED %s %s - a mutating provider call with no explicit "
        "authorization (%s). This is the guard added after an audit agent "
        "paused live campaign 487 on 2026-09-20 simply by importing src and "
        "calling through. NOTHING WAS SENT. If this call is genuinely "
        "authorized, the entry point - not the library - opts in, with "
        "`RESONATE_PROVIDER_WRITES=1` or "
        "`with providers.allow_writes('<reason>'):`."
        % (normalise_method(method), redact(str(url))[:200], why))


def _urllib_transport(method, url, headers, body, timeout):
    # FIRST LINE, before the request object is even built. The refusal has to
    # land before any side effect, exactly as `refuse_production_write` does.
    refuse_unauthorized_write(method, url)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, method=method, data=data, headers=dict(headers))
    if not any(k.lower() == "user-agent" for k in headers):
        req.add_header("User-Agent", USER_AGENT)
    if not any(k.lower() == "accept" for k in headers):
        req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # An HTTPError *is* the response, and an unclosed one holds its
        # socket. Provider errors are exactly when a caller is retrying in a
        # loop, which is the worst place to leak one.
        with e:
            return e.code, e.read().decode("utf-8", "replace")
    except TimeoutError:
        # socket.timeout IS TimeoutError in Python 3.10+. The timeout fired
        # at the HTTP layer: the socket was closed, the request was ABORTED.
        # This proves WE stopped waiting; see HttpTimeout docstring for the
        # honesty caveat about what this does NOT prove.
        raise HttpTimeout(
            f"HTTP {method} timed out after {timeout}s"
        ) from None
    except urllib.error.URLError as e:
        reason = str(getattr(e, "reason", e)).lower()
        if "timed out" in reason or "timeout" in reason:
            raise HttpTimeout(
                f"HTTP {method} timed out after {timeout}s"
            ) from None
        raise HttpTransportError(
            f"{type(e).__name__}: {redact(e)}"
        ) from None
    except OSError as e:
        # Connection refused, DNS failure, network unreachable - the request
        # demonstrably did not arrive. Distinct from HttpTimeout.
        raise HttpTransportError(
            f"{type(e).__name__}: {redact(e)}"
        ) from None
    except Exception as e:
        raise HttpTransportError(
            f"{type(e).__name__}: {redact(e)}"
        ) from None


_transport = _urllib_transport


def set_transport(fn):
    """Swap the wire for a cassette. Tests do this, nothing else should."""
    global _transport
    previous, _transport = _transport, fn
    return previous


def reset_transport():
    set_transport(_urllib_transport)


def request(method, url, headers=None, body=None, timeout=TIMEOUT):
    """Every provider call goes through here. Returns (status, parsed_or_text)."""
    status, text = _transport(method, url, headers or {}, body, timeout)
    try:
        return status, json.loads(text) if text else None
    except (ValueError, TypeError):
        return status, text


def query(url, params):
    clean = {k: v for k, v in params.items() if v not in (None, "", [], {})}
    return f"{url}?{urllib.parse.urlencode(clean, doseq=True)}" if clean else url


def ok(status):
    return status is not None and 200 <= status < 300


def result(provider, status, note, healthy=None):
    """The one shape every check() returns."""
    return {"provider": provider, "ok": ok(status) if healthy is None else healthy,
            "status": status, "note": redact(note)[:120]}


def failed(provider, exc):
    return {"provider": provider, "ok": False, "status": None,
            "note": redact(str(exc))[:120]}


def pick(raw, fields):
    """Trim a payload down to named fields. Nothing else escapes the module."""
    raw = raw or {}
    return {out: raw.get(src) for out, src in fields.items()}


def mapping(data, what="response"):
    """A provider body as an object, or a stated failure.

    `(data or {}).get(...)` is safe against `None` and against `{}` and not
    against a truthy non-mapping. A JSON array body therefore raised
    `AttributeError`, which is not a `ProviderError` and so escaped every
    handler that exists to contain a provider going wrong.

    An empty body is genuinely nothing and stays `{}`. A body of the wrong
    *type* is a contract violation and is raised rather than flattened:
    reading a list as "no results" would report an unavailable provider as
    an empty one, which is the failure this module is supposed to make
    impossible to miss.
    """
    if not data:
        return {}
    if isinstance(data, dict):
        return data
    raise ProviderError(
        f"{what}: expected an object, got {type(data).__name__}")


def first(raw, *names, default=None):
    for n in names:
        if isinstance(raw, dict) and raw.get(n) not in (None, ""):
            return raw[n]
    return default
