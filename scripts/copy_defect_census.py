#!/usr/bin/env python3
"""TASK-092: Count six copy defects across the entire generated estate.

Reads work/queue.snapshot.jsonl (300 records, snapshot taken 2026-09-14T21:52:15Z
from master 0ac5e60). Measures all six defects from the task specification
across every generated step. Outputs results as JSON for the report.

Entry point: the cadence dict on each record, keyed by contact key, then by
step key (li1..li6, em1..em5). Each step has channel, generated flag, and
either 'note' (LinkedIn) or 'subject'+'body' (email).
"""
import hashlib
import json
import re
import sys
import os
from collections import Counter, defaultdict
from difflib import SequenceMatcher

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "work",
                        "queue.snapshot.jsonl")


def load_records():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def hash_id(record_id, contact_key=None):
    """Hash an identifier for safe reporting."""
    raw = f"{record_id}/{contact_key}" if contact_key else record_id
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def all_first_names(records):
    """Collect every first name from every contact in the estate."""
    names = set()
    for rec in records:
        for contact in rec.get("contacts", []):
            name = (contact.get("name") or "").strip()
            if name:
                first = name.split()[0].lower()
                if len(first) > 1:
                    names.add(first)
    return names


def step_text(step):
    """All text content of a step, concatenated."""
    parts = []
    if step.get("note"):
        parts.append(step["note"])
    if step.get("subject"):
        parts.append(step["subject"])
    if step.get("body"):
        parts.append(step["body"])
    return " ".join(parts)


def normalize(text):
    """Normalize for duplicate detection: lowercase, collapse whitespace, strip punctuation."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# --------------------------------------------------------- DEFECT 1: Hardcoded first names

def check_hardcoded_names(records):
    """Check every generated step for literal first names from the contact set."""
    all_names = all_first_names(records)
    findings = []
    steps_checked = 0

    for rec in records:
        cadence = rec.get("cadence") or {}
        for contact_key, steps in cadence.items():
            contact = None
            for c in rec.get("contacts", []):
                if c.get("key") == contact_key:
                    contact = c
                    break
            contact_name = (contact.get("name") or "") if contact else ""
            contact_first = contact_name.split()[0].lower() if contact_name else ""

            for step_id, step in steps.items():
                if not step.get("generated"):
                    continue
                steps_checked += 1
                text = step_text(step).lower()

                # Check for the contact's own first name
                if contact_first and len(contact_first) > 1:
                    pattern = r"\b" + re.escape(contact_first) + r"\b"
                    if re.search(pattern, text):
                        findings.append({
                            "record_id": rec["id"],
                            "contact_key": contact_key,
                            "step_id": step_id,
                            "channel": step.get("channel"),
                            "name_found": contact_first,
                            "hashed_id": hash_id(rec["id"], contact_key),
                            "text_snippet": step_text(step)[:150],
                        })

                # Check for OTHER first names from the estate (cross-contamination)
                for name in all_names:
                    if name == contact_first:
                        continue
                    if len(name) <= 2:
                        continue
                    pattern = r"\b" + re.escape(name) + r"\b"
                    if re.search(pattern, text):
                        findings.append({
                            "record_id": rec["id"],
                            "contact_key": contact_key,
                            "step_id": step_id,
                            "channel": step.get("channel"),
                            "name_found": name,
                            "hashed_id": hash_id(rec["id"], contact_key),
                            "text_snippet": step_text(step)[:150],
                            "type": "cross_contamination",
                        })

    return {
        "defect": "hardcoded_first_names",
        "steps_checked": steps_checked,
        "count": len(findings),
        "findings": findings,
    }


# --------------------------------------------------------- DEFECT 2: Merge variables that are real

# EmailBison exposes: headline, industry, location - and NOTHING else
# (no first_name, no company)
# HeyReach exposes: {FIRST_NAME}, {COMPANY}, {POSITION}, {INDUSTRY},
# {LOCATION}, {MY_FIRST_NAME}, {MY_LAST_NAME}, {Icebreaker}, plus custom fields

EMAILBISON_VARIABLES = {"headline", "industry", "location"}
HEYREACH_VARIABLES = {
    "FIRST_NAME", "COMPANY", "POSITION", "INDUSTRY", "LOCATION",
    "MY_FIRST_NAME", "MY_LAST_NAME", "Icebreaker",
    "connection_note", "connected_1", "connected_2", "connected_3",
    "connected_4", "message_2", "message_3", "message_4",
}

# Pattern for merge variables: {variable_name} or {{variable_name}}
MERGE_VAR_PATTERN = re.compile(r"\{(\{?)([A-Za-z_][A-Za-z0-9_]*)\1\}")


def check_merge_variables(records):
    """Check for variables the provider does NOT expose."""
    findings = []
    steps_checked = 0

    for rec in records:
        cadence = rec.get("cadence") or {}
        for contact_key, steps in cadence.items():
            for step_id, step in steps.items():
                if not step.get("generated"):
                    continue
                steps_checked += 1
                channel = step.get("channel")
                text = step_text(step)

                # Find all {variable} patterns
                vars_found = MERGE_VAR_PATTERN.findall(text)
                for double_brace, var_name in vars_found:
                    is_double = bool(double_brace)
                    if channel == "email":
                        if var_name not in EMAILBISON_VARIABLES:
                            findings.append({
                                "record_id": rec["id"],
                                "contact_key": contact_key,
                                "step_id": step_id,
                                "channel": channel,
                                "variable": var_name,
                                "double_brace": is_double,
                                "hashed_id": hash_id(rec["id"], contact_key),
                                "text_snippet": text[:150],
                            })
                    elif channel == "linkedin":
                        if var_name not in HEYREACH_VARIABLES:
                            findings.append({
                                "record_id": rec["id"],
                                "contact_key": contact_key,
                                "step_id": step_id,
                                "channel": channel,
                                "variable": var_name,
                                "double_brace": is_double,
                                "hashed_id": hash_id(rec["id"], contact_key),
                                "text_snippet": text[:150],
                            })

    return {
        "defect": "unsupported_merge_variables",
        "steps_checked": steps_checked,
        "count": len(findings),
        "findings": findings,
    }


# --------------------------------------------------------- DEFECT 3: Duplicate follow-ups

def check_duplicates(records):
    """Check for duplicate or near-duplicate steps within a sequence."""
    exact_dupes = []
    near_dupes = []
    sequences_checked = 0

    for rec in records:
        cadence = rec.get("cadence") or {}
        for contact_key, steps in cadence.items():
            li_steps = {}
            em_steps = {}
            for step_id, step in steps.items():
                if not step.get("generated"):
                    continue
                if step.get("channel") == "linkedin":
                    li_steps[step_id] = step
                elif step.get("channel") == "email":
                    em_steps[step_id] = step

            for channel, channel_steps in [("linkedin", li_steps), ("email", em_steps)]:
                if len(channel_steps) < 2:
                    continue
                sequences_checked += 1
                step_ids = sorted(channel_steps.keys())
                for i in range(len(step_ids)):
                    for j in range(i + 1, len(step_ids)):
                        sid_i, sid_j = step_ids[i], step_ids[j]
                        text_i = normalize(step_text(channel_steps[sid_i]))
                        text_j = normalize(step_text(channel_steps[sid_j]))

                        if text_i and text_j and text_i == text_j:
                            exact_dupes.append({
                                "record_id": rec["id"],
                                "contact_key": contact_key,
                                "channel": channel,
                                "step_a": sid_i,
                                "step_b": sid_j,
                                "hashed_id": hash_id(rec["id"], contact_key),
                            })
                        elif text_i and text_j:
                            ratio = SequenceMatcher(None, text_i, text_j).ratio()
                            if ratio >= 0.85:
                                near_dupes.append({
                                    "record_id": rec["id"],
                                    "contact_key": contact_key,
                                    "channel": channel,
                                    "step_a": sid_i,
                                    "step_b": sid_j,
                                    "similarity": round(ratio, 3),
                                    "hashed_id": hash_id(rec["id"], contact_key),
                                })

    return {
        "defect": "duplicate_followups",
        "sequences_checked": sequences_checked,
        "exact_duplicates": len(exact_dupes),
        "near_duplicates": len(near_dupes),
        "total": len(exact_dupes) + len(near_dupes),
        "exact_findings": exact_dupes,
        "near_findings": near_dupes,
    }


# --------------------------------------------------------- DEFECT 4: Productive introduced with context

def check_productive_naming(records):
    """Check whether 'Productive' (the product) is named in each sequence,
    and whether the naming is accompanied by an explanation."""
    product_names = ["productive", "productiv"]
    sequences = []

    for rec in records:
        cadence = rec.get("cadence") or {}
        for contact_key, steps in cadence.items():
            li_steps = {}
            em_steps = {}
            for step_id, step in steps.items():
                if not step.get("generated"):
                    continue
                if step.get("channel") == "linkedin":
                    li_steps[step_id] = step
                elif step.get("channel") == "email":
                    em_steps[step_id] = step

            for channel, channel_steps in [("linkedin", li_steps), ("email", em_steps)]:
                if not channel_steps:
                    continue
                seq_key = f"{rec['id']}/{contact_key}/{channel}"
                named = False
                named_at_step = None
                has_explanation = False
                explanation_snippet = ""

                for step_id in sorted(channel_steps.keys()):
                    step = channel_steps[step_id]
                    text = step_text(step).lower()
                    for pname in product_names:
                        if pname in text:
                            named = True
                            if named_at_step is None:
                                named_at_step = step_id
                            # Check for explanation: a sentence containing the product
                            # name AND a verb/description (not just a bare noun)
                            sentences = re.split(r"[.!?]+", text)
                            for sent in sentences:
                                if pname in sent and len(sent.split()) > 5:
                                    has_explanation = True
                                    explanation_snippet = sent.strip()[:150]
                                    break
                    if has_explanation:
                        break

                sequences.append({
                    "record_id": rec["id"],
                    "contact_key": contact_key,
                    "channel": channel,
                    "hashed_id": hash_id(rec["id"], contact_key),
                    "product_named": named,
                    "named_at_step": named_at_step,
                    "has_explanation": has_explanation,
                    "explanation_snippet": explanation_snippet if has_explanation else "",
                    "total_steps": len(channel_steps),
                })

    named_count = sum(1 for s in sequences if s["product_named"])
    explained_count = sum(1 for s in sequences if s["has_explanation"])
    total = len(sequences)

    by_channel = {"linkedin": {"total": 0, "named": 0, "explained": 0},
                  "email": {"total": 0, "named": 0, "explained": 0}}
    for s in sequences:
        by_channel[s["channel"]]["total"] += 1
        if s["product_named"]:
            by_channel[s["channel"]]["named"] += 1
        if s["has_explanation"]:
            by_channel[s["channel"]]["explained"] += 1

    unnamed = [s for s in sequences if not s["product_named"]]

    return {
        "defect": "productive_naming",
        "total_sequences": total,
        "named": named_count,
        "named_pct": round(named_count / total * 100, 1) if total else 0,
        "explained": explained_count,
        "explained_pct": round(explained_count / total * 100, 1) if total else 0,
        "by_channel": by_channel,
        "unnamed_sequences": unnamed[:20],
    }


# --------------------------------------------------------- DEFECT 5: Greeting and personalisation render

GREETING_PATTERNS = [
    (r"(?:hey|hi|hello|dear)\s+,", "empty_greeting"),
    (r"(?:hey|hi|hello|dear)\s+undefined\b", "undefined_greeting"),
    (r"(?:hey|hi|hello|dear)\s+null\b", "null_greeting"),
    (r"(?:hey|hi|hello|dear)\s+none\b", "none_greeting"),
    (r"(?:hey|hi|hello|dear)\s+\{", "placeholder_greeting"),
]

# Cohort names that should not appear as person names
COHORT_NAMES = {"team", "folks", "everyone", "all", "there"}


def check_greetings(records):
    """Check for broken greetings in generated steps."""
    findings = []
    steps_checked = 0
    missing_greeting = []

    for rec in records:
        cadence = rec.get("cadence") or {}
        for contact_key, steps in cadence.items():
            for step_id, step in steps.items():
                if not step.get("generated"):
                    continue
                steps_checked += 1
                text = step_text(step)
                channel = step.get("channel")

                found_defect = False
                for pattern, defect_type in GREETING_PATTERNS:
                    if re.search(pattern, text, re.IGNORECASE):
                        findings.append({
                            "record_id": rec["id"],
                            "contact_key": contact_key,
                            "step_id": step_id,
                            "channel": channel,
                            "defect_type": defect_type,
                            "hashed_id": hash_id(rec["id"], contact_key),
                            "text_snippet": text[:150],
                        })
                        found_defect = True
                        break

                if not found_defect:
                    # Check if the step has NO greeting at all (for email, first line)
                    if channel == "email":
                        body = (step.get("body") or "").strip()
                        first_line = body.split("\n")[0].strip() if body else ""
                        has_greeting = bool(re.match(
                            r"(?:hey|hi|hello|dear|good\s+(?:morning|afternoon|evening))\b",
                            first_line, re.IGNORECASE))
                        if not has_greeting and first_line:
                            # Not every email needs a greeting, but flag if the
                            # first line looks like it should be one
                            pass

    return {
        "defect": "greeting_render",
        "steps_checked": steps_checked,
        "count": len(findings),
        "findings": findings,
    }


# --------------------------------------------------------- DEFECT 6: Signatures

SIGNATURE_PATTERNS = [
    r"(?:best\s+regards|kind\s+regards|regards|thanks|thank\s+you|cheers|sincerely|warm\s+regards|all\s+the\s+best)\s*,?\s*\n?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
    r"(?:--\s*\n)(.+)",
    r"(?:^|\n)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\n(?:CEO|CTO|COO|Founder|Co-Founder|Director|Manager|Head|Lead)",
]

SENDER_IDENTITY_PATTERNS = [
    r"(?:my\s+name\s+is|i\s+am|i'm)\s+([A-Z][a-z]+)",
    r"(?:from|on\s+behalf\s+of|representing)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*(?:\n|$)(?:CEO|CTO|COO|Founder|Director|Manager)",
]


def check_signatures(records):
    """Check for missing or incomplete signatures in email steps."""
    findings = []
    steps_checked = 0
    no_signature = []
    has_signature = 0
    has_sender_identity = 0

    for rec in records:
        cadence = rec.get("cadence") or {}
        for contact_key, steps in cadence.items():
            for step_id, step in steps.items():
                if not step.get("generated"):
                    continue
                if step.get("channel") != "email":
                    continue
                steps_checked += 1
                body = step.get("body") or ""

                # Check for signature
                sig_found = False
                for pattern in SIGNATURE_PATTERNS:
                    if re.search(pattern, body, re.IGNORECASE | re.MULTILINE):
                        sig_found = True
                        has_signature += 1
                        break

                if not sig_found:
                    no_signature.append({
                        "record_id": rec["id"],
                        "contact_key": contact_key,
                        "step_id": step_id,
                        "hashed_id": hash_id(rec["id"], contact_key),
                        "body_tail": body[-200:] if body else "",
                    })

                # Check for sender identity (name of who is writing)
                identity_found = False
                for pattern in SENDER_IDENTITY_PATTERNS:
                    if re.search(pattern, body):
                        identity_found = True
                        has_sender_identity += 1
                        break

                if not identity_found:
                    findings.append({
                        "record_id": rec["id"],
                        "contact_key": contact_key,
                        "step_id": step_id,
                        "hashed_id": hash_id(rec["id"], contact_key),
                        "defect_type": "no_sender_identity",
                        "body_tail": body[-200:] if body else "",
                    })

    return {
        "defect": "signatures",
        "email_steps_checked": steps_checked,
        "has_signature": has_signature,
        "no_signature_count": len(no_signature),
        "has_sender_identity": has_sender_identity,
        "no_sender_identity_count": len(findings),
        "no_signature_examples": no_signature[:5],
        "no_identity_examples": findings[:5],
    }


# --------------------------------------------------------- MAIN

def main():
    records = load_records()
    print(f"Loaded {len(records)} records from snapshot")

    # Filter to records with cadences (generated content)
    recs_with_cadence = [r for r in records if r.get("cadence")]
    print(f"Records with cadences: {len(recs_with_cadence)}")

    # Count total generated steps
    total_gen = 0
    total_li = 0
    total_em = 0
    for rec in records:
        for ck, steps in (rec.get("cadence") or {}).items():
            for sk, step in steps.items():
                if step.get("generated"):
                    total_gen += 1
                    if step.get("channel") == "linkedin":
                        total_li += 1
                    elif step.get("channel") == "email":
                        total_em += 1
    print(f"Total generated steps: {total_gen} (LI: {total_li}, Email: {total_em})")
    print()

    # Run all six checks
    d1 = check_hardcoded_names(records)
    print(f"Defect 1 - Hardcoded first names: {d1['count']} findings "
          f"across {d1['steps_checked']} steps")

    d2 = check_merge_variables(records)
    print(f"Defect 2 - Unsupported merge variables: {d2['count']} findings "
          f"across {d2['steps_checked']} steps")

    d3 = check_duplicates(records)
    print(f"Defect 3 - Duplicate follow-ups: {d3['exact_duplicates']} exact, "
          f"{d3['near_duplicates']} near-duplicates "
          f"across {d3['sequences_checked']} sequences")

    d4 = check_productive_naming(records)
    print(f"Defect 4 - Productive naming: {d4['named']}/{d4['total_sequences']} "
          f"sequences name the product ({d4['named_pct']}%), "
          f"{d4['explained']} with explanation ({d4['explained_pct']}%)")

    d5 = check_greetings(records)
    print(f"Defect 5 - Greeting defects: {d5['count']} findings "
          f"across {d5['steps_checked']} steps")

    d6 = check_signatures(records)
    print(f"Defect 6 - Signatures: {d6['no_signature_count']}/{d6['email_steps_checked']} "
          f"email steps have no signature, "
          f"{d6['no_sender_identity_count']}/{d6['email_steps_checked']} "
          f"have no sender identity")

    # Output full results as JSON
    results = {
        "estate": {
            "total_records": len(records),
            "records_with_cadence": len(recs_with_cadence),
            "total_generated_steps": total_gen,
            "linkedin_steps": total_li,
            "email_steps": total_em,
        },
        "defect_1_hardcoded_names": d1,
        "defect_2_merge_variables": d2,
        "defect_3_duplicates": d3,
        "defect_4_productive_naming": d4,
        "defect_5_greetings": d5,
        "defect_6_signatures": d6,
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "out",
                            "copy_defect_census.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()
