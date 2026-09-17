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
#
# WHICH OF THE TWO IS THE DAILY ALLOWANCE. Measured against
# `/li_account/GetAll`, 41 seats, 2026-09-17. `accountLimits` carries twelve
# numbers, in six `<action>Limit` / `<action>Max` pairs:
#
#   connectioRequestLimit  distinct over 41 seats: 0,5,10,15,17,18,19,22,23,25,40
#   connectioRequestMax    distinct over 41 seats: 40
#
# and the same shape holds for messages, InMail, profile views, follows and
# post likes: the `...Limit` member varies per seat, the `...Max` member is 40
# on every row - including the eight seats whose credential is dead and which
# can send nothing at all. A number identical across every seat in the estate,
# dead ones included, is a plan ceiling, not a seat's allowance.
#
# So `...Limit` is THE CONFIGURED DAILY LIMIT and `...Max` is the ceiling it
# may be configured up to. `<action>Limit <= <action>Max` on all 41 rows, with
# no exceptions.
#
# NEITHER IS A REMAINING-TODAY COUNTER, and the provider exposes none. The
# seat row has fifteen keys and `accountLimits` twelve numbers; not one of the
# twenty-seven is a used-today or left-today figure. `connectioRequestLimit`
# was read as "remaining" here until 2026-09-17, on nothing but its name: it
# showed byte-identical values across all 32 rostered seats between 2026-09-13
# and 2026-09-17 while the cooldown flags moved on four seats over the same
# window, which is what a setting looks like beside something that is
# genuinely volatile. Remaining today is UNKNOWN and is reported as UNKNOWN.
CONNECTION_LIMIT = "connectioRequestLimit"     # configured requests/day
CONNECTION_MAX = "connectioRequestMax"         # plan ceiling, 40 everywhere
MESSAGE_LIMIT = "messageLimit"                 # configured messages/day

# How much of today's allowance is left. The provider does not say, so this is
# what is reported in the place a number would otherwise sit. A string rather
# than `None` deliberately: `None` survives `int(x or 0)` as a zero and
# survives `sum(...)` as nothing, and both of those read as a measured answer.
# A string cannot be summed by accident - it raises. Same idiom as
# `ASSIGNMENT_UNKNOWN` above and `configdiff.UNVERIFIABLE`.
REMAINING_UNKNOWN = "unknown"

# Seats a human has attested belong to this client. HeyReach exposes no tenant,
# client, owner or team field on an account - confirmed across all 15 keys - so
# the attestation IS the field, and it is recorded as exactly that.
#
# Ownership therefore cannot be re-derived and must not be inferred from a
# campaign name. `approved` below is a caller's argument for that reason.
LI_PROVIDER = "heyreach"


def li_seat_state(row):
    """Everything the provider says about one seat.

    `connection_limit` is the seat's CONFIGURED requests/day and
    `connection_max` the plan ceiling it sits under - see the block above the
    constants for how that was established. There is no remaining-today member
    here because the provider publishes no such number; a reader that wants
    one gets `REMAINING_UNKNOWN` from the report rather than a field on
    canonical state that would always hold the same constant.
    """
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
    # CONFIGURED, not remaining. The provider exposes no remaining-today
    # figure, so no reason string here may promise one to an operator.
    configured = state.get("connection_limit")
    if configured == 0:
        return DEGRADED, ("the configured connection-request limit is 0, so "
                          "this seat cannot open a connection cadence")
    if configured is None:
        return DEGRADED, ("no configured connection limit is known, so nothing "
                          "may be planned")
    return READY, (f"auth valid, active, not cooling down, {configured} "
                   f"connection requests/day configured")


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
            # THE CONFIGURED LIMIT, not the plan ceiling. `CONNECTION_MAX` is
            # 40 on all 41 seats and stood here until 2026-09-17, which made
            # every row read 40 - including `li-139699`, configured at 0 and
            # unable to send a connection request at all, and `li-201959`,
            # configured at 15. `senderidentity.capacity` sums this field, so
            # the roster reported 1,280 requests/day for 32 seats against a
            # configured total of 1,014: a planner over-planned the estate by
            # 26%. The ceiling is still kept, under `provider_state`.
            daily_limit=(row.get("accountLimits") or {}).get(CONNECTION_LIMIT),
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


# --------------------------------------------- the roster against the provider
#
# WHY THIS EXISTS. `build_linkedin` drops an unattested seat silently, which is
# the right refusal and the wrong record: a seat nobody vetted comes out
# indistinguishable from a seat nobody ever saw. On 2026-09-17 provider seat
# `174810` was healthy, credential-valid, sitting in eight of the client's live
# campaigns, and absent from the canonical roster - and nothing anywhere said
# whether that was a decision or an oversight.
#
# It is not dangerous: `executionguard` refuses any seat the canonical roster
# does not name, so the gap fails closed. It is unaccountable, which is a
# different defect and the one this repairs. The gap is now reported, with the
# eligibility of each missing seat stated in the provider's own fields, so an
# operator can see what they are choosing not to use.
#
# NOTHING HERE ATTESTS A SEAT. Ownership on HeyReach is the operator's written
# attestation and nothing else - the provider has no owner, tenant, client or
# team field on a seat - so a module that added `174810` to the roster because
# it looked healthy would be deciding whose LinkedIn profile speaks to a
# stranger. `usable` is False on every seat this function returns, including
# the healthy one, and the write-back path below adds no rows at all.


def seat_eligibility(row):
    """`(eligible, why)` for one provider seat, in the provider's own fields.

    Eligible here means only "the provider would let this seat send". It is
    not permission: see `attestation_gap`.
    """
    health = li_health_of(row)
    if health == senderidentity.HEALTH_BLOCKED:
        return False, ("authIsValid is not true: the credential is dead, so "
                       "the seat would accept an assignment and deliver "
                       "nothing")
    if health == senderidentity.HEALTH_PAUSED:
        return False, "isActive is not true: the seat is switched off"
    return True, "isActive and authIsValid are both true"


def attestation_gap(rows, rostered):
    """Provider seats the canonical roster does not name, and why each one is
    or is not eligible.

    Sorted on the id so two reads of an unchanged estate produce the same
    report and a diff between them means something.
    """
    known = {str(a.get("provider_account_id")) for a in rostered}
    out = []
    for row in rows:
        ident = row.get("id")
        if ident in (None, "") or str(ident) in known:
            continue
        eligible, why = seat_eligibility(row)
        limits = row.get("accountLimits") or {}
        if eligible:
            # The finding. Healthy, in the client's live campaigns, and
            # nobody has written down a decision either way.
            unusable = ("no operator has attested this seat, so it is neither "
                        "usable nor recorded as deliberately excluded. "
                        "Attesting a seat is a decision about whose LinkedIn "
                        "profile speaks to a stranger and cannot be derived "
                        "from provider truth")
        else:
            unusable = f"not attested, and not eligible either: {why}"
        out.append({
            "provider_account_id": str(ident),
            "health": li_health_of(row),
            "provider_eligible": eligible,
            "provider_eligibility": why,
            "active_campaigns": row.get("activeCampaigns"),
            "connection_limit": limits.get(CONNECTION_LIMIT),
            "attested": False,
            # Never True. Attestation is the only thing that makes a seat
            # usable and this module does not perform it.
            "usable": False,
            "why_not_usable": unusable,
        })
    return sorted(out, key=lambda s: s["provider_account_id"])


# The stored fields that are the provider's to say and ours only to copy. A
# drift in any of them means the roster is answering a capacity question from a
# stale read.
PROVIDER_OWNED = ("auth_is_valid", "is_active", "active_campaigns",
                  "connection_limit", "connection_max", "message_limit")


def refresh_linkedin_state(rostered, rows):
    """Reapply provider truth to the seats a human already attested. Pure.

    Returns `(refreshed, drift)`. Only the provider's own fields move:
    `sender_id`, `attested`, `account_id`, `workspace` and `created_at` are
    carried through untouched, because none of them is the provider's to say.

    ADDS NOTHING. A rostered seat with no provider row is returned exactly as
    it was and reported under `missing_at_provider`; a provider seat with no
    rostered row is not built here at any time. Refreshing state and attesting
    a seat are different acts and this performs only the first.
    """
    by_id = {str(r.get("id")): r for r in rows
             if r.get("id") not in (None, "")}
    refreshed, drift = [], []
    for account in rostered:
        row = by_id.get(str(account.get("provider_account_id")))
        if row is None:
            refreshed.append(account)
            continue
        state = li_seat_state(row)
        limits = row.get("accountLimits") or {}
        configured = limits.get(CONNECTION_LIMIT)
        updated = dict(
            account,
            active=bool(row.get("isActive")),
            daily_limit=None if configured is None else int(configured),
            health=li_health_of(row),
            provider_state=state,
        )
        stored_state = account.get("provider_state") or {}
        moved = [(f, stored_state.get(f), state.get(f)) for f in PROVIDER_OWNED
                 if stored_state.get(f) != state.get(f)]
        moved += [(f, account.get(f), updated.get(f))
                  for f in ("daily_limit", "health", "active")
                  if account.get(f) != updated.get(f)]
        for field, was, now in moved:
            drift.append({
                "account_id": account.get("account_id"),
                "field": field,
                "stored": was,
                "provider": now,
                "stored_at": stored_state.get("read_at"),
            })
        refreshed.append(updated)
    return refreshed, drift


def reconcile_linkedin(workspace, rows=None, stored=None, live=False,
                       timeout=None):
    """The canonical roster measured against provider truth.

    Dry by default like everything else that can write. `live` writes back the
    refreshed rows for the seats already in the roster and nothing else - the
    attestation gap is reported on every run and closed on none of them.
    """
    if rows is None:
        rows, _ = heyreach.all_li_accounts()
    if stored is None:
        stored = [a for a in senderidentity.linkedin_accounts(workspace)
                  if a.get("provider") == LI_PROVIDER]
    refreshed, drift = refresh_linkedin_state(stored, rows)
    at_provider = {str(r.get("id")) for r in rows}
    missing = sorted(a["account_id"] for a in stored
                     if str(a.get("provider_account_id")) not in at_provider)
    gap = attestation_gap(rows, stored)
    report = {
        "workspace": workspace,
        "seats_at_provider": len(rows),
        "seats_in_roster": len(stored),
        # The two directions of disagreement. They are not the same finding:
        # a roster seat the provider has lost is a phantom, and a provider
        # seat the roster has never named is an unrecorded decision.
        "missing_at_provider": missing,
        "unrostered_seats": gap,
        "unrostered_but_eligible": [s["provider_account_id"] for s in gap
                                    if s["provider_eligible"]],
        "drift": drift,
        "drifted_accounts": sorted({d["account_id"] for d in drift}),
        # Configured, summed over the refreshed rows. The ceiling is reported
        # beside it and is never the capacity.
        "connection_capacity_per_day": sum(
            int(a.get("daily_limit") or 0) for a in refreshed),
        "connection_plan_ceiling_per_day": sum(
            int((a.get("provider_state") or {}).get("connection_max") or 0)
            for a in refreshed),
        "connection_remaining_today": REMAINING_UNKNOWN,
        "seats_with_no_configured_limit": sorted(
            a["account_id"] for a in refreshed if a.get("daily_limit") is None),
        "live": bool(live),
    }
    if live:
        with senderidentity.transaction(timeout) as current:
            by_key = {a["account_id"]: a for a in refreshed}
            for i, row in enumerate(current):
                if (row.get("kind") == senderidentity.LINKEDIN_ACCOUNT
                        and row.get("workspace") == workspace
                        and row.get("provider") == LI_PROVIDER
                        and row.get("account_id") in by_key):
                    current[i] = by_key[row["account_id"]]
        report["refreshed"] = len(refreshed)
    return report


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
        # What the seats are CONFIGURED to send in a day. This summed the
        # ceiling until 2026-09-17 and so could only ever report 40 x seats.
        "connection_capacity_per_day": sum(
            int((a.get("provider_state") or {}).get("connection_limit") or 0)
            for a in accounts if li_readiness(a)[0] == READY),
        # The ceiling, kept and named as one so the two cannot be confused
        # again. It is what the plan would allow if every seat were raised to
        # it, which is not a thing this repo may do - PRODUCTION-SCALE-POLICY
        # is that a sender estate is never made to carry more by raising a
        # limit - so it is a bound, never a capacity.
        "connection_plan_ceiling_per_day": sum(
            int((a.get("provider_state") or {}).get("connection_max") or 0)
            for a in accounts if li_readiness(a)[0] == READY),
        # NOT A NUMBER, and never was. See `REMAINING_UNKNOWN`.
        "connection_remaining_today": REMAINING_UNKNOWN,
        "proposed_canary_seat": (seat or {}).get("provider_account_id"),
        "live": bool(live),
    }
    # Every seat the attestation list left out, and why. `build_linkedin`
    # dropped them in silence, which made an unvetted healthy seat look
    # exactly like a seat that does not exist.
    gap = attestation_gap(rows, accounts)
    report["unrostered_seats"] = gap
    report["unrostered_but_eligible"] = [s["provider_account_id"] for s in gap
                                         if s["provider_eligible"]]
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
    p.add_argument("--reconcile-linkedin", action="store_true",
                   help="measure the canonical LinkedIn roster against "
                        "provider truth: which provider seats it does not "
                        "name, which stored fields have drifted. Reports the "
                        "attestation gap; never closes it")
    a = p.parse_args(argv)
    if a.reconcile_linkedin:
        from .providers import load_env
        load_env()
        print(json.dumps(reconcile_linkedin(a.workspace, live=a.live),
                         indent=2, sort_keys=True))
        return 0
    print(json.dumps(run(a.workspace, live=a.live,
                         expect_workspace=a.expect_workspace),
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
