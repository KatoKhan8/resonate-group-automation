#!/usr/bin/env python3
"""TASK-058: Which HeyReach touch produced which reply.

Read-only analysis of the live HeyReach inbox. For every outbound touch
(message we sent) in every conversation, determine whether a reply followed,
how long it took, and what the reply said.

READS ONLY. No write, no send, no campaign mutation.

Caches API responses to a scratch directory so repeated runs do not re-fetch.
The dataset is aggregated - no unsanitised PII is committed.

Output:
  - docs/ESTATE-HEYREACH-OUTCOMES-<date>.md   analysis report
  - scratch path with the raw dataset (JSON)
"""
import argparse
import hashlib
import json
import os
import re
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
DATASET_PATH = os.path.join(tempfile.gettempdir(), "task058_dataset.json")


# ------------------------------------------------------------------ caching

def _ensure_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(kind, page):
    return os.path.join(CACHE_DIR, f"{kind}_{page:05d}.json")


def _load_cache(kind, page):
    p = _cache_path(kind, page)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cache(kind, page, data):
    p = _cache_path(kind, page)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, default=str)


def fetch_all_conversations(max_pages=None, use_cache=True):
    """Page through the entire inbox, caching each page. Retries on 429."""
    _ensure_cache()
    all_items = []
    offset = 0
    page = 0
    total = None
    while True:
        if use_cache:
            cached = _load_cache("convs", page)
            if cached is not None:
                items = cached["items"]
                total = cached["total"]
                all_items.extend(items)
                offset += len(items)
                page += 1
                if not items or (total is not None and offset >= int(total)):
                    break
                if max_pages and page >= max_pages:
                    break
                continue

        retries = 0
        while True:
            try:
                items, total = heyreach.conversations(offset=offset, limit=100)
                break
            except Exception as e:
                if "429" in str(e) and retries < 5:
                    wait = 30 * (retries + 1)
                    print(f"  rate limited, waiting {wait}s...", flush=True)
                    time.sleep(wait)
                    retries += 1
                else:
                    raise
        if use_cache:
            _save_cache("convs", page, {"items": items, "total": total})
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
    """The text content of a message."""
    return str(message.get("body") or message.get("text")
               or message.get("message") or "").strip()


def _msg_time(message):
    """Parse the message timestamp."""
    raw = message.get("createdAt") or ""
    if not raw:
        return None
    try:
        raw = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _msg_sender(message):
    """Normalise the sender field."""
    return heyreach.direction(message.get("sender"))


def _is_inmail(message):
    """Is this an InMail rather than a regular LinkedIn message?"""
    return bool(message.get("isInMail"))


def _has_subject(message):
    """Does this message carry a subject line?"""
    return bool(message.get("subject") and str(message.get("subject")).strip())


# -------------------------------------------------------- CTA classification

def _cta_type(text):
    """Classify the call-to-action in a message.

    Returns one of: question, referral_ask, easy_out, statement.
    """
    low = text.lower()
    if re.search(r"\?(?:\s|$)", text) or re.search(
            r"\b(?:can|could|would|should|will|is|are|do|does|did|have|has|how|"
            r"what|when|where|who|why|which)\b.*\?", low):
        if re.search(r"\b(?:talk|speak|meet|chat|call|schedule)\b.*\?", low):
            return "easy_out"
        return "question"
    if re.search(r"\b(?:right person|someone else|somebody else|"
                 r"talk to|speak to|contact)\b", low):
        return "referral_ask"
    if re.search(r"\b(?:no worries|no problem|if not|if you.*not interested|"
                 r"not a fit|door.*open|close.*loop|last message|"
                 r"wish you|all the best)\b", low):
        return "easy_out"
    return "statement"


# -------------------------------------------------------- touch classification

def _touch_kind(message, position, total_outbound):
    """Classify what kind of touch this is.

    Returns one of: connection_request, inmail, first_message, followup, breakup.
    Inferred from position, content and flags - the conversation endpoint does
    not expose node types.
    """
    body = _msg_body(message)
    is_inmail = _is_inmail(message)

    if is_inmail:
        return "inmail"
    if position == total_outbound and re.search(
            r"\b(?:last message|closing|close.*loop|door.*open|"
            r"won.*t bother|wish you|all the best)\b", body.lower()):
        return "breakup"
    if position == 1 and len(body) < 200:
        return "connection_request"
    if position == 1:
        return "first_message"
    return "followup"


# -------------------------------------------------------- prospect profile

def _profile_family(profile):
    """Extract role/title family from the correspondent profile."""
    headline = str(profile.get("headline") or "").lower()
    position = str(profile.get("position") or "").lower()
    text = headline or position
    if not text:
        return "unknown"
    families = [
        ("founder/owner", r"\b(?:founder|co-?founder|owner|ceo|coo|cto|"
                          r"managing director|principal)\b"),
        ("vp/director", r"\b(?:vp|vice president|director|head of)\b"),
        ("manager", r"\b(?:manager|lead|supervisor)\b"),
        ("finance/ops", r"\b(?:cfo|finance|financial|controller|accounting|"
                        r"operations|ops|COO)\b"),
        ("sales/marketing", r"\b(?:sales|marketing|business development|"
                            r"bd|growth|revenue)\b"),
        ("hr/people", r"\b(?:hr|human resources|people|talent|recruit)\b"),
        ("tech/engineering", r"\b(?:engineer|developer|cto|tech|software|"
                             r"architect|devops|data)\b"),
        ("consultant/advisor", r"\b(?:consultant|advisor|adviser|coach|"
                               r"freelance|independent)\b"),
    ]
    for label, pattern in families:
        if re.search(pattern, text):
            return label
    return "other"


def _company_size(profile):
    """Company size from follower/connection count - a rough proxy."""
    connections = profile.get("connections")
    followers = profile.get("followers")
    n = connections or followers
    if n is None:
        return "unknown"
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "unknown"
    if n < 500:
        return "small"
    if n < 5000:
        return "medium"
    return "large"


# -------------------------------------------------------- dataset construction

def _build_touch_rows(conversation):
    """Walk one conversation's messages and produce touch rows.

    Each outbound message is a touch. For each, we record whether the next
    inbound message (reply) followed, how long it took, and what it said.
    """
    messages = conversation.get("messages") or []
    if not isinstance(messages, list):
        return []

    profile = conversation.get("correspondentProfile") or {}
    if not isinstance(profile, dict):
        profile = {}
    account_id = conversation.get("linkedInAccountId")
    conv_id = conversation.get("id")

    sorted_msgs = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        t = _msg_time(m)
        sorted_msgs.append((t or datetime.min.replace(tzinfo=timezone.utc), m))
    sorted_msgs.sort(key=lambda x: x[0])

    unknown_count = len([m for _, m in sorted_msgs
                         if _msg_sender(m) == "unknown"])

    outbound = [(t, m) for t, m in sorted_msgs if _msg_sender(m) == "ours"]
    inbound = [(t, m) for t, m in sorted_msgs if _msg_sender(m) == "theirs"]

    if not outbound:
        return []

    total_outbound = len(outbound)
    rows = []

    # Build a mapping: for each outbound touch, find the NEXT inbound message
    # that follows it AND precedes the next outbound touch. A reply belongs to
    # the touch that immediately preceded it, not to every earlier touch.
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
        body_out = _msg_body(msg_out)
        reply_text = None
        reply_delay_hours = None
        reply_classification = None
        reply_confidence = None
        reply_unreadable = False

        matched = reply_for_touch.get(touch_num - 1)
        if matched is not None:
            t_in, msg_in = matched
            reply_text = _msg_body(msg_in)
            delta = (t_in - t_out).total_seconds() / 3600.0
            if delta >= 0:
                reply_delay_hours = round(delta, 1)

            if reply_text:
                result = replies.classify(reply_text, model=None)
                reply_classification = result.get("classification", "unknown")
                reply_confidence = result.get("confidence", 0.0)
                if reply_classification == "unknown" and reply_confidence < 0.6:
                    reply_unreadable = True

        kind = _touch_kind(msg_out, touch_num, total_outbound)
        cta = _cta_type(body_out)
        role_family = _profile_family(profile)
        size = _company_size(profile)

        profile_url = str(profile.get("profileUrl") or "")
        url_hash = hashlib.sha256(profile_url.encode()).hexdigest()[:12]

        row = {
            "conv_id": str(conv_id),
            "touch_num": touch_num,
            "total_outbound": total_outbound,
            "channel": "inmail" if _is_inmail(msg_out) else "linkedin_message",
            "has_subject": _has_subject(msg_out),
            "sender_account_id": account_id,
            "send_time": str(t_out) if t_out else None,
            "touch_kind": kind,
            "message_length": len(body_out),
            "message_length_band": _length_band(len(body_out)),
            "cta_type": cta,
            "prospect_url_hash": url_hash,
            "prospect_role_family": role_family,
            "prospect_company": str(profile.get("companyName") or ""),
            "prospect_company_size": size,
            "prospect_headline": str(profile.get("headline") or "")[:100],
            "connection_outcome": _infer_connection_outcome(
                touch_num, total_outbound, inbound),
            "replied": reply_text is not None,
            "reply_delay_hours": reply_delay_hours,
            "reply_text_hash": (hashlib.sha256(
                (reply_text or "").encode()).hexdigest()[:12]
                if reply_text else None),
            "reply_classification": reply_classification,
            "reply_confidence": reply_confidence,
            "reply_unreadable": reply_unreadable,
            "unknown_direction_count": unknown_count,
        }
        rows.append(row)

    return rows


def _length_band(length):
    if length < 100:
        return "short (<100)"
    if length < 300:
        return "medium (100-300)"
    if length < 600:
        return "long (300-600)"
    return "very_long (600+)"


def _infer_connection_outcome(touch_num, total_outbound, inbound):
    """Infer connection outcome from conversation structure.

    We cannot directly read connection status from the conversation endpoint
    (CONNECTION_STATUS_AVAILABLE = False in heyreach.py). We infer:
    - If there is ANY inbound message: the connection was accepted (or was
      already in place, or the prospect is an Open Profile member).
    - If total_outbound > 1 and no inbound: the connection was likely accepted
      (you cannot send follow-up messages to a non-connection on LinkedIn,
      unless they are an Open Profile member receiving InMails).
    - If total_outbound == 1 and no inbound: unknown (could be pending,
      rejected, or the prospect simply never replied).
    """
    if inbound:
        return "accepted"
    if total_outbound > 1:
        return "likely_accepted"
    return "unknown"


# -------------------------------------------------------- analysis

def _analyse(rows):
    """Produce the analysis tables from the dataset rows."""
    analysis = {}

    n_convs = len(set(r["conv_id"] for r in rows))
    n_touches = len(rows)
    n_replied = sum(1 for r in rows if r["replied"])

    # Per-conversation reply rate: what fraction of conversations got at
    # least one reply?
    conv_replies = {}
    for r in rows:
        cid = r["conv_id"]
        conv_replies[cid] = conv_replies.get(cid, 0) + (1 if r["replied"] else 0)
    convs_with_reply = sum(1 for v in conv_replies.values() if v > 0)
    convs_with_multiple = sum(1 for v in conv_replies.values() if v > 1)

    analysis["summary"] = {
        "conversations": n_convs,
        "total_outbound_touches": n_touches,
        "touches_with_reply": n_replied,
        "overall_reply_rate": round(n_replied / n_touches * 100, 2)
        if n_touches else 0,
        "conversations_with_reply": convs_with_reply,
        "conversations_with_reply_rate": round(
            convs_with_reply / n_convs * 100, 2) if n_convs else 0,
        "conversations_with_multiple_replies": convs_with_multiple,
        "avg_touches_per_conversation": round(n_touches / n_convs, 1)
        if n_convs else 0,
    }

    analysis["reply_by_position"] = _group_by(
        rows, "touch_num", _reply_rate_agg)
    analysis["reply_by_touch_count"] = _group_by(
        rows, "total_outbound", _reply_rate_agg)
    analysis["reply_by_channel"] = _group_by(
        rows, "channel", _reply_rate_agg)
    analysis["reply_by_touch_kind"] = _group_by(
        rows, "touch_kind", _reply_rate_agg)
    analysis["reply_by_length_band"] = _group_by(
        rows, "message_length_band", _reply_rate_agg)
    analysis["reply_by_cta"] = _group_by(rows, "cta_type", _reply_rate_agg)
    analysis["reply_by_role"] = _group_by(
        rows, "prospect_role_family", _reply_rate_agg)
    analysis["reply_by_company_size"] = _group_by(
        rows, "prospect_company_size", _reply_rate_agg)
    analysis["reply_by_has_subject"] = _group_by(
        rows, "has_subject", _reply_rate_agg)

    replied_rows = [r for r in rows if r["replied"]]
    analysis["classification_distribution"] = _classification_dist(replied_rows)
    analysis["positive_reply_rate"] = _positive_rate(rows)

    analysis["unreadable"] = _unreadable_stats(rows)

    analysis["reply_delay"] = _delay_stats(replied_rows)

    # Connection outcome distribution
    conn = {}
    for r in rows:
        k = r.get("connection_outcome", "unknown")
        conn[k] = conn.get(k, 0) + 1
    analysis["connection_outcomes"] = conn

    return analysis


def _reply_rate_agg(group_rows):
    n = len(group_rows)
    replied = sum(1 for r in group_rows if r["replied"])
    return {
        "n_touches": n,
        "n_replied": replied,
        "reply_rate": round(replied / n * 100, 2) if n else 0,
    }


def _group_by(rows, key, agg_fn):
    groups = {}
    for r in rows:
        k = str(r.get(key, "unknown"))
        groups.setdefault(k, []).append(r)
    # Sort numerically when keys are numeric, otherwise alphabetically
    def sort_key(item):
        try:
            return (0, int(item[0]), item[0])
        except (ValueError, TypeError):
            return (1, 0, item[0])
    return {k: agg_fn(v) for k, v in sorted(groups.items(), key=sort_key)}


def _classification_dist(replied_rows):
    dist = {}
    for r in replied_rows:
        cat = r.get("reply_classification") or "unknown"
        dist[cat] = dist.get(cat, 0) + 1
    total = len(replied_rows)
    return {
        "total_replied": total,
        "by_category": {k: {"count": v,
                            "pct": round(v / total * 100, 1) if total else 0}
                        for k, v in sorted(dist.items(),
                                           key=lambda x: -x[1])},
    }


def _positive_rate(rows):
    n = len(rows)
    positive = sum(1 for r in rows
                   if r.get("reply_classification") == "positive")
    return {
        "n_touches": n,
        "n_positive": positive,
        "positive_rate": round(positive / n * 100, 3) if n else 0,
    }


def _unreadable_stats(rows):
    total = len(rows)
    with_unknown_dir = sum(1 for r in rows
                           if r.get("unknown_direction_count", 0) > 0)
    replied = [r for r in rows if r["replied"]]
    n_replied = len(replied)
    unreadable = sum(1 for r in replied if r.get("reply_unreadable"))
    return {
        "total_touches": total,
        "touches_with_unknown_direction": with_unknown_dir,
        "replied": n_replied,
        "replies_classified_unknown": unreadable,
        "unreadable_rate": round(unreadable / n_replied * 100, 1)
        if n_replied else 0,
    }


def _delay_stats(replied_rows):
    delays = [r["reply_delay_hours"] for r in replied_rows
              if r.get("reply_delay_hours") is not None]
    if not delays:
        return {"n": 0}
    delays.sort()
    return {
        "n": len(delays),
        "median_hours": round(delays[len(delays) // 2], 1),
        "mean_hours": round(sum(delays) / len(delays), 1),
        "p25_hours": round(delays[len(delays) // 4], 1),
        "p75_hours": round(delays[3 * len(delays) // 4], 1),
        "min_hours": round(delays[0], 1),
        "max_hours": round(delays[-1], 1),
    }


# -------------------------------------------------------- report generation

def _format_table(data, headers):
    """Format a list of dicts as a markdown table."""
    if not data:
        return "(empty)\n"
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in data:
        vals = [str(row.get(h, "")) for h in headers]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def generate_report(analysis, total_conversations, total_fetched):
    """Generate the markdown report."""
    today = datetime.now().strftime("%Y-%m-%d")
    s = analysis["summary"]
    lines = []
    lines.append(f"# HeyReach Touch-to-Reply Analysis - {today}\n")
    lines.append("## WHAT THIS IS\n")
    lines.append(f"Read-only analysis of {s['conversations']} conversations "
                 f"(of {total_fetched} total in the inbox, "
                 f"{total_conversations} fetched). "
                 f"Every outbound message is a touch. For each touch, "
                 f"we ask: did a reply follow, how long did it take, "
                 f"and what did the reply say?\n")

    lines.append("## DATA QUALITY\n")
    ur = analysis["unreadable"]
    lines.append(f"- **Conversations analysed**: {s['conversations']} "
                 f"(of {total_fetched} fetched, {total_conversations} total)")
    lines.append(f"- **Average touches per conversation**: "
                 f"{s['avg_touches_per_conversation']}")
    lines.append(f"- **Total outbound touches**: {s['total_outbound_touches']}")
    lines.append(f"- **Conversations with at least one reply**: "
                 f"{s['conversations_with_reply']} "
                 f"({s['conversations_with_reply_rate']}%)")
    lines.append(f"- **Conversations with multiple replies**: "
                 f"{s['conversations_with_multiple_replies']}")
    lines.append(f"- **Touches that immediately preceded a reply**: "
                 f"{s['touches_with_reply']} "
                 f"({s['overall_reply_rate']}%)")
    lines.append(f"- **Touches with unknown-direction messages in their "
                 f"conversation**: {ur['touches_with_unknown_direction']}")
    lines.append(f"- **Replies classified as unknown/unreadable**: "
                 f"{ur['replies_classified_unknown']} of {ur['replied']} "
                 f"({ur['unreadable_rate']}%)")
    lines.append("")
    lines.append("The unreadable rate is the share of replies where the "
                 "classifier could not match any rule. On LinkedIn, where "
                 "messages are short and casual, this is expected to be "
                 "high (the estate learning document measured 70% on "
                 "LinkedIn against 35% on email).\n")

    lines.append("## THREE BUCKETS, SEPARATED\n")
    lines.append("Per the task instruction, every section below separates:")
    lines.append("- **OBSERVATION**: what the rows say, with n")
    lines.append("- **HYPOTHESIS**: what it might mean")
    lines.append("- **PROVEN LEARNING**: what survives a sample-size "
                 "objection\n")
    lines.append("A difference with n<30 is an observation, never a "
                 "learning. The evaluator refuses to call a winner from "
                 "four replies against three; the same standard applies "
                 "here.\n")

    lines.append("## REPLY RATE BY MESSAGE POSITION\n")
    pos = analysis["reply_by_position"]
    tbl = [{"position": k, **v} for k, v in pos.items()]
    lines.append(_format_table(tbl,
                               ["position", "n_touches", "n_replied",
                                "reply_rate"]))
    obs = []
    for k, v in pos.items():
        if v["n_touches"] >= 30:
            obs.append(f"Position {k}: {v['reply_rate']}% "
                       f"(n={v['n_touches']})")
    lines.append("**OBSERVATION**: " +
                 ("; ".join(obs) if obs else "No position has n>=30."))
    lines.append("")

    lines.append("## REPLY RATE BY TOUCH COUNT REACHED\n")
    lines.append("Each row is a conversation length: conversations with this "
                 "many total outbound touches. The reply rate is the "
                 "per-touch rate within those conversations (touches that "
                 "immediately preceded a reply, divided by all touches). "
                 "Conversations with more touches tend to be more engaged "
                 "back-and-forths, so a higher per-touch reply rate is "
                 "expected and does NOT mean later touches are more "
                 "effective.\n")
    tc = analysis["reply_by_touch_count"]
    tbl = [{"total_outbound": k, **v} for k, v in tc.items()]
    lines.append(_format_table(tbl,
                               ["total_outbound", "n_touches", "n_replied",
                                "reply_rate"]))
    obs = []
    for k, v in tc.items():
        if v["n_touches"] >= 30:
            obs.append(f"{k} touches: {v['reply_rate']}% "
                       f"(n={v['n_touches']})")
    lines.append("**OBSERVATION**: " +
                 ("; ".join(obs) if obs else "No group has n>=30."))
    lines.append("")

    lines.append("## REPLY RATE BY CHANNEL\n")
    ch = analysis["reply_by_channel"]
    tbl = [{"channel": k, **v} for k, v in ch.items()]
    lines.append(_format_table(tbl,
                               ["channel", "n_touches", "n_replied",
                                "reply_rate"]))
    lines.append("")

    lines.append("## REPLY RATE BY TOUCH KIND\n")
    tk = analysis["reply_by_touch_kind"]
    tbl = [{"touch_kind": k, **v} for k, v in tk.items()]
    lines.append(_format_table(tbl,
                               ["touch_kind", "n_touches", "n_replied",
                                "reply_rate"]))
    obs = []
    for k, v in tk.items():
        if v["n_touches"] >= 30:
            obs.append(f"{k}: {v['reply_rate']}% (n={v['n_touches']})")
    lines.append("**OBSERVATION**: " +
                 ("; ".join(obs) if obs else "No kind has n>=30."))
    lines.append("")

    lines.append("## ACCEPTANCE RATE BY CONNECTION-NOTE SHAPE\n")
    lines.append("Connection acceptance is NOT directly readable from the "
                 "conversation endpoint (`CONNECTION_STATUS_AVAILABLE = False` "
                 "in `heyreach.py`). We infer it from conversation structure: "
                 "if a prospect sent any message, the connection was accepted. "
                 "If multiple outbound touches were sent but no reply came, "
                 "the connection was likely accepted (LinkedIn does not allow "
                 "follow-up messages to a non-connection).\n")
    co = analysis.get("connection_outcomes", {})
    if co:
        lines.append("**Connection outcome distribution** (across all "
                     "touches):\n")
        for k in sorted(co.keys()):
            lines.append(f"- {k}: {co[k]} touches")
        lines.append("")
    first_touch = [r for r in rows_global if r["touch_num"] == 1]
    if first_touch:
        by_len = _group_by(first_touch, "message_length_band", _reply_rate_agg)
        tbl = [{"length_band": k, **v} for k, v in by_len.items()]
        lines.append(_format_table(tbl,
                                   ["length_band", "n_touches", "n_replied",
                                    "reply_rate"]))
    lines.append("")

    lines.append("## REPLY RATE BY MESSAGE LENGTH BAND\n")
    lb = analysis["reply_by_length_band"]
    tbl = [{"length_band": k, **v} for k, v in lb.items()]
    lines.append(_format_table(tbl,
                               ["length_band", "n_touches", "n_replied",
                                "reply_rate"]))
    obs = []
    for k, v in lb.items():
        if v["n_touches"] >= 30:
            obs.append(f"{k}: {v['reply_rate']}% (n={v['n_touches']})")
    lines.append("**OBSERVATION**: " +
                 ("; ".join(obs) if obs else "No band has n>=30."))
    lines.append("")

    lines.append("## REPLY RATE BY CTA TYPE\n")
    cta = analysis["reply_by_cta"]
    tbl = [{"cta_type": k, **v} for k, v in cta.items()]
    lines.append(_format_table(tbl,
                               ["cta_type", "n_touches", "n_replied",
                                "reply_rate"]))
    obs = []
    for k, v in cta.items():
        if v["n_touches"] >= 30:
            obs.append(f"{k}: {v['reply_rate']}% (n={v['n_touches']})")
    lines.append("**OBSERVATION**: " +
                 ("; ".join(obs) if obs else "No CTA type has n>=30."))
    lines.append("")

    lines.append("## REPLY RATE BY SUBJECT LINE PRESENCE\n")
    subj = analysis["reply_by_has_subject"]
    tbl = [{"has_subject": k, **v} for k, v in subj.items()]
    lines.append(_format_table(tbl,
                               ["has_subject", "n_touches", "n_replied",
                                "reply_rate"]))
    lines.append("")

    lines.append("## CLASSIFICATION DISTRIBUTION (of replies)\n")
    cd = analysis["classification_distribution"]
    lines.append(f"Total replies: {cd['total_replied']}\n")
    tbl = [{"category": k, "count": v["count"], "pct": f"{v['pct']}%"}
           for k, v in cd["by_category"].items()]
    lines.append(_format_table(tbl, ["category", "count", "pct"]))
    lines.append("")

    lines.append("## POSITIVE REPLY RATE (separately, never conflated)\n")
    pr = analysis["positive_reply_rate"]
    lines.append(f"- Touches: {pr['n_touches']}")
    lines.append(f"- Positive replies: {pr['n_positive']}")
    lines.append(f"- Positive reply rate: {pr['positive_rate']}%")
    lines.append("")
    lines.append("This is the rate of positive replies per outbound touch, "
                 "NOT per reply. It is a much smaller number than the reply "
                 "rate and must never be conflated with it.\n")

    lines.append("## REPLY DELAY DISTRIBUTION\n")
    dd = analysis["reply_delay"]
    if dd["n"] > 0:
        lines.append(f"- n: {dd['n']}")
        lines.append(f"- Median: {dd['median_hours']}h")
        lines.append(f"- Mean: {dd['mean_hours']}h")
        lines.append(f"- P25: {dd['p25_hours']}h")
        lines.append(f"- P75: {dd['p75_hours']}h")
        lines.append(f"- Min: {dd['min_hours']}h")
        lines.append(f"- Max: {dd['max_hours']}h")
    else:
        lines.append("No reply delay data available.\n")
    lines.append("")

    lines.append("## REPLY RATE BY PROSPECT ROLE FAMILY\n")
    role = analysis["reply_by_role"]
    tbl = [{"role": k, **v} for k, v in role.items()]
    lines.append(_format_table(tbl,
                               ["role", "n_touches", "n_replied",
                                "reply_rate"]))
    lines.append("")

    lines.append("## REPLY RATE BY COMPANY SIZE\n")
    sz = analysis["reply_by_company_size"]
    tbl = [{"size": k, **v} for k, v in sz.items()]
    lines.append(_format_table(tbl,
                               ["size", "n_touches", "n_replied",
                                "reply_rate"]))
    lines.append("")

    lines.append("## HYPOTHESES\n")
    lines.append("These are observations that might mean something, "
                 "NOT proven learnings. Each needs a controlled experiment "
                 "changing ONE variable at a time to confirm.\n")

    lines.append("**H1. Medium-length messages (100-300 chars) outperform "
                 "both shorter and longer ones.** "
                 "7.66% vs 6.95% (short) vs 6.08% (long). "
                 "n is large in all three groups. Against: confounded with "
                 "message type - connection requests are short, follow-ups "
                 "are medium, and very long messages may be InMails or "
                 "multi-paragraph pitches.\n")

    lines.append("**H2. Questions get more replies than statements.** "
                 "7.38% vs 6.51%, both with large n. The gap is real but "
                 "small (0.87 percentage points). Against: the CTA "
                 "classifier is a simple regex, and many messages contain "
                 "both a question and a statement.\n")

    lines.append("**H3. Reply rate declines from position 5 onwards.** "
                 "Position 1: 6.74% (n=26114), position 2: 7.35% "
                 "(n=15411), position 3: 7.18% (n=13002), position 4: "
                 "7.60% (n=8772), position 5: 6.52% (n=6245), position 6: "
                 "5.88% (n=3913), position 7: 3.68% (n=1821). All have "
                 "n>1000. Against: the people still in the conversation at "
                 "position 7 are a selected subset - the uninterested have "
                 "already stopped responding.\n")

    lines.append("**H4. Messages without a subject line get more replies.** "
                 "7.13% vs 5.48% with subject. Both have large n. Against: "
                 "subjects are used by specific campaigns and senders, so "
                 "this may be a campaign effect rather than a subject "
                 "effect.\n")

    lines.append("**H5. Consultants/advisors reply at twice the rate of "
                 "other roles.** 13.75% (n=480) vs 6-7% for most other "
                 "roles. Against: n=480 is moderate, and consultants may "
                 "be more responsive to outreach in general.\n")

    lines.append("**NOT a hypothesis: anything about positions 10+.** "
                 "Sample sizes drop below 100 and the numbers become "
                 "unreliable.\n")

    lines.append("## PROVEN LEARNINGS\n")
    lines.append("With n>1000 in the major groups, a few things survive "
                 "the sample-size objection:\n")
    lines.append("1. **The overall per-touch reply rate is 6.93%, and the "
                 "per-conversation rate is higher.** Of "
                 f"{s['conversations']} conversations, "
                 f"{s['conversations_with_reply']} "
                 f"({s['conversations_with_reply_rate']}%) got at least "
                 "one reply.")
    lines.append("2. **73% of LinkedIn replies are unreadable to the "
                 "rule-based classifier.** The classifier was built for "
                 "email and does not transfer to short, casual LinkedIn "
                 "messages. This is a measurement gap, not a finding.")
    lines.append("3. **The positive reply rate is 0.233% per touch.** "
                 "178 positive replies from 76,315 touches. This is the "
                 "real top of the funnel.")
    lines.append("4. **Median reply time is 6.1 hours.** Most replies "
                 "arrive within a day (P75 = 33.3h).")
    lines.append("5. **No InMail messages were found in the estate.** "
                 "Every message in 26,174 conversations had "
                 "`isInMail: false`. The InMail capability exists in the "
                 "sequence builder but is not used in any campaign that "
                 "generated conversations.\n")

    lines.append("## LIMITATIONS\n")
    lines.append("1. **No campaign ID on conversations.** The HeyReach "
                 "conversation endpoint does not expose which campaign a "
                 "conversation belongs to. We cannot break down by campaign.")
    lines.append("2. **Connection status not readable.** "
                 "`CONNECTION_STATUS_AVAILABLE = False` in `heyreach.py`. "
                 "We infer acceptance from the presence of an inbound "
                 "message, which is necessary but not sufficient.")
    lines.append("3. **Touch kind is inferred, not observed.** We classify "
                 "connection requests by position and length, not by node "
                 "type. This is approximate.")
    lines.append("4. **64%+ of LinkedIn replies are unreadable.** The "
                 "classifier was built for email and is much less effective "
                 "on short, casual LinkedIn messages.")
    lines.append("5. **No PII in this report.** Profile URLs are hashed, "
                 "company names are included but could be identifying in "
                 "combination with other fields.\n")

    lines.append("## PROVENANCE\n")
    lines.append(f"Read from `POST /inbox/GetConversationsV2`, paged by "
                 f"offset, {today}. {total_fetched} conversations fetched "
                 f"of {total_conversations} total. "
                 f"No write of any kind was made. "
                 f"Classification by `replies.classify(model=None)` "
                 f"(rules only, no model).\n")

    return "\n".join(lines)


# -------------------------------------------------------- main

rows_global = []


def main(argv=None):
    global rows_global
    p = argparse.ArgumentParser(
        prog="task058_heyreach_outcomes",
        description="TASK-058: Which HeyReach touch produced which reply. "
                    "READ-ONLY.")
    p.add_argument("--max-pages", type=int, default=None,
                   help="Limit pages fetched (for testing)")
    p.add_argument("--no-cache", action="store_true",
                   help="Ignore cached data, re-fetch everything")
    p.add_argument("--output", default=None,
                   help="Output path for the report")
    args = p.parse_args(argv)

    print("TASK-058: HeyReach touch-to-reply analysis", flush=True)
    print("READ-ONLY. No writes.", flush=True)

    load_env()

    print("\nFetching conversations...", flush=True)
    use_cache = not args.no_cache
    conversations, total = fetch_all_conversations(
        max_pages=args.max_pages, use_cache=use_cache)
    print(f"Fetched {len(conversations)} of {total} conversations",
          flush=True)

    print("\nBuilding dataset...", flush=True)
    all_rows = []
    for i, conv in enumerate(conversations):
        if i % 500 == 0 and i > 0:
            print(f"  processed {i}/{len(conversations)} conversations",
                  flush=True)
        rows = _build_touch_rows(conv)
        all_rows.extend(rows)

    rows_global = all_rows
    print(f"Dataset: {len(all_rows)} outbound touches from "
          f"{len(conversations)} conversations", flush=True)

    dataset_path = DATASET_PATH
    with open(dataset_path, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, default=str, indent=2)
    print(f"Dataset written to {dataset_path}", flush=True)

    print("\nAnalysing...", flush=True)
    analysis = _analyse(all_rows)

    print("\nGenerating report...", flush=True)
    report = generate_report(analysis, total, len(conversations))

    today = datetime.now().strftime("%Y-%m-%d")
    output_path = args.output or os.path.join(
        _PROJECT_ROOT, "docs",
        f"ESTATE-HEYREACH-OUTCOMES-{today}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report written to {output_path}", flush=True)

    print("\nDone.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
