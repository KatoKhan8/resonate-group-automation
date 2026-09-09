#!/usr/bin/env python3
"""Rebuild the canonical email sender inventory from provider truth.

WHY. `work/senders.jsonl` held 32 EmailBison inboxes on the reserved
`productive.test` TLD with `provider_account_id` `bison-1..64`. Every one was
fixture. The real Productive workspace has 225 connected inboxes across 86
domains, and the two sets share no domain and no id, so sender selection could
only ever have addressed an account that does not exist. It failed closed only
because the canary campaign has no senders at all.

WHAT IT REFUSES TO DO.

  - **Invent an owner.** The provider knows nothing about which human sends
    from an inbox, so `sender_id` is None on every rebuilt row and a caller
    that needs one fails closed rather than addressing the wrong colleague.
    Assigning 225 inboxes to invented people would be worse than leaving them
    unassigned. PRODUCT-GAPS 27i is the same gap seen from the other end.
  - **Flatten provider state.** The whole provider row that matters is kept
    under `provider_state`, verbatim: status, type, warmup, tags and the
    lifetime counters. Readiness is then DERIVED from that by `readiness()`
    rather than stored, so there is one source of truth and a screen cannot
    disagree with a scheduler about whether an inbox is usable.
  - **Guess a limit.** `daily_limit` comes from the provider or stays None.
    `senderidentity`'s docstring is explicit that an invented sending limit is
    a number that looks like a control and is not one.
  - **Touch anything else.** Only `email_account` rows for this workspace and
    this provider are replaced. Humans, LinkedIn accounts, pairings, teams and
    every other workspace are left exactly as they were.

HEALTH IS NOT READINESS. `senderidentity.HEALTH` has five words and none of
them means "bouncing too much". Rather than add a sixth and end up with two
vocabularies, health carries what it can say honestly - connected, warming,
blocked - and bounce risk lives in `provider_state` where `readiness()` reads
it. A degraded inbox is a derived judgement about stored facts, not a stored
judgement.
"""
import argparse
import json

from . import senderidentity, store
from .providers import bison, heyreach

PROVIDER = "emailbison"

# A bounce rate above this is a real deliverability signal rather than noise.
# Lifetime counters, so it is a long-run rate and not a bad afternoon.
BOUNCE_DEGRADED = 0.02
# Below this many sends, a rate is not yet a rate.
BOUNCE_MIN_SENDS = 50

READY = "ready"
DEGRADED = "degraded"
NOT_READY = "not_ready"

# Whether a sender is already carrying campaigns. Derived, and `None` where the
# provider does not say - `/sender-emails` carries no campaign membership on a
# row, so an email inbox's assignment is genuinely unknown rather than empty.
# Guessing "available" for an inbox that might be in five campaigns is how an
# allocator double-books a mailbox.
CAMPAIGN_ASSIGNED = "campaign_assigned"
AVAILABLE = "available"
ASSIGNMENT_UNKNOWN = "unknown"


def assignment_of(account):
    """`campaign_assigned` / `available` / `unknown`, from provider state."""
    count = (account.get("provider_state") or {}).get("active_campaigns")
    if count is None:
        return ASSIGNMENT_UNKNOWN
    return CAMPAIGN_ASSIGNED if int(count) > 0 else AVAILABLE


def account_id_for(row):
    """`eb-<provider id>`. Derived, so a re-read produces the same row."""
    ident = row.get("id")
    return f"eb-{ident}" if ident not in (None, "") else None


def _rate(row):
    sent = int(row.get("emails_sent_count") or 0)
    bounced = int(row.get("bounced_count") or 0)
    if sent < BOUNCE_MIN_SENDS:
        return None                       # not enough to judge, so no judgement
    return bounced / sent if sent else None


def provider_state(row):
    """Everything about this inbox the provider actually told us."""
    return {
        "status": row.get("status"),
        "type": row.get("type"),
        "warmup_enabled": row.get("warmup_enabled"),
        "daily_limit": row.get("daily_limit"),
        "tags": [t if not isinstance(t, dict) else t.get("name")
                 for t in (row.get("tags") or [])],
        "emails_sent_count": row.get("emails_sent_count"),
        "bounced_count": row.get("bounced_count"),
        "unique_replied_count": row.get("unique_replied_count"),
        "unsubscribed_count": row.get("unsubscribed_count"),
        "bounce_rate": _rate(row),
        "read_at": store.now(),
    }


def health_of(row):
    """What the five-word vocabulary can say about this inbox truthfully."""
    status = str(row.get("status") or "").strip().lower()
    if status != "connected":
        # Disconnected, pending, errored: whatever the word, it cannot send.
        return senderidentity.HEALTH_BLOCKED
    if row.get("warmup_enabled") and not int(row.get("emails_sent_count") or 0):
        # Warmup on and nothing sent yet is the one case that is genuinely
        # "warming". Warmup on with 800 sends behind it is a provider setting,
        # not a lifecycle stage, and calling it warming would mark 224 of 225
        # inboxes unusable on the strength of a checkbox.
        return senderidentity.HEALTH_WARMING
    return senderidentity.HEALTH_OK


def readiness(account):
    """READY / DEGRADED / NOT_READY, derived from stored provider facts.

    Derived rather than stored so that capacity planning and any screen read
    the same function. Returns `(state, reason)`.
    """
    state = account.get("provider_state") or {}
    if not account.get("active"):
        return NOT_READY, "the account is not active in canonical state"
    if account.get("health") == senderidentity.HEALTH_BLOCKED:
        return NOT_READY, f"provider status is {state.get('status')!r}"
    if account.get("health") == senderidentity.HEALTH_WARMING:
        return DEGRADED, "warmup is on and nothing has been sent from it yet"
    rate = state.get("bounce_rate")
    if rate is not None and rate >= BOUNCE_DEGRADED:
        return DEGRADED, (f"lifetime bounce rate {rate:.1%} is at or above "
                          f"{BOUNCE_DEGRADED:.0%}")
    if account.get("daily_limit") is None:
        return DEGRADED, "no daily limit is known, so nothing may be planned"
    return READY, "connected, limit known, bounce rate within tolerance"


def build(workspace, rows):
    """Provider rows -> canonical `email_account` rows. Pure."""
    out = []
    for row in rows:
        account_id = account_id_for(row)
        address = str(row.get("email") or "").strip().lower()
        if not account_id or "@" not in address:
            continue
        account = senderidentity.new_email_account(
            workspace, account_id,
            # No owner. The provider does not know one and this module will
            # not invent one.
            sender_id=None,
            email_address=address,
            provider=PROVIDER,
            provider_account_id=str(row.get("id")),
            active=str(row.get("status") or "").lower() == "connected",
            daily_limit=row.get("daily_limit"),
            health=health_of(row),
        )
        account["provider_state"] = provider_state(row)
        out.append(account)
    return out


# ------------------------------------------------------------- LinkedIn seats
#
# The provider's own spelling, typo included: `connectioRequestLimit` /
# `connectioRequestMax`. Not corrected here - a key read under a tidier name
# than the wire uses is a key that reads None the day somebody trusts it.
CONNECTION_LIMIT = "connectioRequestLimit"
CONNECTION_MAX = "connectioRequestMax"
MESSAGE_LIMIT = "messageLimit"

# Seats a human has attested belong to this client. HeyReach exposes no tenant,
# client, owner or team field on an account - confirmed across all 15 keys - so
# the attestation IS the field, and it is recorded as exactly that.
#
# Ownership therefore cannot be re-derived and must not be inferred from a
# campaign name. `approved` below is a caller's argument for that reason.
LI_PROVIDER = "heyreach"


def li_seat_state(row):
    """Everything the provider says about one seat."""
    limits = row.get("accountLimits") if isinstance(row.get("accountLimits"),
                                                    dict) else {}
    return {
        "auth_is_valid": row.get("authIsValid"),
        "is_active": row.get("isActive"),
        "active_campaigns": row.get("activeCampaigns"),
        "connection_limit": limits.get(CONNECTION_LIMIT),
        "connection_max": limits.get(CONNECTION_MAX),
        "message_limit": limits.get(MESSAGE_LIMIT),
        "cooldowns": {k: row.get(k) for k in
                      ("connectionRequestCooldown", "connectionNoteCooldown",
                       "inMailCooldown", "searchCooldown")},
        "read_at": store.now(),
    }


def li_health_of(row):
    """The five-word vocabulary, over the two booleans that decide sending."""
    if row.get("authIsValid") is not True:
        # The credential is dead. `isActive: true` makes it worse, not better:
        # the seat is assigned to live campaigns and delivering nothing.
        return senderidentity.HEALTH_BLOCKED
    if row.get("isActive") is not True:
        return senderidentity.HEALTH_PAUSED
    return senderidentity.HEALTH_OK


def li_readiness(account):
    """READY / DEGRADED / NOT_READY for a seat. Derived, like the email side."""
    state = account.get("provider_state") or {}
    if not account.get("active"):
        return NOT_READY, "the seat is not active in canonical state"
    if account.get("health") == senderidentity.HEALTH_BLOCKED:
        return NOT_READY, "authIsValid is not true: the credential is dead"
    if account.get("health") == senderidentity.HEALTH_PAUSED:
        return DEGRADED, "isActive is not true: the seat is switched off"
    if any(state.get("cooldowns", {}).values()):
        on = sorted(k for k, v in state["cooldowns"].items() if v)
        return DEGRADED, f"cooling down: {', '.join(on)}"
    remaining = state.get("connection_limit")
    if remaining == 0:
        return DEGRADED, "no connection requests left against today's limit"
    if remaining is None:
        return DEGRADED, "no connection limit is known, so nothing may be planned"
    return READY, "auth valid, active, not cooling down, limit remaining"


def build_linkedin(workspace, rows, approved=()):
    """Provider seats -> canonical `linkedin_account` rows. Pure.

    `approved` is the operator's attested id list. A seat outside it is simply
    not built: HeyReach has no ownership field, so including an unattested seat
    would put a canary on a profile nobody said we may use.
    """
    allowed = {str(a) for a in approved} if approved else None
    out = []
    for row in rows:
        ident = row.get("id")
        if ident in (None, ""):
            continue
        if allowed is not None and str(ident) not in allowed:
            continue
        profile = str(row.get("profileUrl") or "").strip()
        account = senderidentity.new_linkedin_account(
            workspace, f"li-{ident}",
            sender_id=None,          # HeyReach knows no owner. See LI_PROVIDER.
            profile_url=profile or f"https://www.linkedin.com/in/unknown-{ident}",
            provider=LI_PROVIDER,
            provider_account_id=str(ident),
            active=bool(row.get("isActive")),
            daily_limit=(row.get("accountLimits") or {}).get(CONNECTION_MAX),
            health=li_health_of(row),
        )
        account["provider_state"] = li_seat_state(row)
        account["attested"] = allowed is not None
        out.append(account)
    return out


def replace_linkedin(workspace, accounts, timeout=None):
    with senderidentity.transaction(timeout) as rows:
        keep = [r for r in rows
                if not (r.get("kind") == senderidentity.LINKEDIN_ACCOUNT
                        and r.get("workspace") == workspace
                        and r.get("provider") == LI_PROVIDER)]
        removed = len(rows) - len(keep)
        rows[:] = keep + accounts
    return removed


def canary_seat(accounts):
    """The safest seat for a one-person canary. Deterministic.

    Ordered on (active_campaigns, id): fewest campaigns first because every
    additional campaign is another sequence this system cannot see and could
    collide with, and the id as a total tie-break so the choice is reproducible
    rather than a judgement. Not ordered on a limit - the limits move between
    reads, and a tie-break on a moving field is a judgement wearing a formula.

    READY only. A degraded seat is not a canary seat.
    """
    ready = [a for a in accounts if li_readiness(a)[0] == READY]
    if not ready:
        return None
    return sorted(ready, key=lambda a: (
        int((a.get("provider_state") or {}).get("active_campaigns") or 0),
        int(a.get("provider_account_id") or 0)))[0]


def run_linkedin(workspace, approved=(), live=False):
    rows, total = heyreach.all_li_accounts()
    accounts = build_linkedin(workspace, rows, approved=approved)
    counts = {}
    for account in accounts:
        state = li_readiness(account)[0]
        counts[state] = counts.get(state, 0) + 1
    seat = canary_seat(accounts)
    assign = {}
    for account in accounts:
        state = assignment_of(account)
        assign[state] = assign.get(state, 0) + 1
    report = {
        "by_assignment": assign,
        "workspace": workspace,
        "provider_total": total,
        "seats_read": len(rows),
        "attested_approved": len(approved),
        "built": len(accounts),
        "by_readiness": counts,
        "reasons": {a["account_id"]: li_readiness(a)[1] for a in accounts
                    if li_readiness(a)[0] != READY},
        "connection_capacity_per_day": sum(
            int((a.get("provider_state") or {}).get("connection_max") or 0)
            for a in accounts if li_readiness(a)[0] == READY),
        "connection_remaining_today": sum(
            int((a.get("provider_state") or {}).get("connection_limit") or 0)
            for a in accounts if li_readiness(a)[0] == READY),
        "proposed_canary_seat": (seat or {}).get("provider_account_id"),
        "live": bool(live),
    }
    if live:
        report["replaced"] = replace_linkedin(workspace, accounts)
    return report


def replace(workspace, accounts, timeout=None):
    """Swap in the rebuilt inventory. Only this workspace's email accounts."""
    with senderidentity.transaction(timeout) as rows:
        keep = [r for r in rows
                if not (r.get("kind") == senderidentity.EMAIL_ACCOUNT
                        and r.get("workspace") == workspace
                        and r.get("provider") == PROVIDER)]
        removed = len(rows) - len(keep)
        rows[:] = keep + accounts
    return removed


def summarise(accounts):
    counts, reasons = {}, {}
    for account in accounts:
        state, why = readiness(account)
        counts[state] = counts.get(state, 0) + 1
        reasons.setdefault(state, {})
        reasons[state][why] = reasons[state].get(why, 0) + 1
    capacity = sum(int(a["daily_limit"] or 0) for a in accounts
                   if readiness(a)[0] == READY)
    assign = {}
    for account in accounts:
        state = assignment_of(account)
        assign[state] = assign.get(state, 0) + 1
    return {
        "accounts": len(accounts),
        "by_readiness": counts,
        "by_assignment": assign,
        "reasons": reasons,
        "health": {h: sum(1 for a in accounts if a["health"] == h)
                   for h in senderidentity.HEALTH
                   if any(a["health"] == h for a in accounts)},
        "ready_daily_capacity": capacity,
        "unassigned_owner": sum(1 for a in accounts if not a.get("sender_id")),
    }


def run(workspace, live=False, expect_workspace=None):
    """Read the provider, build, and when `live`, write. Dry by default.

    The pin comes from `BISON_WORKSPACE_ID` when the caller does not supply
    one, which is the same source and the same deliberate default-to-unpinned
    that `replywatch.expected_workspace` uses. Unpinned still records the binding
    it found, so an inventory is never attributed to a workspace nobody
    checked.
    """
    from . import replywatch
    from .providers import load_env
    if expect_workspace is None:
        # The pin lives in `config/.env` and nothing loads that at startup.
        # Loaded here rather than inside `expected_workspace`, which is a pure
        # env reader on purpose: loading it there sets the pin for the whole
        # process and every later caller inherits it.
        load_env()
        expect_workspace = replywatch.expected_workspace("emailbison")
    rows, meta = bison.sender_emails(expect_workspace=expect_workspace)
    bound = bison.bound_workspace()
    accounts = build(workspace, rows)
    report = {
        "workspace": workspace,
        "credential_bound_to": bound,
        "pinned_to": expect_workspace,
        "tenancy": bison.scope()["kind"],
        "provider_total": meta.get("total"),
        "provider_per_page": meta.get("per_page"),
        "provider_pages": meta.get("last_page"),
        "rows_read": len(rows),
        "live": bool(live),
    }
    report.update(summarise(accounts))
    if live:
        report["replaced"] = replace(workspace, accounts)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.senderinventory",
                                description=__doc__)
    p.add_argument("--workspace", default="productive")
    p.add_argument("--live", action="store_true",
                   help="write the rebuilt inventory; dry run otherwise")
    p.add_argument("--expect-workspace",
                   help="refuse unless the credential is bound to this "
                        "provider workspace id (defaults to BISON_WORKSPACE_ID)")
    a = p.parse_args(argv)
    print(json.dumps(run(a.workspace, live=a.live,
                         expect_workspace=a.expect_workspace),
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
