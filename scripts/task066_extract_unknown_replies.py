#!/usr/bin/env python3
"""TASK-066: Extract actual reply texts for unknown-classified replies.

Reads the cached HeyReach conversations from TASK-058 and rebuilds the
touch-to-reply mapping to extract the actual text of replies that were
classified as unknown.

READS ONLY. No provider calls.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.providers import heyreach  # noqa: E402
from src import replies  # noqa: E402

CACHE_DIR = os.path.join(tempfile.gettempdir(), "task058_cache")
DATASET_PATH = os.path.join(tempfile.gettempdir(), "task058_dataset.json")
OUTPUT_PATH = os.path.join(tempfile.gettempdir(), "task066_unknown_replies.json")


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


def _load_cached_conversations():
    """Load all cached conversations."""
    convs = []
    page = 0
    while True:
        p = os.path.join(CACHE_DIR, f"convs_{page:05d}.json")
        if not os.path.exists(p):
            break
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        convs.extend(data["items"])
        page += 1
    return convs


def _extract_replies(conversations):
    """Extract all reply texts with their classifications."""
    results = []
    for conv in conversations:
        messages = conv.get("messages") or []
        if not isinstance(messages, list):
            continue

        sorted_msgs = []
        for m in messages:
            if not isinstance(m, dict):
                continue
            t = _msg_time(m)
            sorted_msgs.append((t or datetime.min.replace(tzinfo=timezone.utc), m))
        sorted_msgs.sort(key=lambda x: x[0])

        outbound = [(t, m) for t, m in sorted_msgs if _msg_sender(m) == "ours"]
        inbound = [(t, m) for t, m in sorted_msgs if _msg_sender(m) == "theirs"]

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

        for touch_num, (t_out, msg_out) in enumerate(outbound, 1):
            matched = reply_for_touch.get(touch_num - 1)
            if matched is None:
                continue
            t_in, msg_in = matched
            reply_text = _msg_body(msg_in)
            if not reply_text:
                continue

            result = replies.classify(reply_text, model=None)
            classification = result.get("classification", "unknown")

            results.append({
                "conv_id": str(conv.get("id")),
                "touch_num": touch_num,
                "reply_text": reply_text,
                "reply_length": len(reply_text),
                "classification": classification,
                "confidence": result.get("confidence", 0.0),
                "reason": result.get("reason", ""),
                "extract_method": result.get("extract_method", ""),
            })

    return results


def main():
    print("Loading cached conversations...")
    convs = _load_cached_conversations()
    print(f"Loaded {len(convs)} conversations")

    print("Extracting replies...")
    all_replies = _extract_replies(convs)
    print(f"Found {len(all_replies)} replies total")

    # Filter to unknown only
    unknown_replies = [r for r in all_replies if r["classification"] == "unknown"]
    print(f"Unknown replies: {len(unknown_replies)}")

    # Save all replies (for re-measurement later)
    all_path = os.path.join(tempfile.gettempdir(), "task066_all_replies.json")
    with open(all_path, "w", encoding="utf-8") as f:
        json.dump(all_replies, f, ensure_ascii=False, indent=1)
    print(f"Saved all replies to {all_path}")

    # Save unknown replies
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(unknown_replies, f, ensure_ascii=False, indent=1)
    print(f"Saved unknown replies to {OUTPUT_PATH}")

    # Print length distribution of unknown replies
    lengths = [r["reply_length"] for r in unknown_replies]
    if lengths:
        lengths.sort()
        print(f"\nUnknown reply length distribution:")
        print(f"  min: {min(lengths)}")
        print(f"  p25: {lengths[len(lengths)//4]}")
        print(f"  median: {lengths[len(lengths)//2]}")
        print(f"  p75: {lengths[3*len(lengths)//4]}")
        print(f"  max: {max(lengths)}")

    # Print first 50 samples
    print(f"\nFirst 50 unknown replies (sorted by length):")
    sorted_unknown = sorted(unknown_replies, key=lambda r: r["reply_length"])
    for i, r in enumerate(sorted_unknown[:50]):
        text = r["reply_text"][:120].replace("\n", " ")
        print(f"  [{r['reply_length']:3d}] {text}")


if __name__ == "__main__":
    main()
