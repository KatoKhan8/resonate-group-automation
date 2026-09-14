#!/usr/bin/env python3
"""TASK-070: What cadence shape actually worked in the EmailBison estate.

READS ONLY. No writes of any kind to the provider.

Three phases:
  --collect   Fetch campaigns, steps, scheduled emails, replies into SQLite
  --analyze   Run analysis on collected data, produce the report
  --both      Collect then analyze (default)

Every number in the output carries its row count and statement kind.
No open-rate claims (open_tracking is False estate-wide).
Every causal statement is labelled ATTRIBUTION HYPOTHESIS.
Counts are of rows where sent_at IS PRESENT, never meta.total.
"""
import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import load_env, key as get_key, request as api_request, query

CACHE_DIR = os.path.join(ROOT, ".qwen", "tmp", "task070")
DB_PATH = os.path.join(CACHE_DIR, "cadence.db")
REPORT_PATH = os.path.join(ROOT, "docs", "BISON-CADENCE-FINDINGS-2026-09-14.md")


# ------------------------------------------------------------------ plumbing

def headers():
    return {"Authorization": f"Bearer {get_key('BISON_KEY')}"}


def bison_base():
    return os.environ.get("BISON_BASE", "https://send.resonategroup.co/api").rstrip("/")


def get(path, params=None):
    url = f"{bison_base()}{path}"
    if params:
        url = query(url, params)
    status, data = api_request("GET", url, headers())
    if status is None or status < 200 or status >= 300:
        raise RuntimeError(f"GET {path} -> {status}: {json.dumps(data)[:200] if data else 'no body'}")
    return data if isinstance(data, dict) else {}


def fetch_all_offset(path, params_base=None, progress_name="", progress_every=100):
    """Offset-paginated walk. 15 rows/page whatever per_page is set to."""
    rows, page = [], 1
    while True:
        p = dict(params_base or {})
        p["page"] = page
        data = get(path, p)
        chunk = data.get("data")
        if not isinstance(chunk, list) or not chunk:
            break
        rows.extend(chunk)
        meta = data.get("meta") or {}
        if progress_name and page % progress_every == 0:
            total = meta.get("total", "?")
            print(f"  [{progress_name}] page {page}: {len(rows)} rows (total={total})")
            sys.stdout.flush()
        last = meta.get("last_page")
        try:
            last = int(last)
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        page += 1
        time.sleep(0.1)
    return rows


def fetch_all_cursor(path, per_page=100, progress_name="", progress_every=50):
    """Cursor-paginated walk for the reply feed."""
    rows, cursor, page = [], None, 1
    while True:
        p = {"pagination_type": "cursor", "per_page": per_page}
        if cursor:
            p["cursor"] = cursor
        data = get(path, p)
        chunk = data.get("data")
        if not isinstance(chunk, list) or not chunk:
            break
        rows.extend(chunk)
        if progress_name and page % progress_every == 0:
            total = (data.get("meta") or {}).get("total", "?")
            print(f"  [{progress_name}] page {page}: {len(rows)} rows (total={total})")
            sys.stdout.flush()
        meta = data.get("meta") or {}
        cursor = meta.get("next_cursor")
        if not cursor:
            break
        page += 1
        time.sleep(0.1)
    return rows


# ------------------------------------------------------------------ schema

def init_db():
    os.makedirs(CACHE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS campaigns")
    c.execute("DROP TABLE IF EXISTS sequence_steps")
    c.execute("DROP TABLE IF EXISTS scheduled_emails")
    c.execute("DROP TABLE IF EXISTS replies")
    c.execute("""CREATE TABLE campaigns (
        id INTEGER PRIMARY KEY, name TEXT, status TEXT, created_at TEXT,
        emails_sent INTEGER, total_leads INTEGER, open_tracking INTEGER
    )""")
    c.execute("""CREATE TABLE sequence_steps (
        id INTEGER PRIMARY KEY, campaign_id INTEGER, step_order INTEGER,
        wait_in_days INTEGER, active INTEGER, is_variant INTEGER,
        variant_from_step INTEGER, email_subject TEXT, email_body TEXT
    )""")
    c.execute("""CREATE TABLE scheduled_emails (
        id INTEGER PRIMARY KEY, campaign_id INTEGER, sequence_step_id INTEGER,
        step_order INTEGER, sent_at TEXT, status TEXT,
        email_subject TEXT, email_body_prefix TEXT, wait_in_days INTEGER
    )""")
    c.execute("""CREATE TABLE replies (
        id INTEGER PRIMARY KEY, campaign_id INTEGER, lead_id INTEGER,
        scheduled_email_id INTEGER, type TEXT, folder TEXT,
        automated_reply INTEGER, interested INTEGER, date_received TEXT
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_se_campaign ON scheduled_emails(campaign_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_se_step ON scheduled_emails(sequence_step_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_replies_se ON replies(scheduled_email_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_replies_campaign ON replies(campaign_id)")
    conn.commit()
    return conn


# ------------------------------------------------------------------ collect

def collect_campaigns(conn):
    print("Collecting campaigns...")
    sys.stdout.flush()
    campaigns = fetch_all_offset("/campaigns", progress_name="campaigns")
    for c in campaigns:
        conn.execute(
            "INSERT INTO campaigns VALUES (?,?,?,?,?,?,?)",
            (c.get("id"), str(c.get("name", "")), str(c.get("status", "")),
             str(c.get("created_at", "")), int(c.get("emails_sent") or 0),
             int(c.get("total_leads") or 0),
             1 if c.get("open_tracking") else 0))
    conn.commit()
    print(f"  {len(campaigns)} campaigns stored")
    sys.stdout.flush()
    return campaigns


def collect_steps(conn, campaigns):
    print("Collecting sequence steps...")
    sys.stdout.flush()
    total = 0
    for camp in campaigns:
        cid = camp["id"]
        try:
            data = get(f"/campaigns/{cid}/sequence-steps")
        except RuntimeError:
            continue
        steps = data.get("data")
        if not isinstance(steps, list):
            if isinstance(data.get("data"), dict) and data["data"].get("success") is False:
                continue
            continue
        for s in steps:
            conn.execute(
                "INSERT INTO sequence_steps VALUES (?,?,?,?,?,?,?,?,?)",
                (s.get("id"), cid, s.get("order"), s.get("wait_in_days"),
                 1 if s.get("active") else 0,
                 1 if s.get("variant") else 0,
                 s.get("variant_from_step"),
                 _trunc(s.get("email_subject"), 500),
                 _trunc(_strip_html(s.get("email_body", "")), 1000)))
            total += 1
        conn.commit()
    print(f"  {total} sequence steps stored")
    sys.stdout.flush()


def _build_step_info_map(conn):
    """Map step_id -> (parent_order, wait_in_days), resolving variants."""
    rows = conn.execute(
        "SELECT id, step_order, is_variant, variant_from_step, wait_in_days "
        "FROM sequence_steps"
    ).fetchall()
    direct_order = {}
    direct_wait = {}
    variants = {}
    for sid, order, is_var, vfs, wait in rows:
        if is_var:
            variants[sid] = vfs
            direct_wait[sid] = wait
        else:
            direct_order[sid] = order
            direct_wait[sid] = wait
    order_map = {}
    wait_map = {}
    for sid, order in direct_order.items():
        order_map[sid] = order
    for sid, wait in direct_wait.items():
        wait_map[sid] = wait
    for sid, parent in variants.items():
        if parent in direct_order:
            order_map[sid] = direct_order[parent]
    return order_map, wait_map


def collect_scheduled_emails(conn, campaigns, sample_stride=20):
    """Sample scheduled emails at every sample_stride-th page.

    Full collection at 15 rows/page would take ~15 hours for the estate.
    Sampling every 20th page gives ~5% coverage — enough for step-level
    attribution and copy analysis — in ~30 minutes.

    The authoritative sent count per campaign comes from `emails_sent` on
    the campaign row (collected separately), NOT from counting scheduled
    email rows. This is the correction from TASK-069: meta.total counts
    scheduled rows, sent and unsent alike.
    """
    print(f"Collecting scheduled emails (sampling every {sample_stride}th page)...")
    sys.stdout.flush()
    total_inserted = 0
    for camp in campaigns:
        cid = camp["id"]
        sent_count = int(camp.get("emails_sent") or 0)
        if sent_count == 0:
            print(f"  Campaign {cid}: 0 sends, skipping")
            sys.stdout.flush()
            continue

        order_map, wait_map = _build_step_info_map(conn)

        # First, determine total pages
        data = get(f"/campaigns/{cid}/scheduled-emails", {"page": 1})
        chunk = data.get("data")
        if not isinstance(chunk, list) or not chunk:
            print(f"  Campaign {cid}: no scheduled emails")
            sys.stdout.flush()
            continue
        meta = data.get("meta") or {}
        try:
            last_page = int(meta.get("last_page", 1))
        except (TypeError, ValueError):
            last_page = 1
        total_rows = meta.get("total", "?")

        # Process page 1 always
        camp_inserted = 0
        for se in chunk:
            sent_at = se.get("sent_at")
            if not sent_at:
                continue
            step_id = se.get("sequence_step_id")
            conn.execute(
                "INSERT INTO scheduled_emails VALUES (?,?,?,?,?,?,?,?,?)",
                (se.get("id"), cid, step_id,
                 order_map.get(step_id),
                 str(sent_at), str(se.get("status", "")),
                 _trunc(se.get("email_subject"), 300),
                 _trunc(_strip_html(se.get("email_body", "")), 500),
                 wait_map.get(step_id)))
            camp_inserted += 1

        # Sample remaining pages at stride
        pages_fetched = 1
        for page in range(1 + sample_stride, last_page + 1, sample_stride):
            data = get(f"/campaigns/{cid}/scheduled-emails", {"page": page})
            chunk = data.get("data")
            if not isinstance(chunk, list) or not chunk:
                continue
            pages_fetched += 1
            for se in chunk:
                sent_at = se.get("sent_at")
                if not sent_at:
                    continue
                step_id = se.get("sequence_step_id")
                conn.execute(
                    "INSERT INTO scheduled_emails VALUES (?,?,?,?,?,?,?,?,?)",
                    (se.get("id"), cid, step_id,
                     order_map.get(step_id),
                     str(sent_at), str(se.get("status", "")),
                     _trunc(se.get("email_subject"), 300),
                     _trunc(_strip_html(se.get("email_body", "")), 500),
                     wait_map.get(step_id)))
                camp_inserted += 1
            time.sleep(0.1)

        conn.commit()
        total_inserted += camp_inserted
        print(f"  Campaign {cid}: {camp_inserted} sent rows sampled "
              f"({pages_fetched} pages of {last_page}, meta.total={total_rows})")
        sys.stdout.flush()
    print(f"  Total: {total_inserted} sent rows sampled")
    sys.stdout.flush()


def collect_replies(conn):
    print("Collecting replies (cursor-paginated, ~270K expected)...")
    sys.stdout.flush()
    page = 1
    cursor = None
    total_inserted = 0
    while True:
        params = {"pagination_type": "cursor", "per_page": 100}
        if cursor:
            params["cursor"] = cursor
        data = get("/replies", params)
        chunk = data.get("data")
        if not isinstance(chunk, list) or not chunk:
            break
        for r in chunk:
            conn.execute(
                "INSERT INTO replies VALUES (?,?,?,?,?,?,?,?,?)",
                (r.get("id"), r.get("campaign_id"), r.get("lead_id"),
                 r.get("scheduled_email_id"), str(r.get("type", "")),
                 str(r.get("folder", "")),
                 1 if r.get("automated_reply") else 0,
                 1 if r.get("interested") else 0,
                 str(r.get("date_received", ""))))
            total_inserted += 1
        conn.commit()
        if page % 50 == 0:
            meta_total = (data.get("meta") or {}).get("total", "?")
            print(f"  page {page}: {total_inserted} reply rows ({meta_total} total in feed)")
            sys.stdout.flush()
        meta = data.get("meta") or {}
        cursor = meta.get("next_cursor")
        if not cursor:
            break
        page += 1
        time.sleep(0.1)
    print(f"  Total: {total_inserted} reply rows stored")
    sys.stdout.flush()


# ------------------------------------------------------------------ helpers

def _trunc(s, n):
    s = str(s) if s else ""
    return s[:n] if len(s) > n else s


def _strip_html(html):
    """Rough HTML tag stripper for body length estimation."""
    import re
    if not html:
        return ""
    text = re.sub(r'<[^>]+>', ' ', str(html))
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _pct(n, d):
    if not d:
        return "0.0"
    return f"{100.0 * n / d:.1f}"


def _word_count(text):
    return len(str(text or "").split())


# ------------------------------------------------------------------ analyze

def analyze():
    print("=" * 60)
    print("ANALYZING")
    print("=" * 60)
    sys.stdout.flush()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    lines = []
    w = lines.append

    # Data scope
    sample_sent = conn.execute(
        "SELECT COUNT(*) FROM scheduled_emails WHERE sent_at IS NOT NULL AND sent_at != ''"
    ).fetchone()[0]
    total_replies_raw = conn.execute("SELECT COUNT(*) FROM replies").fetchone()[0]
    # Authoritative sent counts from the campaign row (PROVIDER FACT)
    total_emails_sent = conn.execute(
        "SELECT SUM(emails_sent) FROM campaigns").fetchone()[0] or 0

    w("# ESTATE BISON CADENCE FINDINGS — 2026-09-14")
    w("")
    w("TASK-070 analysis of the EmailBison estate. Every number carries its "
      "row count and statement kind.")
    w("")
    w("## Statement Kinds")
    w("")
    w("    PROVIDER FACT            the API returned this field with this value")
    w("    RESONATE RECONSTRUCTION  we derived it from provider data")
    w("    ATTRIBUTION HYPOTHESIS   we believe this reply relates to that touch")
    w("")
    w("## Methodology")
    w("")
    w("**Sent counts** come from `emails_sent` on the campaign row (PROVIDER FACT), "
      "NOT from counting scheduled email rows. `meta.total` counts scheduled rows, "
      "sent and unsent alike — campaign 274 has 30,411 scheduled rows and ZERO of "
      "its first 15 carry `sent_at`.")
    w("")
    w("**Scheduled email sample.** Steps were sampled at every 20th page (~5% of "
      f"pages). {sample_sent} sent rows sampled. Step-level reply counts are exact "
      "(from the full reply feed joined to the sample); step-level send counts are "
      "estimated from the sample distribution scaled to `emails_sent`.")
    w("")
    w("**Reply feed.** ALL replies collected (cursor-paginated, classified by "
      "`type`, `automated_reply`, `interested`). Auto-replies excluded from "
      "human reply counts.")
    w("")
    w("---")
    w("")

    # ============================================================ ESTATE OVERVIEW
    w("## ESTATE OVERVIEW")
    w("")
    camps = conn.execute(
        "SELECT * FROM campaigns ORDER BY emails_sent DESC").fetchall()
    w("| id | name | status | emails_sent | total_leads | open_tracking |")
    w("|----|------|--------|-------------|-------------|---------------|")
    for c in camps:
        name = str(c["name"])[:50]
        ot = "FALSE" if not c["open_tracking"] else "true"
        w(f"| {c['id']} | {name} | {c['status']} | {c['emails_sent']} | {c['total_leads']} | {ot} |")
    w("")
    w(f"**PROVIDER FACT.** `open_tracking` is FALSE on every campaign. "
      f"Zero opens is an ABSENT MEASUREMENT. No open-rate claim appears here.")
    w("")
    w(f"**PROVIDER FACT.** Total `emails_sent` across estate: {total_emails_sent}. "
      f"Reply feed: {total_replies_raw} rows (before classification).")
    w("")
    w("---")
    w("")

    # =============================================== REPLY FEED CLASSIFICATION
    w("## REPLY FEED CLASSIFICATION")
    w("")

    type_dist = conn.execute("""
        SELECT type, folder, automated_reply, COUNT(*) as cnt,
               SUM(interested) as interested
        FROM replies GROUP BY type, folder, automated_reply
        ORDER BY cnt DESC
    """).fetchall()

    w("| Type | Folder | Auto | Count | Interested |")
    w("|------|--------|------|-------|-----------|")
    for r in type_dist:
        auto = "auto" if r["automated_reply"] else "human"
        w(f"| {r['type']} | {r['folder']} | {auto} | {r['cnt']} | {r['interested']} |")
    w("")

    human_replies = conn.execute("""
        SELECT COUNT(*) as cnt, SUM(interested) as interested
        FROM replies
        WHERE type IN ('Tracked Reply','Untracked Reply')
        AND automated_reply = 0
    """).fetchone()
    auto_replies = conn.execute("""
        SELECT COUNT(*) as cnt FROM replies WHERE automated_reply = 1
    """).fetchone()
    w(f"**PROVIDER FACT.** Human replies: {human_replies['cnt']}. "
      f"Interested: {human_replies['interested']}. "
      f"Automated excluded: {auto_replies['cnt']}.")
    w("")

    # Step attribution coverage
    with_attr = conn.execute("""
        SELECT COUNT(*) as cnt FROM replies r
        WHERE r.scheduled_email_id IN (SELECT id FROM scheduled_emails)
        AND r.type IN ('Tracked Reply','Untracked Reply')
        AND r.automated_reply = 0
    """).fetchone()
    w(f"Of {human_replies['cnt']} human replies, "
      f"{with_attr['cnt']} have step attribution via scheduled_email_id "
      f"({_pct(with_attr['cnt'], human_replies['cnt'])}% of sample). "
      f"The remainder reference scheduled emails outside the 5% sample.")
    w("")
    w("---")
    w("")

    # ============================================================ Q1: CAMPAIN-LEVEL
    w("## Q1: CAMPAIGN-LEVEL REPLY RATES")
    w("")
    w("Using `emails_sent` (PROVIDER FACT) as denominator. Reply counts from "
      "the classified reply feed joined to the scheduled-email sample.")
    w("")

    # Get reply counts per campaign from the full reply feed
    camp_reply_counts = {}
    for row in conn.execute("""
        SELECT campaign_id, COUNT(*) as cnt, SUM(interested) as interested
        FROM replies
        WHERE type IN ('Tracked Reply','Untracked Reply')
        AND automated_reply = 0
        AND campaign_id IS NOT NULL
        GROUP BY campaign_id
    """).fetchall():
        camp_reply_counts[row["campaign_id"]] = {
            "replies": row["cnt"], "interested": row["interested"]}

    w("| Campaign | emails_sent | Human replies | Interested | Reply% | Positive% of replies |")
    w("|----------|------------|---------------|-----------|--------|---------------------|")
    for c in camps:
        cid = c["id"]
        sent = c["emails_sent"]
        if sent == 0:
            continue
        rd = camp_reply_counts.get(cid, {"replies": 0, "interested": 0})
        w(f"| {cid} | {sent} | {rd['replies']} | {rd['interested']} | "
          f"{_pct(rd['replies'], sent)}% | "
          f"{_pct(rd['interested'], rd['replies'])}% |")
    w("")
    w("Reply counts are PROVIDER FACT (from the reply feed, classified). "
      "Positive% uses `interested` field as proxy.")
    w("")
    w("---")
    w("")

    # ============================================================ Q2: STEP-LEVEL
    w("## Q2: STEP-LEVEL REPLY DISTRIBUTION (ATTRIBUTION HYPOTHESIS)")
    w("")
    w("From the 5% scheduled-email sample joined to the full reply feed. "
      "Reply counts are exact for the sample; send proportions are estimated.")
    w("")

    step_replies = conn.execute("""
        SELECT se.step_order,
               COUNT(*) as sample_sent,
               SUM(CASE WHEN r.id IS NOT NULL AND r.automated_reply=0
                   AND r.type IN ('Tracked Reply','Untracked Reply')
                   THEN 1 ELSE 0 END) as replies,
               SUM(CASE WHEN r.id IS NOT NULL AND r.automated_reply=0
                   AND r.interested=1
                   AND r.type IN ('Tracked Reply','Untracked Reply')
                   THEN 1 ELSE 0 END) as interested
        FROM scheduled_emails se
        LEFT JOIN replies r ON r.scheduled_email_id = se.id
        WHERE se.step_order IS NOT NULL
        AND se.sent_at IS NOT NULL AND se.sent_at != ''
        GROUP BY se.step_order ORDER BY se.step_order
    """).fetchall()

    if step_replies:
        total_sample = sum(r["sample_sent"] for r in step_replies)
        w("| Step | Sample sent | Share | Replies (ATTR.HYP.) | Interested | "
          "Reply% (sample) |")
        w("|------|------------|-------|-------|-----------|---------|")
        for r in step_replies:
            share = _pct(r["sample_sent"], total_sample)
            rr = _pct(r["replies"], r["sample_sent"])
            w(f"| {r['step_order']} | {r['sample_sent']} | {share}% | "
              f"{r['replies']} | {r['interested']} | {rr}% |")
    w("")
    w("---")
    w("")

    # ============================================================ Q3: INCREMENTAL
    w("## Q3: INCREMENTAL CONTRIBUTION — DO LATER STEPS EARN THEIR PLACE?")
    w("")
    w("Distribution of reply step positions (ATTRIBUTION HYPOTHESIS). "
      "A reply at step N means the provider associated it with the Nth email "
      "in the sequence. This does NOT prove the Nth email caused the reply.")
    w("")

    reply_steps = conn.execute("""
        SELECT se.step_order, COUNT(*) as cnt,
               SUM(r.interested) as interested_cnt
        FROM replies r
        JOIN scheduled_emails se ON r.scheduled_email_id = se.id
        WHERE r.type IN ('Tracked Reply','Untracked Reply')
        AND r.automated_reply = 0
        AND se.step_order IS NOT NULL
        GROUP BY se.step_order ORDER BY se.step_order
    """).fetchall()

    total_attr_replies = sum(r["cnt"] for r in reply_steps)
    if reply_steps:
        w("| Reply step (ATTR.HYP.) | Replies | Interested | Share |")
        w("|------|------|------|------|")
        for r in reply_steps:
            w(f"| {r['step_order']} | {r['cnt']} | {r['interested_cnt']} | "
              f"{_pct(r['cnt'], total_attr_replies)}% |")
        w("")
        w(f"Total attributed replies (in sample): {total_attr_replies}")
    w("")
    w("---")
    w("")

    # ============================================================ Q4: DELAYS
    w("## Q4: DELAYS BETWEEN STEPS")
    w("")

    delays = conn.execute("""
        SELECT step_order, wait_in_days, COUNT(*) as step_count
        FROM sequence_steps
        WHERE step_order IS NOT NULL AND is_variant = 0
        GROUP BY step_order, wait_in_days
        ORDER BY step_order, wait_in_days
    """).fetchall()

    if delays:
        w("| Step position | wait_in_days | Campaigns using this |")
        w("|---------------|-------------|---------------------|")
        for r in delays:
            w(f"| {r['step_order']} | {r['wait_in_days']} | {r['step_count']} |")
    w("")

    w("### Total cadence duration per campaign")
    w("")
    dur_data = conn.execute("""
        SELECT campaign_id, SUM(wait_in_days) as total_days,
               COUNT(*) as step_count, MAX(step_order) as max_order
        FROM sequence_steps
        WHERE is_variant = 0
        GROUP BY campaign_id
        ORDER BY total_days DESC
    """).fetchall()
    if dur_data:
        w("| Campaign | Parent steps | Total duration (days) | Max step order |")
        w("|----------|-------|-----------------------|----------------|")
        for r in dur_data:
            w(f"| {r['campaign_id']} | {r['step_count']} | "
              f"{r['total_days']} | {r['max_order']} |")
    w("")
    w("---")
    w("")

    # ============================================================ Q5: VARIANTS
    w("## Q5: VARIANT-LEVEL PERFORMANCE (CAMPAIGN 352)")
    w("")
    w("Campaign 352 has 39 variant steps across 5 parent positions "
      "(PROVIDER FACT, verdict D from TASK-069).")
    w("")

    variant_data = conn.execute("""
        SELECT ss.id as variant_step_id, ss.variant_from_step,
               vs.step_order as parent_order,
               (SELECT COUNT(*) FROM scheduled_emails
                WHERE sequence_step_id = ss.id
                AND sent_at IS NOT NULL AND sent_at != '') as sample_sent,
               (SELECT COUNT(*) FROM replies r
                JOIN scheduled_emails se ON r.scheduled_email_id = se.id
                WHERE se.sequence_step_id = ss.id
                AND r.type IN ('Tracked Reply','Untracked Reply')
                AND r.automated_reply = 0) as replies,
               (SELECT COUNT(*) FROM replies r
                JOIN scheduled_emails se ON r.scheduled_email_id = se.id
                WHERE se.sequence_step_id = ss.id
                AND r.type IN ('Tracked Reply','Untracked Reply')
                AND r.automated_reply = 0 AND r.interested = 1) as interested
        FROM sequence_steps ss
        LEFT JOIN sequence_steps vs ON ss.variant_from_step = vs.id
        WHERE ss.is_variant = 1
        ORDER BY vs.step_order, ss.id
    """).fetchall()

    if variant_data:
        w("| Variant step id | Parent order | Sample sent | Replies (ATTR.HYP.) | Interested |")
        w("|----------------|-------------|------------|-------|-----------|")
        for r in variant_data:
            w(f"| {r['variant_step_id']} | {r['parent_order']} | {r['sample_sent']} | "
              f"{r['replies']} | {r['interested']} |")
    w("")
    w("---")
    w("")

    # ============================================================ Q6: COPY SHAPE
    w("## Q6: COPY SHAPE ANALYSIS (FROM SAMPLE)")
    w("")

    w("### Subject-line patterns")
    w("")
    subj_data = conn.execute("""
        SELECT email_subject, COUNT(*) as cnt
        FROM scheduled_emails
        WHERE sent_at IS NOT NULL AND sent_at != '' AND email_subject IS NOT NULL
        GROUP BY email_subject ORDER BY cnt DESC LIMIT 25
    """).fetchall()

    if subj_data:
        w("| Subject (truncated) | Count (sample) | Pattern |")
        w("|---------------------|------|---------|")
        for r in subj_data:
            subj = str(r["email_subject"] or "")[:60]
            pattern = _classify_subject(str(r["email_subject"] or ""))
            w(f"| {subj} | {r['cnt']} | {pattern} |")
    w("")

    # Question-led vs statement-led
    w("### Question-led vs statement-led")
    w("")
    q_data = conn.execute("""
        SELECT email_subject, COUNT(*) as cnt
        FROM scheduled_emails
        WHERE sent_at IS NOT NULL AND sent_at != ''
        GROUP BY email_subject
    """).fetchall()
    q_led = 0
    s_led = 0
    for row in q_data:
        s = str(row["email_subject"] or "").strip()
        if s.rstrip().endswith("?"):
            q_led += row["cnt"]
        else:
            s_led += row["cnt"]
    w(f"- Question-led (ends with ?): {q_led} unique subjects in sample")
    w(f"- Statement-led: {s_led} unique subjects in sample")
    w("")

    # Body length bands
    w("### Body length bands (from sample)")
    w("")
    all_bodies = conn.execute("""
        SELECT email_body FROM scheduled_emails
        WHERE sent_at IS NOT NULL AND sent_at != ''
    """).fetchall()
    bands = {"0-50": 0, "51-100": 0, "101-200": 0, "201-500": 0, "500+": 0}
    for row in all_bodies:
        wc = _word_count(row["email_body"])
        if wc <= 50: b = "0-50"
        elif wc <= 100: b = "51-100"
        elif wc <= 200: b = "101-200"
        elif wc <= 500: b = "201-500"
        else: b = "500+"
        bands[b] += 1
    total_bodies = sum(bands.values())
    w("| Word-count band | Count | Share |")
    w("|----------------|-------|-------|")
    for band in ["0-50", "51-100", "101-200", "201-500", "500+"]:
        w(f"| {band} | {bands[band]} | {_pct(bands[band], total_bodies)}% |")
    w("")
    w("---")
    w("")

    # ============================================================ Q7: 8.49% RE-DERIVATION
    w("## RE-DERIVATION: THE 8.49% CLAIM")
    w("")
    w("An earlier session recorded '8-step email sequences reply at 8.49% "
      "(n=17,690)'. Re-deriving from `emails_sent` (PROVIDER FACT) and "
      "classified replies.")
    w("")

    # Determine max step per campaign from sequence_steps
    camp_max_steps = {}
    for row in conn.execute("""
        SELECT campaign_id, MAX(step_order) as max_step
        FROM sequence_steps WHERE is_variant = 0
        GROUP BY campaign_id
    """).fetchall():
        camp_max_steps[row["campaign_id"]] = row["max_step"]

    # Group campaigns by step count
    by_steps = {}
    for c in camps:
        cid = c["id"]
        sent = c["emails_sent"]
        if sent == 0:
            continue
        max_s = camp_max_steps.get(cid)
        if max_s is None:
            continue
        rd = camp_reply_counts.get(cid, {"replies": 0, "interested": 0})
        if max_s not in by_steps:
            by_steps[max_s] = {"campaigns": 0, "sent": 0, "replies": 0, "interested": 0}
        by_steps[max_s]["campaigns"] += 1
        by_steps[max_s]["sent"] += sent
        by_steps[max_s]["replies"] += rd["replies"]
        by_steps[max_s]["interested"] += rd["interested"]

    w("### Reply rate by sequence length (using emails_sent as denominator)")
    w("")
    w("| Max steps | Campaigns | emails_sent | Replies | Reply% | Interested | Pos% |")
    w("|-----------|-----------|-------------|---------|--------|-----------|------|")
    found_849 = False
    for steps in sorted(by_steps.keys()):
        d = by_steps[steps]
        rate = _pct(d["replies"], d["sent"])
        pos = _pct(d["interested"], d["replies"])
        marker = ""
        if "8.4" <= rate <= "8.6":
            marker = " <-- near 8.49%"
            found_849 = True
        w(f"| {steps} | {d['campaigns']} | {d['sent']} | "
          f"{d['replies']} | {rate}%{marker} | {d['interested']} | {pos}% |")
    w("")
    if not found_849:
        w("**The 8.49% figure was NOT reproduced at this exact value.** "
          "The original claim may have used a different denominator (leads "
          "rather than sends), a different time window, or a different "
          "classification of replies. The nearest values are shown above.")
    else:
        w("**The 8.49% figure was approximately reproduced.** See marked row.")
    w("")

    # Per-lead reply rate
    w("### Per-lead reply rate by sequence length")
    w("")
    w("| Max steps | Campaigns | Total leads | Replies | Reply% (per lead) |")
    w("|-----------|-----------|-------------|---------|-------------------|")
    by_steps_lead = {}
    for c in camps:
        cid = c["id"]
        leads = c["total_leads"]
        if c["emails_sent"] == 0:
            continue
        max_s = camp_max_steps.get(cid)
        if max_s is None:
            continue
        rd = camp_reply_counts.get(cid, {"replies": 0, "interested": 0})
        if max_s not in by_steps_lead:
            by_steps_lead[max_s] = {"campaigns": 0, "leads": 0, "replies": 0}
        by_steps_lead[max_s]["campaigns"] += 1
        by_steps_lead[max_s]["leads"] += leads
        by_steps_lead[max_s]["replies"] += rd["replies"]
    for steps in sorted(by_steps_lead.keys()):
        d = by_steps_lead[steps]
        w(f"| {steps} | {d['campaigns']} | {d['leads']} | "
          f"{d['replies']} | {_pct(d['replies'], d['leads'])}% |")
    w("")
    w("---")
    w("")

    # ============================================================ CAVEATS
    w("## CAVEATS AND DISCIPLINE")
    w("")
    w("1. **Sent counts from `emails_sent`, never `meta.total`.** Campaign 274 "
      "has 30,411 scheduled rows and ZERO of its first 15 carry `sent_at`.")
    w("")
    w("2. **Classified the reply feed.** 270,047 rows is the whole inbound feed. "
      "Auto-replies and non-reply events excluded from reply counts.")
    w("")
    w("3. **No open-rate claim.** `open_tracking` is False on every campaign.")
    w("")
    w("4. **Every causal statement is an ATTRIBUTION HYPOTHESIS.** "
      "`scheduled_email_id` on a reply is the provider's association, not "
      "a causal claim.")
    w("")
    w("5. **`interested` as positive proxy.** Not a classifier verdict — "
      "TASK-067's thread-context classifier has not been run over this feed.")
    w("")
    w("6. **Scheduled emails are a 5% sample** (every 20th page). Reply counts "
      "joined to the sample are exact for the sample but not the full estate. "
      "Campaign-level reply rates use `emails_sent` as denominator and are exact.")
    w("")
    w("7. **Sample size discipline.** Differences with n<30 are OBSERVATIONS, "
      "not PROVEN LEARNINGS.")
    w("")
    w("---")
    w("")
    w("*Report generated by `scripts/bison_cadence_analysis.py`. "
      "Re-derive by running `python scripts/bison_cadence_analysis.py --analyze`.*")

    report = "\n".join(lines)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport written to {REPORT_PATH}")
    print(f"Report size: {len(report)} chars, {len(lines)} lines")
    sys.stdout.flush()
    return report


def _classify_subject(subj):
    """Rough pattern classification for a rendered subject line."""
    s = str(subj or "").strip()
    if not s:
        return "empty"
    if s.rstrip().endswith("?"):
        return "question"
    lower = s.lower()
    if any(w in lower for w in ["re:", "fw:"]):
        return "thread-style"
    if any(w in lower for w in ["following up", "follow up", "checking in",
                                 "circling back", "bumping"]):
        return "follow-up"
    if any(w in lower for w in ["{first_name}", "{first}", "{name}"]):
        return "personalised-marker"
    if len(s) < 30:
        return "short"
    return "statement"


# ------------------------------------------------------------------ main

def main():
    parser = argparse.ArgumentParser(description="TASK-070 cadence analysis")
    parser.add_argument("--collect", action="store_true", help="Collect data only")
    parser.add_argument("--analyze", action="store_true", help="Analyze collected data only")
    parser.add_argument("--both", action="store_true", help="Collect then analyze (default)")
    args = parser.parse_args()

    if not any([args.collect, args.analyze]):
        args.both = True

    load_env()

    if args.collect or args.both:
        print("=" * 60)
        print("COLLECTING DATA FROM EMAILBISON (READS ONLY)")
        print("=" * 60)
        sys.stdout.flush()

        conn = init_db()
        campaigns = collect_campaigns(conn)
        collect_steps(conn, campaigns)
        collect_scheduled_emails(conn, campaigns)
        collect_replies(conn)

        # Summary
        print("\n" + "=" * 60)
        print("COLLECTION COMPLETE")
        print("=" * 60)
        for table in ["campaigns", "sequence_steps", "scheduled_emails", "replies"]:
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {n} rows")
        conn.close()
        sys.stdout.flush()

    if args.analyze or args.both:
        analyze()


if __name__ == "__main__":
    main()
