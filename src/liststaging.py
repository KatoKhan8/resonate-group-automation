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
    if not str(row.get("linkedin_url") or "").strip():
        problems.append("linkedin_url is required")
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
    read = list_reader or heyreach.list_by_id
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

    expected = {str(u).strip().lower() for u in expected_urls if u}
    if not expected:
        raise ListStagingRefused(
            "readback with no expected URLs verifies nothing")

    members, total = read_members(list_id)
    found = set()
    for m in members:
        url = str(m.get("profile_url") or "").strip().lower()
        if url in expected:
            found.add(url)

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

    url = str(row.get("linkedin_url") or "").strip().lower()
    payload = {
        "listId": int(list_id),
        "leads": [{
            "profileUrl": str(row.get("linkedin_url") or "").strip(),
            "firstName": str(row.get("first_name") or "").strip(),
            "lastName": str(row.get("last_name") or "").strip(),
            "companyName": str(row.get("company") or "").strip(),
            "position": str(row.get("title") or "").strip(),
        }],
    }

    try:
        response = transport(payload)
    except Exception as e:
        raise ListStagingUnverified(
            f"list add raised {type(e).__name__}: the provider may have "
            f"acted. Read provider truth before retrying") from None

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
        "response": response,
        "readback": rb,
    }


class ListStagingUnverified(RuntimeError):
    """The transport succeeded but the readback could not confirm.

    The provider may have acted. Do NOT retry without reading provider truth.
    """
