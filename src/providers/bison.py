#!/usr/bin/env python3
"""EmailBison. BUILD-SPEC section 5.4.

Base https://send.resonategroup.co/api (override with BISON_BASE),
Authorization: Bearer <BISON_KEY>.

This module can build a campaign and stop one. It cannot start one.

Everything here is staging or stopping: create (a DRAFT), cap, schedule, bind
senders, write a sequence, create and attach leads - or pause a campaign and
stop one person's remaining emails. `WRITE_ROUTES` is the allowlist, and
`/campaigns/{id}/resume` is deliberately not in it, which is what makes "this
module cannot send" a fact about the code rather than a promise.

The routes were established on 2026-09-13, against the vendor's own
documentation, after three separate conclusions here that they did not exist -
each reached by guessing a URL and reading the failure as absence.

  python -m src.providers.bison --check      read-only campaign list
"""
import argparse
import os

from . import (ProviderError, key, mapping, ok, query, request, result,
               failed)

DEFAULT_BASE = "https://send.resonategroup.co/api"


def base():
    return (os.environ.get("BISON_BASE") or DEFAULT_BASE).rstrip("/")


def headers():
    return {"Authorization": f"Bearer {key('BISON_KEY')}"}


# There is no way to scope a read to one workspace, and one way to believe you
# have. Probed read-only on 2026-09-07:
#
#   GET /workspaces                    -> 200, thirteen workspaces, PRODUCTIVE
#                                         is id 10 and Ironvault is id 25
#   GET /workspaces/10                 -> 200, but only {id, name, parent_id}
#   GET /workspaces/10/sender-emails   -> 404
#   GET /workspaces/current            -> 404
#   GET /sender-emails                 -> 200, total 225
#   GET /sender-emails?workspace_id=10 -> 200, total 225, same rows
#   GET /sender-emails?workspace_id=3  -> 200, total 225, same rows
#   GET /sender-emails?workspace_id=999-> 200, total 225, same rows
#
# The last three are the trap. `workspace_id` is accepted and discarded, and
# the answer for a workspace that does not exist is byte-identical to the
# answer for the one that does. Anyone who writes that filter will believe
# they scoped to one client and will in fact be holding every inbox in the
# estate, including another client's.
#
# No sender-email row carries a workspace, team, tenant or owner field either,
# so ownership cannot be established from the payload at all. The nearest
# thing is `tags`, which is operator-typed free text with no referential
# integrity to the workspace record - 153 of the 225 mention "Productive", and
# nothing in the API validates that.
#
# Which is why this module has no send function and why sender selection must
# not be inferred from these reads. Recorded in PRODUCT-GAPS.md.


USERS_PATH = "/users"


def bound_workspace():
    """Which workspace this credential is actually reading, per the provider.

    Every list route above answers for exactly one workspace and never says
    which, and `workspace_id` is accepted and discarded - so until this route
    was found there was no way to tell a Productive read from a Bluewave one
    except by looking at the rows and guessing from a free-text tag.

    `GET /api/users` states it. It is the only route that does: `/me`,
    `/user`, `/account`, `/whoami` and `/workspaces/current` are all 404, and
    the plural is the one that answers. Confirmed read-only on 2026-09-08,
    alongside a 403 on `/campaigns/417` whose body names the remedy in the
    vendor's own words - "consider using api-user keys or switch to the
    workspace this record is on".

    Returns {"id": int, "name": str}. Raises rather than guessing: a caller
    that cannot learn the workspace must not proceed as though it had, which
    is why there is no default and no None return.
    """
    status, data = request("GET", f"{base()}{USERS_PATH}", headers())
    if not ok(status):
        raise ProviderError(f"emailbison workspace: GET {USERS_PATH} -> {status}")
    body = data.get("data") if isinstance(data, dict) else None
    workspace = body.get("workspace") if isinstance(body, dict) else None
    if not isinstance(workspace, dict):
        raise ProviderError(
            "emailbison workspace: no `workspace` object in the /users "
            "response; refusing to assume which estate this key reads")
    ident = workspace.get("id")
    # `bool` is an `int` subclass and `True` would key a checkpoint as "ws1".
    if isinstance(ident, bool) or not isinstance(ident, (int, str)):
        raise ProviderError(
            f"emailbison workspace: id is {type(ident).__name__}, not an id")
    text = str(ident).strip()
    if not text.isdigit():
        raise ProviderError(f"emailbison workspace: id {text!r} is not numeric")
    return {"id": int(text), "name": str(workspace.get("name") or "")}


SENDER_EMAILS_PATH = "/sender-emails"


class PartialInventory(ProviderError):
    """A sender listing came back incomplete. Never returned as if whole.

    Raised rather than returning what arrived: an inventory is what capacity is
    planned against, and a short one reads as a small estate rather than as a
    failed read. That is not hypothetical - see `sender_emails` below.
    """


def sender_emails(per_page=None, expect_workspace=None):
    """Every sender inbox in the credential's workspace. Read-only.

    THE DEFECT THIS EXISTS TO PREVENT. There was no function here. The route
    had only ever been probed by hand, and on 2026-09-09 a probe read
    `response["data"]`, found fifteen rows, and reported the Productive estate
    as fifteen inboxes. The operator said 225. Both were looking at the same
    response: `meta.per_page` is 15 and `meta.last_page` was 15, so fifteen was
    the page size. 15 x 15 = 225.

    Nothing was wrong with the API and nothing was wrong with the credential.
    What was wrong is that the read looked at `data` and not at the envelope,
    and a paginated endpoint answered a question about totals with a page.

    So this reads `meta` first, walks every page, and **refuses to return a
    short list**. `meta.total` is compared against what arrived and a mismatch
    raises `PartialInventory`. Offset pagination is used deliberately here
    rather than the cursor form `fetch_replies` needs: this endpoint's `meta`
    carries `total` and `last_page`, which is exactly the completeness check a
    reply feed cannot offer.

    Returns `(rows, meta)` where `meta` is the first page's envelope, so a
    caller can report `total`, `per_page` and `last_page` rather than infer
    them from the length of the list.
    """
    # Before the first page, not after the last: an inventory attributed to the
    # wrong workspace is worse the more complete it is.
    require_workspace(expect_workspace)
    rows, first_meta, page = [], None, 1
    while True:
        params = {"page": page}
        if per_page:
            params["per_page"] = int(per_page)
        status, data = request(
            "GET", query(f"{base()}{SENDER_EMAILS_PATH}", params), headers())
        if not ok(status):
            raise ProviderError(
                f"emailbison sender-emails: page {page} -> {status}")
        if not isinstance(data, dict):
            raise ProviderError(
                "emailbison sender-emails: unexpected response shape")
        chunk = data.get("data")
        if not isinstance(chunk, list):
            # Same reasoning as the reply feed: a 200 with no array is a
            # contract change, not an empty estate.
            raise ProviderError(
                "emailbison sender-emails: no `data` array in the response "
                f"(got {type(chunk).__name__}); refusing to read that as no "
                "inboxes")
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if first_meta is None:
            first_meta = meta
        rows += chunk
        last = meta.get("last_page")
        try:
            last = int(last)
        except (TypeError, ValueError):
            # No `last_page` to walk to. One page is all this response claims
            # to have, and saying so is the caller's business rather than
            # something to assume either way.
            break
        if page >= last:
            break
        page += 1

    total = (first_meta or {}).get("total")
    if isinstance(total, int) and len(rows) != total:
        raise PartialInventory(
            f"emailbison sender-emails: meta.total says {total} inboxes and "
            f"{len(rows)} arrived across {page} page(s). Refusing to return a "
            f"partial inventory: capacity gets planned against this number, "
            f"and a short list reads as a small estate rather than a failed "
            f"read.")
    return rows, (first_meta or {})


# ------------------------------------------------- tenancy, stated explicitly
#
# There is no workspace parameter on any function in this module, and there must
# not be one. `workspace_id` is accepted and discarded by every list route - the
# probe matrix above shows a nonexistent workspace answering byte-identically to
# a real one - so a parameter named after tenancy that the provider ignores is
# worse than none: it is a scope somebody will believe they set.
#
# The credential IS the boundary. That is the whole contract, and it is stated
# here rather than left to be inferred.
WORKSPACE_SCOPE = "credential_bound"


class WorkspaceMismatch(ProviderError):
    """The credential is not bound to the workspace the caller expected.

    Raised rather than reported, and raised BEFORE the read rather than
    alongside it. Between 2026-09-07 and 2026-09-08 this credential answered
    for four different estates without anything changing on this side - 51
    inboxes, then 225, then 32 Greenfield, then 32 Bluewave - because the active
    workspace is chosen in the vendor's UI. A read that does not assert its
    binding is a read whose tenancy is whatever somebody last clicked.
    """


def scope():
    """What tenancy this module can and cannot offer, in one place."""
    return {
        "kind": WORKSPACE_SCOPE,
        "parameter": None,
        "why": ("every list route accepts `workspace_id` and discards it, and "
                "answers identically for a workspace that does not exist, so "
                "no argument on this module can scope a read"),
        "binding_route": USERS_PATH,
        "verifiable": True,
    }


def require_workspace(expected):
    """Assert the credential is bound where the caller thinks it is.

    `expected` is an id, or None to mean unpinned. Unpinned returns None
    WITHOUT calling the binding route: this is a guard, not a getter, and the
    first version called `/users` on every read - which made an unpinned read
    depend on a route it does not need and turned a working inventory read into
    a failure when that route was unavailable. A caller that wants the binding
    recorded asks `bound_workspace()` for it, which `senderinventory` does.

    Unpinned is deliberately not defaulted to Productive's 10, for the reason
    `replywatch.expected_workspace` gives: a default asserts ownership this
    module cannot prove.
    """
    if expected in (None, ""):
        return None
    bound = bound_workspace()
    if str(bound["id"]).strip() != str(expected).strip():
        raise WorkspaceMismatch(
            f"emailbison: this credential is bound to workspace "
            f"{bound['id']} ({bound['name']!r}), not {expected}. Refusing the "
            f"read: `workspace_id` is ignored by every route here, so a read "
            f"taken against the wrong binding cannot be corrected after the "
            f"fact and cannot be told apart from a correct one.")
    return bound


def build_leads(rows):
    """Lint-clean rows from out/emailbison.csv into the leads[] payload.

    Pure: builds a dict, sends nothing.
    """
    return {"leads": [{
        "email": r["email"],
        "first_name": r.get("first_name", ""),
        "last_name": r.get("last_name", ""),
        "company_name": r.get("company", ""),
        # `contact_key` and `client` travel beside `record_id`. They were
        # missing, and `adapters.from_emailbison` has always read all three
        # back off an inbound reply - so a reply could name the company it came
        # from and never the person, on the one provider whose custom variables
        # are known to round-trip (the client's own cadence reads `subject` and
        # `body` out of this same dict).
        # A LIST OF {name, value}, NOT A MAPPING. A mapping is refused with
        # "The custom_variables.<key>.name field is required", and each name
        # must exist on the workspace before a lead may carry it - see
        # `ensure_custom_variables`.
        "custom_variables": _variables({"subject": r.get("subject", ""),
                             "body": r.get("body", ""),
                             "title": r.get("title", ""),
                             "record_id": r.get("record_id", ""),
                             "contact_key": r.get("contact_key", ""),
                             "client": r.get("client", ""),
                             # Which human this lead belongs to, and which of
                             # their inboxes. Identifiers, never credentials -
                             # `sender_account_id` is our own id for the inbox
                             # and `provider_account_id` is EmailBison's, and
                             # neither is a key to anything.
                             #
                             # Sent for the same reason record_id is: a person
                             # looking at this lead in EmailBison's own UI can
                             # see who owns the relationship, and if a reply
                             # echoes them back the attribution is already
                             # there. Whether EmailBison round-trips these
                             # particular fields has NOT been validated against
                             # the live API - see docs. Nothing depends on it.
                             "sender_id": r.get("sender_id", ""),
                             "sender_account_id": r.get("sender_account_id", ""),
                             "provider_account_id": r.get(
                                 "provider_account_id", "")}),
    } for r in rows]}


# The variables a Productive lead carries. `record_id` and `contact_key` are
# the load-bearing ones: `adapters.from_emailbison` reads them off an inbound
# reply, and a reply that cannot name its person stops nobody.
# HOW MANY STEPS OF GENERATED COPY A LEAD CAN CARRY.
#
# A custom variable holds ONE value per lead, so a sequence of five generated
# emails needs five pairs of them - `{SUBJECT_3}` in the template resolves to
# the variable `subject_3`. The unnumbered `subject` and `body` stay for the
# single-step shape campaign 451 is staged against.
#
# Five because that is the email half of `productive_li_heavy_v1`, plus room
# for one more before the ceiling binds. Declaring a variable creates nothing
# and reaches nobody, so an unused name costs a row in a settings table; a
# missing one costs a refused staging run in the middle of a batch.
MAX_SEQUENCE_STEPS = 6

LEAD_VARIABLES = (("subject", "body", "title", "record_id", "contact_key",
                   "client", "sender_id", "sender_account_id",
                   "provider_account_id")
                  + tuple(f"subject_{n}" for n in range(1, MAX_SEQUENCE_STEPS + 1))
                  + tuple(f"body_{n}" for n in range(1, MAX_SEQUENCE_STEPS + 1)))


def _variables(mapping_of):
    """Custom variables in the provider's shape, empties dropped.

    An empty value is left out rather than sent blank: the provider would
    store it, and a blank `record_id` reads exactly like an attributed one
    until somebody tries to use it.
    """
    return [{"name": name, "value": str(value)}
            for name, value in sorted(mapping_of.items())
            if str(value or "").strip()]


def variables_of(lead):
    """A staged lead's custom variables as a mapping, for reading.

    The wire shape is a list of {name, value} because that is what the
    provider takes. `adapters._custom` already reads that shape coming BACK
    off a reply; this is the same view going out, so a caller inspecting what
    was staged does not have to walk a list to find one name.
    """
    return {v.get("name"): v.get("value")
            for v in (lead or {}).get("custom_variables") or []
            if isinstance(v, dict)}


def custom_variables():
    """Every custom variable declared on this workspace, by name.

    PAGED, at fifteen a page like everything else here. This workspace has
    twelve, so one page has been the whole answer so far and would silently
    stop being it at the sixteenth: `ensure_custom_variables` below reads this
    to decide what is MISSING, and a name on page two reads as absent, so it
    would try to create a variable that already exists and be refused. One
    variable away from breaking every staging run.
    """
    rows, _total = _paged(
        "custom_variables",
        lambda page: query(f"{base()}/custom-variables", {"page": page}))
    return {r.get("name"): r.get("id") for r in rows if isinstance(r, dict)}


def ensure_custom_variables(names=LEAD_VARIABLES):
    """Declare any of `names` the workspace does not have yet.

    Idempotent by construction: it reads what exists and creates only the
    difference. Declaring a variable creates no lead and touches no campaign,
    so this is staging in the strictest sense.
    """
    have = custom_variables()
    created = []
    for name in names:
        if name in have:
            continue
        status, data = _post("/custom-variables", {"name": name})
        if not ok(status):
            raise ProviderError(
                f"emailbison ensure_custom_variables: POST {name!r} -> "
                f"{status} {_message(data)}")
        created.append(name)
    return {"declared": sorted(have), "created": created}


def leads_endpoint(campaign_id):
    """Where a campaign's membership is READ.

    This is not where leads are added. `POST` here answers 405 "Supported
    methods: GET, HEAD, DELETE" - measured 2026-09-12. Adding is a two-step on
    this API: create the lead, then attach it. See `attach_leads`.
    """
    return f"{base()}/campaigns/{campaign_id}/leads"


ATTACH_PATH = "/campaigns/{campaign_id}/leads/attach-leads"

# EVERY PATH THIS MODULE IS ALLOWED TO WRITE TO.
#
# The same guarantee `heyreach.WRITE_ROUTES` gives: the verb is not the
# safety property, the ROUTE is. A send on this provider is started by
# `/campaigns/{id}/resume`, and its absence from this tuple is what makes
# "this module cannot start a campaign" a fact about the code rather than a
# promise about the caller.
#
# Two kinds only. STAGING builds a campaign that is left paused and cannot
# send. STOPPING can only ever mean somebody receives less.
WRITE_ROUTES = (
    "/campaigns",                                   # create, as a DRAFT
    "/campaigns/{campaign_id}/update",              # limits
    "/campaigns/{campaign_id}/sequence-steps",      # copy, into a stopped campaign
    "/campaigns/{campaign_id}/leads/attach-leads",  # membership
    "/campaigns/{campaign_id}/pause",               # stop everybody
    # THE ONE ROUTE HERE THAT REACHES A PERSON. Declared so it is visible
    # rather than buried among the staging verbs. `resume_campaign` takes an
    # expected lead count and refuses when the provider disagrees, because a
    # resumed campaign sends to everybody it holds.
    "/campaigns/{campaign_id}/resume",              # START SENDING
    "/campaigns/{campaign_id}/leads/stop-future-emails",   # stop ONE person
    "/campaigns/{campaign_id}/schedule",            # when it may send
    "/campaigns/{campaign_id}/attach-sender-emails",  # which inboxes
    # REMOVING AN INBOX IS A STOPPING VERB, and that is why it belongs here.
    # This tuple admits two kinds only, and detaching a sender is squarely the
    # second: a campaign that sends from one fewer mailbox reaches NOBODY it
    # would not otherwise have reached. It cannot add exposure.
    #
    # DOCUMENTED, NOT GUESSED. `docs/BISON-API-CAPABILITY-MAP-2026-09-14.md`
    # and `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md` both already listed
    # this route as "DOCS | not probed"; the vendor's
    # campaigns/adding-and-removing-sender-emails page specifies it, and
    # bcharleson/emailbison-cli implements it as DELETE independently. This
    # module's own history is three wrong conclusions that a route did not
    # exist, each reached by guessing a URL and reading the failure as
    # absence - so it is added on documentation, not on a probe.
    "/campaigns/{campaign_id}/remove-sender-emails",  # which inboxes, fewer
    "/leads",                                       # create a lead
    # UPDATE ONE LEAD'S FIELDS. Staging, and of the narrowest kind: the only
    # caller is `update_lead`, which rewrites the custom variables carrying
    # approved copy onto a lead that already exists. It was being written to
    # while absent from this tuple, which is how the enforcement below came to
    # be written - a declared allowlist that nothing consults cannot tell
    # anybody it has been left behind.
    "/leads/{lead_id}",                             # correct a staged lead
    "/custom-variables",                            # declare a variable name
)

# ------------------------------------------------------------------- the door
#
# THIS TUPLE WAS A COMMENT UNTIL 2026-09-14. It claimed "the same guarantee
# `heyreach.WRITE_ROUTES` gives", and HeyReach earns that claim with a
# chokepoint - its `_write` refuses a path not on its list before the request
# is built. Here every write called `request()` directly with an f-string URL,
# so the tuple above documented an intention and enforced nothing.
#
# It was already wrong when this was written. `update_lead` writes
# `PATCH /leads/{id}`, which the tuple did not name, and nothing anywhere
# noticed. That is the whole argument for a door: the list drifts from the code
# silently until something compares the two on every call.
#
# THE VERB STAYS A LITERAL IN EACH OF THE THREE FUNCTIONS BELOW, on purpose.
# `tests/test_nothing_writes_to_a_provider` reads this repository's source for
# `request("POST", ...)` and reports a `request(verb, ...)` as DYNAMIC -
# unreadable, and exactly the shape a deliberate bypass would have. A single
# `_write(method, ...)` helper would have made every EmailBison write invisible
# to that audit, trading a static guarantee for a runtime one. Three small
# functions keep both.

WRITE_METHODS = ("POST", "PATCH", "PUT")


def route_of(path):
    """Which `WRITE_ROUTES` template a concrete path matches, or None.

    A braced template segment matches exactly one concrete segment, and the
    segment COUNT must agree - so `/leads` never matches `/leads/{lead_id}`,
    and no longer path can smuggle itself in behind a shorter template.
    """
    parts = [p for p in str(path).split("?")[0].split("/") if p]
    for template in WRITE_ROUTES:
        wanted = [p for p in template.split("/") if p]
        if len(wanted) != len(parts):
            continue
        if all((w.startswith("{") and w.endswith("}")) or w == p
               for w, p in zip(wanted, parts)):
            return template
    return None


def _allow(verb, path):
    """Refuse any write to a path `WRITE_ROUTES` does not name."""
    if route_of(path) is None:
        raise ProviderError(
            f"emailbison: {verb} {path} is not a write route. This module "
            f"writes only to {', '.join(WRITE_ROUTES)}. Adding a route there "
            f"is a decision about what this system may do to real campaigns")


def _post(path, body):
    _allow("POST", path)
    return request("POST", base() + path, _json_headers(), body)


def _patch(path, body):
    _allow("PATCH", path)
    return request("PATCH", base() + path, _json_headers(), body)


def _put(path, body):
    _allow("PUT", path)
    return request("PUT", base() + path, _json_headers(), body)


def _delete(path, body):
    _allow("DELETE", path)
    return request("DELETE", base() + path, _json_headers(), body)


def _json_headers():
    return dict(headers(), **{"Content-Type": "application/json"})


def _message(data):
    """The provider's own error sentence, for an exception a human will read."""
    body = data.get("data") if isinstance(data, dict) else None
    if isinstance(body, dict) and body.get("message"):
        return str(body["message"])[:200]
    if isinstance(data, dict) and data.get("message"):
        return str(data["message"])[:200]
    return str(data)[:200]


def create_lead(fields):
    """Create one lead in the workspace and return the provider's own row.

    `email` and `first_name` are required by the provider. Returns the stored
    row rather than the id alone, because a caller has to be able to see what
    was actually stored: unknown keys are accepted and dropped silently here,
    so a 201 on its own proves nothing about any individual field.
    """
    if not isinstance(fields, dict) or not fields.get("email"):
        raise ProviderError("emailbison create_lead: an email is required")
    status, data = _post("/leads", fields)
    if not ok(status):
        raise ProviderError(
            f"emailbison create_lead: POST /leads -> {status} {_message(data)}")
    row = mapping(data, "create_lead").get("data") or {}
    if not row.get("id"):
        raise ProviderError(
            "emailbison create_lead: the provider returned no id; refusing to "
            "report a lead that cannot be addressed")
    return row


def create_campaign(name):
    """Create a campaign. It comes back in `draft` and sends nothing.

    POST /api/campaigns -> 201, measured 2026-09-12. A draft campaign cannot
    send: resume refuses one without a sequence and a schedule, in the
    provider's own words. So this stages and never exposes anybody.
    """
    if not str(name or "").strip():
        raise ProviderError("emailbison create_campaign: a name is required")
    status, data = _post("/campaigns", {"name": name})
    if not ok(status):
        raise ProviderError(
            f"emailbison create_campaign: POST -> {status} {_message(data)}")
    row = mapping(data, "create_campaign").get("data") or {}
    if not row.get("id"):
        raise ProviderError(
            "emailbison create_campaign: the provider returned no id. A "
            "campaign may exist that nothing here can name; do NOT retry")
    return row


def find_lead_by_email(email, attempts=1, interval=1.0):
    """The one lead with this address, or None. Never a guess.

    `?search=` is the only real filter on this route: a nonsense term returns
    nothing and a known address returns exactly its lead. `?email=` is NOT -
    it is accepted and discarded, and answers with an unfiltered page, which
    is the same trap `workspace_id` sets elsewhere in this API.

    IT IS AN INDEX AND THE INDEX LAGS CREATION. Measured on the campaign
    listing on 2026-09-13, where the same lag is visible and bounded: absent
    in the same second, present one second later. So a lead created moments
    ago by another process is exactly the lead this cannot see, and that is
    precisely when a caller asks - after the provider refused a create with
    "already been taken".

    `attempts` is therefore the caller's, and it defaults to ONE. A caller
    that is merely asking gets one honest read; a caller reconciling a create
    it just lost a race for says how long it is prepared to wait. Waiting is
    not built in by default because a `None` that took five seconds to arrive
    is still a `None`, and most callers are not racing anything.

    An ambiguous answer raises instead of picking a row, at every attempt.
    """
    import time
    import urllib.parse

    address = str(email or "").strip().lower()
    if not address:
        raise ProviderError("emailbison find_lead_by_email: no address given")
    for attempt in range(max(1, int(attempts))):
        if attempt:
            time.sleep(interval)
        status, data = request(
            "GET", f"{base()}/leads?search={urllib.parse.quote(address)}",
            headers())
        if not ok(status):
            raise ProviderError(
                f"emailbison find_lead_by_email: GET -> {status}")
        rows = mapping(data, "find_lead_by_email").get("data")
        if not isinstance(rows, list):
            raise ProviderError(
                "emailbison find_lead_by_email: the lead list is not a list; "
                "refusing to read an unknown shape as 'no such lead'")
        exact = [r for r in rows if isinstance(r, dict)
                 and str(r.get("email") or "").strip().lower() == address]
        if len(exact) > 1:
            raise ProviderError(
                f"emailbison find_lead_by_email: {len(exact)} leads carry "
                f"{address!r}. Refusing to choose one")
        if exact:
            return exact[0]
    return None


def find_campaigns_by_name(name):
    """Every campaign carrying this exact name. A list, never a choice.

    THE ONE THING THAT CAN FIND A CAMPAIGN NOBODY WROTE DOWN. A crash between
    `POST /campaigns` and persisting the id leaves a real campaign that no
    local state names, and the next run would build a second one - measured
    2026-09-13, two campaigns with byte-identical names.

    AND IT WALKS THE LISTING RATHER THAN ASKING `?search=`. `?search=` is a
    real filter on this route - a nonsense term returns nothing - but it is an
    INDEX, and the index lags creation: measured 2026-09-13, a campaign
    created and searched for in the same second came back absent, and was
    found one second later. The whole purpose of this function is to find a
    campaign created moments ago by a process that then died, so a read that
    is a second behind would answer "no such campaign" at exactly the moment
    it matters and the caller would create the duplicate anyway. The listing
    showed the same campaign immediately, on every attempt.

    (`?name=` is neither: it is accepted, discarded, and answers with an
    unfiltered page - the trap `workspace_id` sets elsewhere in this API.)

    Names are NOT unique on this API - it accepted two campaigns with the same
    name without complaint - so this returns everything it found and leaves
    the decision to a caller that can refuse. A short read raises rather than
    returning fewer: "there is no campaign by that name" is the answer that
    licenses creating one, and it must never be produced by a failed read.
    """
    wanted = str(name or "").strip()
    if not wanted:
        raise ProviderError("emailbison find_campaigns_by_name: no name given")
    rows, _total = _paged(
        "find_campaigns_by_name",
        lambda page: query(f"{base()}/campaigns",
                           {"page": page, "per_page": 100}))
    return [{"id": r.get("id"), "name": r.get("name"),
             "status": r.get("status")}
            for r in rows if isinstance(r, dict)
            and str(r.get("name") or "").strip() == wanted]


UPDATE_PATH = "/campaigns/{campaign_id}/update"


def set_limits(campaign_id, name, emails_per_day, new_leads_per_day=None):
    """Cap what this campaign may send in a day, and prove the cap took.

    Two things make this its own function rather than a field on create.

    `POST /campaigns` SILENTLY DISCARDS IT. Measured 2026-09-13: created with
    `max_emails_per_day: 7`, read back 1000. Nothing in the response says a
    field was ignored, so a campaign created with a cap and a campaign created
    without one are indistinguishable until somebody reads it back.

    AND THE WRITE ROUTE IS NOT THE OBVIOUS ONE. `PATCH /campaigns/{id}` is 405
    (Allow: GET, HEAD, DELETE); the write is `/campaigns/{id}/update`, it
    requires `name` alongside the limits, and it enforces
    `max_emails_per_day >= max_new_leads_per_day` in its own words.

    Raises unless the provider reports the numbers asked for. A cap that was
    requested and not stored is the failure this exists to prevent.
    """
    if not isinstance(emails_per_day, int) or emails_per_day < 1:
        raise ProviderError(
            f"emailbison set_limits: {emails_per_day!r} is not a daily send "
            f"cap. Refusing to leave this campaign on the provider default")
    leads = new_leads_per_day
    if leads is None:
        leads = emails_per_day
    if leads > emails_per_day:
        raise ProviderError(
            f"emailbison set_limits: new leads per day ({leads}) exceeds "
            f"emails per day ({emails_per_day}); the provider refuses this")
    status, data = _patch(
        UPDATE_PATH.format(campaign_id=campaign_id),
        {"name": name, "max_emails_per_day": emails_per_day,
         "max_new_leads_per_day": leads})
    if not ok(status):
        raise ProviderError(
            f"emailbison set_limits: PATCH -> {status} {_message(data)}")
    row = campaign(campaign_id)
    got = (row.get("max_emails_per_day"), row.get("max_new_leads_per_day"))
    if got != (emails_per_day, leads):
        raise ProviderError(
            f"emailbison set_limits: asked for {(emails_per_day, leads)} and "
            f"campaign {campaign_id} reads back {got}. The cap did not take")
    return {"campaign_id": campaign_id, "max_emails_per_day": emails_per_day,
            "max_new_leads_per_day": leads}


STOP_PATH = "/campaigns/{campaign_id}/leads/stop-future-emails"

# What the provider calls a membership that will receive nothing further.
# Read from `lead_campaign_data`, which is the provider's own per-campaign
# state for a lead and the only place this is recorded.
STOPPED_STATES = ("stopped", "replied", "bounced", "sequence_finished",
                  "unsubscribed")

# Observed and deliberately NOT stopped: a lead in a paused campaign reads
# `sending_paused`. That is the campaign's state borrowed by the membership,
# and it reverses the moment somebody resumes - so treating it as stopped
# would report a person as safe while one click puts them back in sequence.
RESUMABLE_STATES = ("in_sequence", "sending_paused", "never_contacted")


# THE CAMPAIGN LEAD LIST IGNORES `per_page` AND SERVES FIFTEEN ROWS.
#
# Measured 2026-09-13 on the live estate: `GET /campaigns/352/leads?per_page=200`
# answers fifteen rows with `meta.per_page: 15`, `meta.total: 21159`,
# `meta.last_page: 1411`. `per_page=50` and `per_page=15` answer identically.
# The same is true of `/campaigns/{id}/sender-emails`: campaign 352 reads back
# fifteen inboxes and holds 222.
#
# This is the defect `sender_emails` was written to prevent, living in three
# other reads at once, and every consequence was silent:
#
#   `membership(campaign, [lead])` returned {} for a genuine member of 352,
#   so `leadstop.stop` raised "lead is not a member of campaign 352" - the
#   per-lead STOP was unreachable for every campaign this agency actually
#   runs;
#   `attach_leads` compared a fifteen-row readback against what it asked for
#   and would have raised "the provider answered 200 but N leads are not in
#   the campaign" for any campaign past its first page;
#   `resume_campaign(expect_leads=15)` would have passed on a campaign holding
#   twenty thousand people - the guard whose whole job is to stop a campaign
#   reaching more people than the caller believes.
#
# So nothing here reads a page and calls it a membership. A question about
# SPECIFIC leads is asked of those leads, which is exact and costs one read
# each; a question about the whole campaign is paged, and refuses rather than
# truncating.

#: Pages a whole-campaign walk will do before it gives up. Fifteen rows a
#: page, so 600 leads or 600 inboxes. A campaign larger than this is not
#: read short - it raises, and names the two bounded reads that do scale.
PAGE_CAP = 40
PAGE_SIZE = 15


def _paged(what, url_of, cap=PAGE_CAP):
    """Every row behind a paginated route, or a refusal. Never a page.

    Returns `(rows, total)`. Raises `PartialInventory` when the walk would
    exceed `cap` or when fewer rows arrive than `meta.total` claims: an
    absence read off a short list is the failure this whole file is careful
    about, and it is worse here than anywhere because the lists are
    memberships.
    """
    rows, total, page = [], None, 1
    while True:
        status, data = request("GET", url_of(page), headers())
        if not ok(status):
            raise ProviderError(f"emailbison {what}: page {page} -> {status}")
        chunk = mapping(data, what).get("data")
        if not isinstance(chunk, list):
            raise ProviderError(
                f"emailbison {what}: the list is not a list; refusing to read "
                f"an unknown shape as an empty one")
        rows += chunk
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if total is None:
            total = meta.get("total")
        try:
            last = int(meta.get("last_page"))
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        if page >= cap:
            raise PartialInventory(
                f"emailbison {what}: {last} pages to walk and this read stops "
                f"at {cap}. Refusing to return {len(rows)} of {total} as "
                f"though it were all of them - ask about specific leads with "
                f"`membership(campaign, lead_ids)` or about the size with "
                f"`campaign_lead_count`, both of which are bounded")
        page += 1
    if isinstance(total, int) and len(rows) != total:
        raise PartialInventory(
            f"emailbison {what}: meta.total says {total} and {len(rows)} "
            f"arrived across {page} page(s). Refusing to report a partial "
            f"read as a complete one")
    return rows, total


def _status_in(row, campaign_id):
    """This lead's status IN THIS CAMPAIGN, from the provider's own array.

    `lead_campaign_data` has one entry per campaign the lead belongs to, so it
    is filtered by `campaign_id`. Reading element zero returns another
    campaign's status for a lead that is in several, which is a mistake that
    reads as a successful stop.
    """
    for entry in (row or {}).get("lead_campaign_data") or []:
        if isinstance(entry, dict) and str(entry.get("campaign_id")) == str(
                campaign_id):
            return entry.get("status")
    return None


def membership(campaign_id, lead_ids=None):
    """Each lead's status IN THIS CAMPAIGN, as the provider states it.

    NAMED LEADS ARE ASKED OF THEMSELVES. `GET /leads/{id}` carries the same
    `lead_campaign_data` array and is exact for that person whatever page of
    the campaign they are on - which is the only way this answer can be right
    for a campaign of twenty thousand. It costs one read per named lead, and
    the callers that name leads are naming a handful.

    With no `lead_ids` this walks the campaign and refuses past `PAGE_CAP`.
    That form is for a small campaign; a big one has no cheap whole answer and
    is told so rather than given a page.
    """
    if lead_ids is not None:
        out = {}
        for lead_id in {int(i) for i in lead_ids}:
            status = _status_in(lead(lead_id), campaign_id)
            if status is not None:
                out[lead_id] = status
        return out
    rows, _total = _paged(
        "membership",
        lambda page: query(leads_endpoint(campaign_id), {"page": page}))
    out = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        status = _status_in(row, campaign_id)
        if status is not None:
            out[int(row["id"])] = status
    return out


def campaign_lead_count(campaign_id):
    """How many leads the provider says this campaign holds. One read.

    `meta.total` on the first page, which is the only number on this route
    that is about the campaign rather than about the page. It is what
    `resume_campaign` counts against, because a resumed campaign sends to
    everybody it holds and the size of that is the containment.
    """
    status, data = request(
        "GET", query(leads_endpoint(campaign_id), {"page": 1}), headers())
    if not ok(status):
        raise ProviderError(f"emailbison campaign_lead_count: GET -> {status}")
    meta = data.get("meta") if isinstance(data, dict) else None
    total = (meta or {}).get("total")
    if not isinstance(total, int):
        raise ProviderError(
            "emailbison campaign_lead_count: no `meta.total` in the response; "
            "refusing to count a campaign's reach from the length of a page")
    return total


#: Pages of the membership the blast-radius check reads. Fifteen rows a page.
SAMPLE_PAGES = 2


def _sample(campaign_id, pages=SAMPLE_PAGES):
    """A bounded slice of this campaign's membership, for a before/after diff.

    Deliberately NOT `membership(campaign_id)`: that refuses a big campaign
    rather than truncating it, which is right for a question about the whole
    membership and useless for a check that only has to notice collateral
    damage. This one is honest about being a sample because its caller reports
    the denominator.
    """
    out = {}
    for page in range(1, pages + 1):
        status, data = request(
            "GET", query(leads_endpoint(campaign_id), {"page": page}),
            headers())
        if not ok(status):
            raise ProviderError(f"emailbison stop_lead sample: GET -> {status}")
        rows = mapping(data, "stop_lead sample").get("data")
        if not isinstance(rows, list):
            raise ProviderError(
                "emailbison stop_lead sample: the campaign lead list is not a "
                "list; refusing to read an unknown shape as empty membership")
        for row in rows:
            if isinstance(row, dict) and row.get("id") is not None:
                out[int(row["id"])] = _status_in(row, campaign_id)
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        try:
            if page >= int(meta.get("last_page")):
                break
        except (TypeError, ValueError):
            break
    return out


def stop_lead(campaign_id, lead_ids, attempts=8, interval=2.0):
    """Stop future emails to these people, and confirm nobody else moved.

    THE STATUS CODE IS NOT THE PROOF. This route answers 200 for a lead that
    is not in the campaign at all and does nothing, so a caller trusting the
    response would record a stop that never happened - on the one operation
    whose whole purpose is to guarantee somebody stops hearing from us.

    The write is asynchronous and lands in a second or two, so this polls the
    provider's own membership until every named lead reads as stopped, and
    raises if any does not. A stop that cannot be confirmed must never be
    reported as a stop.

    Returns {"stopped", "untouched", "sampled_of"}. `untouched` is the
    blast-radius check and it is now a SAMPLE that says how big it was.

    It used to read "every other member of the campaign", and it never did:
    the membership route serves fifteen rows whatever it is asked for, so on
    campaign 352 that sentence meant fifteen of 21,159 chosen by the provider.
    Reading all of them is 1,411 requests before the stop and 1,411 after it,
    on the one operation that has to be fast because somebody just replied. So
    the sample is bounded on purpose and `sampled_of` states the denominator -
    a partial check that says it is partial, rather than a complete-sounding
    one that was never complete.

    The leads being STOPPED are not sampled. They are read individually and
    exactly, which is what makes the stop itself confirmable.
    """
    import time

    wanted = [int(i) for i in (lead_ids or [])]
    if not wanted:
        raise ProviderError("emailbison stop_lead: no lead ids given")
    before = membership(campaign_id, wanted)
    absent = [i for i in wanted if i not in before]
    if absent:
        raise ProviderError(
            f"emailbison stop_lead: lead(s) {absent[:5]} are not in campaign "
            f"{campaign_id}. This route answers 200 for them and does "
            f"nothing, so refusing rather than reporting a stop that cannot "
            f"happen")
    total = campaign_lead_count(campaign_id)
    sample_before = _sample(campaign_id)
    status, data = _post(STOP_PATH.format(campaign_id=campaign_id),
                         {"lead_ids": wanted})
    if not ok(status):
        raise ProviderError(
            f"emailbison stop_lead: POST -> {status} {_message(data)}")

    for attempt in range(attempts):
        time.sleep(interval if attempt else 0.5)
        now = membership(campaign_id, wanted)
        pending = [i for i in wanted
                   if str(now.get(i) or "").lower() not in STOPPED_STATES]
        if not pending:
            sample_after = _sample(campaign_id)
            moved = {i: sample_before.get(i) for i in sample_before
                     if i not in wanted
                     and sample_before.get(i) != sample_after.get(i)}
            if moved:
                raise ProviderError(
                    f"emailbison stop_lead: stopping {wanted} also changed "
                    f"{moved}. Refusing to report a per-lead stop that was "
                    f"not per-lead")
            return {"stopped": {i: now.get(i) for i in wanted},
                    "untouched": {i: s for i, s in sample_after.items()
                                  if i not in wanted},
                    "sampled_of": total}
    raise ProviderError(
        f"emailbison stop_lead: the provider accepted the request but lead(s) "
        f"{pending[:5]} still do not read as stopped after "
        f"{attempts * interval:.0f}s. Provider state is UNKNOWN - do not "
        f"record a stop, and do not retry blindly")


SCHEDULE_PATH = "/campaigns/{campaign_id}/schedule"
SENDERS_PATH = "/campaigns/{campaign_id}/attach-sender-emails"

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
        "sunday")


def _hhmm(value):
    """"09:00", "09:00:00" and "9:00" as one comparable (hour, minute)."""
    parts = str(value or "").strip().split(":")
    if len(parts) < 2 or not parts[0].strip().isdigit() \
            or not parts[1].strip().isdigit():
        raise ProviderError(
            f"emailbison schedule: {value!r} is not a time of day")
    return int(parts[0]), int(parts[1])


def schedule_matches(existing, days, start, end, timezone):
    """Is the window the provider holds the window that was asked for?

    Here rather than in the caller because the only hard part is this
    module's business: the provider stores "09:00" and returns "09:00:00", so
    a string comparison says a correct schedule is wrong and an `or`-guarded
    one says a wrong schedule is correct. A caller asking "is this already
    right" and this module asking "did the write take" must not answer that
    differently, which is what happened - `set_schedule` compared the days and
    the timezone, the factory compared the days and the timezone, and neither
    compared the hours.

    An absent schedule is not a match. `{}` here means the campaign has none,
    and "nobody chose" must never satisfy "somebody chose this".
    """
    if not existing:
        return False
    return (str(existing.get("timezone")) == str(timezone)
            and all(bool(existing.get(d)) == (d in days) for d in DAYS)
            and _hhmm(existing.get("start_time")) == _hhmm(start)
            and _hhmm(existing.get("end_time")) == _hhmm(end))


def set_schedule(campaign_id, days, start, end, timezone):
    """When this campaign is allowed to send, and confirm it took.

    All eleven fields are required by the provider - a partial body is a 422.
    `days` names the sending days; everything else is explicitly false rather
    than omitted, because an omitted day is a validation error and not a
    quiet no.

    POST CREATES AND WILL NOT REPLACE. Measured 2026-09-13: on a campaign that
    already has a schedule, `POST .../schedule` answers **200** carrying
    `{"success": false, "message": "Schedule already exists for <name>"}` and
    writes nothing at all. The update verb is `PUT` - `PATCH` and `DELETE` are
    both 405 there, and the 405 names GET, HEAD, POST, PUT. So the verb is
    chosen from whether a schedule exists, and a body that says `success:
    false` is read as the refusal it is rather than as the 200 it arrives in.

    Round-trip asymmetry to know about: a time written as "09:00" reads back
    as "09:00:00", so the readback compares the hour and minute rather than
    the string. It compares them at all now - it did not, and with the POST
    trap above that meant narrowing a window from 09:00-17:00 to 09:00-12:00
    on the same days answered 200, wrote nothing, and returned the OLD
    schedule as though the change had taken.
    """
    unknown = [d for d in days if d not in DAYS]
    if unknown:
        raise ProviderError(f"emailbison set_schedule: not days: {unknown}")
    if not days:
        raise ProviderError(
            "emailbison set_schedule: no sending days. A campaign that may "
            "send on no day is a campaign nobody meant to create")
    body = {day: (day in days) for day in DAYS}
    body.update({"start_time": start, "end_time": end, "timezone": timezone,
                 "save_as_template": False})
    # BOTH VERBS SPELLED OUT, and not chosen into a variable. Every HTTP
    # write in this repository has to be a literal a reader can find -
    # `tests/test_nothing_writes_to_a_provider` refuses a `request(verb, ...)`
    # outright - because a verb decided at runtime is a write no static read
    # can name. Two branches is the price of that, and it is worth it.
    url = SCHEDULE_PATH.format(campaign_id=campaign_id)
    if schedule(campaign_id):
        verb = "PUT"
        status, data = _put(url, body)
    else:
        verb = "POST"
        status, data = _post(url, body)
    if not ok(status):
        raise ProviderError(
            f"emailbison set_schedule: {verb} -> {status} {_message(data)}")
    answered = data.get("data") if isinstance(data, dict) else None
    if isinstance(answered, dict) and answered.get("success") is False:
        raise ProviderError(
            f"emailbison set_schedule: {verb} answered {status} and wrote "
            f"nothing: {_message(data)}. A sending window that was asked for "
            f"and not stored is the whole failure this call exists to catch")
    got = schedule(campaign_id)
    for day in DAYS:
        if bool(got.get(day)) != body[day]:
            raise ProviderError(
                f"emailbison set_schedule: asked for {day}={body[day]} and "
                f"the campaign reads back {got.get(day)!r}")
    for field, wanted in (("start_time", start), ("end_time", end)):
        if _hhmm(got.get(field)) != _hhmm(wanted):
            raise ProviderError(
                f"emailbison set_schedule: asked for {field}={wanted!r} and "
                f"campaign {campaign_id} reads back {got.get(field)!r}")
    if str(got.get("timezone")) != str(timezone):
        raise ProviderError(
            f"emailbison set_schedule: timezone reads back "
            f"{got.get('timezone')!r}, not {timezone!r}")
    return got


def schedule(campaign_id):
    """This campaign's schedule, or {} when it has none.

    A 200 IS NOT AN EXISTENCE PROOF HERE. With no schedule set, this route
    answers 200 carrying {"success": false, "message": "Schedule does not
    exist for <name>"} - so status-code checking reads absent as present.
    """
    status, data = request(
        "GET", base() + SCHEDULE_PATH.format(campaign_id=campaign_id),
        headers())
    if not ok(status):
        raise ProviderError(f"emailbison schedule: GET -> {status}")
    row = mapping(data, "schedule").get("data") or {}
    if row.get("success") is False:
        return {}
    return row


def attach_senders(campaign_id, sender_email_ids):
    """Bind the inboxes this campaign sends from, and read back who is bound.

    THE RESPONSE IS NOT THE ANSWER. This route returns 200 with
    `data.success: false` both for a repeat and for an empty array, so the
    status code cannot distinguish "attached" from "did nothing". The
    membership read is the oracle, and this raises unless every sender asked
    for is actually on the campaign afterwards.
    """
    wanted = [int(i) for i in (sender_email_ids or [])]
    if not wanted:
        raise ProviderError("emailbison attach_senders: no sender ids given")
    status, data = _post(SENDERS_PATH.format(campaign_id=campaign_id),
                         {"sender_email_ids": wanted})
    if not ok(status):
        raise ProviderError(
            f"emailbison attach_senders: POST -> {status} {_message(data)}")
    bound = campaign_senders(campaign_id)
    missing = [i for i in wanted if i not in bound]
    if missing:
        raise ProviderError(
            f"emailbison attach_senders: the provider answered {status} but "
            f"sender(s) {missing} are not on campaign {campaign_id}. This "
            f"route reports success for a write it did not make")
    return {"campaign_id": campaign_id, "senders": bound}


REMOVE_SENDERS_PATH = "/campaigns/{campaign_id}/remove-sender-emails"


def detach_senders(campaign_id, sender_email_ids):
    """Unbind inboxes from a campaign, and read back who is left.

    SUBTRACTIVE, NOT A SET. The vendor route removes the ids you name and
    leaves the rest, which is the mirror of `attach_senders` - measured today,
    attach ADDS: posting `[2736]` to a campaign holding `[2736, 3941]` left it
    holding both. So "this campaign now sends from exactly these inboxes" is
    reached by naming what to remove, never by naming what should remain.

    THE MEMBERSHIP READ IS THE ORACLE, for the same reason it is on attach:
    this API reports success for writes it did not make. This raises unless
    every sender asked for is actually GONE afterwards.

    DELETE FIRST, POST AS THE DOCUMENTED FALLBACK. The vendor's own page
    specifies DELETE in the endpoint block and POST in the curl example
    beneath it; an independent CLI implementation says DELETE. So DELETE is
    tried first and a 405 - the one status that means "wrong method" rather
    than "wrong request" - falls back to POST rather than being read as the
    route being absent. Any other failure raises.
    """
    wanted = [int(i) for i in (sender_email_ids or [])]
    if not wanted:
        raise ProviderError("emailbison detach_senders: no sender ids given")
    path = REMOVE_SENDERS_PATH.format(campaign_id=campaign_id)
    body = {"sender_email_ids": wanted}
    status, data = _delete(path, body)
    if status == 405:
        status, data = _post(path, body)
    if not ok(status):
        raise ProviderError(
            f"emailbison detach_senders: -> {status} {_message(data)}")
    bound = campaign_senders(campaign_id)
    still = [i for i in wanted if i in bound]
    if still:
        raise ProviderError(
            f"emailbison detach_senders: the provider answered {status} but "
            f"sender(s) {still} are STILL on campaign {campaign_id}. This "
            f"route reports success for a write it did not make")
    return {"campaign_id": campaign_id, "senders": bound}


def campaign_senders(campaign_id):
    """Which sender inboxes the PROVIDER says this campaign sends from.

    PAGED, because this route ignores `per_page` too. It was asked for 200 and
    answered 15 with `meta.total: 222` for campaign 352 - so `attach_senders`
    below, which reads this back to prove a bind took, would have raised
    "sender(s) are not on this campaign" for any campaign past fifteen
    inboxes, on a write that had in fact succeeded. Fifteen inboxes is a
    canary; a real campaign here runs on fifty-nine.
    """
    rows, _total = _paged(
        "campaign_senders",
        lambda page: query(f"{base()}/campaigns/{campaign_id}/sender-emails",
                           {"page": page}))
    return [r.get("id") for r in rows if isinstance(r, dict) and r.get("id")]


def lead(lead_id):
    """One lead as the provider holds it, custom variables included."""
    status, data = request("GET", f"{base()}/leads/{lead_id}", headers())
    if not ok(status):
        raise ProviderError(f"emailbison lead: GET -> {status}")
    return mapping(data, "lead").get("data") or {}


def update_lead(lead_id, fields):
    """Change a lead, and confirm the change is what the provider now holds.

    `PATCH /api/leads/{id}` MERGES custom variables rather than replacing the
    set, so a partial update leaves the names it did not mention alone. That
    is the behaviour wanted here - attribution is written once at creation and
    the copy is what changes - but it also means a variable cannot be removed
    by omitting it.

    Raises unless every variable asked for reads back with the value asked
    for. Copy that was updated and did not take is worse than copy that was
    never updated: the readback would look right and the wrong words would
    send.
    """
    status, data = _patch(f"/leads/{lead_id}", fields)
    if not ok(status):
        raise ProviderError(
            f"emailbison update_lead: PATCH -> {status} {_message(data)}")
    held = variables_of(lead(lead_id))
    for wanted in fields.get("custom_variables") or []:
        got = held.get(wanted["name"])
        # CLEARING A VARIABLE: THE PROVIDER STORES ABSENCE, NOT AN EMPTY STRING.
        #
        # `PATCH /leads/{id}` MERGES, so a variable cannot be removed by
        # omitting it - TASK-217 clears the numbered positions above the
        # sequence length by writing "" into them instead. The provider reads
        # those back as None, and comparing "" to None raised on a write that
        # had done exactly what was asked: measured on lead 203708,
        # `subject_2=''` reading back `None`.
        #
        # THIS IS NOT A LOOSENED COMPARISON. It is only reached when the value
        # ASKED FOR is empty, and the invariant those writes exist to enforce
        # is "this position carries no prospect-facing words". Absent and empty
        # both satisfy it; nothing else is accepted for either. A non-empty
        # value still has to match exactly, so copy that was updated and did
        # not take still raises - which is the failure this function is for.
        if not str(wanted["value"] or "") and not str(got or ""):
            continue
        if got != wanted["value"]:
            raise ProviderError(
                f"emailbison update_lead: asked for "
                f"{wanted['name']}={wanted['value'][:40]!r} and lead "
                f"{lead_id} reads back {str(got)[:40]!r}")
    return held


def campaign_lead_ids(campaign_id):
    """Every lead id the PROVIDER says is in this campaign, or a refusal.

    Membership read from the provider rather than from anything we remember
    writing. Paged, and it refuses past `PAGE_CAP` rather than returning a
    page: it used to take `per_page=200`, which this route ignores, and
    returned fifteen ids for a campaign of 21,159.

    For a big campaign the honest answers are `campaign_lead_count` and
    `membership(campaign, lead_ids)`, both of which are bounded, and this says
    so instead of guessing.
    """
    rows, _total = _paged(
        "campaign_lead_ids",
        lambda page: query(leads_endpoint(campaign_id), {"page": page}))
    return [r.get("id") for r in rows if isinstance(r, dict) and r.get("id")]


class LeadsNotAttachable(ProviderError):
    """This campaign may not hold these people, and the provider said so.

    Its own class because the caller has to be able to tell it from a
    transport failure: a retry fixes a 500 and cannot fix this.
    """


# The provider's own sentence for the refusal, lowercased. It names THREE
# different facts at once - in another sequence, previously bounced,
# unsubscribed - and two of them are suppression. Matching on it is matching
# on an ambiguity, which is exactly why `_attach_refusal` below goes and asks
# the leads rather than reporting this message as though it meant one thing.
REFUSED_ATTACH = "no leads were added"

# How many leads a refusal will interrogate before it stops. A refusal names
# none of them, so the diagnosis costs one GET per lead; on a campaign of two
# hundred that is two hundred reads on an error path. Bounded, and the message
# says the bound was reached rather than implying the rest are clean.
DIAGNOSE_AT_MOST = 50


def _attach_refusal(campaign_id, lead_ids, status, data):
    """Name WHO could not be attached and WHICH campaign is holding them.

    ONE PERSON, ONE LIVE SEQUENCE - AND THE PROVIDER ENFORCES IT SILENTLY.
    Measured 2026-09-13: a lead whose `lead_campaign_data` reads `in_sequence`
    for any campaign cannot be attached to a second one. The refusal is a 422
    naming no lead and no campaign, and it is all-or-nothing: one held person
    in a batch of two hundred attaches nobody.

    `in_sequence` is not the same as "the campaign is running". A lead
    attached to a campaign still in DRAFT reads `in_sequence` immediately;
    pausing that campaign moves it to `sending_paused` and it becomes
    attachable again. So the thing that holds a person is any campaign that
    has not been stopped, which a caller cannot see from its own state.

    The other two facts in the provider's sentence - bounced, unsubscribed -
    are suppression, and they are NOT reported as a sequence collision. An
    address nobody may write to and a person already in a cadence are
    different answers, and a caller that confused them would keep retrying a
    person it must never contact.
    """
    held, unknown, checked = [], [], list(lead_ids)[:DIAGNOSE_AT_MOST]
    for lead_id in checked:
        row = lead(lead_id)
        entries = [e for e in (row.get("lead_campaign_data") or [])
                   if isinstance(e, dict)]
        blocking = [e for e in entries
                    if str(e.get("status") or "").lower() == "in_sequence"
                    and str(e.get("campaign_id")) != str(campaign_id)]
        if blocking:
            held.append(f"{row.get('email') or lead_id} is in_sequence in "
                        f"campaign(s) "
                        f"{sorted(str(e.get('campaign_id')) for e in blocking)}")
        else:
            unknown.append(f"{row.get('email') or lead_id} "
                           f"({[e.get('status') for e in entries] or 'no campaign'})")
    tail = ("" if len(lead_ids) <= DIAGNOSE_AT_MOST else
            f" Only the first {DIAGNOSE_AT_MOST} of {len(lead_ids)} were "
            f"checked, so this list may be incomplete.")
    return (
        f"emailbison attach_leads: campaign {campaign_id} refused all "
        f"{len(lead_ids)} lead(s) with {status} - the provider says they are "
        f"'either in other sequences, have previously bounced, or "
        f"unsubscribed', which is three different facts in one sentence. "
        f"Held elsewhere: {held or 'none found'}. Not explained by a sequence "
        f"collision, so bounced or unsubscribed is the remaining reading and "
        f"this call will not guess which: {unknown or 'none'}.{tail} Nothing "
        f"was attached: this route is all-or-nothing.")


def attach_leads(campaign_id, lead_ids):
    """Put existing leads into a campaign, and prove they arrived.

    The verb the email lane was missing. `POST /api/campaigns/{id}/leads` is a
    405; this is the route that works, measured against a campaign and leads
    this system created on 2026-09-12.

    Idempotent on both sides. The provider itself refuses to double-add
    ("Existing leads were not added"), and this reads membership first, so a
    repeat costs one read per lead and writes nothing.

    BOTH READS ASK ABOUT THE LEADS THIS CALL NAMES, not about the campaign.
    They used to list the campaign's members, which serves fifteen rows
    whatever it is asked for - so for any campaign past its first page the
    readback found the leads absent and raised "the provider answered 200 but
    N leads are not in campaign X" on a write that had actually succeeded.
    Asking the named leads is exact at any campaign size, and it is bounded by
    the size of the batch rather than by the size of the campaign.

    Returns {"attached", "already", "members", "count"}, where `members` is
    the leads THIS CALL asked about that the provider confirms are in the
    campaign afterwards, and `count` is how many leads the campaign holds in
    total. A caller asking whether a lead is in a campaign reads `members`,
    never the status code.
    """
    wanted = [i for i in (lead_ids or []) if i is not None]
    if not wanted:
        raise ProviderError("emailbison attach_leads: no lead ids given")
    before = set(membership(campaign_id, wanted))
    missing = [i for i in wanted if int(i) not in before]
    if not missing:
        return {"attached": [], "already": list(wanted),
                "members": sorted(before),
                "count": campaign_lead_count(campaign_id)}
    status, data = _post(ATTACH_PATH.format(campaign_id=campaign_id),
                         {"lead_ids": missing})
    if not ok(status):
        if REFUSED_ATTACH in _message(data).lower():
            raise LeadsNotAttachable(_attach_refusal(campaign_id, missing,
                                                     status, data))
        raise ProviderError(
            f"emailbison attach_leads: POST attach-leads -> {status} "
            f"{_message(data)}")
    after = set(membership(campaign_id, wanted))
    absent = [i for i in wanted if int(i) not in after]
    if absent:
        raise ProviderError(
            f"emailbison attach_leads: the provider answered {status} but "
            f"{len(absent)} of {len(wanted)} leads are not in campaign "
            f"{campaign_id} on readback: {absent[:5]}")
    return {"attached": missing,
            "already": [i for i in wanted if int(i) in before],
            "members": sorted(after),
            "count": campaign_lead_count(campaign_id)}


def sequence_steps(campaign_id):
    """The steps this campaign actually holds, in the provider's own words.

    THE READBACK `set_sequence` NEVER HAD. Without it, writing a sequence was
    a write nobody could classify: `bisonfactory` passed a readback computed
    from its own input, so it compared the request to itself and always
    agreed. `GET /campaigns/{id}/sequence-steps` answers 200 with the stored
    steps, so the real question is answerable and now is.

    TWO THINGS ABOUT THIS ROUTE, BOTH MEASURED 2026-09-13 AND BOTH THE
    OPPOSITE OF ITS NEIGHBOURS.

    A 200 IS NOT AN EXISTENCE PROOF, exactly as on the schedule route: a
    campaign with no sequence answers 200 carrying `{"success": false,
    "message": "Sequence steps do not exist for <name>"}`, so absence is read
    from the body.

    AND IT IS NOT PAGINATED. Campaign 352 returns all 44 of its steps in one
    response with no `meta` at all, and `?page=2` returns the same 44. So this
    is one read and not a walk - which is why it does not go through `_paged`
    like the membership routes, and why that is stated rather than left to
    look like an oversight.
    """
    status, data = request(
        "GET", f"{base()}/campaigns/{campaign_id}/sequence-steps", headers())
    if not ok(status):
        raise ProviderError(f"emailbison sequence_steps: GET -> {status}")
    rows = mapping(data, "sequence_steps").get("data")
    if isinstance(rows, dict) and rows.get("success") is False:
        return []
    if not isinstance(rows, list):
        raise ProviderError(
            "emailbison sequence_steps: the step list is not a list and does "
            "not say the sequence is absent; refusing to read an unknown "
            "shape as 'this campaign has no sequence', which is what licenses "
            "writing one into a route that only appends")
    return [{"id": r.get("id"), "order": r.get("order"),
             "email_subject": r.get("email_subject"),
             "email_body": r.get("email_body"),
             "wait_in_days": r.get("wait_in_days"),
             "active": r.get("active"),
             "variant": r.get("variant"),
             "variant_from_step": r.get("variant_from_step"),
             "thread_reply": r.get("thread_reply")}
            for r in rows if isinstance(r, dict)]


def set_sequence(campaign_id, title, steps):
    """Write the campaign's sequence. Requires `title` AND `sequence_steps`.

    Measured 2026-09-12: an empty body answers 422 naming both as required,
    and `title` plus a NESTED `sequence_steps` array answers 201. A flat
    single step is rejected - the steps have to be nested.

    THIS APPENDS. IT DOES NOT REPLACE, AND NOTHING CAN. Measured 2026-09-13 on
    a throwaway campaign: writing one step, then another, left the campaign
    holding BOTH, and a third write of two steps left four - renumbered 1, 3,
    2, 4, so the orders interleave rather than following the writes. There is
    no removal: `/campaigns/{id}/sequence-steps` is GET, HEAD, POST only, PUT
    is 405, and no per-step route exists at all.

    So a campaign whose sequence is written twice sends twice, the second
    email carrying the older copy, and the only remedy is deleting the
    campaign. The caller is responsible for writing this ONLY into a campaign
    that holds no steps - `bisonfactory._ensure_sequence` reads
    `sequence_steps` first and refuses a mismatch rather than appending.
    """
    if not steps:
        raise ProviderError("emailbison set_sequence: no steps given")
    status, data = _post(f"/campaigns/{campaign_id}/sequence-steps",
                         {"title": title, "sequence_steps": list(steps)})
    if not ok(status):
        raise ProviderError(
            f"emailbison set_sequence: POST -> {status} {_message(data)}")
    return mapping(data, "set_sequence").get("data") or {}


def campaign(campaign_id):
    """One campaign as the provider states it, including `status`."""
    status, data = request("GET", f"{base()}/campaigns/{campaign_id}",
                           headers())
    if not ok(status):
        raise ProviderError(f"emailbison campaign: GET -> {status}")
    return mapping(data, "campaign").get("data") or {}


def scheduled_emails(campaign_id):
    """The pre-send queue for one campaign, AS THE PROVIDER WILL SEND IT.

    The only place the RENDERED copy is visible. `email_subject` and
    `email_body` here carry merge fields already resolved - measured against
    the client's live campaign, where the stored template
    `{me again, {FIRST_NAME}|...}` reads back as "me again, Matija". Rows go
    `scheduled` -> `sent` | `bounced` | `stopped`.

    So "did our copy render" is answerable BEFORE anybody receives anything,
    which is the difference between proving a template was stored and proving
    what a person will actually read.

    PAGED, AND `per_page` IS GONE because it never did anything. This route
    ignores it exactly as the membership routes do: campaign 352 asked for 50
    answers fifteen rows with `meta.total: 95312`. A queue read is consumed as
    "what is about to go out", and fifteen of ninety-five thousand answering
    that question is how a send nobody expected becomes a send nobody saw. A
    queue too big to walk raises rather than returning its first page.
    """
    rows, _total = _paged(
        "scheduled_emails",
        lambda page: query(
            f"{base()}/campaigns/{campaign_id}/scheduled-emails",
            {"page": page}))
    return rows


# WHAT A CAMPAIGN'S `status` CAN SAY, CLASSIFIED RATHER THAN ASSUMED.
# Observed on this instance: draft, paused, queued, active, failed, completed,
# archived, and "pending deletion". Only the first group means the provider
# accepted the start and is sending.
STARTED_STATES = ("active", "running", "completed")
# Accepted and NOT started yet. `PATCH .../resume` answers 200 and the row
# reads `queued` for a second or two while the provider decides - so `queued`
# is an unfinished answer, never a started one.
STARTING_STATES = ("queued", "starting")
NOT_STARTED_STATES = ("draft", "paused")
# The provider tried to start it and gave up. Measured twice on 2026-09-13: a
# campaign with a sequence, a schedule, a sender and a lead went queued ->
# failed within three seconds because its next sending window was six days
# away. It answers 200 the whole time.
FAILED_STATES = ("failed",)
# Queued for deletion and still answering GET with a row. Two seconds later
# the same GET is a 404. A binding pointing here is stale, not reusable.
PENDING_DELETION = "pending deletion"


def resume_campaign(campaign_id, expect_leads=None, attempts=8, interval=2.0):
    """Start a campaign sending, and confirm from the provider that it did.

    THE ONE VERB IN THIS MODULE THAT REACHES A PERSON. Everything else here
    stages or stops; this is what makes a staged sequence start emailing, and
    it is why `WRITE_ROUTES` names the resume path explicitly rather than
    letting it hide among the others.

    `expect_leads` is the containment. A resumed campaign sends to EVERY lead
    it holds, so the caller states how many it believes are in there and this
    refuses if the provider disagrees. A canary that was meant to reach one
    person and finds nine is stopped here rather than discovered afterwards -
    there is no recalling the other eight.

    The provider refuses an incomplete campaign in its own words: it wants a
    sequence, a schedule, senders AND leads. So a 400 is a statement about the
    campaign rather than a failed call.

    AND THE 200 IS NOT THE ANSWER EITHER. The readback used to accept any
    status that was not `draft` or `paused`, which made `queued` - the
    provider still thinking - and `failed` - the provider having given up -
    both read as started. Measured twice on 2026-09-13: `resume` answered 200,
    this returned `{"status": "queued"}`, and three seconds later the campaign
    read `failed` and never sent anything. An operator would have been told
    the campaign was live.

    So the status is classified rather than defaulted, and `queued` is polled
    out rather than reported. A resume whose outcome is still unknown when the
    polling runs out raises: "we do not know yet" and "it started" must not be
    the same answer on the one verb here that reaches a person.
    """
    import time

    if expect_leads is not None:
        # COUNTED FROM `meta.total`, NOT FROM A LIST. The list route serves
        # fifteen rows however many the campaign holds, so this guard used to
        # compare the caller's expectation against a page: `expect_leads=15`
        # would have passed on a campaign of twenty thousand people, on the
        # one check whose whole job is to stop a campaign reaching more people
        # than the caller believes.
        held = campaign_lead_count(campaign_id)
        if held != int(expect_leads):
            raise ProviderError(
                f"emailbison resume_campaign: campaign {campaign_id} holds "
                f"{held} lead(s) and the caller expected "
                f"{expect_leads}. Refusing to start a campaign whose reach is "
                f"not what the caller thinks it is")
    status, data = _patch(f"/campaigns/{campaign_id}/resume", {})
    if not ok(status):
        raise ProviderError(
            f"emailbison resume_campaign: PATCH -> {status} {_message(data)}")
    state = ""
    for attempt in range(attempts):
        if attempt:
            time.sleep(interval)
        state = str(campaign(campaign_id).get("status") or "").lower()
        if state in STARTED_STATES:
            return {"campaign_id": campaign_id, "status": state}
        if state in FAILED_STATES:
            raise ProviderError(
                f"emailbison resume_campaign: the provider answered {status} "
                f"and then moved campaign {campaign_id} to {state!r}. It is "
                f"NOT sending. One cause is known: a campaign whose next "
                f"sending window is days away fails this way within seconds")
        if state in NOT_STARTED_STATES:
            raise ProviderError(
                f"emailbison resume_campaign: the provider answered {status} "
                f"but campaign {campaign_id} still reads back as {state!r}")
        if state not in STARTING_STATES:
            raise ProviderError(
                f"emailbison resume_campaign: campaign {campaign_id} reads "
                f"back as {state!r}, which this module cannot classify as "
                f"started or not started. Refusing to report a send that "
                f"cannot be confirmed")
    raise ProviderError(
        f"emailbison resume_campaign: campaign {campaign_id} is still "
        f"{state!r} after {attempts * interval:.0f}s. Whether it is sending "
        f"is UNKNOWN - read provider truth before resuming again")


def pause_campaign(campaign_id):
    """Stop a campaign, and confirm from the provider that it stopped.

    `PATCH /api/campaigns/{id}/pause` -> 200, status `paused`, measured
    2026-09-12. The readback is the point: this returns the provider's own
    status string and raises when that status is not `paused`, so a local
    record can never say PAUSED while EmailBison is still sending.
    """
    status, data = _patch(f"/campaigns/{campaign_id}/pause", {})
    if not ok(status):
        raise ProviderError(
            f"emailbison pause_campaign: PATCH -> {status} {_message(data)}")
    state = str(campaign(campaign_id).get("status") or "").lower()
    if state != "paused":
        raise ProviderError(
            f"emailbison pause_campaign: the provider answered {status} but "
            f"campaign {campaign_id} reads back as {state!r}, not 'paused'")
    return {"campaign_id": campaign_id, "status": state}


# --------------------------------------------------------- inbound events
#
# What is confirmed: this deployment is a self-hosted EmailBison at BISON_BASE,
# and GET /campaigns answers. What is NOT confirmed is how reply events are
# retrieved - whether this instance exposes a webhook subscription, a polling
# endpoint, or neither. No path for it is guessed here.
#
# So the adapter is split in two. The mapping below is pure and fully tested:
# hand it a payload and it produces neutral events. The *retrieval* is refused
# until someone confirms the contract, exactly as Deliverable's was, because a
# polled endpoint invented from a plausible name either 404s or, far worse,
# returns something that parses and is wrong.

# --------------------------------------------------------- inbound events
#
# Confirmed live against this instance on 2026-08-26, read-only:
#
#   GET /api/replies -> {"data": [...], "meta": {"next_cursor", "prev_cursor",
#                        "per_page"}, "links": {...}}
#
# Cursor pagination, newest first. `meta.next_cursor` is an opaque base64
# string, and it is deliberately NOT stored as a checkpoint: it bounds the page
# to older rows, so resuming from it walks backwards into history and never
# returns to the head. `poller` keeps a high-water mark on `created_at` instead
# and uses this cursor only to page down within a single run.
#
# There is no webhook management endpoint on this instance (/api/webhooks
# answers 404), and the product documents no signature on the webhooks it can
# send. Polling is therefore the transport, and a webhook - if one is ever
# pointed at us - is treated as a hint to poll rather than as evidence.
#
# Confirmed against 30 real rows on 2026-08-26: `custom_variables` does NOT
# appear on a reply, and `lead`, `lead_id` and `campaign_id` were null on every
# historical row - those pre-date any lead created through the API. So identity
# for matching comes from `from_email_address` today, and the adapter reads
# custom_variables and lead only because a reply to a lead WE created should
# carry them. A row with neither is unmatched, never guessed.
#
# The trap, and it is a bad one: this feed carries our OWN sent mail.
#   type   Bounced | Outgoing Email | Untracked Reply | Tracked Reply
#   folder Bounced | Inbox | Sent
# Ingesting "Outgoing Email" as a reply would pause every company the moment we
# contacted it. reply_types() below is an allowlist, never a denylist.

EVENTS_CONTRACT_CONFIRMED = True          # for reading. Sending is not.


class EventContractNotConfirmed(ProviderError):
    """Kept for callers that still ask. Reading is confirmed; this is raised
    only if the confirmed path is reconfigured to something unread."""


def events_contract():
    """What is known about getting events out of this instance."""
    return {
        "provider": "emailbison",
        "confirmed": EVENTS_CONTRACT_CONFIRMED,
        "base": base(),
        "polling": "confirmed live: GET /api/replies, cursor paginated under "
                   "meta.next_cursor",
        "webhook": "the product can send them and documents no signature; this "
                   "instance exposes no /api/webhooks. Treated as a hint to "
                   "poll, never as evidence",
        "mapping": "src/adapters.from_emailbison, written against a real page",
        "hazard": "the feed carries our own sent mail as type 'Outgoing Email' "
                  "in folder 'Sent'. Never ingest it as a reply",
    }


REPLIES_PATH = "/replies"

# Sent, but this instance ignores it: 5, 15 and 50 all return 15 rows.
# Pagination is therefore entirely the cursor's job, which is why a repeating
# cursor has to be treated as the end rather than as a reason to ask again.
PER_PAGE_MAX = 100

# What each `type` means to us. Anything not named here is ignored, loudly.
REPLY_TYPES = ("untracked reply", "tracked reply", "reply")
BOUNCE_TYPES = ("bounced", "bounce")
OUTGOING_TYPES = ("outgoing email", "sent")


# A webhook names its own event; a polled row describes itself with type and
# folder. Both are understood, and both are allowlists.
WEBHOOK_REPLY = ("replied", "reply", "reply_received")
WEBHOOK_BOUNCE = ("bounced", "bounce")
WEBHOOK_DELIVERED = ("delivered", "sent", "email_sent")


def classify_reply_row(row):
    """reply | bounce | delivered | outgoing | unknown. An allowlist, on purpose."""
    # A row of the wrong type is unclassifiable, and this function already
    # has the word for that. It does not raise the way the body readers do:
    # `unknown` is the honest answer to "what is this", it is the answer
    # this allowlist gives to anything it does not recognise, and one
    # malformed row in a webhook batch must not stop the rest from being
    # read. What it must not do is crash on `.get`, which it did.
    row = row if isinstance(row, dict) else {}
    declared = str(row.get("event") or "").strip().lower()
    if declared:
        if declared in WEBHOOK_REPLY:
            return "reply"
        if declared in WEBHOOK_BOUNCE:
            return "bounce"
        if declared in WEBHOOK_DELIVERED:
            return "delivered"
        return "unknown"

    kind = str(row.get("type") or "").strip().lower()
    folder = str(row.get("folder") or "").strip().lower()
    if kind in OUTGOING_TYPES or folder == "sent":
        return "outgoing"
    if kind in BOUNCE_TYPES or folder == "bounced":
        return "bounce"
    if kind in REPLY_TYPES or folder == "inbox":
        return "reply"
    return "unknown"


def fetch_replies(cursor=None, per_page=PER_PAGE_MAX, path=REPLIES_PATH):
    """One page of replies. Read-only: this endpoint creates nothing.

    Returns (rows, next_cursor). The caller stores the cursor; this module
    holds no state of its own.

    `pagination_type=cursor` is not optional. EmailBison defaults to offset
    pagination, whose `meta` carries `current_page`/`last_page`/`total` and
    no `next_cursor`, and it refuses `page` beyond 1000 - so the default is
    both uncheckpointable and unable to reach a large reply history. Asking
    for cursor pagination is what makes `meta.next_cursor` below exist.
    """
    params = {"per_page": min(int(per_page), PER_PAGE_MAX),
              "pagination_type": "cursor"}
    if cursor:
        params["cursor"] = cursor
    status, data = request("GET", query(f"{base()}{path}", params), headers())
    if not ok(status):
        raise ProviderError(f"emailbison replies: {status}")
    if not isinstance(data, dict):
        raise ProviderError("emailbison replies: unexpected response shape")
    rows = data.get("data")
    if not isinstance(rows, list):
        # A 200 with no `data` array is a contract change, not an empty
        # feed. Flattening it to `[]` tells `poller.poll_emailbison` it has
        # caught up, and the run reports `events: 0` with no error - on the
        # one path whose job is to stop a cadence when somebody replies.
        # An empty list is a real "no replies" and passes straight through.
        raise ProviderError(
            "emailbison replies: no `data` array in the response (got "
            f"{type(rows).__name__}); refusing to read that as no replies")
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    return rows, meta.get("next_cursor")


def check():
    """Read-only: list campaigns. Creates nothing, sends nothing."""
    try:
        status, data = request("GET", f"{base()}/campaigns", headers())
        note = data if isinstance(data, str) else str(data)
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            note = f"{len(data['data'])} campaigns"
        return result("EmailBison", status, note)
    except ProviderError as e:
        return failed("EmailBison", e)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.providers.bison")
    p.add_argument("--check", action="store_true")
    p.parse_args(argv)
    r = check()
    print(f"{'ok  ' if r['ok'] else 'FAIL'} {r['provider']:<12} {r['status']}  {r['note']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
