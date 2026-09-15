#!/usr/bin/env python3
"""TASK-121: Examine CONNECTION_REQUEST multi-message nodes and error campaigns."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import heyreach, load_env, request  # noqa: E402


def main():
    load_env()
    base, hdr = heyreach.BASE, heyreach.headers()

    # Campaign 429680 (OMEGA 2) has a CONNECTION_REQUEST with 15 messages
    print("=" * 72)
    print("CONNECTION_REQUEST with 15 messages - campaign 429680")
    print("=" * 72)
    seq = heyreach.campaign_sequence(429680)
    nodes, types, truncated = heyreach.walk_sequence(seq)
    for n in nodes:
        if n.get("nodeType") != "CONNECTION_REQUEST":
            continue
        payload = n.get("payload") or {}
        msgs = payload.get("messages") or []
        print("  nodeType: CONNECTION_REQUEST")
        print("  message_count: %d" % len(msgs))
        print("  payload_keys: %s" % sorted(payload.keys()))
        for i, m in enumerate(msgs):
            if isinstance(m, str):
                print("  [%d] len=%d: %s" % (i, len(m), m[:100]))
            elif isinstance(m, dict):
                print("  [%d] dict keys=%s: %s" % (i, sorted(m.keys()), str(m)[:100]))
            else:
                print("  [%d] %s" % (i, type(m).__name__))

    # Campaign 524026 has a CONNECTION_REQUEST with 5 messages
    print()
    print("=" * 72)
    print("CONNECTION_REQUEST with 5 messages - campaign 524026")
    print("=" * 72)
    seq = heyreach.campaign_sequence(524026)
    nodes, types, truncated = heyreach.walk_sequence(seq)
    for n in nodes:
        if n.get("nodeType") != "CONNECTION_REQUEST":
            continue
        payload = n.get("payload") or {}
        msgs = payload.get("messages") or []
        print("  nodeType: CONNECTION_REQUEST")
        print("  message_count: %d" % len(msgs))
        for i, m in enumerate(msgs):
            if isinstance(m, str):
                print("  [%d] len=%d: %s" % (i, len(m), m[:100]))

    # Error campaigns
    print()
    print("=" * 72)
    print("Error campaigns: 594060 and 594057")
    print("=" * 72)
    for cid in [594060, 594057]:
        try:
            seq = heyreach.campaign_sequence(cid)
            print("  campaign %s: type=%s" % (cid, type(seq).__name__))
            if isinstance(seq, dict):
                print("    keys: %s" % sorted(seq.keys())[:10])
            else:
                print("    value: %s" % str(seq)[:200])
        except Exception as exc:
            print("  campaign %s: ERROR %s" % (cid, exc))

    # Check: does the campaign list endpoint carry any selection/rotation config?
    print()
    print("=" * 72)
    print("Campaign-level config check (campaign 428676 - 20 messages)")
    print("=" * 72)
    st, data = request("POST", base + "/campaign/GetAll", hdr, {"offset": 0, "limit": 100})
    for c in (data.get("items") or []):
        if c.get("id") == 428676:
            # Print all top-level keys
            for k in sorted(c.keys()):
                v = c[k]
                if isinstance(v, (str, int, float, bool, type(None))):
                    print("  %s: %s" % (k, v))
                elif isinstance(v, list) and len(v) < 5:
                    print("  %s: %s" % (k, v))
                elif isinstance(v, dict):
                    print("  %s: {dict with %d keys}" % (k, len(v)))
                elif isinstance(v, list):
                    print("  %s: [list with %d items]" % (k, len(v)))
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
