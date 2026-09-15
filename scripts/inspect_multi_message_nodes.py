#!/usr/bin/env python3
"""Inspect the structure of multi-message nodes to understand what they are.

TASK-121 follow-up: are the multiple messages variants (rotation), sequential
steps, or something else?
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.providers import load_env, heyreach


def all_campaigns():
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


def analyse_node(node, campaign_id, campaign_name):
    """Return a description of a multi-message node."""
    kind = str(node.get("nodeType") or "UNKNOWN")
    payload = node.get("payload")
    if not isinstance(payload, dict):
        return None
    messages = payload.get("messages")
    if not isinstance(messages, list) or len(messages) <= 1:
        return None

    result = {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "node_type": kind,
        "message_count": len(messages),
        "delay": node.get("actionDelay"),
        "delay_unit": node.get("actionDelayUnit"),
        "has_fallback": payload.get("fallbackMessage") is not None,
        "fallback_preview": None,
        "message_previews": [],
        "has_conditional": node.get("conditionalNode") is not None,
        "has_unconditional": node.get("unconditionalNode") is not None,
    }

    fb = payload.get("fallbackMessage")
    if isinstance(fb, str):
        result["fallback_preview"] = fb[:80]
    elif isinstance(fb, dict):
        result["fallback_preview"] = str({k: str(v)[:40] for k, v in fb.items()})

    for i, msg in enumerate(messages):
        if isinstance(msg, str):
            result["message_previews"].append(msg[:100])
        elif isinstance(msg, dict):
            preview = {k: str(v)[:60] for k, v in msg.items()}
            result["message_previews"].append(preview)
        else:
            result["message_previews"].append(f"<{type(msg).__name__}>")

    return result


def main():
    load_env()
    campaigns, total = all_campaigns()
    print(f"Campaigns: {len(campaigns)} of {total}")
    print()

    multi_nodes = []
    single_nodes = 0
    zero_msg_nodes = 0

    for camp in campaigns:
        cid = camp.get("id")
        cname = camp.get("name", "?")
        try:
            seq = heyreach.campaign_sequence(cid)
        except Exception:
            continue
        nodes, types, truncated = heyreach.walk_sequence(seq)
        for node in nodes:
            payload = node.get("payload")
            if not isinstance(payload, dict):
                continue
            messages = payload.get("messages")
            if not isinstance(messages, list):
                continue
            if len(messages) == 0:
                zero_msg_nodes += 1
            elif len(messages) == 1:
                single_nodes += 1
            else:
                info = analyse_node(node, cid, cname)
                if info:
                    multi_nodes.append(info)

    print(f"Nodes with 0 messages: {zero_msg_nodes}")
    print(f"Nodes with 1 message: {single_nodes}")
    print(f"Nodes with >1 messages: {len(multi_nodes)}")
    print()

    # Group by campaign
    by_campaign = {}
    for n in multi_nodes:
        key = (n["campaign_id"], n["campaign_name"])
        by_campaign.setdefault(key, []).append(n)

    # Show a representative sample: one campaign with small counts, one large
    print("=" * 70)
    print("SAMPLE 1: A campaign with 2-message nodes (recent)")
    print("=" * 70)
    for camp_key, nodes in sorted(by_campaign.items()):
        if any(n["message_count"] == 2 for n in nodes) and \
           all(n["message_count"] <= 3 for n in nodes):
            cid, cname = camp_key
            print(f"\nCampaign {cid}: {cname}")
            for n in nodes:
                print(f"  Node type={n['node_type']}, messages={n['message_count']}, "
                      f"delay={n['delay']} {n['delay_unit']}, "
                      f"fallback={n['has_fallback']}")
                for i, preview in enumerate(n["message_previews"]):
                    print(f"    msg[{i}]: {preview!r}")
            break

    print()
    print("=" * 70)
    print("SAMPLE 2: A campaign with the highest message count")
    print("=" * 70)
    max_node = max(multi_nodes, key=lambda n: n["message_count"])
    cid, cname = max_node["campaign_id"], max_node["campaign_name"]
    print(f"\nCampaign {cid}: {cname}")
    print(f"  Node type={max_node['node_type']}, messages={max_node['message_count']}")
    for i, preview in enumerate(max_node["message_previews"]):
        print(f"    msg[{i}]: {preview!r}")

    print()
    print("=" * 70)
    print("SAMPLE 3: A CONNECTION_REQUEST with multiple messages")
    print("=" * 70)
    for n in multi_nodes:
        if n["node_type"] == "CONNECTION_REQUEST" and n["message_count"] > 2:
            print(f"\nCampaign {n['campaign_id']}: {n['campaign_name']}")
            print(f"  messages={n['message_count']}")
            for i, preview in enumerate(n["message_previews"]):
                print(f"    msg[{i}]: {preview!r}")
            break

    print()
    print("=" * 70)
    print("SAMPLE 4: An INMAIL with multiple messages")
    print("=" * 70)
    for n in multi_nodes:
        if n["node_type"] == "INMAIL" and n["message_count"] > 1:
            print(f"\nCampaign {n['campaign_id']}: {n['campaign_name']}")
            print(f"  messages={n['message_count']}")
            for i, preview in enumerate(n["message_previews"]):
                print(f"    msg[{i}]: {preview!r}")
            break

    # Distribution of message counts
    print()
    print("=" * 70)
    print("DISTRIBUTION: message counts across all multi-message nodes")
    print("=" * 70)
    from collections import Counter
    counts = Counter(n["message_count"] for n in multi_nodes)
    for count in sorted(counts):
        print(f"  {count} messages: {counts[count]} nodes")

    # Distribution by node type
    print()
    print("=" * 70)
    print("DISTRIBUTION: multi-message nodes by type")
    print("=" * 70)
    type_counts = Counter(n["node_type"] for n in multi_nodes)
    for t, c in sorted(type_counts.items()):
        print(f"  {t}: {c}")

    # How many distinct campaigns have multi-message nodes?
    camp_ids = set(n["campaign_id"] for n in multi_nodes)
    print(f"\nCampaigns with at least one multi-message node: {len(camp_ids)} of {len(campaigns)}")

    # Check: do any of the recent campaigns (599020 area) have multi-message?
    print()
    print("=" * 70)
    print("CAMPAIGN 599020 specifically")
    print("=" * 70)
    for camp in campaigns:
        if str(camp.get("id")) == "599020":
            try:
                seq = heyreach.campaign_sequence(str(camp.get("id")))
                nodes, types, truncated = heyreach.walk_sequence(seq)
                for node in nodes:
                    payload = node.get("payload")
                    if isinstance(payload, dict):
                        msgs = payload.get("messages")
                        if isinstance(msgs, list) and len(msgs) > 0:
                            print(f"  type={node.get('nodeType')}, messages={len(msgs)}")
            except Exception as e:
                print(f"  Failed: {e}")
            break


if __name__ == "__main__":
    main()
