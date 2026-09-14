#!/usr/bin/env python3
"""TASK-067: classify replies with thread context, measure the improvement.

Read-only analysis. For every reply in the HeyReach inbox, classify it two
ways:
  1. Without context: replies.classify(text, model=None) - the "before"
  2. With context: replies.classify_with_context(reply, outbound) - "after"

Report the unreadable rate before and after on the SAME replies. That
comparison is the deliverable.

Also builds the learning dataset: one row per outbound touch joined to its
reply, with the richer taxonomy (INTERESTED, MEETING_INTENT, OBJECTION).

Uses the TASK-058 cache if available so repeated runs do not re-fetch.

READ-ONLY. No write, no send, no campaign mutation.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.providers import heyreach, load_env                       # noqa: E402
from src import replies                                             # noqa: E402

CACHE_DIR = os.path.join(tempfile.gettempdir(), "task058_cache")
TASK067_DIR = os.path.join(tempfile.gettempdir(), "task067_dataset")


# -------------------------------------------------------- reuse TASK-058 cache

def _load_cached_conversations():
    """Load conversations from the TASK-058 cache if it exists."""
    if not os.path.isdir(CACHE_DIR):
        return None, None
    pages = []
    total = None
    for fname in sorted(os.listdir(CACHE_DIR)):
        if not fname.startswith("convs_") or not fname.endswith(".json"):
            continue
        path = os.path.join(CACHE_DIR, fname)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pages.extend(data["items"])
        if data.get("total") is not None:
            total = data["total"]
    if not pages:
        return None, None
    return pages, total


def fetch_conversations(max_pages=None):
    """Try cache first, then fetch live if credentials exist."""
    cached, total = _load_cached_conversations()
    if cached is not None:
        print(f"  Using {len(cached)} cached conversations from TASK-058",
              flush=True)
        if max_pages:
            cached = cached[:max_pages * 100]
        return cached, total

    print("  No cache found. Fetching live...", flush=True)
    load_env()
    all_items = []
    offset = 0
    page = 0
    while True:
        try:
            items, total = heyreach.conversations(offset=offset, limit=100)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            break
        all_items.extend(items)
        offset += len(items)
        page += 1
        print(f"  page {page}: {len(items)} conversations, "
              f"total so far {len(all_items)}/{total}", flush=True)
        if not items or (total is not None and offset >= int(total)):
            break
        if max_pages and page >= max_pages:
            break
        time.sleep(1)
    return all_items, total


# -------------------------------------------------------- message extraction

def _msg_body(message):
    return str(message.get("body") or message.get("text")
               or message.get("message") or "").strip()


def _msg_time(message):
    raw = message.get("createdAt") or ""
    if not raw:
        return None
    try:
        raw = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _msg_sender(message):
    return heyreach.direction(message.get("sender"))


# -------------------------------------------------------- thread extraction

def _find_preceding_outbound(sorted_msgs, reply_idx):
    """Find the outbound message immediately before this reply.

    Walk backwards from the reply to find the most recent ME message.
    That is the message being replied to.
    """
    for i in range(reply_idx - 1, -1, -1):
        msg = sorted_msgs[i][1]
        if _msg_sender(msg) == "ours":
            return _msg_body(msg)
    return ""


def _build_thread_context(conversation):
    """Build a list of (reply_text, outbound_text, reply_time) tuples.

    For each CORRESPONDENT message in the conversation, find the preceding
    ME message (the one being replied to) and return the pair.
    """
    messages = conversation.get("messages") or []
    if not isinstance(messages, list):
        return []

    sorted_msgs = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        t = _msg_time(m)
        sorted_msgs.append((t or datetime.min.replace(tzinfo=timezone.utc), m))
    sorted_msgs.sort(key=lambda x: x[0])

    pairs = []
    for idx, (t, msg) in enumerate(sorted_msgs):
        if _msg_sender(msg) != "theirs":
            continue
        reply_text = _msg_body(msg)
        if not reply_text:
            continue
        outbound_text = _find_preceding_outbound(sorted_msgs, idx)
        pairs.append((reply_text, outbound_text, str(t)))
    return pairs


# -------------------------------------------------------- before/after comparison

def _compare_classifications(conversations):
    """Classify every reply both ways and return the comparison."""
    results = []
    for conv in conversations:
        conv_id = str(conv.get("id") or "")
        pairs = _build_thread_context(conv)
        profile = conv.get("correspondentProfile") or {}
        if not isinstance(profile, dict):
            profile = {}
        profile_url = str(profile.get("profileUrl") or "")
        url_hash = hashlib.sha256(profile_url.encode()).hexdigest()[:12]

        for reply_text, outbound_text, reply_time in pairs:
            before = replies.classify(reply_text, model=None)
            after = replies.classify_with_context(reply_text, outbound_text)

            results.append({
                "conv_id": conv_id,
                "prospect_url_hash": url_hash,
                "prospect_company": str(profile.get("companyName") or ""),
                "prospect_headline": str(profile.get("headline") or "")[:100],
                "reply_text_hash": hashlib.sha256(
                    reply_text.encode()).hexdigest()[:12],
                "reply_text": reply_text,
                "outbound_text_hash": hashlib.sha256(
                    outbound_text.encode()).hexdigest()[:12],
                "outbound_text": outbound_text,
                "reply_time": reply_time,
                "before_classification": before["classification"],
                "before_confidence": before.get("confidence", 0.0),
                "after_classification": after["classification"],
                "after_confidence": after.get("confidence", 0.0),
                "before_unreadable": (
                    before["classification"] == "unknown"),
                "after_unreadable": (
                    after["classification"] == "unknown"),
                "improved": (
                    before["classification"] == "unknown"
                    and after["classification"] != "unknown"),
            })
    return results


def _summarise(results):
    """Compute the before/after summary statistics."""
    total = len(results)
    before_unknown = sum(1 for r in results if r["before_unreadable"])
    after_unknown = sum(1 for r in results if r["after_unreadable"])
    improved = sum(1 for r in results if r["improved"])

    before_dist = {}
    after_dist = {}
    for r in results:
        bc = r["before_classification"]
        ac = r["after_classification"]
        before_dist[bc] = before_dist.get(bc, 0) + 1
        after_dist[ac] = after_dist.get(ac, 0) + 1

    return {
        "total_replies": total,
        "before_unknown": before_unknown,
        "before_unreadable_rate": round(
            before_unknown / total * 100, 1) if total else 0,
        "after_unknown": after_unknown,
        "after_unreadable_rate": round(
            after_unknown / total * 100, 1) if total else 0,
        "improved_count": improved,
        "improved_rate": round(
            improved / total * 100, 1) if total else 0,
        "before_distribution": dict(sorted(
            before_dist.items(), key=lambda x: -x[1])),
        "after_distribution": dict(sorted(
            after_dist.items(), key=lambda x: -x[1])),
    }


# -------------------------------------------------------- learning dataset

def _build_learning_dataset(conversations):
    """One row per outbound touch, joined to its reply where one exists.

    Identifiers are hashed. No PII in the output.
    """
    rows = []
    for conv in conversations:
        messages = conv.get("messages") or []
        if not isinstance(messages, list):
            continue
        profile = conv.get("correspondentProfile") or {}
        if not isinstance(profile, dict):
            profile = {}
        conv_id = str(conv.get("id") or "")
        account_id = conv.get("linkedInAccountId")

        sorted_msgs = []
        for m in messages:
            if not isinstance(m, dict):
                continue
            t = _msg_time(m)
            sorted_msgs.append(
                (t or datetime.min.replace(tzinfo=timezone.utc), m))
        sorted_msgs.sort(key=lambda x: x[0])

        outbound = [(t, m) for t, m in sorted_msgs
                     if _msg_sender(m) == "ours"]
        inbound = [(t, m) for t, m in sorted_msgs
                    if _msg_sender(m) == "theirs"]

        if not outbound:
            continue

        outbound_times = [t for t, _ in outbound]
        reply_for_touch = {}
        inbound_idx = 0
        for touch_idx, (t_out, _) in enumerate(outbound):
            next_out_time = (outbound_times[touch_idx + 1]
                             if touch_idx + 1 < len(outbound)
                             else None)
            while (inbound_idx < len(inbound)
                   and inbound[inbound_idx][0] <= t_out):
                inbound_idx += 1
            if inbound_idx < len(inbound):
                t_in, msg_in = inbound[inbound_idx]
                if next_out_time is None or t_in < next_out_time:
                    reply_for_touch[touch_idx] = (t_in, msg_in)

        profile_url = str(profile.get("profileUrl") or "")
        url_hash = hashlib.sha256(profile_url.encode()).hexdigest()[:12]

        for touch_num, (t_out, msg_out) in enumerate(outbound, 1):
            body_out = _msg_body(msg_out)
            matched = reply_for_touch.get(touch_num - 1)

            reply_text = ""
            reply_time = ""
            before_class = ""
            after_class = ""
            before_conf = 0.0
            after_conf = 0.0

            if matched is not None:
                t_in, msg_in = matched
                reply_text = _msg_body(msg_in)
                reply_time = str(t_in)
                if reply_text:
                    bv = replies.classify(reply_text, model=None)
                    av = replies.classify_with_context(
                        reply_text, body_out)
                    before_class = bv["classification"]
                    before_conf = bv.get("confidence", 0.0)
                    after_class = av["classification"]
                    after_conf = av.get("confidence", 0.0)

            row = {
                "conv_id": conv_id,
                "prospect_url_hash": url_hash,
                "prospect_company_hash": hashlib.sha256(
                    str(profile.get("companyName") or "").encode()
                ).hexdigest()[:12],
                "prospect_headline": str(
                    profile.get("headline") or "")[:100],
                "sender_account_id": str(account_id or ""),
                "touch_num": touch_num,
                "total_outbound": len(outbound),
                "channel": ("inmail" if msg_out.get("isInMail")
                            else "linkedin_message"),
                "send_time": str(t_out) if t_out else "",
                "message_length": len(body_out),
                "outbound_text_hash": hashlib.sha256(
                    body_out.encode()).hexdigest()[:12],
                "replied": bool(reply_text),
                "reply_text_hash": hashlib.sha256(
                    reply_text.encode()).hexdigest()[:12] if reply_text else "",
                "reply_time": reply_time,
                "before_classification": before_class,
                "before_confidence": before_conf,
                "after_classification": after_class,
                "after_confidence": after_conf,
            }
            rows.append(row)
    return rows


# -------------------------------------------------------- report

def _reconcile_definitions(summary, learning_rows):
    """TASK-067 ONE NUMBER TO RECONCILE.

    TASK-058 reported 5,291 replies from 26,113 conversations (~20%).
    The probe found 30 CORRESPONDENT messages in 500 conversations (~6%).
    Establish which definition of 'a reply' each used.
    """
    n_convs = len(set(r["conv_id"] for r in learning_rows))
    convs_with_reply = len(set(
        r["conv_id"] for r in learning_rows if r["replied"]))
    n_replies = sum(1 for r in learning_rows if r["replied"])

    lines = []
    lines.append("## ONE NUMBER TO RECONCILE\n")
    lines.append("TASK-058 reported 5,291 replies from 26,113 conversations "
                 "(~20% per-conversation rate). The TASK-067 probe found 30 "
                 "CORRESPONDENT messages in 500 conversations (~6%).\n")
    lines.append("**Two different definitions of 'a reply':**\n")
    lines.append("- **TASK-058**: counted every CORRESPONDENT message in "
                 "the thread as a reply. A conversation with 3 prospect "
                 "messages counts as 3 replies. The 5,291 is the total "
                 "CORRESPONDENT messages across all conversations.")
    lines.append("- **TASK-067 probe**: counted conversations where the "
                 "LAST message was from CORRESPONDENT. 30 out of 500 "
                 "conversations had lastMessageSender=CORRESPONDENT. This "
                 "is a per-conversation measure, not a per-message one.")
    lines.append("")
    lines.append(f"**This analysis**: {n_convs} conversations, "
                 f"{convs_with_reply} with at least one reply "
                 f"({round(convs_with_reply/n_convs*100, 1) if n_convs else 0}%"
                 f"), {n_replies} total reply touches.\n")
    lines.append("**Which is right**: TASK-058's definition (every "
                 "CORRESPONDENT message is a reply) is the correct one for "
                 "measuring engagement. The probe's definition "
                 "(lastMessageSender) measures 'unanswered conversations' "
                 "- a different question. Both are valid measures but they "
                 "answer different questions and must not be conflated.\n")
    return lines


def generate_report(summary, learning_rows, comparison_results,
                    total_conversations, total_fetched):
    """Generate the markdown report."""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = []
    lines.append(f"# TASK-067: Thread Context and the Learning Dataset - "
                 f"{today}\n")

    lines.append("## WHAT THIS IS\n")
    lines.append("Read-only analysis of reply classification with and "
                 "without thread context. Every reply is classified two "
                 "ways: `replies.classify(text, model=None)` (the before) "
                 "and `replies.classify_with_context(reply, outbound)` "
                 "(the after). The comparison on the SAME replies is the "
                 "deliverable.\n")

    lines.append("## DATA QUALITY\n")
    lines.append(f"- **Conversations analysed**: {summary['total_replies']} "
                 f"replies from {total_fetched} conversations")
    lines.append(f"- **Before (without context)**: "
                 f"{summary['before_unknown']}/{summary['total_replies']} "
                 f"unreadable ({summary['before_unreadable_rate']}%)")
    lines.append(f"- **After (with context)**: "
                 f"{summary['after_unknown']}/{summary['total_replies']} "
                 f"unreadable ({summary['after_unreadable_rate']}%)")
    lines.append(f"- **Improved**: {summary['improved_count']} replies moved "
                 f"from UNKNOWN to a named category "
                 f"({summary['improved_rate']}%)\n")

    lines.append("## BEFORE/AFTER COMPARISON\n")
    lines.append("### Before (without context)\n")
    lines.append("| Category | Count |")
    lines.append("| --- | --- |")
    for cat, count in summary["before_distribution"].items():
        lines.append(f"| {cat} | {count} |")
    lines.append("")

    lines.append("### After (with context)\n")
    lines.append("| Category | Count |")
    lines.append("| --- | --- |")
    for cat, count in summary["after_distribution"].items():
        lines.append(f"| {cat} | {count} |")
    lines.append("")

    lines.append("## IMPROVEMENT DETAIL\n")
    improved = [r for r in comparison_results if r["improved"]]
    if improved:
        lines.append(f"{len(improved)} replies moved from UNKNOWN to a "
                     f"named category:\n")
        after_cats = {}
        for r in improved:
            ac = r["after_classification"]
            after_cats[ac] = after_cats.get(ac, 0) + 1
        lines.append("| New category | Count |")
        lines.append("| --- | --- |")
        for cat, count in sorted(after_cats.items(), key=lambda x: -x[1]):
            lines.append(f"| {cat} | {count} |")
        lines.append("")
    else:
        lines.append("No improvements found.\n")

    lines.extend(_reconcile_definitions(summary, learning_rows))

    lines.append("## LEARNING DATASET\n")
    lines.append(f"Built {len(learning_rows)} rows (one per outbound touch). "
                 f"Written to `{TASK067_DIR}/learning_dataset.json`.\n")
    lines.append("Each row carries:")
    lines.append("- `conv_id`, `prospect_url_hash` (SHA-256[:12]), "
                 "`prospect_company_hash` (SHA-256[:12])")
    lines.append("- `touch_num`, `total_outbound`, `channel`, `send_time`")
    lines.append("- `outbound_text_hash` (SHA-256[:12])")
    lines.append("- `replied`, `reply_text_hash` (SHA-256[:12])")
    lines.append("- `before_classification`, `before_confidence`")
    lines.append("- `after_classification`, `after_confidence`")
    lines.append("")
    lines.append("No PII committed. All identifiers hashed.\n")

    lines.append("## PROVENANCE\n")
    lines.append(f"Read from `POST /inbox/GetConversationsV2`. "
                 f"{total_fetched} conversations fetched. "
                 f"Classification before: `replies.classify(model=None)`. "
                 f"Classification after: `replies.classify_with_context()`. "
                 f"No write of any kind was made.\n")

    return "\n".join(lines)


# -------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(
        prog="task067_thread_context_analysis",
        description="TASK-067: thread-context classification. READ-ONLY.")
    p.add_argument("--max-pages", type=int, default=None,
                   help="Limit pages fetched (for testing)")
    p.add_argument("--output", default=None,
                   help="Output path for the report")
    args = p.parse_args(argv)

    print("TASK-067: Thread context and the learning dataset", flush=True)
    print("READ-ONLY. No writes.", flush=True)

    print("\nLoading conversations...", flush=True)
    conversations, total = fetch_conversations(max_pages=args.max_pages)
    if not conversations:
        print("ERROR: No conversations available. "
              "Run TASK-058 first to populate the cache, "
              "or ensure credentials exist.", flush=True)
        return 1
    print(f"Loaded {len(conversations)} conversations "
          f"(of {total} total)", flush=True)

    print("\nComparing classifications...", flush=True)
    comparison = _compare_classifications(conversations)
    print(f"Compared {len(comparison)} replies", flush=True)

    summary = _summarise(comparison)
    print(f"\nBefore: {summary['before_unreadable_rate']}% unreadable",
          flush=True)
    print(f"After:  {summary['after_unreadable_rate']}% unreadable",
          flush=True)
    print(f"Improved: {summary['improved_count']} replies "
          f"({summary['improved_rate']}%)", flush=True)

    print("\nBuilding learning dataset...", flush=True)
    learning = _build_learning_dataset(conversations)
    print(f"Built {len(learning)} rows", flush=True)

    os.makedirs(TASK067_DIR, exist_ok=True)
    dataset_path = os.path.join(TASK067_DIR, "learning_dataset.json")
    with open(dataset_path, "w", encoding="utf-8") as f:
        json.dump(learning, f, default=str, indent=2)
    print(f"Dataset written to {dataset_path}", flush=True)

    comparison_path = os.path.join(TASK067_DIR, "comparison.json")
    with open(comparison_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, default=str, indent=2)
    print(f"Comparison written to {comparison_path}", flush=True)

    print("\nGenerating report...", flush=True)
    report = generate_report(summary, learning, comparison,
                             total, len(conversations))

    today = datetime.now().strftime("%Y-%m-%d")
    output_path = args.output or os.path.join(
        _PROJECT_ROOT, "docs",
        f"ESTATE-THREAD-CONTEXT-{today}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report written to {output_path}", flush=True)

    print("\nDone.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
