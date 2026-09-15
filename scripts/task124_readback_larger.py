#!/usr/bin/env python3
"""TASK-124: prove readback on a larger campaign with diverse lead states.

Reads only. Writes nothing. Campaign 594061 proved the route works with
1 lead. This script reads a campaign with more leads and more diverse
states to prove the readback handles the full lifecycle.
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers import heyreach


def _hash(value):
    if not value:
        return "<empty>"
    return "sha256:" + hashlib.sha256(str(value).encode()).hexdigest()[:16]


def main():
    # Pick a campaign with diverse states - look for one with finished,
    # failed, and in-progress leads. Campaign 524002 has a good mix.
    # But let's find a smaller one to keep the read fast.
    # Let's look for campaigns with 10-100 leads for a manageable read.

    print("=== Finding a campaign with diverse states and manageable size ===")
    candidates = []
    offset = 0
    while True:
        items, total = heyreach.campaigns(offset, 50)
        if not items:
            break
        for item in items:
            stats = item.get("progressStats") or {}
            ip = stats.get("totalUsersInProgress", 0) or 0
            pend = stats.get("totalUsersPending", 0) or 0
            fin = stats.get("totalUsersFinished", 0) or 0
            fail = stats.get("totalUsersFailed", 0) or 0
            total_users = stats.get("totalUsers", 0) or 0
            # Want diverse states and manageable size
            state_types = sum(1 for x in [ip, pend, fin, fail] if x > 0)
            if 5 <= total_users <= 200 and state_types >= 2:
                candidates.append({
                    "id": item.get("id"),
                    "name": item.get("name", "<unnamed>"),
                    "status": item.get("status"),
                    "total": total_users,
                    "state_types": state_types,
                    "ip": ip, "pend": pend, "fin": fin, "fail": fail,
                })
        offset += len(items)
        if total is not None and offset >= int(total):
            break

    candidates.sort(key=lambda c: (-c["state_types"], c["total"]))
    if not candidates:
        print("No suitable candidate found. Using the canary.")
        return

    target = candidates[0]
    print(f"Selected campaign {target['id']}: {target['name'][:50]}")
    print(f"  Status: {target['status']}")
    print(f"  Total leads: {target['total']}")
    print(f"  in_progress={target['ip']}, pending={target['pend']}, "
          f"finished={target['fin']}, failed={target['fail']}")
    print()

    # Read all leads
    print(f"=== Reading all leads from campaign {target['id']} ===")
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

    print(f"Leads read: {len(all_leads)}")
    print()

    # State distribution
    state_counts = {}
    connection_counts = {}
    message_counts = {}
    error_codes = {}
    leads_with_timestamps = 0

    for lead in all_leads:
        state = lead.get("state", "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1

        raw = lead.get("raw", {})
        conn = str(raw.get("leadConnectionStatus") or "None").lower()
        connection_counts[conn] = connection_counts.get(conn, 0) + 1

        msg = str(raw.get("leadMessageStatus") or "None").lower()
        message_counts[msg] = message_counts.get(msg, 0) + 1

        ec = lead.get("error_code")
        if ec:
            error_codes[str(ec)] = error_codes.get(str(ec), 0) + 1

        if lead.get("at"):
            leads_with_timestamps += 1

    print("=== Lifecycle state distribution ===")
    for state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")
    print()

    print("=== Connection state distribution ===")
    for state, count in sorted(connection_counts.items(),
                                key=lambda x: -x[1]):
        print(f"  {state}: {count}")
    print()

    print("=== Message state distribution ===")
    for state, count in sorted(message_counts.items(),
                                key=lambda x: -x[1]):
        print(f"  {state}: {count}")
    print()

    if error_codes:
        print("=== Error codes ===")
        for ec, count in sorted(error_codes.items(), key=lambda x: -x[1]):
            print(f"  {ec}: {count}")
        print()

    print(f"Leads with action timestamps: {leads_with_timestamps}/{len(all_leads)}")
    print()

    # Show one lead per state
    print("=== One lead per lifecycle state (HASHED identifiers) ===")
    seen_states = set()
    for lead in all_leads:
        state = lead.get("state", "unknown")
        if state in seen_states:
            continue
        seen_states.add(state)
        print(f"\n  State: {state}")
        print(f"    provider_lead_id: {_hash(lead.get('provider_lead_id'))}")
        print(f"    profile_url: {_hash(lead.get('profile_url'))}")
        print(f"    sender_id: {_hash(lead.get('sender_id'))}")
        print(f"    error_code: {lead.get('error_code')}")
        print(f"    created_at: {lead.get('created_at')}")
        print(f"    last_action: {lead.get('at')}")
        raw = lead.get("raw", {})
        print(f"    raw.campaign: {raw.get('leadCampaignStatus')}")
        print(f"    raw.connection: {raw.get('leadConnectionStatus')}")
        print(f"    raw.message: {raw.get('leadMessageStatus')}")

    # Test readback_membership with a sample
    print()
    print("=== readback_membership test ===")
    sample_urls = [l["profile_url"] for l in all_leads[:5]
                   if l.get("profile_url")]
    if sample_urls:
        result = heyreach.readback_membership(target["id"], sample_urls)
        print(f"Expected: {len(sample_urls)} URLs")
        print(f"Found: {len(result['found'])}")
        print(f"Missing: {len(result['missing'])}")
        print(f"Campaign total: {result['total']}")
        for pl in result["per_lead"]:
            print(f"  {_hash(pl.get('profile_url'))}: "
                  f"state={pl.get('state')}, "
                  f"connection={pl.get('raw', {}).get('leadConnectionStatus')}, "
                  f"message={pl.get('raw', {}).get('leadMessageStatus')}")

    # Cross-check with campaign_stats
    print()
    print("=== campaign_stats cross-check ===")
    try:
        stats = heyreach.campaign_stats(target["id"])
        for k, v in sorted(stats.items()):
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"  Error: {e}")

    # Prove the key property: every lead has a profile URL
    print()
    print("=== KEY PROPERTY: profile URL availability ===")
    with_url = sum(1 for l in all_leads if l.get("profile_url"))
    without_url = len(all_leads) - with_url
    print(f"  With profile URL: {with_url}/{len(all_leads)}")
    print(f"  Without profile URL: {without_url}/{len(all_leads)}")
    if with_url == len(all_leads):
        print("  CONFIRMED: every lead carries a profile URL, which is "
              "what readback_membership matches on")
    else:
        print("  WARNING: some leads lack profile URLs")


if __name__ == "__main__":
    main()
