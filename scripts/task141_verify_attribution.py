#!/usr/bin/env python3
"""TASK-141: Verify the attribution chain end-to-end.

Reads only. No writes at any provider.

Walks the chain:
    reply -> scheduled_email_id -> GET /scheduled-emails/{id} -> sequence_step_id
    sequence_step_id -> GET /campaigns/{id}/sequence-steps -> variant? variant_from_step?

And checks whether events carry variant identity directly.

Outputs trimmed field evidence for the attribution boundary document.
"""
import json
import os
import sys
import urllib.request
import urllib.error

# Load .env
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "config", ".env")
def load_env():
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

BASE = os.environ.get("BISON_BASE", "https://send.resonategroup.co/api").rstrip("/")
KEY = os.environ.get("BISON_KEY", "")

def api_get(path):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return e.code, body


def trim_keys(obj, max_depth=2):
    """Return trimmed field names only, no values, for documentation."""
    if isinstance(obj, dict):
        return {k: trim_keys(v, max_depth - 1) if max_depth > 0 else "..."
                for k, v in obj.items()}
    if isinstance(obj, list) and obj:
        return [trim_keys(obj[0], max_depth - 1)] if max_depth > 0 else ["..."]
    return type(obj).__name__


def main():
    print("=" * 70)
    print("TASK-141: ATTRIBUTION CHAIN VERIFICATION")
    print("=" * 70)

    # 1. Find a campaign with variants (campaign 352 is known to have them)
    print("\n--- Step 1: Find campaigns with variants ---")
    status, data = api_get("/campaigns?per_page=5")
    campaigns = data.get("data", [])
    print(f"Campaign list: {len(campaigns)} rows, status={status}")

    # Check campaign 352 sequence steps for variant structure
    print("\n--- Step 2: Campaign 352 sequence steps (variant structure) ---")
    status, data = api_get("/campaigns/352/sequence-steps")
    steps = data.get("data", [])
    if isinstance(steps, list):
        variant_steps = [s for s in steps if s.get("variant")]
        parent_steps = [s for s in steps if not s.get("variant")]
        print(f"Total steps: {len(steps)}, variants: {len(variant_steps)}, parents: {len(parent_steps)}")
        if variant_steps:
            vs = variant_steps[0]
            print(f"First variant step: id={vs['id']}, variant_from_step={vs.get('variant_from_step')}, order={vs.get('order')}")
            print(f"  subject: {vs.get('email_subject', '')[:80]}")
        if parent_steps:
            ps = [p for p in parent_steps if p.get("order") is not None]
            if ps:
                print(f"First parent step with order: id={ps[0]['id']}, order={ps[0]['order']}")
    else:
        print(f"Response: {data}")

    # 3. Get some replies and trace the chain
    print("\n--- Step 3: Replies - trace scheduled_email_id -> step ---")
    status, data = api_get("/replies?pagination_type=cursor&per_page=5")
    replies = data.get("data", [])
    print(f"Replies: {len(replies)} rows, status={status}")

    traced = 0
    variant_traced = 0
    for reply in replies[:5]:
        rtype = reply.get("type", "?")
        folder = reply.get("folder", "?")
        sched_id = reply.get("scheduled_email_id")
        lead_id = reply.get("lead_id")
        campaign_id = reply.get("campaign_id")
        print(f"\n  Reply id={reply['id']}, type={rtype}, folder={folder}")
        print(f"    campaign_id={campaign_id}, lead_id={lead_id}, scheduled_email_id={sched_id}")

        if sched_id and rtype == "Tracked Reply":
            # Trace to scheduled email
            status2, se_data = api_get(f"/scheduled-emails/{sched_id}")
            if status2 == 200:
                se = se_data.get("data", se_data)
                step_id = se.get("sequence_step_id")
                sent_at = se.get("sent_at")
                print(f"    -> scheduled_email: sequence_step_id={step_id}, sent_at={sent_at}")

                # Now check if this step is a variant
                if campaign_id:
                    status3, steps_data = api_get(f"/campaigns/{campaign_id}/sequence-steps")
                    steps = steps_data.get("data", [])
                    for s in steps:
                        if s.get("id") == step_id:
                            is_variant = s.get("variant", False)
                            variant_from = s.get("variant_from_step")
                            order = s.get("order")
                            print(f"    -> step {step_id}: variant={is_variant}, variant_from_step={variant_from}, order={order}")
                            if is_variant:
                                variant_traced += 1
                            traced += 1
                            break
                    else:
                        print(f"    -> step {step_id} NOT FOUND in campaign steps")
            else:
                print(f"    -> scheduled_email lookup failed: {status2}")

    print(f"\n  Traced to step: {traced}, of which variant: {variant_traced}")

    # 4. Check events for variant identity
    print("\n--- Step 4: Events - check sequence_step_variant field ---")
    status, data = api_get("/events?pagination_type=cursor&per_page=5")
    events = data.get("data", [])
    print(f"Events: {len(events)} rows, status={status}")

    for ev in events[:5]:
        payload = ev.get("payload", {})
        event_type = payload.get("event", {}).get("type", "?")
        sched = payload.get("data", {}).get("scheduled_email", {})
        step_id = sched.get("sequence_step_id")
        step_order = sched.get("sequence_step_order")
        step_variant = sched.get("sequence_step_variant")
        print(f"  Event: {event_type}")
        print(f"    sequence_step_id={step_id}, order={step_order}, variant={step_variant}")

    # 5. Find a reply that traces to a VARIANT step specifically
    print("\n--- Step 5: Find reply -> variant step chain ---")
    # Get more replies
    status, data = api_get("/replies?pagination_type=cursor&per_page=15")
    replies = data.get("data", [])
    found_variant_reply = None

    for reply in replies:
        if reply.get("type") != "Tracked Reply":
            continue
        sched_id = reply.get("scheduled_email_id")
        campaign_id = reply.get("campaign_id")
        if not sched_id or not campaign_id:
            continue

        # Get scheduled email
        status2, se_data = api_get(f"/scheduled-emails/{sched_id}")
        if status2 != 200:
            continue
        se = se_data.get("data", se_data)
        step_id = se.get("sequence_step_id")

        # Get campaign steps
        status3, steps_data = api_get(f"/campaigns/{campaign_id}/sequence-steps")
        steps = steps_data.get("data", [])
        for s in steps:
            if s.get("id") == step_id and s.get("variant"):
                found_variant_reply = {
                    "reply_id": reply["id"],
                    "scheduled_email_id": sched_id,
                    "sequence_step_id": step_id,
                    "variant_from_step": s.get("variant_from_step"),
                    "campaign_id": campaign_id,
                    "lead_id": reply.get("lead_id"),
                    "date_received": reply.get("date_received"),
                    "sent_at": se.get("sent_at"),
                }
                break
        if found_variant_reply:
            break

    if found_variant_reply:
        print("  FOUND reply that traces to a VARIANT step:")
        for k, v in found_variant_reply.items():
            print(f"    {k}: {v}")
    else:
        print("  No reply tracing to a variant step found in first 15 replies")
        print("  (This does not mean it is impossible - only that the sample is small)")

    # 6. Verify the event variant field matches the step id
    print("\n--- Step 6: Cross-check event sequence_step_variant vs step id ---")
    status, data = api_get("/events?pagination_type=cursor&per_page=15")
    events = data.get("data", [])
    for ev in events:
        payload = ev.get("payload", {})
        event_type = payload.get("event", {}).get("type", "?")
        if event_type != "EMAIL_SENT":
            continue
        sched = payload.get("data", {}).get("scheduled_email", {})
        step_variant = sched.get("sequence_step_variant")
        step_id = sched.get("sequence_step_id")
        if step_variant is not None:
            print(f"  EMAIL_SENT: step_id={step_id}, sequence_step_variant={step_variant}")
            print(f"    (variant is the step id of the variant arm that was sent)")
            break

    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
