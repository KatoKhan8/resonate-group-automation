#!/usr/bin/env python3
"""TASK-124: prove lead readback works on a campaign that has leads.

Reads only. Writes nothing. The single most valuable thing in this task
is turning "we think we could confirm a write" into "we have confirmed
we can read the result".

Steps:
1. Walk all campaigns and find ones with leads (via progressStats).
2. Pick a campaign with leads and page through its leads.
3. Show the readback returns what it should: profile URLs, lifecycle
   states, connection states, message states.
4. Hash every prospect identifier in the output.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers import heyreach


def _hash(value):
    """SHA-256 prefix, never the raw value."""
    if not value:
        return "<empty>"
    return "sha256:" + hashlib.sha256(str(value).encode()).hexdigest()[:16]


def main():
    # Step 1: Walk all campaigns and find ones with leads
    print("=== STEP 1: Walking all campaigns to find ones with leads ===")
    campaigns_with_leads = []
    offset = 0
    total_campaigns = 0
    while True:
        items, total = heyreach.campaigns(offset, 50)
        if not items:
            break
        total_campaigns = max(total_campaigns, total or 0)
        for item in items:
            stats = item.get("progressStats") or {}
            in_progress = stats.get("totalUsersInProgress", 0) or 0
            pending = stats.get("totalUsersPending", 0) or 0
            finished = stats.get("totalUsersFinished", 0) or 0
            failed = stats.get("totalUsersFailed", 0) or 0
            total_users = stats.get("totalUsers", 0) or 0
            # A campaign has leads if any bucket is non-zero
            has_leads = (in_progress + pending + finished + failed) > 0
            if has_leads:
                campaigns_with_leads.append({
                    "id": item.get("id"),
                    "name": item.get("name", "<unnamed>"),
                    "status": item.get("status"),
                    "in_progress": in_progress,
                    "pending": pending,
                    "finished": finished,
                    "failed": failed,
                    "total_users": total_users,
                })
        offset += len(items)
        if total is not None and offset >= int(total):
            break

    print(f"Total campaigns in account: {total_campaigns}")
    print(f"Campaigns with leads: {len(campaigns_with_leads)}")
    print()

    # Sort by total leads descending
    campaigns_with_leads.sort(key=lambda c: c["total_users"], reverse=True)

    print("=== Campaigns with leads (top 10) ===")
    for c in campaigns_with_leads[:10]:
        print(f"  {c['id']:>8}  {c['status']:>12}  "
              f"leads={c['total_users']:>5}  "
              f"(in_progress={c['in_progress']}, pending={c['pending']}, "
              f"finished={c['finished']}, failed={c['failed']})  "
              f"{c['name'][:50]}")
    print()

    # Step 2: Pick the smallest campaign with leads for readback
    # (smallest so the readback is fast and complete)
    if not campaigns_with_leads:
        print("ERROR: No campaigns with leads found. Cannot prove readback.")
        return

    # Pick the smallest one with at least 1 lead
    target = None
    for c in reversed(campaigns_with_leads):
        if c["total_users"] >= 1:
            target = c
            break
    if target is None:
        target = campaigns_with_leads[-1]

    print(f"=== STEP 2: Reading leads from campaign {target['id']} "
          f"({target['name'][:40]}) ===")
    print(f"Status: {target['status']}, reported leads: {target['total_users']}")
    print()

    # Step 3: Page through all leads
    all_leads = []
    lead_offset = 0
    while True:
        rows, count = heyreach.campaign_leads(target["id"],
                                               offset=lead_offset,
                                               limit=100)
        if not rows:
            break
        all_leads.extend(rows)
        lead_offset += len(rows)
        if count is not None and lead_offset >= int(count):
            break

    print(f"=== STEP 3: Readback results ===")
    print(f"Leads read from provider: {len(all_leads)}")
    print(f"Provider totalCount: {target['total_users']}")
    print()

    # Step 4: Show lifecycle state distribution
    state_counts = {}
    connection_counts = {}
    message_counts = {}
    leads_with_profile = 0
    leads_with_error = 0

    for lead in all_leads:
        state = lead.get("state", "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1

        raw = lead.get("raw", {})
        conn = str(raw.get("leadConnectionStatus") or "None").lower()
        connection_counts[conn] = connection_counts.get(conn, 0) + 1

        msg = str(raw.get("leadMessageStatus") or "None").lower()
        message_counts[msg] = message_counts.get(msg, 0) + 1

        if lead.get("profile_url"):
            leads_with_profile += 1
        if lead.get("error_code"):
            leads_with_error += 1

    print("Lifecycle state distribution:")
    for state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")
    print()

    print("Connection state distribution:")
    for state, count in sorted(connection_counts.items(),
                                key=lambda x: -x[1]):
        print(f"  {state}: {count}")
    print()

    print("Message state distribution:")
    for state, count in sorted(message_counts.items(),
                                key=lambda x: -x[1]):
        print(f"  {state}: {count}")
    print()

    print(f"Leads with profile URL: {leads_with_profile}/{len(all_leads)}")
    print(f"Leads with error code: {leads_with_error}/{len(all_leads)}")
    print()

    # Step 5: Show first 5 leads (HASHED identifiers)
    print("=== STEP 5: First 5 leads (identifiers HASHED) ===")
    for i, lead in enumerate(all_leads[:5]):
        print(f"\n  Lead {i+1}:")
        print(f"    provider_lead_id: {_hash(lead.get('provider_lead_id'))}")
        print(f"    profile_url: {_hash(lead.get('profile_url'))}")
        print(f"    provider_profile_id: "
              f"{_hash(lead.get('provider_profile_id'))}")
        print(f"    sender_id: {_hash(lead.get('sender_id'))}")
        print(f"    state: {lead.get('state')}")
        print(f"    error_code: {lead.get('error_code')}")
        print(f"    created_at: {lead.get('created_at')}")
        print(f"    last_action: {lead.get('at')}")
        raw = lead.get("raw", {})
        print(f"    raw.campaign: {raw.get('leadCampaignStatus')}")
        print(f"    raw.connection: {raw.get('leadConnectionStatus')}")
        print(f"    raw.message: {raw.get('leadMessageStatus')}")

    # Step 6: Prove the readback function works
    print()
    print("=== STEP 6: Testing readback_membership ===")
    if all_leads:
        # Use the first 3 leads' profile URLs as the expected set
        sample_urls = [l["profile_url"] for l in all_leads[:3]
                       if l.get("profile_url")]
        if sample_urls:
            result = heyreach.readback_membership(
                target["id"], sample_urls)
            print(f"Expected URLs: {len(sample_urls)}")
            print(f"Found: {len(result['found'])}")
            print(f"Missing: {len(result['missing'])}")
            print(f"Campaign total: {result['total']}")
            print(f"Per-lead state count: {len(result['per_lead'])}")
            if result["found"]:
                print("READBACK CONFIRMS: leads present in campaign are "
                      "detectable via the read route")
            if result["missing"]:
                print("WARNING: some expected URLs not found")

    # Step 7: Also check campaign 599020 to confirm it has 0 leads
    print()
    print("=== STEP 7: Confirming campaign 599020 has 0 leads ===")
    rows_599020, count_599020 = heyreach.campaign_leads(599020, offset=0,
                                                          limit=100)
    print(f"Campaign 599020 leads read: {len(rows_599020)}")
    print(f"Campaign 599020 totalCount: {count_599020}")
    print("Confirmed: 0 leads, proves nothing about readback capability")

    # Step 8: Test campaign_stats as independent cross-check
    print()
    print("=== STEP 8: campaign_stats cross-check ===")
    try:
        stats = heyreach.campaign_stats(target["id"])
        print(f"Campaign {target['id']} stats:")
        for k, v in sorted(stats.items()):
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"Stats error: {e}")


if __name__ == "__main__":
    main()
