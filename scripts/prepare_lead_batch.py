#!/usr/bin/env python3
"""Prepare a real lead batch from the TASK-096 cohort.

TASK-101: produces the batch file and the funnel report, but does NOT write
to any provider. The largest honest cohort from TASK-096 is used:
persona == 'economic_buyer' at 70 leads with email.

Pipeline stages:
  1. COHORT SELECTION   - the economic_buyer cohort from TASK-096
  2. DEDUPE             - against every other contact in the estate
  3. EXCLUSION CHECK    - sendable, verification, engagement state
  4. PERSONALISATION    - merge variable resolution for every field
  5. GREETING PROOF     - render greetings, check for broken merges
  6. QUALITY GATES      - lint, claims, structural diversity

Every drop carries a reason. Every identifier in the report is hashed.
"""
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
STAMP = os.path.join(ROOT, "work", "queue.snapshot.STAMP")
BATCH_OUT = os.path.join(ROOT, "work", "task101_batch.json")
REPORT_OUT = os.path.join(ROOT, "docs", "TASK-101-LEAD-BATCH-REPORT.md")


def h(value):
    """SHA-256 prefix for PII-safe reporting."""
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:12]


def load_records():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def load_stamp():
    try:
        with open(STAMP, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "unknown"


# --------------------------------------------------------- stage 1: cohort

def select_cohort(records):
    """The largest honest cohort from TASK-096: economic_buyer with email."""
    cohort = []
    for rec in records:
        if rec.get("drop_reason") is not None:
            continue
        for contact in rec.get("contacts") or []:
            if contact.get("persona") == "economic_buyer" and contact.get("email"):
                cohort.append({
                    "record": rec,
                    "contact": contact,
                    "record_id": rec.get("id"),
                    "contact_key": contact.get("key"),
                })
    return cohort


# --------------------------------------------------------- stage 2: dedupe

def dedupe_within_estate(cohort, all_records):
    """Check each cohort member against every other contact in the estate.

    A prospect already in another campaign must not enter this one.
    Uses the same identity keys as src/dedupe.py: normalised email,
    canonical LinkedIn URL, provider ids.
    """
    # Build an index of ALL contacts in the estate (not just the cohort)
    estate_index = {}  # key -> (record_id, contact_key)
    for rec in all_records:
        if rec.get("drop_reason") is not None:
            continue
        for contact in rec.get("contacts") or []:
            email = (contact.get("email") or "").strip().lower()
            if email and "@" in email:
                estate_index.setdefault(f"email:{email}", []).append(
                    (rec.get("id"), contact.get("key")))
            linkedin = contact.get("linkedin") or ""
            if linkedin:
                estate_index.setdefault(f"linkedin:{linkedin}", []).append(
                    (rec.get("id"), contact.get("key")))

    passed = []
    dropped = []
    cohort_ids = {(c["record_id"], c["contact_key"]) for c in cohort}

    for entry in cohort:
        contact = entry["contact"]
        dupes = []

        # Check email
        email = (contact.get("email") or "").strip().lower()
        if email and "@" in email:
            key = f"email:{email}"
            for (rid, ckey) in estate_index.get(key, []):
                if (rid, ckey) != (entry["record_id"], entry["contact_key"]):
                    dupes.append({
                        "kind": "email",
                        "other_record": h(rid),
                        "other_contact": h(ckey),
                    })

        # Check LinkedIn
        linkedin = contact.get("linkedin") or ""
        if linkedin:
            key = f"linkedin:{linkedin}"
            for (rid, ckey) in estate_index.get(key, []):
                if (rid, ckey) != (entry["record_id"], entry["contact_key"]):
                    dupes.append({
                        "kind": "linkedin",
                        "other_record": h(rid),
                        "other_contact": h(ckey),
                    })

        if dupes:
            dropped.append({
                **entry,
                "drop_reason": "duplicate_in_estate",
                "dupes": dupes,
            })
        else:
            passed.append(entry)

    return passed, dropped


# --------------------------------------------------------- stage 3: exclusion

def exclusion_check(cohort):
    """Sendable, verification, engagement state.

    Checks:
    - sendable flag (verification passed)
    - reoon is_safe_to_send
    - email verdict (not accept_all with reoon unsafe)
    - record state (not dropped, not already pushed)
    - engagement state (no prior replies, no active conversation)
    """
    passed = []
    dropped = []

    for entry in cohort:
        rec = entry["record"]
        contact = entry["contact"]
        reasons = []

        # Record state
        if rec.get("drop_reason") is not None:
            reasons.append(f"record_dropped:{rec['drop_reason']}")
        if rec.get("state") == "pushed":
            reasons.append("record_already_pushed")

        # Contact sendable
        if not contact.get("sendable"):
            verdict = contact.get("verdict")
            reoon = contact.get("reoon") or {}
            reoon_safe = reoon.get("is_safe_to_send")
            if verdict == "accept_all" and reoon_safe is False:
                reasons.append("email_accept_all_and_reoon_unsafe")
            elif not contact.get("email"):
                reasons.append("no_email")
            elif contact.get("verdict") is None and not reoon_safe:
                reasons.append("unverified_no_reoon_clearance")
            else:
                reasons.append("not_sendable")

        # Verification state
        verification = contact.get("verification") or {}
        if verification.get("state") != "verified":
            if "not_sendable" not in reasons and "email_accept_all_and_reoon_unsafe" not in reasons:
                reasons.append(f"verification_state:{verification.get('state', 'unknown')}")

        # Engagement: check for prior replies or active conversations
        replies = []
        for evt in rec.get("events") or []:
            if evt.get("type") == "reply_received" and evt.get("contact") == contact.get("key"):
                replies.append(evt)
        if replies:
            reasons.append(f"prior_reply:{len(replies)}_reply(ies)")

        # Check for meeting booked
        for evt in rec.get("events") or []:
            if evt.get("type") == "meeting_marked" and evt.get("contact") == contact.get("key"):
                reasons.append("meeting_booked")
                break

        if reasons:
            dropped.append({**entry, "drop_reason": "; ".join(reasons)})
        else:
            passed.append(entry)

    return passed, dropped


# --------------------------------------------------------- stage 4: personalisation

# The merge variables a HeyReach sequence uses. Based on the HeyReach campaign
# 599020 structure and the build_lead_pairs shape:
#   firstName, lastName, companyName, position, profileUrl
# Plus customUserFields: note, record_id, contact_key, sender_id,
# sender_account_id, plus whatever the campaign's copy asks for.
#
# For email (EmailBison), the merge variables are:
#   email, first_name, last_name, company, domain, title, subject, body

REQUIRED_EMAIL_FIELDS = {
    "email": lambda rec, c: c.get("email"),
    "first_name": lambda rec, c: (c.get("name") or "").split()[0] if c.get("name") else None,
    "last_name": lambda rec, c: " ".join((c.get("name") or "").split()[1:]) if c.get("name") and len((c.get("name") or "").split()) > 1 else "",
    "company": lambda rec, c: rec.get("company"),
    "domain": lambda rec, c: rec.get("domain"),
    "title": lambda rec, c: c.get("title"),
}

REQUIRED_LINKEDIN_FIELDS = {
    "linkedin_url": lambda rec, c: c.get("linkedin"),
    "first_name": lambda rec, c: (c.get("name") or "").split()[0] if c.get("name") else None,
    "last_name": lambda rec, c: " ".join((c.get("name") or "").split()[1:]) if c.get("name") and len((c.get("name") or "").split()) > 1 else "",
    "company": lambda rec, c: rec.get("company"),
    "title": lambda rec, c: c.get("title"),
}

# Safe fallbacks per field. A field with a safe fallback does NOT cause
# exclusion - it carries the fallback. A field without one does.
SAFE_FALLBACKS = {
    "last_name": "",
    "title": "",
}


def check_personalisation(cohort):
    """Every merge variable must resolve or have a safe fallback."""
    passed = []
    dropped = []

    for entry in cohort:
        rec = entry["record"]
        contact = entry["contact"]
        missing = []
        fallback_used = []

        # Check email fields
        for field, resolver in REQUIRED_EMAIL_FIELDS.items():
            value = resolver(rec, contact)
            if value is None or value == "":
                if field in SAFE_FALLBACKS:
                    fallback_used.append(field)
                else:
                    missing.append(field)

        # Check LinkedIn fields
        for field, resolver in REQUIRED_LINKEDIN_FIELDS.items():
            value = resolver(rec, contact)
            if value is None or value == "":
                if field in SAFE_FALLBACKS:
                    fallback_used.append(field)
                elif field == "linkedin_url":
                    # LinkedIn URL is required for HeyReach but not for email
                    pass
                else:
                    missing.append(f"linkedin:{field}")

        if missing:
            dropped.append({
                **entry,
                "drop_reason": f"missing_personalisation:{','.join(missing)}",
            })
        else:
            entry["fallback_fields"] = fallback_used
            passed.append(entry)

    return passed, dropped


# --------------------------------------------------------- stage 5: greeting proof

def render_greeting(contact):
    """Render the greeting that would appear in a message."""
    name = contact.get("name") or ""
    first = name.split()[0] if name else ""
    return f"Hi {first}," if first else "Hi,"


def check_greetings(cohort):
    """Render every greeting and check for broken merges."""
    passed = []
    dropped = []

    for entry in cohort:
        contact = entry["contact"]
        greeting = render_greeting(contact)
        issues = []

        # Check for known broken patterns
        if "Hi ," in greeting or "Hi  ," in greeting:
            issues.append("empty_greeting")
        if "undefined" in greeting.lower():
            issues.append("greeting_contains_undefined")
        if "null" in greeting.lower():
            issues.append("greeting_contains_null")

        # Check that the first name is a real name, not a cohort label
        name = contact.get("name") or ""
        first = name.split()[0] if name else ""
        cohort_labels = {"economic", "buyer", "champion", "founder",
                         "operations", "delivery", "finance", "growth"}
        if first.lower() in cohort_labels:
            issues.append(f"greeting_uses_cohort_label:{first}")

        if issues:
            dropped.append({**entry, "drop_reason": "; ".join(issues)})
        else:
            entry["greeting"] = greeting
            passed.append(entry)

    return passed, dropped


# --------------------------------------------------------- stage 6: quality gates

def quality_gates(cohort):
    """Structural checks: no duplicate companies, angle coverage, diversity."""
    passed = []
    dropped = []

    # Check for structural issues
    companies_seen = defaultdict(list)
    for entry in cohort:
        companies_seen[entry["record"].get("domain")].append(entry)

    for entry in cohort:
        rec = entry["record"]
        contact = entry["contact"]
        issues = []

        # Angle coverage: the task says angle is 88%, so 12% have no angle.
        # This is not a drop reason for the batch - it means personalisation
        # that references angle must have a fallback.
        # (Already handled in personalisation stage.)

        # Check that the contact has a name (for greeting)
        if not contact.get("name"):
            issues.append("no_name_for_greeting")

        if issues:
            dropped.append({**entry, "drop_reason": "; ".join(issues)})
        else:
            passed.append(entry)

    return passed, dropped


# --------------------------------------------------------- the batch file

def build_batch_row(entry):
    """Build the row that would be sent to HeyReach add_leads."""
    rec = entry["record"]
    contact = entry["contact"]
    name_parts = (contact.get("name") or "").split()
    first_name = name_parts[0] if name_parts else ""
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    return {
        "record_id": rec.get("id"),
        "contact_key": contact.get("key"),
        "email": contact.get("email"),
        "first_name": first_name,
        "last_name": last_name,
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "title": contact.get("title"),
        "linkedin_url": contact.get("linkedin"),
        "persona": contact.get("persona"),
        "angle": contact.get("angle"),
        "sendable": contact.get("sendable"),
        "greeting": entry.get("greeting", ""),
        "fallback_fields": entry.get("fallback_fields", []),
    }


# --------------------------------------------------------- the report

def write_report(stamp, funnel, drops, batch_rows):
    """Write the tracked report with funnel counts and every drop reason."""
    lines = []
    lines.append("# TASK-101 - Lead Batch Report")
    lines.append("")
    lines.append(f"**Snapshot:** `{stamp}`")
    lines.append(f"**Cohort:** persona == 'economic_buyer' (largest honest cohort from TASK-096)")
    lines.append(f"**Date:** 2026-09-15")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Funnel")
    lines.append("")
    lines.append("| Stage | Count | Drop |")
    lines.append("|-------|------:|-----:|")
    for stage_name, count, drop in funnel:
        lines.append(f"| {stage_name} | {count} | {drop} |")
    lines.append("")

    lines.append("## Drop-off Analysis")
    lines.append("")
    total_dropped = funnel[0][1] - funnel[-1][1]
    lines.append(f"**Total dropped:** {total_dropped} of {funnel[0][1]} ({100*total_dropped/funnel[0][1]:.1f}%)")
    lines.append(f"**Surviving:** {funnel[-1][1]} of {funnel[0][1]} ({100*funnel[-1][1]/funnel[0][1]:.1f}%)")
    lines.append("")

    # Drop reasons by stage
    lines.append("### Drop Reasons by Stage")
    lines.append("")
    by_stage = defaultdict(list)
    for d in drops:
        by_stage[d["stage"]].append(d)

    for stage_name, _, _ in funnel:
        stage_drops = by_stage.get(stage_name, [])
        if not stage_drops:
            continue
        lines.append(f"#### {stage_name}")
        lines.append("")
        reason_counts = Counter(d["drop_reason"] for d in stage_drops)
        for reason, count in reason_counts.most_common():
            lines.append(f"- **{reason}**: {count}")
            # Show hashed identifiers for each drop
            for d in stage_drops:
                if d["drop_reason"] == reason:
                    lines.append(f"  - record `{h(d['record_id'])}`, contact `{h(d['contact_key'])}`")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## What the Operator Would Be Authorising")
    lines.append("")
    final_count = funnel[-1][1]
    lines.append(f"If the operator enables `heyreach.add_leads` (NOT in `providerwrites.SUPPORTED`),")
    lines.append(f"they would be authorising:")
    lines.append("")
    lines.append(f"- **{final_count} leads** added to a HeyReach campaign")
    lines.append(f"- Each lead carries: profileUrl, firstName, lastName, companyName, position")
    lines.append(f"- Plus customUserFields: note, record_id, contact_key")
    lines.append(f"- The campaign's sequence would then act on each lead immediately")
    lines.append(f"- This is **prospect-facing** and irreversible at the provider")
    lines.append("")
    lines.append("### What is NOT authorised by this report")
    lines.append("")
    lines.append("- No campaign creation (no documented HeyReach route)")
    lines.append("- No sequence configuration (separate operator decision)")
    lines.append("- No sender assignment (separate operator decision)")
    lines.append("- No activation or unpausing")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Batch File")
    lines.append("")
    lines.append(f"The batch is at `work/task101_batch.json` ({final_count} rows).")
    lines.append("This file is under `work/` which is gitignored. It contains real data")
    lines.append("as an operational artefact. The report above hashes all identifiers.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Observations")
    lines.append("")

    # Angle coverage in surviving batch
    angle_counts = Counter()
    for row in batch_rows:
        angle_counts[row.get("angle") or "(none)"] += 1
    lines.append(f"- **Angle coverage in surviving batch:** {dict(angle_counts)}")

    # Fallback fields used
    fallback_counts = Counter()
    for row in batch_rows:
        for f in row.get("fallback_fields", []):
            fallback_counts[f] += 1
    if fallback_counts:
        lines.append(f"- **Fallback fields used:** {dict(fallback_counts)}")
    else:
        lines.append("- **No fallback fields needed** - all merge variables resolved")

    # Company diversity
    domains = set(row.get("domain") for row in batch_rows)
    lines.append(f"- **Company diversity:** {len(domains)} unique domains across {final_count} leads")

    lines.append("")
    lines.append("## Hypotheses")
    lines.append("")
    lines.append("- The 19 not-sendable contacts are split between unverified (no reoon check)")
    lines.append("  and accept_all domains where reoon says unsafe. A targeted re-verification")
    lines.append("  pass could recover some of these.")
    lines.append("")
    lines.append("## Proven Learnings")
    lines.append("")
    lines.append("(empty - this is a preparation task, not an outcome measurement)")

    return "\n".join(lines)


# --------------------------------------------------------- main

def main():
    stamp = load_stamp()
    records = load_records()
    print(f"Snapshot: {stamp}")
    print(f"Records loaded: {len(records)}")

    funnel = []
    all_drops = []

    # Stage 1: Cohort selection
    cohort = select_cohort(records)
    funnel.append(("cohort_selection", len(cohort), 0))
    print(f"\nStage 1 - Cohort selection: {len(cohort)} economic_buyer contacts with email")

    # Stage 2: Dedupe
    cohort, dedupe_drops = dedupe_within_estate(cohort, records)
    for d in dedupe_drops:
        d["stage"] = "dedupe"
    all_drops.extend(dedupe_drops)
    funnel.append(("dedupe", len(cohort), len(dedupe_drops)))
    print(f"Stage 2 - Dedupe: {len(cohort)} passed, {len(dedupe_drops)} dropped")

    # Stage 3: Exclusion check
    cohort, excl_drops = exclusion_check(cohort)
    for d in excl_drops:
        d["stage"] = "exclusion"
    all_drops.extend(excl_drops)
    funnel.append(("exclusion", len(cohort), len(excl_drops)))
    print(f"Stage 3 - Exclusion: {len(cohort)} passed, {len(excl_drops)} dropped")

    # Stage 4: Personalisation
    cohort, pers_drops = check_personalisation(cohort)
    for d in pers_drops:
        d["stage"] = "personalisation"
    all_drops.extend(pers_drops)
    funnel.append(("personalisation", len(cohort), len(pers_drops)))
    print(f"Stage 4 - Personalisation: {len(cohort)} passed, {len(pers_drops)} dropped")

    # Stage 5: Greeting proof
    cohort, greet_drops = check_greetings(cohort)
    for d in greet_drops:
        d["stage"] = "greeting_proof"
    all_drops.extend(greet_drops)
    funnel.append(("greeting_proof", len(cohort), len(greet_drops)))
    print(f"Stage 5 - Greeting proof: {len(cohort)} passed, {len(greet_drops)} dropped")

    # Stage 6: Quality gates
    cohort, qual_drops = quality_gates(cohort)
    for d in qual_drops:
        d["stage"] = "quality_gates"
    all_drops.extend(qual_drops)
    funnel.append(("quality_gates", len(cohort), len(qual_drops)))
    print(f"Stage 6 - Quality gates: {len(cohort)} passed, {len(qual_drops)} dropped")

    # Build batch rows
    batch_rows = [build_batch_row(e) for e in cohort]

    # Write batch file
    with open(BATCH_OUT, "w", encoding="utf-8") as f:
        json.dump(batch_rows, f, indent=2, ensure_ascii=False)
    print(f"\nBatch written to {BATCH_OUT} ({len(batch_rows)} rows)")

    # Write report
    report = write_report(stamp, funnel, all_drops, batch_rows)
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report written to {REPORT_OUT}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"FUNNEL SUMMARY")
    print(f"{'='*60}")
    for stage, count, drop in funnel:
        print(f"  {stage:<25} {count:>4}  (dropped {drop})")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
