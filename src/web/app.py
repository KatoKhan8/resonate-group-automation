#!/usr/bin/env python3
"""The HTTP layer. Routing, sessions, CSRF, status codes. No decisions.

## What a handler is allowed to do

Read the request, ask `api.py` for data, hand it to `pages.py`, set a status
code. That is the whole responsibility. WEB-READINESS states the rule as
"arguments in, JSON out, status code from the exception type", and every rule
this application enforces already has a home in the domain layer.

## Why `http.server`

The repository has no third-party dependencies at all - `clients.py` hand-parses
the subset of YAML it needs rather than taking PyYAML. That is a property worth
more than a router: it means this application starts with `py -m src.web` on any
machine with Python and nothing else, has no build step, no lockfile and no
supply chain. `ThreadingHTTPServer` handles an operator and their browser
comfortably; the deployment note in WEB-APP.md describes what to put in front
of it when more than one person uses it.

## What it refuses

Anything mutating without a CSRF token. Any request carrying a field the server
decides (`sendable`, `approved`, `eligible`). Any client slug that is not a
known client. Any path with traversal in it - there is no filesystem route at
all, assets are served from memory.
"""
import argparse
import json
import os
import sys
import tempfile
import traceback
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .. import config as app_config
from .. import repo as repo_module
from .. import agencydnc, clients, gtm, hygiene, interactions, jobs as jobs_module
from .. import senderidentity
from .. import (digestwatch, qualify as qualify_module, replywatch,
                store, workspaces)
from .. import reportdraft as reportdraft_module
from . import api, assets, demodata, oidc, pages, security, upload

DEFAULT_PORT = 8765

# How a repeated form field is carried alongside its first value. See `_form`.
LIST_SUFFIX = "__list"


def form_list(fields, name):
    """Every value submitted under one name, in order.

    One ticked checkbox is a single value and never gets a companion key, so
    reading only the companion would lose it. Both shapes come back here as a
    list, which is what a caller actually wants.
    """
    values = fields.get(name + LIST_SUFFIX)
    if values:
        return [v for v in values if str(v).strip()]
    single = fields.get(name)
    return [single] if single not in (None, "") else []

# Set by `serve()`. A module-level singleton because there is exactly one
# server per process and threading it through every handler would be noise.
STATE = {
    "sessions": security.Sessions(),
    # Sign-ins that have left for the identity provider and not come back.
    # Server-side and single-use; `security.PendingSignIns` says why it is
    # not a cookie.
    "pending": security.PendingSignIns(),
    "demo": False,
    "uploads": {},          # token -> parsed CSV awaiting a commit
}


class NoSuchIdentity(Exception):
    """A proved address this system does not recognise.

    Deliberately distinct from "the proof failed". One is somebody who is
    not who they said; the other is somebody who is exactly who they said
    and has no access here. Conflating the two would either create accounts
    for strangers or tell strangers which addresses exist.
    """

    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


class PayloadTooLarge(Exception):
    """A request larger than the transport will carry.

    Raised before reading rather than after truncating: a short read is
    indistinguishable from a smaller file, and the announced
    `Content-Length` is enough to decide on.
    """


class Handled(Exception):
    """A response has already been decided. Carries status and body."""

    def __init__(self, status, body, content_type="text/html; charset=utf-8",
                 headers=None):
        super().__init__(body if isinstance(body, str) else "")
        self.status = status
        self.body = body
        self.content_type = content_type
        self.headers = headers or []


SLACK_INTERACTIONS_PATH = "/slack/interactions"

# Slack's own limit is well under this; anything larger is not an interaction
# payload. Named rather than inline so a test can assert the refusal.
SLACK_MAX_BODY = 128 * 1024

# How much of an over-long body is read and thrown away so the 413 reaches
# the sender rather than arriving as a reset. An order of magnitude above
# the limit: far enough that a mistake gets its status code, near enough
# that a flood does not get a free read.
SLACK_DRAIN_LIMIT = 1024 * 1024


def _slack_answer(result):
    """What Slack shows the person who pressed the button.

    A sentence rather than a status code, and every branch names what
    happened to the campaign - "OK" beside a button that did nothing is the
    failure this endpoint exists to prevent.
    """
    status = (result or {}).get("status")
    if status == "duplicate":
        return "Already handled - this click was a repeat, nothing changed."
    if status == "ignored":
        return result.get("why") or "Nothing to do."
    if status in ("approved", "rejected"):
        return f"Campaign {result.get('campaign_id')} {status}."
    return result.get("why") or f"Recorded: {status}."


def redirect(location):
    raise Handled(HTTPStatus.SEE_OTHER, "", headers=[("Location", location)])


# Every read surface and the permission it needs, checked in one place before
# the handler runs. A table rather than a check scattered through twenty
# handlers, because "what can a viewer see" should be a question with exactly
# one place to look - and because the handler that forgets is the one that
# leaks. Longest prefix first: `/companies/<id>` must not match before
# `/companies`.
READ_PERMISSIONS = (
    # The two global surfaces. Both aggregate only the workspaces the caller
    # is a member of - see `api.global_overview` - so the permission here is
    # the one that says "you may look at a workspace at all", and the
    # membership table decides which.
    ("/global/reporting", workspaces.REPORTING_VIEW),
    ("/global", workspaces.WORKSPACE_VIEW),
    ("/reporting/client", workspaces.REPORTING_VIEW),
    ("/reporting/editor", workspaces.REPORTING_VIEW),
    ("/health", workspaces.OPERATIONS_VIEW),
    ("/refresh", workspaces.OPERATIONS_VIEW),
    ("/revival", workspaces.OPERATIONS_VIEW),
    ("/audience", workspaces.CONTACTS_VIEW),
    ("/discovery", workspaces.OPERATIONS_VIEW),
    ("/reporting/cohorts", workspaces.OPERATIONS_VIEW),
    ("/reporting/senders", workspaces.REPORTING_VIEW),
    ("/senders", workspaces.OPERATIONS_VIEW),
    ("/batches", workspaces.OPERATIONS_VIEW),
    ("/upload", workspaces.BATCH_CREATE),
    ("/icp", workspaces.CONTACTS_VIEW),
    ("/companies", workspaces.CONTACTS_VIEW),
    ("/segments", workspaces.CONTACTS_VIEW),
    ("/contacts", workspaces.CONTACTS_VIEW),
    ("/jobs", workspaces.OPERATIONS_VIEW),
    ("/outreach", workspaces.OPERATIONS_VIEW),
    ("/campaigns/new", workspaces.CAMPAIGN_CREATE),
    ("/signals", workspaces.CONTACTS_VIEW),
    ("/strategy", workspaces.OPERATIONS_VIEW),
    ("/campaigns", workspaces.OPERATIONS_VIEW),
    ("/approvals", workspaces.APPROVALS_REVIEW),
    ("/tasks", workspaces.OPERATIONS_VIEW),
    ("/replies/policy", workspaces.OPERATIONS_VIEW),
    # Before "/replies", which is a prefix of it.
    ("/replies/returns", workspaces.OPERATIONS_VIEW),
    ("/replies", workspaces.REPLIES_VIEW),
    ("/reporting", workspaces.REPORTING_VIEW),
    ("/compare", workspaces.REPORTING_VIEW),
    ("/simulator", workspaces.OPERATIONS_VIEW),
    ("/timezones", workspaces.OPERATIONS_VIEW),
    # Settings names the verification waterfall, the MX policy and the
    # provider mapping. That is the vendor stack, and a client-facing role has
    # no reason to learn it from a settings page.
    # Longest prefix first: the personas screen changes who is selected, so
    # it is the one settings surface a role that may only *read* operations
    # is not offered.
    ("/settings/personas", workspaces.WORKSPACE_MANAGE),
    ("/settings", workspaces.OPERATIONS_VIEW),
    ("/users", workspaces.USERS_MANAGE),
    ("/audit", workspaces.OPERATIONS_VIEW),
    # The notification log names event types, channels and provider warnings.
    # A workspace's own positive replies are in it, and so is every
    # operational alert tagged with that workspace, which is why this is the
    # operator's permission and not the one a client-facing role carries.
    ("/notifications", workspaces.OPERATIONS_VIEW),
    # Setup is the one operational screen a client-facing role may read: it
    # says what their workspace still needs, and nothing on it names a
    # supplier or a credit.
    ("/onboarding", workspaces.WORKSPACE_VIEW),
    ("/suppression", workspaces.CONTACTS_VIEW),
    # Search reads only workspaces the caller is a member of, through the
    # same Repo.for_user every other read uses, so the permission here is the
    # one that says "you may look at a workspace at all".
    ("/search", workspaces.WORKSPACE_VIEW),
    ("/diagnostics", workspaces.OPERATIONS_VIEW),
    ("/export/contacts.csv", workspaces.CONTACTS_EXPORT),
    ("/export/analytics.csv", workspaces.REPORTING_EXPORT),
    ("/export/analytics.json", workspaces.REPORTING_EXPORT),
    ("/", workspaces.WORKSPACE_VIEW),
)


def redact(line):
    """A log line with its query string removed.

    Everything after the first `?` up to the next space goes. That is
    the whole query, not a chosen subset of it: the parameter that
    leaked here was `code`, and the next one will have a name nobody
    thought to add to a list.
    """
    if "?" not in line:
        return line
    head, _, rest = line.partition("?")
    tail = rest.partition(" ")[2]
    return head + "?<redacted>" + ((" " + tail) if tail else "")


def permission_for(path):
    """The permission this path needs, or None if it needs only a session."""
    for prefix, permission in READ_PERMISSIONS:
        if path == prefix or (prefix != "/" and path.startswith(prefix + "/")):
            return permission
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "Resonate"
    sys_version = ""

    # ----------------------------------------------------------- plumbing

    # Query strings that must never reach the access log. The identity
    # provider sends the authorization code back *in the URL*, so the
    # default request-line log writes a live OAuth credential to stdout -
    # where a platform keeps it, indefinitely, for anyone who can read the
    # project's logs.
    #
    # Found in production: `GET /auth/callback?state=...&code=4/0ATsMZq...`
    # sitting in Railway's log store. PKCE makes that code useless to
    # whoever lifts it - the verifier never leaves this process, and the
    # code is single-use and was already spent - but "harmless when
    # stolen" is not a reason to write a credential down.
    #
    # The path is kept and the whole query dropped, rather than particular
    # parameters being redacted. `_refusal` below already made exactly
    # this decision for the audit log - "not the query string, not the
    # form, not the id that was reached for" - and a denylist of sensitive
    # names is one new parameter away from leaking again.

    def log_message(self, fmt, *args):
        if os.environ.get("WEB_QUIET"):
            return
        sys.stderr.write("  %s %s\n"
                         % (self.address_string(), redact(fmt % args)))

    def _session(self):
        cookie = self.headers.get("Cookie") or ""
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "rsid":
                return value, STATE["sessions"].get(value)
        return None, None

    def _ctx(self, session):
        mine = (workspaces.workspaces_for(session["email"])
                if session else [])
        return {
            "workspaces": [{"slug": w["slug"], "name": w["name"]} for w in mine],
            "workspace": (session or {}).get("workspace"),
            "email": (session or {}).get("email"),
            "role": security.role_of(session) if session else None,
            "permissions": (workspaces.permissions_of(security.role_of(session))
                            if session else []),
            "csrf": (session or {}).get("csrf"),
            "demo": STATE["demo"],
            "super_admin": bool(
                session and (workspaces.user(session["email"]) or {})
                .get("super_admin")),
        }

    def _repo(self, session):
        """Scoped by membership. A slug in a URL never reaches this."""
        workspace = (session or {}).get("workspace")
        if not workspace:
            redirect("/workspaces")
        return repo_module.Repo.for_user(session["email"], workspace)

    def _send(self, status, body, content_type="text/html; charset=utf-8",
              headers=()):
        payload = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(int(status))
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        # A browser is a hostile rendering environment for text that came off
        # a crawl. These are cheap and they close the classes of mistake a
        # template author makes on a Friday.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; form-action 'self'; base-uri 'none'; "
            "frame-ancestors 'none'")
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _page(self, body, session, path, title="Control Center", status=200):
        self._send(status, pages.shell(body, session, self._ctx(session),
                                       path=path, title=title))

    # ------------------------------------------------- Slack interactions

    def _slack_interaction(self):
        """Read the raw body, verify, apply, answer. No decisions here.

        The body is read raw rather than through `_form`, because the
        signature is computed over the exact bytes Slack sent and a parse and
        re-encode would not reproduce them.
        """
        length = int(self.headers.get("Content-Length") or 0)
        if length > SLACK_MAX_BODY:
            # Slack interaction payloads are a few kilobytes. Something this
            # size is not one, and it is refused without being parsed.
            #
            # It is still *drained* first, up to a bound. A response written
            # while the client is mid-upload arrives on a socket the client
            # is not reading yet, and it sees the close as a connection
            # reset rather than as the 413 - so the refusal it was given is
            # the one message it never receives. Draining is what makes the
            # status code reach the sender.
            #
            # Bounded, because the whole point was not to read an unbounded
            # body. A sender that ignores the limit by an order of magnitude
            # gets the close instead, which is the outcome it chose.
            remaining = min(length, SLACK_DRAIN_LIMIT)
            while remaining > 0:
                # Exactly what was declared, never more: `read(n)` on a
                # socket blocks until it has n bytes, so asking for a round
                # chunk past the end of the body waits for a sender that has
                # already finished.
                chunk = self.rfile.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
            raise Handled(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                          "payload too large", "text/plain; charset=utf-8")
        body = self.rfile.read(max(0, length)).decode("utf-8", "replace")
        timestamp, signature = interactions.headers_from(self.headers)

        try:
            result = interactions.handle(body, timestamp, signature)
        except interactions.Rejected as e:
            reason = str(e)
            if reason.startswith("signature:"):
                # Nothing about this request has been trusted yet, so nothing
                # about it is described back. A forged payload learns that it
                # was refused and not which of the three checks refused it.
                raise Handled(HTTPStatus.UNAUTHORIZED, "unauthorised",
                              "text/plain; charset=utf-8")
            # Past verification this is a real person who pressed a real
            # button, and the useful answer is why it did not work. 200
            # because none of these is retryable and a non-2xx asks Slack to
            # deliver the same click again.
            raise Handled(HTTPStatus.OK, reason,
                          "text/plain; charset=utf-8")
        except Exception:
            # An unexpected fault must not answer 500 to Slack, which would
            # redeliver the click and re-run whatever half-happened.
            traceback.print_exc()
            raise Handled(HTTPStatus.OK,
                          "something went wrong handling that; nothing was "
                          "changed", "text/plain; charset=utf-8")

        raise Handled(HTTPStatus.OK, _slack_answer(result),
                      "text/plain; charset=utf-8")

    def _form(self):
        """The submitted form. Refuses a request that cannot arrive whole."""
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}, {}
        ctype = self.headers.get("Content-Type") or ""
        # Refused whole rather than read short.
        #
        # This read `min(length, MAX_BYTES + 4096)` and dropped the rest on
        # the floor, and nothing compared what arrived against what was
        # announced. `upload.parse` re-checks the size, so the loss was
        # caught only while the surviving CSV was still over `MAX_BYTES` -
        # a margin of 4096 bytes minus the multipart framing, which is
        # about 3.5KB. The `notes` field on the upload form has no
        # `maxlength`, so a long note eats that margin and the truncated
        # file then passes the size check.
        #
        # Measured: a 300,000 row, 77MB export with a 5,000 character note
        # was accepted as 32,893 rows. The preview said "32,893 uploaded,
        # 0 invalid", the button offered to import 32,893 companies, and
        # the audit entry recorded 32,893 - because 32,893 is what
        # survived the socket read, and nothing anywhere knew that was not
        # the number in the file. 267,107 rows disappeared with no trace
        # but a single ragged row.
        #
        # "Never silently discard meaningful imported data" is the rule
        # this broke, and the announced length is enough to refuse on
        # before a byte is read.
        if length > upload.MAX_BYTES + 4096:
            raise PayloadTooLarge(
                f"this request is {length // (1024 * 1024)}MB, over the "
                f"{upload.MAX_BYTES // (1024 * 1024)}MB limit. Nothing was "
                "read: a request that cannot arrive whole is refused rather "
                "than truncated, because a short read looks exactly like a "
                "smaller file")
        raw = self.rfile.read(min(length, upload.MAX_BYTES + 4096))
        if len(raw) < length:
            raise PayloadTooLarge(
                f"only {len(raw)} of {length} announced bytes arrived. "
                "Refused rather than imported short")
        if ctype.startswith("multipart/form-data"):
            # `cgi.FieldStorage` was removed in Python 3.13 and this repository
            # takes no third-party dependencies, so `upload.parse_multipart`
            # handles the one shape a browser form actually sends.
            return upload.parse_multipart(raw, ctype)
        # `keep_blank_values=True` because a field a person *cleared* is a
        # field they submitted. Without it `parse_qs` drops it, the handler
        # never sees it, and "remove this cap" silently means "leave it".
        # It also means a request carrying `sendable=` is refused by
        # `refuse_client_verdicts` rather than quietly ignored, which is the
        # behaviour that module promises.
        parsed = urllib.parse.parse_qs(raw.decode("utf-8", "replace"),
                                       keep_blank_values=True)
        fields = {k: v[0] for k, v in parsed.items()}
        # A checkbox group and a multi-select send one name many times, and
        # `v[0]` throws all but the first away - which for a report's section
        # list means silently generating a different document from the one
        # somebody ticked.
        #
        # The extra keys are suffixed rather than replacing `fields`, and only
        # added where there really is more than one value. Handlers that scan
        # this dict by prefix - `policy:` on the settings form - would treat an
        # unconditional companion key as an invented setting and refuse the
        # whole submission.
        for key, values in parsed.items():
            if len(values) > 1:
                fields[key + LIST_SUFFIX] = values
        return fields, {}

    # ------------------------------------------------------------ routing

    def do_GET(self):
        self._route("GET")

    def do_HEAD(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def _route(self, method):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = {k: v[0] for k, v in
                 urllib.parse.parse_qs(parsed.query).items()}
        token, session = self._session()

        try:
            self._dispatch(method, path, query, token, session)
        except Handled as done:
            self._send(done.status, done.body, done.content_type, done.headers)
        except repo_module.CrossClientAccess as e:
            # 404, not 403. Telling a caller that an object exists but belongs
            # to somebody else is itself a disclosure.
            #
            # And the body must not say it either, which is what this used
            # to do: `str(e)` is "record 'x' belongs to another client and
            # is not readable here", printed on the page. An unknown id
            # renders "No such company"; a real one from another workspace
            # rendered the sentence above. Two different answers is an
            # oracle, and record ids are a deterministic function of the
            # domain, so the question it answers is "is this company on
            # another Resonate client's target list?" - askable for any
            # domain, by any member of any workspace.
            #
            # The reason still reaches the refusal log, where it belongs:
            # an operator investigating needs to know it was a tenancy
            # refusal rather than a typo. The person who asked does not.
            self._refusal(session, method, path, "cross_workspace", e)
            self._page(pages.empty("Not found", ""), session, path,
                       status=404)
        except PayloadTooLarge as e:
            self._refusal(session, method, path, "payload_too_large", e)
            self._page(pages.empty("That upload is too large", str(e)),
                       session, path, status=413)
        except repo_module.UnknownClient as e:
            self._refusal(session, method, path, "unknown_client", e)
            self._page(pages.empty("Unknown client", str(e)), session, path,
                       status=404)
        except workspaces.NotAMember as e:
            # 404, not 403. "Exists but is not yours" is itself a disclosure,
            # so a forged workspace slug and a real one a user is not in are
            # indistinguishable from outside.
            self._refusal(session, method, path, "not_a_member", e)
            self._page(pages.empty("Not found", str(e)), session, path,
                       status=404)
        except (security.Refused, workspaces.NotPermitted) as e:
            self._refusal(session, method, path, "refused", e)
            self._page(pages.empty("Refused", str(e)), session, path,
                       status=403)
        except Exception as e:                    # noqa: BLE001 - the last net
            if os.environ.get("WEB_DEBUG"):
                traceback.print_exc()
            self._page(
                pages.empty("Something went wrong",
                            f"{type(e).__name__}. Nothing was changed."),
                session, path, status=500)

    def _refusal(self, session, method, path, kind, error):
        """Write down that a request was refused, and why.

        A refusal that leaves no trace is a refusal nobody can review. Somebody
        walking record ids looking for one that answers 200 is the shape this
        exists to make visible, and it is invisible if the only evidence is a
        status code the attacker also has.

        What is recorded is who, when, which workspace, which path and which
        class of refusal. Not the query string, not the form, not the id that
        was reached for: an attacker who can choose what goes in your log has
        been handed a second tool. The path is enough to see the pattern.

        Failing to log must never turn a refusal into a 500, so this swallows
        its own errors: the refusal is the point, the record of it is not worth
        losing the refusal over.
        """
        try:
            workspaces.record(
                (session or {}).get("email") or "anonymous",
                (session or {}).get("workspace"),
                "security.refused",
                resource_type="request",
                resource_id=f"{method} {path}"[:120],
                metadata={"kind": kind, "error": type(error).__name__},
                reason=str(error)[:200])
        except Exception:                          # noqa: BLE001
            pass

    def _dispatch(self, method, path, query, token, session):
        # ---- assets and health, no session needed
        if path == "/assets/app.css":
            raise Handled(200, assets.CSS, "text/css; charset=utf-8",
                          [("Cache-Control", "public, max-age=86400")])
        if path == "/assets/app.js":
            raise Handled(200, assets.JS,
                          "application/javascript; charset=utf-8",
                          [("Cache-Control", "public, max-age=86400")])
        if path == "/healthz":
            raise Handled(200, json.dumps({
                "ok": True, "demo": STATE["demo"], "live_sending": False,
                "sessions": STATE["sessions"].count()}),
                "application/json; charset=utf-8")

        # ---- Slack interactions
        #
        # `src/interactions.py` has verified, deduplicated and applied a Slack
        # button click since it was written, and its docstring says what it
        # needs: "whatever eventually terminates the request should read the
        # raw body and three headers, call handle(), and return its status".
        # Nothing did. Every approval notification `notify.py` builds carries
        # Approve / Reject / Hold buttons, and the URL a Slack app would post
        # them to did not exist - so the buttons were an interface with no
        # other side, and the failure would have surfaced as a client
        # clicking Approve and nothing happening.
        #
        # Placed here, above the session gate, because Slack has no cookie and
        # no CSRF token. It authenticates with an HMAC over the raw body,
        # which `handle()` checks before it parses a single field. That is a
        # stronger check than a session, not a weaker one - but it is a
        # different one, so this is the only path in the application that
        # skips both, and it is deliberately three lines from the routing
        # table where anyone auditing can see it.
        if path == SLACK_INTERACTIONS_PATH:
            if method != "POST":
                raise Handled(HTTPStatus.METHOD_NOT_ALLOWED, "POST only",
                              "text/plain; charset=utf-8")
            return self._slack_interaction()

        # ---- sign in
        #
        # Which mechanism answers here is decided by `AUTH_PROVIDER` and by
        # nothing on the request. Both branches end at `_establish`, so
        # whatever proved the address, what happens next - which workspaces
        # it may enter, which one the session starts in - is resolved the
        # same way from the same table.
        mode = security.sign_in_mode()

        if path == "/login":
            if mode == security.OIDC_SIGN_IN:
                if method == "POST":
                    # The demo form does not exist on this build's sign-in
                    # page, so a POST here is somebody who kept an old page
                    # open or is trying the mechanism by hand. Refused
                    # rather than ignored.
                    raise Handled(405, pages.provider_login_page(
                        error="This deployment signs in with an identity "
                              "provider. There is no password form to post "
                              "to."))
                raise Handled(200, pages.provider_login_page())
            if method == "POST":
                return self._login()
            raise Handled(200, pages.login_page(workspaces.users()))

        if path == "/auth/start":
            if mode != security.OIDC_SIGN_IN:
                raise Handled(404, pages.login_page(
                    workspaces.users(),
                    error="No identity provider is configured."))
            return self._auth_start()

        if path == "/auth/callback":
            if mode != security.OIDC_SIGN_IN:
                raise Handled(404, pages.login_page(
                    workspaces.users(),
                    error="No identity provider is configured."))
            return self._auth_callback(query)

        if path == "/logout":
            STATE["sessions"].destroy(token)
            raise Handled(HTTPStatus.SEE_OTHER, "",
                          headers=[("Location", "/login"),
                                   ("Set-Cookie",
                                    security.session_cookie(None,
                                                            clearing=True))])

        if not session:
            redirect("/login")

        if method == "POST":
            fields, files = self._form()
            security.check_csrf(session, fields.get("csrf"))
            security.refuse_client_verdicts(fields)
            return self._post(path, fields, files, token, session)

        return self._get(path, query, session, token)

    # ------------------------------------------------------------- reads

    def _get(self, path, query, session, token=None):
        # Two surfaces exist before a workspace does. `/workspaces` is how a
        # user with no current workspace picks one, and `/admin` is explicitly
        # not scoped to any.
        if path == "/select-workspace":
            # A GET here is the workspace card's "Enter" link. It only ever
            # *reads* which workspace the session points at next, and the
            # membership check below is the same one the POST does - a slug in
            # a query string reaches `Repo.for_user` and no further.
            slug = query.get("to")
            repo_module.Repo.for_user(session["email"], slug)
            STATE["sessions"].set_workspace(token, slug)
            redirect("/")
        if path == "/workspaces":
            return self._page(
                pages.workspace_list(
                    *self._workspace_list_args(session)),
                session, path, "Workspaces")
        if path == "/admin":
            self._require_super_admin(session)
            return self._page(pages.admin(api.admin_overview()), session, path,
                              "Admin")
        if path == "/admin/health":
            self._require_super_admin(session)
            return self._page(pages.system_health(api.system_health()),
                              session, path, "System health")
        if path == "/admin/slack":
            # The only screen that reads every workspace's Slack routing at
            # once. Guarded the same way `/admin` is, and for the same reason:
            # a table of other clients' channel names is a cross-tenant read
            # however harmless each individual row looks.
            self._require_super_admin(session)
            return self._page(pages.slack_admin(api.slack_overview()), session,
                              path, "Slack operations")

        needed = permission_for(path)
        if needed:
            # Before the handler, not inside it. A refusal here cannot be
            # skipped by a handler that forgot to ask.
            security.require(session, needed)

        repo = self._repo(session)

        if path == "/":
            # `operations.view` is the line between the people who run the
            # machine and the people it is run for. A viewer gets the outcome;
            # the vendor names, the credit exposure and the job queue are not
            # theirs to see.
            simple = not security.may(session, workspaces.OPERATIONS_VIEW)
            return self._page(
                pages.dashboard(api.dashboard(repo), simple,
                                slack=api.workspace_slack(repo)),
                session, path, "Dashboard")
        if path == "/batches":
            return self._page(pages.batch_list(api.batch_list(repo)),
                              session, path, "Batches")
        if path.startswith("/batches/"):
            batch = path.split("/", 2)[2]
            return self._page(
                pages.batch_detail(api.batch_detail(repo, batch),
                                   api.preflight(repo, batch)),
                session, path, f"Batch {batch}")
        if path == "/upload":
            return self._page(
                pages.upload_form(session["csrf"], repo.workspace),
                session, path, "New batch")
        if path == "/companies":
            filters = {k: v for k, v in query.items()
                       if k in ("region", "vertical", "icp_status", "icp_tier",
                                "employee_band", "country")}
            rows = api.company_rows(repo, query.get("batch"), filters or None)
            # One page of rows. The list assembles in well under a second
            # at thirty thousand records; it is the rendering that falls
            # over, so the window is applied here rather than deeper.
            page = api.paginate(rows, query.get("page"))
            return self._page(
                pages.company_list(page["rows"], query.get("batch"),
                                   page=page),
                session, path, "Companies")
        if path.startswith("/companies/"):
            record_id = path.split("/", 2)[2]
            detail = api.company_dossier(repo, record_id)
            if detail is None:
                return self._page(pages.empty("No such company", record_id),
                                  session, path, status=404)
            return self._page(pages.company_dossier(detail), session, path,
                              detail.get("company") or record_id)
        if path == "/icp":
            return self._page(
                pages.icp_review(
                    api.icp_queue(repo, query.get("status") or None,
                                  query.get("batch") or None,
                                  query.get("decided") or None),
                    session["csrf"]),
                session, path, "ICP review")
        if path == "/segments":
            rows = api.company_rows(repo)
            return self._page(
                pages.segment_explorer(api.segment_tree(repo), len(rows),
                                       api.segment_health(repo)),
                session, path, "Segments")
        if path == "/contacts":
            rows = api.contact_rows(repo, query.get("batch"),
                                    query.get("mode") or None,
                                    query.get("flag") or None)
            page = api.paginate(rows, query.get("page"))
            return self._page(
                pages.contact_list(page["rows"], query.get("mode"),
                                   query.get("flag"), page=page),
                session, path, "Contacts")
        if path.startswith("/contacts/"):
            parts = path.split("/")
            if len(parts) < 4:
                return self._page(pages.empty("Not found", path), session,
                                  path, status=404)
            record_id, contact_key = parts[2], parts[3]
            view = api.contact_view(repo, record_id, contact_key)
            if view is None:
                return self._page(pages.empty("No such contact", contact_key),
                                  session, path, status=404)
            out = api.outreach(repo, record_id, contact_key)
            return self._page(pages.contact_detail(view, out), session, path,
                              view.get("name") or contact_key)
        if path == "/global":
            return self._page(
                pages.global_overview(api.global_overview(session["email"]),
                                      session["csrf"]),
                session, path, "All workspaces")
        if path == "/global/reporting":
            return self._page(
                pages.global_comparison(
                    api.global_comparison(session["email"],
                                          query.get("metric")
                                          or "positive_replies")),
                session, path, "Global reporting")
        if path == "/reporting/senders":
            return self._page(
                pages.sender_report(
                    api.sender_report(
                        repo,
                        query.get("dimension") or "sender_pair")),
                session, path, "Reporting by sender")
        if path == "/senders":
            return self._page(
                pages.senders_page(
                    api.sender_roster(repo), session["csrf"],
                    security.may(session, workspaces.WORKSPACE_MANAGE),
                    query.get("tab") or "overview")
                + pages.sender_assignments(api.sender_assignments(repo)),
                session, path, "Senders")
        if path == "/jobs":
            return self._page(
                pages.jobs_page(api.job_rows(repo, query.get("batch") or None),
                                session["csrf"]),
                session, path, "Batch processing")
        if path == "/outreach":
            return self._page(
                pages.full_outreach(
                    api.full_outreach(repo, query.get("campaign") or None)),
                session, path, "Full outreach preview")
        if path == "/campaigns/new":
            return self._page(
                pages.campaign_builder(
                    api.campaign_builder(repo, query.get("segment") or None,
                                         query.get("batch") or None),
                    session["csrf"]),
                session, path, "Campaign builder")
        if path == "/campaigns":
            return self._page(
                pages.campaign_list(
                    api.campaign_rows(repo), session["csrf"],
                    security.may(session, workspaces.CAMPAIGN_PAUSE)),
                session, path, "Campaigns")
        # Before the campaign-detail route: `/campaigns/experiments` is a
        # screen, not a campaign id, and the prefix match below would read
        # it as one.
        if path == "/discovery/review.csv":
            found = api.discovery_csv(repo)
            raise Handled(200, found["csv"], "text/csv; charset=utf-8",
                          headers=[("Content-Disposition",
                                    "attachment; filename=\""
                                    + found["filename"] + "\"")])
        if path == "/tasks":
            return self._page(
                pages.task_queue(api.task_queue(repo)),
                session, "/tasks", "Work queue")
        if path == "/revival":
            return self._page(
                pages.revival_view(api.revival_view(repo)),
                session, "/revival", "Revival")
        if path == "/replies/returns":
            return self._page(
                pages.returns_view(api.returns_view(repo)),
                session, "/replies/returns", "Out-of-office returns")
        if path == "/refresh":
            return self._page(
                pages.refresh_plan(api.refresh_plan(repo)),
                session, "/refresh", "Refresh plan")
        if path == "/health":
            return self._page(
                pages.operational_health(api.operational_health(repo)),
                session, "/health", "Operational health")
        if path == "/audience":
            return self._page(
                pages.audience_overview(
                    api.audience_overview(repo, query.get("batch"))),
                session, "/audience", "Audience")
        if path == "/discovery":
            return self._page(pages.discovery_view(api.discovery_view(repo)),
                              session, "/discovery", "Discovery")
        if path == "/reporting/cohorts":
            return self._page(
                pages.cohort_performance(
                    api.cohort_performance(
                        repo, [query["dimension"]] if query.get("dimension")
                        else None)),
                session, "/reporting/cohorts", "Cohort performance")
        if path == "/strategy":
            return self._page(
                pages.strategy_centre(api.strategy_centre(repo),
                                      session["csrf"]),
                session, "/strategy", "Strategy")
        if path == "/signals":
            return self._page(
                pages.signal_dashboard(
                    api.signal_dashboard(repo, query.get("tier"))),
                session, "/signals", "Account intelligence")
        if path == "/campaigns/experiments":
            return self._page(
                pages.campaign_experiments(
                    api.campaign_experiments(repo, query.get("campaign"),
                                             demo=STATE["demo"])),
                session, "/campaigns/experiments", "Copy experiments")
        if path.startswith("/campaigns/"):
            campaign_id = path.split("/", 2)[2]
            detail = api.campaign_detail(repo, campaign_id)
            if detail is None:
                return self._page(pages.empty("No such campaign", campaign_id),
                                  session, path, status=404)
            preview = pages.provider_previews(
                api.provider_preview(repo, campaign_id))
            return self._page(pages.campaign_detail(detail, preview), session,
                              path, detail["campaign"].get("name"))
        if path == "/approvals/plan":
            return self._page(
                pages.campaign_plan_qa(
                    api.campaign_plan_qa(repo, query.get("campaign"),
                                         query.get("template"))),
                session, "/approvals", "Plan review")
        if path == "/approvals":
            return self._page(
                pages.approvals(api.approval_queue(repo), session["csrf"],
                                security.may(session, workspaces.CAMPAIGN_APPROVE)),
                session, path, "Approvals")
        if path == "/replies":
            inbox = api.reply_inbox(repo, query.get("kind") or None,
                                    carries=query.get("carries") or None)
            return self._page(
                pages.replies(inbox["rows"], query.get("kind"),
                              api.slack_previews(repo), session["csrf"],
                              security.may(session, workspaces.REPLIES_MANAGE),
                              data=inbox),
                session, path, "Inbox")
        if path == "/reporting":
            dimensions = self._dimensions(session)
            filters = {f: query.get(f) for f, _ in dimensions if query.get(f)}
            data = api.analytics(repo, query.get("dimension"), filters,
                                 dimensions)
            simple = not security.may(session, workspaces.OPERATIONS_VIEW)
            body = pages.reporting(api.reporting(repo), simple=simple)
            if not simple:
                body += pages.analytics(
                    data, session["csrf"],
                    can_export=security.may(session,
                                            workspaces.REPORTING_EXPORT))
            return self._page(body, session, path, "Reporting")
        if path == "/search":
            return self._page(
                pages.search(api.search(session["email"], query.get("q"),
                                        query.get("workspace"))),
                session, path, "Search")
        if path == "/suppression":
            return self._page(pages.suppression(api.suppression(repo)),
                              session, path, "Suppression")
        if path == "/outreach/accounts":
            return self._page(
                pages.account_list(api.account_rows(repo,
                                                    query.get("batch"))),
                session, path, "Accounts")
        if path == "/outreach/cadence":
            return self._page(
                pages.cadence_view(api.cadence_view(repo,
                                                    query.get("campaign"),
                                                    query.get("template"))),
                session, path, "Cadence")
        if path.startswith("/outreach/contact/"):
            parts = path.split("/", 5)
            record_id = urllib.parse.unquote(parts[3])
            contact_key = urllib.parse.unquote(parts[4]) if len(parts) > 4 \
                else ""
            view = api.contact_outreach(repo, record_id, contact_key,
                                        query.get("campaign"))
            if view is None:
                return self._page(
                    pages.empty("No such contact", contact_key),
                    session, "/outreach/accounts", "Contact", status=404)
            return self._page(pages.contact_outreach(view), session,
                              "/outreach/accounts", "Contact")
        if path.startswith("/outreach/account/"):
            record_id = urllib.parse.unquote(path.split("/", 3)[3])
            view = api.account_view(repo, record_id, query.get("campaign"))
            if view is None:
                # 404 rather than 403: an account id from another workspace
                # must not be distinguishable from one that never existed.
                return self._page(pages.empty("No such account", record_id),
                                  session, "/outreach/accounts", "Accounts",
                                  status=404)
            view["signal_form"] = api.signal_form(repo, record_id)
            view["csrf"] = session["csrf"]
            return self._page(pages.account_view(view), session,
                              "/outreach/accounts", "Account")
        if path == "/onboarding":
            return self._page(pages.onboarding(api.onboarding(repo)),
                              session, path, "Workspace setup")
        if path == "/replies/policy":
            return self._page(pages.reply_policies(api.reply_policies(repo)),
                              session, path, "Reply policy")
        if path.startswith("/replies/context/"):
            parts = path.split("/", 5)
            view = api.reply_context(repo, urllib.parse.unquote(parts[3]),
                                     urllib.parse.unquote(parts[4])
                                     if len(parts) > 4 else "")
            if view is None:
                return self._page(pages.empty("No such reply", path),
                                  session, "/replies", "Replies", status=404)
            return self._page(pages.reply_context(view, session["csrf"]),
                              session, "/replies", "Reply")
        if path == "/reporting/editor":
            view = api.report_editor(repo, query.get("draft"))
            if view is None:
                return self._page(pages.empty("No such draft",
                                              query.get("draft")),
                                  session, "/reporting/editor",
                                  "Report editor", status=404)
            return self._page(pages.report_editor(view, session["csrf"]),
                              session, path, "Report editor")
        if path == "/reporting/editor/export":
            row, raw = api.render_draft(repo, query.get("draft"),
                                        by=session["email"],
                                        demo=STATE["demo"])
            if row is None:
                return self._page(pages.empty("No such draft",
                                              query.get("draft")),
                                  session, "/reporting/editor",
                                  "Report editor", status=404)
            if raw is None:
                return self._page(
                    pages.empty("Report could not be rendered",
                                row.get("error") or "unknown error"),
                    session, "/reporting/editor", "Report editor", status=500)
            raise Handled(200, raw, "application/pdf",
                          [("Content-Disposition",
                            'attachment; filename="%s"'
                            % api.report_filename(repo, row))])
        if path == "/reporting/client":
            return self._page(
                pages.client_reports(api.client_reports(repo),
                                     session["csrf"]),
                session, path, "Client reports")
        if path == "/reporting/client/download":
            # Re-rendered rather than served from a stored file. The PDF is a
            # pure function of the data and the settings, so regenerating is
            # both possible and more honest than handing back bytes that
            # would keep looking authoritative after the numbers behind them
            # were corrected.
            row = api.report_row(repo, query.get("id"))
            if row is None:
                # 404 rather than 403: a report id belonging to another
                # workspace must not be distinguishable from one that does
                # not exist.
                return self._page(pages.empty("No such report",
                                              query.get("id")),
                                  session, "/reporting/client",
                                  "Client reports", status=404)
            fresh, raw = api.regenerate_report(repo, row,
                                               by=session["email"],
                                               demo=STATE["demo"])
            if raw is None:
                return self._page(
                    pages.empty("Report could not be rebuilt",
                                fresh.get("error") or "unknown error"),
                    session, "/reporting/client", "Client reports",
                    status=500)
            raise Handled(200, raw, "application/pdf",
                          [("Content-Disposition",
                            'attachment; filename="%s"'
                            % api.report_filename(repo, row))])
        if path == "/compare":
            return self._page(
                pages.comparison(api.comparison(repo, query.get("dimension"),
                                                query.get("left"),
                                                query.get("right"),
                                                self._dimensions(session))),
                session, path, "Compare")
        if path == "/settings/personas":
            return self._page(
                pages.workspace_personas(api.personas_view(repo),
                                         session["csrf"],
                                         error=query.get("error")),
                session, path, "Personas")
        if path == "/settings":
            return self._page(
                pages.workspace_settings(
                    api.workspace_settings(repo),
                    security.may(session, workspaces.PROVIDER_SETTINGS_VIEW),
                    session["csrf"]),
                session, path, "Settings")
        if path == "/users":
            return self._page(
                pages.workspace_users(
                    api.workspace_people(repo), session["csrf"],
                    security.may(session, workspaces.USERS_MANAGE),
                    result=query.get("result")),
                session, path, "Users")
        if path == "/audit":
            # Scoped to this workspace. `?scope=all` widens it to every
            # workspace and to the account-level entries that belong to none -
            # and it is the super-admin check, not the query parameter, that
            # decides whether that happens. A parameter that widens a scope on
            # its own is not a parameter, it is the vulnerability.
            person = workspaces.user(session["email"]) or {}
            everything = (query.get("scope") == "all"
                          and bool(person.get("super_admin")))
            scope = None if everything else repo.workspace
            return self._page(
                pages.audit_log(api.audit_entries(scope), scope,
                                may_widen=bool(person.get("super_admin")),
                                total=api.audit_total(scope)),
                session, path, "Audit log")
        if path == "/notifications":
            # Scoped to this workspace, and `?scope=all` widens it only for a
            # super admin - the same shape as `/audit`, deliberately. A
            # parameter that widens a scope on its own is not a parameter.
            person = workspaces.user(session["email"]) or {}
            everything = (query.get("scope") == "all"
                          and bool(person.get("super_admin")))
            return self._page(
                pages.slack_notifications(
                    api.notification_history(None if everything else repo,
                                             query.get("type"),
                                             query.get("status")),
                    may_widen=bool(person.get("super_admin")),
                    # The scenario board names every workspace's channel,
                    # because showing that the same event reaches two
                    # different rooms is the whole point of it. That makes it
                    # a cross-tenant read, so it is offered only where every
                    # other cross-tenant read is: the unscoped view, to a
                    # super admin. A demo is not a reason to widen a scope.
                    demo=(api.slack_demo()
                          if STATE["demo"] and everything else None)),
                session, path, "Notifications")
        if path == "/export/contacts.csv":
            repo.audit("export.contacts", "workspace", repo.workspace,
                       metadata={"format": "csv"})
            api.announce_report(repo, "contacts.csv", session["email"],
                                batch=query.get("batch"), at=store.now())
            raise Handled(200, api.export_contacts(repo, query.get("batch")),
                          "text/csv; charset=utf-8",
                          [("Content-Disposition",
                            'attachment; filename="contacts.csv"')])
        if path == "/export/analytics.csv":
            dimensions = self._dimensions(session)
            filters = {f: query.get(f) for f, _ in dimensions if query.get(f)}
            repo.audit("export.analytics", "workspace", repo.workspace,
                       metadata={"format": "csv",
                                 "dimension": query.get("dimension")})
            api.announce_report(repo, "breakdown.csv", session["email"],
                                dimension=query.get("dimension"),
                                at=store.now())
            raise Handled(200,
                          api.export_analytics(repo, query.get("dimension"),
                                               filters, dimensions),
                          "text/csv; charset=utf-8",
                          [("Content-Disposition",
                            'attachment; filename="breakdown.csv"')])
        if path == "/export/analytics.json":
            dimensions = self._dimensions(session)
            filters = {f: query.get(f) for f, _ in dimensions if query.get(f)}
            repo.audit("export.analytics", "workspace", repo.workspace,
                       metadata={"format": "json"})
            api.announce_report(repo, "analytics.json", session["email"],
                                dimension=query.get("dimension"),
                                at=store.now())
            raise Handled(200, json.dumps(
                api.analytics(repo, query.get("dimension"), filters,
                              dimensions),
                indent=2, default=str),
                "application/json; charset=utf-8")
        if path == "/simulator":
            size = query.get("size")
            result = None
            if size:
                try:
                    result = api.simulation(min(int(size), 5000))
                except (TypeError, ValueError):
                    result = None
            return self._page(pages.simulator(result, size), session, path,
                              "Simulator")
        if path == "/timezones":
            return self._page(pages.timezones(api.timezone_preview(repo)),
                              session, path, "Timezones")
        if path == "/diagnostics":
            return self._page(pages.diagnostics(api.diagnostics(repo)),
                              session, path, "Diagnostics")

        return self._page(pages.empty("Not found", path), session, path,
                          status=404)

    # ------------------------------------------------------------ writes

    def _post(self, path, fields, files, token, session):
        if path == "/select-workspace":
            slug = fields.get("workspace")
            # Built through the membership check, so switching to a workspace
            # this user is not in is refused here rather than filtered later.
            repo_module.Repo.for_user(session["email"], slug)
            STATE["sessions"].set_workspace(token, slug)
            redirect("/")

        repo = self._repo(session)

        if path == "/strategy":
            try:
                api.record_decision(
                    repo, fields.get("area"), fields.get("decided"),
                    fields.get("why"), basis=fields.get("basis"),
                    evidence=fields.get("evidence"),
                    policy_key=fields.get("policy_key"),
                    supersedes=(fields.get("supersedes") or "").strip()
                    or None)
            except gtm.DecisionRefused as e:
                data = api.strategy_centre(repo)
                data["error"] = str(e)
                return self._page(
                    pages.strategy_centre(data, session["csrf"]),
                    session, "/strategy", "Strategy", status=400)
            redirect("/strategy")

        if path == "/signals":
            # The permission is asked inside `record_signal`, before it
            # reads anything - a refusal here must not depend on the
            # record having been found first.
            record_id = (fields.get("record_id") or "").strip()
            try:
                entry = api.record_signal(
                    repo, record_id,
                    (fields.get("type") or "").strip(),
                    fields.get("evidence"),
                    observed_at=fields.get("observed_at"),
                    confidence=(fields.get("confidence") or "").strip()
                    or None,
                    contact_key=(fields.get("contact_key") or "").strip()
                    or None,
                    source_ref=fields.get("source_ref"))
            except api.SignalRefused as e:
                view = api.account_view(repo, record_id)
                if view is None:
                    return self._page(
                        pages.empty("No such account", record_id),
                        session, "/outreach/accounts", "Accounts", status=404)
                view["signal_form"] = api.signal_form(repo, record_id)
                view["csrf"] = session["csrf"]
                view["signal_error"] = str(e)
                return self._page(pages.account_view(view), session,
                                  "/outreach/accounts", "Account", status=400)
            if entry is None:
                # Same 404 an unknown account gets on the read side: an id
                # from another workspace must not be distinguishable from
                # one that never existed.
                return self._page(pages.empty("No such account", record_id),
                                  session, "/outreach/accounts", "Accounts",
                                  status=404)
            redirect("/outreach/account/" + urllib.parse.quote(record_id))

        if path == "/upload":
            # The same permission the GET carries. Without it this handler
            # was an oracle: a viewer could POST a CSV of domains and read
            # back how many were suppressed, already present, or previously
            # engaged - workspace history, answered one upload at a time,
            # for the one role that may not see contacts at all.
            security.require(session, workspaces.BATCH_CREATE)
            data = files.get("csv")
            batch = (fields.get("batch") or "").strip()
            try:
                if not batch:
                    raise upload.UploadRefused("a batch name is required")
                # Scoped by `repo.records()`, which has already narrowed to
                # this workspace. The hygiene index never widens what it is
                # given, so a client's history cannot reach another's import.
                mine = repo.records()
                existing = {r.get("domain") for r in mine}
                parsed = upload.parse(
                    data, existing_domains=existing, batch=batch,
                    client=repo.client,
                    history=hygiene.index(mine, workspace=repo.workspace),
                    agency=agencydnc.Index(),
                    # This workspace's own waterfall, so the estimate is
                    # the bill this client would actually get.
                    policy=clients.verification_policy(repo.config()))
            except upload.UploadRefused as e:
                return self._page(
                    pages.upload_form(session["csrf"], repo.workspace,
                                      error=str(e)),
                    session, path, "New batch", status=400)
            STATE["uploads"][token] = parsed
            return self._page(
                pages.upload_form(session["csrf"], repo.workspace,
                                  result=parsed),
                session, path, "New batch")

        if path == "/upload/commit":
            security.require(session, workspaces.BATCH_CREATE)
            parsed = STATE["uploads"].get(token)
            if not parsed:
                return self._page(
                    pages.empty("Nothing to commit",
                                "Parse a CSV first; the preview expired."),
                    session, path, status=400)
            try:
                upload.commit(repo, parsed)
            except upload.UploadRefused as e:
                return self._page(
                    pages.empty("Nothing to commit", str(e)),
                    session, path, "New batch", status=400)
            STATE["uploads"].pop(token, None)
            redirect("/batches/" + urllib.parse.quote(parsed["batch"]))

        if path == "/workspaces/create":
            # Creating a workspace is not an action inside one, so it is
            # gated the way /admin is rather than by a workspace
            # permission - a workspace admin may run their own client, not
            # add somebody else's.
            self._require_super_admin(session)
            try:
                created = api.create_workspace(
                    fields.get("slug"), fields.get("name"),
                    fields.get("domain"), fields.get("booking_link"),
                    by=session["email"])
            except api.WorkspaceRefused as exc:
                return self._page(
                    pages.workspace_list(*self._workspace_list_args(session),
                                         error=str(exc)),
                    session, "/workspaces", "Workspaces", status=400)
            redirect("/workspaces?created="
                     + urllib.parse.quote(created["slug"]))

        if path == "/users/add":
            security.require(session, workspaces.USERS_MANAGE)
            email = (fields.get("email") or "").strip().lower()
            role = fields.get("role")
            if role == workspaces.SUPER_ADMIN:
                # Super admin is an account-level fact, not a role a workspace
                # admin can hand out from inside their own workspace.
                raise security.Refused(
                    "super_admin is not assignable from a workspace")
            try:
                # `invite` handles both halves: somebody already here gets
                # their role set, somebody who has never signed in gets a
                # pending invitation. Before this, the second case answered
                # "no such user" and there was no way to grant access to
                # anybody who had not already been turned away once.
                result = workspaces.invite(email, repo.workspace, role,
                                           actor=session["email"])
            except (workspaces.RoleNotAssignable, workspaces.NotAMember,
                    ValueError) as e:
                redirect("/users?result=error")
            redirect("/users?result=" + urllib.parse.quote(result["outcome"]))

        if path == "/users/revoke":
            security.require(session, workspaces.USERS_MANAGE)
            email = (fields.get("email") or "").strip().lower()
            # Scoped to this repo's workspace, so a slug in the form reaches
            # nothing: `repo.workspace` is resolved from the session.
            done = workspaces.revoke_invitation(email, repo.workspace,
                                                actor=session["email"])
            redirect("/users?result="
                     + ("revoked" if done else "nothing_to_revoke"))

        if path == "/users/role":
            security.require(session, workspaces.USERS_MANAGE)
            email = (fields.get("email") or "").strip().lower()
            role = fields.get("role")
            if role == workspaces.SUPER_ADMIN:
                raise security.Refused(
                    "super_admin is not assignable from a workspace")
            try:
                workspaces.assign(email, repo.workspace, role,
                                  actor=session["email"])
            except (workspaces.NoSuchUser, ValueError) as e:
                return self._page(
                    pages.empty("Not changed", str(e)), session, "/users",
                    "Users", status=400)
            redirect("/users")

        if path == "/campaigns/pause":
            security.require(session, workspaces.CAMPAIGN_PAUSE)
            return self._campaign_run_state(repo, fields, session, "pause")

        if path == "/campaigns/resume":
            security.require(session, workspaces.CAMPAIGN_PAUSE)
            return self._campaign_run_state(repo, fields, session, "resume")

        if path == "/replies/handle":
            security.require(session, workspaces.REPLIES_MANAGE)
            try:
                handled = api.handle_reply(
                    repo, fields.get("record_id"), fields.get("contact_key"),
                    fields.get("at"), by=session["email"],
                    note=fields.get("note") or "")
            except api.ActionRefused as e:
                return self._page(pages.empty("Not recorded", str(e)), session,
                                  "/replies", "Replies", status=409)
            if handled is None:
                return self._page(
                    pages.empty("No such reply", fields.get("record_id")),
                    session, "/replies", "Replies", status=404)
            redirect("/replies")

        if path == "/senders/reassign":
            security.require(session, workspaces.WORKSPACE_MANAGE)
            try:
                entry = api.reassign_sender(
                    repo, fields.get("record_id"), fields.get("contact_key"),
                    fields.get("channel"), fields.get("sender_id"),
                    by=session["email"], reason=fields.get("reason") or "")
            except (api.ReassignRefused, senderidentity.CrossWorkspaceSender,
                    senderidentity.UnknownSender) as e:
                return self._page(pages.empty("Not reassigned", str(e)),
                                  session, "/senders", "Senders", status=409)
            if entry is None:
                return self._page(
                    pages.empty("No such contact", fields.get("record_id")),
                    session, "/senders", "Senders", status=404)
            redirect("/senders")

        if path == "/reporting/editor/new":
            security.require(session, workspaces.REPORTING_EXPORT)
            draft = api.create_draft(
                repo, fields.get("template"), by=session["email"],
                period=fields.get("period") or None,
                campaigns=form_list(fields, "campaigns"))
            redirect("/reporting/editor?draft="
                     + urllib.parse.quote(draft["id"]))
        if path == "/reporting/editor/save":
            security.require(session, workspaces.REPORTING_EXPORT)
            narrative = {k.split(":", 1)[1]: v for k, v in fields.items()
                         if k.startswith("n:")}
            recommendations = []
            for key, value in sorted(fields.items()):
                if not key.startswith("r:"):
                    continue
                for line in str(value).split("\n"):
                    if line.strip():
                        recommendations.append({"kind": key.split(":", 1)[1],
                                                "text": line.strip()})
            try:
                updated = api.edit_draft(
                    repo, fields.get("draft"), by=session["email"],
                    narrative=narrative,
                    sections=form_list(fields, "sections"),
                    recommendations=recommendations)
            except reportdraft_module.DraftError as e:
                return self._page(pages.empty("Not saved", str(e)), session,
                                  "/reporting/editor", "Report editor",
                                  status=400)
            if updated is None:
                return self._page(pages.empty("No such draft",
                                              fields.get("draft")),
                                  session, "/reporting/editor",
                                  "Report editor", status=404)
            redirect("/reporting/editor?draft="
                     + urllib.parse.quote(updated["id"]))
        if path == "/reporting/editor/finalise":
            security.require(session, workspaces.REPORTING_EXPORT)
            draft = api.reportdraft.get(fields.get("draft"))
            if draft is None or draft.get("workspace") != repo.workspace:
                return self._page(pages.empty("No such draft",
                                              fields.get("draft")),
                                  session, "/reporting/editor",
                                  "Report editor", status=404)
            if draft.get("status") == api.reportdraft.FINAL:
                api.reportdraft.reopen(draft["id"], session["email"])
                repo.audit("report.draft_reopened", "report_draft",
                           draft["id"])
            else:
                api.finalise_draft(repo, draft["id"], session["email"])
            redirect("/reporting/editor?draft="
                     + urllib.parse.quote(draft["id"]))

        if path == "/reporting/client/generate":
            security.require(session, workspaces.REPORTING_VIEW)
            row, raw = api.generate_report(
                repo,
                template=fields.get("template"),
                sections=form_list(fields, "sections"),
                campaigns=form_list(fields, "campaigns"),
                since=fields.get("since") or None,
                until=fields.get("until") or None,
                by=session["email"], demo=STATE["demo"])
            if raw is None:
                return self._page(
                    pages.client_reports(api.client_reports(repo),
                                         session["csrf"], generated=row),
                    session, "/reporting/client", "Client reports",
                    status=500)
            raise Handled(200, raw, "application/pdf",
                          [("Content-Disposition",
                            'attachment; filename="%s"'
                            % api.report_filename(repo, row))])

        if path == "/settings/policy":
            security.require(session, workspaces.WORKSPACE_MANAGE)
            updates = {k.split(":", 1)[1]: v for k, v in fields.items()
                       if k.startswith("policy:")}
            try:
                api.update_policy(repo, updates, by=session["email"])
            except workspaces.NotOverridable as e:
                # Refused rather than clamped, and refused as a whole: a
                # half-applied policy is a workspace running under rules
                # nobody chose.
                return self._page(pages.empty("Not saved", str(e)), session,
                                  "/settings", "Settings", status=400)
            redirect("/settings")

        if path == "/replies/referral/add":
            # `batch.create` as well as `contacts.view`: this writes a
            # person into the account, which is the same authority as
            # importing one, not the authority to read a reply.
            security.require(session, workspaces.BATCH_CREATE)
            record_id = fields.get("record_id") or ""
            contact_key = fields.get("contact_key") or ""
            try:
                added = api.add_referred_contact(
                    repo, record_id, contact_key, fields.get("event_id"),
                    by=session["email"])
            except api.ActionRefused as e:
                return self._page(pages.empty("Not added", str(e)), session,
                                  "/replies", "Reply", status=400)
            if added is None:
                return self._page(
                    pages.empty("No such referral", fields.get("event_id")),
                    session, "/replies", "Reply", status=404)
            redirect(f"/replies/context/{urllib.parse.quote(record_id)}/"
                     f"{urllib.parse.quote(contact_key)}")

        if path == "/settings/personas/save":
            security.require(session, workspaces.WORKSPACE_MANAGE)
            try:
                api.save_persona(repo, fields.get("name"),
                                 fields.get("titles"), fields.get("cap"),
                                 fields.get("angles"), by=session["email"])
            except workspaces.NotOverridable as e:
                # Refused as a whole, like every other policy change: half a
                # persona is a targeting rule nobody chose.
                return self._page(
                    pages.workspace_personas(api.personas_view(repo),
                                             session["csrf"], error=str(e)),
                    session, "/settings/personas", "Personas", status=400)
            redirect("/settings/personas")

        if path == "/settings/personas/remove":
            security.require(session, workspaces.WORKSPACE_MANAGE)
            api.remove_persona(repo, fields.get("name"), by=session["email"])
            redirect("/settings/personas")

        if path == "/settings/mapping":
            security.require(session, workspaces.PROVIDER_SETTINGS_MANAGE)
            campaign = api.set_provider_mapping(
                repo, fields.get("campaign_id"), fields.get("bison"),
                fields.get("heyreach"), by=session["email"])
            if campaign is None:
                return self._page(
                    pages.empty("No such campaign", fields.get("campaign_id")),
                    session, "/settings", "Settings", status=404)
            redirect("/settings")

        if path == "/jobs/run":
            security.require(session, workspaces.BATCH_RUN)
            try:
                job = api.run_job(repo, fields.get("job_type"),
                                  fields.get("batch"), by=session["email"],
                                  job_id=fields.get("job_id") or None)
            except (api.JobRefused, jobs_module.JobError) as e:
                return self._page(pages.empty("Not run", str(e)), session,
                                  "/jobs", "Batch processing", status=400)
            if job is None:
                return self._page(pages.empty("No such job",
                                              fields.get("job_id")),
                                  session, "/jobs", "Batch processing",
                                  status=404)
            redirect("/jobs")

        if path == "/jobs/cancel":
            security.require(session, workspaces.BATCH_RUN)
            job = api.cancel_job(repo, fields.get("job_id"),
                                 by=session["email"])
            if job is None:
                return self._page(pages.empty("No such job",
                                              fields.get("job_id")),
                                  session, "/jobs", "Batch processing",
                                  status=404)
            redirect("/jobs")

        if path == "/campaigns/create":
            security.require(session, workspaces.CAMPAIGN_CREATE)
            try:
                campaign = api.create_campaign(
                    repo, fields.get("segment_key"), fields.get("name"),
                    fields.get("campaign_id"), by=session["email"],
                    batch=fields.get("batch") or None)
            except api.BuildRefused as e:
                return self._page(
                    pages.empty("Not created", str(e)), session,
                    "/campaigns/new", "Campaign builder", status=400)
            redirect("/campaigns/"
                     + urllib.parse.quote(campaign["campaign_id"]))

        if path == "/icp/decide":
            # `approvals.review` rather than `contacts.view`: reading the
            # queue and ruling on it are different acts, and this one is the
            # one that can unlock spending.
            security.require(session, workspaces.APPROVALS_REVIEW)
            try:
                review = api.decide_icp(
                    repo, fields.get("record_id"), fields.get("decision"),
                    fields.get("fingerprint"), by=session["email"],
                    note=fields.get("note") or "")
            except (api.ReviewRefused, qualify_module.BadDecision) as e:
                return self._page(
                    pages.empty("Not recorded", str(e)), session, "/icp",
                    "ICP review", status=409)
            if review is None:
                return self._page(
                    pages.empty("No such company", fields.get("record_id")),
                    session, "/icp", "ICP review", status=404)
            redirect("/icp")

        if path == "/approvals/campaign":
            security.require(session, workspaces.CAMPAIGN_APPROVE)
            return self._approve_campaign(repo, fields, session)

        return self._page(pages.empty("Not found", path), session, path,
                          status=404)

    def _campaign_run_state(self, repo, fields, session, action):
        """Pause or resume. Neither of these sends anything or starts sending.

        Resuming does not launch: `orchestrator.resume` re-runs every check and
        puts a campaign back into whatever state it was stopped from, and
        `push.run(live=True)` still raises underneath it.
        """
        run = api.pause_campaign if action == "pause" else api.resume_campaign
        kwargs = ({"why": fields.get("why") or ""} if action == "pause" else {})
        try:
            campaign = run(repo, fields.get("campaign_id"),
                           by=session["email"], **kwargs)
        except api.ActionRefused as e:
            return self._page(pages.empty(f"Not {action}d", str(e)), session,
                              "/campaigns", "Campaigns", status=409)
        if campaign is None:
            return self._page(
                pages.empty("No such campaign", fields.get("campaign_id")),
                session, "/campaigns", "Campaigns", status=404)
        redirect("/campaigns")

    def _dimensions(self, session):
        """Which breakdown dimensions this role may reach.

        A client-facing role gets the company dimensions only. The four it does
        not get name the vendor stack - which email-security gateway was found,
        which verifier confirmed an address, which provider supplied a contact
        - and a reporting dropdown is a strange place to publish a supplier
        list. Narrowed here rather than in the template, so a hand-typed query
        string does not reach them either.
        """
        if security.may(session, workspaces.OPERATIONS_VIEW):
            return api.DIMENSIONS
        return api.CLIENT_DIMENSIONS

    def _workspace_list_args(self, session):
        data = api.workspace_list(session["email"])
        person = workspaces.user(session["email"]) or {}
        return (data["workspaces"], session.get("workspace"),
                data["memberships"],
                security.may(session, workspaces.WORKSPACE_MANAGE),
                session["csrf"], bool(person.get("super_admin")))

    def _require_super_admin(self, session):
        """The one deliberate way across a workspace boundary."""
        person = workspaces.user(session["email"]) or {}
        if not person.get("super_admin"):
            # 404 rather than 403: a workspace user learning that an admin
            # console exists here is a disclosure with no upside.
            raise Handled(404, pages.shell(
                pages.empty("Not found", "/admin"), session,
                self._ctx(session), "/admin", "Not found"))
        return True

    def _approve_campaign(self, repo, fields, session):
        """Local approval only. No provider is touched by this.

        The fingerprint the form carried is sent back and the server
        recomputes and compares - that is what makes "approve" mean "approve
        this". A stale one is refused rather than applied.
        """
        from .. import orchestrator, roles

        campaign_id = fields.get("campaign_id")
        campaign = repo.campaign(campaign_id)
        if campaign is None:
            return self._page(pages.empty("No such campaign", campaign_id),
                              session, "/approvals", status=404)
        recs = [r for r in repo.records()
                if r["id"] in (campaign.get("record_ids") or [])]
        config = repo.config()
        action = fields.get("action", "approve")
        before = {"status": campaign.get("status"),
                  "approval": (campaign.get("approval") or {}).get("action")}
        try:
            orchestrator.request_approval(campaign, recs, config)
            result = orchestrator.decide(
                campaign, session["email"], action,
                fingerprint=fields.get("fingerprint"),
                interaction_id=f"web:{session["email"]}:{campaign_id}",
                config=config, recs=recs,
                # Deliberately the *lowest* engine role that carries approve
                # and reject, whatever the workspace role above it is. A
                # workspace admin approving a campaign needs
                # APPROVE_CAMPAIGN, not LAUNCH_CAMPAIGN, and handing out
                # `roles.ADMIN` here because the person happens to be one
                # would grant the launch permission this build exists to
                # withhold. `campaign.approve` was already required before
                # this handler ran; this says which engine permission that
                # buys, and it buys the minimum.
                role=roles.REVIEWER)
        except Exception as e:
            # A refused approval is written down too. "Somebody tried to
            # approve this and was not allowed to" is a thing a reviewer of
            # the audit log needs to be able to see, and it is exactly what is
            # invisible if only successes are recorded.
            repo.audit("campaign.approval_refused", "campaign", campaign_id,
                       before=before, after=before,
                       reason=f"{type(e).__name__}: {str(e)[:160]}")
            return self._page(
                pages.empty("Approval refused", f"{type(e).__name__}: {e}"),
                session, "/approvals", status=403)
        repo.save_campaign(campaign)

        # The most consequential action on this system, in the durable trail
        # rather than only in the campaign's own log. `orchestrator.decide`
        # writes the campaign log; this is the workspace's record of who
        # decided what, which is the one a super admin reads.
        status = result.get("status")
        repo.audit(
            "campaign.approval_stale" if status == "stale"
            else f"campaign.{'approved' if action == 'approve' else 'rejected'}",
            "campaign", campaign_id, before=before,
            after={"status": campaign.get("status"),
                   "approval": (campaign.get("approval") or {}).get("action"),
                   "result": status},
            reason=("the campaign changed after the page was rendered"
                    if status == "stale" else None),
            metadata={"fingerprint": campaign.get("fingerprint")})

        if status == "stale":
            return self._page(
                pages.empty("That approval was stale",
                            "The campaign changed after the page was rendered. "
                            "Reload and look again before approving."),
                session, "/approvals", status=409)
        redirect("/approvals")

    def _login(self):
        """Demo sign-in: pick a known user. Only reachable in demo mode.

        Nothing about what this person may do is taken from the form: the
        browser supplies who they claim to be, and every permission after
        that is resolved from the workspace membership table on the server.
        What the form *does* decide is who they are, which is exactly why
        this mechanism is unreachable the moment `AUTH_PROVIDER` is set.
        """
        fields, _ = self._form()
        email = (fields.get("email") or "").strip().lower()[:120]
        try:
            return self._establish(email)
        except NoSuchIdentity as e:
            raise Handled(e.status,
                          pages.login_page(workspaces.users(), error=str(e)))

    # ------------------------------------------------ the identity provider

    def _auth_start(self):
        """Mint a sign-in and send the browser to the provider.

        Nothing is trusted from the request - not a `next`, not a workspace,
        not an email. A redirect target taken from a query string is an open
        redirect, and one taken from a form is an invitation.
        """
        settings = security.auth_settings()
        try:
            document = oidc.discover(settings["issuer"])
            flow = STATE["pending"].start(oidc.begin())
            url = oidc.authorization_url(document, settings["client_id"],
                                         settings["redirect_url"], flow)
        except oidc.AuthError as e:
            return self._auth_failed(e)
        raise Handled(HTTPStatus.SEE_OTHER, "", headers=[("Location", url)])

    def _auth_callback(self, query):
        """The provider's answer, checked before anybody is anybody.

        Order matters and is deliberate. The state is claimed first, and
        claiming it consumes it, so a replayed callback finds nothing left
        even when every other field is perfect. The provider's own error is
        read only after that, for the same reason.
        """
        settings = security.auth_settings()

        flow = STATE["pending"].take(query.get("state"))
        if flow is None:
            return self._auth_failed(oidc.AuthError(
                "this sign-in did not start here, has already been used, or "
                "took too long"))

        if query.get("error"):
            # The provider declined - consent refused, account suspended.
            # Its wording goes to the log; the browser gets one sentence.
            return self._auth_failed(oidc.AuthError(
                "the provider refused: " + str(query.get("error"))[:80]))

        code = query.get("code")
        if not code:
            return self._auth_failed(oidc.AuthError("no authorization code"))

        try:
            document = oidc.discover(settings["issuer"])
            tokens = oidc.exchange(document, settings["client_id"],
                                   settings["client_secret"],
                                   settings["redirect_url"], code,
                                   flow["verifier"])
            proved = oidc.verified_email(
                document, settings["client_id"], tokens, flow,
                allowed_domains=settings["allowed_domains"])
        except oidc.AuthError as e:
            return self._auth_failed(e)

        try:
            return self._establish(proved["email"], subject=proved["subject"],
                                   proved=True)
        except NoSuchIdentity as e:
            # The provider proved an address this system has never heard of.
            # No account is created: `workspaces.jsonl` is the canonical
            # roster, and a directory that can add people to it is a
            # directory that decides who works here. The page says to ask an
            # administrator, and names nothing about who already has access.
            # The identity *was* proved. What is missing is a user row, and
            # that distinction is what the bootstrap below depends on.
            self._auth_note(workspaces.IDENTITY_PROVED, proved["email"],
                            "unknown_identity", str(e))
            # 403 for both shapes of this, and deliberately not `e.status`.
            # The demo form distinguishes "no such user" from "no workspace"
            # because you picked the address off a list it drew. Here the
            # address was proved, so nothing about the request was
            # malformed - it is a refusal, not a bad request - and the two
            # cases answering differently would tell whoever is holding a
            # valid Google account which addresses have a user row.
            raise Handled(403, pages.provider_login_page(
                error="You signed in successfully, but this account has no "
                      "access here. Ask a Resonate administrator to add it."))

    def _auth_failed(self, error):
        """One page, one sentence, and the detail only in the log.

        Which check failed is useful to an attacker and useless to the
        person: "nonce mismatch", "expired" and "wrong audience" all mean
        the same thing to somebody who should simply try again.
        """
        self._auth_note(workspaces.IDENTITY_REFUSED, None,
                        "provider_sign_in_failed", str(error))
        raise Handled(401, pages.provider_login_page(
            error="Sign-in could not be completed. Please try again."))

    def _auth_note(self, action, email, kind, detail):
        """A sign-in that leaves no trace is one nobody can review.

        The action is passed in rather than fixed. It was fixed, at
        `security.refused`, which meant a *successful* identity proof was
        written into the audit log labelled as a refusal - and
        `workspaces.proved_addresses`, which is what the first-administrator
        bootstrap reads, would have found nothing but refusals to choose
        from.
        """
        try:
            workspaces.record(email or "anonymous", None, action,
                              resource_type="sign_in", resource_id=kind,
                              metadata={"kind": kind},
                              reason=str(detail)[:200])
        except Exception:                              # noqa: BLE001
            pass

    # ------------------------------------------------------ one way through

    def _establish(self, email, subject=None, proved=False):
        """Turn a *proved* address into a session. The only place that does.

        Both mechanisms end here, so the two questions that decide access
        are asked once: is this a user this system knows, and which
        workspaces does the membership table say they may enter. Neither
        answer comes from the request in either mechanism - the demo form
        supplies an email and nothing else, and the provider supplies an
        email and nothing else.

        The session is created with `mine[0]`, resolved on the server, and
        it never carries a role: `security.membership` re-resolves that per
        request, so a membership removed a minute ago stops working now
        rather than at the next sign-in.
        """
        email = str(email or "").strip().lower()[:120]

        # A pending invitation becomes membership here and nowhere else,
        # and only for an address an identity provider has just proved.
        # `proved` is passed explicitly rather than inferred from `subject`,
        # which a provider is allowed to omit - and inferring it would mean
        # the demo form could claim an invitation by typing an address,
        # which is precisely what invitations exist not to be.
        if proved:
            workspaces.consume_invitations(email, subject=subject)

        person = workspaces.user(email)
        if person is None:
            raise NoSuchIdentity("no such user: " + (email or "none"), 400)
        mine = workspaces.workspaces_for(email)
        if not mine:
            raise NoSuchIdentity(email + " is not a member of any workspace",
                                 403)
        token = STATE["sessions"].create(email, mine[0]["slug"])
        if subject:
            # Recorded, never matched on. The mailbox is canonical identity
            # here; the provider's subject is evidence about how it was
            # proved, and worth having in the audit log when somebody asks
            # later how an account got in.
            self._auth_note(workspaces.IDENTITY_PROVED, email, "signed_in",
                            "subject=" + str(subject))
        raise Handled(HTTPStatus.SEE_OTHER, "", headers=[
            # The agency view first. Somebody who works across several clients
            # should see the estate before being dropped inside one of them,
            # and somebody with one workspace sees a one-card version of the
            # same screen rather than a different product.
            ("Location", "/global"),
            ("Set-Cookie", security.session_cookie(token))])


# ---------------------------------------------------------------- the CLI

class Unauthenticated(RuntimeError):
    """Refused: there would be nothing between the network and every workspace."""


# Interfaces only this machine can reach. The empty string is not one of
# them: `ThreadingHTTPServer(("", port))` binds every interface, which is
# the same exposure as 0.0.0.0 spelt in a way that looks like a default.
LOOPBACK = ("127.0.0.1", "::1", "localhost")


def check_configuration(host, demo):
    """Refuse to start rather than start somewhere nobody can see is wrong.

    Two refusals, in the order that gives the most useful message.

    **The environment.** `config.verify()` raises in production mode if
    something production needs is missing, and names it. `AUTH_PROVIDER`
    and the four settings behind it are REQUIRED there, so a production
    process with no identity provider stops here with a list rather than a
    verdict. It never raises in demo, which is the point of having modes:
    an empty environment must still be able to run the demonstration.

    **A reachable interface.** Binding anything but loopback puts a console
    that can pause campaigns, read every workspace and spend credits in
    front of whoever finds the port. Demo mode is the one exemption and it
    earns it: `main()` points every state file at a throwaway directory and
    installs a fictional estate before this process can read a real client
    file, so an exposed demo leaks nothing that exists.

    Refused in code rather than behind a flag, for the reason
    `push.run(live=True)` is: a flag is a thing somebody sets in a hurry.

    ## There was a third, and the mutation audit removed it

    A separate branch refused `APP_MODE=production` outright. It was
    correct when written - production authentication did not exist - and
    tonight's work made it unreachable: `AUTH_PROVIDER` became REQUIRED in
    production, so `config.verify()` above now refuses that state first and
    with a better message, and a provider that *is* configured returns
    early two lines up.

    The audit found it by failing to kill it. A branch a mutation cannot
    kill is a branch nothing depends on, and leaving it would have been
    exactly the "existence is not function" defect this repository keeps
    finding. The invariant it protected still has a home: `AUTH_PROVIDER`
    is REQUIRED in `config.VARIABLES`, and
    `test_config.test_a_real_auth_provider_is_required` fails if anybody
    reclassifies it.
    """
    app_config.verify()

    if security.sign_in_proves_identity():
        return

    if not demo and str(host) not in LOOPBACK:
        raise Unauthenticated(
            f"refusing to bind {host or 'every interface'}: this build signs "
            "in by picking an email from a list, with no password and no "
            "identity provider, so anything that can reach this port is a "
            f"super admin. Bind one of {', '.join(LOOPBACK)}, or serve the "
            "fictional estate with --demo.")


def serve(port=DEFAULT_PORT, demo=False, host="127.0.0.1"):
    check_configuration(host, demo)
    STATE["demo"] = bool(demo)
    server = ThreadingHTTPServer((host, port), Handler)
    return server


BOOTSTRAP_EMAIL_VAR = "BOOTSTRAP_SUPER_ADMIN"
BOOTSTRAP_WORKSPACE_VAR = "BOOTSTRAP_WORKSPACE"


def run_bootstrap(say=None):
    """Create the first administrator at startup, if there is not one.

    At startup and not in a command, because on a platform there is no
    shell: the process is the only thing that runs, and the volume the
    state lives on is only mounted inside it.

    It is safe there because `workspaces.bootstrap_super_admin` decides,
    and it refuses on two independent grounds - any existing user makes it
    inert, and the named address must already appear in the audit log as an
    identity a provider actually proved. Neither of those can be satisfied
    by setting a variable.

    Whatever happens is printed. This runs where nobody can attach a
    debugger, so the log is the only account of it there will ever be.
    """
    say = say or (lambda line: None)
    email = (os.environ.get(BOOTSTRAP_EMAIL_VAR) or "").strip()
    if not email:
        return None

    slug = (os.environ.get(BOOTSTRAP_WORKSPACE_VAR) or "").strip()
    try:
        result = workspaces.bootstrap_super_admin(email, slug)
    except workspaces.BootstrapRefused as e:
        # Not fatal. A refusal here means the console cannot be entered
        # yet, which is a state somebody has to fix - and refusing to
        # serve as well would take away the sign-in screen that produces
        # the proof it is asking for.
        say("")
        say(f"  Bootstrap refused: {e}")
        say("")
        return None

    if result is None:
        say(f"  Bootstrap:     inert, {BOOTSTRAP_EMAIL_VAR} is set and a "
            "user already exists")
        return None

    say("")
    say(f"  Bootstrap:     {result['email']} is now SUPER_ADMIN")
    say(f"  Workspace:     {result['workspace']}")
    say("  Recorded in the audit log. Unset "
        f"{BOOTSTRAP_EMAIL_VAR} once you have signed in.")
    say("")
    return result


def parser():
    """The command line, built where a test can read the same one main uses.

    Defaults are resolved per call rather than at import, so `WEB_HOST` and
    `WEB_PORT` are read from the environment the process is actually in.
    """
    p = argparse.ArgumentParser(prog="python -m src.web", description=__doc__)
    # `WEB_HOST` and `WEB_PORT` are declared in `src/config.py` and were read
    # by nothing, which is the defect this repository keeps producing in its
    # smallest form: configuration an operator can set, a screen can report,
    # and no code path consumes. The flags still win, so a deployment that
    # passes --port $PORT is unaffected.
    p.add_argument("--port", type=int,
                   default=int(os.environ.get("WEB_PORT") or DEFAULT_PORT))
    p.add_argument("--host", default=os.environ.get("WEB_HOST") or "127.0.0.1")
    p.add_argument("--demo", action="store_true",
                   help="install a deterministic fictional dataset into a "
                        "throwaway store and serve that")
    return p


def main(argv=None):
    args = parser().parse_args(argv)

    # The flag, or an environment that explicitly asked. `--demo` is how a
    # person asks on their own machine; `APP_MODE=demo` is how the deployed
    # demonstration asks, because a platform runs a start command rather
    # than typing one. `config.demo_estate_requested` says why an *unset*
    # APP_MODE must not count.
    demo = args.demo or app_config.demo_estate_requested()

    if demo:
        # Every store this process can write to, pointed at a throwaway
        # directory before anything is installed. Client configs included: a
        # demo must not be able to read, shadow or overwrite a real client
        # file, and the way to guarantee that is for it to read from somewhere
        # else entirely.
        workdir = tempfile.mkdtemp(prefix="resonate-demo-")
        store.use_directory(os.path.join(workdir, "work"))
        os.environ["MX_CACHE"] = os.path.join(workdir, "mx-cache.json")
        os.environ["OUT"] = os.path.join(workdir, "out")
        os.environ["CLIENTS_DIR"] = os.path.join(workdir, "clients")
        demodata.install()

    bootstrapped = run_bootstrap(say=lambda line: print(line, flush=True))

    server = serve(args.port, demo=demo, host=args.host)
    url = f"http://{args.host}:{server.server_address[1]}"

    # Flushed, because stdout is block-buffered whenever it is not a terminal.
    # Piped into a file or captured by a supervisor, the URL and the sign-in
    # list are the first things somebody needs and the last things they would
    # get - they would sit in the buffer until the process exited, which for a
    # server is the one moment they are no longer useful.
    def say(line=""):
        print(line, flush=True)

    say()
    say("  Resonate Outbound Control Center")
    say(f"  {url}")
    say()
    say(f"  Demo mode:     {'enabled' if demo else 'disabled'}")
    say("  Live sending:  disabled")
    if demo:
        say(f"  Demo store:    {os.path.dirname(store.queue_path())}")
        say(f"  Demo clients:  {clients.clients_dir()}")
        say()
        say("  Three workspaces, and one sign-in per role. There is no")
        say("  password: what you may do comes from the membership table,")
        say("  not from the form.")
        say()
        width = max(len(u["email"]) for u in demodata.USERS)
        for person in demodata.USERS:
            if person.get("super_admin"):
                where = "super admin - every workspace"
            else:
                where = ", ".join(f"{slug} as {role}"
                                  for slug, role in person["memberships"])
            say(f"    {person['email']:<{width}}  {where}")
    # Reply protection is the one background thing this process owes the
    # operator: a cadence step can fire in the gap between a reply arriving
    # and somebody remembering to poll. It is off unless asked for, and it
    # says which it is either way rather than starting silently.
    #
    # The digest rides the same thread. Separately switchable, because a
    # workspace with no provider credentials still wants a summary and a
    # process polling replies does not automatically owe anybody one.
    watcher = None
    digest_why = "off"
    after = ()
    try:
        hook = digestwatch.hook()
        digest_why = digestwatch.settings()["label"]
        after = (("digest", hook),) if hook else ()
    except digestwatch.NotConfigured as exc:
        digest_why = f"refused to schedule: {exc}"
    try:
        watcher, why = replywatch.start(after=after)
    except replywatch.NotConfigured as exc:
        why = f"refused to start: {exc}"
    say(f"  Reply polling: {why}")
    say(f"  Daily digest:  {digest_why}")
    say()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped\n")
    finally:
        if watcher is not None:
            watcher.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
