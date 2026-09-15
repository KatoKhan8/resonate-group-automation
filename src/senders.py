#!/usr/bin/env python3
"""Which account a given contact is sent from, and why it is always that one.

Assignment is deterministic: the same contact lands on the same sender on every
rerun, on any machine, in any order. That is not a nicety. A contact that hops
between inboxes on a rerun looks to a mailbox provider like two strangers
writing about the same thing, and to the prospect like an organisation that has
lost track of itself. The mapping is a hash of the contact's own identity over
the eligible accounts, so it is stable without anything having to be stored.

An account is eligible when it is enabled, belongs to this client's campaign,
and has not used up its daily allowance. Everything else - who is over cap, who
is disabled, which channel has no account at all - is reported rather than
worked around, because silently sending from the wrong account is worse than
not sending.

Config lives on the campaign, not in this module:

    senders:
      email:    [{id: bison-1, daily_limit: 40}, {id: bison-2, enabled: false}]
      linkedin: [{id: hr-9, daily_limit: 20}]
"""
import hashlib

EMAIL = "email"
LINKEDIN = "linkedin"
CHANNELS = (EMAIL, LINKEDIN)

DEFAULT_DAILY_LIMIT = 50


class NoSenderAvailable(RuntimeError):
    """No account can carry this step. Nothing is assigned, nothing is sent."""


def accounts(campaign, channel):
    """Every account configured for a channel, in a stable order.

    TWO SPELLINGS OF ONE IDENTIFIER, and this is the third place that had to
    learn about it. A campaign sender row is `{"id": ...}` here, and
    `senderidentity` writes seats as `provider_account_id` - so a campaign row
    populated from a seat carries a key this function did not look for, the
    row was skipped, and `check_mapping` reported "no account configured" for
    a campaign whose seat was correct.

    Measured on campaign 599020 the same afternoon: the identical mismatch
    also emptied `configdiff._ids` (approved sender set frozenset()) and
    `executionguard._sender_for` ("names 0 linkedin senders"). Three readers,
    three private re-implementations of "get the id off a sender row", one
    bug in each.

    Both spellings are accepted here rather than one being declared wrong,
    because the data on disk already uses both and a reader that refuses real
    data is not stricter, only broken. Consolidating the three readers onto
    this one is recorded as a follow-up rather than done mid-deployment - it
    is a refactor, and the failure mode in every case was fail-closed.
    """
    rows = (campaign.get("senders") or {}).get(channel) or []
    out = []
    for row in rows:
        if isinstance(row, str):
            row = {"id": row}
        if isinstance(row, dict) and not row.get("id"):
            alias = row.get("provider_account_id")
            if alias not in (None, ""):
                row = dict(row, id=alias)
        if not isinstance(row, dict) or not row.get("id"):
            continue
        out.append({
            "id": str(row["id"]),
            "enabled": row.get("enabled", True) is not False,
            "daily_limit": int(row.get("daily_limit") or DEFAULT_DAILY_LIMIT),
            "external_id": row.get("external_id") or row.get("account_id"),
        })
    return sorted(out, key=lambda a: a["id"])


def enabled(campaign, channel):
    return [a for a in accounts(campaign, channel) if a["enabled"]]


def _slot(key, count):
    """A stable index for a key. sha1 of the key, not Python's salted hash."""
    digest = hashlib.sha1(str(key).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % count


def assign(campaign, channel, contact_key, used=None):
    """The account this contact sends from. Same answer every time.

    `used` is a {account_id: count} of what today has already spent, so an
    account at its limit is passed over. Passing over is still deterministic:
    the candidates are walked from the contact's own slot, in order, so two
    runs with the same usage make the same choice.
    """
    candidates = enabled(campaign, channel)
    if not candidates:
        raise NoSenderAvailable(
            f"no enabled {channel} sender is configured for campaign "
            f"{campaign.get('campaign_id')}")
    used = used or {}
    start = _slot(contact_key, len(candidates))
    for offset in range(len(candidates)):
        account = candidates[(start + offset) % len(candidates)]
        if used.get(account["id"], 0) < account["daily_limit"]:
            return account
    raise NoSenderAvailable(
        f"every {channel} sender is at its daily limit "
        f"({sum(a['daily_limit'] for a in candidates)} total)")


def assign_all(campaign, items):
    """Assign every prepared step, respecting each account's daily allowance.

    Items are walked in a sorted order rather than the order they arrived, so a
    rerun that collects the same work assigns it the same way even if the queue
    was read in a different sequence.
    """
    used = {}
    assigned, refused = [], []
    ordered = sorted(items, key=lambda i: (i.get("channel") or "",
                                           i.get("push_id") or ""))
    for item in ordered:
        channel = item.get("channel")
        contact_key = item.get("contact_key")
        try:
            account = assign(campaign, channel, contact_key, used)
        except NoSenderAvailable as e:
            refused.append({"push_id": item.get("push_id"), "channel": channel,
                            "why": str(e)})
            continue
        used[account["id"]] = used.get(account["id"], 0) + 1
        assigned.append({"push_id": item.get("push_id"), "channel": channel,
                         "contact_key": contact_key, "account": account["id"],
                         "external_id": account.get("external_id")})
    by_channel = {}
    for row in assigned:
        by_channel.setdefault(row["channel"], set()).add(row["account"])
    return {"assigned": assigned, "refused": refused, "used": used,
            "by_channel": {k: sorted(v) for k, v in by_channel.items()}}


def capacity(campaign, channel):
    return sum(a["daily_limit"] for a in enabled(campaign, channel))


def check_mapping(campaign, channels=None):
    """Is the sender configuration usable? Returns (ok, detail) for the
    launch checklist."""
    channels = channels or [c for c in CHANNELS
                            if (campaign.get("senders") or {}).get(c)]
    if not channels:
        return False, "no sender accounts are configured on this campaign"
    problems, notes = [], []
    for channel in channels:
        all_accounts = accounts(campaign, channel)
        live = enabled(campaign, channel)
        if not all_accounts:
            problems.append(f"{channel}: no account configured")
            continue
        if not live:
            problems.append(f"{channel}: every account is disabled")
            continue
        volume = (campaign.get("daily_volume") or {}).get(channel) or 0
        room = capacity(campaign, channel)
        if volume > room:
            problems.append(f"{channel}: daily volume {volume} exceeds the "
                            f"{room} the enabled accounts allow")
        notes.append(f"{channel}: {len(live)} account(s), capacity {room}/day")
    if problems:
        return False, "; ".join(problems)
    return True, "; ".join(notes)
