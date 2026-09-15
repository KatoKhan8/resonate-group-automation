#!/usr/bin/env python3
"""Walk every campaign in the HeyReach account and count messages per node.

TASK-121: does any node in any campaign carry more than one entry in
payload.messages?

Reads only. No writes to any provider or state file.
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.providers import load_env, heyreach


def all_campaigns():
    """Every campaign in the account, paged."""
    items, total, offset = [], None, 0
    while True:
        page, count = heyreach.campaigns(offset, 100)
        if total is None:
            total = count
        items.extend(page)
        offset += len(page)
        if not page or (total is not None and offset >= int(total)):
            break
    return items, total


def main():
    load_env()
    campaigns, total = all_campaigns()
    print(f"Total campaigns reported: {total}")
    print(f"Campaigns fetched: {len(campaigns)}")
    print()

    multi_message_nodes = []
    total_nodes_walked = 0
    total_truncated = 0
    nodes_with_messages = 0
    nodes_by_type = {}
    max_messages_seen = 0

    for camp in campaigns:
        cid = camp.get("id")
        cname = camp.get("name", "?")
        try:
            seq = heyreach.campaign_sequence(cid)
        except Exception as e:
            print(f"  Campaign {cid} ({cname}): sequence fetch FAILED: {e}")
            continue

        nodes, types, truncated = heyreach.walk_sequence(seq)
        total_nodes_walked += len(nodes)
        if truncated:
            total_truncated += 1

        for node in nodes:
            kind = str(node.get("nodeType") or "UNKNOWN")
            nodes_by_type[kind] = nodes_by_type.get(kind, 0) + 1
            payload = node.get("payload")
            if not isinstance(payload, dict):
                continue
            messages = payload.get("messages")
            if not isinstance(messages, list):
                continue
            count = len(messages)
            if count == 0:
                continue
            nodes_with_messages += 1
            if count > max_messages_seen:
                max_messages_seen = count
            if count > 1:
                multi_message_nodes.append({
                    "campaign_id": cid,
                    "campaign_name": cname,
                    "node_type": kind,
                    "message_count": count,
                })

    print(f"Total nodes walked: {total_nodes_walked}")
    print(f"Nodes with messages: {nodes_with_messages}")
    print(f"Graphs truncated: {total_truncated}")
    print(f"Max messages on a single node: {max_messages_seen}")
    print()
    print("Node type distribution:")
    for kind, count in sorted(nodes_by_type.items()):
        print(f"  {kind}: {count}")
    print()

    if multi_message_nodes:
        print(f"MULTI-MESSAGE NODES FOUND: {len(multi_message_nodes)}")
        for entry in multi_message_nodes:
            print(f"  Campaign {entry['campaign_id']} "
                  f"({entry['campaign_name']}): "
                  f"type={entry['node_type']}, "
                  f"messages={entry['message_count']}")
    else:
        print("NO MULTI-MESSAGE NODES FOUND across all campaigns.")
        print("Every node with messages carries exactly 1.")


if __name__ == "__main__":
    main()
