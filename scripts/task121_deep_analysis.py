#!/usr/bin/env python3
"""TASK-121 deep analysis: what do multi-message nodes actually contain?

For a representative sample of multi-message nodes, examine the structure
of each message entry to determine whether they are:
- A/B variants (same intent, different wording)
- Sequential messages (step 1, step 2, etc.)
- Something else

Also check: does the node have any selection/rotation config?
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import heyreach, load_env, request  # noqa: E402


def all_campaigns(base, hdr):
    out, off, total = [], 0, None
    while True:
        st, data = request("POST", base + "/campaign/GetAll", hdr,
                           {"offset": off, "limit": 100})
        if st != 200:
            raise RuntimeError("GetAll failed: %s %s" % (st, str(data)[:200]))
        items = data.get("items") or []
        out.extend(items)
        total = data.get("totalCount")
        off += len(items)
        if not items or off >= (total or 0):
            break
    return out, total


def examine_node(node):
    """Extract everything interesting from a multi-message node."""
    payload = node.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    msgs = payload.get("messages")
    msgs = msgs if isinstance(msgs, list) else []

    result = {
        "nodeType": node.get("nodeType"),
        "message_count": len(msgs),
        "payload_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
        "messages": [],
    }

    for i, m in enumerate(msgs):
        entry = {"index": i}
        if isinstance(m, str):
            entry["type"] = "string"
            entry["length"] = len(m)
            entry["preview"] = m[:120]
        elif isinstance(m, dict):
            entry["type"] = "dict"
            entry["keys"] = sorted(m.keys())
            # For INMAIL nodes, messages are dicts with subject+body
            if "subject" in m:
                entry["subject"] = m.get("subject", "")[:80]
            if "message" in m:
                entry["body_length"] = len(m.get("message", ""))
                entry["body_preview"] = m.get("message", "")[:120]
            elif "body" in m:
                entry["body_length"] = len(m.get("body", ""))
                entry["body_preview"] = m.get("body", "")[:120]
        else:
            entry["type"] = type(m).__name__
        result["messages"].append(entry)

    # Check for any rotation/selection config at the node level
    for key in ("messageSelection", "selectionType", "rotationType",
                "messageRotation", "variantType", "abTest", "randomize",
                "selectionMode"):
        if key in node:
            result[key] = node[key]
        if key in payload:
            result["payload." + key] = payload[key]

    return result


def main():
    load_env()
    base, hdr = heyreach.BASE, heyreach.headers()

    st, _ = request("GET", base + "/auth/CheckApiKey", hdr)
    if st != 200:
        print("HeyReach credential rejected: HTTP %s" % st)
        return 2

    campaigns, total = all_campaigns(base, hdr)

    # Pick representative campaigns: a few from different eras
    # that have multi-message nodes
    target_ids = set()

    # The "CONNECTIONS" cluster (567xxx) - 3-4 messages per node
    # The "FIXED" cluster (523xxx-524xxx) - up to 20 messages
    # The oldest (OMEGA, 429xxx) - up to 19 messages
    # The "INTERESTED/MAYBE" (583xxx) - 2 messages
    # Our own campaign (599020) - 1 message per node (control)

    sample_ids = [
        583549,   # INTERESTED - Bison - 2 messages
        567758,   # ANA L CONNECTIONS - 3-4 messages
        524002,   # FIXED - 11 messages
        523993,   # FIXED - 20 messages (max)
        523987,   # FIXED OMEGA - 17 messages
        429680,   # OMEGA 2 - 15 messages on CONNECTION_REQUEST
        428676,   # PRODUCTIVE ALL LEADS - 20 messages
        388960,   # USA 2ND CLEANED - 18 messages
    ]

    for cid in sample_ids:
        print("=" * 72)
        print("CAMPAIGN %s" % cid)
        print("=" * 72)
        try:
            seq = heyreach.campaign_sequence(cid)
        except Exception as exc:
            print("  ERROR: %s" % exc)
            continue

        if not seq:
            print("  empty sequence")
            continue

        nodes, types, truncated = heyreach.walk_sequence(seq)
        print("  nodes=%d types=%s truncated=%s" % (len(nodes), sorted(types), truncated))

        multi_nodes = []
        for n in nodes:
            payload = n.get("payload")
            payload = payload if isinstance(payload, dict) else {}
            msgs = payload.get("messages")
            msgs = msgs if isinstance(msgs, list) else []
            if len(msgs) > 1:
                multi_nodes.append(n)

        if not multi_nodes:
            print("  no multi-message nodes")
            continue

        # Show the node with the most messages
        biggest = max(multi_nodes, key=lambda n: len((n.get("payload") or {}).get("messages") or []))
        examined = examine_node(biggest)
        print()
        print("  LARGEST multi-message node:")
        print("    nodeType: %s" % examined["nodeType"])
        print("    message_count: %d" % examined["message_count"])
        print("    payload_keys: %s" % examined["payload_keys"])

        # Show selection/rotation config if any
        for key in examined:
            if key not in ("nodeType", "message_count", "payload_keys", "messages"):
                print("    %s: %s" % (key, examined[key]))

        print()
        print("    Messages:")
        for m in examined["messages"]:
            if m["type"] == "string":
                print("      [%d] string len=%d: %s" % (m["index"], m["length"], m["preview"][:80]))
            elif m["type"] == "dict":
                subj = m.get("subject", "")
                preview = m.get("body_preview", "")[:80]
                print("      [%d] dict keys=%s subj=%s body_len=%s: %s" % (
                    m["index"], m.get("keys"), subj, m.get("body_length"), preview))
            else:
                print("      [%d] %s" % (m["index"], m["type"]))

        # Also show a smaller multi-message node from the same campaign for comparison
        if len(multi_nodes) > 1:
            smallest = min(multi_nodes, key=lambda n: len((n.get("payload") or {}).get("messages") or []))
            s_msgs = len((smallest.get("payload") or {}).get("messages") or [])
            b_msgs = len((biggest.get("payload") or {}).get("messages") or [])
            if s_msgs != b_msgs:
                examined_s = examine_node(smallest)
                print()
                print("  SMALLEST multi-message node (for comparison):")
                print("    nodeType: %s" % examined_s["nodeType"])
                print("    message_count: %d" % examined_s["message_count"])
                for m in examined_s["messages"]:
                    if m["type"] == "string":
                        print("      [%d] string len=%d: %s" % (m["index"], m["length"], m["preview"][:80]))
                    elif m["type"] == "dict":
                        subj = m.get("subject", "")
                        preview = m.get("body_preview", "")[:80]
                        print("      [%d] dict keys=%s subj=%s body_len=%s: %s" % (
                            m["index"], m.get("keys"), subj, m.get("body_length"), preview))

        print()

    # Now: a statistical summary across all campaigns
    print()
    print("=" * 72)
    print("STATISTICAL SUMMARY")
    print("=" * 72)

    node_type_multi = {}  # nodeType -> count of multi-message nodes
    node_type_max = {}    # nodeType -> max messages seen
    campaigns_with_multi = set()
    total_multi_nodes = 0

    for c in campaigns:
        cid = c.get("id")
        try:
            seq = heyreach.campaign_sequence(cid)
        except Exception:
            continue
        if not seq:
            continue
        nodes, types, truncated = heyreach.walk_sequence(seq)
        for n in nodes:
            payload = n.get("payload")
            payload = payload if isinstance(payload, dict) else {}
            msgs = payload.get("messages")
            msgs = msgs if isinstance(msgs, list) else []
            nt = n.get("nodeType", "?")
            if len(msgs) > 1:
                total_multi_nodes += 1
                campaigns_with_multi.add(cid)
                node_type_multi[nt] = node_type_multi.get(nt, 0) + 1
                node_type_max[nt] = max(node_type_max.get(nt, 0), len(msgs))

    print("Campaigns with multi-message nodes: %d / %d" % (len(campaigns_with_multi), len(campaigns)))
    print("Total multi-message nodes across estate: %d" % total_multi_nodes)
    print()
    print("By node type:")
    for nt in sorted(node_type_multi.keys()):
        print("  %s: %d nodes, max %d messages" % (nt, node_type_multi[nt], node_type_max[nt]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
