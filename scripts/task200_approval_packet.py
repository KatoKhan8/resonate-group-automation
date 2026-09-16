#!/usr/bin/env python3
"""TASK-200: Generate the approval packet document.

Reads the queue snapshot and produces docs/APPROVAL-PACKET-2026-09-16.md:
one document an operator can read start to finish and approve or reject from,
without opening the repository.

No provider calls. No model calls. No generation. No approval field mutations.
"""
import hashlib
import json
import os
import sys
import textwrap

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import claims, lint

SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
OUTPUT = os.path.join(ROOT, "docs", "APPROVAL-PACKET-2026-09-16.md")

# Step ordering for display: email and LinkedIn interleaved by day
STEP_ORDER = ["em1", "li1", "em2", "li2", "em3", "li3", "em4", "li4",
              "em5", "li5", "em6", "li6",
              "day1", "day3", "day5", "day8", "day10", "day15", "day21"]

# Day mapping for step keys (from cadencelibrary.py sequences)
STEP_DAY_MAP = {
    # LinkedIn-heavy v1
    "li1": 1, "em1": 1, "li2": 3, "em2": 4, "li3": 6, "em3": 8,
    "li4": 10, "em4": 12, "li5": 15, "em5": 21,
    # Extended LinkedIn (li6 appears in some records)
    "li6": 18,
    # Balanced v1
    "day1": 1, "day3": 3, "day5": 5, "day8": 8, "day10": 10,
    "day15": 15, "day21": 21,
}


def _step_sort_key(step_key):
    try:
        return STEP_ORDER.index(step_key)
    except ValueError:
        return len(STEP_ORDER)


def hash_id(value):
    """Hash an identifier so no real PII appears in the packet."""
    if not value:
        return "(none)"
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def load_snapshot():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def find_contact(rec, key):
    for c in (rec.get("contacts") or []):
        if c.get("key") == key:
            return c
    return None


def lint_step(rec, contact_key, step):
    """Run lint on one step. Returns (failures_list, verdict_string)."""
    failures = lint.check_step(rec, contact_key, step)
    verdict = lint.classify(failures) if step.get("channel") == "email" \
        else classify_linkedin(failures)
    return failures, verdict


def classify_linkedin(failures):
    if not failures:
        return "clean"
    held = {"profile_missing"}
    if set(failures) <= held:
        return "held"
    return "failed"


def claims_check(step, rec, contact):
    """Run claims verification on one step. Returns list of problems."""
    return claims.verify(step, rec, contact)


def get_evidence_for_contact(rec, contact_key):
    """Evidence rows for a contact, from research field."""
    research = rec.get("research") or []
    contact_research = [r for r in research
                        if r.get("contact_key") == contact_key or not r.get("contact_key")]
    return contact_research


def detect_fallbacks(rec, contact, step):
    """Detect variable fallbacks and CONTROL text.

    Returns a list of flag strings.
    """
    flags = []

    # Template step = deterministic fallback text, not model-generated
    if step.get("template"):
        flags.append("TEMPLATE (deterministic fallback text, not model-generated)")

    # Contact-level fallbacks
    if contact:
        if not contact.get("persona"):
            flags.append("persona=None (angle chosen by default, not by role)")
        if not contact.get("angle"):
            flags.append("angle=None (no sales angle assigned)")

        # Check if first_name would fall back
        name = contact.get("name")
        if not name:
            flags.append("first_name fallback (no contact name, resolves to 'there')")

        # Check if company name would fall back to domain
        facts = rec.get("company_facts") or {}
        if not facts.get("name") and not rec.get("company"):
            flags.append("company fallback (no company name, resolves to domain)")

        # Check if sector/industry would fall back
        if not facts.get("industry"):
            flags.append("sector fallback (no industry, resolves to 'services')")

    # Check if evidence line would fall back
    evidence = rec.get("evidence") or {}
    contact_evidence = evidence.get(contact.get("key") if contact else "", [])
    if not contact_evidence:
        flags.append("evidence fallback (no evidence lines for line variable)")

    return flags


def compute_record_cost(rec, contact_key, steps_data):
    """Compute a cost score for ordering. Lower = cheaper to approve.

    - Each clean step: 0
    - Each template step: 1
    - Each step with lint failures: 3
    - Each step with claims problems: 2
    - Each fallback flag: 1
    - persona=None: 5
    """
    score = 0
    for sd in steps_data:
        if sd["lint_verdict"] == "failed":
            score += 3
        if sd["claims_problems"]:
            score += 2
        if sd["fallback_flags"]:
            score += len(sd["fallback_flags"])
        if "TEMPLATE" in " ".join(sd["fallback_flags"]):
            score += 1
    # persona=None penalty
    contact = find_contact(rec, contact_key)
    if contact and not contact.get("persona"):
        score += 5
    return score


def build_step_data(rec, contact_key, step_key, step):
    """Build the display data for one step."""
    contact = find_contact(rec, contact_key)
    channel = step.get("channel", "email")

    # Rendered copy
    if channel == "email":
        subject = step.get("subject", "")
        body = step.get("body", "")
        rendered = f"Subject: {subject}\n\n{body}" if subject else body
    else:
        note = step.get("note", "")
        body = step.get("body", "")
        rendered = note or body

    # Lint
    failures, verdict = lint_step(rec, contact_key, step)

    # Claims
    claims_problems = []
    if rendered.strip():
        claims_problems = claims_check(step, rec, contact)

    # Fallbacks
    fallback_flags = detect_fallbacks(rec, contact, step)

    # Approval status
    approval = step.get("approval")
    is_approved = approval is not None

    # Evidence
    evidence_rows = get_evidence_for_contact(rec, contact_key)

    # Day and requires
    day = step.get("day") or STEP_DAY_MAP.get(step_key, "?")
    requires = step.get("requires")

    return {
        "step_key": step_key,
        "channel": channel,
        "day": day,
        "requires": requires,
        "rendered": rendered,
        "lint_failures": failures,
        "lint_verdict": verdict,
        "claims_problems": claims_problems,
        "fallback_flags": fallback_flags,
        "is_approved": is_approved,
        "approval_by": approval.get("by") if approval else None,
        "approval_at": approval.get("at") if approval else None,
        "evidence_rows": evidence_rows,
        "is_generated": step.get("generated", False),
        "template_name": step.get("template"),
    }


def collect_record_data(rec):
    """Collect all step data for one record."""
    cadence = rec.get("cadence") or {}
    all_steps = []
    for contact_key, steps in cadence.items():
        contact = find_contact(rec, contact_key)
        contact_steps = []
        for step_key, step in steps.items():
            sd = build_step_data(rec, contact_key, step_key, step)
            contact_steps.append(sd)
        contact_steps.sort(key=lambda s: _step_sort_key(s["step_key"]))
        all_steps.append({
            "contact_key": contact_key,
            "contact": contact,
            "steps": contact_steps,
        })
    return all_steps


def band_for(record_steps):
    """Classify a record into an approval-cost band.

    Band 1: Every step passes both gates, no fallbacks, no templates.
    Band 2: Every step passes both gates, but has template or fallback flags.
    Band 3: Some steps have lint or claims failures.
    Band 4: All or most steps are template/fallback text.
    """
    total = 0
    clean = 0
    has_template = 0
    has_any_fallback = 0
    has_failure = 0

    for cs in record_steps:
        for sd in cs["steps"]:
            if sd["is_approved"]:
                continue
            total += 1
            lint_ok = sd["lint_verdict"] == "clean"
            claims_ok = not sd["claims_problems"]
            is_template = bool(sd["template_name"])
            has_fallbacks = bool(sd["fallback_flags"])

            if lint_ok and claims_ok and not is_template and not has_fallbacks:
                clean += 1
            if is_template:
                has_template += 1
            if has_fallbacks:
                has_any_fallback += 1
            if not lint_ok or not claims_ok:
                has_failure += 1

    if total == 0:
        return 4  # nothing to approve
    if has_failure > 0:
        return 3
    if clean == total:
        return 1
    if has_template > 0 or has_any_fallback > 0:
        return 2
    return 2


def format_evidence(evidence_rows, max_rows=5):
    """Format evidence rows for display."""
    if not evidence_rows:
        return "_No research evidence on this record._"
    lines = []
    for i, r in enumerate(evidence_rows[:max_rows]):
        if isinstance(r, dict):
            fact = str(r.get("fact", ""))[:120]
            url = r.get("source_url", "")
            retrieved = r.get("retrieved_at", "")
            lines.append(f"  {i+1}. {fact}")
            if url:
                lines.append(f"     Source: {url}")
            if retrieved:
                lines.append(f"     Retrieved: {retrieved}")
        else:
            lines.append(f"  {i+1}. {str(r)[:160]}")
    if len(evidence_rows) > max_rows:
        lines.append(f"  ... and {len(evidence_rows) - max_rows} more")
    return "\n".join(lines)


def format_step_for_packet(sd, rec_id, contact_key):
    """Format one step for the markdown packet."""
    lines = []
    status = "APPROVED" if sd["is_approved"] else "PENDING"
    approved_note = ""
    if sd["is_approved"]:
        approved_note = f" (approved by {sd['approval_by']} at {sd['approval_at']})"

    channel_icon = "[EMAIL]" if sd["channel"] == "email" else "[LI]"
    requires_note = f" [requires: {sd['requires']}]" if sd["requires"] else ""

    lines.append(f"#### {channel_icon} {sd['step_key']} -- Day {sd['day']}{requires_note} [{status}]{approved_note}")
    lines.append("")

    # Rendered copy
    lines.append("**As the prospect receives it:**")
    lines.append("")
    lines.append("```")
    lines.append(sd["rendered"])
    lines.append("```")
    lines.append("")

    # Gate verdicts - compact format
    lint_str = sd['lint_verdict']
    if sd["lint_failures"]:
        lint_str += f" ({', '.join(sd['lint_failures'])})"
    claims_str = "PASS" if not sd["claims_problems"] else "FAIL"
    lines.append(f"**Gates:** lint={lint_str}, claims={claims_str}")
    if sd["claims_problems"]:
        for p in sd["claims_problems"]:
            lines.append(f"  - \"{p['sentence']}\" -- {p['why']}")
    lines.append("")

    # Fallback flags
    if sd["fallback_flags"]:
        lines.append("**Flags:** " + " | ".join(sd["fallback_flags"]))
        lines.append("")

    return "\n".join(lines)


def generate_packet(records):
    """Generate the full approval packet markdown."""
    # Read the snapshot stamp
    stamp_path = os.path.join(ROOT, "work", "queue.snapshot.STAMP")
    stamp_info = ""
    if os.path.exists(stamp_path):
        with open(stamp_path, encoding="utf-8") as f:
            stamp_info = f.read().strip()

    # Filter to records with unapproved steps
    approvable = []
    for rec in records:
        if rec.get("state") not in ("drafted", "approved"):
            continue
        cadence = rec.get("cadence") or {}
        has_unapproved = False
        for ck, steps in cadence.items():
            for sk, sv in steps.items():
                if not sv.get("approval"):
                    has_unapproved = True
                    break
            if has_unapproved:
                break
        if has_unapproved:
            approvable.append(rec)

    # Collect data for each record
    record_data = []
    for rec in approvable:
        steps_data = collect_record_data(rec)
        band = band_for(steps_data)

        # Count unapproved steps
        unapproved = 0
        for cs in steps_data:
            for sd in cs["steps"]:
                if not sd["is_approved"]:
                    unapproved += 1

        record_data.append({
            "rec": rec,
            "steps_data": steps_data,
            "band": band,
            "unapproved": unapproved,
        })

    # Sort by band (cheapest first), then by unapproved count
    record_data.sort(key=lambda rd: (rd["band"], rd["unapproved"]))

    # Count bands
    band_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    total_unapproved = 0
    for rd in record_data:
        band_counts[rd["band"]] = band_counts.get(rd["band"], 0) + 1
        total_unapproved += rd["unapproved"]

    # Build the document
    doc = []
    doc.append("# Approval Packet -- 2026-09-16")
    doc.append("")
    if stamp_info:
        doc.append(f"_Generated from queue snapshot: {stamp_info}_")
        doc.append("")
    doc.append("## WARNING: This document contains unhashed prospect data in copy blocks")
    doc.append("")
    doc.append("The rendered copy below is what a prospect would receive. It may contain ")
    doc.append("company names, contact first names, and domain references as they appear ")
    doc.append("in the message. **Do not paste these sections anywhere public.**")
    doc.append("Record identifiers and contact keys are hashed throughout.")
    doc.append("")
    doc.append("---")
    doc.append("")
    doc.append("## Summary")
    doc.append("")
    doc.append(f"**Total records awaiting approval:** {len(record_data)}")
    doc.append(f"**Total unapproved steps:** {total_unapproved}")
    doc.append("")
    doc.append("### Records by approval-cost band")
    doc.append("")
    doc.append(f"| Band | Description | Count |")
    doc.append(f"|------|-------------|-------|")
    doc.append(f"| 1 | Every step passes both gates, no fallbacks, no templates | {band_counts.get(1, 0)} |")
    doc.append(f"| 2 | Every step passes both gates, but has template or fallback flags | {band_counts.get(2, 0)} |")
    doc.append(f"| 3 | Some steps have lint or claims failures | {band_counts.get(3, 0)} |")
    doc.append(f"| 4 | All or most steps are template/fallback text | {band_counts.get(4, 0)} |")
    doc.append("")
    doc.append("### Reading order")
    doc.append("")
    doc.append("Records are ordered cheapest-decision-first. Band 1 records have every step ")
    doc.append("passing both gates with no fallbacks -- these are the fastest yes. Band 4 ")
    doc.append("records are entirely template or fallback text -- these need the most attention.")
    doc.append("")
    doc.append("### What approving one record causes")
    doc.append("")
    doc.append("- **No campaign exists yet.** Campaigns have not been created for these records.")
    doc.append("- **Each record carries 11 steps** (em1–em5, li1–li6) across two channels.")
    doc.append("- **Cadence span:** Day 1 through Day 21 (three weeks).")
    doc.append("- **Sender:** Not yet assigned. The workspace sender configuration applies.")
    doc.append("- **Messages per contact:** Up to 11 touches (5 emails + 6 LinkedIn notes).")
    doc.append("")
    doc.append("---")
    doc.append("")

    # Render each record
    for idx, rd in enumerate(record_data, 1):
        rec = rd["rec"]
        rec_id_hashed = hash_id(rec["id"])
        domain_hashed = hash_id(rec.get("domain", ""))

        doc.append(f"## Record {idx}: `{rec_id_hashed}`")
        doc.append("")
        doc.append(f"- **Band:** {rd['band']}")
        doc.append(f"- **State:** {rec.get('state')}")
        doc.append(f"- **Client:** {rec.get('client')}")
        doc.append(f"- **Domain (hashed):** `{domain_hashed}`")
        doc.append(f"- **Lane:** {rec.get('lane')}")
        doc.append(f"- **Unapproved steps:** {rd['unapproved']}")
        doc.append("")

        for cs in rd["steps_data"]:
            contact = cs["contact"]
            ck_hashed = hash_id(cs["contact_key"])
            contact_name_hashed = hash_id(contact.get("name") if contact else "")

            doc.append(f"### Contact: `{ck_hashed}`")
            doc.append("")
            if contact:
                persona = contact.get("persona") or "None"
                angle = contact.get("angle") or "None"
                title = contact.get("title") or "Unknown"
                doc.append(f"- **Name (hashed):** `{contact_name_hashed}`")
                doc.append(f"- **Title:** {title}")
                doc.append(f"- **Persona:** {persona}")
                doc.append(f"- **Angle:** {angle}")
                if not contact.get("persona"):
                    doc.append(f"- **WARNING: persona=None** -- angle chosen by default, not by role")
            doc.append("")

            # Evidence for this contact (shown once, not per step)
            evidence_rows = get_evidence_for_contact(rec, cs["contact_key"])
            if evidence_rows:
                doc.append("**Research evidence for this contact:**")
                doc.append("")
                doc.append(format_evidence(evidence_rows, max_rows=8))
                doc.append("")

            for sd in cs["steps"]:
                if sd["is_approved"]:
                    # Show approved steps briefly
                    doc.append(f"#### [OK] {sd['step_key']} -- Day {sd['day']} [APPROVED]")
                    doc.append(f"  Approved by {sd['approval_by']} at {sd['approval_at']}")
                    doc.append("")
                    continue
                doc.append(format_step_for_packet(sd, rec_id_hashed, cs["contact_key"]))

        doc.append("---")
        doc.append("")

    return "\n".join(doc)


def main():
    records = load_snapshot()
    packet = generate_packet(records)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(packet)

    print(f"Approval packet written to {OUTPUT}")
    print(f"Total records: {len([r for r in records if r.get('state') in ('drafted', 'approved')])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
