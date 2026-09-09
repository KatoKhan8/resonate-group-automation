#!/usr/bin/env python3
"""EmailBison. BUILD-SPEC section 5.4.

Base https://send.resonategroup.co/api (override with BISON_BASE),
Authorization: Bearer <BISON_KEY>.

Phase 3 is auth, health and the request builder only. There is deliberately no
send function in this module: adding leads to a campaign is phase 7, where dry
run is the default and --live is explicit. The builder puts the generated
subject and body in custom_variables so the client's existing 5 to 7 step
cadence continues after step one.

  python -m src.providers.bison --check      read-only campaign list
"""
import argparse
import os

from . import ProviderError, key, ok, query, request, result, failed

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
        "custom_variables": {"subject": r.get("subject", ""),
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
                                 "provider_account_id", "")},
    } for r in rows]}


def leads_endpoint(campaign_id):
    """The URL phase 7 will POST to. Named here so it is reviewable."""
    return f"{base()}/campaigns/{campaign_id}/leads"


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
