#!/usr/bin/env python3
"""TASK-080 supplement: reply-centric scheduled email fetch.

For each human reply in the database, fetch the scheduled email it
references via GET /scheduled-emails/{id}. This gives us thread_reply,
sequence_step_id, and rendered copy for exactly the emails that got replies.

460 API calls, ~2-3 minutes. READS ONLY.
"""
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import load_env, key as get_key, request as api_request, query

DB_PATH = os.path.join(ROOT, ".qwen", "tmp", "task080", "thread.db")


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


def main():
    load_env()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Create the reply-centric table
    conn.execute("DROP TABLE IF EXISTS reply_se")
    conn.execute("""CREATE TABLE reply_se (
        scheduled_email_id INTEGER PRIMARY KEY,
        campaign_id INTEGER,
        sequence_step_id INTEGER,
        step_order INTEGER,
        thread_reply INTEGER,
        sent_at TEXT,
        email_subject TEXT,
        email_body TEXT,
        lead_id INTEGER,
        status TEXT
    )""")
    conn.commit()

    # Get all unique scheduled_email_ids from human replies
    se_ids = conn.execute("""
        SELECT DISTINCT r.scheduled_email_id, r.campaign_id, r.lead_id
        FROM replies r
        WHERE r.type IN ('Tracked Reply','Untracked Reply')
        AND r.automated_reply = 0
        AND r.scheduled_email_id IS NOT NULL
    """).fetchall()

    print(f"Fetching {len(se_ids)} scheduled emails referenced by replies...")
    sys.stdout.flush()

    # Build step_id -> (step_order, thread_reply_from_step) map
    step_map = {}
    for r in conn.execute(
        "SELECT id, step_order, thread_reply, is_variant, variant_from_step "
        "FROM sequence_steps"
    ).fetchall():
        step_map[r["id"]] = r

    # Resolve variant -> parent order
    def resolve_order(step_id):
        s = step_map.get(step_id)
        if not s:
            return None
        if s["is_variant"]:
            parent = step_map.get(s["variant_from_step"])
            return parent["step_order"] if parent else None
        return s["step_order"]

    fetched = 0
    errors = 0
    for row in se_ids:
        se_id = row["scheduled_email_id"]
        try:
            data = get(f"/scheduled-emails/{se_id}")
            d = data.get("data", data)
            if not isinstance(d, dict):
                errors += 1
                continue

            step_id = d.get("sequence_step_id")
            order = resolve_order(step_id)

            import re
            body = str(d.get("email_body", ""))
            body_text = re.sub(r'<[^>]+>', ' ', body)
            body_text = re.sub(r'\s+', ' ', body_text).strip()

            conn.execute(
                "INSERT INTO reply_se VALUES (?,?,?,?,?,?,?,?,?,?)",
                (se_id,
                 d.get("campaign_id"),
                 step_id,
                 order,
                 1 if d.get("thread_reply") else 0,
                 str(d.get("sent_at", "")),
                 str(d.get("email_subject", ""))[:500],
                 body_text[:1000],
                 row["lead_id"],
                 str(d.get("status", ""))))
            fetched += 1
        except RuntimeError as e:
            errors += 1
            if errors <= 5:
                print(f"  Error fetching {se_id}: {e}")

        if fetched % 50 == 0 and fetched > 0:
            print(f"  {fetched} fetched, {errors} errors")
            sys.stdout.flush()
        time.sleep(0.1)

    conn.commit()
    print(f"\nDone: {fetched} fetched, {errors} errors")

    # Summary
    print("\n=== reply_se summary ===")
    for r in conn.execute("""
        SELECT campaign_id, step_order, thread_reply, COUNT(*) as cnt
        FROM reply_se
        WHERE step_order IS NOT NULL
        GROUP BY campaign_id, step_order, thread_reply
        ORDER BY campaign_id, step_order
    """).fetchall():
        tr = "TRUE" if r["thread_reply"] else "False"
        print(f"  Campaign {r['campaign_id']}, step {r['step_order']}: "
              f"thread_reply={tr}, n={r['cnt']}")

    conn.close()


if __name__ == "__main__":
    main()
