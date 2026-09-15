#!/usr/bin/env python3
"""TASK-105: sample scheduled emails for campaigns 262-266.

Get step-2 sent counts and check for reply data on those emails.
Also sample a few treatment campaign step-2 emails for body length
comparison (re-deriving the 857/571 numbers).

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

    # Step 2 IDs for control campaigns (from previous script)
    control_step2 = {
        262: 2919, 263: 2927, 264: 2933,
        265: 2939, 266: 2945,
    }

    # Step 2 IDs for treatment campaigns
    treatment_step2 = {}
    for cid in [274, 327, 328, 329, 330, 331, 334, 335, 352]:
        data = get(f"/campaigns/{cid}/sequence-steps")
        steps = data.get("data", [])
        parents = [s for s in steps if not s.get("variant")]
        for s in parents:
            if s.get("order") == 2:
                treatment_step2[cid] = s["id"]
                break
        time.sleep(0.1)

    print("=== Step-2 scheduled email sampling ===")
    print("(per_page is IGNORED by API - always 15 rows per page)")
    print()

    # For each campaign, sample the first N pages of scheduled emails
    # and count step-2 sends
    SAMPLE_PAGES = 20  # 20 pages * 15 = up to 300 rows per campaign

    all_step2_emails = {}  # campaign_id -> list of (se_id, thread_reply, sent_at, body_len)

    for label, camps, step2_map in [
        ("CONTROL", [262, 263, 264, 265, 266], control_step2),
        ("TREATMENT", [352, 327, 328], treatment_step2),
    ]:
        print(f"--- {label} group ---")
        for cid in camps:
            step2_id = step2_map.get(cid)
            if not step2_id:
                print(f"  Campaign {cid}: no step-2 ID")
                continue

            step2_count = 0
            total_sampled = 0
            step2_emails = []

            for page in range(1, SAMPLE_PAGES + 1):
                try:
                    data = get(f"/campaigns/{cid}/scheduled-emails",
                               {"page": page})
                except RuntimeError:
                    break
                chunk = data.get("data")
                if not isinstance(chunk, list) or not chunk:
                    break
                total_sampled += len(chunk)

                for se in chunk:
                    if se.get("sequence_step_id") == step2_id:
                        sent_at = se.get("sent_at")
                        if sent_at:  # only count sent emails
                            step2_count += 1
                            body = strip_html(se.get("email_body", ""))
                            step2_emails.append({
                                "id": se.get("id"),
                                "thread_reply": bool(se.get("thread_reply")),
                                "sent_at": str(sent_at),
                                "body_len": len(body),
                                "subject": str(se.get("email_subject", ""))[:60],
                            })

                time.sleep(0.1)

            all_step2_emails[cid] = step2_emails
            tr_val = step2_emails[0]["thread_reply"] if step2_emails else "?"
            print(f"  Campaign {cid}: sampled {total_sampled} rows, "
                  f"step-2 sent={step2_count}, "
                  f"thread_reply={tr_val}")

    # Body length analysis for step-2 emails
    print(f"\n=== Body length at step 2 ===")
    print(f"(only emails that have body data available in sample)")

    for label, camps in [
        ("CONTROL (thread_reply=False)", [262, 263, 264, 265, 266]),
        ("TREATMENT (thread_reply=True)", [352, 327, 328]),
    ]:
        bodies = []
        for cid in camps:
            for em in all_step2_emails.get(cid, []):
                bodies.append(em["body_len"])
        if bodies:
            avg = sum(bodies) / len(bodies)
            print(f"  {label}:")
            print(f"    n={len(bodies)}, avg body length={avg:.0f} chars")
            print(f"    min={min(bodies)}, max={max(bodies)}")
        else:
            print(f"  {label}: no step-2 emails in sample")

    # Check if any step-2 emails in the control group have replies
    # by looking at the scheduled email status
    print(f"\n=== Reply status of step-2 emails ===")
    for cid in [262, 263, 264, 265, 266]:
        emails = all_step2_emails.get(cid, [])
        replied = [e for e in emails if "reply" in e.get("subject", "").lower()
                   or e.get("thread_reply")]
        print(f"  Campaign {cid}: {len(emails)} step-2 emails sampled, "
              f"{len(replied)} with reply indicators")

    # Total step-2 estimated sends (extrapolated from sample)
    print(f"\n=== Estimated step-2 sends (extrapolated) ===")
    for cid in [262, 263, 264, 265, 266, 352, 327, 328]:
        emails = all_step2_emails.get(cid, [])
        data = get(f"/campaigns/{cid}")
        camp = data.get("data", data)
        total_sent = int(camp.get("emails_sent", 0)) if isinstance(camp, dict) else 0
        n_steps = len(campaign_steps_cache.get(cid, []))
        if n_steps > 0:
            estimated_per_step = total_sent / n_steps
        else:
            estimated_per_step = 0
        print(f"  Campaign {cid}: total_sent={total_sent}, "
              f"est. per step={estimated_per_step:.0f}, "
              f"step-2 in sample={len(emails)}")
        time.sleep(0.1)


# Cache for campaign step counts
campaign_steps_cache = {}


def cache_steps():
    global campaign_steps_cache
    for cid in [262, 263, 264, 265, 266, 352, 327, 328]:
        data = get(f"/campaigns/{cid}/sequence-steps")
        steps = data.get("data", [])
        parents = [s for s in steps if not s.get("variant")]
        campaign_steps_cache[cid] = parents
        time.sleep(0.1)


if __name__ == "__main__":
    load_env()
    cache_steps()
    main()
