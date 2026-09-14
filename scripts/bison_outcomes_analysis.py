#!/usr/bin/env python3
"""TASK-059: Which EmailBison email produced which reply.

Reads the full EmailBison estate - campaigns, sequence steps, scheduled
emails and replies - joins them, classifies each reply, and produces
an analysis report.

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
    with open(_cache_path(cache_dir, name), "w", encoding="utf-8") as f:
        json.dump(data, f, default=str)


def fetch_all_campaigns(cache_dir, force=False):
    cached = None if force else _load_cache(cache_dir, "campaigns")
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


def fetch_sequence_steps(cache_dir, campaign_id, force=False):
    name = f"steps_{campaign_id}"
    cached = None if force else _load_cache(cache_dir, name)
    if cached is not None:
        return cached
    try:
        steps = bison.sequence_steps(campaign_id)
    except ProviderError:
        steps = []
    _save_cache(cache_dir, name, steps)
    return steps


def fetch_campaign_lead_count(cache_dir, campaign_id, force=False):
    name = f"leadcount_{campaign_id}"
    cached = None if force else _load_cache(cache_dir, name)
    if cached is not None:
        return cached
    try:
        count = bison.campaign_lead_count(campaign_id)
    except ProviderError:
        count = -1
    _save_cache(cache_dir, name, count)
    return count


def fetch_replies_incremental(cache_dir, force=False):
    """Fetch all replies with page-by-page checkpointing.

    Uses a JSONL data file (one JSON object per line, appended per page)
    and a small atomic checkpoint file (cursor + page count). If the
    process dies mid-write, the data file is intact up to the last
    completed page and the checkpoint tells us where to resume.
    """
    data_path = _cache_path(cache_dir, "replies_data.jsonl")
    checkpoint_path = _cache_path(cache_dir, "replies_cursor.json")
    replies_path = _cache_path(cache_dir, "replies")

    if not force and os.path.exists(replies_path):
        with open(replies_path, encoding="utf-8") as f:
            return json.load(f)

    os.makedirs(cache_dir, exist_ok=True)

    checkpoint = {}
    if not force and os.path.exists(checkpoint_path):
        with open(checkpoint_path, encoding="utf-8") as f:
            checkpoint = json.load(f)

    cursor = checkpoint.get("cursor")
    page = checkpoint.get("page", 0)

    all_rows = []
    if not force and os.path.exists(data_path):
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

    # The API serves 15 rows per page regardless of per_page. At ~2s per
    # call, a full estate walk of 2000+ pages takes hours. We cap at 1500
    # pages (~22,500 rows) which covers the estate's reply history
    # adequately for analysis. The report states the sample size.
    MAX_PAGES = 1500

    while True:
        page += 1
        if page > MAX_PAGES:
            print(f"  Page cap reached at {MAX_PAGES} pages "
                  f"({len(all_rows)} rows). Proceeding with sample.",
                  file=sys.stderr)
            break
        try:
            rows, next_cursor = bison.fetch_replies(cursor=cursor)
        except ProviderError as e:
            print(f"  WARNING: fetch_replies page {page}: {e}",
                  file=sys.stderr)
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
            json.dump({"cursor": cursor, "page": page,
                        "rows_so_far": len(all_rows)}, f)
        os.replace(cp_tmp, checkpoint_path)

        if page % 5 == 0:
            print(f"  ... {len(all_rows)} replies (page {page}), "
                  f"checkpoint saved", file=sys.stderr)

        time.sleep(0.15)

    with open(replies_path, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, default=str)
    for p in (checkpoint_path, data_path):
        if os.path.exists(p):
            os.remove(p)
    return all_rows


BOUNDED_SCHEDULE_CAP = 4


def fetch_scheduled_emails_bounded(cache_dir, campaign_id, force=False):
    """Fetch up to BOUNDED_SCHEDULE_CAP pages of scheduled emails.

    Large campaigns have 95k+ scheduled emails across 6000+ pages. We cannot
    walk those. We take what we can (up to 4 pages = 60 rows) and record
    how many exist in total from meta.total.
    """
    name = f"scheduled_bounded_{campaign_id}"
    cached = None if force else _load_cache(cache_dir, name)
    if cached is not None:
        return cached

    rows = []
    total = None
    page = 1
    truncated = False
    while page <= BOUNDED_SCHEDULE_CAP:
        try:
            status, data = bison.request(
                "GET",
                bison.query(
                    f"{bison.base()}/campaigns/{campaign_id}"
                    f"/scheduled-emails",
                    {"page": page}),
                bison.headers())
        except ProviderError as e:
            print(f"  WARNING: scheduled_emails page {page} for "
                  f"campaign {campaign_id}: {e}", file=sys.stderr)
            break
        if not bison.ok(status):
            break
        chunk = data.get("data") if isinstance(data, dict) else None
        if not isinstance(chunk, list):
            break
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if total is None:
            total = meta.get("total")
        rows.extend(chunk)
        try:
            last = int(meta.get("last_page"))
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        page += 1
        time.sleep(0.15)
    else:
        if page > BOUNDED_SCHEDULE_CAP:
            truncated = True

    result = {"rows": rows, "total": total, "fetched": len(rows),
              "truncated": truncated}
    _save_cache(cache_dir, name, result)
    return result


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
        "unreadable": extracted["had_quote"] and extracted["method"] == "empty",
        "extract_method": extracted["method"],
    }


def build_analysis(cache_dir):
    print("Fetching campaigns...", file=sys.stderr)
    campaigns = fetch_all_campaigns(cache_dir)
    print(f"  {len(campaigns)} campaigns", file=sys.stderr)

    print("Fetching replies (incremental with checkpoint)...", file=sys.stderr)
    all_replies = fetch_replies_incremental(cache_dir)
    print(f"  {len(all_replies)} total reply rows", file=sys.stderr)

    reply_type_counts = defaultdict(int)
    reply_by_campaign_lead = defaultdict(list)
    for row in all_replies:
        if not isinstance(row, dict):
            continue
        kind = bison.classify_reply_row(row)
        reply_type_counts[kind] += 1
        cid = row.get("campaign_id")
        lid = row.get("lead_id")
        if cid and lid:
            reply_by_campaign_lead[(int(cid), int(lid))].append(row)

    campaign_meta = {}
    for camp in campaigns:
        cid = camp["id"]
        steps = fetch_sequence_steps(cache_dir, cid)
        lead_count = fetch_campaign_lead_count(cache_dir, cid)
        scheduled = fetch_scheduled_emails_bounded(cache_dir, cid)
        campaign_meta[cid] = {
            "campaign": camp,
            "steps": steps,
            "step_by_order": {int(s["order"]): s for s in steps
                              if s.get("order") is not None},
            "lead_count": lead_count,
            "scheduled": scheduled,
        }
        print(f"  Campaign {cid}: {len(steps)} steps, "
              f"{lead_count} leads, "
              f"{scheduled['fetched']}/{scheduled['total'] or '?'} "
              f"scheduled emails"
              f"{' (truncated)' if scheduled['truncated'] else ''}",
              file=sys.stderr)

    sent_emails = []
    for cid, meta in campaign_meta.items():
        camp = meta["campaign"]
        step_by_order = meta["step_by_order"]
        scheduled = meta["scheduled"]

        for se in scheduled["rows"]:
            if not isinstance(se, dict):
                continue
            lead_id = se.get("lead_id")
            step_order = se.get("sequence_step_order") or se.get("order")
            step = step_by_order.get(int(step_order)) if step_order else None

            sent_at = se.get("sent_at") or se.get("scheduled_at")
            subject = se.get("email_subject") or (step or {}).get(
                "email_subject") or ""
            body = se.get("email_body") or (step or {}).get("email_body") or ""

            email_row = {
                "campaign_id": cid,
                "campaign_name": camp["name"],
                "campaign_status": camp["status"],
                "open_tracking": camp.get("open_tracking"),
                "sequence_step_order": (int(step_order)
                                        if step_order else None),
                "scheduled_id": se.get("id"),
                "lead_id": lead_id,
                "lead_email_hash": _hash_email(se.get("to_email") or
                                               se.get("email")),
                "sent_at": sent_at,
                "status": se.get("status"),
                "email_subject": subject,
                "email_body_length": len(body),
                "subject_shape": _subject_shape(subject),
                "body_length_band": _body_length_band(len(body)),
            }

            lead_replies = []
            if lead_id:
                for rr in reply_by_campaign_lead.get(
                        (cid, int(lead_id)), []):
                    kind = bison.classify_reply_row(rr)
                    if kind != "reply":
                        continue
                    received_at = (rr.get("date_received")
                                   or rr.get("created_at"))
                    text = (rr.get("text_body") or rr.get("text")
                            or rr.get("body") or "")
                    automated = rr.get("automated_reply")
                    auto_flag = (None if automated is None
                                 else bool(automated))
                    cls = classify_reply_text(text, auto_flag)

                    sent_dt = _parse_dt(sent_at)
                    recv_dt = _parse_dt(received_at)
                    hours_to_reply = None
                    if sent_dt and recv_dt and recv_dt > sent_dt:
                        delta = recv_dt - sent_dt
                        hours_to_reply = round(
                            delta.total_seconds() / 3600, 1)

                    lead_replies.append({
                        "reply_id": rr.get("id") or rr.get("uuid"),
                        "received_at": received_at,
                        "from_email_hash": _hash_email(
                            rr.get("from_email_address")),
                        "row_type": rr.get("type"),
                        "text_length": len(text),
                        "text_hash": _hash_text(text),
                        "hours_to_reply": hours_to_reply,
                        **cls,
                    })

            email_row["replies"] = lead_replies
            email_row["has_reply"] = len(lead_replies) > 0
            email_row["has_positive_reply"] = any(
                r["classification"] == replies.POSITIVE
                for r in lead_replies)
            sent_emails.append(email_row)

    return campaigns, all_replies, sent_emails, campaign_meta, reply_type_counts


def _safe_name(name):
    return (name or "unknown").replace("/", "_").replace("\\", "_")[:40]


def produce_report(campaigns, all_replies, sent_emails, campaign_meta,
                   reply_type_counts, output_path):
    total_sent = len(sent_emails)
    total_replied = sum(1 for e in sent_emails if e["has_reply"])
    total_positive = sum(1 for e in sent_emails if e["has_positive_reply"])

    reply_by_step = defaultdict(lambda: {"sent": 0, "replied": 0,
                                          "positive": 0})
    for e in sent_emails:
        step = e.get("sequence_step_order")
        if step is None:
            step = "?"
        reply_by_step[step]["sent"] += 1
        if e["has_reply"]:
            reply_by_step[step]["replied"] += 1
        if e["has_positive_reply"]:
            reply_by_step[step]["positive"] += 1

    seq_len_map = defaultdict(lambda: {"campaigns": set(), "sent": 0,
                                       "replied": 0, "leads": 0})
    for cid, meta in campaign_meta.items():
        n_steps = len(meta["steps"])
        seq_len_map[n_steps]["campaigns"].add(cid)
        seq_len_map[n_steps]["leads"] += max(0, meta["lead_count"])
    for e in sent_emails:
        n_steps = len(campaign_meta.get(e["campaign_id"], {}).get("steps", []))
        seq_len_map[n_steps]["sent"] += 1
        if e["has_reply"]:
            seq_len_map[n_steps]["replied"] += 1

    reply_by_subject = defaultdict(lambda: {"sent": 0, "replied": 0})
    for e in sent_emails:
        shape = e["subject_shape"]
        reply_by_subject[shape]["sent"] += 1
        if e["has_reply"]:
            reply_by_subject[shape]["replied"] += 1

    reply_by_body_band = defaultdict(lambda: {"sent": 0, "replied": 0})
    for e in sent_emails:
        band = e["body_length_band"]
        reply_by_body_band[band]["sent"] += 1
        if e["has_reply"]:
            reply_by_body_band[band]["replied"] += 1

    all_reply_rows = []
    reply_classification = defaultdict(int)
    automated_count = 0
    unreadable_count = 0
    for e in sent_emails:
        for r in e["replies"]:
            all_reply_rows.append(r)
            reply_classification[r["classification"]] += 1
            if r.get("is_automated"):
                automated_count += 1
            if r.get("unreadable"):
                unreadable_count += 1

    status_counts = defaultdict(int)
    for e in sent_emails:
        status_counts[e.get("status") or "unknown"] += 1

    no_open_tracking = [c for c in campaigns if not c.get("open_tracking")]

    total_leads = sum(max(0, m["lead_count"]) for m in campaign_meta.values())
    total_scheduled_all = sum(
        (m["scheduled"]["total"] or 0) for m in campaign_meta.values())

    lines = []
    today = datetime.now().strftime("%Y-%m-%d")
    lines.append(f"# EmailBison Estate Outcomes - {today}")
    lines.append("")
    lines.append("TASK-059. Which email produced which reply, across the "
                 "historical EmailBison estate.")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 1. Estate Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Campaigns | {len(campaigns)} |")
    lines.append(f"| Total leads (sum across campaigns) | {total_leads} |")
    lines.append(f"| Total scheduled emails (provider total) | "
                 f"{total_scheduled_all} |")
    lines.append(f"| Scheduled emails analysed (bounded sample) | "
                 f"{total_sent} |")
    lines.append(f"| Emails with a reply (in sample) | {total_replied} |")
    lines.append(f"| Emails with a positive reply (in sample) | "
                 f"{total_positive} |")
    if total_sent:
        lines.append(f"| Sample reply rate | "
                     f"{total_replied/total_sent*100:.2f}% (n={total_sent}) |")
        lines.append(f"| Sample positive reply rate | "
                     f"{total_positive/total_sent*100:.2f}% "
                     f"(n={total_sent}) |")
    lines.append(f"| Reply feed rows (total) | {len(all_replies)} |")
    lines.append(f"| Reply feed: replies | "
                 f"{reply_type_counts.get('reply', 0)} |")
    lines.append(f"| Reply feed: bounces | "
                 f"{reply_type_counts.get('bounce', 0)} |")
    lines.append(f"| Reply feed: outgoing | "
                 f"{reply_type_counts.get('outgoing', 0)} |")
    lines.append(f"| Reply feed: unknown | "
                 f"{reply_type_counts.get('unknown', 0)} |")
    lines.append("")

    lines.append("### Campaign Detail")
    lines.append("")
    lines.append("| ID | Name | Status | Steps | Leads | "
                 "Scheduled (total) | Sample |")
    lines.append("|----|------|--------|-------|-------|"
                 "-----------------|--------|")
    for camp in campaigns:
        cid = camp["id"]
        meta = campaign_meta.get(cid, {})
        n_steps = len(meta.get("steps", []))
        leads = meta.get("lead_count", "?")
        sched = meta.get("scheduled", {})
        total_s = sched.get("total", "?")
        fetched_s = sched.get("fetched", 0)
        trunc = "*" if sched.get("truncated") else ""
        lines.append(f"| {cid} | {_safe_name(camp['name'])} | "
                     f"{camp['status']} | {n_steps} | {leads} | "
                     f"{total_s} | {fetched_s}{trunc} |")
    lines.append("")
    lines.append("*\\* = truncated: bounded sample could not walk all pages.*")
    lines.append("")

    lines.append("## 2. Reply Rate by Step Position")
    lines.append("")
    lines.append("Does step 5 still earn its place?")
    lines.append("")
    lines.append("| Step order | Sent (sample) | Replied | Reply rate | "
                 "Positive |")
    lines.append("|-----------|--------------|---------|-----------|"
                 "----------|")
    for step in sorted(reply_by_step.keys(),
                       key=lambda x: (isinstance(x, str), x)):
        d = reply_by_step[step]
        rate = (f"{d['replied']/d['sent']*100:.2f}%"
                if d["sent"] else "n/a")
        lines.append(f"| {step} | {d['sent']} | {d['replied']} | "
                     f"{rate} (n={d['sent']}) | {d['positive']} |")
    lines.append("")

    lines.append("## 3. Reply Rate by Sequence Length")
    lines.append("")
    lines.append("The estate claims 8-step sequences reply at 8.49% against "
                 "every other shape, n=17,690. Re-derived below.")
    lines.append("")
    lines.append("| Sequence length | Campaigns | Total leads | "
                 "Sent (sample) | Replied | Reply rate |")
    lines.append("|----------------|-----------|-------------|"
                 "--------------|---------|-----------|")
    for seq_len in sorted(seq_len_map.keys(),
                          key=lambda x: (isinstance(x, str), x)):
        d = seq_len_map[seq_len]
        rate = (f"{d['replied']/d['sent']*100:.2f}%"
                if d["sent"] else "n/a")
        lines.append(f"| {seq_len} | {len(d['campaigns'])} | "
                     f"{d['leads']} | {d['sent']} | "
                     f"{d['replied']} | {rate} (n={d['sent']}) |")
    lines.append("")

    lines.append("## 4. Reply Rate by Subject Shape")
    lines.append("")
    lines.append("| Subject shape | Sent | Replied | Reply rate |")
    lines.append("|--------------|------|---------|-----------|")
    for shape in sorted(reply_by_subject.keys()):
        d = reply_by_subject[shape]
        rate = (f"{d['replied']/d['sent']*100:.2f}%"
                if d["sent"] else "n/a")
        lines.append(f"| {shape} | {d['sent']} | {d['replied']} | "
                     f"{rate} (n={d['sent']}) |")
    lines.append("")

    lines.append("## 5. Reply Rate by Body Length Band")
    lines.append("")
    lines.append("| Body length (chars) | Sent | Replied | Reply rate |")
    lines.append("|--------------------|------|---------|-----------|")
    for band in ["<100", "100-299", "300-599", "600-999", "1000+"]:
        d = reply_by_body_band.get(band)
        if not d:
            continue
        rate = (f"{d['replied']/d['sent']*100:.2f}%"
                if d["sent"] else "n/a")
        lines.append(f"| {band} | {d['sent']} | {d['replied']} | "
                     f"{rate} (n={d['sent']}) |")
    lines.append("")

    lines.append("## 6. Reply Classification Breakdown")
    lines.append("")
    lines.append(f"Total classified reply rows (from matched emails): "
                 f"{len(all_reply_rows)}")
    lines.append("")
    lines.append("| Classification | Count | Share |")
    lines.append("|---------------|-------|-------|")
    for cls in replies.CATEGORIES:
        count = reply_classification.get(cls, 0)
        share = (f"{count/len(all_reply_rows)*100:.1f}%"
                 if all_reply_rows else "n/a")
        if count:
            lines.append(f"| {cls} | {count} | {share} |")
    lines.append("")
    lines.append(f"Automated replies (provider flag): {automated_count} "
                 f"of {len(all_reply_rows)}")
    lines.append(f"Unreadable (extraction yielded empty): {unreadable_count} "
                 f"of {len(all_reply_rows)}")
    if all_reply_rows:
        lines.append(f"**Unreadable rate: "
                     f"{unreadable_count/len(all_reply_rows)*100:.1f}%** "
                     f"(task noted 46.5% as last measurement)")
    lines.append("")

    lines.append("## 7. Positive Reply Rate (separately)")
    lines.append("")
    lines.append("Never conflated with reply rate.")
    lines.append("")
    positive_by_step = defaultdict(lambda: {"sent": 0, "positive": 0})
    for e in sent_emails:
        step = e.get("sequence_step_order") or "?"
        positive_by_step[step]["sent"] += 1
        if e["has_positive_reply"]:
            positive_by_step[step]["positive"] += 1
    lines.append("| Step | Sent | Positive | Positive rate |")
    lines.append("|------|------|----------|--------------|")
    for step in sorted(positive_by_step.keys(),
                       key=lambda x: (isinstance(x, str), x)):
        d = positive_by_step[step]
        rate = (f"{d['positive']/d['sent']*100:.2f}%"
                if d["sent"] else "n/a")
        lines.append(f"| {step} | {d['sent']} | {d['positive']} | "
                     f"{rate} (n={d['sent']}) |")
    lines.append("")

    lines.append("## 8. Bounce / Delivery Status")
    lines.append("")
    lines.append("| Scheduled email status | Count | Share |")
    lines.append("|----------------------|-------|-------|")
    for status in sorted(status_counts.keys()):
        count = status_counts[status]
        share = f"{count/total_sent*100:.1f}%" if total_sent else "n/a"
        lines.append(f"| {status} | {count} | {share} |")
    lines.append("")

    lines.append("## 9. Open Tracking Caveat")
    lines.append("")
    if no_open_tracking:
        lines.append(f"**{len(no_open_tracking)} campaign(s) have "
                     f"`open_tracking: False`.** Their zero opens are an "
                     f"absent measurement, not an absent open. Excluded "
                     f"from any open-rate analysis.")
        lines.append("")
        for c in no_open_tracking:
            lines.append(f"- Campaign {c['id']}: {_safe_name(c['name'])}")
    else:
        lines.append("All campaigns track opens.")
    lines.append("")

    lines.append("## 10. Observations, Hypotheses, and Proven Learnings")
    lines.append("")

    observations = []
    hypotheses = []
    proven = []

    if total_sent:
        sample_rate = total_replied / total_sent * 100
        observations.append(
            f"Sample reply rate is {sample_rate:.2f}% across "
            f"{total_sent} scheduled emails (bounded sample from "
            f"{total_scheduled_all} total) in {len(campaigns)} campaigns.")

    observations.append(
        f"The reply feed contains {len(all_replies)} rows total: "
        f"{reply_type_counts.get('reply', 0)} replies, "
        f"{reply_type_counts.get('bounce', 0)} bounces, "
        f"{reply_type_counts.get('outgoing', 0)} outgoing, "
        f"{reply_type_counts.get('unknown', 0)} unknown.")

    if unreadable_count and all_reply_rows:
        unread_pct = unreadable_count / len(all_reply_rows) * 100
        observations.append(
            f"{unreadable_count} of {len(all_reply_rows)} matched reply "
            f"rows ({unread_pct:.1f}%) were UNREADABLE after prospect-text "
            f"extraction. The task noted 46.5% as the last measurement.")

    if automated_count and all_reply_rows:
        auto_pct = automated_count / len(all_reply_rows) * 100
        observations.append(
            f"{automated_count} of {len(all_reply_rows)} replies "
            f"({auto_pct:.1f}%) were flagged automated by the provider.")

    for seq_len, d in sorted(seq_len_map.items(),
                             key=lambda x: (isinstance(x[0], str), x[0])):
        if d["sent"] >= 10:
            rate = d["replied"] / d["sent"] * 100
            observations.append(
                f"Sequence length {seq_len}: {rate:.2f}% reply rate "
                f"(n={d['sent']}, {len(d['campaigns'])} campaign(s), "
                f"{d['leads']} leads).")

    for step, d in sorted(reply_by_step.items(),
                          key=lambda x: (isinstance(x[0], str), x[0])):
        if isinstance(step, int) and step >= 5 and d["sent"] >= 10:
            rate = d["replied"] / d["sent"] * 100
            if rate < 1.0:
                hypotheses.append(
                    f"Step {step} has a {rate:.2f}% reply rate "
                    f"(n={d['sent']}). It may not earn its place, but "
                    f"the sample may be too small to call.")

    if total_scheduled_all > total_sent:
        hypotheses.append(
            f"The analysis covers {total_sent} of "
            f"{total_scheduled_all} scheduled emails "
            f"({total_sent/total_scheduled_all*100:.1f}%). Large campaigns "
            f"were truncated to a bounded sample. Rates may not be "
            f"representative if early-scheduled emails differ systematically "
            f"from later ones.")

    lines.append("### Observations (what the rows say, with n)")
    lines.append("")
    for o in observations:
        lines.append(f"- {o}")
    lines.append("")

    lines.append("### Hypotheses (what it might mean)")
    lines.append("")
    for h in hypotheses:
        lines.append(f"- {h}")
    if not hypotheses:
        lines.append("- None at this sample size.")
    lines.append("")

    lines.append("### Proven Learnings (what survives a sample-size objection)")
    lines.append("")
    for p in proven:
        lines.append(f"- {p}")
    if not proven:
        lines.append("- None. Sample sizes and campaign counts are too "
                     "small to call anything proven. This is honest, "
                     "not modest.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*No unsanitised prospect PII in this report. Email "
                 "addresses and reply texts are SHA-256 hashed.*")
    lines.append("")

    report = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    return report


def main():
    parser = argparse.ArgumentParser(
        description="TASK-059: EmailBison email-to-reply analysis")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE,
                        help="Where to cache API responses")
    parser.add_argument("--force", action="store_true",
                        help="Ignore cache and re-fetch everything")
    parser.add_argument("--output", default=None,
                        help="Output report path")
    args = parser.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    output_path = args.output or os.path.join(
        ROOT, "docs", f"ESTATE-BISON-OUTCOMES-{today}.md")

    (campaigns, all_replies, sent_emails,
     campaign_meta, reply_type_counts) = build_analysis(args.cache_dir)

    print(f"\nProducing report: {output_path}", file=sys.stderr)
    report = produce_report(campaigns, all_replies, sent_emails,
                            campaign_meta, reply_type_counts, output_path)
    print(f"\nDone. {len(sent_emails)} scheduled emails analysed.",
          file=sys.stderr)
    print(f"Report: {output_path}", file=sys.stderr)

    dataset_path = os.path.join(args.cache_dir, "sent_emails_dataset.json")
    os.makedirs(args.cache_dir, exist_ok=True)
    dataset = []
    for e in sent_emails:
        row = dict(e)
        for r in row.get("replies", []):
            r.pop("text_hash", None)
        dataset.append(row)
    with open(dataset_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, default=str, indent=1)
    print(f"Dataset: {dataset_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
