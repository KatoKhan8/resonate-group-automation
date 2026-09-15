#!/usr/bin/env python3
"""Read-only analysis: which senders are on which campaigns, and what status.

TASK-127 analysis. Reads all campaigns from HeyReach, maps each healthy sender
to its campaigns and their statuses, and determines effective availability.

READ-ONLY. Writes nothing to any provider.
Output goes to stdout as JSON.
"""

import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import heyreach, load_env, request  # noqa: E402


def h(value):
    v = " ".join(str(value or "").split()).lower()
    return hashlib.sha256(v.encode("utf-8")).hexdigest()[:12] if v else None


def main():
    load_env()
    base, hdr = heyreach.BASE, heyreach.headers()

    # Fetch all seats
    st, adata = request("POST", base + "/li_account/GetAll", hdr,
                        {"offset": 0, "limit": 100})
    if st != 200:
        print("li_account/GetAll failed: HTTP %s" % st, file=sys.stderr)
        return 2
    seats = {a["id"]: a for a in (adata.get("items") or [])}

    # Fetch all campaigns (paginated)
    all_campaigns = []
    offset = 0
    while True:
        st, cdata = request("POST", base + "/campaign/GetAll", hdr,
                            {"offset": offset, "limit": 100})
        if st != 200:
            print("campaign/GetAll failed: HTTP %s" % st, file=sys.stderr)
            return 2
        items = cdata.get("items") or []
        all_campaigns.extend(items)
        if len(items) < 100:
            break
        offset += 100

    # Build campaign lookup
    campaigns = {}
    for c in all_campaigns:
        cid = c.get("id")
        campaigns[cid] = {
            "id": cid,
            "name": c.get("name", ""),
            "status": c.get("status", ""),
            "campaignAccountIds": [int(a) for a in (c.get("campaignAccountIds") or [])],
            "lead_count": (c.get("progressStats") or {}).get("totalUsers", 0),
        }

    # For each healthy sender, find which campaigns it is on and their statuses
    healthy_senders = {sid: s for sid, s in seats.items()
                       if s.get("isActive") and s.get("authIsValid")}
    auth_invalid = {sid: s for sid, s in seats.items()
                    if s.get("isActive") and not s.get("authIsValid")}

    sender_analysis = {}
    for sid, s in sorted(healthy_senders.items()):
        on_campaigns = []
        for cid, camp in campaigns.items():
            if sid in camp["campaignAccountIds"]:
                on_campaigns.append({
                    "campaign_id": cid,
                    "name": camp["name"][:60],
                    "status": camp["status"],
                    "lead_count": camp["lead_count"],
                })

        # Classify effective availability
        statuses = [c["status"] for c in on_campaigns]
        in_progress = sum(1 for st in statuses if st == "IN_PROGRESS")
        draft = sum(1 for st in statuses if st == "DRAFT")
        paused = sum(1 for st in statuses if st == "PAUSED")
        finished = sum(1 for st in statuses if st == "FINISHED")

        # A seat is effectively idle if it has NO IN_PROGRESS campaigns
        # DRAFT campaigns could send if activated; PAUSED can be resumed;
        # FINISHED campaigns are done.
        effectively_idle = in_progress == 0

        limits = s.get("accountLimits") or {}
        sender_analysis[str(sid)] = {
            "sender_id": sid,
            "identity_hash": h("%s %s|%s" % (s.get("firstName"), s.get("lastName"),
                                              s.get("emailAddress"))),
            "sales_navigator": s.get("isValidNavigator", False),
            "daily_cr_limit": limits.get("connectioRequestLimit") or limits.get("connectionRequestLimit") or 0,
            "daily_msg_limit": limits.get("messageLimit") or 0,
            "total_campaigns": len(on_campaigns),
            "by_status": {
                "IN_PROGRESS": in_progress,
                "DRAFT": draft,
                "PAUSED": paused,
                "FINISHED": finished,
            },
            "effectively_idle": effectively_idle,
            "campaigns": sorted(on_campaigns, key=lambda c: (
                {"IN_PROGRESS": 0, "DRAFT": 1, "PAUSED": 2, "FINISHED": 3}.get(c["status"], 4),
                c["campaign_id"]
            )),
        }

    # Auth-invalid sender analysis
    auth_invalid_analysis = []
    for sid, s in sorted(auth_invalid.items()):
        on_campaigns = []
        for cid, camp in campaigns.items():
            if sid in camp["campaignAccountIds"]:
                on_campaigns.append({
                    "campaign_id": cid,
                    "name": camp["name"][:60],
                    "status": camp["status"],
                    "lead_count": camp["lead_count"],
                })
        auth_invalid_analysis.append({
            "sender_id": sid,
            "identity_hash": h("%s %s|%s" % (s.get("firstName"), s.get("lastName"),
                                              s.get("emailAddress"))),
            "campaigns": on_campaigns,
        })

    # Summary
    idle_count = sum(1 for v in sender_analysis.values() if v["effectively_idle"])
    total_healthy = len(healthy_senders)

    # Campaign sender count distribution
    sender_counts = {}
    for camp in campaigns.values():
        n = len(camp["campaignAccountIds"])
        sender_counts[n] = sender_counts.get(n, 0) + 1

    # Max senders on any single campaign
    max_senders = max(len(c["campaignAccountIds"]) for c in campaigns.values()) if campaigns else 0
    multi_sender_campaigns = sum(1 for c in campaigns.values() if len(c["campaignAccountIds"]) > 1)

    result = {
        "summary": {
            "total_campaigns": len(campaigns),
            "total_healthy_senders": total_healthy,
            "effectively_idle_healthy_senders": idle_count,
            "auth_invalid_senders": len(auth_invalid_analysis),
            "campaigns_with_multiple_senders": multi_sender_campaigns,
            "max_senders_on_one_campaign": max_senders,
            "sender_count_distribution": dict(sorted(sender_counts.items())),
            "status_totals": {},
        },
        "sender_analysis": sender_analysis,
        "auth_invalid_senders": auth_invalid_analysis,
    }

    # Campaign status totals
    for c in campaigns.values():
        st = c["status"]
        result["summary"]["status_totals"][st] = result["summary"]["status_totals"].get(st, 0) + 1

    json.dump(result, sys.stdout, indent=2, default=str)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
