"""TASK-179: Approval mechanism analysis and CONTROL-fallback canary check.

This script:
1. Explains the approval mechanism
2. Renders the CONTROL fallbacks for contacts 2 and 3
3. Checks if the CONTROL fallbacks pass lint and claims
"""
import hashlib
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import lint, claims, heyreachfactory

SNAPSHOT = os.path.join("work", "queue.snapshot.jsonl")
CONFIG_PATH = os.path.join("config", "clients", "productive.yaml")
OUTPUT_DOC = os.path.join("docs", "LI6-AND-APPROVAL-2026-09-16.md")

# The three rung-3 contacts by domain (from TASK-176)
TARGET_DOMAINS = {"20northmarketing.com", "2ton.com", "321webmarketing.com"}


def _hash(value):
    """SHA-256 prefix for PII hashing. 12 hex chars."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def load_snapshot():
    """Load the queue snapshot."""
    recs = []
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                recs.append(json.loads(line))
    return recs


def load_config():
    """Load the client config."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_target_records(recs):
    """Find the three target records."""
    targets = {}
    for rec in recs:
        if rec.get("domain") in TARGET_DOMAINS:
            targets[rec["domain"]] = rec
    return targets


def get_control_fallbacks(config):
    """Get the CONTROL fallbacks from the config."""
    return (config.get("linkedin_sequence") or {}).get("fallbacks") or {}


def check_lint_linkedin(text, is_note=False):
    """Check if LinkedIn text passes lint."""
    # Mirror the lint checks from src/lint.py
    fails = set()
    text = text.replace("\r\n", "\n").replace("\r\n", "\n").strip()

    if not text:
        fails.add("note_missing" if is_note else "message_missing")
        return sorted(fails)

    # Placeholder check
    import re
    placeholder_re = re.compile(r"[\[{<](?!http)[^\]}>\n]{2,40}[\]}>]")
    if placeholder_re.search(text):
        fails.add("placeholder")

    # Em dash check
    substituted_punctuation = ("\u2014", "\u2013", "\u2011", "\u2019", "\u2018")
    if any(d in text for d in substituted_punctuation):
        fails.add("em_dash")

    # Attachment check
    attachment_re = re.compile(
        r"\battachment\b"
        r"|attached (is|are|you'?ll|please|here|below)"
        r"|(see|find|i'?ve|i have|we'?ve) attached"
        r"|attached (file|screenshot|deck|pdf|doc|csv|list|sheet|rate card)"
        r"|(file|screenshot|deck|pdf|doc|csv|sheet|rate card|image)s? attached",
        re.I)
    if attachment_re.search(text):
        fails.add("attachment")

    # Banned phrases
    banned_phrases = (
        "i hope this email finds you well", "i wanted to reach out", "circling back",
        "just following up", "touching base", "as per my last email", "synergy",
        "game-changer",
    )
    low = text.lower()
    if any(phrase in low for phrase in banned_phrases):
        fails.add("banned_phrase")

    # Cross-channel terms
    cross_channel_terms = ("my email", "the email i sent", "as i wrote",
                           "my last message", "i emailed", "check your inbox",
                           "sent you a note earlier")
    if any(term in low for term in cross_channel_terms):
        fails.add("cross_channel")

    # Length checks
    if is_note:
        if len(text) > 300:
            fails.add("note_too_long")
        if len(text) < 40:
            fails.add("note_too_short")
    else:
        if len(text) > 1900:
            fails.add("message_too_long")
        if len(text) < 60:
            fails.add("message_too_short")

    return sorted(fails)


def check_claims(text, rec, contact):
    """Check if text passes claims gate."""
    problems = claims.check(text, rec, contact)
    return problems


def main():
    recs = load_snapshot()
    config = load_config()
    targets = find_target_records(recs)
    fallbacks = get_control_fallbacks(config)

    print(f"Loaded {len(recs)} records, found {len(targets)} targets")
    print(f"CONTROL fallbacks: {len(fallbacks)} roles")
    print()

    # Render the CONTROL fallbacks
    print("CONTROL fallbacks:")
    for role, text in sorted(fallbacks.items()):
        print(f"  {role}: {text[:60]}... ({len(text)} chars)")
    print()

    # Check lint for each fallback
    print("Lint check for CONTROL fallbacks:")
    all_lint_pass = True
    for role, text in sorted(fallbacks.items()):
        is_note = (role == "connection_note")
        fails = check_lint_linkedin(text, is_note=is_note)
        status = "PASS" if not fails else f"FAIL: {', '.join(fails)}"
        print(f"  {role}: {status}")
        if fails:
            all_lint_pass = False
    print()

    # Check claims for each target contact
    print("Claims check for CONTROL fallbacks per contact:")
    for domain, rec in sorted(targets.items()):
        print(f"\n  Record: {rec['id']} (domain: {domain})")
        for contact in rec.get("contacts") or []:
            if not contact.get("linkedin"):
                continue
            contact_key = contact.get("key")
            print(f"    Contact: {contact_key}")

            # Check each fallback
            all_claims_pass = True
            for role, text in sorted(fallbacks.items()):
                problems = check_claims(text, rec, contact)
                if problems:
                    all_claims_pass = False
                    print(f"      {role}: FAIL - {problems[0].get('why', 'unsupported')}")
                else:
                    print(f"      {role}: PASS")

            if all_claims_pass:
                print(f"    All CONTROL fallbacks pass claims for this contact")
            print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"CONTROL fallbacks lint: {'ALL PASS' if all_lint_pass else 'FAILURES DETECTED'}")
    print()
    print("The CONTROL fallbacks are generic, non-personalized messages.")
    print("They should pass lint (no em dashes, no banned phrases, etc.)")
    print("and claims (no unsupported assertions about the prospect).")
    print()
    print("If the CONTROL fallbacks pass both gates, then replacing the")
    print("generated copy for contacts 2 and 3 with CONTROL fallbacks")
    print("would make them staging-eligible (subject to approval).")


if __name__ == "__main__":
    main()
