#!/usr/bin/env python3
"""TASK-141: Trace the attribution chain from reply to variant.

READS ONLY. No write route is called. Proves what EmailBison can and cannot
join by provider data alone, versus what requires reconstruction or is
pure hypothesis.

The chain under test:
    campaign -> sequence -> step -> lead -> variant -> send -> reply -> outcome

For each reply we answer:
  1. Can it be joined to a SPECIFIC STEP by provider data alone?
  2. Can it be joined to a SPECIFIC VARIANT?
  3. What fields decide each answer?
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers import load_env
load_env()

import urllib.request
import urllib.parse

BASE = os.environ.get("BISON_BASE", "https://send.resonategroup.co/api").rstrip("/")
KEY = os.environ["BISON_KEY"]


def _get(path, params=None):
    """One GET. Returns parsed JSON."""
    url = f"{BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def get_replies(n=5):
    """Fetch n tracked replies."""
    data = _get("/replies", {"per_page": 15, "pagination_type": "cursor"})
    rows = data.get("data", [])
    tracked = [r for r in rows if r.get("type") == "Tracked Reply"]
    return tracked[:n]


def get_scheduled_email(se_id):
    """GET /scheduled-emails/{id} — the second hop."""
    return _get(f"/scheduled-emails/{se_id}")


def get_sequence_steps(campaign_id):
    """GET /campaigns/{id}/sequence-steps."""
    return _get(f"/campaigns/{campaign_id}/sequence-steps")


def get_events(n=5):
    """GET /events — 10-day window."""
    data = _get("/events", {"per_page": 15, "pagination_type": "cursor"})
    return data.get("data", [])[:n]


def get_campaign(campaign_id):
    """GET /campaigns/{id}."""
    return _get(f"/campaigns/{campaign_id}")


def trim(d, keys):
    """Return only the named keys from a dict."""
    return {k: d.get(k) for k in keys if k in d}


def main():
    print("=" * 78)
    print("TASK-141 ATTRIBUTION CHAIN PROBE")
    print("=" * 78)

    # --- 1. CAMPAIGN LEVEL ---
    print("\n## 1. CAMPAIGN LEVEL")
    campaigns_data = _get("/campaigns", {"per_page": 15})
    campaigns = campaigns_data.get("data", [])
    active = [c for c in campaigns if c.get("status") in ("active", "completed")]
    print(f"  Total campaigns: {len(campaigns)}")
    print(f"  Active/completed: {len(active)}")
    if active:
        c = active[0]
        print(f"  Sample campaign fields: {sorted(c.keys())}")
        print(f"  Campaign {c['id']}: status={c['status']}, "
              f"emails_sent={c.get('emails_sent')}, replied={c.get('replied')}, "
              f"open_tracking={c.get('open_tracking')}")

    # --- 2. SEQUENCE STEPS ---
    print("\n## 2. SEQUENCE STEPS (variant structure)")
    # Find a campaign with variants
    variant_campaigns = []
    for c in active[:10]:
        try:
            steps_data = get_sequence_steps(c["id"])
            steps = steps_data.get("data", [])
            if not steps and isinstance(steps_data.get("success"), bool):
                continue
            variants = [s for s in steps if s.get("variant")]
            if variants:
                variant_campaigns.append((c["id"], c["name"], steps, variants))
                print(f"  Campaign {c['id']} ({c['name']}): "
                      f"{len(steps)} steps, {len(variants)} variants")
        except Exception as e:
            print(f"  Campaign {c['id']}: error - {e}")

    if variant_campaigns:
        cid, cname, steps, variants = variant_campaigns[0]
        print(f"\n  Detailed variant structure for campaign {cid}:")
        for s in steps[:15]:
            vflag = "VARIANT" if s.get("variant") else "parent"
            vfrom = s.get("variant_from_step")
            print(f"    step {s['id']}: order={s.get('order')}, "
                  f"{vflag}, variant_from_step={vfrom}, "
                  f"subject={s.get('email_subject', '')[:50]}")

    # --- 3. REPLIES ---
    print("\n## 3. REPLIES (the inbox feed)")
    replies = get_replies(5)
    print(f"  Fetched {len(replies)} tracked replies")

    for r in replies:
        print(f"\n  Reply {r['id']}:")
        print(f"    type={r.get('type')}, folder={r.get('folder')}")
        print(f"    campaign_id={r.get('campaign_id')}")
        print(f"    lead_id={r.get('lead_id')}")
        print(f"    scheduled_email_id={r.get('scheduled_email_id')}")
        print(f"    date_received={r.get('date_received')}")
        print(f"    interested={r.get('interested')}")
        print(f"    tracked_reply={r.get('tracked_reply')}")
        print(f"    automated_reply={r.get('automated_reply')}")
        print(f"    Keys NOT present: sequence_step_id, step_id, variant_id")
        se_id = r.get("scheduled_email_id")

        if se_id:
            # --- 4. THE SECOND HOP ---
            print(f"\n    ## 4. SECOND HOP: scheduled_email {se_id}")
            try:
                se = get_scheduled_email(se_id)
                # The response may be wrapped in 'data'
                if isinstance(se.get("data"), dict):
                    se = se["data"]
                print(f"      sequence_step_id={se.get('sequence_step_id')}")
                print(f"      status={se.get('status')}")
                print(f"      sent_at={se.get('sent_at')}")
                print(f"      email_subject={str(se.get('email_subject', ''))[:60]}")
                print(f"      replies={se.get('replies')}")
                print(f"      Keys: {sorted(se.keys())}")

                step_id = se.get("sequence_step_id")
                if step_id and variant_campaigns:
                    # Check if this step IS a variant or a parent
                    for vc, vn, vsteps, vvs in variant_campaigns:
                        if vc == r.get("campaign_id"):
                            for s in vsteps:
                                if s["id"] == step_id:
                                    is_variant = s.get("variant", False)
                                    vfrom = s.get("variant_from_step")
                                    print(f"\n      ## 5. VARIANT RESOLUTION")
                                    print(f"        Step {step_id} is_variant={is_variant}")
                                    if is_variant:
                                        print(f"        This IS a variant step. "
                                              f"Step id={step_id} is the variant id.")
                                    else:
                                        print(f"        This is a PARENT step. "
                                              f"Variant children: "
                                              f"{[v['id'] for v in vvs if v.get('variant_from_step') == step_id]}")
                                    break
                            break
            except Exception as e:
                print(f"      Error fetching scheduled email: {e}")

    # --- 5. EVENTS (the variant-rich endpoint) ---
    print("\n## 5. EVENTS (10-day window)")
    events = get_events(10)
    print(f"  Fetched {len(events)} events")
    for ev in events:
        etype = ev.get("payload", {}).get("event", {}).get("type", "?")
        se = ev.get("payload", {}).get("data", {}).get("scheduled_email", {})
        if se:
            print(f"  Event {ev['id']}: {etype}")
            print(f"    sequence_step_id={se.get('sequence_step_id')}")
            print(f"    sequence_step_order={se.get('sequence_step_order')}")
            print(f"    sequence_step_variant={se.get('sequence_step_variant')}")
            print(f"    lead_id={se.get('lead_id')}")
            print(f"    sent_at={se.get('sent_at')}")
        else:
            print(f"  Event {ev['id']}: {etype} (no scheduled_email)")

    # --- 6. THE ATTRIBUTION BOUNDARY SUMMARY ---
    print("\n" + "=" * 78)
    print("ATTRIBUTION BOUNDARY SUMMARY")
    print("=" * 78)
    print("""
LEVEL              | PROVIDER FACT              | RECONSTRUCTION           | HYPOTHESIS
-------------------|----------------------------|--------------------------|------------
campaign           | campaign_id on reply       | -                        | -
sequence           | via campaign.sequence_id   | -                        | -
step               | via scheduled_email join   | step order from events   | -
variant (events)   | sequence_step_variant      | -                        | -
                   | on EMAIL_SENT event        |                          |
variant (reply)    | step is_variant=True means | if step is parent,       | which
                   | step_id = variant_id       | which child was sent?    | variant of
                   |                            | only events carry this   | a parent step
                   |                            | (10-day window)          | was sent
lead               | lead_id on reply           | -                        | -
send               | scheduled_email_id         | sent_at from sched email | -
reply              | reply row directly         | -                        | -
outcome            | interested, type, folder   | positive vs negative     | unknown reply
                   |                            | requires human read      | = negative
""")

    print("\nDone. READS ONLY — no write route was called.")


if __name__ == "__main__":
    main()
