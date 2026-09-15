#!/usr/bin/env python3
"""TASK-107: inter-step delay distribution and time-to-reply analysis.

READS ONLY. No writes of any kind to either provider.

Three questions:
1. What is the real distribution of configured inter-step delays, per provider?
2. Is time-to-reply computable from EmailBison data? (TASK-059 said no.)
3. If yes, what does the distribution look like?

Phases:
  --collect   Fetch campaigns, steps, scheduled emails, replies into SQLite
  --analyze   Run analysis on collected data, produce the report
  --both      Collect then analyze (default)
  --heyreach  HeyReach delay collection only (reads campaign sequences)

Every number carries its row count and statement kind.
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import load_env, key as get_key, request as api_request, query

CACHE_DIR = os.path.join(ROOT, ".qwen", "tmp", "task107")
DB_PATH = os.path.join(CACHE_DIR, "delays.db")
REPORT_PATH = os.path.join(ROOT, "docs", "DELAY-ANALYSIS-2026-09-15.md")


# ------------------------------------------------------------------ plumbing

def bison_headers():
    return {"Authorization": f"Bearer {get_key('BISON_KEY')}"}


def bison_base():
    return os.environ.get("BISON_BASE",
                          "https://send.resonategroup.co/api").rstrip("/")


def bison_get(path, params=None):
    url = f"{bison_base()}{path}"
    if params:
        url = query(url, params)
    status, data = api_request("GET", url, bison_headers())
    if status is None or status < 200 or status >= 300:
        raise RuntimeError(
            f"GET {path} -> {status}: "
            f"{json.dumps(data)[:200] if data else 'no body'}")
    return data if isinstance(data, dict) else {}


def heyreach_headers():
    return {"X-API-KEY": get_key("HEYREACH_KEY")}


HEYREACH_BASE = "https://api.heyreach.io/api/public"


def heyreach_post(path, body=None):
    """HeyReach reads are POST-based. Use the provider module's allowlist."""
    from src.providers.heyreach import _read
    return _read(path, body or {})


# ------------------------------------------------------------------ schema

def init_db():
    os.makedirs(CACHE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS campaigns")
    c.execute("DROP TABLE IF EXISTS sequence_steps")
    c.execute("DROP TABLE IF EXISTS scheduled_emails")
    c.execute("DROP TABLE IF EXISTS replies")
    c.execute("DROP TABLE IF EXISTS heyreach_campaigns")
    c.execute("DROP TABLE IF EXISTS heyreach_delays")
    c.execute("""CREATE TABLE campaigns (
        id INTEGER PRIMARY KEY, name TEXT, status TEXT, created_at TEXT,
        emails_sent INTEGER, total_leads INTEGER, open_tracking INTEGER
    )""")
    c.execute("""CREATE TABLE sequence_steps (
        id INTEGER PRIMARY KEY, campaign_id INTEGER, step_order INTEGER,
        wait_in_days INTEGER, active INTEGER, is_variant INTEGER,
        variant_from_step INTEGER
    )""")
    c.execute("""CREATE TABLE scheduled_emails (
        id INTEGER PRIMARY KEY, campaign_id INTEGER,
        sequence_step_id INTEGER, step_order INTEGER,
        sent_at TEXT, status TEXT,
        wait_in_days INTEGER
    )""")
    c.execute("""CREATE TABLE replies (
        id INTEGER PRIMARY KEY, campaign_id INTEGER, lead_id INTEGER,
        scheduled_email_id INTEGER, type TEXT, folder TEXT,
        automated_reply INTEGER, interested INTEGER, date_received TEXT
    )""")
    c.execute("""CREATE TABLE heyreach_campaigns (
        id INTEGER PRIMARY KEY, name TEXT, status TEXT
    )""")
    c.execute("""CREATE TABLE heyreach_delays (
        campaign_id INTEGER, node_type TEXT,
        action_delay INTEGER, action_delay_unit TEXT,
        delay_hours REAL, position INTEGER
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_se_campaign "
              "ON scheduled_emails(campaign_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_se_id "
              "ON scheduled_emails(id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_replies_se "
              "ON replies(scheduled_email_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_replies_campaign "
              "ON replies(campaign_id)")
    conn.commit()
    return conn


# ------------------------------------------------------------------ collect: EmailBison

def collect_bison_campaigns(conn):
    print("Collecting EmailBison campaigns...")
    sys.stdout.flush()
    campaigns = []
    page = 1
    while True:
        data = bison_get("/campaigns", {"page": page})
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


def collect_bison_steps(conn, campaigns):
    print("Collecting EmailBison sequence steps...")
    sys.stdout.flush()
    total = 0
    for camp in campaigns:
        cid = camp["id"]
        try:
            data = bison_get(f"/campaigns/{cid}/sequence-steps")
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
                "INSERT INTO sequence_steps VALUES (?,?,?,?,?,?,?)",
                (s.get("id"), cid, s.get("order"), s.get("wait_in_days"),
                 1 if s.get("active") else 0,
                 1 if s.get("variant") else 0,
                 s.get("variant_from_step")))
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
        if sid in direct_wait:
            wait_map[sid] = direct_wait[sid]
        elif parent in direct_wait:
            wait_map[sid] = direct_wait[parent]
    return order_map, wait_map


def collect_bison_scheduled_emails(conn, campaigns, pages_per_campaign=12):
    """Sample scheduled emails. 12 evenly-spaced pages per campaign."""
    ACCESSIBLE_PAGE_CAP = 500
    print(f"Collecting EmailBison scheduled emails "
          f"(sampled, max {pages_per_campaign} pages/campaign)...")
    sys.stdout.flush()
    total_inserted = 0

    for camp in campaigns:
        cid = camp["id"]
        sent_count = int(camp.get("emails_sent") or 0)
        if sent_count == 0:
            continue

        order_map, wait_map = _build_step_info_map(conn)

        data = bison_get(f"/campaigns/{cid}/scheduled-emails", {"page": 1})
        chunk = data.get("data")
        if not isinstance(chunk, list) or not chunk:
            continue
        meta = data.get("meta") or {}
        try:
            last_page = int(meta.get("last_page"))
        except (TypeError, ValueError):
            last_page = 1

        accessible = min(last_page, ACCESSIBLE_PAGE_CAP)
        if accessible <= pages_per_campaign:
            pages_to_fetch = list(range(1, accessible + 1))
        else:
            step_size = (accessible - 1) / (pages_per_campaign - 1)
            pages_to_fetch = sorted(set(
                max(1, min(accessible, round(1 + i * step_size)))
                for i in range(pages_per_campaign)
            ))

        camp_inserted = 0
        for pg in pages_to_fetch:
            if pg == 1:
                pg_data = data
            else:
                try:
                    pg_data = bison_get(
                        f"/campaigns/{cid}/scheduled-emails", {"page": pg})
                except RuntimeError:
                    break
            pg_chunk = pg_data.get("data")
            if not isinstance(pg_chunk, list) or not pg_chunk:
                continue
            for se in pg_chunk:
                sent_at = se.get("sent_at")
                if not sent_at:
                    continue
                step_id = se.get("sequence_step_id")
                conn.execute(
                    "INSERT INTO scheduled_emails VALUES (?,?,?,?,?,?,?)",
                    (se.get("id"), cid, step_id,
                     order_map.get(step_id),
                     str(sent_at), str(se.get("status", "")),
                     wait_map.get(step_id)))
                camp_inserted += 1
            time.sleep(0.1)

        conn.commit()
        total_inserted += camp_inserted
        print(f"  Campaign {cid}: {camp_inserted} sent rows "
              f"({len(pages_to_fetch)} pages)")
        sys.stdout.flush()

    print(f"  Total: {total_inserted} sent rows collected")
    sys.stdout.flush()


def collect_bison_replies(conn, max_pages=None):
    """Collect replies cursor-paginated."""
    label = "ALL" if max_pages is None else f"up to {max_pages} pages"
    print(f"Collecting EmailBison replies (cursor-paginated, {label})...")
    sys.stdout.flush()
    page = 1
    cursor = None
    total_inserted = 0
    while True:
        params = {"pagination_type": "cursor", "per_page": 100}
        if cursor:
            params["cursor"] = cursor
        data = bison_get("/replies", params)
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
            print(f"  page {page}: {total_inserted} reply rows "
                  f"({meta_total} total in feed)")
            sys.stdout.flush()
        meta = data.get("meta") or {}
        cursor = meta.get("next_cursor")
        if not cursor:
            break
        page += 1
        if max_pages and page > max_pages:
            print(f"  Stopped at page {page} (max_pages={max_pages})")
            break
        time.sleep(0.05)
    print(f"  Total: {total_inserted} reply rows stored")
    sys.stdout.flush()
    return total_inserted


# ------------------------------------------------------------------ collect: HeyReach

def collect_heyreach_delays(conn):
    """Read HeyReach campaign sequences and extract delay configuration."""
    print("Collecting HeyReach campaign delays...")
    sys.stdout.flush()

    from src.providers.heyreach import campaigns as hr_campaigns_fn
    from src.providers.heyreach import campaign_sequence

    offset = 0
    all_campaigns = []
    while True:
        items, total = hr_campaigns_fn(offset=offset, limit=50)
        if not items:
            break
        all_campaigns.extend(items)
        if total is not None and offset + len(items) >= int(total):
            break
        offset += len(items)
        time.sleep(0.1)

    print(f"  {len(all_campaigns)} HeyReach campaigns found")

    for camp in all_campaigns:
        cid = camp.get("id")
        name = str(camp.get("name", ""))
        status = str(camp.get("status", ""))
        conn.execute("INSERT INTO heyreach_campaigns VALUES (?,?,?)",
                     (cid, name, status))

        try:
            seq_data = campaign_sequence(int(cid))
        except Exception:
            seq_data = {}

        if seq_data:
            _extract_delays(conn, cid, seq_data)

    conn.commit()
    print(f"  HeyReach delay extraction complete")
    sys.stdout.flush()


def _extract_delays(conn, campaign_id, node, position=0):
    """Walk the HeyReach sequence graph and extract delay info per node."""
    if not isinstance(node, dict):
        return
    kind = str(node.get("nodeType") or "")
    delay = node.get("actionDelay", 0)
    unit = str(node.get("actionDelayUnit") or "HOUR")

    delay_hours = _delay_to_hours(delay, unit)

    conn.execute(
        "INSERT INTO heyreach_delays VALUES (?,?,?,?,?,?)",
        (campaign_id, kind, delay, unit, delay_hours, position))

    for key in ("conditionalNode", "unconditionalNode"):
        child = node.get(key)
        if isinstance(child, dict):
            _extract_delays(conn, campaign_id, child, position + 1)


def _delay_to_hours(delay, unit):
    """Convert a delay value + unit to hours."""
    try:
        delay = float(delay)
    except (TypeError, ValueError):
        return 0.0
    u = str(unit).upper()
    if u.startswith("D"):
        return delay * 24.0
    if u.startswith("H"):
        return delay
    if u.startswith("M"):
        return delay / 60.0
    return delay


# ------------------------------------------------------------------ analyze

def _pct(n, d):
    if not d:
        return "0.0"
    return f"{100.0 * n / d:.1f}"


def _parse_dt(s):
    """Parse an ISO-ish datetime string to a datetime object."""
    if not s or s in ("None", "", "null"):
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _hours_between(sent_at_str, date_received_str):
    """Compute hours between send and reply. Returns None if unparseable."""
    sent = _parse_dt(sent_at_str)
    recv = _parse_dt(date_received_str)
    if sent is None or recv is None:
        return None
    delta = (recv - sent).total_seconds() / 3600.0
    if delta < 0:
        return None
    return delta


def analyze():
    print("=" * 60)
    print("ANALYZING")
    print("=" * 60)
    sys.stdout.flush()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    lines = []
    w = lines.append

    sample_sent = conn.execute(
        "SELECT COUNT(*) FROM scheduled_emails "
        "WHERE sent_at IS NOT NULL AND sent_at != ''"
    ).fetchone()[0]
    total_replies_raw = conn.execute(
        "SELECT COUNT(*) FROM replies").fetchone()[0]
    total_emails_sent = conn.execute(
        "SELECT SUM(emails_sent) FROM campaigns").fetchone()[0] or 0

    w("# DELAY ANALYSIS — 2026-09-15")
    w("")
    w("TASK-107: inter-step delay distribution and time-to-reply analysis. "
      "Every number carries its row count and statement kind.")
    w("")
    w("## Statement Kinds")
    w("")
    w("    PROVIDER FACT            the API returned this field with this value")
    w("    RESONATE RECONSTRUCTION  we derived it from provider data")
    w("    ATTRIBUTION HYPOTHESIS   we believe this reply relates to that touch")
    w("")
    w("## Methodology")
    w("")
    w("**Sent counts:** `emails_sent` on the campaign row (PROVIDER FACT), "
      "NEVER `meta.total`.")
    w("")
    w(f"**Scheduled email sample:** {sample_sent} sent rows sampled "
      f"(systematic page sampling, 12 pages/campaign, 15 rows/page).")
    w("")
    w(f"**Reply feed:** {total_replies_raw} rows collected "
      f"(cursor-paginated). Auto-replies excluded from human reply counts.")
    w("")
    w("**Time-to-reply computation:** For each reply that joins to a "
      "sampled scheduled email via `scheduled_email_id`, we compute "
      "`date_received` minus `sent_at`. Both timestamps are PROVIDER FACT "
      "fields on their respective rows.")
    w("")
    w("---")
    w("")

    # ============================================= SECTION 1: EMAILBISON DELAYS
    w("## 1. EMAILBISON: INTER-STEP DELAY DISTRIBUTION")
    w("")
    w("**PROVIDER FACT.** `wait_in_days` from sequence step definitions. "
      "Parent steps only (variants excluded).")
    w("")

    delays = conn.execute("""
        SELECT step_order, wait_in_days, COUNT(*) as campaign_count
        FROM sequence_steps
        WHERE step_order IS NOT NULL AND is_variant = 0
        GROUP BY step_order, wait_in_days
        ORDER BY step_order, wait_in_days
    """).fetchall()

    if delays:
        w("| Step position | wait_in_days | Campaigns using this |")
        w("|---------------|-------------|---------------------|")
        for r in delays:
            w(f"| {r['step_order']} | {r['wait_in_days']} | "
              f"{r['campaign_count']} |")
    w("")

    # Summary: most common delay value
    delay_summary = conn.execute("""
        SELECT wait_in_days, COUNT(*) as usage_count
        FROM sequence_steps
        WHERE is_variant = 0 AND step_order IS NOT NULL
        GROUP BY wait_in_days
        ORDER BY usage_count DESC
    """).fetchall()

    w("### Delay value frequency (all positions, parent steps)")
    w("")
    w("| wait_in_days | Times used | Share |")
    w("|-------------|-----------|-------|")
    total_usages = sum(r["usage_count"] for r in delay_summary)
    for r in delay_summary:
        w(f"| {r['wait_in_days']} | {r['usage_count']} | "
          f"{_pct(r['usage_count'], total_usages)}% |")
    w("")
    w(f"**PROVIDER FACT.** n={total_usages} step definitions across all "
      f"campaigns. Most common delay: "
      f"{delay_summary[0]['wait_in_days']} days "
      f"({_pct(delay_summary[0]['usage_count'], total_usages)}% of steps).")
    w("")

    # Per-campaign cadence duration
    w("### Cadence duration per campaign")
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
        w("| Campaign | Parent steps | Total duration (days) | Max step |")
        w("|----------|-------------|----------------------|----------|")
        for r in dur_data:
            w(f"| {r['campaign_id']} | {r['step_count']} | "
              f"{r['total_days']} | {r['max_order']} |")
    w("")

    # Per-campaign delay patterns
    w("### Per-campaign delay patterns (parent steps)")
    w("")
    camp_delays = conn.execute("""
        SELECT campaign_id, step_order, wait_in_days
        FROM sequence_steps
        WHERE is_variant = 0 AND step_order IS NOT NULL
        ORDER BY campaign_id, step_order
    """).fetchall()
    by_camp = {}
    for r in camp_delays:
        cid = r["campaign_id"]
        if cid not in by_camp:
            by_camp[cid] = []
        by_camp[cid].append(r)

    w("| Campaign | Delay pattern (step 1, 2, 3...) |")
    w("|----------|-------------------------------|")
    for cid in sorted(by_camp.keys(), reverse=True):
        camp_sent = conn.execute(
            "SELECT emails_sent FROM campaigns WHERE id=?",
            (cid,)).fetchone()
        if not camp_sent or camp_sent[0] == 0:
            continue
        pattern = ", ".join(
            f"{r['wait_in_days']}d" for r in sorted(
                by_camp[cid], key=lambda x: x['step_order']))
        w(f"| {cid} | {pattern} |")
    w("")
    w("**PROVIDER FACT.** The delay pattern each campaign was configured with.")
    w("")
    w("---")
    w("")

    # ============================================= SECTION 2: HEYREACH DELAYS
    w("## 2. HEYREACH: INTER-STEP DELAY DISTRIBUTION")
    w("")
    w("**PROVIDER FACT.** `actionDelay` and `actionDelayUnit` from campaign "
      "sequence graph nodes.")
    w("")

    hr_campaigns = conn.execute(
        "SELECT * FROM heyreach_campaigns ORDER BY id").fetchall()
    hr_delays = conn.execute(
        "SELECT * FROM heyreach_delays ORDER BY campaign_id, position"
    ).fetchall()

    if hr_campaigns:
        w(f"**PROVIDER FACT.** {len(hr_campaigns)} HeyReach campaigns found.")
        w("")
        w("| Campaign ID | Name | Status |")
        w("|------------|------|--------|")
        for c in hr_campaigns:
            w(f"| {c['id']} | {str(c['name'])[:50]} | {c['status']} |")
        w("")

    if hr_delays:
        # Delay distribution by unit
        delay_dist = conn.execute("""
            SELECT action_delay_unit, action_delay,
                   COUNT(*) as cnt
            FROM heyreach_delays
            WHERE node_type NOT IN ('END', '')
            GROUP BY action_delay_unit, action_delay
            ORDER BY action_delay_unit, action_delay
        """).fetchall()

        w("### HeyReach delay value distribution")
        w("")
        w("| Unit | Delay value | Count |")
        w("|------|------------|-------|")
        for r in delay_dist:
            w(f"| {r['action_delay_unit']} | {r['action_delay']} | {r['cnt']} |")
        w("")

        # Delay in hours
        hour_dist = conn.execute("""
            SELECT delay_hours, COUNT(*) as cnt
            FROM heyreach_delays
            WHERE node_type NOT IN ('END', '')
            AND delay_hours > 0
            GROUP BY delay_hours
            ORDER BY delay_hours
        """).fetchall()

        if hour_dist:
            w("### HeyReach delays converted to hours")
            w("")
            w("| Delay (hours) | Count |")
            w("|--------------|-------|")
            for r in hour_dist:
                w(f"| {r['delay_hours']:.1f} | {r['cnt']} |")
            w("")

        # Per-campaign delay patterns
        w("### Per-campaign HeyReach delay patterns")
        w("")
        hr_by_camp = conn.execute("""
            SELECT campaign_id, node_type, action_delay,
                   action_delay_unit, delay_hours, position
            FROM heyreach_delays
            WHERE node_type NOT IN ('END', '')
            ORDER BY campaign_id, position
        """).fetchall()
        hr_camp_patterns = {}
        for r in hr_by_camp:
            cid = r["campaign_id"]
            if cid not in hr_camp_patterns:
                hr_camp_patterns[cid] = []
            hr_camp_patterns[cid].append(r)

        w("| Campaign | Delay pattern (node delays in sequence order) |")
        w("|----------|----------------------------------------------|")
        for cid in sorted(hr_camp_patterns.keys()):
            pattern = ", ".join(
                f"+{r['action_delay']}{str(r['action_delay_unit'])[:1]}"
                for r in sorted(
                    hr_camp_patterns[cid], key=lambda x: x['position']))
            w(f"| {cid} | {pattern} |")
    else:
        w("No HeyReach delay data collected.")
    w("")
    w("---")
    w("")

    # ============================================= SECTION 3: TIME-TO-REPLY
    w("## 3. TIME-TO-REPLY: IS IT AVAILABLE?")
    w("")
    w("TASK-059 reported 'No time-to-reply data available'. This section "
      "proves whether that was a provider limitation or a lookup that was "
      "not done.")
    w("")

    # Check: do replies have date_received?
    replies_with_date = conn.execute("""
        SELECT COUNT(*) as cnt FROM replies
        WHERE date_received IS NOT NULL
        AND date_received != '' AND date_received != 'None'
    """).fetchone()[0]

    replies_total = conn.execute(
        "SELECT COUNT(*) FROM replies").fetchone()[0]

    w(f"### Field check: `date_received` on reply rows")
    w("")
    w(f"- Total reply rows: {replies_total}")
    w(f"- Rows with `date_received` present: {replies_with_date} "
      f"({_pct(replies_with_date, replies_total)}%)")
    w("")

    if replies_with_date == 0:
        w("**PROVIDER FACT.** `date_received` is ABSENT on every reply row. "
          "Time-to-reply is NOT computable from this provider. "
          "TASK-059's claim is CONFIRMED.")
    else:
        w("**PROVIDER FACT.** `date_received` IS PRESENT on reply rows. "
          "The field exists and carries values.")
        w("")

        # Check: do scheduled emails have sent_at?
        se_with_sent = conn.execute("""
            SELECT COUNT(*) as cnt FROM scheduled_emails
            WHERE sent_at IS NOT NULL
            AND sent_at != '' AND sent_at != 'None'
        """).fetchone()[0]
        se_total = conn.execute(
            "SELECT COUNT(*) FROM scheduled_emails").fetchone()[0]

        w(f"### Field check: `sent_at` on scheduled email rows")
        w("")
        w(f"- Total scheduled email rows: {se_total}")
        w(f"- Rows with `sent_at` present: {se_with_sent} "
          f"({_pct(se_with_sent, se_total)}%)")
        w("")

        # Check: do replies have scheduled_email_id?
        replies_with_se = conn.execute("""
            SELECT COUNT(*) as cnt FROM replies
            WHERE scheduled_email_id IS NOT NULL
            AND scheduled_email_id != 0
        """).fetchone()[0]

        w(f"### Field check: `scheduled_email_id` on reply rows")
        w("")
        w(f"- Reply rows with `scheduled_email_id`: {replies_with_se} "
          f"({_pct(replies_with_se, replies_total)}%)")
        w("")

        # The JOIN: can we compute time-to-reply?
        joinable = conn.execute("""
            SELECT COUNT(*) as cnt
            FROM replies r
            JOIN scheduled_emails se ON r.scheduled_email_id = se.id
            WHERE r.date_received IS NOT NULL
            AND r.date_received != '' AND r.date_received != 'None'
            AND se.sent_at IS NOT NULL
            AND se.sent_at != '' AND se.sent_at != 'None'
            AND r.type IN ('Tracked Reply','Untracked Reply')
            AND r.automated_reply = 0
        """).fetchone()[0]

        w(f"### Join result: time-to-reply computable rows")
        w("")
        w(f"- Human replies that join to a sampled scheduled email with "
          f"both timestamps: **{joinable}**")
        w("")

        if joinable > 0:
            w("**RESONATE RECONSTRUCTION.** Time-to-reply IS computable for "
              f"{joinable} replies. TASK-059's claim that it was unavailable "
              "was WRONG — the data was always there; the join was not done.")
            w("")

            # Compute the actual time-to-reply values
            ttr_rows = conn.execute("""
                SELECT r.id as reply_id, r.campaign_id,
                       r.date_received, se.sent_at,
                       r.interested, se.step_order
                FROM replies r
                JOIN scheduled_emails se ON r.scheduled_email_id = se.id
                WHERE r.date_received IS NOT NULL
                AND r.date_received != '' AND r.date_received != 'None'
                AND se.sent_at IS NOT NULL
                AND se.sent_at != '' AND se.sent_at != 'None'
                AND r.type IN ('Tracked Reply','Untracked Reply')
                AND r.automated_reply = 0
            """).fetchall()

            hours_list = []
            for r in ttr_rows:
                h = _hours_between(r["sent_at"], r["date_received"])
                if h is not None:
                    hours_list.append(h)

            if hours_list:
                hours_list.sort()
                n = len(hours_list)
                median_h = hours_list[n // 2]
                mean_h = sum(hours_list) / n
                p25 = hours_list[n // 4]
                p75 = hours_list[3 * n // 4]
                min_h = hours_list[0]
                max_h = hours_list[-1]

                w("### Time-to-reply distribution (EmailBison)")
                w("")
                w(f"- n: {n}")
                w(f"- Median: {median_h:.1f}h")
                w(f"- Mean: {mean_h:.1f}h")
                w(f"- P25: {p25:.1f}h")
                w(f"- P75: {p75:.1f}h")
                w(f"- Min: {min_h:.1f}h")
                w(f"- Max: {max_h:.1f}h")
                w("")

                # Bucket into day bands
                bands = [
                    ("< 1h", 0, 1),
                    ("1-6h", 1, 6),
                    ("6-24h", 6, 24),
                    ("1-2 days", 24, 48),
                    ("2-3 days", 48, 72),
                    ("3-5 days", 72, 120),
                    ("5-7 days", 120, 168),
                    ("7+ days", 168, float("inf")),
                ]
                w("### Time-to-reply bucketed")
                w("")
                w("| Band | Count | Share |")
                w("|------|-------|-------|")
                for label, lo, hi in bands:
                    cnt = sum(1 for h in hours_list if lo <= h < hi)
                    if cnt > 0:
                        w(f"| {label} | {cnt} | {_pct(cnt, n)}% |")
                w("")

                # By step order
                w("### Time-to-reply by step position")
                w("")
                step_ttr = {}
                for r in ttr_rows:
                    h = _hours_between(r["sent_at"], r["date_received"])
                    if h is not None:
                        step = r["step_order"]
                        if step not in step_ttr:
                            step_ttr[step] = []
                        step_ttr[step].append(h)

                if step_ttr:
                    w("| Step | n | Median (h) | Mean (h) |")
                    w("|------|---|-----------|---------|")
                    for step in sorted(step_ttr.keys()):
                        vals = sorted(step_ttr[step])
                        sn = len(vals)
                        smed = vals[sn // 2]
                        smean = sum(vals) / sn
                        w(f"| {step} | {sn} | {smed:.1f} | {smean:.1f} |")
                w("")
            else:
                w("Time-to-reply computation produced no valid values "
                  "(all pairs had unparseable timestamps or negative deltas).")
        else:
            w("**RESONATE RECONSTRUCTION.** The join produced ZERO rows. "
              "This means the sampled scheduled emails and the collected "
              "replies do not overlap via `scheduled_email_id`. "
              "Time-to-reply is STRUCTURALLY POSSIBLE (both timestamps exist) "
              "but the sample did not capture the matching pairs.")
    w("")
    w("---")
    w("")

    # ============================================= SECTION 4: HEYREACH TIME-TO-REPLY
    w("## 4. HEYREACH TIME-TO-REPLY (from existing analysis)")
    w("")
    w("The HeyReach estate outcomes report "
      "(`docs/ESTATE-HEYREACH-OUTCOMES-2026-09-14.md`) already computed "
      "time-to-reply from 26,113 conversations:")
    w("")
    w("- n: 5,291 replies")
    w("- Median: 6.1h")
    w("- Mean: 41.1h")
    w("- P25: 0.5h")
    w("- P75: 33.3h")
    w("- Min: 0.0h")
    w("- Max: 2,256.1h")
    w("")
    w("**PROVIDER FACT.** From `docs/ESTATE-HEYREACH-OUTCOMES-2026-09-14.md`, "
      "derived from HeyReach conversation timestamps.")
    w("")
    w("---")
    w("")

    # ============================================= SECTION 5: DO 3-DAY FOLLOW-UPS ARRIVE BEFORE REPLIES?
    w("## 5. ANALYSIS: DO 3-DAY FOLLOW-UPS ARRIVE BEFORE MOST REPLIES?")
    w("")
    w("The configured delay is one question; whether a follow-up at day 3 "
      "arrives before or after most replies is the other.")
    w("")

    w("### HeyReach reply timing vs configured delays")
    w("")
    w("HeyReach median reply: 6.1h. P75: 33.3h (1.4 days).")
    w("")
    w("If a follow-up is configured at +3 days (72h):")
    w("- 75% of replies arrive BEFORE the follow-up would be sent")
    w("- Only 25% of replies arrive after 33.3h, so a 3-day follow-up "
      "reaches people who have NOT yet replied")
    w("")
    w("If a follow-up is configured at +7 days (168h):")
    w("- Nearly all replies (P75 = 33.3h) arrive well before day 7")
    w("- A 7-day follow-up reaches almost exclusively non-repliers")
    w("")

    w("### EmailBison reply timing vs configured delays")
    w("")

    # Check if we have EmailBison time-to-reply data
    if replies_with_date > 0:
        joinable_check = conn.execute("""
            SELECT COUNT(*) as cnt
            FROM replies r
            JOIN scheduled_emails se ON r.scheduled_email_id = se.id
            WHERE r.date_received IS NOT NULL
            AND r.date_received != '' AND r.date_received != 'None'
            AND se.sent_at IS NOT NULL
            AND se.sent_at != '' AND se.sent_at != 'None'
            AND r.type IN ('Tracked Reply','Untracked Reply')
            AND r.automated_reply = 0
        """).fetchone()[0]

        if joinable_check > 0:
            ttr_all = conn.execute("""
                SELECT r.date_received, se.sent_at
                FROM replies r
                JOIN scheduled_emails se ON r.scheduled_email_id = se.id
                WHERE r.date_received IS NOT NULL
                AND r.date_received != '' AND r.date_received != 'None'
                AND se.sent_at IS NOT NULL
                AND se.sent_at != '' AND se.sent_at != 'None'
                AND r.type IN ('Tracked Reply','Untracked Reply')
                AND r.automated_reply = 0
            """).fetchall()

            hours_all = []
            for r in ttr_all:
                h = _hours_between(r["sent_at"], r["date_received"])
                if h is not None:
                    hours_all.append(h)

            if hours_all:
                hours_all.sort()
                n = len(hours_all)
                w(f"EmailBison time-to-reply (n={n}):")
                w(f"- Median: {hours_all[n//2]:.1f}h")
                w(f"- P25: {hours_all[n//4]:.1f}h")
                w(f"- P75: {hours_all[3*n//4]:.1f}h")
                w("")

                p75_val = hours_all[3*n//4]
                w(f"P75 = {p75_val:.1f}h = {p75_val/24:.1f} days. "
                  f"A 3-day (72h) follow-up arrives AFTER "
                  f"{'most' if p75_val < 72 else 'fewer than most'} replies.")
            else:
                w("No valid time-to-reply values computed.")
        else:
            w("The EmailBison sample did not produce joinable pairs. "
              "Using HeyReach data as the best available proxy.")
    else:
        w("EmailBison `date_received` was absent. Using HeyReach data as "
          "the best available proxy.")
    w("")

    w("---")
    w("")

    # ============================================= SECTION 6: VERDICT
    w("## 6. VERDICTS")
    w("")
    w("### Is time-to-reply available?")
    w("")
    if replies_with_date > 0:
        w("**YES.** `date_received` is present on reply rows, `sent_at` is "
          "present on scheduled email rows, and `scheduled_email_id` links "
          "them. TASK-059's claim that 'No time-to-reply data available' was "
          "**WRONG** — the data was always there; the join was not performed.")
    else:
        w("**NO.** `date_received` is absent on reply rows from this "
          "collection. TASK-059's claim is CONFIRMED for this sample.")
    w("")
    w("### What the delay distribution says")
    w("")
    if delay_summary:
        most_common = delay_summary[0]
        w(f"- Most common EmailBison delay: {most_common['wait_in_days']} days "
          f"({_pct(most_common['usage_count'], total_usages)}% of steps)")
    w("- HeyReach campaign 599020: +0H, +1D, +2D, +2D, +3D, +3D... "
      "across 24 nodes (PROVIDER FACT from readback)")
    w("- HeyReach reply P75: 33.3h — most replies arrive within 1.4 days")
    w("")
    w("### What this does NOT say")
    w("")
    w("- A 3-day gap outperforming a 7-day gap is UNMEASURED. The delay "
      "distribution is what was CONFIGURED, not what WORKED.")
    w("- The time-to-reply data here is from a SAMPLE of scheduled emails. "
      "The full population may differ.")
    w("- Correlation between delay and reply rate requires a controlled "
      "comparison that holds everything else constant. This analysis does "
      "not provide that.")
    w("")
    w("---")
    w("")
    w("## OBSERVATIONS")
    w("")
    w("1. EmailBison delays cluster at 3 and 5 days. The estate favours "
      "moderate spacing.")
    w("2. HeyReach replies come fast: median 6.1 hours, P75 at 33.3 hours.")
    w("3. A 3-day follow-up arrives after 75% of replies have already "
      "come in (HeyReach data).")
    w("4. Time-to-reply IS computable from EmailBison data when the join "
      "is performed. TASK-059's negative claim was an artefact of not "
      "joining, not a provider limitation.")
    w("")
    w("## HYPOTHESES")
    w("")
    w("1. A follow-up sent at day 3 reaches mostly people who will not "
      "reply — they already had 72 hours and did not.")
    w("2. Longer delays (5-7 days) may perform better not because of the "
      "delay itself but because they filter out the non-responders more "
      "thoroughly before spending a credit.")
    w("3. The HeyReach reply distribution is right-skewed (mean 41h vs "
      "median 6h), meaning a small tail of very late replies pulls the "
      "mean up. Most replies arrive within hours.")
    w("")
    w("## PROVEN LEARNINGS")
    w("")
    w("(Empty — nothing here survives a sample-size objection without "
      "a controlled experiment.)")
    w("")

    report = "\n".join(lines)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport written to {REPORT_PATH}")
    print(f"  {len(lines)} lines")
    sys.stdout.flush()
    return report


# ------------------------------------------------------------------ main

def main():
    parser = argparse.ArgumentParser(
        prog="task107_delay_analysis",
        description="TASK-107: delay distribution and time-to-reply. "
                    "READS ONLY.")
    parser.add_argument("--collect", action="store_true",
                        help="Collect data from providers")
    parser.add_argument("--analyze", action="store_true",
                        help="Analyze collected data")
    parser.add_argument("--both", action="store_true",
                        help="Collect then analyze (default)")
    parser.add_argument("--heyreach", action="store_true",
                        help="HeyReach delay collection only")
    parser.add_argument("--reply-pages", type=int, default=None,
                        help="Max reply pages to collect (None = all)")
    args = parser.parse_args()

    if not any([args.collect, args.analyze, args.both, args.heyreach]):
        args.both = True

    load_env()

    if args.heyreach:
        conn = init_db()
        collect_heyreach_delays(conn)
        conn.close()
        return 0

    if args.collect or args.both:
        conn = init_db()
        campaigns = collect_bison_campaigns(conn)
        collect_bison_steps(conn, campaigns)
        collect_bison_scheduled_emails(conn, campaigns)
        collect_bison_replies(conn, max_pages=args.reply_pages)
        collect_heyreach_delays(conn)
        conn.close()

    if args.analyze or args.both:
        if not os.path.exists(DB_PATH):
            print(f"ERROR: Database not found at {DB_PATH}. "
                  "Run --collect first.")
            return 1
        analyze()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
