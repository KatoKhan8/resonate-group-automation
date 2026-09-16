#!/usr/bin/env python3
"""TASK-197: Identify the 15 verified records with no cadence.

Reads the snapshot (work/queue.snapshot.jsonl), finds records that are
verified with confirmed addresses but have no cadence at all, and
distinguishes 'never ran' from 'ran and produced nothing'.
"""
import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import lint, verification

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "work", "queue.snapshot.jsonl")


def load_snapshot():
    recs = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def hash_id(rec_id):
    return hashlib.sha256(rec_id.encode("utf-8")).hexdigest()[:12]


def has_verified_contact(rec):
    """Does this record have at least one contact with verification.state == verified?"""
    for c in rec.get("contacts") or []:
        v = c.get("verification") or {}
        if v.get("state") == "verified":
            return True
        # Also check via the sendable path
        if lint.sendable(c):
            return True
    return False


def has_sendable_contact(rec):
    """Does this record have at least one sendable contact?"""
    for c in rec.get("contacts") or []:
        if lint.sendable(c):
            return True
    return False


def has_linkedin_contact(rec):
    """Does this record have at least one contact with a LinkedIn profile?"""
    from src import channels
    for c in rec.get("contacts") or []:
        ok, _ = channels.linkedin_verdict(rec, c)
        if ok:
            return True
    return False


def has_any_cadence(rec):
    """Does this record have any cadence entries at all?"""
    cadence = rec.get("cadence") or {}
    if not cadence:
        return False
    for contact_key, steps in cadence.items():
        if steps:
            return True
    return False


def has_generation_log(rec):
    """Did generation ever run on this record? Check the log for draft/linkedin_note steps."""
    for entry in rec.get("log") or []:
        step = entry.get("step", "")
        if step in ("draft", "linkedin_note", "linkedin_set"):
            return True
    return False


def has_workable_contact(rec):
    """Does the record have any contact that is sendable OR has LinkedIn?"""
    sendable = [c for c in rec.get("contacts") or [] if lint.sendable(c)]
    if sendable:
        return True
    from src import channels
    for c in rec.get("contacts") or []:
        ok, _ = channels.linkedin_verdict(rec, c)
        if ok:
            return True
    return False


def main():
    recs = load_snapshot()
    print(f"Snapshot: {len(recs)} records")

    # Find verified records
    verified = [r for r in recs if has_verified_contact(r)]
    print(f"Verified records (at least one verified contact): {len(verified)}")

    # Filter to those with no cadence at all
    no_cadence = [r for r in verified if not has_any_cadence(r)]
    print(f"Verified records with NO cadence at all: {len(no_cadence)}")

    # Now distinguish: did generation ever run?
    never_ran = []
    ran_empty = []
    for r in no_cadence:
        if has_generation_log(r):
            ran_empty.append(r)
        else:
            never_ran.append(r)

    print(f"\n  Never ran (no draft/linkedin_note in log): {len(never_ran)}")
    print(f"  Ran but produced nothing: {len(ran_empty)}")

    # Also check: are there records with no workable contacts?
    no_workable = [r for r in no_cadence if not has_workable_contact(r)]
    print(f"  No workable contacts (not sendable, no LinkedIn): {len(no_workable)}")

    print("\n" + "=" * 80)
    print("THE 15 (or however many) - VERIFIED, NO CADENCE, NEVER RAN:")
    print("=" * 80)

    all_no_cadence = never_ran + ran_empty
    for i, r in enumerate(all_no_cadence, 1):
        hid = hash_id(r["id"])
        company = r.get("company", "?")
        domain = r.get("domain", "?")
        lane = r.get("lane", "?")
        state = r.get("state", "?")
        contacts = r.get("contacts") or []
        sendable_count = sum(1 for c in contacts if lint.sendable(c))

        # Check LinkedIn
        from src import channels
        li_count = 0
        for c in contacts:
            ok, _ = channels.linkedin_verdict(r, c)
            if ok:
                li_count += 1

        has_gen = has_generation_log(r)
        gen_label = "NEVER RAN" if not has_gen else "RAN BUT EMPTY"

        # Check what log entries exist
        log_steps = [e.get("step") for e in (r.get("log") or [])]
        step_counts = {}
        for s in log_steps:
            step_counts[s] = step_counts.get(s, 0) + 1

        print(f"\n  {i}. [{hid}] {company} ({domain})")
        print(f"     lane={lane} state={state} gen={gen_label}")
        print(f"     contacts: {len(contacts)} total, {sendable_count} sendable, {li_count} LinkedIn-ok")
        print(f"     log steps: {dict(step_counts)}")

        # List contacts (hashed)
        for c in contacts:
            ckey = c.get("key", "?")
            hck = hashlib.sha256(ckey.encode("utf-8")).hexdigest()[:10]
            name = c.get("name", "?")
            title = c.get("title", "?")
            v = c.get("verification") or {}
            vstate = v.get("state", "?")
            email = c.get("email")
            has_email = bool(email)
            send = lint.sendable(c)
            li_ok, li_reason = channels.linkedin_verdict(r, c)
            print(f"       contact [{hck}] {name} / {title}")
            print(f"         verification={vstate} email={has_email} sendable={send} "
                  f"linkedin={li_ok} ({li_reason})")

    print("\n" + "=" * 80)
    print("RECORDS WITH NO WORKABLE CONTACTS (cannot generate for):")
    print("=" * 80)
    for r in no_workable:
        hid = hash_id(r["id"])
        print(f"  [{hid}] {r.get('company')} ({r.get('domain')})")

    # IDs for generation
    print("\n" + "=" * 80)
    print("RECORD IDS FOR GENERATION (never-ran only):")
    print("=" * 80)
    for r in never_ran:
        if has_workable_contact(r):
            print(f"  --id {r['id']}")


if __name__ == "__main__":
    main()
