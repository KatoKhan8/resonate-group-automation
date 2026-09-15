"""TASK-150: Measure how much company evidence is duplicated across contacts.

For a multi-contact record, builds the real generation context for each
contact through generate.context_for and measures byte-identical overlap
in the company-derived portions.
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import generate, store


def company_derived_keys(block):
    """Keys in a context block that come from the company/record, not the contact."""
    return {"company", "domain", "facts", "public_evidence", "research"}


def measure_record(rec):
    contacts = rec.get("contacts", [])
    if len(contacts) < 3:
        return None

    # Build context for each contact at the "draft" step (the main email generation)
    contexts = []
    for c in contacts:
        ctx = generate.context_for("draft", rec, contact=c)
        contexts.append((c.get("name", "?"), ctx))

    # Analyse company-derived blocks
    print(f"\n{'='*70}")
    print(f"Record: {rec['id']}  domain: {rec.get('domain')}  contacts: {len(contacts)}")
    print(f"Research rows: {len(rec.get('research', []))}")
    print(f"{'='*70}")

    # For each company-derived key, check byte-identity across all contacts
    company_keys = company_derived_keys(contexts[0][1])
    for key in sorted(company_keys):
        values = []
        for name, ctx in contexts:
            val = ctx.get(key)
            values.append((name, val))

        # Check if all values are byte-identical
        serialized = [json.dumps(v, sort_keys=True, ensure_ascii=False) for _, v in values]
        all_identical = len(set(serialized)) == 1
        unique_count = len(set(serialized))

        # Token estimate: ~4 chars per token for English
        total_chars = sum(len(s) for s in serialized)
        estimated_tokens = total_chars // 4

        print(f"\n  Key: {key}")
        print(f"    All contacts identical: {all_identical}  (unique variants: {unique_count})")
        print(f"    Total chars across {len(contacts)} contacts: {total_chars}")
        print(f"    Estimated tokens (all contacts): {estimated_tokens}")
        if not all_identical:
            # Show what differs
            for name, s in zip([n for n, _ in values], serialized):
                print(f"      {name}: {len(s)} chars")

    # Now compute the TOTAL company-derived content per contact
    print(f"\n  --- TOTAL COMPANY-DERIVED CONTENT PER CONTACT ---")
    total_per_contact = []
    for name, ctx in contexts:
        company_chars = 0
        for key in company_keys:
            val = ctx.get(key)
            if val is not None:
                company_chars += len(json.dumps(val, sort_keys=True, ensure_ascii=False))
        total_per_contact.append((name, company_chars))
        print(f"    {name}: {company_chars} chars (~{company_chars // 4} tokens)")

    # Compute the unique company content (build once)
    # Use the first contact's values for identical keys
    unique_chars = 0
    for key in sorted(company_keys):
        val = contexts[0][1].get(key)
        if val is not None:
            unique_chars += len(json.dumps(val, sort_keys=True, ensure_ascii=False))
    print(f"\n  Unique company content (build once): {unique_chars} chars (~{unique_chars // 4} tokens)")
    total_sent = sum(c for _, c in total_per_contact)
    print(f"  Total sent across {len(contacts)} contacts: {total_sent} chars (~{total_sent // 4} tokens)")
    if unique_chars > 0:
        print(f"  Duplication factor: {total_sent / unique_chars:.1f}x")
        saving = total_sent - unique_chars
        print(f"  Saving from build-once: {saving} chars (~{saving // 4} tokens)")

    # Contact-specific content (what SHOULD differ)
    print(f"\n  --- CONTACT-SPECIFIC CONTENT PER CONTACT ---")
    contact_keys = set(ctx.keys()) - company_keys
    for name, ctx in contexts:
        contact_chars = 0
        for key in contact_keys:
            val = ctx.get(key)
            if val is not None:
                contact_chars += len(json.dumps(val, sort_keys=True, ensure_ascii=False))
        print(f"    {name}: {contact_chars} chars (contact-specific)")

    return contexts


def main():
    # Load snapshot
    snapshot_path = os.path.join(os.path.dirname(__file__), "..", "work", "queue.snapshot.jsonl")
    records = []
    with open(snapshot_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # Find multi-contact records with research
    multi = [r for r in records if len(r.get("contacts", [])) >= 3 and r.get("research")]
    print(f"Snapshot: 550 records, 14 multi-contact with research")
    print(f"Found {len(multi)} candidates")

    # Pick surface51-com (exactly 3 contacts, 5 research rows)
    target = None
    for r in multi:
        if r["id"] == "surface51-com":
            target = r
            break

    if target is None:
        # Fallback to first
        target = multi[0]

    measure_record(target)

    # Also measure a larger one for comparison
    print("\n\n" + "#" * 70)
    print("# SECONDARY: larger record for scale comparison")
    print("#" * 70)
    for r in multi:
        if r["id"] == "directmail-com":
            measure_record(r)
            break


if __name__ == "__main__":
    main()
