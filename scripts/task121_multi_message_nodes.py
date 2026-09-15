#!/usr/bin/env python3
"""TASK-121: Does any node in any campaign carry more than one payload.messages entry?

Reads only. No writes, no sends. Pages every campaign, fetches each sequence,
walks the graph, and counts messages per node.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.providers import heyreach


def main():
    # Step 1: page through ALL campaigns
    all_campaigns = []
    offset = 0
    page_size = 100  # MAX_PAGE
    total = None

    print("=== Paging all campaigns ===")
    while True:
        try:
            items, count = heyreach.campaigns(offset, page_size)
        except Exception as e:
            print(f"ERROR fetching campaigns at offset {offset}: {e}")
            sys.exit(1)
        if total is None:
            total = count
            print(f"Total campaigns reported: {total}")
        all_campaigns.extend(items)
        offset += len(items)
        if not items or (total is not None and offset >= int(total)):
            break
        time.sleep(0.2)

    print(f"Campaigns fetched: {len(all_campaigns)}")
    if total is not None and len(all_campaigns) != int(total):
        print(f"WARNING: fetched {len(all_campaigns)} but totalCount says {total}")
    print()

    # Step 2: for each campaign, fetch its sequence and walk the graph
    total_nodes = 0
    total_copy_nodes = 0
    total_truncated = 0
    multi_message_nodes = []
    campaigns_with_sequences = 0
    campaigns_without_sequences = 0
    campaigns_error = []
    messages_per_node_distribution = {}

    print("=== Walking every campaign's sequence ===")
    for i, camp in enumerate(all_campaigns):
        cid = camp.get("id")
        cname = camp.get("name", "?")
        cstatus = camp.get("status", "?")

        try:
            seq = heyreach.campaign_sequence(cid)
        except Exception as e:
            campaigns_error.append((cid, cname, str(e)))
            continue

        if not seq or not isinstance(seq, dict):
            campaigns_without_sequences += 1
            continue

        campaigns_with_sequences += 1
        nodes, types, truncated = heyreach.walk_sequence(seq)
        if truncated:
            total_truncated += 1

        for node in nodes:
            total_nodes += 1
            payload = node.get("payload")
            if not isinstance(payload, dict):
                continue
            messages = payload.get("messages")
            if not isinstance(messages, list):
                continue

            n = len(messages)
            total_copy_nodes += 1
            messages_per_node_distribution[n] = messages_per_node_distribution.get(n, 0) + 1

            if n > 1:
                multi_message_nodes.append({
                    "campaign_id": cid,
                    "campaign_name": cname,
                    "campaign_status": cstatus,
                    "node_type": node.get("nodeType"),
                    "message_count": n,
                    "messages_preview": [
                        (str(m)[:80] if isinstance(m, str) else json.dumps(m)[:80])
                        for m in messages
                    ],
                })

        if (i + 1) % 10 == 0:
            print(f"  ...processed {i + 1}/{len(all_campaigns)} campaigns")
            time.sleep(0.2)

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Campaigns fetched:          {len(all_campaigns)}")
    print(f"Campaigns with sequences:   {campaigns_with_sequences}")
    print(f"Campaigns without sequence: {campaigns_without_sequences}")
    print(f"Campaigns with errors:      {len(campaigns_error)}")
    print(f"Total nodes walked:         {total_nodes}")
    print(f"Nodes carrying copy:        {total_copy_nodes}")
    print(f"Graphs truncated:           {total_truncated}")
    print()
    print("Messages-per-node distribution:")
    for k in sorted(messages_per_node_distribution.keys()):
        print(f"  {k} message(s): {messages_per_node_distribution[k]} nodes")
    print()

    if multi_message_nodes:
        print(f"MULTI-MESSAGE NODES FOUND: {len(multi_message_nodes)}")
        for mm in multi_message_nodes:
            print(f"  Campaign {mm['campaign_id']} ({mm['campaign_name']!r}, "
                  f"status={mm['campaign_status']})")
            print(f"    Node type: {mm['node_type']}")
            print(f"    Message count: {mm['message_count']}")
            for j, preview in enumerate(mm['messages_preview']):
                print(f"    Message[{j}]: {preview}")
            print()
    else:
        print("NO MULTI-MESSAGE NODES FOUND across all campaigns.")
        print("Every copy-bearing node carries exactly 1 entry in payload.messages.")

    if campaigns_error:
        print()
        print(f"Campaigns that errored ({len(campaigns_error)}):")
        for cid, cname, err in campaigns_error:
            print(f"  {cid} ({cname!r}): {err}")


if __name__ == "__main__":
    main()
