#!/usr/bin/env python3
"""TASK-110: Read every generated sequence as a set.

Extracts all contact-level sequences from the queue snapshot and analyses
each for five sequence-level defects:
  1. Progression collapse (multiple rungs doing the same job)
  2. Tone drift / inconsistent voice
  3. Missing easy-out (no graceful decline at the end)
  4. Later steps pretending to be first contact
  5. Conceptual duplication (same ask in different words)

Reads only. No provider calls. Hashes all identifiers.
"""
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
STAMP = os.path.join(ROOT, "work", "queue.snapshot.STAMP")


def load_records():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_stamp():
    with open(STAMP, "r", encoding="utf-8") as f:
        return f.read().strip()


def hash_id(record_id, contact_name=None):
    """Hash a record ID or contact name to a short opaque token."""
    raw = record_id
    if contact_name:
        raw = f"{record_id}/{contact_name}"
    return "seq-" + hashlib.sha256(raw.encode()).hexdigest()[:10]


def hash_domain(domain):
    return "d-" + hashlib.sha256(domain.encode()).hexdigest()[:8]


def get_text(step):
    """Extract the readable text from a step."""
    parts = []
    if step.get("subject"):
        parts.append(f"Subject: {step['subject']}")
    if step.get("body"):
        parts.append(step["body"])
    if step.get("note"):
        parts.append(step["note"])
    return " | ".join(parts)


def normalise(text):
    """Lowercase, collapse whitespace, strip punctuation for comparison."""
    t = text.lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def similarity(a, b):
    """SequenceMatcher ratio between two normalised strings."""
    na, nb = normalise(a), normalise(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def extract_question(text):
    """Extract question sentences from text."""
    sentences = re.split(r'[.!?]\s+|\n', text)
    return [s.strip() for s in sentences if '?' in s]


def check_easy_out(steps_ordered):
    """Check if the last step provides an easy out / graceful decline."""
    if not steps_ordered:
        return False, "no steps"
    last_text = get_text(steps_ordered[-1][1]).lower()
    easy_out_phrases = [
        "no worries", "no problem", "if now's not", "if now is not",
        "if this isn't", "if this is not", "not the right time",
        "wish you", "wishing you", "no pressure", "understand if",
        "completely understand", "don't worry", "feel free to",
        "opt out", "unsubscribe", "stop hearing", "permission to stop",
        "close the loop", "easy no",
    ]
    found = [p for p in easy_out_phrases if p in last_text]
    return bool(found), found


def check_first_contact_pretend(steps_ordered):
    """Check if later steps re-introduce as if first contact."""
    if len(steps_ordered) < 2:
        return False, []
    issues = []
    intro_phrases = [
        "i'm reaching out", "i am reaching out", "my name is",
        "i work with", "i work at", "let me introduce",
        "i wanted to reach out", "reaching out to you",
        "i'm writing to you", "i am writing",
    ]
    for i, (key, step) in enumerate(steps_ordered[1:], start=2):
        text = get_text(step).lower()
        found_intros = [p for p in intro_phrases if p in text]
        if found_intros:
            issues.append((i, key, found_intros))
    return bool(issues), issues


def check_progression_keywords(steps_ordered):
    """Analyse what each step talks about - extract key phrases."""
    step_topics = []
    for key, step in steps_ordered:
        text = normalise(get_text(step))
        words = set(text.split())
        step_topics.append((key, words, text))
    return step_topics


def compute_pairwise_similarity(steps_ordered):
    """Compute pairwise text similarity between all steps."""
    pairs = []
    texts = [(key, get_text(step)) for key, step in steps_ordered]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            sim = similarity(texts[i][1], texts[j][1])
            if sim > 0.3:
                pairs.append((texts[i][0], texts[j][0], sim))
    return sorted(pairs, key=lambda x: -x[2])


def check_product_naming(steps_ordered):
    """Check if/where the product name appears in the sequence."""
    product_names = ["productive", "the platform", "the tool", "the system"]
    found_at = []
    for key, step in steps_ordered:
        text = get_text(step).lower()
        for pn in product_names:
            if pn in text:
                found_at.append((key, pn))
                break
    return found_at


def check_sender_identity(steps_ordered):
    """Check if any step identifies who is writing."""
    identity_phrases = [
        "i'm", "i am", "my name", "i work", "our team",
        "we are", "we're", "on behalf", "from res",
    ]
    found_at = []
    for key, step in steps_ordered:
        text = get_text(step).lower()
        found = [p for p in identity_phrases if p in text]
        if found:
            found_at.append((key, found))
    return found_at


def check_question_collapse(steps_ordered):
    """Check if multiple steps ask the same question."""
    questions_by_step = []
    for key, step in steps_ordered:
        text = get_text(step)
        qs = extract_question(text)
        questions_by_step.append((key, qs))

    collapse_pairs = []
    for i in range(len(questions_by_step)):
        for j in range(i + 1, len(questions_by_step)):
            ki, qi = questions_by_step[i]
            kj, qj = questions_by_step[j]
            for q1 in qi:
                for q2 in qj:
                    sim = similarity(q1, q2)
                    if sim > 0.5:
                        collapse_pairs.append((ki, kj, sim, q1[:80], q2[:80]))
    return collapse_pairs


def check_unacknowledged_silence(steps_ordered):
    """Check if later steps acknowledge earlier steps went unanswered."""
    if len(steps_ordered) < 3:
        return True, []  # Too short to need this
    ack_phrases = [
        "following up", "just checking", "circling back",
        "wanted to follow", "revisiting", "bumping",
        "i know you're busy", "i understand you",
        "in case you missed", "just wanted to",
        "checking in", "wanted to circle",
    ]
    issues = []
    for i, (key, step) in enumerate(steps_ordered[2:], start=3):
        text = get_text(step).lower()
        has_ack = any(p in text for p in ack_phrases)
        if not has_ack and i > 2:
            issues.append((i, key, "no acknowledgement of prior silence"))
    return len(issues) == 0, issues


def analyse_sequence(record_id, contact_name, steps_dict):
    """Full analysis of one contact's sequence."""
    # Order steps by their key
    step_order = sorted(steps_dict.keys(),
                        key=lambda k: (
                            0 if k.startswith("em") else
                            1 if k.startswith("li") else -1,
                            int(re.search(r'\d+', k).group() or 0)
                            if re.search(r'\d+', k) else 0
                        ))

    steps_ordered = [(k, steps_dict[k]) for k in step_order]
    generated_steps = [(k, s) for k, s in steps_ordered if s.get("generated")]

    result = {
        "record_id_hash": hash_id(record_id),
        "contact_hash": hash_id(record_id, contact_name),
        "domain_hash": hash_domain(record_id),
        "contact_name_hash": hash_id(contact_name),
        "total_steps": len(steps_ordered),
        "generated_steps": len(generated_steps),
        "channels": list(set(s.get("channel", "?") for _, s in steps_ordered)),
        "step_keys": step_order,
    }

    # 1. Easy out
    has_easy_out, easy_out_detail = check_easy_out(steps_ordered)
    result["easy_out"] = has_easy_out
    result["easy_out_detail"] = easy_out_detail

    # 2. First contact pretend
    has_pretend, pretend_detail = check_first_contact_pretend(steps_ordered)
    result["first_contact_pretend"] = has_pretend
    result["pretend_detail"] = pretend_detail

    # 3. Product naming
    product_at = check_product_naming(steps_ordered)
    result["product_named"] = len(product_at) > 0
    result["product_named_at"] = product_at

    # 4. Pairwise similarity (conceptual duplication)
    high_sim_pairs = compute_pairwise_similarity(steps_ordered)
    result["high_similarity_pairs"] = [(a, b, round(s, 3))
                                       for a, b, s in high_sim_pairs[:10]]
    result["max_similarity"] = round(high_sim_pairs[0][2], 3) if high_sim_pairs else 0.0

    # 5. Question collapse
    collapse = check_question_collapse(steps_ordered)
    result["question_collapse"] = collapse
    result["question_collapse_count"] = len(collapse)

    # 6. Unacknowledged silence
    silence_ok, silence_issues = check_unacknowledged_silence(steps_ordered)
    result["silence_acknowledged"] = silence_ok
    result["silence_issues_count"] = len(silence_issues)

    # 7. Sender identity
    identity = check_sender_identity(steps_ordered)
    result["sender_identity_at"] = [(k, fs) for k, fs in identity]

    # Full text for qualitative review
    result["step_texts"] = {k: get_text(s) for k, s in steps_ordered}

    return result


def main():
    records = load_records()
    stamp = read_stamp()

    print(f"Snapshot: {stamp}")
    print(f"Records: {len(records)}")

    all_sequences = []
    records_with_cadence = 0
    total_contacts = 0

    for rec in records:
        cadence = rec.get("cadence", {})
        if not cadence:
            continue
        records_with_cadence += 1
        for contact_name, steps in cadence.items():
            if not steps:
                continue
            total_contacts += 1
            result = analyse_sequence(rec["id"], contact_name, steps)
            result["record_state"] = rec.get("state", "?")
            result["company"] = rec.get("company", "")
            all_sequences.append(result)

    print(f"Records with cadence: {records_with_cadence}")
    print(f"Total sequences: {len(all_sequences)}")
    print()

    # Aggregate stats
    with_easy_out = sum(1 for s in all_sequences if s["easy_out"])
    with_pretend = sum(1 for s in all_sequences if s["first_contact_pretend"])
    with_product = sum(1 for s in all_sequences if s["product_named"])
    with_silence_ok = sum(1 for s in all_sequences if s["silence_acknowledged"])
    with_identity = sum(1 for s in all_sequences
                        if len(s["sender_identity_at"]) > 0)
    with_question_collapse = sum(1 for s in all_sequences
                                 if s["question_collapse_count"] > 0)
    with_high_sim = sum(1 for s in all_sequences if s["max_similarity"] > 0.5)

    n = len(all_sequences)
    print("=" * 70)
    print("AGGREGATE SEQUENCE QA METRICS")
    print("=" * 70)
    print(f"Denominator (total sequences): {n}")
    print()
    print(f"1. Easy out present:          {with_easy_out}/{n} "
          f"({100*with_easy_out/n:.1f}%)")
    print(f"2. First-contact pretend:     {with_pretend}/{n} "
          f"({100*with_pretend/n:.1f}%)")
    print(f"3. Product named somewhere:   {with_product}/{n} "
          f"({100*with_product/n:.1f}%)")
    print(f"4. Silence acknowledged:      {with_silence_ok}/{n} "
          f"({100*with_silence_ok/n:.1f}%)")
    print(f"5. Sender identity present:   {with_identity}/{n} "
          f"({100*with_identity/n:.1f}%)")
    print(f"6. Question collapse (>0.5):  {with_question_collapse}/{n} "
          f"({100*with_question_collapse/n:.1f}%)")
    print(f"7. High similarity pair (>0.5): {with_high_sim}/{n} "
          f"({100*with_high_sim/n:.1f}%)")
    print()

    # Output full text for qualitative review
    print("=" * 70)
    print("PER-SEQUENCE DETAIL (for qualitative review)")
    print("=" * 70)
    for seq in all_sequences:
        print()
        print(f"--- {seq['record_id_hash']} / {seq['contact_hash']} "
              f"(state={seq['record_state']}, steps={seq['total_steps']}, "
              f"gen={seq['generated_steps']}, "
              f"channels={seq['channels']}) ---")
        print(f"  Step keys: {seq['step_keys']}")
        print(f"  Easy out: {seq['easy_out']} ({seq['easy_out_detail']})")
        print(f"  First-contact pretend: {seq['first_contact_pretend']}")
        if seq['pretend_detail']:
            for step_i, key, phrases in seq['pretend_detail']:
                print(f"    Step {step_i} ({key}): {phrases}")
        print(f"  Product named: {seq['product_named']} at {seq['product_named_at']}")
        print(f"  Max similarity: {seq['max_similarity']}")
        if seq['high_similarity_pairs']:
            for a, b, s in seq['high_similarity_pairs'][:5]:
                print(f"    {a} <-> {b}: {s}")
        print(f"  Question collapse pairs: {seq['question_collapse_count']}")
        for ki, kj, s, q1, q2 in seq['question_collapse'][:3]:
            print(f"    {ki} <-> {kj} (sim={s:.2f})")
            print(f"      Q1: {q1}")
            print(f"      Q2: {q2}")
        print(f"  Silence acknowledged: {seq['silence_acknowledged']} "
              f"(issues: {seq['silence_issues_count']})")
        print(f"  Sender identity at: {seq['sender_identity_at']}")
        print()
        for key in seq['step_keys']:
            text = seq['step_texts'].get(key, '')
            print(f"  [{key}] {text[:300]}")
        print()


if __name__ == "__main__":
    main()
