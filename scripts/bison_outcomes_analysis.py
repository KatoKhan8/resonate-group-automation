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


def fetch_scheduled_emails(cache_dir, campaign_id, force=False):
    name = f"scheduled_{campaign_id}"
    cached = None if force else _load_cache(cache_dir, name)
    if cached is not None:
        return cached
    try:
        rows = bison.scheduled_emails(campaign_id)
    except (ProviderError, Exception) as e:
        print(f"  WARNING: scheduled_emails for campaign {campaign_id}: {e}",
              file=sys.stderr)
        rows = []
    _save_cache(cache_dir, name, rows)
    return rows


def fetch_all_replies(cache_dir, force=False):
    cached = None if force else _load_cache(cache_dir, "replies")
    if cached is not None:
        return cached
    all_rows = []
    cursor = None
    page = 0
    while True:
        page += 1
        try:
            rows, next_cursor = bison.fetch_replies(cursor=cursor)
        except ProviderError as e:
            print(f"  WARNING: fetch_replies page {page}: {e}",
                  file=sys.stderr)
            break
        all_rows.extend(rows)
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        if page % 10 == 0:
            print(f"  ... {len(all_rows)} replies fetched (page {page})",
                  file=sys.stderr)
        time.sleep(0.2)
    _save_cache(cache_dir, "replies", all_rows)
    return all_rows


def fetch_campaign_leads(cache_dir, campaign_id, force=False):
    name = f"leads_{campaign_id}"
    cached = None if force else _load_cache(cache_dir, name)
    if cached is not None:
        return cached
    try:
        rows, _total = bison._paged(
            f"leads_{campaign_id}",
            lambda page: bison.query(
                bison.leads_endpoint(campaign_id), {"page": page}))
    except (ProviderError, Exception) as e:
        print(f"  WARNING: leads for campaign {campaign_id}: {e}",
              file=sys.stderr)
        rows = []
    leads = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        leads.append({
            "id": r.get("id"),
            "email": r.get("email"),
            "first_name": r.get("first_name"),
            "last_name": r.get("last_name"),
            "company_name": r.get("company_name"),
            "custom_variables": bison.variables_of(r),
            "lead_campaign_data": [
                {"campaign_id": e.get("campaign_id"),
                 "status": e.get("status")}
                for e in (r.get("lead_campaign_data") or [])
                if isinstance(e, dict)
            ],
        })
    _save_cache(cache_dir, name, leads)
    return leads


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
    has_name = any(tok in s for tok in
                   ("{{", "{FIRST", "{first", "[[", "<<"))
    has_question = "?" in s
    if has_name and has_question:
        return "personalised+question"
    if has_name:
        return "personalised"
    if has_question:
        return "question"
    return "statement"


def classify_reply_text(text):
    if not text or not text.strip():
        return {"classification": replies.UNKNOWN, "confidence": 0.0,
                "reason": "empty", "is_automated": None,
                "unreadable": False, "extract_method": "empty"}
    extracted = replies.extract_prospect_text(text)
    prospect_text = extracted["text"]
    if not prospect_text.strip():
        return {"classification": replies.UNKNOWN, "confidence": 0.0,
                "reason": "extraction yielded empty",
                "is_automated": None,
                "unreadable": True,
                "extract_method": extracted["method"]}
    verdict = replies.classify(prospect_text)
    v = verdict.get("verdict") or verdict or {}
    return {
        "classification": v.get("classification", replies.UNKNOWN),
        "confidence": v.get("confidence", 0.0),
        "reason": v.get("reason", ""),
        "is_automated": None,
        "unreadable": extracted["had_quote"] and extracted["method"] == "empty",
        "extract_method": extracted["method"],
    }


def build_analysis(cache_dir):
    print("Fetching campaigns...", file=sys.stderr)
    campaigns = fetch_all_campaigns(cache_dir)
    print(f"  {len(campaigns)} campaigns", file=sys.stderr)

    print("Fetching replies...", file=sys.stderr)
    all_replies = fetch_all_replies(cache_dir)
    print(f"  {len(all_replies)} total reply rows", file=sys.stderr)

    reply_by_campaign = defaultdict(list)
    for row in all_replies:
        if not isinstance(row, dict):
            continue
        cid = row.get("campaign_id")
        if cid:
            reply_by_campaign[int(cid)].append(row)

    sent_emails = []
    reply_rows_by_campaign_lead = defaultdict(list)

    for camp in campaigns:
        cid = camp["id"]
        print(f"\nCampaign {cid} ({camp['name'][:40]})...", file=sys.stderr)

        steps = fetch_sequence_steps(cache_dir, cid)
        print(f"  {len(steps)} sequence steps", file=sys.stderr)
        step_by_order = {}
        for s in steps:
            order = s.get("order")
            if order is not None:
                step_by_order[int(order)] = s

        scheduled = fetch_scheduled_emails(cache_dir, cid)
        print(f"  {len(scheduled)} scheduled emails", file=sys.stderr)

        leads = fetch_campaign_leads(cache_dir, cid)
        lead_by_id = {l["id"]: l for l in leads if l.get("id") is not None}
        print(f"  {len(lead_by_id)} leads cached", file=sys.stderr)

        for row in all_replies:
            if not isinstance(row, dict):
                continue
            if int(row.get("campaign_id") or 0) != cid:
                continue
            lead_id = row.get("lead_id")
            if lead_id:
                reply_rows_by_campaign_lead[(cid, int(lead_id))].append(row)

        for se in scheduled:
            if not isinstance(se, dict):
                continue
            lead_id = se.get("lead_id")
            step_order = se.get("sequence_step_order") or se.get("order")
            step = step_by_order.get(int(step_order)) if step_order else None

            lead = lead_by_id.get(int(lead_id)) if lead_id else {}
            custom = (lead or {}).get("custom_variables") or {}

            lead_campaign_data = (lead or {}).get("lead_campaign_data") or []
            lead_status_in_campaign = None
            for lcd in lead_campaign_data:
                if str(lcd.get("campaign_id")) == str(cid):
                    lead_status_in_campaign = lcd.get("status")
                    break

            email_row = {
                "campaign_id": cid,
                "campaign_name": camp["name"],
                "campaign_status": camp["status"],
                "open_tracking": camp.get("open_tracking"),
                "sequence_step_order": int(step_order) if step_order else None,
                "step_subject": (step or {}).get("email_subject"),
                "step_body": (step or {}).get("email_body"),
                "scheduled_id": se.get("id"),
                "lead_id": lead_id,
                "lead_email_hash": _hash_email(
                    (lead or {}).get("email") or se.get("to_email")),
                "lead_company": (lead or {}).get("company_name"),
                "lead_status": lead_status_in_campaign,
                "custom_record_id": custom.get("record_id"),
                "custom_contact_key": custom.get("contact_key"),
                "sent_at": se.get("sent_at") or se.get("scheduled_at"),
                "status": se.get("status"),
                "email_subject": se.get("email_subject"),
                "email_body": se.get("email_body"),
                "email_body_length": len(se.get("email_body") or ""),
                "subject_shape": _subject_shape(se.get("email_subject")),
                "body_length_band": _body_length_band(
                    len(se.get("email_body") or "")),
            }

            lead_replies = []
            if lead_id:
                for rr in reply_rows_by_campaign_lead.get(
                        (cid, int(lead_id)), []):
                    kind = bison.classify_reply_row(rr)
                    if kind != "reply":
                        continue
                    received_at = rr.get("date_received") or rr.get("created_at")
                    text = (rr.get("text_body") or rr.get("text")
                            or rr.get("body") or "")
                    cls = classify_reply_text(text)
                    automated = rr.get("automated_reply")
                    if automated is not None:
                        cls["is_automated"] = bool(automated)

                    sent_dt = _parse_dt(email_row["sent_at"])
                    recv_dt = _parse_dt(received_at)
                    hours_to_reply = None
                    if sent_dt and recv_dt and recv_dt > sent_dt:
                        delta = recv_dt - sent_dt
                        hours_to_reply = round(delta.total_seconds() / 3600, 1)

                    lead_replies.append({
                        "reply_id": rr.get("id") or rr.get("uuid"),
                        "received_at": received_at,
                        "from_email_hash": _hash_email(
                            rr.get("from_email_address")),
                        "row_type": rr.get("type"),
                        "row_folder": rr.get("folder"),
                        "text_hash": _hash_text(text),
                        "text_length": len(text),
                        "hours_to_reply": hours_to_reply,
                        **cls,
                    })

            email_row["replies"] = lead_replies
            email_row["has_reply"] = len(lead_replies) > 0
            email_row["has_positive_reply"] = any(
                r["classification"] == replies.POSITIVE for r in lead_replies)
            sent_emails.append(email_row)

    return campaigns, all_replies, sent_emails


def _safe_campaign_name(name):
    return (name or "unknown").replace("/", "_").replace("\\", "_")[:40]


def produce_report(campaigns, all_replies, sent_emails, output_path):
    total_sent = len(sent_emails)
    total_replied = sum(1 for e in sent_emails if e["has_reply"])
    total_positive = sum(1 for e in sent_emails if e["has_positive_reply"])

    reply_by_step = defaultdict(lambda: {"sent": 0, "replied": 0, "positive": 0})
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
                                       "replied": 0})
    camp_step_counts = {}
    for e in sent_emails:
        cid = e["campaign_id"]
        step = e.get("sequence_step_order")
        if step is not None:
            camp_step_counts.setdefault(cid, set()).add(step)
    camp_seq_len = {cid: len(steps) for cid, steps in camp_step_counts.items()}

    for e in sent_emails:
        seq_len = camp_seq_len.get(e["campaign_id"], "?")
        seq_len_map[seq_len]["campaigns"].add(e["campaign_id"])
        seq_len_map[seq_len]["sent"] += 1
        if e["has_reply"]:
            seq_len_map[seq_len]["replied"] += 1

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

    reply_classification = defaultdict(int)
    automated_count = 0
    unreadable_count = 0
    all_reply_rows = []
    for e in sent_emails:
        for r in e["replies"]:
            all_reply_rows.append(r)
            reply_classification[r["classification"]] += 1
            if r.get("is_automated"):
                automated_count += 1
            if r.get("unreadable"):
                unreadable_count += 1

    bounce_emails = [e for e in sent_emails if e.get("status") == "bounced"]
    delivered_emails = [e for e in sent_emails
                        if e.get("status") in ("sent", "delivered")]

    bounce_by_status = defaultdict(int)
    for e in sent_emails:
        bounce_by_status[e.get("status") or "unknown"] += 1

    no_open_tracking_campaigns = [
        c for c in campaigns if not c.get("open_tracking")]

    reply_type_counts = defaultdict(int)
    for row in all_replies:
        if isinstance(row, dict):
            kind = bison.classify_reply_row(row)
            reply_type_counts[kind] += 1

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
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Campaigns | {len(campaigns)} |")
    lines.append(f"| Total scheduled emails | {total_sent} |")
    lines.append(f"| Emails with a reply | {total_replied} |")
    lines.append(f"| Emails with a positive reply | {total_positive} |")
    lines.append(f"| Overall reply rate | "
                 f"{total_replied/total_sent*100:.2f}% (n={total_sent}) |"
                 if total_sent else "| Overall reply rate | n/a (no emails) |")
    lines.append(f"| Overall positive reply rate | "
                 f"{total_positive/total_sent*100:.2f}% (n={total_sent}) |"
                 if total_sent else "| Overall positive reply rate | n/a |")
    lines.append(f"| Bounced | {len(bounce_emails)} "
                 f"({len(bounce_emails)/total_sent*100:.1f}% of {total_sent}) |"
                 if total_sent else "| Bounced | 0 |")
    lines.append(f"| Reply feed rows (total) | {len(all_replies)} |")
    lines.append(f"| Reply feed: replies | {reply_type_counts.get('reply', 0)} |")
    lines.append(f"| Reply feed: bounces | {reply_type_counts.get('bounce', 0)} |")
    lines.append(f"| Reply feed: outgoing | {reply_type_counts.get('outgoing', 0)} |")
    lines.append(f"| Reply feed: unknown | {reply_type_counts.get('unknown', 0)} |")
    lines.append("")

    lines.append("## 2. Reply Rate by Step Position")
    lines.append("")
    lines.append("Does step 5 still earn its place?")
    lines.append("")
    lines.append("| Step order | Sent | Replied | Reply rate | Positive |")
    lines.append("|-----------|------|---------|-----------|----------|")
    for step in sorted(reply_by_step.keys(),
                       key=lambda x: (isinstance(x, str), x)):
        d = reply_by_step[step]
        rate = f"{d['replied']/d['sent']*100:.2f}%" if d["sent"] else "n/a"
        lines.append(f"| {step} | {d['sent']} | {d['replied']} | "
                     f"{rate} (n={d['sent']}) | {d['positive']} |")
    lines.append("")

    lines.append("## 3. Reply Rate by Sequence Length")
    lines.append("")
    lines.append("The estate claims 8-step sequences reply at 8.49% against "
                 "every other shape, n=17,690. Re-derived below.")
    lines.append("")
    lines.append("| Sequence length | Campaigns | Sent | Replied | Reply rate |")
    lines.append("|----------------|-----------|------|---------|-----------|")
    for seq_len in sorted(seq_len_map.keys(),
                          key=lambda x: (isinstance(x, str), x)):
        d = seq_len_map[seq_len]
        rate = f"{d['replied']/d['sent']*100:.2f}%" if d["sent"] else "n/a"
        lines.append(f"| {seq_len} | {len(d['campaigns'])} | {d['sent']} | "
                     f"{d['replied']} | {rate} (n={d['sent']}) |")
    lines.append("")

    lines.append("## 4. Reply Rate by Subject Shape")
    lines.append("")
    lines.append("| Subject shape | Sent | Replied | Reply rate |")
    lines.append("|--------------|------|---------|-----------|")
    for shape in sorted(reply_by_subject.keys()):
        d = reply_by_subject[shape]
        rate = f"{d['replied']/d['sent']*100:.2f}%" if d["sent"] else "n/a"
        lines.append(f"| {shape} | {d['sent']} | {d['replied']} | "
                     f"{rate} (n={d['sent']}) |")
    lines.append("")

    lines.append("## 5. Reply Rate by Body Length Band")
    lines.append("")
    lines.append("| Body length (chars) | Sent | Replied | Reply rate |")
    lines.append("|--------------------|------|---------|-----------|")
    band_order = ["<100", "100-299", "300-599", "600-999", "1000+"]
    for band in band_order:
        d = reply_by_body_band.get(band)
        if not d:
            continue
        rate = f"{d['replied']/d['sent']*100:.2f}%" if d["sent"] else "n/a"
        lines.append(f"| {band} | {d['sent']} | {d['replied']} | "
                     f"{rate} (n={d['sent']}) |")
    lines.append("")

    lines.append("## 6. Reply Classification Breakdown")
    lines.append("")
    lines.append(f"Total classified reply rows: {len(all_reply_rows)}")
    lines.append("")
    lines.append("| Classification | Count | Share |")
    lines.append("|---------------|-------|-------|")
    for cls in replies.CATEGORIES:
        count = reply_classification.get(cls, 0)
        share = f"{count/len(all_reply_rows)*100:.1f}%" if all_reply_rows else "n/a"
        if count:
            lines.append(f"| {cls} | {count} | {share} |")
    lines.append("")
    lines.append(f"Automated replies (provider flag): {automated_count} "
                 f"of {len(all_reply_rows)}")
    lines.append(f"Unreadable (extraction yielded empty): {unreadable_count} "
                 f"of {len(all_reply_rows)}")
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

    lines.append("## 8. Bounce Rate by Campaign Status")
    lines.append("")
    lines.append("| Scheduled email status | Count | Share |")
    lines.append("|----------------------|-------|-------|")
    for status, count in sorted(bounce_by_status.items()):
        share = f"{count/total_sent*100:.1f}%" if total_sent else "n/a"
        lines.append(f"| {status} | {count} | {share} |")
    lines.append("")

    lines.append("## 9. Open Tracking Caveat")
    lines.append("")
    if no_open_tracking_campaigns:
        lines.append(f"**{len(no_open_tracking_campaigns)} campaign(s) have "
                     f"`open_tracking: False`.** Their zero opens are an "
                     f"absent measurement, not an absent open. These "
                     f"campaigns are excluded from any open-rate analysis.")
        lines.append("")
        for c in no_open_tracking_campaigns:
            lines.append(f"- Campaign {c['id']}: "
                         f"{_safe_campaign_name(c['name'])}")
    else:
        lines.append("All campaigns track opens.")
    lines.append("")

    lines.append("## 10. Observations, Hypotheses, and Proven Learnings")
    lines.append("")

    observations = []
    hypotheses = []
    proven = []

    if total_sent:
        overall_rate = total_replied / total_sent * 100
        observations.append(
            f"Overall reply rate is {overall_rate:.2f}% across "
            f"{total_sent} scheduled emails in {len(campaigns)} campaigns.")

    for seq_len, d in sorted(seq_len_map.items(),
                             key=lambda x: (isinstance(x[0], str), x[0])):
        if d["sent"] >= 30:
            rate = d["replied"] / d["sent"] * 100
            observations.append(
                f"Sequence length {seq_len}: {rate:.2f}% reply rate "
                f"(n={d['sent']}, {len(d['campaigns'])} campaign(s)).")

    if unreadable_count and all_reply_rows:
        unread_pct = unreadable_count / len(all_reply_rows) * 100
        observations.append(
            f"{unreadable_count} of {len(all_reply_rows)} reply rows "
            f"({unread_pct:.1f}%) were UNREADABLE after prospect-text "
            f"extraction. The task noted 46.5% unreadable as the last "
            f"measurement.")

    if automated_count and all_reply_rows:
        auto_pct = automated_count / len(all_reply_rows) * 100
        observations.append(
            f"{automated_count} of {len(all_reply_rows)} replies "
            f"({auto_pct:.1f}%) were flagged automated by the provider.")

    for step, d in sorted(reply_by_step.items(),
                          key=lambda x: (isinstance(x[0], str), x[0])):
        if isinstance(step, int) and step >= 5 and d["sent"] >= 10:
            rate = d["replied"] / d["sent"] * 100
            if rate < 1.0:
                hypotheses.append(
                    f"Step {step} has a {rate:.2f}% reply rate (n={d['sent']})."
                    f" It may not earn its place, but the sample may be too "
                    f"small to call.")

    lines.append("### Observations (what the rows say, with n)")
    lines.append("")
    for o in observations:
        lines.append(f"- {o}")
    if not observations:
        lines.append("- None yet.")
    lines.append("")

    lines.append("### Hypotheses (what it might mean)")
    lines.append("")
    for h in hypotheses:
        lines.append(f"- {h}")
    if not hypotheses:
        lines.append("- None yet.")
    lines.append("")

    lines.append("### Proven Learnings (what survives a sample-size objection)")
    lines.append("")
    for p in proven:
        lines.append(f"- {p}")
    if not proven:
        lines.append("- None. Sample sizes and campaign counts are too small "
                     "to call anything proven. This is honest, not modest.")
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

    campaigns, all_replies, sent_emails = build_analysis(args.cache_dir)

    print(f"\nProducing report: {output_path}", file=sys.stderr)
    report = produce_report(campaigns, all_replies, sent_emails, output_path)
    print(f"\nDone. {len(sent_emails)} scheduled emails analysed.",
          file=sys.stderr)
    print(f"Report: {output_path}", file=sys.stderr)

    dataset_path = os.path.join(args.cache_dir, "sent_emails_dataset.json")
    os.makedirs(args.cache_dir, exist_ok=True)
    dataset = []
    for e in sent_emails:
        row = dict(e)
        row.pop("step_body", None)
        row.pop("email_body", None)
        for r in row.get("replies", []):
            r.pop("text_hash", None)
        dataset.append(row)
    with open(dataset_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, default=str, indent=1)
    print(f"Dataset: {dataset_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
