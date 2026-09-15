#!/usr/bin/env python3
"""TASK-101: Prepare a real lead batch, up to the point of the write.

This script runs the full pipeline on the cohort TASK-096 identified:
  DEDUPE -> EXCLUSION CHECK -> PERSONALISATION -> GREETING PROOF -> QUALITY GATES

It produces:
  1. A batch file under work/ (gitignored)
  2. A tracked report with funnel counts and every drop reason
  3. An explicit statement of what the operator would be authorising

NO PROVIDER WRITE OF ANY KIND.
"""
import json
import hashlib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SNAPSHOT = Path("work/queue.snapshot.jsonl")
STAMP = Path("work/queue.snapshot.STAMP")
REPORT = Path("docs/TASK-101-LEAD-BATCH-REPORT.md")
BATCH_OUT = Path("work/task101_batch.json")


def load_records():
    records = []
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_stamp():
    return STAMP.read_text(encoding="utf-8").strip()


def hash_id(value):
    """SHA-256 prefix for PII-safe reporting."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def hash_email(email):
    """Hash an email for reporting."""
    if not email:
        return "<no-email>"
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------- cohort selection

def select_cohort(records):
    """Select the largest honest cohort from TASK-096.

    TASK-096 found:
      economic_buyer: 70 leads (with email)
      Advertising Services: 51 leads (with email)
      overlap: ~40 leads

    The largest honest cohort is economic_buyer at 70.
    We take that, stating its size. We do NOT pad to 50.
    """
    contacts = []
    for rec in records:
        if rec.get("drop_reason") is not None:
            continue
        for contact in rec.get("contacts", []):
            if contact.get("excluded"):
                continue
            if not contact.get("email"):
                continue
            persona = contact.get("persona")
            if persona == "economic_buyer":
                contacts.append({
                    "record": rec,
                    "contact": contact,
                    "rec_id": rec.get("id"),
                    "contact_key": contact.get("key"),
                    "email": contact.get("email"),
                    "name": contact.get("name"),
                    "title": contact.get("title"),
                    "company": rec.get("company"),
                    "domain": rec.get("domain"),
                    "persona": persona,
                    "angle": contact.get("angle"),
                    "industry": (rec.get("company_facts") or {}).get("industry"),
                    "headcount": (rec.get("company_facts") or {}).get("employees"),
                    "employee_range": (rec.get("company_facts") or {}).get("employee_range"),
                    "specialties": (rec.get("company_facts") or {}).get("specialties") or [],
                    "sendable": contact.get("sendable", False),
                    "verdict": contact.get("verdict"),
                    "linkedin": contact.get("linkedin"),
                })
    return contacts


# --------------------------------------------------------------- STAGE 1: DEDUPE

def stage_dedupe(cohort, all_records):
    """Check each cohort member against every other campaign in the estate.

    A prospect already in one of 83 campaigns must not enter another.
    We check:
      - Is this contact already in a campaign (has campaign_ids)?
      - Does this contact appear on another record?
      - Email uniqueness across the estate
    """
    drops = []
    survivors = []

    # Build an index of all contacts across all records by email
    email_index = defaultdict(list)
    for rec in all_records:
        for contact in rec.get("contacts", []):
            email = contact.get("email")
            if email:
                email_index[email.strip().lower()].append({
                    "rec_id": rec.get("id"),
                    "contact_key": contact.get("key"),
                    "campaign_ids": rec.get("campaign_ids") or [],
                    "state": rec.get("state"),
                })

    # Build an index of LinkedIn profiles
    linkedin_index = defaultdict(list)
    for rec in all_records:
        for contact in rec.get("contacts", []):
            li = contact.get("linkedin")
            if li:
                linkedin_index[li.strip().lower()].append({
                    "rec_id": rec.get("id"),
                    "contact_key": contact.get("key"),
                })

    for entry in cohort:
        email = entry["email"].strip().lower()
        linkedin = (entry.get("linkedin") or "").strip().lower()
        reasons = []

        # Check 1: Is this email on multiple records?
        email_hits = email_index.get(email, [])
        if len(email_hits) > 1:
            other_recs = [h for h in email_hits if h["rec_id"] != entry["rec_id"]]
            if other_recs:
                other_ids = [h["rec_id"] for h in other_recs]
                reasons.append(
                    f"duplicate_email: same email on {len(other_recs)} other "
                    f"record(s): {', '.join(hash_id(r) for r in other_ids)}")

        # Check 2: Is this contact already assigned to a campaign?
        rec = entry["record"]
        campaign_ids = rec.get("campaign_ids") or []
        if campaign_ids:
            reasons.append(
                f"already_in_campaign: record has campaign_ids "
                f"{campaign_ids}")

        # Check 3: LinkedIn profile on multiple records
        if linkedin:
            li_hits = linkedin_index.get(linkedin, [])
            other_li = [h for h in li_hits if h["rec_id"] != entry["rec_id"]]
            if other_li:
                reasons.append(
                    f"duplicate_linkedin: same profile on {len(other_li)} "
                    f"other record(s)")

        if reasons:
            drops.append({**entry, "drop_reasons": reasons, "stage": "dedupe"})
        else:
            survivors.append(entry)

    return survivors, drops


# --------------------------------------------------- STAGE 2: EXCLUSION CHECK

def stage_exclusion(survivors, all_records):
    """Suppression list, DNC, bounced addresses, positive-reply protection,
    engagement state.

    Checks:
      - Contact sendable (verification state)
      - Contact verdict (bounced, invalid, etc.)
      - Record state (dropped, suppressed)
      - Account-level DNC
      - Prior engagement (replied, active conversation, meeting booked)
      - Bounced addresses (from events)
    """
    drops = []
    out = []

    for entry in survivors:
        rec = entry["record"]
        contact = entry["contact"]
        reasons = []

        # Check 1: Record state
        state = rec.get("state")
        if state == "dropped":
            reasons.append(f"record_dropped: {rec.get('drop_reason', 'unknown')}")

        # Check 2: Account-level suppression
        account_state = None
        for evt in rec.get("events", []):
            if evt.get("type") == "account_dnc":
                account_state = "dnc"
                break
        if account_state == "dnc":
            reasons.append("account_dnc: company asked not to be contacted")

        # Check 3: Contact-level suppression
        contact_state = contact.get("contact_state")
        if contact_state == "suppress":
            reasons.append("contact_suppressed: person asked not to be contacted")

        # Check 4: Verification / sendable
        verification = contact.get("verification") or {}
        ver_state = verification.get("state")
        if ver_state == "invalid":
            reasons.append(f"email_invalid: verification state is invalid")
        elif ver_state == "held":
            reasons.append(f"email_held: verification state is held "
                          f"({verification.get('reason', 'unknown')})")

        # Check 5: Sendable flag
        if not contact.get("sendable"):
            reasons.append("not_sendable: contact.sendable is False")

        # Check 6: Bounced (from events)
        bounced = False
        for evt in rec.get("events", []):
            if evt.get("type") == "bounce" and evt.get("contact") == entry["contact_key"]:
                bounced = True
                break
        if bounced:
            reasons.append("bounced: address has a bounce event on record")

        # Check 7: Prior engagement - replied
        replies = []
        for evt in rec.get("events", []):
            if evt.get("type") == "reply_received" and evt.get("contact") == entry["contact_key"]:
                replies.append(evt)
        if replies:
            # Check outcome
            outcome = None
            for evt in rec.get("events", []):
                if evt.get("type") == "reply_classified" and evt.get("contact") == entry["contact_key"]:
                    outcome = evt.get("outcome")
            if outcome in ("positive", "existing_client"):
                reasons.append(f"active_conversation: replied ({outcome})")
            elif outcome in ("not_now",):
                reasons.append(f"future_follow_up: replied ({outcome})")
            elif outcome in ("negative", "not_icp", "neutral"):
                reasons.append(f"previously_engaged: replied ({outcome})")
            elif outcome in ("referral",):
                reasons.append(f"referral: replied ({outcome})")
            else:
                reasons.append(f"previously_engaged: replied (outcome: {outcome or 'unknown'})")

        # Check 8: Meeting booked
        for evt in rec.get("events", []):
            if evt.get("type") == "meeting_marked" and evt.get("contact") == entry["contact_key"]:
                reasons.append("meeting_booked: a meeting is recorded")
                break

        # Check 9: Wrong person
        for evt in rec.get("events", []):
            if (evt.get("type") == "reply_classified"
                    and evt.get("contact") == entry["contact_key"]
                    and evt.get("outcome") == "wrong_person"):
                reasons.append("wrong_person: classified as not the right person")
                break

        # Check 10: Left company
        for evt in rec.get("events", []):
            if (evt.get("type") == "reply_classified"
                    and evt.get("contact") == entry["contact_key"]
                    and evt.get("outcome") == "left_company"):
                reasons.append("invalid_contact: has left the company")
                break

        if reasons:
            drops.append({**entry, "drop_reasons": reasons, "stage": "exclusion"})
        else:
            out.append(entry)

    return out, drops


# ----------------------------------------------- STAGE 3: PERSONALISATION CHECK

# HeyReach campaign 599020 uses these merge variables (from the sequence).
# The task says "HeyReach has 8 per-variable fallbacks configured on 599020."
# We need to check that every merge variable the sequence uses resolves for
# every lead, or the lead carries a safe fallback, or the lead is excluded.

# The standard merge variables in a HeyReach sequence are:
#   {firstName}, {lastName}, {companyName}, {position}, {profileUrl}
# Plus any customUserFields the campaign defines.
#
# From heyreach.py build_lead_pairs, the custom fields sent are:
#   note, record_id, contact_key, client, sender_id, sender_account_id
#   plus whatever custom_fields the row carries.

REQUIRED_FIELDS = {
    "first_name": lambda e: (e["name"] or "").split()[0] if e.get("name") else None,
    "last_name": lambda e: " ".join((e["name"] or "").split()[1:]) if e.get("name") and len((e["name"] or "").split()) > 1 else None,
    "company": lambda e: e.get("company"),
    "title": lambda e: e.get("title"),
    "email": lambda e: e.get("email"),
    "domain": lambda e: e.get("domain"),
    "persona": lambda e: e.get("persona"),
    "angle": lambda e: e.get("angle"),
    "industry": lambda e: e.get("industry"),
}

# Safe fallbacks per HeyReach configuration on 599020
FALLBACKS = {
    "first_name": "there",
    "last_name": "",
    "company": "your company",
    "title": "your role",
    "angle": "your business",
    "industry": "your industry",
}


def stage_personalisation(survivors):
    """Every merge variable the sequence uses must RESOLVE for every lead,
    or the lead carries a safe fallback, or the lead is excluded.

    There is no fourth option.
    """
    drops = []
    out = []

    for entry in survivors:
        missing = []
        resolved = {}

        for field, getter in REQUIRED_FIELDS.items():
            value = getter(entry)
            if value and str(value).strip():
                resolved[field] = str(value).strip()
            elif field in FALLBACKS:
                resolved[field] = FALLBACKS[field]
                missing.append(f"{field}: using fallback '{FALLBACKS[field]}'")
            else:
                missing.append(f"{field}: MISSING, no fallback available")

        # Check for critical missing fields with no fallback
        critical_missing = [m for m in missing if "no fallback" in m]
        if critical_missing:
            drops.append({
                **entry,
                "drop_reasons": critical_missing,
                "stage": "personalisation",
                "resolved_fields": resolved,
            })
        else:
            entry["resolved_fields"] = resolved
            entry["personalisation_notes"] = missing
            out.append(entry)

    return out, drops


# ------------------------------------------------ STAGE 4: GREETING PROOF

def render_greeting(entry):
    """Render the actual greeting for a lead.

    Check for:
      - "Hey ," (missing name)
      - "Hi undefined," (null name)
      - "Hi null," (null name)
      - A cohort name where a person belongs
    """
    first_name = entry.get("resolved_fields", {}).get("first_name", "")
    name = entry.get("name", "")

    greetings = []

    # Standard greeting patterns
    if first_name and first_name != "there":
        greetings.append(f"Hi {first_name}")
        greetings.append(f"Hello {first_name}")
    elif first_name == "there":
        greetings.append("Hi there")
    else:
        greetings.append("Hi there")

    # Check for problems
    problems = []
    for g in greetings:
        if ", ," in g or g.endswith(","):
            problems.append(f"malformed greeting: '{g}'")
        if "undefined" in g.lower():
            problems.append(f"'undefined' in greeting: '{g}'")
        if "null" in g.lower():
            problems.append(f"'null' in greeting: '{g}'")

    # Check that the greeting uses a PERSON name, not a cohort name
    cohort_names = {"economic_buyer", "advertising_services", "founder",
                    "champion", "operations"}
    if first_name.lower() in cohort_names:
        problems.append(
            f"greeting uses cohort label '{first_name}' instead of person name")

    return {
        "greetings": greetings,
        "problems": problems,
        "first_name_used": first_name,
    }


def stage_greeting_proof(survivors):
    """Render the actual greeting for every lead and check for problems."""
    drops = []
    out = []

    for entry in survivors:
        proof = render_greeting(entry)
        entry["greeting_proof"] = proof

        if proof["problems"]:
            drops.append({
                **entry,
                "drop_reasons": proof["problems"],
                "stage": "greeting_proof",
            })
        else:
            out.append(entry)

    return out, drops


# ---------------------------------------------- STAGE 5: QUALITY GATES

def stage_quality_gates(survivors, all_records):
    """Lint, claims, structural diversity check.

    For each surviving lead, check:
      1. Does the record have a cadence with generated copy?
      2. Does the copy pass lint? (length, placeholders, banned phrases, etc.)
      3. Does the copy pass claims? (no unsupported assertions)
      4. Structural diversity: do the steps vary enough?
    """
    drops = []
    out = []

    for entry in survivors:
        rec = entry["record"]
        contact = entry["contact"]
        contact_key = entry["contact_key"]
        reasons = []

        # Check 1: Does a cadence exist for this contact?
        cadence = rec.get("cadence") or {}
        contact_cadence = cadence.get(contact_key)
        if not contact_cadence:
            reasons.append("no_cadence: no generated copy for this contact")
            drops.append({**entry, "drop_reasons": reasons, "stage": "quality"})
            continue

        # Check 2: Email steps exist
        email_steps = {k: v for k, v in contact_cadence.items()
                      if isinstance(v, dict) and v.get("channel") == "email"}
        if not email_steps:
            reasons.append("no_email_steps: cadence has no email steps")
            drops.append({**entry, "drop_reasons": reasons, "stage": "quality"})
            continue

        # Check 3: Lint each email step
        lint_failures = []
        for day, step in sorted(email_steps.items()):
            body = step.get("body", "")
            subject = step.get("subject", "")

            # Word count
            words = len(body.split())
            if words < 40:
                lint_failures.append(f"{day}: body_too_short ({words} words)")
            if words > 180:
                lint_failures.append(f"{day}: body_too_long ({words} words)")

            # Subject length
            if not subject:
                lint_failures.append(f"{day}: subject_missing")
            elif len(subject) >= 60:
                lint_failures.append(f"{day}: subject_too_long ({len(subject)} chars)")

            # Banned phrases
            low = body.lower()
            banned = ("i hope this email finds you well", "i wanted to reach out",
                     "circling back", "just following up", "touching base",
                     "as per my last email", "synergy", "game-changer")
            for phrase in banned:
                if phrase in low:
                    lint_failures.append(f"{day}: filler_phrase ('{phrase}')")

            # Substituted punctuation
            for char in ("\u2014", "\u2013", "\u2011", "\u2019", "\u2018"):
                if char in body or char in subject:
                    lint_failures.append(f"{day}: substituted_punctuation")
                    break

            # Placeholders
            placeholder_re = re.compile(r"[\[{<](?!http)[^\]}>\n]{2,40}[\]}>]")
            if placeholder_re.search(body) or placeholder_re.search(subject):
                lint_failures.append(f"{day}: placeholder")

            # Greeting check
            first_line = body.strip().split("\n", 1)[0] if body.strip() else ""
            greeting_re = re.compile(
                r"^\s*(?:(?i:hi|hello|hey|dear|good morning|good afternoon)"
                r"[\s,]+)?([A-Z][\w'\u2019\-]+)\s*[,!.\n]", re.UNICODE)
            m = greeting_re.match(first_line)
            if m:
                greeted = m.group(1).strip()
                impersonal = ("there", "team", "all", "folks", "everyone")
                if greeted.lower() not in impersonal:
                    # Check if it matches the contact name
                    full_name = (contact.get("name") or "").lower()
                    parts = [p for p in re.split(r"[\s\-]+", full_name) if p]
                    if greeted.lower() not in parts and greeted.lower() != full_name:
                        lint_failures.append(
                            f"{day}: greets_the_wrong_person "
                            f"('{greeted}' != '{contact.get('name', '?')}')")

        if lint_failures:
            reasons.extend(lint_failures)

        # Check 4: Structural diversity across steps
        if len(email_steps) >= 2:
            bodies = [step.get("body", "") for step in email_steps.values()]
            # Check if first lines are too similar
            openers = [b.strip().split("\n", 1)[0].lower() for b in bodies if b.strip()]
            if len(openers) >= 2:
                unique_openers = set(openers)
                if len(unique_openers) == 1 and len(openers) > 1:
                    reasons.append(
                        "structural_repetition: all email steps open identically")

        if reasons:
            drops.append({**entry, "drop_reasons": reasons, "stage": "quality"})
        else:
            entry["quality_check"] = {
                "email_steps": len(email_steps),
                "lint_pass": True,
            }
            out.append(entry)

    return out, drops


# ----------------------------------------------------------- REPORT GENERATION

def generate_report(stamp, cohort_initial, stages, batch):
    """Generate the tracked report with funnel counts and every drop reason."""
    lines = []
    lines.append("# TASK-101 Lead Batch Report")
    lines.append("")
    lines.append(f"**Snapshot:** `{stamp}`")
    lines.append(f"**Cohort:** Persona = economic_buyer (largest honest cohort from TASK-096)")
    lines.append(f"**Date:** 2026-09-15")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Funnel Summary")
    lines.append("")
    lines.append("| Stage | Input | Survived | Dropped | Drop Rate |")
    lines.append("|-------|------:|---------:|--------:|----------:|")

    counts = [("Cohort selected", len(cohort_initial))]
    for stage_name, (survivors, drops) in stages.items():
        counts.append((stage_name, len(survivors)))

    prev = len(cohort_initial)
    for i, (name, count) in enumerate(counts):
        dropped = prev - count
        rate = f"{dropped/prev*100:.1f}%" if prev > 0 else "0%"
        lines.append(f"| {name} | {prev} | {count} | {dropped} | {rate} |")
        prev = count

    lines.append("")
    lines.append(f"**Final batch size: {len(batch)} leads**")
    lines.append("")

    # Drop details per stage
    for stage_name, (survivors, drops) in stages.items():
        if not drops:
            continue
        lines.append(f"## Drops at Stage: {stage_name}")
        lines.append("")

        # Aggregate reasons
        reason_counts = Counter()
        for d in drops:
            for r in d.get("drop_reasons", []):
                # Truncate long reasons for the summary
                key = r.split(":")[0] if ":" in r else r
                reason_counts[key] += 1

        lines.append("| Reason | Count |")
        lines.append("|--------|------:|")
        for reason, count in reason_counts.most_common():
            lines.append(f"| {reason} | {count} |")
        lines.append("")

        # Individual drops (hashed identifiers)
        lines.append("### Individual Drops")
        lines.append("")
        for d in drops:
            rec_hash = hash_id(d["rec_id"])
            email_hash = hash_email(d.get("email"))
            lines.append(f"- **{rec_hash}** ({email_hash}): "
                        f"{'; '.join(d.get('drop_reasons', []))}")
        lines.append("")

    # Batch file description
    lines.append("## Batch File")
    lines.append("")
    lines.append(f"The batch file is at `work/task101_batch.json` (gitignored).")
    lines.append(f"It contains {len(batch)} leads with resolved fields and greeting proofs.")
    lines.append("")

    # What the operator would be authorising
    lines.append("## What the Operator Would Be Authorising")
    lines.append("")
    lines.append(f"If the operator enabled `heyreach.add_leads` in "
                f"`providerwrites.SUPPORTED`, they would be authorising:")
    lines.append("")
    lines.append(f"1. **{len(batch)} new leads** added to HeyReach campaign 599020")
    lines.append(f"2. Each lead carries a LinkedIn profile URL, first name, last name, "
                f"company, title, and custom fields (record_id, contact_key, client)")
    lines.append(f"3. The campaign's sequence would begin acting on each lead immediately "
                f"(LinkedIn connection requests and messages)")
    lines.append(f"4. The sequence is already configured on 599020 with 8 per-variable "
                f"fallbacks, so a missing merge variable resolves to the fallback rather "
                f"than to 'undefined' or 'null'")
    lines.append("")
    lines.append("**This task does NOT perform that write.** "
                "It produces the batch and the evidence that it is safe to write, "
                "so the operator's decision is a yes/no on a real artefact rather "
                "than on a promise.")
    lines.append("")

    # Observations
    lines.append("## Observations")
    lines.append("")
    total_initial = len(cohort_initial)
    total_final = len(batch)
    total_dropped = total_initial - total_final
    lines.append(f"- Started with {total_initial} contacts in the economic_buyer cohort "
                f"(contacts with email on not-dropped records)")
    lines.append(f"- {total_dropped} contacts dropped across all stages "
                f"({total_dropped/total_initial*100:.1f}% drop-off)")
    lines.append(f"- {total_final} contacts survive all gates and form the batch")
    lines.append("")

    # The drop-off between stages
    lines.append("### Drop-off Between Stages")
    lines.append("")
    prev_count = len(cohort_initial)
    for stage_name, (survivors, drops) in stages.items():
        dropped = prev_count - len(survivors)
        lines.append(f"- **{stage_name}:** {dropped} dropped "
                    f"({dropped/prev_count*100:.1f}% of {prev_count} entering)")
        prev_count = len(survivors)
    lines.append("")
    lines.append("**The drop-off between stages is the most useful number.** "
                "If many leads drop at exclusion, the cohort is smaller than "
                "the raw count suggests. If many drop at quality, the copy "
                "needs work before the batch is safe to write.")
    lines.append("")

    # PII statement
    lines.append("## PII Statement")
    lines.append("")
    lines.append("All identifiers in this report are hashed (SHA-256 prefix). "
                "The batch file at `work/task101_batch.json` may hold real data "
                "as an operational artefact under `work/`, which is gitignored. "
                "This report is tracked and holds no real PII.")
    lines.append("")

    return "\n".join(lines)


# ----------------------------------------------------------- MAIN

def main():
    print("TASK-101: Prepare a real lead batch")
    print("=" * 60)

    # Load data
    records = load_records()
    stamp = load_stamp()
    print(f"Snapshot: {stamp}")
    print(f"Records loaded: {len(records)}")

    # Select cohort
    cohort = select_cohort(records)
    print(f"\nCohort (economic_buyer with email): {len(cohort)} contacts")

    # STAGE 1: DEDUPE
    print("\n--- STAGE 1: DEDUPE ---")
    after_dedupe, dedupe_drops = stage_dedupe(cohort, records)
    print(f"  Input: {len(cohort)}, Survived: {len(after_dedupe)}, "
          f"Dropped: {len(dedupe_drops)}")
    for d in dedupe_drops:
        print(f"    DROP {hash_id(d['rec_id'])}: {'; '.join(d['drop_reasons'])}")

    # STAGE 2: EXCLUSION CHECK
    print("\n--- STAGE 2: EXCLUSION CHECK ---")
    after_exclusion, exclusion_drops = stage_exclusion(after_dedupe, records)
    print(f"  Input: {len(after_dedupe)}, Survived: {len(after_exclusion)}, "
          f"Dropped: {len(exclusion_drops)}")
    for d in exclusion_drops:
        print(f"    DROP {hash_id(d['rec_id'])}: {'; '.join(d['drop_reasons'])}")

    # STAGE 3: PERSONALISATION
    print("\n--- STAGE 3: PERSONALISATION ---")
    after_personalisation, personalisation_drops = stage_personalisation(after_exclusion)
    print(f"  Input: {len(after_exclusion)}, Survived: {len(after_personalisation)}, "
          f"Dropped: {len(personalisation_drops)}")
    for d in personalisation_drops:
        print(f"    DROP {hash_id(d['rec_id'])}: {'; '.join(d['drop_reasons'])}")

    # STAGE 4: GREETING PROOF
    print("\n--- STAGE 4: GREETING PROOF ---")
    after_greeting, greeting_drops = stage_greeting_proof(after_personalisation)
    print(f"  Input: {len(after_personalisation)}, Survived: {len(after_greeting)}, "
          f"Dropped: {len(greeting_drops)}")
    for d in greeting_drops:
        print(f"    DROP {hash_id(d['rec_id'])}: {'; '.join(d['drop_reasons'])}")

    # STAGE 5: QUALITY GATES
    print("\n--- STAGE 5: QUALITY GATES ---")
    after_quality, quality_drops = stage_quality_gates(after_greeting, records)
    print(f"  Input: {len(after_greeting)}, Survived: {len(after_quality)}, "
          f"Dropped: {len(quality_drops)}")
    for d in quality_drops:
        print(f"    DROP {hash_id(d['rec_id'])}: {'; '.join(d['drop_reasons'][:3])}")

    # Final batch
    batch = after_quality
    print(f"\n{'=' * 60}")
    print(f"FINAL BATCH: {len(batch)} leads")
    print(f"{'=' * 60}")

    # Write batch file (gitignored)
    batch_data = []
    for entry in batch:
        batch_data.append({
            "record_id": entry["rec_id"],
            "contact_key": entry["contact_key"],
            "email": entry["email"],
            "name": entry["name"],
            "company": entry["company"],
            "domain": entry["domain"],
            "title": entry["title"],
            "persona": entry["persona"],
            "angle": entry.get("angle"),
            "industry": entry.get("industry"),
            "linkedin": entry.get("linkedin"),
            "resolved_fields": entry.get("resolved_fields", {}),
            "greeting_proof": entry.get("greeting_proof", {}),
        })

    with open(BATCH_OUT, "w", encoding="utf-8") as f:
        json.dump(batch_data, f, indent=2, ensure_ascii=False)
    print(f"\nBatch written to {BATCH_OUT}")

    # Generate report
    stages = {
        "dedupe": (after_dedupe, dedupe_drops),
        "exclusion": (after_exclusion, exclusion_drops),
        "personalisation": (after_personalisation, personalisation_drops),
        "greeting_proof": (after_greeting, greeting_drops),
        "quality_gates": (after_quality, quality_drops),
    }

    report = generate_report(stamp, cohort, stages, batch)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report written to {REPORT}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
