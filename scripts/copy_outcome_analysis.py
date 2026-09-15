#!/usr/bin/env python3
"""TASK-106: Analyse what copy that earned replies had in common.

Reads the EmailBison reply feed (sampled), classifies each reply, then
compares the campaign sequence-step copy associated with MEETING_INTENT
replies against the copy associated with OBJECTION replies.

READS ONLY. No POST/PATCH/PUT/DELETE. No sends. No campaign mutation.

Usage:
    py -3 -m scripts.copy_outcome_analysis
"""
import json
import os
import re
import sys
import time

# Ensure project root is on the path.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load environment using the project's own loader.
from src.providers import load_env
load_env()

from src.providers.bison import (
    fetch_replies, sequence_steps, campaign, base, headers,
    classify_reply_row, REPLIES_PATH, PER_PAGE_MAX
)
from src.providers import request, ok
from src.replies import (
    classify, MEETING_INTENT, OBJECTION, UNSUBSCRIBE, NEGATIVE,
    ACCOUNT_DNC, UNKNOWN, POSITIVE, NEUTRAL, OUT_OF_OFFICE,
    NOT_NOW, NOT_RELEVANT, REFERRAL, INTERESTED,
    extract_prospect_text, normalise
)


def fetch_sampled_replies(max_pages=200):
    """Walk the reply feed up to max_pages. Returns (rows, pages_walked)."""
    rows, cursor, pages = [], None, 0
    seen_cursors = set()
    while pages < max_pages:
        page_rows, next_cursor = fetch_replies(cursor=cursor,
                                               per_page=PER_PAGE_MAX)
        if not page_rows:
            break
        rows.extend(page_rows)
        pages += 1
        if not next_cursor:
            break
        if next_cursor == cursor or next_cursor in seen_cursors:
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor
        if pages % 50 == 0:
            print(f"  ... page {pages}, {len(rows)} rows", file=sys.stderr)
    return rows, pages


def classify_all_replies(rows):
    """Classify each reply row. Returns (results, skip_counts)."""
    results = []
    skipped = {"outgoing": 0, "bounce": 0, "unknown_kind": 0}
    for row in rows:
        kind = classify_reply_row(row)
        if kind == "outgoing":
            skipped["outgoing"] += 1
            continue
        if kind == "bounce":
            skipped["bounce"] += 1
            continue
        if kind == "unknown":
            skipped["unknown_kind"] += 1
            continue

        body = row.get("text_body") or ""
        extracted = extract_prospect_text(body)
        prospect_text = extracted["text"]
        if not prospect_text.strip():
            verdict = {"classification": UNKNOWN, "confidence": 0.0,
                       "reason": "empty reply body", "evidence": [],
                       "classifier": "rules-3"}
        else:
            verdict = classify(prospect_text)
        results.append({
            "row": row,
            "verdict": verdict,
            "prospect_text": prospect_text,
            "campaign_id": row.get("campaign_id"),
            "lead_id": row.get("lead_id"),
            "scheduled_email_id": row.get("scheduled_email_id"),
            "subject": row.get("subject") or "",
        })
    return results, skipped


def analyse_copy(text, subject=""):
    """Extract measurable characteristics from an email body."""
    if not text:
        return None
    body = text.strip()
    if not body:
        return None
    words = body.split()
    word_count = len(words)
    char_count = len(body)
    sentence_count = max(len(re.split(r'[.!?]+', body)), 1)
    lines = [l.strip() for l in body.split('\n') if l.strip()]

    # Opening type
    opening_type = "unknown"
    if lines:
        first = lines[0].lower()
        if re.match(r'^(hi|hey|hello|dear|good\s+\w+)', first):
            opening_type = "greeting"
        elif first.endswith('?'):
            opening_type = "opening_question"
        elif re.match(r'^(i|we|my|our)\b', first):
            opening_type = "first_person"
        elif re.match(r'^(your|you)\b', first):
            opening_type = "second_person"
        else:
            opening_type = "other"

    # Questions
    questions = len(re.findall(r'\?', body))

    # CTA detection
    cta_patterns = [
        r'\b(?:book|schedule|set up|arrange)\s+(?:a\s+)?(?:call|meeting|chat)\b',
        r'\b(?:let\'?s|lets)\s+(?:chat|talk|meet|connect|schedule)\b',
        r'\b(?:send|share)\s+(?:me\s+)?(?:a\s+)?(?:calendar|invite|link)\b',
        r'\b(?:demo|proposal|quote)\b',
        r'\b(?:when|what time|how about)\b.*\b(?:work|available|free)\b',
        r'\b(?:reply|respond|get back)\s+(?:to|at)\b',
    ]
    cta_count = sum(1 for p in cta_patterns if re.search(p, body, re.I))
    cta_type = "has_cta" if cta_count > 0 else "no_cta"

    # Personalisation markers
    personalisation = []
    if re.search(r'\{(?:FIRST_NAME|first_name)\}', body + " " + subject, re.I):
        personalisation.append("first_name_var")
    if re.search(r'\{(?:COMPANY|company)\}', body + " " + subject, re.I):
        personalisation.append("company_var")
    if re.search(r'\b(?:I saw|I noticed|I came across)\b', body, re.I):
        personalisation.append("research_opener")
    if re.search(r'\b(?:your (?:recent|latest|new) )\b', body, re.I):
        personalisation.append("recent_activity")
    if lines and re.match(r'^(?:hi|hey|hello)\s+[A-Z]', lines[0], re.I):
        personalisation.append("name_in_greeting")
    personalisation_depth = len(personalisation)

    # Product naming
    product_named = bool(re.search(
        r'\b(?:our platform|our tool|our solution|AI|automation)\b',
        body, re.I))

    # Sender identification
    sender_identified = bool(
        re.search(r'\b(?:I\'m|I am)\s+[A-Z]', body) or
        re.search(r'(?:regards|best|thanks),?\s*\n\s*[A-Z]', body))

    # Length category
    if word_count <= 50:
        length_cat = "short"
    elif word_count <= 150:
        length_cat = "medium"
    else:
        length_cat = "long"

    return {
        "word_count": word_count,
        "char_count": char_count,
        "sentence_count": sentence_count,
        "opening_type": opening_type,
        "question_count": questions,
        "question_ratio": round(questions / sentence_count, 3),
        "cta_type": cta_type,
        "cta_count": cta_count,
        "personalisation_depth": personalisation_depth,
        "personalisation_kinds": personalisation,
        "product_named": product_named,
        "sender_identified": sender_identified,
        "length_category": length_cat,
    }


def aggregate(features_list):
    """Compute aggregate statistics from a list of feature dicts."""
    valid = [f for f in features_list if f]
    n = len(valid)
    if n == 0:
        return {"n": 0}

    def avg(key):
        vals = [f[key] for f in valid if key in f]
        return round(sum(vals) / len(vals), 1) if vals else 0

    def median(key):
        vals = sorted(f[key] for f in valid if key in f)
        if not vals:
            return 0
        mid = len(vals) // 2
        return vals[mid] if len(vals) % 2 else (vals[mid-1] + vals[mid]) / 2

    def dist(key):
        d = {}
        for f in valid:
            v = f.get(key, "unknown")
            d[v] = d.get(v, 0) + 1
        return d

    def count_true(key):
        return sum(1 for f in valid if f.get(key))

    return {
        "n": n,
        "word_mean": avg("word_count"),
        "word_median": median("word_count"),
        "question_mean": avg("question_count"),
        "question_ratio_mean": round(avg("question_ratio"), 3),
        "opening_types": dist("opening_type"),
        "cta_types": dist("cta_type"),
        "cta_mean": avg("cta_count"),
        "product_named": f"{count_true('product_named')}/{n}",
        "sender_identified": f"{count_true('sender_identified')}/{n}",
        "personalisation_mean": avg("personalisation_depth"),
        "personalisation_any": f"{sum(1 for f in valid if f.get('personalisation_depth', 0) > 0)}/{n}",
        "length_dist": dist("length_category"),
    }


def main():
    print("TASK-106: Copy outcome pattern analysis", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Step 1: Fetch sampled replies
    print("\n[1/4] Fetching reply feed (sampled)...", file=sys.stderr)
    all_rows, pages = fetch_sampled_replies(max_pages=300)
    print(f"  Sampled {len(all_rows)} rows across {pages} pages",
          file=sys.stderr)

    # Step 2: Classify
    print("\n[2/4] Classifying replies...", file=sys.stderr)
    classified, skipped = classify_all_replies(all_rows)
    print(f"  Classified {len(classified)} replies, skipped {skipped}",
          file=sys.stderr)

    # Tally
    verdict_counts = {}
    for item in classified:
        v = item["verdict"].get("classification", UNKNOWN)
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
    print(f"  Verdict tally:", file=sys.stderr)
    for k, v in sorted(verdict_counts.items(), key=lambda x: -x[1]):
        print(f"    {k}: {v}", file=sys.stderr)

    # Step 3: Build analysis sets
    positive = [i for i in classified
                if i["verdict"].get("classification") == MEETING_INTENT]
    negative = [i for i in classified
                if i["verdict"].get("classification") in
                (OBJECTION, UNSUBSCRIBE, ACCOUNT_DNC)]

    pos_cids = set(i["campaign_id"] for i in positive if i.get("campaign_id"))
    neg_cids = set(i["campaign_id"] for i in negative if i.get("campaign_id"))
    print(f"\n  MEETING_INTENT: n={len(positive)}, campaigns={sorted(pos_cids)}",
          file=sys.stderr)
    print(f"  OBJECTION+UNSUB+DNC: n={len(negative)}, campaigns={sorted(neg_cids)}",
          file=sys.stderr)

    # Step 4: Fetch campaign sequence steps
    print("\n[3/4] Fetching campaign sequence steps...", file=sys.stderr)
    campaign_steps = {}
    for cid in pos_cids | neg_cids:
        try:
            steps = sequence_steps(cid)
            campaign_steps[cid] = steps
            print(f"  Campaign {cid}: {len(steps)} steps", file=sys.stderr)
            time.sleep(0.3)
        except Exception as e:
            print(f"  Campaign {cid}: FAILED ({e})", file=sys.stderr)
            campaign_steps[cid] = []

    # Also fetch outgoing emails from the feed for these campaigns
    outgoing_by_campaign = {}
    for row in all_rows:
        if classify_reply_row(row) != "outgoing":
            continue
        cid = row.get("campaign_id")
        if cid:
            outgoing_by_campaign.setdefault(cid, []).append(row)

    # Analyse copy
    print("\n[4/4] Analysing copy characteristics...", file=sys.stderr)

    # Campaign sequence step copy (what we sent)
    pos_step_features = []
    neg_step_features = []
    for cid in pos_cids:
        for step in campaign_steps.get(cid, []):
            body = step.get("email_body") or ""
            subj = step.get("email_subject") or ""
            f = analyse_copy(body, subj)
            if f:
                f["campaign_id"] = cid
                f["step_order"] = step.get("order")
                pos_step_features.append(f)
    for cid in neg_cids:
        for step in campaign_steps.get(cid, []):
            body = step.get("email_body") or ""
            subj = step.get("email_subject") or ""
            f = analyse_copy(body, subj)
            if f:
                f["campaign_id"] = cid
                f["step_order"] = step.get("order")
                neg_step_features.append(f)

    # Outgoing emails from the feed
    pos_outgoing_features = []
    neg_outgoing_features = []
    for cid in pos_cids:
        for row in outgoing_by_campaign.get(cid, []):
            body = row.get("text_body") or ""
            subj = row.get("subject") or ""
            f = analyse_copy(body, subj)
            if f:
                pos_outgoing_features.append(f)
    for cid in neg_cids:
        for row in outgoing_by_campaign.get(cid, []):
            body = row.get("text_body") or ""
            subj = row.get("subject") or ""
            f = analyse_copy(body, subj)
            if f:
                neg_outgoing_features.append(f)

    # Reply text characteristics (what the prospect said)
    pos_reply_features = [analyse_copy(i["prospect_text"]) for i in positive]
    neg_reply_features = [analyse_copy(i["prospect_text"]) for i in negative]

    # Build report
    report = {
        "sampling": {
            "total_rows": len(all_rows),
            "pages": pages,
            "per_page_note": "EmailBison ignores per_page, always returns 15",
            "pagination": "cursor",
            "replies_classified": len(classified),
            "skipped": skipped,
            "verdict_tally": verdict_counts,
        },
        "positive_set": {
            "classifier": MEETING_INTENT,
            "precision": "1.00",
            "recall": "1.00",
            "n_replies": len(positive),
            "campaign_ids": sorted(pos_cids),
            "n_sequence_steps": len(pos_step_features),
            "n_outgoing_in_feed": len(pos_outgoing_features),
            "campaign_copy": aggregate(pos_step_features),
            "outgoing_copy": aggregate(pos_outgoing_features),
            "reply_text": aggregate(pos_reply_features),
        },
        "negative_set": {
            "classifier": "objection + unsubscribe + account_dnc",
            "precision": "1.00 (objection)",
            "recall": "0.67 (objection)",
            "n_replies": len(negative),
            "campaign_ids": sorted(neg_cids),
            "n_sequence_steps": len(neg_step_features),
            "n_outgoing_in_feed": len(neg_outgoing_features),
            "campaign_copy": aggregate(neg_step_features),
            "outgoing_copy": aggregate(neg_outgoing_features),
            "reply_text": aggregate(neg_reply_features),
        },
    }

    # Also save qualitative data: anonymised reply excerpts and campaign copy
    qualitative = {
        "meeting_intent_replies": [],
        "objection_replies": [],
        "unsubscribe_replies": [],
        "campaign_sequence_copy": {},
    }
    for item in positive:
        text = item["prospect_text"][:300]  # truncate for safety
        qualitative["meeting_intent_replies"].append({
            "campaign_id": item.get("campaign_id"),
            "subject": item.get("subject", "")[:100],
            "text_preview": text,
            "word_count": len(item["prospect_text"].split()),
        })
    for item in negative:
        cat = item["verdict"].get("classification", "")
        text = item["prospect_text"][:300]
        entry = {
            "campaign_id": item.get("campaign_id"),
            "classification": cat,
            "subject": item.get("subject", "")[:100],
            "text_preview": text,
            "word_count": len(item["prospect_text"].split()),
        }
        if cat == OBJECTION:
            qualitative["objection_replies"].append(entry)
        else:
            qualitative["unsubscribe_replies"].append(entry)

    # Save campaign sequence step copy (first 3 steps per campaign)
    for cid in pos_cids | neg_cids:
        steps = campaign_steps.get(cid, [])
        step_copy = []
        for step in steps[:5]:  # first 5 steps max
            body = (step.get("email_body") or "")[:500]
            subj = (step.get("email_subject") or "")[:200]
            step_copy.append({
                "order": step.get("order"),
                "subject": subj,
                "body_preview": body,
                "word_count": len((step.get("email_body") or "").split()),
            })
        qualitative["campaign_sequence_copy"][str(cid)] = step_copy

    # Write outputs
    os.makedirs(os.path.join(ROOT, "work"), exist_ok=True)
    json_path = os.path.join(ROOT, "work", "task106_analysis.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    qual_path = os.path.join(ROOT, "work", "task106_qualitative.json")
    with open(qual_path, "w", encoding="utf-8") as f:
        json.dump(qualitative, f, indent=2, default=str)
    print(f"\nJSON report: {json_path}", file=sys.stderr)
    print(f"Qualitative data: {qual_path}", file=sys.stderr)

    # Print summary to stdout
    print(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    main()
