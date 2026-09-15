#!/usr/bin/env python3
"""TASK-121: Does any node in any campaign carry more than one message?

Reads-only. Walks every campaign in the HeyReach account, gets its sequence
graph, walks the graph, and counts payload.messages on every node.

The question is whether the provider has ever been given a multi-message node
by any of the 83 campaigns built here since April - not just the one we built.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import heyreach, load_env, request  # noqa: E402


def all_campaigns(base, hdr):
    """Every campaign in the account, paginated."""
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


def analyse_campaign(base, hdr, campaign_id, campaign_name, campaign_status):
    """Walk one campaign's sequence graph. Return a summary dict."""
    try:
        seq = heyreach.campaign_sequence(campaign_id)
    except Exception as exc:
        return {
            "campaign_id": campaign_id,
            "name": campaign_name,
            "status": campaign_status,
            "error": "sequence fetch failed: %s" % str(exc)[:200],
        }
    if not seq or not isinstance(seq, dict):
        return {
            "campaign_id": campaign_id,
            "name": campaign_name,
            "status": campaign_status,
            "error": "empty or non-dict sequence",
        }

    nodes, types, truncated = heyreach.walk_sequence(seq)
    max_msgs = 0
    multi_message_nodes = []
    total_nodes_with_copy = 0
    msg_counts = []

    for n in nodes:
        payload = n.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        msgs = payload.get("messages")
        msgs = msgs if isinstance(msgs, list) else []
        count = len(msgs)
        if count > 0:
            total_nodes_with_copy += 1
            msg_counts.append(count)
        if count > max_msgs:
            max_msgs = count
        if count > 1:
            multi_message_nodes.append({
                "nodeType": n.get("nodeType"),
                "message_count": count,
            })

    return {
        "campaign_id": campaign_id,
        "name": campaign_name,
        "status": campaign_status,
        "total_nodes": len(nodes),
        "node_types": {t: sum(1 for n in nodes if n.get("nodeType") == t)
                       for t in sorted(types)},
        "truncated": truncated,
        "nodes_carrying_copy": total_nodes_with_copy,
        "max_messages_on_any_node": max_msgs,
        "message_count_distribution": sorted(msg_counts),
        "multi_message_nodes": multi_message_nodes,
    }


def main():
    load_env()
    base, hdr = heyreach.BASE, heyreach.headers()

    st, _ = request("GET", base + "/auth/CheckApiKey", hdr)
    if st != 200:
        print("HeyReach credential rejected: HTTP %s" % st)
        return 2

    campaigns, total = all_campaigns(base, hdr)
    print("Account campaigns total: %d" % total)
    print("Fetched: %d" % len(campaigns))
    print()

    any_multi = False
    results = []
    errors = []

    for i, c in enumerate(campaigns):
        cid = c.get("id")
        cname = c.get("name") or "(unnamed)"
        cstatus = c.get("status") or "?"
        sys.stdout.write("\r  walking %d/%d: %s" % (i + 1, len(campaigns), cname[:50]))
        sys.stdout.flush()
        r = analyse_campaign(base, hdr, cid, cname, cstatus)
        if "error" in r:
            errors.append(r)
        else:
            results.append(r)
            if r["multi_message_nodes"]:
                any_multi = True

    print()
    print()
    print("=" * 72)
    print("RESULT: %s" % ("MULTI-MESSAGE NODES FOUND" if any_multi
                          else "NO MULTI-MESSAGE NODE IN ANY CAMPAIGN"))
    print("=" * 72)
    print()

    # Summary statistics
    campaigns_walked = len(results)
    campaigns_with_errors = len(errors)
    campaigns_with_copy = sum(1 for r in results if r["nodes_carrying_copy"] > 0)
    all_max = max((r["max_messages_on_any_node"] for r in results), default=0)
    truncated_count = sum(1 for r in results if r["truncated"])

    print("Campaigns walked:          %d" % campaigns_walked)
    print("Campaigns with errors:     %d" % campaigns_with_errors)
    print("Campaigns with any copy:   %d" % campaigns_with_copy)
    print("Truncated graphs:          %d" % truncated_count)
    print("Max messages on any node:  %d" % all_max)
    print()

    if any_multi:
        print("MULTI-MESSAGE NODES:")
        for r in results:
            for mn in r["multi_message_nodes"]:
                print("  campaign=%s (%s) nodeType=%s messages=%d" % (
                    r["campaign_id"], r["name"][:40],
                    mn["nodeType"], mn["message_count"]))
    else:
        # Show the distribution of message counts across all copy-bearing nodes
        all_counts = []
        for r in results:
            all_counts.extend(r["message_count_distribution"])
        from collections import Counter
        dist = Counter(all_counts)
        print("Message-count distribution across all copy-bearing nodes:")
        for count in sorted(dist.keys()):
            print("  %d message(s): %d node(s)" % (count, dist[count]))

    if errors:
        print()
        print("ERRORS:")
        for e in errors:
            print("  campaign=%s (%s): %s" % (
                e["campaign_id"], e["name"][:40], e["error"]))

    # Write full results to a temp file for reference
    out_dir = os.path.join(ROOT, ".qwen", "tmp", "task121")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_campaigns": total,
            "walked": campaigns_walked,
            "errors": campaigns_with_errors,
            "any_multi_message_node": any_multi,
            "max_messages_on_any_node": all_max,
            "truncated_graphs": truncated_count,
            "campaigns": results,
            "error_details": errors,
        }, f, indent=2, ensure_ascii=False)
    print()
    print("Full results: %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
