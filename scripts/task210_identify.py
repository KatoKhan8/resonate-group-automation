"""TASK-210: Identify the 11 records and match them to live queue state.

The cohort is 17 from task177_results.json. 6 have persona=None.
16 survive the collision check. One of the 6 persona=None contacts
was also the one the collision check excluded, so 16 - 5 = 11.

Matching: sha256(rec_id)[:12] and sha256(contact["name"])[:12].
"""

import hashlib
import json
import sys


def h(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def main():
    # Load task177 results
    with open("scripts/task177_results.json", encoding="utf-8") as f:
        t177 = json.load(f)

    # The persona_none_contacts list
    persona_none = set()
    for entry in t177["persona_none_contacts"]:
        persona_none.add(entry["rec_id_hash"])

    # The survivors list - those with persona != null
    survivors_11 = []
    for s in t177["survivors"]:
        if s["persona"] is not None:
            survivors_11.append(s)

    print(f"Survivors with persona: {len(survivors_11)}")
    print(f"Persona=None contacts: {len(persona_none)}")
    print()

    # Load live queue
    recs = []
    with open("work/queue.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))

    print(f"Live queue records: {len(recs)}")
    print()

    # Build index: rec_id_hash -> record
    rec_by_id_hash = {}
    for rec in recs:
        rid = rec.get("id", "")
        rec_by_id_hash[h(rid)] = rec

    # Match each of the 11
    matched = []
    unmatched = []
    for s in survivors_11:
        rec_id_hash = s["rec_id_hash"]
        contact_hash = s["contact_hash"]
        rec = rec_by_id_hash.get(rec_id_hash)
        if rec is None:
            unmatched.append(s)
            continue

        # Now find the contact whose name hashes to contact_hash
        found_contact = None
        for c in rec.get("contacts", []):
            name = c.get("name", "")
            if h(name) == contact_hash:
                found_contact = c
                break

        if found_contact is None:
            unmatched.append(s)
            continue

        matched.append({
            "task177_idx": s["idx"],
            "rec_id_hash": rec_id_hash,
            "contact_hash": contact_hash,
            "domain_hash": s["domain_hash"],
            "persona": s["persona"],
            "angle": s["angle"],
            "record_id": rec.get("id"),
            "record_state": rec.get("state"),
            "contact_key": found_contact.get("key"),
            "contact_name_hash": h(found_contact.get("name", "")),
            "contact_email_hash": h(found_contact.get("email", "")),
            "sendable": found_contact.get("sendable"),
            "email_verified": found_contact.get("email_verified"),
            "verification_state": (found_contact.get("verification") or {}).get("state"),
        })

    print(f"Matched: {len(matched)}")
    print(f"Unmatched: {len(unmatched)}")
    print()

    for m in matched:
        print(f"  TASK-177 #{m['task177_idx']:2d} | "
              f"rec={m['rec_id_hash']} contact={m['contact_hash']} | "
              f"state={m['record_state']:10s} sendable={m['sendable']} "
              f"persona={m['persona']} angle={m['angle']}")

    if unmatched:
        print()
        print("UNMATCHED:")
        for u in unmatched:
            print(f"  TASK-177 #{u['idx']} rec={u['rec_id_hash']} "
                  f"contact={u['contact_hash']}")

    # Write matched data for use by the main script
    with open("scripts/task210_matched.json", "w", encoding="utf-8") as f:
        json.dump(matched, f, indent=2, ensure_ascii=False)
    print(f"\nWrote scripts/task210_matched.json")


if __name__ == "__main__":
    main()
