#!/usr/bin/env python3
"""TASK-105: collect replies with proper cursor pagination.

Uses the same pagination as TASK-080 (pagination_type=cursor, per_page=100).
Checks whether campaigns 262-266 appear in the reply feed at all.
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import load_env, key as get_key, request as api_request, query


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

    control_ids = {262, 263, 264, 265, 266}
    treatment_ids = {274, 327, 328, 329, 330, 331, 334, 335, 352}

    # Collect replies with proper cursor pagination
    MAX_PAGES = 200  # 200 pages * 100/page = 20,000 replies
    print(f"Collecting up to {MAX_PAGES} pages of replies "
          f"(cursor, per_page=100)...")

    all_replies = []
    cursor = None
    page = 0
    control_replies = []
    oldest_date = None
    newest_date = None

    while page < MAX_PAGES:
        params = {"pagination_type": "cursor", "per_page": 100}
        if cursor:
            params["cursor"] = cursor
        data = get("/replies", params)
        chunk = data.get("data")
        if not isinstance(chunk, list) or not chunk:
            break
        all_replies.extend(chunk)

        for r in chunk:
            cid = r.get("campaign_id")
            date = r.get("date_received", "")
            if date:
                if newest_date is None:
                    newest_date = date
                oldest_date = date  # keeps updating to the last seen

            if cid in control_ids:
                control_replies.append(r)

        page += 1
        if page % 50 == 0:
            meta = data.get("meta") or {}
            total = meta.get("total", "?")
            print(f"  page {page}: {len(all_replies)} rows "
                  f"(feed total: {total}), "
                  f"control replies so far: {len(control_replies)}")
            sys.stdout.flush()

        meta = data.get("meta") or {}
        cursor = meta.get("next_cursor")
        if not cursor:
            break
        time.sleep(0.05)

    print(f"\nTotal: {page} pages, {len(all_replies)} replies")
    print(f"Date range: {oldest_date} to {newest_date}")
    print(f"Control group replies (262-266): {len(control_replies)}")

    # Classify
    human = [r for r in all_replies
             if r.get("type") in ("Tracked Reply", "Untracked Reply")
             and not r.get("automated_reply")]
    print(f"Human replies: {len(human)}")

    human_control = [r for r in control_replies
                     if r.get("type") in ("Tracked Reply", "Untracked Reply")
                     and not r.get("automated_reply")]
    print(f"Human control replies: {len(human_control)}")

    # Distribution by campaign
    by_camp = {}
    for r in human:
        cid = r.get("campaign_id")
        by_camp.setdefault(cid, []).append(r)

    print(f"\nReply distribution by campaign (human only):")
    for cid in sorted(by_camp.keys()):
        label = "CONTROL" if cid in control_ids else \
                "TREATMENT" if cid in treatment_ids else "other"
        print(f"  Campaign {cid}: {len(by_camp[cid])} replies [{label}]")

    # Campaigns NOT in the reply feed at all
    seen_camps = set(r.get("campaign_id") for r in all_replies)
    missing_control = control_ids - seen_camps
    if missing_control:
        print(f"\nControl campaigns NOT in reply feed: {missing_control}")


if __name__ == "__main__":
    main()
