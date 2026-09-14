#!/usr/bin/env python3
"""TASK-064: Render the actual LinkedIn cadence for human reading.

Reads from Claude's worktree (read-only) to access work/queue.jsonl and
work/campaigns.jsonl. Renders both branches for every contact in the
campaign, showing what a person would actually read.

ZERO provider calls. ZERO writes. Read-only everywhere.
"""
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

CLAUDE = r"C:\Users\Zvonimir\Desktop\resonate-group-automation"

def setup():
    """Point at Claude's data (read-only)."""
    for env_key, subpath in [
        ("QUEUE", os.path.join("work", "queue.jsonl")),
        ("CAMPAIGNS", os.path.join("work", "campaigns.jsonl")),
        ("CLIENTS_DIR", os.path.join("config", "clients")),
    ]:
        full = os.path.join(CLAUDE, subpath)
        if os.path.exists(full):
            os.environ[env_key] = full

def main():
    setup()
    from src import campaigns, clients, heyreachfactory, store

    campaign_id = "productive-linkedin-production-v1"
    rows = list(campaigns.load())
    campaign = campaigns.require(campaign_id, rows)
    client_name = campaign.get("client")
    config = clients.load(client_name)
    recs = list(store.load())

    fallbacks = ((config.get("linkedin_sequence") or {}).get("fallbacks") or {})

    # Run _plan to get per-contact fields
    plan = heyreachfactory._plan(campaign, recs, config)

    rec_map = {r.get("id"): r for r in recs}

    # Branch roles
    ALREADY = ("connected_1", "connected_2", "connected_3", "connected_4")
    NOT_CONNECTED = ("connection_note", "message_2", "message_3", "message_4")

    # Role -> step key mapping
    role_to_step = {}
    for sk, m in heyreachfactory.COPY_MAPPING.items():
        r = m["role"]
        if isinstance(r, str):
            r = (r,)
        for role in r:
            role_to_step[role] = sk

    print("=" * 80)
    print("  TASK-064: HUMAN READ OF THE LINKEDIN CADENCE")
    print("  Campaign:", campaign_id)
    print("  Client:", client_name)
    print("  HeyReach ID:", campaign.get("heyreach_campaign_id"))
    print("  Records:", campaign.get("record_ids") or [])
    print("  Total contacts:", len(plan.get("contacts") or []))
    print("  Pushable contacts:", len(plan.get("pushable") or []))
    print("=" * 80)

    # Print fallbacks first
    print()
    print("-" * 80)
    print("  HAND-WRITTEN OPERATOR FALLBACKS (the quality floor)")
    print("-" * 80)
    for role in heyreachfactory.REQUIRED_ROLES:
        fb = fallbacks.get(role, "(none)")
        step = role_to_step.get(role, "?")
        print(f"\n  [{role}] (from step {step}):")
        print(f"    {fb}")

    # Render each contact
    contacts = plan.get("contacts") or []
    for i, contact in enumerate(contacts):
        rec = rec_map.get(contact["record_id"])
        if not rec:
            continue
        contact_key = contact["contact_key"]
        fields = contact.get("custom_fields") or {}
        missing = contact.get("missing") or []
        unsupported = contact.get("unsupported") or []

        # Find the contact details
        contact_detail = None
        for c in (rec.get("contacts") or []):
            if c.get("key") == contact_key:
                contact_detail = c
                break
        if not contact_detail:
            continue

        print()
        print("=" * 80)
        print(f"  CONTACT {i+1}/{len(contacts)}")
        print(f"  Record: {rec.get('id')}")
        print(f"  Company: {rec.get('company')}")
        print(f"  Contact: {contact_detail.get('name', '?')}")
        print(f"  Title: {contact_detail.get('title', '?')}")
        print(f"  Persona: {contact_detail.get('persona', '?')}")
        print(f"  Angle: {contact_detail.get('angle', '?')}")
        if missing:
            print(f"  MISSING: {missing}")
        if unsupported:
            print(f"  UNSUPPORTED: {unsupported}")
        pushable = not missing and not unsupported
        print(f"  Pushable: {pushable}")
        print("=" * 80)

        # Branch 1: Already connected
        print()
        print(f"  --- BRANCH: ALREADY CONNECTED ---")
        print(f"  (connected_1 -> connected_2 -> connected_3 -> connected_4)")
        for role in ALREADY:
            text = fields.get(role, "")
            fb = fallbacks.get(role, "")
            step = role_to_step.get(role, "?")
            source = "lead" if text and str(text).strip() else "fallback"
            display = text if source == "lead" else fb
            print(f"\n  [{role}] (step {step}, source: {source}):")
            print(f"    \"{display}\"")

        # Branch 2: Not yet connected
        print()
        print(f"  --- BRANCH: NOT YET CONNECTED ---")
        print(f"  (connection_note -> message_2 -> message_3 -> message_4)")
        for role in NOT_CONNECTED:
            text = fields.get(role, "")
            fb = fallbacks.get(role, "")
            step = role_to_step.get(role, "?")
            source = "lead" if text and str(text).strip() else "fallback"
            display = text if source == "lead" else fb
            print(f"\n  [{role}] (step {step}, source: {source}):")
            print(f"    \"{display}\"")

    print()
    print("=" * 80)
    print("  END OF CADENCE RENDER")
    print("=" * 80)

if __name__ == "__main__":
    main()
