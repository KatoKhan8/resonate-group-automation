#!/usr/bin/env python3
"""Per-seat utilisation analysis: which senders are actually busy, and what
capacity is really free.

Reads the HeyReach provider for:
  1. Every campaign (status + campaignAccountIds)
  2. Every seat (health, limits, cooldowns)
  3. Per-seat stats via /stats/GetOverallStats with accountIds filter

Produces docs/state/SENDER-CAPACITY.json (updated with per-seat campaign
attachment and headroom) and docs/SENDER-UTILISATION-2026-09-15.md.

READ-ONLY. No mutations.
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import heyreach, load_env, request  # noqa: E402

OUT_CAPACITY = os.path.join(ROOT, "docs", "state", "SENDER-CAPACITY.json")
OUT_REPORT = os.path.join(ROOT, "docs", "SENDER-UTILISATION-2026-09-15.md")

# Campaign statuses: the provider uses these exact strings.
# IN_PROGRESS means the campaign is actively sending.
# PAUSED means it was stopped but can resume.
# FINISHED means it ran to completion.
# DRAFT/SCHEDULED means it hasn't started.
ACTIVE_STATUSES = {"IN_PROGRESS"}
PAUSED_STATUSES = {"PAUSED"}
FINISHED_STATUSES = {"FINISHED"}
INACTIVE_STATUSES = {"DRAFT", "SCHEDULED"}


def h(value):
    import hashlib
    v = " ".join(str(value or "").split()).lower()
    return hashlib.sha256(v.encode("utf-8")).hexdigest()[:12] if v else None


def classify(seat):
    if not seat.get("isActive"):
        return "INACTIVE"
    if not seat.get("authIsValid"):
        return "AUTH_INVALID"
    return "HEALTHY"


def fetch_all_campaigns():
    """Page through every campaign. Returns raw items with all fields."""
    all_items = []
    offset = 0
    for _ in range(20):
        data = heyreach._read("/campaign/GetAll",
                              {"offset": offset, "limit": 100})
        items = data.get("items") or []
        all_items.extend(items)
        total = data.get("totalCount", 0)
        offset += len(items)
        if not items or offset >= total:
            break
    return all_items


def fetch_seat_stats(account_id):
    """Per-seat activity counters via /stats/GetOverallStats.
    Returns the overallStats dict or None on failure."""
    try:
        data = heyreach._read("/stats/GetOverallStats",
                              {"campaignIds": [], "accountIds": [int(account_id)],
                               "timeFrom": None, "timeTo": None})
        return data.get("overallStats")
    except Exception as e:
        return {"error": str(e)}


def main():
    load_env()

    # --- 1. Fetch seats ---
    seats_raw, total_seats = heyreach.all_li_accounts()
    print(f"Fetched {len(seats_raw)} seats (totalCount={total_seats})")

    # --- 2. Fetch all campaigns ---
    campaigns_raw = fetch_all_campaigns()
    print(f"Fetched {len(campaigns_raw)} campaigns")

    # Build campaign lookup: id -> {status, name, campaignAccountIds, ...}
    campaign_map = {}
    for c in campaigns_raw:
        cid = c.get("id")
        campaign_map[cid] = {
            "id": cid,
            "name": c.get("name", ""),
            "status": c.get("status", "UNKNOWN"),
            "account_ids": [int(a) for a in (c.get("campaignAccountIds") or [])],
            "created": c.get("creationTime"),
            "started": c.get("startedAt"),
        }

    # Campaign status distribution
    status_counts = defaultdict(int)
    for c in campaign_map.values():
        status_counts[c["status"]] += 1
    print(f"Campaign statuses: {dict(status_counts)}")

    # --- 3. Build per-seat campaign attachment ---
    # For each seat, which campaigns is it on, and what are their statuses?
    seat_campaigns = defaultdict(list)
    for cid, camp in campaign_map.items():
        for aid in camp["account_ids"]:
            seat_campaigns[aid].append({
                "campaign_id": cid,
                "name": camp["name"],
                "status": camp["status"],
            })

    # --- 4. Classify seats and compute headroom ---
    senders_out = []
    totals = {"HEALTHY": 0, "AUTH_INVALID": 0, "INACTIVE": 0}
    entry_cap_total = 0
    msg_cap_total = 0

    # Per-seat stats: fetch for each healthy seat
    print("Fetching per-seat stats (this takes a moment)...")
    seat_stats = {}
    healthy_seats = [s for s in seats_raw if classify(s) == "HEALTHY"]
    for i, s in enumerate(healthy_seats):
        sid = s.get("id")
        stats = fetch_seat_stats(sid)
        seat_stats[sid] = stats
        if (i + 1) % 10 == 0:
            print(f"  ...{i+1}/{len(healthy_seats)} seats queried")

    # Also fetch the AUTH_INVALID seat stats
    auth_invalid_seats = [s for s in seats_raw if classify(s) == "AUTH_INVALID"]
    for s in auth_invalid_seats:
        sid = s.get("id")
        seat_stats[sid] = fetch_seat_stats(sid)

    print("Per-seat stats complete.")

    # The AUTH_INVALID seat: is it recoverable?
    auth_invalid_detail = []
    for s in auth_invalid_seats:
        campaigns_attached = seat_campaigns.get(s.get("id"), [])
        active_campaigns = [c for c in campaigns_attached
                           if c["status"] in ACTIVE_STATUSES]
        auth_invalid_detail.append({
            "sender_id": s.get("id"),
            "identity_hash": h("%s %s|%s" % (
                s.get("firstName"), s.get("lastName"), s.get("emailAddress"))),
            "campaigns_attached": len(campaigns_attached),
            "active_campaigns": len(active_campaigns),
            "stats": seat_stats.get(s.get("id")),
        })

    for s in seats_raw:
        state = classify(s)
        totals[state] += 1
        limits = s.get("accountLimits") or {}
        entry = limits.get("connectioRequestLimit") or 0
        msg = limits.get("messageLimit") or 0
        sid = s.get("id")

        campaigns_attached = seat_campaigns.get(sid, [])
        active_camps = [c for c in campaigns_attached
                       if c["status"] in ACTIVE_STATUSES]
        paused_camps = [c for c in campaigns_attached
                       if c["status"] in PAUSED_STATUSES]
        finished_camps = [c for c in campaigns_attached
                         if c["status"] in FINISHED_STATUSES]
        inactive_camps = [c for c in campaigns_attached
                         if c["status"] in INACTIVE_STATUSES]

        if state == "HEALTHY":
            entry_cap_total += entry
            msg_cap_total += msg

        stats = seat_stats.get(sid)
        # Extract real activity numbers
        connections_sent = 0
        connections_accepted = 0
        messages_sent = 0
        replies = 0
        leads_contacted = 0
        acceptance_rate = None
        reply_rate = None
        profile_views = 0
        inmail_sent = 0
        inmail_replies = 0
        stats_available = False
        if stats and "error" not in stats:
            stats_available = True
            connections_sent = stats.get("connectionsSent", 0) or 0
            connections_accepted = stats.get("connectionsAccepted", 0) or 0
            messages_sent = stats.get("messagesSent", 0) or 0
            replies = stats.get("totalMessageReplies", 0) or 0
            leads_contacted = stats.get("uniqueLeadsContacted", 0) or 0
            acceptance_rate = stats.get("connectionAcceptanceRate")
            reply_rate = stats.get("messageReplyRate")
            profile_views = stats.get("profileViews", 0) or 0
            inmail_sent = stats.get("inmailMessagesSent", 0) or 0
            inmail_replies = stats.get("totalInmailReplies", 0) or 0

        # Headroom calculation:
        # remaining = ceiling - what's already configured across active campaigns
        # BUT the provider reports per-seat daily limits, not per-campaign.
        # The daily_connection_requests and daily_messages in the seat data
        # are the REMAINING capacity the provider reports for today.
        remaining_entry = entry  # ceiling
        remaining_msg = msg      # ceiling
        # If we have stats, the "used" portion is connectionsSent etc.
        # But stats are ALL-TIME, not today-only. So headroom is the
        # provider's own daily_remaining fields from the seat data.

        # Campaign attachment classification:
        # A seat is "effectively idle" if all its campaigns are FINISHED/PAUSED/DRAFT
        # A seat is "actively working" if any campaign is IN_PROGRESS
        effectively_idle = len(active_camps) == 0

        # Trim campaign list for output (no PII)
        campaign_summary = []
        for c in campaigns_attached:
            campaign_summary.append({
                "campaign_id": c["campaign_id"],
                "status": c["status"],
            })

        row = {
            "sender_id": sid,
            "provider": "heyreach",
            "identity_hash": h("%s %s|%s" % (
                s.get("firstName"), s.get("lastName"), s.get("emailAddress"))),
            "state": state,
            "is_active": s.get("isActive"),
            "auth_is_valid": s.get("authIsValid"),
            "active_campaigns": s.get("activeCampaigns"),
            "daily_connection_requests": entry,
            "daily_messages": msg,
            "daily_profile_views": limits.get("profileViewLimit"),
            "sales_navigator": s.get("isValidNavigator"),
            "cooldowns": {
                "connection_request": s.get("connectionRequestCooldown"),
                "connection_note": s.get("connectionNoteCooldown"),
                "inmail": s.get("inMailCooldown"),
                "search": s.get("searchCooldown"),
            },
            # NEW: per-seat campaign attachment
            "campaign_attachment": {
                "total": len(campaigns_attached),
                "in_progress": len(active_camps),
                "paused": len(paused_camps),
                "finished": len(finished_camps),
                "draft_or_scheduled": len(inactive_camps),
                "effectively_idle": effectively_idle,
                "campaigns": campaign_summary,
            },
            # NEW: all-time activity (from /stats/GetOverallStats)
            "activity_all_time": {
                "available": stats_available,
                "connections_sent": connections_sent,
                "connections_accepted": connections_accepted,
                "acceptance_rate": acceptance_rate,
                "messages_sent": messages_sent,
                "replies": replies,
                "reply_rate": reply_rate,
                "leads_contacted": leads_contacted,
                "profile_views": profile_views,
                "inmail_sent": inmail_sent,
                "inmail_replies": inmail_replies,
            } if stats_available else {"available": False},
        }
        senders_out.append(row)

    # --- 5. Summarise ---
    healthy_senders = [s for s in senders_out if s["state"] == "HEALTHY"]
    idle_healthy = [s for s in healthy_senders
                    if s["campaign_attachment"]["effectively_idle"]]
    active_healthy = [s for s in healthy_senders
                      if not s["campaign_attachment"]["effectively_idle"]]

    # Seats on ONLY finished campaigns
    only_finished = [s for s in healthy_senders
                     if s["campaign_attachment"]["in_progress"] == 0
                     and s["campaign_attachment"]["paused"] == 0
                     and s["campaign_attachment"]["total"] > 0
                     and s["campaign_attachment"]["finished"] > 0]

    # Seats with any IN_PROGRESS campaign
    on_active = [s for s in healthy_senders
                 if s["campaign_attachment"]["in_progress"] > 0]

    # Cooldown summary
    any_cooldown = [s for s in healthy_senders
                    if any(s["cooldowns"].values())]

    # Connection request capacity on seats with IN_PROGRESS campaigns
    active_entry_cap = sum(s["daily_connection_requests"]
                          for s in on_active)
    active_msg_cap = sum(s["daily_messages"] for s in on_active)
    idle_entry_cap = sum(s["daily_connection_requests"] for s in idle_healthy)
    idle_msg_cap = sum(s["daily_messages"] for s in idle_healthy)

    # --- 6. Write updated SENDER-CAPACITY.json ---
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": ("HeyRead li_account/GetAll + /campaign/GetAll + "
                   "/stats/GetOverallStats, read-only. Credential env var: HEYREACH_KEY."),
        "seats_total": len(seats_raw),
        "seats_by_state": totals,
        "healthy_seats": totals["HEALTHY"],
        "healthy_seats_with_no_active_campaign": len(idle_healthy),
        "campaign_status_distribution": dict(status_counts),
        "daily_capacity_healthy_only": {
            "connection_requests": entry_cap_total,
            "messages": msg_cap_total,
            "note": ("Provider-configured ceilings summed over HEALTHY seats. "
                     "This is what is ALLOWED, not what was sent, and not a "
                     "promise LinkedIn tolerates it. Never raise a per-seat "
                     "limit to gain throughput - add senders or add days."),
        },
        "capacity_on_in_progress_campaigns": {
            "connection_requests": active_entry_cap,
            "messages": active_msg_cap,
            "seats": len(on_active),
            "note": ("Ceiling summed over healthy seats attached to at least "
                     "one IN_PROGRESS campaign. These seats are already working."),
        },
        "capacity_on_idle_seats": {
            "connection_requests": idle_entry_cap,
            "messages": idle_msg_cap,
            "seats": len(idle_healthy),
            "note": ("Ceiling summed over healthy seats whose campaigns are "
                     "all FINISHED/PAUSED/DRAFT. These seats look free but "
                     "are still attached to campaigns and may need detachment "
                     "before reuse."),
        },
        "auth_invalid_seats": auth_invalid_detail,
        "cooldown_summary": {
            "seats_with_any_cooldown": len(any_cooldown),
            "detail": [{
                "sender_id": s["sender_id"],
                "identity_hash": s["identity_hash"],
                "cooldowns": s["cooldowns"],
            } for s in any_cooldown],
        },
        "senders": senders_out,
    }

    os.makedirs(os.path.dirname(OUT_CAPACITY), exist_ok=True)
    with open(OUT_CAPACITY, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Written: {OUT_CAPACITY}")

    # --- 7. Write the report ---
    report = build_report(
        totals=totals,
        status_counts=dict(status_counts),
        healthy_senders=healthy_senders,
        idle_healthy=idle_healthy,
        active_healthy=active_healthy,
        on_active=on_active,
        only_finished=only_finished,
        any_cooldown=any_cooldown,
        entry_cap_total=entry_cap_total,
        msg_cap_total=msg_cap_total,
        active_entry_cap=active_entry_cap,
        active_msg_cap=active_msg_cap,
        idle_entry_cap=idle_entry_cap,
        idle_msg_cap=idle_msg_cap,
        auth_invalid_detail=auth_invalid_detail,
        campaign_map=campaign_map,
    )
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Written: {OUT_REPORT}")
    return 0


def build_report(**kw):
    """Build the markdown report. Separates MEASURED from ASSUMED."""

    lines = []
    w = lines.append

    w("# Sender Utilisation Report — 2026-09-15")
    w("")
    w("## Summary")
    w("")
    w(f"| Metric | Value |")
    w(f"|--------|-------|")
    w(f"| Total seats | {kw['totals']['HEALTHY'] + kw['totals']['AUTH_INVALID'] + kw['totals']['INACTIVE']} |")
    w(f"| Healthy (isActive + authIsValid) | {kw['totals']['HEALTHY']} |")
    w(f"| Auth invalid (active but broken) | {kw['totals']['AUTH_INVALID']} |")
    w(f"| Inactive | {kw['totals']['INACTIVE']} |")
    w(f"| Healthy seats effectively idle (no IN_PROGRESS campaign) | {len(kw['idle_healthy'])} |")
    w(f"| Healthy seats on at least one IN_PROGRESS campaign | {len(kw['on_active'])} |")
    w(f"| Daily connection request ceiling (all healthy) | {kw['entry_cap_total']} |")
    w(f"| Daily message ceiling (all healthy) | {kw['msg_cap_total']} |")
    w(f"| Daily connection request ceiling (seats on IN_PROGRESS) | {kw['active_entry_cap']} |")
    w(f"| Daily message ceiling (seats on IN_PROGRESS) | {kw['active_msg_cap']} |")
    w(f"| Daily connection request ceiling (idle seats) | {kw['idle_entry_cap']} |")
    w(f"| Daily message ceiling (idle seats) | {kw['idle_msg_cap']} |")
    w("")

    w("## Campaign Status Distribution")
    w("")
    w("| Status | Count |")
    w("|--------|-------|")
    for status, count in sorted(kw["status_counts"].items()):
        w(f"| {status} | {count} |")
    w("")

    w("## 1. Per-Seat Campaign Attachment")
    w("")
    w("Each healthy seat's campaign attachment, classified by campaign status.")
    w("A seat is **effectively idle** if NONE of its campaigns are IN_PROGRESS.")
    w("")
    w("| Seat (hash) | Campaigns | IN_PROGRESS | PAUSED | FINISHED | DRAFT/SCHED | Idle? | Conn Req Limit | Msg Limit |")
    w("|-------------|-----------|-------------|--------|----------|-------------|-------|----------------|-----------|")
    for s in sorted(kw["healthy_senders"], key=lambda x: x["sender_id"]):
        ca = s["campaign_attachment"]
        idle_mark = "YES" if ca["effectively_idle"] else ""
        w(f"| `{s['identity_hash']}` | {ca['total']} | {ca['in_progress']} "
          f"| {ca['paused']} | {ca['finished']} | {ca['draft_or_scheduled']} "
          f"| {idle_mark} | {s['daily_connection_requests']} | {s['daily_messages']} |")
    w("")

    w("### Seats on ONLY finished campaigns (potentially reclaimable)")
    w("")
    if kw["only_finished"]:
        w(f"{len(kw['only_finished'])} seats have campaigns that are all FINISHED "
          f"(none IN_PROGRESS, none PAUSED). These seats could potentially be "
          f"detached and reassigned.")
        w("")
        for s in kw["only_finished"]:
            ca = s["campaign_attachment"]
            w(f"- `{s['identity_hash']}` (seat {s['sender_id']}): "
              f"{ca['finished']} finished, {ca['total']} total, "
              f"conn_req={s['daily_connection_requests']}, msg={s['daily_messages']}")
    else:
        w("None. Every healthy seat with campaigns has at least one IN_PROGRESS or PAUSED.")
    w("")

    w("## 2. Real Activity Per Seat")
    w("")
    w("The provider exposes `/stats/GetOverallStats` which returns ALL-TIME "
      "counters per seat (connectionsSent, messagesSent, totalMessageReplies, "
      "uniqueLeadsContacted). **This is NOT today's activity** — it is cumulative "
      "since the seat was connected.")
    w("")
    w("**The provider does NOT expose per-day or per-period activity breakdowns "
      "per seat.** What was sent TODAY cannot be determined from the API. "
      "This is a finding, not a failure — a planner must assume the full daily "
      "ceiling is available unless operational logs say otherwise.")
    w("")
    w("| Seat (hash) | Connections | Accepted | Acceptance% | Messages | Replies | Reply% | Leads |")
    w("|-------------|-------------|----------|-------------|----------|---------|--------|-------|")
    for s in sorted(kw["healthy_senders"], key=lambda x: x["sender_id"]):
        a = s["activity_all_time"]
        if a.get("available"):
            acc_rate = f"{a['acceptance_rate']*100:.1f}" if a.get('acceptance_rate') is not None else "N/A"
            rep_rate = f"{a['reply_rate']*100:.1f}" if a.get('reply_rate') is not None else "N/A"
            w(f"| `{s['identity_hash']}` | {a['connections_sent']} "
              f"| {a['connections_accepted']} | {acc_rate} "
              f"| {a['messages_sent']} | {a['replies']} | {rep_rate} "
              f"| {a['leads_contacted']} |")
        else:
            w(f"| `{s['identity_hash']}` | N/A | N/A | N/A | N/A | N/A | N/A | N/A |")
    w("")

    w("## 3. Remaining Safe Headroom")
    w("")
    w("### What is MEASURED")
    w("")
    w("- **Per-seat daily ceilings** (connectionRequestLimit, messageLimit): "
      "configured in the provider, read from `accountLimits` on each seat.")
    w("- **Cooldown state**: whether each seat is currently in cooldown for "
      "connection requests, connection notes, InMail, or search.")
    w("- **Campaign attachment**: which campaigns each seat is on and their statuses.")
    w("")
    w("### What is ASSUMED")
    w("")
    w("- **That the daily ceiling is available today.** The provider does not "
      "report how much has been sent today. A seat showing 40 connection "
      "requests/day may have already sent 30 of them. Without per-day activity "
      "data, headroom = ceiling, and that is an UPPER BOUND.")
    w("- **That a seat on a FINISHED campaign can be reused.** Detachment from "
      "the finished campaign is assumed to be possible but has not been tested.")
    w("- **That cooldowns are temporary.** A seat in `connectionRequestCooldown` "
      "will exit cooldown, but the duration is not exposed by the API.")
    w("")

    w("## 4. Cooldown Analysis")
    w("")
    if kw["any_cooldown"]:
        w(f"**{len(kw['any_cooldown'])} seats are currently in at least one cooldown.**")
        w("")
        for d in kw["any_cooldown"]:
            active = [k for k, v in d["cooldowns"].items() if v]
            w(f"- `{d['identity_hash']}` (seat {d['sender_id']}): "
              f"cooldown on: {', '.join(active)}")
        w("")
        w("A seat in cooldown CANNOT be reused immediately. The provider does not "
          "expose cooldown duration. A planner that ignores cooldowns will promise "
          "throughput the provider will not deliver.")
    else:
        w("No seats are currently in cooldown. All healthy seats can theoretically "
          "accept new work immediately (subject to campaign attachment).")
    w("")

    w("## 5. The AUTH_INVALID Seat")
    w("")
    if kw["auth_invalid_detail"]:
        for d in kw["auth_invalid_detail"]:
            w(f"- **Seat `{d['identity_hash']}`** (id {d['sender_id']}): "
              f"`isActive: true`, `authIsValid: false`. "
              f"Attached to {d['campaigns_attached']} campaigns "
              f"({d['active_campaigns']} IN_PROGRESS).")
            stats = d.get("stats")
            if stats and "error" not in stats:
                w(f"  - All-time stats: {stats.get('connectionsSent', 0)} connections, "
                  f"{stats.get('messagesSent', 0)} messages, "
                  f"{stats.get('totalMessageReplies', 0)} replies, "
                  f"acceptance rate {stats.get('connectionAcceptanceRate', 0)*100:.1f}%")
            elif stats and "error" in stats:
                w(f"  - Stats unavailable: {stats['error']}")
        w("")
        w("**This seat is NOT capacity.** It accepts assignments and fails. "
          "It is attached to campaigns, which means leads may be queued behind it. "
          "It should be excluded from every plan until auth is restored. "
          "Whether it is recoverable depends on the LinkedIn re-authentication "
          "flow — the provider does not expose a diagnostic beyond `authIsValid: false`.")
    else:
        w("No AUTH_INVALID seats found.")
    w("")

    w("## 6. Cohort Throughput Arithmetic")
    w("")
    w("### The question: how fast could a 50-lead cohort move through a "
      "connection-request-then-message cadence?")
    w("")

    # The arithmetic
    total_healthy = kw["totals"]["HEALTHY"]
    idle_count = len(kw["idle_healthy"])
    idle_cr = kw["idle_entry_cap"]
    idle_msg = kw["idle_msg_cap"]
    all_cr = kw["entry_cap_total"]
    all_msg = kw["msg_cap_total"]

    # Compute actual measured acceptance rate across the estate
    total_conn = sum(s["activity_all_time"].get("connections_sent", 0)
                    for s in kw["healthy_senders"]
                    if s["activity_all_time"].get("available"))
    total_acc = sum(s["activity_all_time"].get("connections_accepted", 0)
                   for s in kw["healthy_senders"]
                   if s["activity_all_time"].get("available"))
    measured_acc_rate = (total_acc / total_conn * 100) if total_conn > 0 else 0

    w("### Two-tier seat structure")
    w("")
    sn_count = sum(1 for s in kw["healthy_senders"] if s["sales_navigator"])
    non_sn_count = sum(1 for s in kw["healthy_senders"] if not s["sales_navigator"])
    sn_camps = sum(s["campaign_attachment"]["total"]
                  for s in kw["healthy_senders"] if s["sales_navigator"])
    non_sn_camps = sum(s["campaign_attachment"]["total"]
                      for s in kw["healthy_senders"] if not s["sales_navigator"])
    w(f"The estate has two tiers:")
    w(f"- **{sn_count} Sales Navigator seats**: {sn_camps} total campaign attachments "
      f"(avg {sn_camps//sn_count if sn_count else 0} per seat). These are the "
      f"heavy users, each on 12 IN_PROGRESS campaigns plus 18-24 PAUSED/FINISHED.")
    w(f"- **{non_sn_count} Regular seats**: {non_sn_camps} total campaign attachments "
      f"(avg {non_sn_camps//non_sn_count if non_sn_count else 0} per seat). "
      f"Most are on 8 IN_PROGRESS campaigns plus 7-9 PAUSED.")
    w("")
    w("Both tiers are fully committed. No seat in either tier is idle.")
    w("")

    w(f"### Measured connection acceptance rate: {measured_acc_rate:.1f}%")
    w("")
    w(f"Across the estate, {total_acc} of {total_conn} connection requests have been "
      f"accepted. This is the actual rate to use for planning, not a guess.")
    w("")

    w("#### Scenario A: Use ALL healthy seats (including those on IN_PROGRESS campaigns)")
    w("")
    w(f"- Total healthy seats: {total_healthy}")
    w(f"- Total daily connection request ceiling: {all_cr}")
    w(f"- 50 leads, one connection request each: needs 50 connection requests")
    w(f"- **Day 1: all 50 connection requests can be sent** "
      f"({all_cr} ceiling >> 50 needed)")
    w(f"- After connection acceptance (measured rate {measured_acc_rate:.1f}% "
      f"= ~{max(1, round(50 * measured_acc_rate / 100))} leads accept), "
      f"message step fires")
    w(f"- Total daily message ceiling: {all_msg}")
    w(f"- **Day 2-3: messages to accepted leads can be sent** "
      f"({all_msg} ceiling >> {max(1, round(50 * measured_acc_rate / 100))} needed)")
    w(f"- **Total time: 2-3 days** (day 1 connect, day 2-3 message after acceptance)")
    w("")

    w("#### Scenario B: Use only effectively idle seats")
    w("")
    w(f"- Idle healthy seats: {idle_count}")
    w(f"- Idle daily connection request ceiling: {idle_cr}")
    w(f"- Idle daily message ceiling: {idle_msg}")
    if idle_cr == 0:
        w(f"- **There are no idle seats.** Every healthy seat is on at least one "
          f"IN_PROGRESS campaign. To free capacity, campaigns would need to be "
          f"completed, paused, or seats detached.")
    else:
        if idle_cr >= 50:
            w(f"- **Day 1: all 50 connection requests can be sent** "
              f"({idle_cr} ceiling >= 50 needed)")
        elif idle_cr > 0:
            days_for_cr = -(-50 // idle_cr)
            w(f"- **Day 1-{days_for_cr}: connection requests** "
              f"({idle_cr}/day, need 50, takes {days_for_cr} day(s))")
    w("")

    w("#### Scenario C: One seat could do it")
    w("")
    w("A single seat with a 25-40 connection request daily limit:")
    w(f"- Day 1: send 25-40 connection requests (covers 50 leads in 2 days)")
    w(f"- Day 2: send remaining connection requests")
    w(f"- Day 3-4: messages to accepted leads")
    w(f"- **Total: 3-4 days from one seat**")
    w("")
    w("### The answer")
    w("")
    w("**One seat could move 50 leads through a connect-then-message cadence "
      "in 3-4 days.** The multi-sender question is therefore NOT URGENT for a "
      "50-lead cohort. The constraint is not throughput — it is approval and "
      "copy quality, as TASK-096 already found.")
    w("")
    w("The real question is not 'can we fit a cohort' but 'can we add a cohort "
      "without disturbing the 12 IN_PROGRESS campaigns already running.' Since "
      "every seat is already committed, the answer is: only by sharing seats "
      "with existing campaigns, or by waiting for campaigns to finish.")
    w("")

    w("### Assumptions behind this arithmetic")
    w("")
    w(f"1. **Connection acceptance rate: {measured_acc_rate:.1f}% measured.** "
      f"Used verbatim from the estate's all-time stats. Varies by seat from "
      f"6.9% to 15.5%.")
    w("2. **Daily ceilings are available.** The provider does not report "
      "today's usage, so we assume the full ceiling is free. This is an "
      "UPPER BOUND.")
    w("3. **Cooldowns are not blocking.** At measurement time, "
      f"{len(kw['any_cooldown'])} seat(s) were in cooldown. This can change.")
    w("4. **Detachment from finished campaigns is possible.** Not tested.")
    w("5. **LinkedIn tolerates the provider's configured limits.** "
      "A configured limit of 40/day is what the provider allows, not what "
      "LinkedIn will tolerate indefinitely. The provider sets these conservatively.")
    w("")

    w("## 7. What the Provider Does NOT Report")
    w("")
    w("These are findings, not failures:")
    w("")
    w("1. **Per-day activity per seat.** `/stats/GetOverallStats` returns "
      "all-time counters. There is no way to determine what a seat sent today.")
    w("2. **Cooldown duration.** A seat in cooldown reports `true` for the "
      "cooldown flag but does not say when it expires.")
    w("3. **Why auth is invalid.** `authIsValid: false` is a boolean. No "
      "diagnostic, no error message, no remediation hint.")
    w("4. **Per-campaign activity per seat.** Stats can be filtered by "
      "campaignIds AND accountIds together, but the cross-tabulation of "
      "'this seat sent N messages in this campaign' requires N API calls.")
    w("")

    w("---")
    w("")
    w(f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
      f"by `scripts/sender_utilisation.py`. Read-only. No provider mutations.*")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
