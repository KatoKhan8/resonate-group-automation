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
LEAD_VARIABLES = ("subject", "body", "title", "record_id", "contact_key",
                  "client", "sender_id", "sender_account_id",
                  "provider_account_id")


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
    """Every custom variable declared on this workspace, by name."""
    status, data = request("GET", f"{base()}/custom-variables", headers())
    if not ok(status):
        raise ProviderError(f"emailbison custom_variables: GET -> {status}")
    rows = mapping(data, "custom_variables").get("data")
    if not isinstance(rows, list):
        raise ProviderError(
            "emailbison custom_variables: the list is not a list; refusing to "
            "read an unknown shape as 'nothing is declared'")
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
        status, data = request("POST", f"{base()}/custom-variables",
                               _json_headers(), {"name": name})
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
    "/campaigns/{campaign_id}/leads/stop-future-emails",   # stop ONE person
    "/campaigns/{campaign_id}/schedule",            # when it may send
    "/campaigns/{campaign_id}/attach-sender-emails",  # which inboxes
    "/leads",                                       # create a lead
    "/custom-variables",                            # declare a variable name
)


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
    status, data = request("POST", f"{base()}/leads", _json_headers(), fields)
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
    status, data = request("POST", f"{base()}/campaigns", _json_headers(),
                           {"name": name})
    if not ok(status):
        raise ProviderError(
            f"emailbison create_campaign: POST -> {status} {_message(data)}")
    row = mapping(data, "create_campaign").get("data") or {}
    if not row.get("id"):
        raise ProviderError(
            "emailbison create_campaign: the provider returned no id. A "
            "campaign may exist that nothing here can name; do NOT retry")
    return row


def find_lead_by_email(email):
    """The one lead with this address, or None. Never a guess.

    `?search=` is the only real filter on this route: a nonsense term returns
    nothing and a known address returns exactly its lead. `?email=` is NOT -
    it is accepted and discarded, and answers with an unfiltered page, which
    is the same trap `workspace_id` sets elsewhere in this API.

    It lags behind creation, so a lead made seconds ago may not be findable.
    That is why this is a reconciliation path and not the primary one, and why
    an ambiguous answer raises instead of picking a row.
    """
    import urllib.parse

    address = str(email or "").strip().lower()
    if not address:
        raise ProviderError("emailbison find_lead_by_email: no address given")
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
    if not exact:
        return None
    if len(exact) > 1:
        raise ProviderError(
            f"emailbison find_lead_by_email: {len(exact)} leads carry "
            f"{address!r}. Refusing to choose one")
    return exact[0]


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
    status, data = request(
        "PATCH", base() + UPDATE_PATH.format(campaign_id=campaign_id),
        _json_headers(),
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


def membership(campaign_id, lead_ids=None, per_page=200):
    """Each lead's status IN THIS CAMPAIGN, as the provider states it.

    `lead_campaign_data` is an ARRAY - one entry per campaign the lead belongs
    to - so it is filtered by `campaign_id` here. Reading element zero returns
    another campaign's status for a lead that is in several, which is a
    mistake that reads as a successful stop.
    """
    wanted = None if lead_ids is None else {int(i) for i in lead_ids}
    url = query(leads_endpoint(campaign_id), {"per_page": per_page})
    status, data = request("GET", url, headers())
    if not ok(status):
        raise ProviderError(f"emailbison membership: GET -> {status}")
    rows = mapping(data, "membership").get("data")
    if not isinstance(rows, list):
        raise ProviderError(
            "emailbison membership: the campaign lead list is not a list; "
            "refusing to read an unknown shape as empty membership")
    out = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        if wanted is not None and int(row["id"]) not in wanted:
            continue
        for entry in row.get("lead_campaign_data") or []:
            if isinstance(entry, dict) and str(entry.get("campaign_id")) == str(
                    campaign_id):
                out[int(row["id"])] = entry.get("status")
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

    Returns {"stopped": {...}, "untouched": {...}} - the second being every
    other member of the campaign, so a caller can see that stopping one
    person left the rest alone.
    """
    import time

    wanted = [int(i) for i in (lead_ids or [])]
    if not wanted:
        raise ProviderError("emailbison stop_lead: no lead ids given")
    before = membership(campaign_id)
    absent = [i for i in wanted if i not in before]
    if absent:
        raise ProviderError(
            f"emailbison stop_lead: lead(s) {absent[:5]} are not in campaign "
            f"{campaign_id}. This route answers 200 for them and does "
            f"nothing, so refusing rather than reporting a stop that cannot "
            f"happen")
    status, data = request(
        "POST", base() + STOP_PATH.format(campaign_id=campaign_id),
        _json_headers(), {"lead_ids": wanted})
    if not ok(status):
        raise ProviderError(
            f"emailbison stop_lead: POST -> {status} {_message(data)}")

    for attempt in range(attempts):
        time.sleep(interval if attempt else 0.5)
        now = membership(campaign_id)
        pending = [i for i in wanted
                   if str(now.get(i) or "").lower() not in STOPPED_STATES]
        if not pending:
            moved = {i: before.get(i) for i in before
                     if i not in wanted and before.get(i) != now.get(i)}
            if moved:
                raise ProviderError(
                    f"emailbison stop_lead: stopping {wanted} also changed "
                    f"{moved}. Refusing to report a per-lead stop that was "
                    f"not per-lead")
            return {"stopped": {i: now.get(i) for i in wanted},
                    "untouched": {i: now.get(i) for i in now
                                  if i not in wanted}}
    raise ProviderError(
        f"emailbison stop_lead: the provider accepted the request but lead(s) "
        f"{pending[:5]} still do not read as stopped after "
        f"{attempts * interval:.0f}s. Provider state is UNKNOWN - do not "
        f"record a stop, and do not retry blindly")


SCHEDULE_PATH = "/campaigns/{campaign_id}/schedule"
SENDERS_PATH = "/campaigns/{campaign_id}/attach-sender-emails"

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
        "sunday")


def set_schedule(campaign_id, days, start, end, timezone):
    """When this campaign is allowed to send, and confirm it took.

    All eleven fields are required by the provider - a partial body is a 422.
    `days` names the sending days; everything else is explicitly false rather
    than omitted, because an omitted day is a validation error and not a
    quiet no.

    Round-trip asymmetry to know about: a time written as "09:00" reads back
    as "09:00:00", so the readback compares the hour and minute rather than
    the string.
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
    status, data = request(
        "POST", base() + SCHEDULE_PATH.format(campaign_id=campaign_id),
        _json_headers(), body)
    if not ok(status):
        raise ProviderError(
            f"emailbison set_schedule: POST -> {status} {_message(data)}")
    got = schedule(campaign_id)
    for day in DAYS:
        if bool(got.get(day)) != body[day]:
            raise ProviderError(
                f"emailbison set_schedule: asked for {day}={body[day]} and "
                f"the campaign reads back {got.get(day)!r}")
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
    status, data = request(
        "POST", base() + SENDERS_PATH.format(campaign_id=campaign_id),
        _json_headers(), {"sender_email_ids": wanted})
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


def campaign_senders(campaign_id):
    """Which sender inboxes the PROVIDER says this campaign sends from."""
    status, data = request(
        "GET", f"{base()}/campaigns/{campaign_id}/sender-emails?per_page=200",
        headers())
    if not ok(status):
        raise ProviderError(f"emailbison campaign_senders: GET -> {status}")
    rows = mapping(data, "campaign_senders").get("data")
    if not isinstance(rows, list):
        raise ProviderError(
            "emailbison campaign_senders: the sender list is not a list; "
            "refusing to read an unknown shape as 'no senders bound'")
    return [r.get("id") for r in rows if isinstance(r, dict) and r.get("id")]


def campaign_lead_ids(campaign_id, per_page=200):
    """Which lead ids the PROVIDER says are in this campaign.

    Membership read from the provider rather than from anything we remember
    writing. Used to confirm an attach and to make one idempotent.
    """
    url = query(leads_endpoint(campaign_id), {"per_page": per_page})
    status, data = request("GET", url, headers())
    if not ok(status):
        raise ProviderError(f"emailbison campaign_lead_ids: GET -> {status}")
    rows = mapping(data, "campaign_lead_ids").get("data")
    if not isinstance(rows, list):
        raise ProviderError(
            "emailbison campaign_lead_ids: the campaign lead list is not a "
            "list; refusing to read an unknown shape as empty membership")
    return [r.get("id") for r in rows if isinstance(r, dict) and r.get("id")]


def attach_leads(campaign_id, lead_ids):
    """Put existing leads into a campaign, and prove they arrived.

    The verb the email lane was missing. `POST /api/campaigns/{id}/leads` is a
    405; this is the route that works, measured against a campaign and leads
    this system created on 2026-09-12.

    Idempotent on both sides. The provider itself refuses to double-add
    ("Existing leads were not added"), and this reads membership first, so a
    repeat costs one GET and writes nothing.

    Returns {"attached", "already", "members"}, where `members` is the
    provider's own membership AFTER the write. A caller asking whether a lead
    is in a campaign reads `members`, never the status code: this raises when
    the readback lacks what was asked for, so a silent partial attach cannot
    be reported as success.
    """
    wanted = [i for i in (lead_ids or []) if i is not None]
    if not wanted:
        raise ProviderError("emailbison attach_leads: no lead ids given")
    before = set(campaign_lead_ids(campaign_id))
    missing = [i for i in wanted if i not in before]
    if not missing:
        return {"attached": [], "already": list(wanted),
                "members": sorted(before)}
    status, data = request(
        "POST", base() + ATTACH_PATH.format(campaign_id=campaign_id),
        _json_headers(), {"lead_ids": missing})
    if not ok(status):
        raise ProviderError(
            f"emailbison attach_leads: POST attach-leads -> {status} "
            f"{_message(data)}")
    after = set(campaign_lead_ids(campaign_id))
    absent = [i for i in wanted if i not in after]
    if absent:
        raise ProviderError(
            f"emailbison attach_leads: the provider answered {status} but "
            f"{len(absent)} of {len(wanted)} leads are not in campaign "
            f"{campaign_id} on readback: {absent[:5]}")
    return {"attached": missing, "already": [i for i in wanted if i in before],
            "members": sorted(after)}


def set_sequence(campaign_id, title, steps):
    """Write the campaign's sequence. Requires `title` AND `sequence_steps`.

    Measured 2026-09-12: an empty body answers 422 naming both as required,
    and `title` plus a NESTED `sequence_steps` array answers 201. A flat
    single step is rejected - the steps have to be nested.
    """
    if not steps:
        raise ProviderError("emailbison set_sequence: no steps given")
    status, data = request(
        "POST", f"{base()}/campaigns/{campaign_id}/sequence-steps",
        _json_headers(), {"title": title, "sequence_steps": list(steps)})
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


def pause_campaign(campaign_id):
    """Stop a campaign, and confirm from the provider that it stopped.

    `PATCH /api/campaigns/{id}/pause` -> 200, status `paused`, measured
    2026-09-12. The readback is the point: this returns the provider's own
    status string and raises when that status is not `paused`, so a local
    record can never say PAUSED while EmailBison is still sending.
    """
    status, data = request("PATCH", f"{base()}/campaigns/{campaign_id}/pause",
                           _json_headers(), {})
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
