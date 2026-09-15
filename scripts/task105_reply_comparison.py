#!/usr/bin/env python3
"""TASK-105: reply comparison for the newly discovered control group.

Campaigns 262-266 have thread_reply=False at step 2 AND sends > 0.
This script fetches their reply data and step-2 sent counts to compare
against the treatment group (campaigns with thread_reply=True at step 2).

READS ONLY.
"""
import json
import os
import re
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


def strip_html(text):
    text = re.sub(r'<[^>]+>', ' ', text or '')
    return re.sub(r'\s+', ' ', text).strip()


def main():
    load_env()

    # Campaigns with thread_reply=False at step 2 AND sends > 0 (CONTROL)
    control_campaigns = [262, 263, 264, 265, 266]
    # Campaigns with thread_reply=True at step 2 AND sends > 0 (TREATMENT)
    treatment_campaigns = [274, 327, 328, 329, 330, 331, 334, 335, 352]

    print("=== Reply feed collection ===")
    print("Collecting ALL replies (cursor pagination)...")

    all_replies = []
    cursor = None
    page = 0
    while True:
        params = {"per_page": 15}
        if cursor:
            params["cursor"] = cursor
        data = get("/replies", params)
        chunk = data.get("data")
        if not isinstance(chunk, list) or not chunk:
            break
        all_replies.extend(chunk)
        page += 1
        meta = data.get("meta") or {}
        cursor = meta.get("next_cursor") or meta.get("cursor")
        if not cursor:
            break
        if page % 100 == 0:
            print(f"  {page} pages, {len(all_replies)} replies so far...")
            sys.stdout.flush()
        time.sleep(0.05)

    print(f"  Total: {page} pages, {len(all_replies)} replies collected")

    # Classify replies
    human_replies = [r for r in all_replies
                     if r.get("type") in ("Tracked Reply", "Untracked Reply")
                     and not r.get("automated_reply")]
    print(f"  Human replies: {len(human_replies)}")

    # Group by campaign
    by_campaign = {}
    for r in human_replies:
        cid = r.get("campaign_id")
        by_campaign.setdefault(cid, []).append(r)

    print(f"\n=== Step-2 reply comparison ===")
    print(f"\n--- CONTROL group (thread_reply=False at step 2) ---")

    # For each control campaign, we need:
    # 1. The step-2 step ID
    # 2. How many step-2 emails were sent
    # 3. How many step-2 emails got replies

    control_total_sends = 0
    control_total_replies = 0
    control_step2_ids = set()

    for cid in control_campaigns:
        data = get(f"/campaigns/{cid}/sequence-steps")
        steps = data.get("data", [])
        parents = [s for s in steps if not s.get("variant")]
        parents.sort(key=lambda s: s.get("order", 0))

        step2 = None
        for s in parents:
            if s.get("order") == 2:
                step2 = s
                break

        if not step2:
            print(f"  Campaign {cid}: no step 2 found")
            continue

        step2_id = step2["id"]
        control_step2_ids.add(step2_id)
        tr = "TRUE" if step2.get("thread_reply") else "False"
        print(f"  Campaign {cid}: step2_id={step2_id}, "
              f"thread_reply={tr}")

        # Count replies for this campaign
        camp_replies = by_campaign.get(cid, [])
        print(f"    Total human replies: {len(camp_replies)}")

        # We need to check which replies reference step-2 emails
        # For that, we need the scheduled_email_id -> step mapping
        # Fetch replies' scheduled_email_ids
        step2_reply_count = 0
        for r in camp_replies:
            se_id = r.get("scheduled_email_id")
            if se_id:
                try:
                    se_data = get(f"/scheduled-emails/{se_id}")
                    se = se_data.get("data", se_data)
                    if isinstance(se, dict):
                        if se.get("sequence_step_id") == step2_id:
                            step2_reply_count += 1
                except RuntimeError:
                    pass
                time.sleep(0.05)

        print(f"    Step-2 replies: {step2_reply_count}")
        control_total_replies += step2_reply_count

    # Get sent counts for control campaigns
    print(f"\n--- CONTROL sent counts ---")
    for cid in control_campaigns:
        data = get(f"/campaigns/{cid}")
        camp = data.get("data", data)
        if isinstance(camp, dict):
            sent = camp.get("emails_sent", 0)
            print(f"  Campaign {cid}: emails_sent={sent}")
            control_total_sends += int(sent or 0)
        time.sleep(0.1)

    print(f"\n  CONTROL total emails_sent: {control_total_sends}")
    print(f"  CONTROL total step-2 replies: {control_total_replies}")

    # Treatment group
    print(f"\n--- TREATMENT group (thread_reply=True at step 2) ---")
    treatment_total_replies = 0
    treatment_step2_ids = set()

    for cid in treatment_campaigns:
        data = get(f"/campaigns/{cid}/sequence-steps")
        steps = data.get("data", [])
        parents = [s for s in steps if not s.get("variant")]
        parents.sort(key=lambda s: s.get("order", 0))

        step2 = None
        for s in parents:
            if s.get("order") == 2:
                step2 = s
                break

        if not step2:
            print(f"  Campaign {cid}: no step 2 found")
            continue

        step2_id = step2["id"]
        treatment_step2_ids.add(step2_id)
        tr = "TRUE" if step2.get("thread_reply") else "False"

        camp_replies = by_campaign.get(cid, [])

        # Count step-2 replies
        step2_reply_count = 0
        for r in camp_replies:
            se_id = r.get("scheduled_email_id")
            if se_id:
                try:
                    se_data = get(f"/scheduled-emails/{se_id}")
                    se = se_data.get("data", se_data)
                    if isinstance(se, dict):
                        if se.get("sequence_step_id") == step2_id:
                            step2_reply_count += 1
                except RuntimeError:
                    pass
                time.sleep(0.05)

        print(f"  Campaign {cid}: thread_reply={tr}, "
              f"replies_total={len(camp_replies)}, "
              f"step2_replies={step2_reply_count}")
        treatment_total_replies += step2_reply_count

    treatment_total_sends = 0
    for cid in treatment_campaigns:
        data = get(f"/campaigns/{cid}")
        camp = data.get("data", data)
        if isinstance(camp, dict):
            sent = camp.get("emails_sent", 0)
            treatment_total_sends += int(sent or 0)
        time.sleep(0.1)

    print(f"\n  TREATMENT total emails_sent: {treatment_total_sends}")
    print(f"  TREATMENT total step-2 replies: {treatment_total_replies}")

    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"  CONTROL (thread_reply=False at step 2):")
    print(f"    Campaigns: {control_campaigns}")
    print(f"    Total sends: {control_total_sends}")
    print(f"    Step-2 replies: {control_total_replies}")
    if control_total_sends > 0:
        print(f"    Overall reply rate: "
              f"{control_total_replies/control_total_sends*100:.2f}%")

    print(f"  TREATMENT (thread_reply=True at step 2):")
    print(f"    Campaigns: {treatment_campaigns}")
    print(f"    Total sends: {treatment_total_sends}")
    print(f"    Step-2 replies: {treatment_total_replies}")
    if treatment_total_sends > 0:
        print(f"    Overall reply rate: "
              f"{treatment_total_replies/treatment_total_sends*100:.2f}%")

    print(f"\n  CAVEAT: These are OVERALL campaign reply rates, not")
    print(f"  step-2-specific rates. The denominator is total campaign")
    print(f"  sends, not step-2 sends. Step-2-specific denominators")
    print(f"  require systematic sampling of scheduled emails.")


if __name__ == "__main__":
    main()
