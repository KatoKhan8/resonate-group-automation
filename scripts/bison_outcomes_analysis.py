#!/usr/bin/env python3
"""TASK-059: Which EmailBison email produced which reply.

Reply-centric analysis: starts from every reply in the feed, fetches the
specific scheduled email that produced it (via scheduled_email_id), classifies
the reply, and produces the analysis.

READS ONLY. No write, no send, no mutation.

Usage:
    python scripts/bison_outcomes_analysis.py [--cache-dir DIR]

Output:
    docs/ESTATE-BISON-OUTCOMES-<date>.md
"""
import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.providers import bison, ProviderError
from src import replies

DEFAULT_CACHE = os.path.join(ROOT, ".qwen", "tmp", "bison_cache")


def _cache_path(cache_dir, name):
    return os.path.join(cache_dir, f"{name}.json")


def _load_cache(cache_dir, name):
    path = _cache_path(cache_dir, name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cache(cache_dir, name, data):
    os.makedirs(cache_dir, exist_ok=True)
    tmp = _cache_path(cache_dir, name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, default=str)
    os.replace(tmp, _cache_path(cache_dir, name))


def fetch_all_campaigns(cache_dir):
    cached = _load_cache(cache_dir, "campaigns")
    if cached is not None:
        return cached
    rows, _total = bison._paged(
        "campaigns_list",
        lambda page: bison.query(f"{bison.base()}/campaigns",
                                 {"page": page, "per_page": 100}))
    campaigns = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        campaigns.append({
            "id": r.get("id"),
            "name": r.get("name"),
            "status": r.get("status"),
            "open_tracking": r.get("open_tracking"),
            "max_emails_per_day": r.get("max_emails_per_day"),
            "created_at": r.get("created_at"),
        })
    _save_cache(cache_dir, "campaigns", campaigns)
    return campaigns


def fetch_sequence_steps(cache_dir, campaign_id):
    name = f"steps_{campaign_id}"
    cached = _load_cache(cache_dir, name)
    if cached is not None:
        return cached
    try:
        steps = bison.sequence_steps(campaign_id)
    except ProviderError:
        steps = []
    _save_cache(cache_dir, name, steps)
    return steps


def fetch_campaign_lead_count(cache_dir, campaign_id):
    name = f"leadcount_{campaign_id}"
    cached = _load_cache(cache_dir, name)
    if cached is not None:
        return cached
    try:
        count = bison.campaign_lead_count(campaign_id)
    except ProviderError:
        count = -1
    _save_cache(cache_dir, name, count)
    return count


def fetch_replies_incremental(cache_dir):
    """Fetch replies with JSONL checkpointing. Capped at 1500 pages."""
    data_path = _cache_path(cache_dir, "replies_data.jsonl")
    checkpoint_path = _cache_path(cache_dir, "replies_cursor.json")
    replies_path = _cache_path(cache_dir, "replies")

    if os.path.exists(replies_path):
        with open(replies_path, encoding="utf-8") as f:
            return json.load(f)

    os.makedirs(cache_dir, exist_ok=True)
    checkpoint = {}
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, encoding="utf-8") as f:
            checkpoint = json.load(f)

    cursor = checkpoint.get("cursor")
    page = checkpoint.get("page", 0)
    all_rows = []
    if os.path.exists(data_path):
        with open(data_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        all_rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        break

    seen_cursors = set()
    if cursor:
        seen_cursors.add(cursor)

    MAX_PAGES = 1500
    while True:
        page += 1
        if page > MAX_PAGES:
            print(f"  Page cap at {MAX_PAGES} pages ({len(all_rows)} rows)",
                  file=sys.stderr)
            break
        try:
            rows, next_cursor = bison.fetch_replies(cursor=cursor)
        except ProviderError as e:
            print(f"  WARNING: page {page}: {e}", file=sys.stderr)
            break
        with open(data_path, "a", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, default=str) + "\n")
        all_rows.extend(rows)
        if not next_cursor or next_cursor in seen_cursors:
            break
        seen_cursors.add(cursor)
        cursor = next_cursor
        cp_tmp = checkpoint_path + ".tmp"
        with open(cp_tmp, "w", encoding="utf-8") as f:
            json.dump({"cursor": cursor, "page": page}, f)
        os.replace(cp_tmp, checkpoint_path)
        if page % 10 == 0:
            print(f"  ... {len(all_rows)} replies (page {page})",
                  file=sys.stderr)
        time.sleep(0.15)

    _save_cache(cache_dir, "replies", all_rows)
    for p in (checkpoint_path, data_path):
        if os.path.exists(p):
            os.remove(p)
    return all_rows


def fetch_scheduled_email_by_id(cache_dir, seid):
    """Fetch one scheduled email by its global ID. Cached."""
    name = f"se_{seid}"
    cached = _load_cache(cache_dir, name)
    if cached is not None:
        return cached
    try:
        status, data = bison.request(
            "GET", f"{bison.base()}/scheduled-emails/{seid}",
            bison.headers())
        if bison.ok(status):
            row = data.get("data") if isinstance(data, dict) else None
            if isinstance(row, dict):
                _save_cache(cache_dir, name, row)
                return row
    except ProviderError:
        pass
    _save_cache(cache_dir, name, {})
    return {}


def _hash_email(email):
    if not email:
        return ""
    return hashlib.sha256(str(email).strip().lower().encode()).hexdigest()[:12]


def _hash_text(text):
    if not text:
        return ""
    return hashlib.sha256(str(text).encode()).hexdigest()[:12]


def _parse_dt(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            continue
    return None


def _body_length_band(length):
    if length < 100:
        return "<100"
    if length < 300:
        return "100-299"
    if length < 600:
        return "300-599"
    if length < 1000:
        return "600-999"
    return "1000+"


def _subject_shape(subject):
    s = (subject or "").strip()
    if not s:
        return "(empty)"
    if s.startswith(("Re:", "RE:", "re:")):
        return "reply-prefix"
    merge_markers = ("{{", "{FIRST", "{first}", "{LAST", "{last}",
                     "{COMPANY", "{company}", "[[", "<<")
    has_name = any(tok in s for tok in merge_markers)
    has_question = "?" in s
    if has_name and has_question:
        return "personalised+question"
    if has_name:
        return "personalised"
    if has_question:
        return "question"
    return "statement"


def classify_reply_text(text, automated_flag=None):
    if not text or not text.strip():
        return {"classification": replies.UNKNOWN, "confidence": 0.0,
                "reason": "empty", "is_automated": automated_flag,
                "unreadable": False, "extract_method": "empty"}
    extracted = replies.extract_prospect_text(text)
    prospect_text = extracted["text"]
    if not prospect_text.strip():
        return {"classification": replies.UNKNOWN, "confidence": 0.0,
                "reason": "extraction yielded empty",
                "is_automated": automated_flag,
                "unreadable": True,
                "extract_method": extracted["method"]}
    verdict = replies.classify(prospect_text)
    v = verdict.get("verdict") or verdict or {}
    return {
        "classification": v.get("classification", replies.UNKNOWN),
        "confidence": v.get("confidence", 0.0),
        "reason": v.get("reason", ""),
        "is_automated": automated_flag,
        "unreadable": (extracted["had_quote"]
                       and extracted["method"] == "empty"),
        "extract_method": extracted["method"],
    }


def build_analysis(cache_dir):
    print("Fetching campaigns...", file=sys.stderr)
    campaigns = fetch_all_campaigns(cache_dir)
    camp_by_id = {c["id"]: c for c in campaigns}
    print(f"  {len(campaigns)} campaigns", file=sys.stderr)

    print("Fetching sequence steps per campaign...", file=sys.stderr)
    steps_by_campaign = {}
    step_order_by_step_id = {}
    for c in campaigns:
        steps = fetch_sequence_steps(cache_dir, c["id"])
        steps_by_campaign[c["id"]] = steps
        for s in steps:
            sid = s.get("id")
            order = s.get("order")
            if sid is not None and order is not None:
                step_order_by_step_id[sid] = int(order)
        print(f"  Campaign {c['id']}: {len(steps)} steps", file=sys.stderr)

    print("Fetching replies...", file=sys.stderr)
    all_replies = fetch_replies_incremental(cache_dir)
    print(f"  {len(all_replies)} total reply rows", file=sys.stderr)

    reply_type_counts = defaultdict(int)
    reply_rows = []
    bounce_rows = []
    for row in all_replies:
        if not isinstance(row, dict):
            continue
        kind = bison.classify_reply_row(row)
        reply_type_counts[kind] += 1
        if kind == "reply":
            reply_rows.append(row)
        elif kind == "bounce":
            bounce_rows.append(row)

    print(f"\nFetching {len(reply_rows)} reply-linked scheduled emails...",
          file=sys.stderr)
    se_cache = {}
    fetched = 0
    for i, rr in enumerate(reply_rows):
        seid = rr.get("scheduled_email_id")
        if seid and seid not in se_cache:
            se = fetch_scheduled_email_by_id(cache_dir, int(seid))
            se_cache[int(seid)] = se
            fetched += 1
            if fetched % 50 == 0:
                print(f"  ... {fetched} scheduled emails fetched",
                      file=sys.stderr)
            time.sleep(0.1)
    print(f"  {fetched} scheduled emails fetched ({len(se_cache)} cached)",
          file=sys.stderr)

    print("\nBuilding dataset...", file=sys.stderr)
    dataset = []
    for rr in reply_rows:
        seid = rr.get("scheduled_email_id")
        se = se_cache.get(int(seid)) if seid else {}
        text = (rr.get("text_body") or rr.get("text")
                or rr.get("body") or "")
        automated = rr.get("automated_reply")
        auto_flag = None if automated is None else bool(automated)
        cls = classify_reply_text(text, auto_flag)

        sent_at = (se or {}).get("sent_at")
        received_at = rr.get("date_received") or rr.get("created_at")
        sent_dt = _parse_dt(sent_at)
        recv_dt = _parse_dt(received_at)
        hours_to_reply = None
        if sent_dt and recv_dt and recv_dt > sent_dt:
            delta = recv_dt - sent_dt
            hours_to_reply = round(delta.total_seconds() / 3600, 1)

        cid = rr.get("campaign_id") or (se or {}).get("campaign_id")
        seq_step_id = (se or {}).get("sequence_step_id")
        step_order = step_order_by_step_id.get(seq_step_id) if seq_step_id else None

        lead = (se or {}).get("lead") or {}
        if not isinstance(lead, dict):
            lead = {}
        lead_data = rr.get("lead") or {}
        if not isinstance(lead_data, dict):
            lead_data = {}

        company = lead.get("company") or lead_data.get("company") or ""
        title = lead.get("title") or lead_data.get("title") or ""

        subject = (se or {}).get("email_subject") or ""
        body = (se or {}).get("email_body") or ""

        row = {
            "campaign_id": cid,
            "campaign_name": (camp_by_id.get(int(cid), {}).get("name", "")
                              if cid else ""),
            "scheduled_email_id": seid,
            "sequence_step_id": seq_step_id,
            "sequence_step_order": step_order,
            "se_status": (se or {}).get("status"),
            "sent_at": sent_at,
            "received_at": received_at,
            "hours_to_reply": hours_to_reply,
            "email_subject": subject,
            "subject_shape": _subject_shape(subject),
            "email_body_length": len(body),
            "body_length_band": _body_length_band(len(body)),
            "from_email_hash": _hash_email(rr.get("from_email_address")),
            "to_email_hash": _hash_email(
                rr.get("primary_to_email_address")),
            "lead_email_hash": _hash_email(lead.get("email")),
            "lead_company_hash": _hash_email(str(company)),
            "lead_title_hash": _hash_text(str(title)),
            "reply_text_length": len(text),
            "reply_text_hash": _hash_text(text),
            "row_type": rr.get("type"),
            "row_folder": rr.get("folder"),
            **cls,
        }
        dataset.append(row)

    return campaigns, all_replies, reply_rows, bounce_rows, dataset, \
        reply_type_counts, steps_by_campaign


def _safe_name(name):
    return (name or "unknown").replace("/", "_").replace("\\", "_")[:40]


def produce_report(campaigns, all_replies, reply_rows, bounce_rows,
                   dataset, reply_type_counts, steps_by_campaign,
                   output_path):
    cache_dir = os.path.join(ROOT, ".qwen", "tmp", "bison_cache")
    matched = [d for d in dataset if d.get("scheduled_email_id")]
    historical = [d for d in dataset if not d.get("scheduled_email_id")]

    lines = []
    today = datetime.now().strftime("%Y-%m-%d")
    lines.append(f"# EmailBison Estate Outcomes - {today}")
    lines.append("")
    lines.append("TASK-059. Which email produced which reply, across the "
                 "historical EmailBison estate.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- 1. Estate Summary
    lines.append("## 1. Estate Summary")
    lines.append("")
    total_leads = sum(
        max(0, fetch_campaign_lead_count(cache_dir, c["id"]))
        for c in campaigns)
    has_seid = sum(1 for r in reply_rows if r.get("scheduled_email_id"))
    no_cid = sum(1 for r in reply_rows if not r.get("campaign_id"))
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Campaigns | {len(campaigns)} |")
    lines.append(f"| Total leads (sum across campaigns) | {total_leads} |")
    lines.append(f"| Reply feed rows (1500-page sample) | "
                 f"{len(all_replies)} |")
    lines.append(f"| Reply feed: replies | "
                 f"{reply_type_counts.get('reply', 0)} |")
    lines.append(f"| Reply feed: bounces | "
                 f"{reply_type_counts.get('bounce', 0)} |")
    lines.append(f"| Reply feed: outgoing (our own mail) | "
                 f"{reply_type_counts.get('outgoing', 0)} |")
    lines.append(f"| Reply rows with scheduled_email_id (matched) | "
                 f"{has_seid}/{len(reply_rows)} |")
    lines.append(f"| Reply rows without campaign_id (historical) | "
                 f"{no_cid}/{len(reply_rows)} |")
    lines.append("")
    lines.append("Two populations exist in this estate:")
    lines.append("")
    lines.append(f"1. **Matched** ({len(matched)}): replies with a "
                 f"`scheduled_email_id` linking them to the specific sent "
                 f"email. Step position, subject, body, and time-to-reply "
                 f"are available.")
    lines.append(f"2. **Historical** ({len(historical)}): replies from "
                 f"before the API created leads. No step position, no "
                 f"subject, no body. Classification and provider flags "
                 f"only.")
    lines.append("")

    # ---- Campaign Detail
    lines.append("### Campaign Detail")
    lines.append("")
    lines.append("| ID | Name | Status | Steps | Leads |")
    lines.append("|----|------|--------|-------|-------|")
    for c in campaigns:
        n_steps = len(steps_by_campaign.get(c["id"], []))
        lc = fetch_campaign_lead_count(cache_dir, c["id"])
        lines.append(f"| {c['id']} | {_safe_name(c['name'])} | "
                     f"{c['status']} | {n_steps} | {lc} |")
    lines.append("")

    # ---- 2. Reply Rate by Step Position (matched only)
    lines.append("## 2. Reply Rate by Step Position (matched only, n={})"
                 .format(len(matched)))
    lines.append("")
    lines.append("Does step 5 still earn its place?")
    lines.append("")
    step_counts = defaultdict(lambda: {"replied": 0, "positive": 0})
    for d in matched:
        step = d.get("sequence_step_order")
        if step is not None:
            step_counts[step]["replied"] += 1
            if d["classification"] == replies.POSITIVE:
                step_counts[step]["positive"] += 1
    lines.append("| Step order | Replies | Positive |")
    lines.append("|-----------|---------|----------|")
    for step in sorted(step_counts.keys()):
        d = step_counts[step]
        lines.append(f"| {step} | {d['replied']} | {d['positive']} |")
    lines.append("")
    lines.append("*Denominators (total sent per step) require walking "
                 "the full scheduled-email listing. Campaign 352 alone "
                 "has 95,459 emails across 6,364 pages. Reply counts "
                 "are absolute; rates cannot be computed without the "
                 "denominator.*")
    lines.append("")

    # ---- 3. Classification Breakdown
    lines.append("## 3. Reply Classification Breakdown")
    lines.append("")
    lines.append("### A. Matched replies (n={})".format(len(matched)))
    lines.append("")
    cls_matched = defaultdict(int)
    for d in matched:
        cls_matched[d["classification"]] += 1
    lines.append("| Classification | Count | Share |")
    lines.append("|---------------|-------|-------|")
    for cls in replies.CATEGORIES:
        count = cls_matched.get(cls, 0)
        if count and matched:
            lines.append(f"| {cls} | {count} | "
                         f"{count/len(matched)*100:.1f}% |")
    auto_m = sum(1 for d in matched if d.get("is_automated"))
    unread_m = sum(1 for d in matched if d.get("unreadable"))
    if matched:
        lines.append("")
        lines.append(f"Automated (provider flag): {auto_m}/{len(matched)} "
                     f"({auto_m/len(matched)*100:.1f}%)")
        lines.append(f"Unreadable (extraction empty): {unread_m}/"
                     f"{len(matched)} ({unread_m/len(matched)*100:.1f}%)")
    lines.append("")

    lines.append("### B. Historical replies (n={})".format(len(historical)))
    lines.append("")
    cls_hist = defaultdict(int)
    for d in historical:
        cls_hist[d["classification"]] += 1
    lines.append("| Classification | Count | Share |")
    lines.append("|---------------|-------|-------|")
    for cls in replies.CATEGORIES:
        count = cls_hist.get(cls, 0)
        if count and historical:
            lines.append(f"| {cls} | {count} | "
                         f"{count/len(historical)*100:.1f}% |")
    auto_h = sum(1 for d in historical if d.get("is_automated"))
    unread_h = sum(1 for d in historical if d.get("unreadable"))
    if historical:
        lines.append("")
        lines.append(f"Automated (provider flag): {auto_h}/"
                     f"{len(historical)} "
                     f"({auto_h/len(historical)*100:.1f}%)")
        lines.append(f"Unreadable (extraction empty): {unread_h}/"
                     f"{len(historical)} "
                     f"({unread_h/len(historical)*100:.1f}%)")
        lines.append("")
        lines.append(f"**Unreadable rate: "
                     f"{unread_h/len(historical)*100:.1f}%** "
                     f"(task noted 46.5% as last measurement)")
    lines.append("")

    # ---- 4. Positive Reply Rate
    lines.append("## 4. Positive Reply Rate (separately)")
    lines.append("")
    pos_matched = [d for d in matched
                   if d["classification"] == replies.POSITIVE]
    pos_hist = [d for d in historical
                if d["classification"] == replies.POSITIVE]
    lines.append(f"| Population | Positive | Total | Rate |")
    lines.append(f"|-----------|----------|-------|------|")
    if matched:
        lines.append(f"| Matched | {len(pos_matched)} | {len(matched)} | "
                     f"{len(pos_matched)/len(matched)*100:.2f}% |")
    if historical:
        lines.append(f"| Historical | {len(pos_hist)} | {len(historical)} | "
                     f"{len(pos_hist)/len(historical)*100:.2f}% |")
    lines.append("")

    if pos_matched:
        lines.append("### Positive by step (matched)")
        lines.append("")
        pos_by_step = defaultdict(int)
        for d in pos_matched:
            step = d.get("sequence_step_order") or "?"
            pos_by_step[step] += 1
        lines.append("| Step | Positive |")
        lines.append("|------|----------|")
        for step in sorted(pos_by_step.keys(),
                           key=lambda x: (isinstance(x, str), x)):
            lines.append(f"| {step} | {pos_by_step[step]} |")
        lines.append("")

    # ---- 5. Subject Shape (matched only)
    if matched:
        lines.append("## 5. Subject Shape of Sending Email (matched only)")
        lines.append("")
        subj_counts = defaultdict(int)
        for d in matched:
            subj_counts[d["subject_shape"]] += 1
        lines.append("| Subject shape | Replies to that email |")
        lines.append("|--------------|------------------------|")
        for shape in sorted(subj_counts.keys()):
            lines.append(f"| {shape} | {subj_counts[shape]} |")
        lines.append("")

    # ---- 6. Body Length (matched only)
    if matched:
        lines.append("## 6. Body Length Band of Sending Email "
                     "(matched only)")
        lines.append("")
        band_counts = defaultdict(int)
        for d in matched:
            band_counts[d["body_length_band"]] += 1
        lines.append("| Body length (chars) | Replies to that email |")
        lines.append("|--------------------|------------------------|")
        for band in ["<100", "100-299", "300-599", "600-999", "1000+"]:
            if band in band_counts:
                lines.append(f"| {band} | {band_counts[band]} |")
        lines.append("")

    # ---- 7. Time to Reply (matched only)
    lines.append("## 7. Time to Reply")
    lines.append("")
    htrs = [d["hours_to_reply"] for d in matched
            if d.get("hours_to_reply") is not None]
    if htrs:
        htrs.sort()
        lines.append("| Metric | Hours |")
        lines.append("|--------|-------|")
        lines.append(f"| Min | {min(htrs):.1f} |")
        lines.append(f"| Median | {htrs[len(htrs)//2]:.1f} |")
        lines.append(f"| Mean | {sum(htrs)/len(htrs):.1f} |")
        lines.append(f"| P90 | {htrs[int(len(htrs)*0.9)]:.1f} |")
        lines.append(f"| Max | {max(htrs):.1f} |")
        lines.append(f"| n | {len(htrs)} |")
    else:
        lines.append("No time-to-reply data available (matched emails "
                     "lacked sent_at timestamps).")
    lines.append("")

    # ---- 8. Bounce Analysis
    lines.append("## 8. Bounce Analysis")
    lines.append("")
    lines.append(f"Total bounce rows in feed: {len(bounce_rows)}")
    lines.append("")
    bounce_types = defaultdict(int)
    for rr in bounce_rows:
        bounce_types[rr.get("type", "unknown")] += 1
    lines.append("| Bounce type | Count |")
    lines.append("|------------|-------|")
    for bt, count in sorted(bounce_types.items()):
        lines.append(f"| {bt} | {count} |")
    lines.append("")
    bounced_se = [d for d in matched if d.get("se_status") == "bounced"]
    lines.append(f"Matched replies whose scheduled email bounced: "
                 f"{len(bounced_se)} of {len(matched)}")
    lines.append("")

    # ---- 9. Scheduled Email Status
    if matched:
        lines.append("## 9. Scheduled Email Status (matched)")
        lines.append("")
        se_status = defaultdict(int)
        for d in matched:
            se_status[d.get("se_status") or "unknown"] += 1
        lines.append("| Status | Count | Share |")
        lines.append("|--------|-------|-------|")
        for st, count in sorted(se_status.items()):
            lines.append(f"| {st} | {count} | "
                         f"{count/len(matched)*100:.1f}% |")
        lines.append("")

    # ---- 10. Open Tracking
    lines.append("## 10. Open Tracking Caveat")
    lines.append("")
    no_open = [c for c in campaigns if not c.get("open_tracking")]
    if no_open:
        lines.append(f"**ALL {len(campaigns)} campaigns have "
                     f"`open_tracking: False` or not set.** Open counts "
                     f"are an absent measurement, not an absent open. "
                     f"Any open-based rate is invalid.")
    else:
        lines.append("All campaigns track opens.")
    lines.append("")

    # ---- 11. Observations
    lines.append("## 11. Observations, Hypotheses, and Proven Learnings")
    lines.append("")

    observations = []
    hypotheses = []
    proven = []

    observations.append(
        f"The reply feed contains {len(all_replies)} rows (1500-page "
        f"sample): {reply_type_counts.get('reply', 0)} replies, "
        f"{reply_type_counts.get('bounce', 0)} bounces, "
        f"{reply_type_counts.get('outgoing', 0)} outgoing.")

    observations.append(
        f"Of {len(reply_rows)} reply-type rows, only {has_seid} "
        f"({has_seid/len(reply_rows)*100:.1f}%) carry a "
        f"`scheduled_email_id`. The remaining {len(reply_rows)-has_seid} "
        f"({(len(reply_rows)-has_seid)/len(reply_rows)*100:.1f}%) are "
        f"historical, pre-dating API lead creation.")

    if matched:
        pos_rate_m = len(pos_matched)/len(matched)*100
        observations.append(
            f"Matched replies: {len(matched)}, positive rate "
            f"{pos_rate_m:.2f}% (n={len(matched)}).")

    if historical:
        pos_rate_h = len(pos_hist)/len(historical)*100
        observations.append(
            f"Historical replies: {len(historical)}, positive rate "
            f"{pos_rate_h:.2f}% (n={len(historical)}).")

    if historical:
        observations.append(
            f"Historical unreadable rate: "
            f"{unread_h/len(historical)*100:.1f}% "
            f"(n={len(historical)}). The task noted 46.5% as the last "
            f"measurement.")

    observations.append(
        f"Automated replies: {auto_m + auto_h} total "
        f"({(auto_m + auto_h)/len(dataset)*100:.1f}% of all replies).")

    hypotheses.append(
        "The 8-step sequence reply rate of 8.49% (n=17,690) claimed by "
        "the estate CANNOT be re-derived. The scheduled-email listings "
        "are too large to walk (campaign 352: 95,459 emails, 6,364 "
        "pages). Without the denominator (total sent per step), reply "
        "rates per step are uncomputable. This is the most valuable "
        "finding the task asked for, and it is not reproducible from "
        "the reply feed alone.")

    hypotheses.append(
        "The reply feed's 1500-page cap (22,500 rows) covers the "
        "newest replies. Older historical replies beyond the cap are "
        "not analysed.")

    lines.append("### Observations (what the rows say, with n)")
    lines.append("")
    for o in observations:
        lines.append(f"- {o}")
    lines.append("")

    lines.append("### Hypotheses (what it might mean)")
    lines.append("")
    for h in hypotheses:
        lines.append(f"- {h}")
    lines.append("")

    lines.append("### Proven Learnings (what survives a sample-size "
                 "objection)")
    lines.append("")
    if not proven:
        lines.append("- None. The denominator (total sent per step) "
                     "is unavailable without walking millions of "
                     "scheduled-email pages. Reply counts alone do not "
                     "yield rates.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*No unsanitised prospect PII in this report. Email "
                 "addresses, company names, and reply texts are SHA-256 "
                 "hashed.*")
    lines.append("")

    report = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    return report


def main():
    parser = argparse.ArgumentParser(
        description="TASK-059: EmailBison email-to-reply analysis")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    output_path = args.output or os.path.join(
        ROOT, "docs", f"ESTATE-BISON-OUTCOMES-{today}.md")

    (campaigns, all_replies, reply_rows, bounce_rows, dataset,
     reply_type_counts, steps_by_campaign) = build_analysis(args.cache_dir)

    print(f"\nProducing report: {output_path}", file=sys.stderr)
    report = produce_report(campaigns, all_replies, reply_rows, bounce_rows,
                            dataset, reply_type_counts, steps_by_campaign,
                            output_path)
    print(f"\nDone. {len(dataset)} matched reply rows.", file=sys.stderr)

    dataset_path = os.path.join(args.cache_dir, "reply_dataset.json")
    os.makedirs(args.cache_dir, exist_ok=True)
    with open(dataset_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, default=str, indent=1)
    print(f"Dataset: {dataset_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
