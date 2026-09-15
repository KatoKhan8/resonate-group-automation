#!/usr/bin/env python3
"""TASK-121: walk every campaign in the account and count payload.messages
per node. Reads only. Writes nothing.

Answers:
  1. Does ANY node in ANY campaign carry more than one entry in
     payload.messages?
  2. If yes: which campaign, which node type, how many entries?
  3. If no: report the totals so the absence is measured, not asserted.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers import heyreach


def count_messages_per_node(sequence):
    """Walk a sequence graph and return per-node message counts."""
    nodes, types, truncated = heyreach.walk_sequence(sequence)
    results = []
    for node in nodes:
        node_type = str(node.get("nodeType") or "<no-type>")
        payload = node.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        messages = payload.get("messages")
        msg_count = len(messages) if isinstance(messages, list) else 0
        results.append({
            "nodeType": node_type,
            "messageCount": msg_count,
        })
    return results, types, truncated


def main():
    total_campaigns = 0
    campaigns_with_multi = []
    campaigns_with_zero_nodes = []
    all_node_counts = {}  # nodeType -> count of nodes
    all_msg_counts = {}   # messageCount -> count of nodes
    total_nodes = 0
    total_truncated = 0
    errors = []

    # Page through all campaigns
    offset = 0
    page_size = 50
    all_campaigns = []
    while True:
        items, total = heyreach.campaigns(offset, page_size)
        if not items:
            break
        all_campaigns.extend(items)
        offset += len(items)
        if total is not None and offset >= int(total):
            break

    total_campaigns = len(all_campaigns)
    print(f"Total campaigns in account: {total_campaigns}")
    print()

    for campaign in all_campaigns:
        cid = campaign.get("id")
        cname = campaign.get("name", "<unnamed>")
        try:
            sequence = heyreach.campaign_sequence(cid)
        except Exception as e:
            errors.append((cid, cname, str(e)))
            continue

        node_results, types, truncated = count_messages_per_node(sequence)
        if truncated:
            total_truncated += 1

        if not node_results:
            campaigns_with_zero_nodes.append((cid, cname))
            continue

        has_multi = False
        multi_nodes = []
        for nr in node_results:
            total_nodes += 1
            nt = nr["nodeType"]
            mc = nr["messageCount"]
            all_node_counts[nt] = all_node_counts.get(nt, 0) + 1
            all_msg_counts[mc] = all_msg_counts.get(mc, 0) + 1
            if mc > 1:
                has_multi = True
                multi_nodes.append(nr)

        if has_multi:
            campaigns_with_multi.append({
                "campaignId": cid,
                "campaignName": cname,
                "multiMessageNodes": multi_nodes,
                "nodeTypes": sorted(types),
                "truncated": truncated,
            })

    # Report
    print(f"Campaigns walked: {total_campaigns}")
    print(f"Campaigns with errors: {len(errors)}")
    print(f"Campaigns with zero nodes: {len(campaigns_with_zero_nodes)}")
    print(f"Campaigns with truncated graphs: {total_truncated}")
    print(f"Total nodes across all campaigns: {total_nodes}")
    print()

    print("=== Node type distribution ===")
    for nt, count in sorted(all_node_counts.items(), key=lambda x: -x[1]):
        print(f"  {nt}: {count}")
    print()

    print("=== Message count distribution ===")
    for mc, count in sorted(all_msg_counts.items()):
        print(f"  {mc} message(s): {count} nodes")
    print()

    if campaigns_with_multi:
        print(f"=== CAMPAIGNS WITH MULTI-MESSAGE NODES ({len(campaigns_with_multi)}) ===")
        for entry in campaigns_with_multi:
            print(f"\n  Campaign {entry['campaignId']}: {entry['campaignName']}")
            print(f"  Node types: {', '.join(entry['nodeTypes'])}")
            print(f"  Truncated: {entry['truncated']}")
            for mn in entry["multiMessageNodes"]:
                print(f"    {mn['nodeType']}: {mn['messageCount']} messages")
    else:
        print("=== NO CAMPAIGN HAS A MULTI-MESSAGE NODE ===")
        print("Across all campaigns and all nodes, every payload.messages")
        print("list has 0 or 1 entries. None has more than one.")

    if errors:
        print(f"\n=== ERRORS ({len(errors)}) ===")
        for cid, cname, err in errors:
            print(f"  Campaign {cid} ({cname}): {err}")

    if campaigns_with_zero_nodes:
        print(f"\n=== CAMPAIGNS WITH ZERO NODES ({len(campaigns_with_zero_nodes)}) ===")
        for cid, cname in campaigns_with_zero_nodes:
            print(f"  Campaign {cid}: {cname}")


if __name__ == "__main__":
    main()
