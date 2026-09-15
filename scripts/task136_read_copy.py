#!/usr/bin/env python3
"""TASK-136: generate a sample of full sequences against the corrected brief
so they can be read as a human. Does NOT write to the queue.

Picks up to 12 records with economic_buyer contacts from the snapshot,
generates all 6 LinkedIn notes and 5 emails for each, and saves the
output to work/task136_generated.json for reading.
"""
import json
import sys
import os
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import providers, llm, generate, clients, lint


SNAPSHOT = "work/queue.snapshot.jsonl"
OUTPUT = "work/task136_generated.json"


def load_records():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def hash_id(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:12]


def pick_records(records, n=12):
    """Pick n records with economic_buyer contacts."""
    candidates = []
    for rec in records:
        if rec.get("drop_reason"):
            continue
        contacts = rec.get("contacts", {})
        if isinstance(contacts, list):
            contact_list = contacts
        elif isinstance(contacts, dict):
            contact_list = list(contacts.values())
        else:
            continue
        has_eb = any(c.get("persona") == "economic_buyer" for c in contact_list)
        if has_eb and rec.get("cadence"):
            candidates.append(rec)
    return candidates[:n]


def generate_sequence(rec, contact, client):
    """Generate all LinkedIn notes and emails for one contact."""
    result = {"linkedin": {}, "email": {}}

    li_keys = ["li1", "li2", "li3", "li4", "li5", "li6"]
    for step_key in li_keys:
        try:
            prompt = generate.render_prompt(
                "linkedin_note", rec, contact, client, step_key)
            data, _, _ = llm.ask(llm.OpenAICompatibleModel(),
                                 "linkedin_note", prompt)
            note = data.get("note", "").strip()
            note = lint.normalise_punctuation(note)
            result["linkedin"][step_key] = note
        except Exception as e:
            result["linkedin"][step_key] = f"ERROR: {e}"

    email_keys = ["em1", "em2", "em3", "em4", "em5"]
    for step_key in email_keys:
        try:
            prompt = generate.render_prompt(
                "draft", rec, contact, client, step_key)
            data, _, _ = llm.ask(llm.OpenAICompatibleModel(),
                                 "draft", prompt)
            subject = lint.normalise_punctuation(data.get("subject", ""))
            body = lint.normalise_punctuation(data.get("body", ""))
            result["email"][step_key] = {"subject": subject, "body": body}
        except Exception as e:
            result["email"][step_key] = {"subject": "ERROR",
                                          "body": str(e)}

    return result


def main():
    providers.load_env()
    model = llm.OpenAICompatibleModel()
    if not model.configured():
        print("ERROR: model not configured")
        return 1

    client = clients.load("productive")
    records = load_records()
    sample = pick_records(records, 12)

    if not sample:
        print("ERROR: no suitable records found")
        return 1

    print(f"Generating {len(sample)} sequences...")
    print(f"Model: {model.model}")
    print()

    output = []
    for i, rec in enumerate(sample):
        contacts = rec.get("contacts", {})
        if isinstance(contacts, list):
            contact = contacts[0]
        elif isinstance(contacts, dict):
            contact = list(contacts.values())[0]
        else:
            continue

        company = rec.get("company", "?")
        domain = rec.get("domain", "?")
        contact_name = contact.get("name", "?")
        contact_key = contact.get("key", "?")

        print(f"  [{i+1}/{len(sample)}] {company} / {contact_key}...")

        seq = generate_sequence(rec, contact, client)

        output.append({
            "company": company,
            "domain": domain,
            "contact_name_hash": hash_id(contact_name),
            "contact_key_hash": hash_id(contact_key),
            "sequence": seq,
        })

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {len(output)} sequences written to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
