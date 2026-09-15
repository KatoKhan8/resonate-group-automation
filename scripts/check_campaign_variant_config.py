#!/usr/bin/env python3
"""Check if campaigns carry any variant-selection configuration.

TASK-121 follow-up: is there a campaign-level or node-level setting that
controls how multiple messages are chosen?
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.providers import load_env, heyreach


def main():
    load_env()

    # Pick a campaign with many variants
    target_ids = ["523993", "523932", "429680", "388960"]

    for tid in target_ids:
        print(f"{'=' * 70}")
        print(f"Campaign {tid}")
        print(f"{'=' * 70}")

        # Get the campaign itself (top-level fields)
        camp = heyreach.campaign_by_id(tid)
        if camp:
            # Print all top-level keys except sequence
            for k, v in sorted(camp.items()):
                if k in ("sequence", "sequenceId"):
                    continue
                if isinstance(v, (dict, list)):
                    print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:200]}")
                else:
                    print(f"  {k}: {v}")

        # Get the sequence root
        try:
            seq = heyreach.campaign_sequence(tid)
        except Exception as e:
            print(f"  Sequence fetch failed: {e}")
            print()
            continue

        # Print root-level keys (not node-level)
        print(f"\n  Sequence root keys:")
        for k, v in sorted(seq.items()):
            if isinstance(v, (dict, list)):
                val_str = json.dumps(v, ensure_ascii=False)
                print(f"    {k}: {val_str[:200]}")
            else:
                print(f"    {k}: {v}")

        # Find the first multi-message node and show its full structure
        nodes, types, truncated = heyreach.walk_sequence(seq)
        for node in nodes:
            payload = node.get("payload")
            if isinstance(payload, dict):
                msgs = payload.get("messages")
                if isinstance(msgs, list) and len(msgs) > 1:
                    print(f"\n  First multi-message node:")
                    print(f"    nodeType: {node.get('nodeType')}")
                    print(f"    actionDelay: {node.get('actionDelay')} {node.get('actionDelayUnit')}")
                    # Show all payload keys
                    print(f"    payload keys: {sorted(payload.keys())}")
                    # Show all node keys
                    print(f"    node keys: {sorted(node.keys())}")
                    # Show message count and first 80 chars of each
                    for i, m in enumerate(msgs):
                        if isinstance(m, str):
                            print(f"    msg[{i}]: {m[:80]!r}")
                        elif isinstance(m, dict):
                            print(f"    msg[{i}]: {json.dumps(m, ensure_ascii=False)[:120]}")
                    break
        print()


if __name__ == "__main__":
    main()
