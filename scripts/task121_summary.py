#!/usr/bin/env python3
"""TASK-121 summary: compact view of multi-message nodes per campaign."""
import json
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.providers import heyreach


def main():
    # Page all campaigns
    all_campaigns = []
    offset = 0
    total = None
    while True:
        items, count = heyreach.campaigns(offset, 100)
        if total is None:
            total = count
        all_campaigns.extend(items)
        offset += len(items)
        if not items or (total is not None and offset >= int(total)):
            break
        time.sleep(0.2)

    print(f"Campaigns: {len(all_campaigns)} (totalCount={total})")

    # Per-campaign summary
    campaign_summaries = {}
    errors = []

    for camp in all_campaigns:
        cid = camp.get("id")
        cname = camp.get("name", "?")
        cstatus = camp.get("status", "?")

        try:
            seq = heyreach.campaign_sequence(cid)
        except Exception as e:
            errors.append((cid, cname, str(e)))
            continue

        if not seq or not isinstance(seq, dict):
            continue

        nodes, types, truncated = heyreach.walk_sequence(seq)

        # Count nodes by type
        type_counts = defaultdict(int)
        for n in nodes:
            t = n.get("nodeType", "?")
            type_counts[t] += 1

        # Check multi-message nodes
        multi = []
        single = 0
        for node in nodes:
            payload = node.get("payload")
            if not isinstance(payload, dict):
                continue
            messages = payload.get("messages")
            if not isinstance(messages, list):
                continue
            n_msg = len(messages)
            if n_msg > 1:
                multi.append({
                    "node_type": node.get("nodeType"),
                    "count": n_msg,
                })
            elif n_msg == 1:
                single += 1

        campaign_summaries[cid] = {
            "name": cname,
            "status": cstatus,
            "total_nodes": len(nodes),
            "node_types": dict(type_counts),
            "single_msg_nodes": single,
            "multi_msg_nodes": len(multi),
            "multi_details": multi,
            "truncated": truncated,
        }
        time.sleep(0.1)

    # Print summary
    print()
    print("=" * 70)
    print("CAMPAIGNS WITH MULTI-MESSAGE NODES")
    print("=" * 70)

    multi_camps = {k: v for k, v in campaign_summaries.items()
                   if v["multi_msg_nodes"] > 0}
    single_only = {k: v for k, v in campaign_summaries.items()
                   if v["multi_msg_nodes"] == 0 and v["single_msg_nodes"] > 0}
    no_copy = {k: v for k, v in campaign_summaries.items()
               if v["single_msg_nodes"] == 0 and v["multi_msg_nodes"] == 0}

    print(f"\nCampaigns with multi-message nodes: {len(multi_camps)}")
    print(f"Campaigns with single-message nodes only: {len(single_only)}")
    print(f"Campaigns with no copy-bearing nodes: {len(no_copy)}")
    print(f"Campaigns that errored: {len(errors)}")

    # Aggregate: what node types carry multiple messages?
    node_type_multi = defaultdict(list)
    for cid, info in multi_camps.items():
        for detail in info["multi_details"]:
            node_type_multi[detail["node_type"]].append(
                (cid, info["name"][:50], info["status"], detail["count"]))

    print()
    print("NODE TYPES CARRYING MULTIPLE MESSAGES:")
    for nt, entries in sorted(node_type_multi.items()):
        counts = [e[3] for e in entries]
        print(f"  {nt}: {len(entries)} nodes, range {min(counts)}-{max(counts)} messages")

    # Per-campaign detail
    print()
    print("-" * 70)
    print("PER-CAMPAIGN DETAIL (multi-message campaigns only)")
    print("-" * 70)
    for cid in sorted(multi_camps.keys()):
        info = multi_camps[cid]
        print(f"\nCampaign {cid}: {info['name']!r}")
        print(f"  Status: {info['status']}")
        print(f"  Total nodes: {info['total_nodes']}, "
              f"single-msg: {info['single_msg_nodes']}, "
              f"multi-msg: {info['multi_msg_nodes']}")
        print(f"  Node types: {info['node_types']}")
        for d in info["multi_details"]:
            print(f"    {d['node_type']}: {d['count']} messages")

    # Campaigns with NO multi-message nodes
    print()
    print("-" * 70)
    print("CAMPAIGNS WITH ONLY SINGLE-MESSAGE NODES")
    print("-" * 70)
    for cid in sorted(single_only.keys()):
        info = single_only[cid]
        print(f"  {cid}: {info['name'][:60]!r} ({info['status']}) "
              f"- {info['single_msg_nodes']} single-msg nodes")

    if errors:
        print()
        print(f"ERRORS ({len(errors)}):")
        for cid, cname, err in errors:
            print(f"  {cid} ({cname!r}): {err}")


if __name__ == "__main__":
    main()
