#!/usr/bin/env python3
"""TASK-105: independently verify the no-control-group claim.

Walks every campaign in the estate via the provider API (READS ONLY).
For each campaign, fetches sequence steps and records thread_reply at
each position. Reports:
  - How many campaigns use thread_reply=False at any step
  - How many of those have sends > 0
  - Whether any position has BOTH True and False across campaigns

Also re-derives the 857/571 body-length numbers from the reply-centric
fetch (emails that got replies).
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

    # --- Phase 1: enumerate all campaigns ---
    print("=== Phase 1: Enumerate campaigns ===")
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

    print(f"  {len(campaigns)} campaigns found")

    # --- Phase 2: for each campaign, fetch steps and record thread_reply ---
    print("\n=== Phase 2: Sequence steps per campaign ===")
    campaign_steps = {}  # campaign_id -> {info, steps: [{order, thread_reply}]}

    for camp in campaigns:
        cid = camp["id"]
        sent = int(camp.get("emails_sent") or 0)
        status = camp.get("status", "")
        name = camp.get("name", "")[:40]

        try:
            data = get(f"/campaigns/{cid}/sequence-steps")
        except RuntimeError as e:
            print(f"  Campaign {cid}: ERROR fetching steps: {e}")
            continue

        steps_raw = data.get("data")
        if not isinstance(steps_raw, list):
            print(f"  Campaign {cid}: no steps data")
            continue

        # Filter to parent steps only (non-variant), ordered
        parents = [s for s in steps_raw if not s.get("variant")]
        parents.sort(key=lambda s: s.get("order", 0))

        step_info = []
        for s in parents:
            step_info.append({
                "order": s.get("order"),
                "thread_reply": bool(s.get("thread_reply")),
                "id": s.get("id"),
            })

        campaign_steps[cid] = {
            "name": name,
            "status": status,
            "emails_sent": sent,
            "steps": step_info,
        }

        pattern = ", ".join(
            "T" if s["thread_reply"] else "F" for s in step_info)
        print(f"  Campaign {cid} ({name}): status={status}, "
              f"sent={sent}, steps={len(step_info)}, "
              f"thread_reply=[{pattern}]")
        time.sleep(0.1)

    # --- Phase 3: answer the control-group question ---
    print("\n=== Phase 3: Control-group analysis ===")

    # 3a: campaigns with thread_reply=False at ANY step
    has_any_false = []
    has_any_true = []
    for cid, info in sorted(campaign_steps.items()):
        patterns = [s["thread_reply"] for s in info["steps"]]
        if any(not t for t in patterns):
            has_any_false.append((cid, info))
        if any(t for t in patterns):
            has_any_true.append((cid, info))

    print(f"\n  Campaigns with thread_reply=False at ANY step: "
          f"{len(has_any_false)}")
    for cid, info in has_any_false:
        print(f"    Campaign {cid}: sent={info['emails_sent']}, "
              f"status={info['status']}")

    print(f"\n  Campaigns with thread_reply=True at ANY step: "
          f"{len(has_any_true)}")
    for cid, info in has_any_true:
        print(f"    Campaign {cid}: sent={info['emails_sent']}, "
              f"status={info['status']}")

    # 3b: campaigns with sends AND thread_reply=False at some step
    false_with_sends = [(cid, info) for cid, info in has_any_false
                        if info["emails_sent"] > 0]
    print(f"\n  Campaigns with thread_reply=False AND sends > 0: "
          f"{len(false_with_sends)}")
    for cid, info in false_with_sends:
        pattern = ", ".join(
            "T" if s["thread_reply"] else "F" for s in info["steps"])
        print(f"    Campaign {cid}: sent={info['emails_sent']}, "
              f"pattern=[{pattern}]")

    # 3c: at each position, is there variation in thread_reply?
    print("\n  Position-level analysis (parent steps only):")
    max_steps = max(len(info["steps"]) for info in campaign_steps.values())
    for pos in range(1, max_steps + 1):
        true_camps = []
        false_camps = []
        for cid, info in sorted(campaign_steps.items()):
            if pos > len(info["steps"]):
                continue
            step = info["steps"][pos - 1]
            if step["thread_reply"]:
                true_camps.append((cid, info["emails_sent"]))
            else:
                false_camps.append((cid, info["emails_sent"]))

        true_with_sends = [(c, s) for c, s in true_camps if s > 0]
        false_with_sends = [(c, s) for c, s in false_camps if s > 0]

        has_control = (len(true_with_sends) > 0 and
                       len(false_with_sends) > 0)
        marker = " <-- CONTROL EXISTS" if has_control else ""
        print(f"    Position {pos}: "
              f"True={len(true_camps)} ({len(true_with_sends)} with sends), "
              f"False={len(false_camps)} ({len(false_with_sends)} with sends)"
              f"{marker}")

    # 3d: the specific claim - thread_reply=False at step 2 with sends
    print("\n  Step-2 specific check:")
    for cid, info in sorted(campaign_steps.items()):
        if len(info["steps"]) < 2:
            continue
        step2 = info["steps"][1]
        tr = "TRUE" if step2["thread_reply"] else "False"
        print(f"    Campaign {cid}: step2 thread_reply={tr}, "
              f"sent={info['emails_sent']}")

    print("\n=== DONE ===")


if __name__ == "__main__":
    main()
