#!/usr/bin/env python3
"""TASK-131: sample regeneration to measure the four defect fixes.

Picks 3 records from the snapshot, generates LinkedIn notes and emails
against the updated prompts, and measures:
  1. Easy out at the last rung
  2. "I noticed" opener
  3. Unsupported "i admire how" claim
  4. Repeated greeting across rungs

Does NOT write to the queue. Read-only against the snapshot.
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import providers, llm, generate, clients, lint
from src import claims as claims_mod


def load_snapshot_records(n=3):
    """Pick n records with contacts from the snapshot."""
    records = []
    with open("work/queue.snapshot.jsonl", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("contacts") and rec.get("cadence"):
                records.append(rec)
            if len(records) >= n:
                break
    return records


def has_easy_out(text):
    """Does the text give a graceful way to decline?"""
    low = text.lower()
    markers = [
        "leave it here", "happy to leave", "if the timing",
        "no problem", "totally understand", "completely understand",
        "if now isn't", "if this isn't", "if you'd rather",
        "someone else", "somebody else", "right person",
        "who owns", "who handles", "who manages",
    ]
    return any(m in low for m in markers)


def has_i_noticed(text):
    """Does the text open with 'i noticed' or 'i saw that'?"""
    low = text.lower().strip()
    return bool(re.match(r"^(hi\s+\S+,?\s+)?i\s+(?:noticed|saw\s+that)\b", low))


def has_admire_claim(text):
    """Does the text contain 'i admire how' or similar unsupported flattery?"""
    low = text.lower()
    patterns = [
        r"i\s+admire\s+how",
        r"i\s+admire\s+your",
        r"impressive\s+growth",
        r"i\s+love\s+what\s+(?:you|your)",
        r"amazing\s+(?:work|job|growth|progress)",
    ]
    return any(re.search(p, low) for p in patterns)


def extract_greeting(text):
    """Extract the opening greeting pattern from a LinkedIn note."""
    low = text.lower().strip()
    m = re.match(r"^(hi\s+\S+,?\s+\S+\s+(?:here|from)\s+\S+)", low)
    if m:
        return m.group(1)
    m = re.match(r"^(hi\s+\S+,?\s+\S+\s+from\s+\S+)", low)
    if m:
        return m.group(1)
    return ""


def measure_greeting_repetition(notes):
    """Count how many notes share the same greeting pattern."""
    greetings = [extract_greeting(n) for n in notes if extract_greeting(n)]
    if not greetings:
        return 0, len(notes)
    from collections import Counter
    counts = Counter(greetings)
    most_common = counts.most_common(1)[0]
    return most_common[1], len(notes)


def main():
    providers.load_env()
    model = llm.OpenAICompatibleModel()
    if not model.configured():
        print("ERROR: model not configured")
        return 1

    client = clients.load("productive")
    records = load_snapshot_records(3)
    if not records:
        print("ERROR: no records found in snapshot")
        return 1

    print(f"Sample: {len(records)} records, model={model.model}")
    print(f"Records: {[r.get('company', '?') for r in records]}")
    print()

    total_li_notes = 0
    total_emails = 0
    defect1_no_easy_out = 0
    defect2_i_noticed = 0
    defect3_admire = 0
    defect4_repeated_greeting = 0

    for ri, rec in enumerate(records):
        contacts = rec.get("contacts", {})
        if isinstance(contacts, list):
            contact = contacts[0]
            contact_key = contact.get("key", "contact")
        else:
            contact_key = list(contacts.keys())[0]
            contact = contacts[contact_key]
        company = rec.get("company", "?")
        print(f"--- Record {ri+1}: {company} / {contact_key} ---")

        # Generate LinkedIn notes for all 6 rungs
        li_notes = []
        li_keys = ["li1", "li2", "li3", "li4", "li5", "li6"]
        for step_key in li_keys:
            try:
                prompt = generate.render_prompt(
                    "linkedin_note", rec, contact, client, step_key)
                data, _, _ = llm.ask(model, "linkedin_note", prompt)
                note = data.get("note", "").strip()
                note = lint.normalise_punctuation(note)
                li_notes.append((step_key, note))
                total_li_notes += 1
            except Exception as e:
                print(f"  {step_key}: ERROR - {e}")
                li_notes.append((step_key, ""))

        # Generate emails for all 5 rungs
        emails = []
        email_keys = ["em1", "em2", "em3", "em4", "em5"]
        for step_key in email_keys:
            try:
                prompt = generate.render_prompt(
                    "draft", rec, contact, client, step_key)
                data, _, _ = llm.ask(model, "draft", prompt)
                subject = lint.normalise_punctuation(
                    data.get("subject", ""))
                body = lint.normalise_punctuation(data.get("body", ""))
                emails.append((step_key, subject, body))
                total_emails += 1
            except Exception as e:
                print(f"  {step_key}: ERROR - {e}")
                emails.append((step_key, "", ""))

        # Print generated content
        print("\n  LinkedIn notes:")
        for key, note in li_notes:
            print(f"    {key}: {note[:120]}...")

        print("\n  Emails:")
        for key, subj, body in emails:
            print(f"    {key}: [{subj}] {body[:100]}...")

        # Measure defects
        print("\n  Defect measurements:")

        # Defect 1: Easy out at last LinkedIn rung
        last_li = li_notes[-1][1] if li_notes else ""
        if last_li and not has_easy_out(last_li):
            defect1_no_easy_out += 1
            print(f"    [FAIL] Defect 1: No easy out in {li_notes[-1][0]}")
        elif last_li:
            print(f"    [PASS] Defect 1: Easy out present in {li_notes[-1][0]}")

        # Defect 2: "I noticed" opener in emails
        email_had_i_noticed = False
        for key, subj, body in emails:
            if has_i_noticed(body):
                defect2_i_noticed += 1
                email_had_i_noticed = True
                print(f"    [FAIL] Defect 2: 'I noticed' in {key}")
        for key, note in li_notes:
            if has_i_noticed(note):
                defect2_i_noticed += 1
                email_had_i_noticed = True
                print(f"    [FAIL] Defect 2: 'I noticed' in {key}")
        if not email_had_i_noticed:
            print(f"    [PASS] Defect 2: No 'I noticed' openers")

        # Defect 3: "i admire how" unsupported claim
        admire_found = False
        for key, note in li_notes:
            if has_admire_claim(note):
                defect3_admire += 1
                admire_found = True
                print(f"    [FAIL] Defect 3: Unsupported claim in {key}")
        for key, subj, body in emails:
            if has_admire_claim(body):
                defect3_admire += 1
                admire_found = True
                print(f"    [FAIL] Defect 3: Unsupported claim in {key}")
        if not admire_found:
            print(f"    [PASS] Defect 3: No unsupported flattery")

        # Defect 4: Repeated greeting
        note_texts = [n for _, n in li_notes if n]
        if len(note_texts) >= 2:
            repeat_count, total = measure_greeting_repetition(note_texts)
            if repeat_count > 2:
                defect4_repeated_greeting += 1
                print(f"    [FAIL] Defect 4: Greeting repeated "
                      f"{repeat_count}/{total} times")
            else:
                print(f"    [PASS] Defect 4: Max greeting repeat "
                      f"{repeat_count}/{total}")

        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Records sampled: {len(records)}")
    print(f"LinkedIn notes generated: {total_li_notes}")
    print(f"Emails generated: {total_emails}")
    print()
    print(f"Defect 1 (no easy out):       "
          f"{defect1_no_easy_out}/{len(records)} sequences")
    print(f"Defect 2 ('I noticed' opener): {defect2_i_noticed} occurrences")
    print(f"Defect 3 (unsupported claim):  {defect3_admire} occurrences")
    print(f"Defect 4 (repeated greeting):  "
          f"{defect4_repeated_greeting}/{len(records)} sequences")
    print()

    # Verdict
    all_pass = (defect1_no_easy_out == 0 and defect2_i_noticed == 0
                and defect3_admire == 0 and defect4_repeated_greeting == 0)
    if all_pass:
        print("VERDICT: ALL FOUR DEFECTS FIXED IN SAMPLE")
    else:
        print("VERDICT: SOME DEFECTS REMAIN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
