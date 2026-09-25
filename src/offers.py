"""The Offer Engine.

Offers are DATA, never generated. Every offer is loaded from
`config/clients/productive-offers.yaml` and nothing in this module calls an
LLM, reads an LLM response, or constructs an offer from anything other than
that file.

Schema from ARCHITECTURE-UPGRADE-SPEC section 3E: offer id, segment, persona,
business problem, value proposition, concrete deliverable, supporting
evidence, CTA, conditions, approval status, version, campaigns using it.

The rule: an offer whose `approval_status` is not `approved` CANNOT reach
copy generation. `for_campaign(campaign_id, require_approved=True)` raises
`NotApproved` rather than returning one. Production does not approve its own
offers - this is the same shape as `reviewapproval`.

Ships with the six confirmed capabilities from `product.capabilities` in
`productive.yaml` and nothing else: project_management, time_tracking,
budgeting, resource_planning, billing, profitability.
"""
import os

from . import clients

#: The six capabilities Productive actually has. An offer naming anything
#: outside this set is an invented capability and must not pass.
CONFIRMED_CAPABILITIES = frozenset({
    "project_management",
    "time_tracking",
    "budgeting",
    "resource_planning",
    "billing",
    "profitability",
})

#: Only this value lets an offer reach copy generation.
APPROVED = "approved"


class NotApproved(Exception):
    """An offer whose approval_status is not 'approved' was requested for
    copy generation. Production does not approve its own offers."""


def _offers_path():
    return os.path.join(
        os.path.dirname(clients.path_for("productive")),
        "productive-offers.yaml",
    )


def _load_raw():
    """Parse the offers file. No caching - the file is small and changes
    only when the operator edits it."""
    path = _offers_path()
    with open(path, "r", encoding="utf-8") as fh:
        return clients.parse(fh.read())


def _validate(offer_id, offer):
    """An offer that names a capability Productive does not have is rejected
    at load time rather than reaching a prompt."""
    cap = offer.get("capability")
    if cap and cap not in CONFIRMED_CAPABILITIES:
        raise ValueError(
            f"offer {offer_id} names capability {cap!r} which is not in "
            f"Productive's confirmed capabilities: {sorted(CONFIRMED_CAPABILITIES)}"
        )
    status = offer.get("approval_status")
    if status is None:
        raise ValueError(
            f"offer {offer_id} has no approval_status; it must be explicit"
        )


def load():
    """Return the offers dict, validated. Keys are offer IDs."""
    raw = _load_raw()
    offers = raw.get("offers") or {}
    for offer_id, offer in offers.items():
        _validate(offer_id, offer)
    return offers


def for_campaign(campaign_id, require_approved=False):
    """Return the offers assigned to `campaign_id`.

    If `require_approved` is True, every returned offer has been checked:
    any offer whose `approval_status` is not `approved` raises `NotApproved`
    before anything is returned. This is a refusal, not a warning.
    """
    offers = load()
    matched = {
        oid: offer for oid, offer in offers.items()
        if campaign_id in (offer.get("campaigns") or [])
    }
    if require_approved:
        for oid, offer in matched.items():
            if offer.get("approval_status") != APPROVED:
                raise NotApproved(
                    f"offer {oid} has approval_status="
                    f"{offer.get('approval_status')!r}, not 'approved'. "
                    f"Production does not approve its own offers."
                )
    return matched


def missing():
    """Return what the client must supply.

    Seeded from what is already known absent: no customer case studies, no
    verified benchmarks, no dashboard or workflow example, no calculator,
    no demo link. Returns a list of dicts with `gap` and `detail` keys.
    """
    raw = _load_raw()
    gaps = raw.get("missing") or {}
    return [
        {"gap": v.get("gap", k), "detail": v.get("detail", "")}
        for k, v in gaps.items()
    ]


def all_offers():
    """Every offer, for the index page. Not for prompts."""
    return load()
