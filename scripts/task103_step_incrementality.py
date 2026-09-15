#!/usr/bin/env python3
"""TASK-103: Does step 5 generate INCREMENTAL value?

READS ONLY. No writes of any kind to the provider.

The question, stated precisely:
    Of the people who did NOT reply to steps 1-4, what fraction replied to
    step 5 - and how does that compare to the cost of sending it?

Method:
    Pick the smallest campaign with a full multi-step cadence and real sends.
    Walk its scheduled emails exhaustively (all accessible pages).
    Compute per-step denominators (count rows WHERE sent_at IS PRESENT).
    Collect ALL replies (cursor-paginated).
    Join replies to scheduled emails by scheduled_email_id.
    Compute survivors entering each step and incremental replies.

Output: docs/STEP-INCREMENTALITY-2026-09-15.md

Every number carries its n and statement kind.
No open-rate claims (open_tracking is False estate-wide).
Every causal statement is labelled ATTRIBUTION HYPOTHESIS.
Counts are of rows WHERE sent_at IS PRESENT, never meta.total.
per_page is accepted and IGNORED (15 rows per request always).
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import load_env, key as get_key, request as api_request, query

CACHE_DIR = os.path.join(ROOT, ".qwen", "tmp", "task103")
DB_PATH = os.path.join(CACHE_DIR, "incrementality.db")
REPORT_PATH = os.path.join(ROOT, "docs", "STEP-INCREMENTALITY-2026-09-15.md")

ACCESSIBLE_PAGE_CAP = 500


# ------------------------------------------------------------------ plumbing

def headers():
    return {"Authorization": f"Bearer {get_key('BISON_KEY')}"}


def bison_base():
    return os.environ.get("BISON_BASE",
                          "https://send.resonategroup.co/api").rstrip("/")


def get(path, params=None):
    url = f"{bison_base()}{path}"
    if params:
        url = query(url, params)
    status, data = api_request("GET", url, headers())
    if status is None or status < 200 or status >= 300:
        raise RuntimeError(
            f"GET {path} -> {status}: "
            f"{json.dumps(data)[:200] if data else 'no body'}")
    return data if isinstance(data, dict) else {}


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
        variant_from_step INTEGER, thread_reply INTEGER,
        email_subject TEXT, email_body TEXT
    )""")
    c.execute("""CREATE TABLE scheduled_emails (
        id INTEGER PRIMARY KEY, campaign_id INTEGER,
        sequence_step_id INTEGER, step_order INTEGER,
        sent_at TEXT, status TEXT, lead_id INTEGER,
        page_number INTEGER
    )""")
    c.execute("""CREATE TABLE replies (
        id INTEGER PRIMARY KEY, campaign_id INTEGER, lead_id INTEGER,
        scheduled_email_id INTEGER, type TEXT, folder TEXT,
        automated_reply INTEGER, interested INTEGER, date_received TEXT
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_se_campaign "
              "ON scheduled_emails(campaign_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_se_step "
              "ON scheduled_emails(sequence_step_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_se_id "
              "ON scheduled_emails(id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_replies_se "
              "ON replies(scheduled_email_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_replies_campaign "
              "ON replies(campaign_id)")
    conn.commit()
    return conn


# ------------------------------------------------------------------ collect

def collect_campaigns(conn):
    print("Collecting campaigns...")
    sys.stdout.flush()
    campaigns = []
    page = 1
    while True:
        data = get("/campaigns", {"page": page})
        chunk = data.get("data")
        if not isinstance(chunk, list) or not chunk:
            break
        campaigns.extend(chunk)
        meta = data.get("meta") or {}
        try:
            last = int(meta.get("last_page"))
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        page += 1
        time.sleep(0.1)

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
            if isinstance(data.get("data"), dict) and \
               data["data"].get("success") is False:
                continue
            continue
        for s in steps:
            conn.execute(
                "INSERT INTO sequence_steps VALUES (?,?,?,?,?,?,?,?,?,?)",
                (s.get("id"), cid, s.get("order"), s.get("wait_in_days"),
                 1 if s.get("active") else 0,
                 1 if s.get("variant") else 0,
                 s.get("variant_from_step"),
                 1 if s.get("thread_reply") else 0,
                 _trunc(s.get("email_subject"), 500),
                 _trunc(_strip_html(s.get("email_body", "")), 1000)))
            total += 1
        conn.commit()
    print(f"  {total} sequence steps stored")
    sys.stdout.flush()


def _build_step_info_map(conn):
    """Map step_id -> parent_order, resolving variants to their parent."""
    rows = conn.execute(
        "SELECT id, step_order, is_variant, variant_from_step "
        "FROM sequence_steps"
    ).fetchall()
    direct_order = {}
    variants = {}
    for sid, order, is_var, vfs in rows:
        if is_var:
            variants[sid] = vfs
        else:
            direct_order[sid] = order
    order_map = dict(direct_order)
    for sid, parent in variants.items():
        if parent in direct_order:
            order_map[sid] = direct_order[parent]
    return order_map


def find_target_campaign(conn):
    """Find the smallest campaign with >= 5 parent steps and real sends.

    Returns (campaign_id, emails_sent, step_count) or None.
    """
    rows = conn.execute("""
        SELECT c.id, c.emails_sent, c.name,
               COUNT(DISTINCT ss.step_order) as parent_steps
        FROM campaigns c
        JOIN sequence_steps ss ON ss.campaign_id = c.id
        WHERE c.emails_sent > 0
        AND ss.is_variant = 0
        AND ss.step_order IS NOT NULL
        GROUP BY c.id
        HAVING parent_steps >= 5
        ORDER BY c.emails_sent ASC
    """).fetchall()
    if rows:
        return rows[0]
    return None


def collect_scheduled_emails_exhaustive(conn, campaign_id, order_map):
    """Walk ALL accessible pages for one campaign.

    The API refuses offset pagination beyond ~500 pages (422).
    We walk pages 1..min(last_page, 500).

    ONLY rows where sent_at IS PRESENT are stored.
    Returns (rows_inserted, pages_fetched, total_pages, stopped_early).
    """
    print(f"Collecting scheduled emails for campaign {campaign_id} "
          f"(exhaustive, cap {ACCESSIBLE_PAGE_CAP} pages)...")
    sys.stdout.flush()

    # First page to learn last_page
    data = get(f"/campaigns/{campaign_id}/scheduled-emails", {"page": 1})
    chunk = data.get("data")
    if not isinstance(chunk, list) or not chunk:
        print("  No data on page 1")
        sys.stdout.flush()
        return 0, 0, 0, False

    meta = data.get("meta") or {}
    try:
        last_page = int(meta.get("last_page"))
    except (TypeError, ValueError):
        last_page = 1
    meta_total = meta.get("total", "?")

    accessible = min(last_page, ACCESSIBLE_PAGE_CAP)
    stopped_early = last_page > ACCESSIBLE_PAGE_CAP

    print(f"  Campaign has {last_page} total pages "
          f"(meta.total={meta_total}), "
          f"accessible: {accessible}")
    sys.stdout.flush()

    total_inserted = 0
    pages_fetched = 0

    # Process page 1 (already fetched)
    for se in chunk:
        sent_at = se.get("sent_at")
        if not sent_at:
            continue
        step_id = se.get("sequence_step_id")
        conn.execute(
            "INSERT INTO scheduled_emails VALUES (?,?,?,?,?,?,?,?,?)",
            (se.get("id"), campaign_id, step_id,
             order_map.get(step_id),
             str(sent_at), str(se.get("status", "")),
             se.get("lead_id"),
             1))
        total_inserted += 1
    pages_fetched = 1

    # Remaining pages
    for page in range(2, accessible + 1):
        try:
            data = get(f"/campaigns/{campaign_id}/scheduled-emails",
                       {"page": page})
        except RuntimeError as e:
            if "too many" in str(e).lower() or "422" in str(e):
                print(f"  API refused page {page}: {e}")
                stopped_early = True
                break
            raise
        pg_chunk = data.get("data")
        if not isinstance(pg_chunk, list) or not pg_chunk:
            break
        for se in pg_chunk:
            sent_at = se.get("sent_at")
            if not sent_at:
                continue
            step_id = se.get("sequence_step_id")
            conn.execute(
                "INSERT INTO scheduled_emails VALUES (?,?,?,?,?,?,?,?,?)",
                (se.get("id"), campaign_id, step_id,
                 order_map.get(step_id),
                 str(sent_at), str(se.get("status", "")),
                 se.get("lead_id"),
                 page))
            total_inserted += 1
        pages_fetched += 1

        if page % 50 == 0:
            conn.commit()
            print(f"  page {page}: {total_inserted} sent rows so far")
            sys.stdout.flush()
        time.sleep(0.1)

    conn.commit()
    print(f"  Done: {total_inserted} sent rows, "
          f"{pages_fetched} pages fetched"
          f"{' (stopped early - campaign exceeds accessible range)' if stopped_early else ''}")
    sys.stdout.flush()
    return total_inserted, pages_fetched, last_page, stopped_early


def collect_replies(conn, campaign_id=None):
    """Collect ALL replies cursor-paginated.

    If campaign_id is given, still collect the full feed (cursor pagination
    has no campaign filter) but report the count for the target campaign.
    """
    print("Collecting replies (cursor-paginated, full feed)...")
    sys.stdout.flush()
    page = 1
    cursor = None
    total_inserted = 0
    camp_inserted = 0
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
            if campaign_id and r.get("campaign_id") == campaign_id:
                camp_inserted += 1
        conn.commit()
        if page % 50 == 0:
            meta_total = (data.get("meta") or {}).get("total", "?")
            print(f"  page {page}: {total_inserted} reply rows "
                  f"({meta_total} total in feed), "
                  f"{camp_inserted} for campaign {campaign_id}")
            sys.stdout.flush()
        meta = data.get("meta") or {}
        cursor = meta.get("next_cursor")
        if not cursor:
            break
        page += 1
        time.sleep(0.05)
    print(f"  Total: {total_inserted} reply rows stored, "
          f"{camp_inserted} for campaign {campaign_id}")
    sys.stdout.flush()
    return total_inserted, camp_inserted


# ------------------------------------------------------------------ helpers

def _trunc(s, n):
    s = str(s) if s else ""
    return s[:n] if len(s) > n else s


def _strip_html(html):
    if not html:
        return ""
    text = re.sub(r'<[^>]+>', ' ', str(html))
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _pct(n, d):
    if not d:
        return "0.0"
    return f"{100.0 * n / d:.1f}"


# ------------------------------------------------------------------ analyze

def analyze(target_campaign_id, pages_fetched, total_pages, stopped_early,
            total_replies_stored, camp_replies_stored):
    print("=" * 60)
    print("ANALYZING")
    print("=" * 60)
    sys.stdout.flush()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    lines = []
    w = lines.append

    # Campaign info
    camp = conn.execute(
        "SELECT * FROM campaigns WHERE id = ?",
        (target_campaign_id,)).fetchone()
    camp_name = str(camp["name"]) if camp else "?"
    camp_sent = int(camp["emails_sent"]) if camp else 0
    camp_leads = int(camp["total_leads"]) if camp else 0

    # Sample scope
    sample_sent = conn.execute(
        "SELECT COUNT(*) FROM scheduled_emails "
        "WHERE campaign_id = ? AND sent_at IS NOT NULL AND sent_at != ''",
        (target_campaign_id,)).fetchone()[0]

    # Step definitions for target campaign
    step_defs = conn.execute("""
        SELECT id, step_order, wait_in_days, active, thread_reply,
               email_subject
        FROM sequence_steps
        WHERE campaign_id = ? AND is_variant = 0
        AND step_order IS NOT NULL
        ORDER BY step_order
    """, (target_campaign_id,)).fetchall()

    max_step = max((r["step_order"] for r in step_defs), default=0)

    # ============================================= BUILD THE REPORT
    w("# STEP INCREMENTALITY ANALYSIS — 2026-09-15")
    w("")
    w("TASK-103: Does step 5 generate incremental value?")
    w("")
    w("## THE QUESTION")
    w("")
    w("Of the people who did NOT reply to steps 1-4, what fraction replied to")
    w("step 5 — and how does that compare to the cost of sending it?")
    w("")
    w("## STATEMENT KINDS")
    w("")
    w("    PROVIDER FACT            the API returned this field with this value")
    w("    RESONATE RECONSTRUCTION  we derived it, and here is the derivation")
    w("    ATTRIBUTION HYPOTHESIS   we believe this reply relates to that touch")
    w("")
    w("## METHODOLOGY")
    w("")
    w("**Campaign selection:** The smallest campaign (by `emails_sent`) with "
      ">= 5 parent steps and real sends. This is a DELIBERATE SAMPLE of one "
      "campaign, not an estate-wide measurement.")
    w("")
    w("**Sent counts per step:** Count of scheduled email rows WHERE "
      "`sent_at` IS PRESENT, grouped by `step_order`. NEVER `meta.total`. "
      "Campaign 274 reports 30,411 scheduled rows with zero sent in its "
      "first 100 pages.")
    w("")
    w("**Pagination:** Offset pagination, 15 rows per page (per_page is "
      "accepted and IGNORED by the API). Accessible page cap: 500 pages. "
      "Offset pagination is refused with 422 beyond ~500 pages.")
    w("")
    w("**Reply feed:** Cursor-paginated, ALL replies collected. "
      "Auto-replies excluded from human reply counts. "
      "Replies joined to scheduled emails by `scheduled_email_id`.")
    w("")
    w("**No open-rate claim.** `open_tracking` is False estate-wide. "
      "Zero opens is an absent measurement, not a zero.")
    w("")
    w("---")
    w("")

    # ============================================= CAMPAIGN OVERVIEW
    w("## CAMPAIGN OVERVIEW (PROVIDER FACT)")
    w("")
    w(f"| Field | Value |")
    w(f"|-------|-------|")
    w(f"| Campaign ID | {target_campaign_id} |")
    w(f"| Name | {camp_name} |")
    w(f"| Status | {camp['status'] if camp else '?'} |")
    w(f"| emails_sent (provider fact) | {camp_sent} |")
    w(f"| total_leads | {camp_leads} |")
    w(f"| open_tracking | {'TRUE' if camp and camp['open_tracking'] else 'FALSE'} |")
    w(f"| Parent steps | {len(step_defs)} |")
    w(f"| Max step order | {max_step} |")
    w("")

    # Step definitions
    w("### Step definitions (PROVIDER FACT)")
    w("")
    w("| Step | wait_in_days | active | thread_reply | Subject (truncated) |")
    w("|------|-------------|--------|-------------|------|")
    for s in step_defs:
        tr = "TRUE" if s["thread_reply"] else "False"
        act = "TRUE" if s["active"] else "False"
        subj = str(s["email_subject"] or "")[:60]
        w(f"| {s['step_order']} | {s['wait_in_days']} | {act} | {tr} | {subj} |")
    w("")
    w("---")
    w("")

    # ============================================= PAGE BUDGET
    w("## PAGE BUDGET")
    w("")
    w(f"| Metric | Value |")
    w(f"|--------|-------|")
    w(f"| Total pages (meta.last_page) | {total_pages} |")
    w(f"| Accessible pages (capped at {ACCESSIBLE_PAGE_CAP}) | "
      f"{min(total_pages, ACCESSIBLE_PAGE_CAP)} |")
    w(f"| Pages actually fetched | {pages_fetched} |")
    w(f"| Stopped early (cap hit) | {'YES' if stopped_early else 'No'} |")
    w(f"| Scheduled email rows with sent_at present | {sample_sent} |")
    w(f"| Reply rows stored (full feed) | {total_replies_stored} |")
    w(f"| Reply rows for this campaign | {camp_replies_stored} |")
    w("")
    if stopped_early:
        w(f"**WARNING:** Campaign exceeds the 500-page accessible range. "
          f"Only the first {pages_fetched * 15} scheduled emails were "
          f"accessible. The measurement is a PREFIX SAMPLE, not exhaustive. "
          f"Step denominators are lower bounds.")
    else:
        w(f"**COMPLETE:** All {total_pages} pages were walked. "
          f"The measurement is exhaustive for this campaign.")
    w("")
    w("---")
    w("")

    # ============================================= PER-STEP DENOMINATORS
    w("## PER-STEP SENT COUNTS (RESONATE RECONSTRUCTION)")
    w("")
    w("Count of scheduled email rows WHERE `sent_at` IS PRESENT, "
      "grouped by step_order. This is the DENOMINATOR for each step's "
      "reply rate.")
    w("")

    step_sent = conn.execute("""
        SELECT step_order, COUNT(*) as sent
        FROM scheduled_emails
        WHERE campaign_id = ? AND sent_at IS NOT NULL AND sent_at != ''
        AND step_order IS NOT NULL
        GROUP BY step_order
        ORDER BY step_order
    """, (target_campaign_id,)).fetchall()

    sent_by_step = {r["step_order"]: r["sent"] for r in step_sent}
    total_sampled = sum(sent_by_step.values())

    w("| Step | Sent (rows with sent_at) | Share of sample |")
    w("|------|--------------------------|-----------------|")
    for step_order in sorted(sent_by_step.keys()):
        sent = sent_by_step[step_order]
        share = _pct(sent, total_sampled)
        w(f"| {step_order} | {sent} | {share}% |")
    w(f"| **Total** | **{total_sampled}** | **100%** |")
    w("")

    # Cross-check against provider fact
    w(f"**Cross-check:** Campaign `emails_sent` (PROVIDER FACT) = {camp_sent}. "
      f"Sampled sent rows = {total_sampled}.")
    if total_sampled > 0 and camp_sent > 0:
        coverage = _pct(total_sampled, camp_sent)
        w(f"Coverage: {coverage}% of provider-reported sends.")
        if stopped_early:
            w("The gap is expected: the 500-page cap truncates the sample.")
        elif total_sampled < camp_sent * 0.8:
            w("**NOTE:** Sampled rows are <80% of provider-reported sends. "
              "Some sent rows may lack `sent_at` or fall outside the "
              "paginated range.")
    w("")
    w("---")
    w("")

    # ============================================= PER-STEP REPLIES
    w("## PER-STEP REPLY COUNTS (ATTRIBUTION HYPOTHESIS)")
    w("")
    w("Human replies (type IN ('Tracked Reply','Untracked Reply'), "
      "automated_reply=0) joined to scheduled emails by `scheduled_email_id`.")
    w("")

    step_replies = conn.execute("""
        SELECT se.step_order,
               COUNT(*) as replies,
               SUM(r.interested) as interested
        FROM replies r
        JOIN scheduled_emails se ON r.scheduled_email_id = se.id
        WHERE se.campaign_id = ?
        AND r.type IN ('Tracked Reply','Untracked Reply')
        AND r.automated_reply = 0
        AND se.step_order IS NOT NULL
        GROUP BY se.step_order
        ORDER BY se.step_order
    """, (target_campaign_id,)).fetchall()

    replies_by_step = {}
    interested_by_step = {}
    for r in step_replies:
        replies_by_step[r["step_order"]] = r["replies"]
        interested_by_step[r["step_order"]] = r["interested"] or 0

    total_attributed = sum(replies_by_step.values())
    total_interested = sum(interested_by_step.values())

    w("| Step | Sent | Replied | Reply rate | Interested | Positive rate |")
    w("|------|------|---------|-----------|-----------|--------------|")
    all_steps = sorted(set(list(sent_by_step.keys()) +
                           list(replies_by_step.keys())))
    for step in all_steps:
        sent = sent_by_step.get(step, 0)
        replied = replies_by_step.get(step, 0)
        interested = interested_by_step.get(step, 0)
        rr = _pct(replied, sent) if sent else "n/a"
        pr = _pct(interested, replied) if replied else "n/a"
        w(f"| {step} | {sent} | {replied} | {rr}% | {interested} | {pr}% |")
    w(f"| **Total** | **{total_sampled}** | **{total_attributed}** | "
      f"**{_pct(total_attributed, total_sampled)}%** | "
      f"**{total_interested}** | "
      f"**{_pct(total_interested, total_attributed)}%** |")
    w("")

    # Attribution coverage
    human_replies_camp = conn.execute("""
        SELECT COUNT(*) as cnt FROM replies
        WHERE campaign_id = ?
        AND type IN ('Tracked Reply','Untracked Reply')
        AND automated_reply = 0
    """, (target_campaign_id,)).fetchone()
    total_human = human_replies_camp["cnt"] if human_replies_camp else 0

    w(f"**Attribution coverage:** Of {total_human} human replies in this "
      f"campaign, {total_attributed} join to the sampled scheduled emails "
      f"({_pct(total_attributed, total_human)}%). "
      f"The remainder reference scheduled emails outside the sample "
      f"(unsent rows, or rows beyond the accessible page range).")
    w("")
    w("---")
    w("")

    # ============================================= SURVIVOR ANALYSIS
    w("## SURVIVOR ANALYSIS: WHO ENTERS EACH STEP?")
    w("")
    w("A lead 'survives' to step N if they were sent step N's email. "
      "This is the denominator for incremental reply rate: of the people "
      "who received step N, how many replied AT step N (having not replied "
      "to earlier steps)?")
    w("")
    w("**Important:** We cannot directly observe 'did not reply to steps 1-4' "
      "from the scheduled email data alone. A reply to step 5 might be from "
      "someone who also replied to step 2 but was still sent step 5 (the "
      "provider does not always stop the sequence on reply). What we CAN "
      "compute is:")
    w("")
    w("1. How many leads were SENT each step's email (the denominator)")
    w("2. How many of those replies are ATTRIBUTED to that step")
    w("3. The reply rate at each step, holding the denominator explicit")
    w("")

    # Leads per step
    leads_per_step = conn.execute("""
        SELECT step_order,
               COUNT(DISTINCT lead_id) as unique_leads,
               COUNT(*) as total_sends
        FROM scheduled_emails
        WHERE campaign_id = ? AND sent_at IS NOT NULL AND sent_at != ''
        AND step_order IS NOT NULL
        GROUP BY step_order
        ORDER BY step_order
    """, (target_campaign_id,)).fetchall()

    leads_by_step = {}
    for r in leads_per_step:
        leads_by_step[r["step_order"]] = {
            "unique_leads": r["unique_leads"],
            "total_sends": r["total_sends"]}

    w("| Step | Unique leads sent | Total sends | "
      "Replies at this step | Reply rate (per lead) |")
    w("|------|------------------|-------------|"
      "---------------------|----------------------|")
    for step in all_steps:
        ld = leads_by_step.get(step, {"unique_leads": 0, "total_sends": 0})
        replied = replies_by_step.get(step, 0)
        ul = ld["unique_leads"]
        rr = _pct(replied, ul) if ul else "n/a"
        w(f"| {step} | {ul} | {ld['total_sends']} | {replied} | {rr}% |")
    w("")

    # Step-over-step decay in leads
    w("### Step-over-step lead decay")
    w("")
    w("| Step | Unique leads | vs. previous step | vs. step 1 |")
    w("|------|-------------|-------------------|-----------|")
    first_leads = leads_by_step.get(1, {}).get("unique_leads", 0)
    prev_leads = 0
    for step in all_steps:
        ul = leads_by_step.get(step, {}).get("unique_leads", 0)
        if prev_leads > 0:
            vs_prev = _pct(ul, prev_leads) + "%"
        else:
            vs_prev = "—"
        if first_leads > 0:
            vs_first = _pct(ul, first_leads) + "%"
        else:
            vs_first = "—"
        w(f"| {step} | {ul} | {vs_prev} | {vs_first} |")
        prev_leads = ul
    w("")
    w("---")
    w("")

    # ============================================= INCREMENTAL REPLIES
    w("## INCREMENTAL REPLIES PER STEP (ATTRIBUTION HYPOTHESIS)")
    w("")
    w("Each reply is attributed to exactly one step (the step of the "
      "scheduled email it references). The 'incremental reply' question is:")
    w("")
    w("    Of the replies attributed to step N, how many are the ONLY "
      "reply from that lead in the campaign?")
    w("")
    w("A lead that replied at step 2 AND step 5 contributes one reply to "
      "each step's count. The step-5 reply is only 'incremental' if the "
      "lead did NOT reply at steps 1-4.")
    w("")

    # Find leads that replied at each step
    # First, map each reply to its step
    lead_reply_steps = conn.execute("""
        SELECT r.lead_id, se.step_order
        FROM replies r
        JOIN scheduled_emails se ON r.scheduled_email_id = se.id
        WHERE se.campaign_id = ?
        AND r.type IN ('Tracked Reply','Untracked Reply')
        AND r.automated_reply = 0
        AND se.step_order IS NOT NULL
        ORDER BY r.lead_id, se.step_order
    """, (target_campaign_id,)).fetchall()

    # Build lead -> set of steps they replied at
    lead_steps = {}
    for r in lead_reply_steps:
        lid = r["lead_id"]
        if lid not in lead_steps:
            lead_steps[lid] = set()
        lead_steps[lid].add(r["step_order"])

    # For each step, count:
    # - total replies at that step
    # - replies from leads who ONLY replied at this step (purely incremental)
    # - replies from leads who also replied at earlier steps (not incremental)
    step_incremental = {}
    step_multi = {}
    for step in all_steps:
        purely_incremental = 0
        multi_step = 0
        for lid, steps in lead_steps.items():
            if step in steps:
                earlier = [s for s in steps if s < step]
                if not earlier:
                    purely_incremental += 1
                else:
                    multi_step += 1
        step_incremental[step] = purely_incremental
        step_multi[step] = multi_step

    w("| Step | Total replies at step | Purely incremental "
      "(no earlier reply) | Also replied earlier | "
      "Incremental reply rate (per lead entering step) |")
    w("|------|----------------------|------"
      "---------------------|---------------------|"
      "--------------------------------------------|")
    for step in all_steps:
        total_r = replies_by_step.get(step, 0)
        incr = step_incremental.get(step, 0)
        multi = step_multi.get(step, 0)
        ul = leads_by_step.get(step, {}).get("unique_leads", 0)
        # Survivors: leads entering this step who had NOT replied earlier
        # We approximate: leads sent at this step minus leads who replied
        # at earlier steps (from the lead_steps data)
        irr = _pct(incr, ul) if ul else "n/a"
        w(f"| {step} | {total_r} | {incr} | {multi} | {irr}% |")
    w("")

    total_purely_incr = sum(step_incremental.values())
    w(f"**Total purely incremental replies (no earlier reply from same "
      f"lead): {total_purely_incr}**")
    w("")

    # The step-5 specific answer
    w("---")
    w("")
    w("## THE STEP-5 ANSWER")
    w("")

    step5_sent = sent_by_step.get(5, 0)
    step5_leads = leads_by_step.get(5, {}).get("unique_leads", 0)
    step5_replies = replies_by_step.get(5, 0)
    step5_interested = interested_by_step.get(5, 0)
    step5_purely_incr = step_incremental.get(5, 0)
    step5_multi = step_multi.get(5, 0)

    # How many leads entering step 5 had NOT replied to steps 1-4?
    # Count leads who were sent step 5 AND whose reply set has no step < 5
    leads_at_5 = conn.execute("""
        SELECT DISTINCT lead_id FROM scheduled_emails
        WHERE campaign_id = ? AND step_order = 5
        AND sent_at IS NOT NULL AND sent_at != ''
    """, (target_campaign_id,)).fetchall()
    leads_at_5_ids = set(r["lead_id"] for r in leads_at_5)

    # Of those, how many had replied at steps 1-4?
    replied_earlier_than_5 = set()
    for lid, steps in lead_steps.items():
        if lid in leads_at_5_ids:
            earlier = [s for s in steps if s < 5]
            if earlier:
                replied_earlier_than_5.add(lid)

    survivors_at_5 = len(leads_at_5_ids) - len(replied_earlier_than_5)
    step5_replies_from_survivors = step5_purely_incr

    w(f"**Campaign {target_campaign_id} ({camp_name}):**")
    w("")
    w(f"| Metric | Value | n | Statement kind |")
    w(f"|--------|-------|---|----------------|")
    w(f"| Leads sent step 5 | {step5_leads} | "
      f"COUNT(DISTINCT lead_id) WHERE step_order=5 AND sent_at present | "
      f"RESONATE RECONSTRUCTION |")
    w(f"| Of those, also replied at steps 1-4 | "
      f"{len(replied_earlier_than_5)} | "
      f"leads in step-5 set who have a reply at step < 5 | "
      f"RESONATE RECONSTRUCTION |")
    w(f"| Survivors entering step 5 (no earlier reply) | "
      f"{survivors_at_5} | step-5 leads minus earlier repliers | "
      f"RESONATE RECONSTRUCTION |")
    w(f"| Replied AT step 5 | {step5_replies} | "
      f"replies joined to step-5 scheduled emails | "
      f"ATTRIBUTION HYPOTHESIS |")
    w(f"| Of those, purely incremental (no earlier reply) | "
      f"{step5_replies_from_survivors} | "
      f"replies from leads whose only reply is at step 5 | "
      f"ATTRIBUTION HYPOTHESIS |")
    w(f"| Also replied at earlier steps | {step5_multi} | "
      f"leads who replied at step 5 AND at least one earlier step | "
      f"ATTRIBUTION HYPOTHESIS |")
    w(f"| Interested (positive) at step 5 | {step5_interested} | "
      f"`interested` field from reply feed | PROVIDER FACT |")
    w("")

    if survivors_at_5 > 0:
        incr_rate = _pct(step5_replies_from_survivors, survivors_at_5)
        w(f"**Incremental reply rate at step 5:** "
          f"{step5_replies_from_survivors} / {survivors_at_5} = {incr_rate}%")
    else:
        w("**Incremental reply rate at step 5:** cannot be computed "
          "(zero survivors or zero leads at step 5)")
    w("")

    if step5_replies > 0:
        raw_rate = _pct(step5_replies, step5_leads)
        w(f"**Raw reply rate at step 5 (not incremental):** "
          f"{step5_replies} / {step5_leads} = {raw_rate}%")
    else:
        w("**Raw reply rate at step 5:** zero replies observed")
    w("")

    # Confidence assessment
    w("### Confidence assessment")
    w("")
    if step5_replies < 5:
        w(f"**LOW CONFIDENCE.** Only {step5_replies} replies at step 5. "
          f"This is too few to draw a conclusion. A single reply changes "
          f"the rate materially.")
    elif step5_replies < 15:
        w(f"**MODERATE CONFIDENCE.** {step5_replies} replies at step 5. "
          f"Enough to observe a pattern, but one or two outliers shift "
          f"the rate significantly.")
    else:
        w(f"**REASONABLE CONFIDENCE.** {step5_replies} replies at step 5. "
          f"Large enough sample for a directional conclusion.")
    w("")

    if stopped_early:
        w("**CAVEAT:** The 500-page cap truncated the scheduled email "
          "sample. Step-5 denominators may be undercounted if step-5 "
          "emails fall in the truncated tail of the pagination.")
    w("")
    w("---")
    w("")

    # ============================================= FULL STEP COMPARISON
    w("## FULL STEP-BY-STEP COMPARISON")
    w("")
    w("| Step | Sent | Leads | Replied | "
      "Reply rate | Purely incremental | "
      "Incr. rate | Interested |")
    w("|------|------|-------|---------|"
      "-----------|---------------------|"
      "-----------|-----------|")
    for step in all_steps:
        sent = sent_by_step.get(step, 0)
        leads = leads_by_step.get(step, {}).get("unique_leads", 0)
        replied = replies_by_step.get(step, 0)
        incr = step_incremental.get(step, 0)
        interested = interested_by_step.get(step, 0)
        rr = _pct(replied, leads) if leads else "n/a"
        ir = _pct(incr, leads) if leads else "n/a"
        w(f"| {step} | {sent} | {leads} | {replied} | "
          f"{rr}% | {incr} | {ir}% | {interested} |")
    w("")
    w("---")
    w("")

    # ============================================= COST COMPARISON
    w("## COST COMPARISON: IS STEP 5 WORTH THE CREDIT?")
    w("")
    w("Each sent email burns one email credit. The question is whether "
      "step 5's incremental replies justify that cost relative to earlier "
      "steps.")
    w("")

    # Compute cost-effectiveness: incremental replies per 100 sends
    w("| Step | Sends | Purely incremental replies | "
      "Incr. replies per 100 sends |")
    w("|------|-------|--------------------------|"
      "------------------------------|")
    for step in all_steps:
        leads = leads_by_step.get(step, {}).get("unique_leads", 0)
        incr = step_incremental.get(step, 0)
        per_100 = _pct(incr * 100, leads) if leads else "n/a"
        w(f"| {step} | {leads} | {incr} | {per_100} |")
    w("")

    if step5_leads > 0 and step5_purely_incr > 0:
        cost_per_incr = step5_leads / step5_purely_incr
        w(f"**Step 5 cost:** {cost_per_incr:.1f} email credits per "
          f"incremental reply.")
    elif step5_purely_incr == 0:
        w("**Step 5 cost:** No incremental replies observed. "
          "Every step-5 send is a cost with no observed return.")
    else:
        w("**Step 5 cost:** Cannot be computed (zero leads at step 5).")
    w("")
    w("---")
    w("")

    # ============================================= OBSERVATIONS AND HYPOTHESES
    w("## OBSERVATIONS (with n)")
    w("")
    w("1. "
      f"Campaign {target_campaign_id} has {len(step_defs)} parent steps "
      f"and {camp_sent} provider-reported sends.")
    w("2. "
      f"Sampled {total_sampled} sent rows across {pages_fetched} pages.")
    w("3. "
      f"Total human replies in campaign: {total_human}. "
      f"Attributed to sampled steps: {total_attributed} "
      f"({_pct(total_attributed, total_human)}%).")
    w("4. "
      f"Step-5 sends: {step5_leads} unique leads. "
      f"Step-5 replies: {step5_replies}. "
      f"Purely incremental: {step5_purely_incr}.")
    w("")
    w("## HYPOTHESES")
    w("")
    if step5_purely_incr > 0:
        w(f"- Step 5 generates {step5_purely_incr} incremental replies "
          f"from {survivors_at_5} survivors "
          f"({_pct(step5_purely_incr, survivors_at_5)}% rate). "
          f"Whether this justifies the credit cost depends on the "
          f"credit price and the reply value.")
    else:
        w("- Step 5 generated zero purely incremental replies in this "
          "campaign. Either the step is not reaching new responders, or "
          "the sample is too small to observe them.")
    w("")
    w("## PROVEN LEARNINGS")
    w("")
    w("None. One campaign is a sample, not a finding. A second campaign "
      "measurement would either confirm or contradict this.")
    w("")

    report = "\n".join(lines)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport written to {REPORT_PATH}")
    sys.stdout.flush()

    # Also print summary to stdout
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Campaign: {target_campaign_id} ({camp_name})")
    print(f"Parent steps: {len(step_defs)}")
    print(f"emails_sent (provider fact): {camp_sent}")
    print(f"Sampled sent rows: {total_sampled} across {pages_fetched} pages")
    print(f"Total human replies: {total_human}")
    print(f"Attributed replies: {total_attributed}")
    print(f"\nStep-5 specifically:")
    print(f"  Leads sent step 5: {step5_leads}")
    print(f"  Survivors (no earlier reply): {survivors_at_5}")
    print(f"  Replied at step 5: {step5_replies}")
    print(f"  Purely incremental: {step5_purely_incr}")
    print(f"  Interested: {step5_interested}")
    if survivors_at_5 > 0:
        print(f"  Incremental rate: "
              f"{_pct(step5_purely_incr, survivors_at_5)}%")

    conn.close()
    return report


# ------------------------------------------------------------------ main

def main():
    parser = argparse.ArgumentParser(description="TASK-103 step incrementality")
    parser.add_argument("--collect", action="store_true",
                        help="Collect data from providers")
    parser.add_argument("--analyze", action="store_true",
                        help="Analyze collected data")
    parser.add_argument("--both", action="store_true",
                        help="Collect then analyze (default)")
    parser.add_argument("--campaign-id", type=int, default=None,
                        help="Target a specific campaign instead of "
                             "auto-selecting the smallest")
    args = parser.parse_args()

    if not (args.collect or args.analyze):
        args.both = True

    load_env()

    target_id = args.campaign_id

    if args.collect or args.both:
        conn = init_db()
        campaigns = collect_campaigns(conn)
        collect_steps(conn, campaigns)

        if target_id is None:
            result = find_target_campaign(conn)
            if result is None:
                print("ERROR: No campaign found with >= 5 parent steps "
                      "and real sends.")
                sys.exit(1)
            target_id = result["id"]
            print(f"\nAuto-selected campaign {target_id} "
                  f"({result['name']}) with "
                  f"{result['emails_sent']} sends and "
                  f"{result['parent_steps']} parent steps")
            sys.stdout.flush()

        order_map = _build_step_info_map(conn)
        inserted, pages, total_pages, stopped = \
            collect_scheduled_emails_exhaustive(conn, target_id, order_map)
        total_replies, camp_replies = collect_replies(conn, target_id)
        conn.close()
    else:
        # Just analyze existing data
        if target_id is None:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            result = find_target_campaign(conn)
            conn.close()
            if result is None:
                print("ERROR: No campaign found. Run --collect first.")
                sys.exit(1)
            target_id = result["id"]

        # Recover page budget from the data
        pages = conn.execute(
            "SELECT MAX(page_number) FROM scheduled_emails "
            "WHERE campaign_id = ?", (target_id,)).fetchone()[0] or 0

    if args.analyze or args.both:
        # Recover page budget info
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        max_page = conn.execute(
            "SELECT MAX(page_number) FROM scheduled_emails "
            "WHERE campaign_id = ?", (target_id,)).fetchone()[0] or 0
        total_replies = conn.execute(
            "SELECT COUNT(*) FROM replies").fetchone()[0]
        camp_replies = conn.execute(
            "SELECT COUNT(*) FROM replies WHERE campaign_id = ?",
            (target_id,)).fetchone()[0]

        # Check if we stopped early by trying to fetch one more page
        # (we can't know for sure without the original last_page, but
        # we can check if max_page == ACCESSIBLE_PAGE_CAP)
        stopped = max_page >= ACCESSIBLE_PAGE_CAP

        # Get total pages from first scheduled email query
        try:
            data = get(f"/campaigns/{target_id}/scheduled-emails",
                       {"page": 1})
            meta = data.get("meta") or {}
            total_pages = int(meta.get("last_page", max_page))
        except Exception:
            total_pages = max_page

        conn.close()

        analyze(target_id, max_page, total_pages, stopped,
                total_replies, camp_replies)


if __name__ == "__main__":
    main()
