"""List-level staging: the primitive that exists because campaigns cannot.

WHY A SEPARATE MODULE.

`providerwrites.py` owns the write gate and this task may not modify it.
`heyreach.py` owns the transport and knows nothing about safety. The list
staging primitive sits between them: it validates the lead, asserts the list
is safe, calls the transport, and reads back — the same four-step shape
`providerwrites.perform` uses for every other write, applied to a route that
is not yet in `SUPPORTED`.

When an operator decides to promote this into `SUPPORTED`, the operation
name is `heyreach.add_lead_to_list`, it is NOT prospect-facing, and its
`CONDITIONAL` entry points at `assert_list_safe`.

THE SAFETY PROPERTY.

A list is safe to stage into exactly when it is unbound — attached to no
campaign. `campaignIds` is a provider fact that can change without us: a
human can attach a list to a campaign in the vendor UI. So the predicate is
checked at the provider immediately before every add, not remembered from a
prior read.

The moment a list is attached to a campaign, adding to it is adding to a
campaign, and the campaign-level gate (`LINKEDIN_ADD_LEAD` with its
conditional permission) is the only path through.
"""
from .providers import heyreach
from .providerwrites import LINKEDIN_ADD_LEAD_TO_LIST


class ListStagingRefused(RuntimeError):
    """A list staging write was refused before the transport was touched."""


# -------------------------------------------------------------- validation

def canonical_profile_url(value):
    """A full LinkedIn profile URL, or None if this cannot be made into one.

    WHY THIS EXISTS, MEASURED. The first live canary staging attempt on
    2026-09-16 sent the record's `linkedin` field straight through as
    `profileUrl`. That field holds a bare VANITY SLUG - 23 characters, no
    scheme, no host - and the provider accepted the request and added nothing.
    The readback caught it (lead missing, total unchanged), which is the system
    working, but the lead had already been silently dropped once.

    TASK-158 established the working shape against the provider, and it is a
    full URL: `https://www.linkedin.com/in/<slug>`. So a slug is not a
    profileUrl, and the difference is invisible in a 200 response.

    Returns a canonical `https://www.linkedin.com/in/<slug>` for either input
    shape, or None for something that is neither - which `validate_lead_row`
    turns into a refusal BEFORE the transport, where a silent drop cannot
    happen.
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    low = raw.lower()
    if "linkedin.com" in low:
        # Already a URL. Normalise the scheme and host, keep the slug.
        tail = raw.split("linkedin.com", 1)[1].lstrip("/")
        if tail.startswith("in/"):
            slug = tail[3:]
        elif tail.startswith("pub/"):
            slug = tail[4:]
        else:
            slug = tail
        slug = slug.split("?")[0].split("#")[0].strip("/")
        return f"https://www.linkedin.com/in/{slug}" if slug else None
    if "/" in raw or " " in raw or "." in raw:
        # Not a slug and not a linkedin.com URL. Refuse rather than guess: a
        # guessed URL is a lead added for somebody who may not be the prospect.
        return None
    return f"https://www.linkedin.com/in/{raw}"


def validate_lead_row(row):
    """Refuse a lead that the provider would silently drop.

    `firstName` and `lastName` are required. The provider returns
    `addedLeadsCount: 0` with no error for a lead missing either — a 200
    response is not a success. A code path that treats a 200 as a staged
    lead is the defect this function exists to prevent.

    Returns True on success. Raises `ListStagingRefused` with every problem
    named, so a caller can report all of them rather than one at a time.
    """
    row = row or {}
    problems = []
    if not str(row.get("first_name") or "").strip():
        problems.append("firstName is required")
    if not str(row.get("last_name") or "").strip():
        problems.append("lastName is required")
    raw_url = str(row.get("linkedin_url") or "").strip()
    if not raw_url:
        problems.append("linkedin_url is required")
    elif not canonical_profile_url(raw_url):
        problems.append(
            f"linkedin_url {raw_url[:12]!r}... cannot be made into a "
            f"canonical profile URL. The provider accepts "
            f"https://www.linkedin.com/in/<slug> and silently drops anything "
            f"else with a 200")
    if problems:
        raise ListStagingRefused(
            f"lead would be silently dropped by the provider: "
            f"{'; '.join(problems)}")
    return True


# --------------------------------------------------------- safety predicate

def list_is_unbound(list_row):
    """True only when the list is attached to no campaign.

    `campaignIds` is a provider fact. A list created by hand in the vendor
    UI starts with `campaignIds: []`. The moment it is attached to a
    campaign, adding to it is adding to that campaign — which is the
    prospect-facing path this module deliberately is not.
    """
    ids = list_row.get("campaignIds") or []
    if isinstance(ids, (list, tuple)):
        return len(ids) == 0
    return False


_ACTIVE_LIST_READER = None


def assert_list_safe(list_id, list_reader=None):
    """Read the list from the provider and refuse unless it is unbound.

    `list_reader` is injected for testing. Defaults to `heyreach.list_by_id`.
    Raises `ListStagingRefused` if the list is bound, unreadable, or belongs
    to no identifiable tenant.

    THE READ IS LIVE, NOT REMEMBERED. A list that was unbound at planning
    time can be attached to a campaign by the time the write arrives. This
    is the same shape as `_campaign_is_a_declared_staging_campaign` — a
    provider read at the moment of the write.
    """
    # `_ACTIVE_LIST_READER` exists because `perform` evaluates this module's
    # condition through `CONDITIONAL`, and its call signature is fixed at
    # (provider_campaign_id, campaign_id) - there is nowhere to pass a reader.
    # Without this, routing `stage_lead` through `perform` made the condition
    # read the LIVE provider even when the caller had injected a fake, so
    # every test hit a missing HEYREACH_KEY and the double read cost a real
    # API call per write in production too.
    #
    # `stage_lead` sets it for the duration of its own call and clears it in a
    # finally. Outside that window it is None and the live reader is used,
    # which is the correct default for any other caller.
    read = list_reader or _ACTIVE_LIST_READER or heyreach.list_by_id
    if list_id in (None, "", 0):
        raise ListStagingRefused(
            "no list_id supplied; a list add without a destination verifies "
            "nothing")
    try:
        row = read(list_id)
    except Exception as e:
        raise ListStagingRefused(
            f"list {list_id} could not be read "
            f"({type(e).__name__}: {e}). A list whose state is unknown is "
            f"not proven safe. The transport was not reached") from None
    if not row or not row.get("id"):
        raise ListStagingRefused(
            f"list {list_id} returned no row or no id. A missing list is "
            f"not an unbound one. The transport was not reached")
    if not list_is_unbound(row):
        bound_to = row.get("campaignIds") or []
        raise ListStagingRefused(
            f"list {list_id} is attached to campaign(s) "
            f"{bound_to}. Adding a lead to a bound list is adding to a "
            f"campaign, which is the prospect-facing path and not staging. "
            f"The transport was not reached")
    return row


# ------------------------------------------------------------ readback

def readback_list_add(list_id, expected_urls, list_reader=None,
                      members_reader=None):
    """Prove the lead is present AND the list is still unbound.

    Two reads, two questions:

      1. `members_reader` (default `heyreach.list_leads`) — is the lead
         there? `addedLeadsCount: 1` from the write response is the
         provider's claim about its own write, not a readback.
      2. `list_reader` (default `heyreach.list_by_id`) — is the list still
         unbound? A list that was unbound before the add and bound after
         means the add triggered a binding change.

    Returns a dict with `found`, `missing`, `total`, `still_unbound`, and
    `list_row`. The caller classifies: ACCEPTED iff `found == expected` AND
    `still_unbound` is True.
    """
    read_list = list_reader or heyreach.list_by_id
    read_members = members_reader or heyreach.list_leads

    # BOTH SIDES CANONICAL. Lowercasing alone compared a URL to a URL in a
    # different shape: the provider may answer with or without `www`, with a
    # trailing slash, or with a tracking query, and the estate stores some
    # profiles as bare vanity slugs. Comparing raw strings made a lead that
    # WAS in the list read as missing, which classifies as UNKNOWN and raises
    # - a false alarm indistinguishable from a real silent drop.
    expected = {canonical_profile_url(u).lower()
                for u in expected_urls if u and canonical_profile_url(u)}
    if not expected:
        raise ListStagingRefused(
            "readback with no expected URLs verifies nothing")

    members, total = read_members(list_id)
    found = set()
    for m in members:
        canon = canonical_profile_url(m.get("profile_url"))
        if canon and canon.lower() in expected:
            found.add(canon.lower())

    list_row = read_list(list_id)
    still_unbound = list_is_unbound(list_row)

    return {
        "found": found,
        "missing": expected - found,
        "total": total,
        "still_unbound": still_unbound,
        "list_row": list_row,
    }


def classify_readback(readback_result):
    """ACCEPTED, DRIFTED, or UNKNOWN from a readback result.

    ACCEPTED: every expected lead found AND list still unbound.
    DRIFTED: list became bound (the activation defect).
    UNKNOWN: one or more leads missing.
    """
    if not readback_result.get("still_unbound"):
        return "DRIFTED"
    if readback_result.get("missing"):
        return "UNKNOWN"
    return "ACCEPTED"


# --------------------------------------------------------- full staging path

def stage_lead(list_id, row, transport, list_reader=None,
               members_reader=None):
    """The full list staging path: validate, gate, transport, readback.

    Returns a result dict on success. Raises `ListStagingRefused` before the
    transport is touched, or `ListStagingUnverified` if the transport
    succeeded but the readback could not confirm.

    `transport` is a callable that takes the payload dict and returns the
    provider response. It is injected so this function can be tested without
    a live provider.
    """
    validate_lead_row(row)
    assert_list_safe(list_id, list_reader=list_reader)

    # ONE canonical URL, used for the payload AND the readback comparison.
    # They were derived separately before, so a slug went to the provider and
    # a lowercased slug was looked for in the readback - both wrong, and
    # consistently wrong, which is how it looked like a provider problem.
    canonical = canonical_profile_url(row.get("linkedin_url"))
    url = canonical.lower()
    payload = {
        "listId": int(list_id),
        "leads": [{
            "profileUrl": canonical,
            "firstName": str(row.get("first_name") or "").strip(),
            "lastName": str(row.get("last_name") or "").strip(),
            "companyName": str(row.get("company") or "").strip(),
            "position": str(row.get("title") or "").strip(),
        }],
    }

    # THE WRITE GOES THROUGH THE DOOR, NOT ROUND IT.
    #
    # This function used to call `transport(payload)` directly. Its own checks
    # - `validate_lead_row`, `assert_list_safe`, and the readback below - were
    # real, and they were not everything. Going direct skipped
    # `providerwrites.require_supported` (so the permission the operator
    # granted on 2026-09-16 would have governed a path nobody called), the
    # action ledger, the spend ledger, the killswitch, and the idempotency
    # check that stops the same material being staged twice.
    #
    # The operator's authorization was explicit that audit, ledger, killswitch
    # and the fail-closed gates are preserved. A path around `perform` does
    # not preserve them, so the path was moved. Found 2026-09-16 by a test
    # that had been written to assert the bypass - TASK-186's
    # `test_perform_refuses_the_same_write`, which said in its own docstring
    # that "the wrapper that unifies them does not exist yet".
    #
    # THE LOCAL CHECKS ABOVE STAY. `perform` runs the condition too, so
    # `assert_list_safe` is asked twice. Two gates asking the same question is
    # not a defect; it is the cheaper one failing first, before any network
    # read, and the authoritative one failing at the moment of the write.
    from . import providerwrites

    # `perform` owns the call now, so the provider's own response is captured
    # here rather than returned by an assignment. It is still reported in the
    # result dict, because `addedLeadsCount` is the provider's claim about its
    # own write and is worth recording next to the readback that checks it.
    captured = {}

    def _transport(p):
        captured["response"] = transport(p)
        return captured["response"]

    def _readback():
        rb = readback_list_add(list_id, [url], list_reader=list_reader,
                               members_reader=members_reader)
        return {"class": classify_readback(rb), "detail": rb}

    global _ACTIVE_LIST_READER
    _previous_reader = _ACTIVE_LIST_READER
    _ACTIVE_LIST_READER = list_reader
    try:
        providerwrites.perform(
            LINKEDIN_ADD_LEAD_TO_LIST,
            provider_campaign_id=list_id,
            payload=payload,
            transport=_transport,
            readback=_readback,
            expected={"class": "ACCEPTED"},
            step="list-staging",
        )
    except providerwrites.WriteRefused as e:
        # A refusal means nothing happened at the provider, which is exactly
        # what `ListStagingRefused` means to this module's callers.
        raise ListStagingRefused(str(e)) from None
    except Exception as e:
        # Anything else - an unverified write, a drifted read-back, a
        # transport that raised - is the state where the provider MAY have
        # acted. It is never retryable without reading provider truth first.
        raise ListStagingUnverified(
            f"{type(e).__name__} staging into list {list_id}: {e}") from None
    finally:
        _ACTIVE_LIST_READER = _previous_reader

    rb = readback_list_add(list_id, [url], list_reader=list_reader,
                           members_reader=members_reader)
    verdict = classify_readback(rb)
    if verdict != "ACCEPTED":
        raise ListStagingUnverified(
            f"list add readback says {verdict}: expected {url!r} in list "
            f"{list_id}, found {rb.get('found')}, missing {rb.get('missing')}"
            f"{', list became bound' if verdict == 'DRIFTED' else ''}")

    return {
        "operation": LINKEDIN_ADD_LEAD_TO_LIST,
        "class": verdict,
        "list_id": list_id,
        "profile_url": url,
        "response": captured.get("response"),
        "readback": rb,
    }


class ListStagingUnverified(RuntimeError):
    """The transport succeeded but the readback could not confirm.

    The provider may have acted. Do NOT retry without reading provider truth.
    """
