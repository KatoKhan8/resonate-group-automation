#!/usr/bin/env python3
"""TASK-121: inspect the structure of a multi-message node to understand
if there's any rotation/selection configuration.

Reads one campaign with multi-message nodes and dumps the full payload
structure of a MESSAGE node with multiple messages.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers import heyreach


def main():
    # Campaign 523993 has 20, 14, 19 messages - among the highest
    # Campaign 567758 has 4, 3, 3 - a typical one
    # Let's look at a medium one first: 567758
    campaign_id = 567758
    print(f"=== Campaign {campaign_id} ===")
    seq = heyreach.campaign_sequence(campaign_id)
    nodes, types, truncated = heyreach.walk_sequence(seq)
    print(f"Node types: {sorted(types)}")
    print(f"Truncated: {truncated}")
    print()

    for i, node in enumerate(nodes):
        nt = node.get("nodeType")
        payload = node.get("payload") or {}
        messages = payload.get("messages") if isinstance(payload, dict) else None
        if isinstance(messages, list) and len(messages) > 1:
            print(f"--- Node {i}: {nt}, {len(messages)} messages ---")
            # Show all keys at the node level
            node_keys = sorted(node.keys())
            print(f"Node-level keys: {node_keys}")
            # Show payload keys
            if isinstance(payload, dict):
                print(f"Payload keys: {sorted(payload.keys())}")
            # Show first message structure
            for j, msg in enumerate(messages):
                if isinstance(msg, dict):
                    print(f"  Message {j} keys: {sorted(msg.keys())}")
                    # Show a truncated version of each message
                    preview = {}
                    for k, v in msg.items():
                        if isinstance(v, str) and len(v) > 80:
                            preview[k] = v[:80] + "..."
                        else:
                            preview[k] = v
                    print(f"  Message {j}: {json.dumps(preview, ensure_ascii=False)}")
                else:
                    print(f"  Message {j}: {type(msg).__name__} = {str(msg)[:100]}")
            print()

    # Now look at one of the biggest: 523993 (20 messages)
    print("\n\n=== Campaign 523993 (20-message node) ===")
    campaign_id = 523993
    seq = heyreach.campaign_sequence(campaign_id)
    nodes, types, truncated = heyreach.walk_sequence(seq)
    for i, node in enumerate(nodes):
        nt = node.get("nodeType")
        payload = node.get("payload") or {}
        messages = payload.get("messages") if isinstance(payload, dict) else None
        if isinstance(messages, list) and len(messages) > 10:
            print(f"--- Node {i}: {nt}, {len(messages)} messages ---")
            node_keys = sorted(node.keys())
            print(f"Node-level keys: {node_keys}")
            if isinstance(payload, dict):
                payload_keys = sorted(payload.keys())
                print(f"Payload keys: {payload_keys}")
                # Check for any rotation/selection config keys
                for pk in payload_keys:
                    if pk != "messages":
                        v = payload[pk]
                        if isinstance(v, str) and len(v) > 200:
                            print(f"  payload.{pk} = {v[:200]}...")
                        else:
                            print(f"  payload.{pk} = {v}")
            # Show first 3 messages briefly
            for j, msg in enumerate(messages[:3]):
                if isinstance(msg, dict):
                    print(f"  Message {j} keys: {sorted(msg.keys())}")
                    for k, v in msg.items():
                        if isinstance(v, str) and len(v) > 100:
                            print(f"    {k}: {v[:100]}...")
                        else:
                            print(f"    {k}: {v}")
            print(f"  ... and {len(messages)-3} more messages")
            print()


if __name__ == "__main__":
    main()
