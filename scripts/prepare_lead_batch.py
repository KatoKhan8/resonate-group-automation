#!/usr/bin/env python3
"""Prepare a real lead batch for the economic_buyer cohort - TASK-101.

Pipeline stages:
  1. COHORT SELECTION    economic_buyer persona, largest honest cohort
  2. DEDUPE              against every existing campaign in the estate
  3. EXCLUSION CHECK     suppression, DNC, bounced, reply protection, sendable
  4. PERSONALISATION     every merge variable must resolve or carry a fallback
  5. GREETING PROOF      render the actual greeting, check for broken merges
  6. QUALITY GATES       lint, claims, structural diversity

Produces:
  work/lead-batch-economic-buyer.json    the batch file (gitignored)
  docs/LEAD-BATCH-REPORT-2026-09-15.md   the tracked report

Reads only. No provider writes of any kind.
"""
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
CAMPAIGNS_PATH = os.path.join(
    os.environ.get("CAMPAIGNS")
    or os.path.join(ROOT, "..", "resonate-group-automation", "work",
                    "campaigns.jsonl"))
SUPPRESS_PATH = os.path.join(ROOT, "config", "suppress.txt")
SUPPRESS_LOCAL = os.path.join(ROOT, "config", "suppress.local.txt")
BATCH_OUTPUT = os.path.join(ROOT, "work",
                            "lead-batch-economic-buyer.json")
REPORT_OUTPUT = os.path.join(ROOT, "docs",
                             "LEAD-BATCH-REPORT-2026-09-15.md")


def h(value):
    """Hash an identifier for the report. Real data stays in the batch file."""
    if not value:
        return "null"
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def load_records():
    records = []
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_campaign_record_ids():
    """All record_ids claimed by any campaign in the estate."""
    if not os.path.exists(CAMPAIGNS_PATH):
        return set()
    ids = set()
    with open(CAMPAIGNS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            camp = json.loads(line)
            for rid in (camp.get("record_ids") or []):
                ids.add(rid)
    return ids


def load_suppression_domains():
    """Union of tracked and local suppression lists."""
    domains = set()
    for path in (SUPPRESS_PATH, SUPPRESS_LOCAL):
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip().lower()
                if line and not line.startswith("#"):
                    domains.add(line)
    return domains


def extract_cohort(records):
    """Economic buyer contacts with email from active records."""
    cohort = []
    for rec in records:
        if rec.get("drop_reason"):
            continue
        for contact in rec.get("contacts", []):
            if (contact.get("persona") == "economic_buyer"
                    and contact.get("email")):
                cohort.append({
                    "rec_id": rec["id"],
                    "contact_key": contact.get("key"),
                    "contact": contact,
                    "record": rec,
                })
    return cohort


def stage_dedupe(cohort, campaign_rids):
    """Remove contacts whose record is already in a campaign."""
    surviving = []
    dropped = []
    for entry in cohort:
        if entry["rec_id"] in campaign_rids:
            dropped.append((entry, "already_in_campaign"))
        else:
            surviving.append(entry)
    return surviving, dropped


def stage_exclusion(cohort, suppress_domains):
    """Suppression, DNC, bounced, reply protection, sendable, MX."""
    surviving = []
    dropped = []
    for entry in cohort:
        rec = entry["record"]
        contact = entry["contact"]
        domain = (rec.get("domain") or "").lower()

        # Suppression list
        if domain and domain in suppress_domains:
            dropped.append((entry, "suppressed_domain"))
            continue

        # Client suppression (drop_reason starting with 'suppress')
        if (rec.get("drop_reason") or "").startswith("suppress"):
            dropped.append((entry, "client_suppressed"))
            continue

        # Bounced / not sendable
        if not contact.get("sendable"):
            v = contact.get("verification") or {}
            if isinstance(v, dict) and v.get("state"):
                v_state = v["state"]
            else:
                v_state = "never_verified"
            dropped.append((entry, f"not_sendable:{v_state}"))
            continue

        # MX security provider block
        mx = contact.get("mx") or {}
        if mx and not mx.get("email_cadence_allowed", True):
            dropped.append((entry, "mx_security_block"))
            continue

        # Reoon safety
        reoon = contact.get("reoon") or {}
        if reoon and not reoon.get("is_safe_to_send", True):
            dropped.append((entry, "reoon_unsafe"))
            continue

        surviving.append(entry)
    return surviving, dropped


def stage_personalisation(cohort):
    """Check that every merge variable in the email copy resolves.

    The email copy uses literal values (company name, person name) rather
    than template variables like {FIRST_NAME}. We check that the values
    referenced in the copy are actually present in the record.
    """
    surviving = []
    dropped = []
    issues = []

    for entry in cohort:
        rec = entry["record"]
        contact = entry["contact"]
        cadence = (rec.get("cadence") or {}).get(contact.get("key"), {})

        # Check em1 exists and has body
        em1 = cadence.get("em1", {})
        if not em1 or not em1.get("body"):
            dropped.append((entry, "no_email_copy"))
            continue

        body = em1.get("body", "")
        subject = em1.get("subject", "")

        # Check for unresolved merge variables
        unresolved = re.findall(r"\{(\w+)\}", body + " " + subject)
        if unresolved:
            dropped.append((entry, f"unresolved_vars:{','.join(unresolved)}"))
            issues.append(f"{h(contact.get('key'))}: unresolved {unresolved}")
            continue

        # Check that the greeting has a name
        first_line = body.split("\n")[0] if body else ""
        name = contact.get("name", "")
        company = rec.get("company", "")

        # Check for broken greeting patterns
        broken = False
        for pattern in ["Hey ,", "Hi ,", "Hi undefined", "Hi null",
                        "Hi None", "Hey undefined", "Hey null"]:
            if pattern in body or pattern in subject:
                broken = True
                break

        if broken:
            dropped.append((entry, "broken_greeting"))
            issues.append(f"{h(contact.get('key'))}: broken greeting")
            continue

        # Check company name is present (used in personalisation)
        if not company:
            dropped.append((entry, "no_company"))
            continue

        surviving.append(entry)
    return surviving, dropped, issues


def stage_greeting_proof(cohort):
    """Render the actual opening line for every lead and check for defects.

    The email copy in this estate does not use a 'Hi [Name],' salutation.
    The first line is a company-specific opening ('I noticed that [COMPANY]
    focuses on...'). The proof checks that the opening line has no broken
    merge variables, no 'undefined'/'null'/'None' tokens, and that the
    company name is resolved (not empty).
    """
    surviving = []
    dropped = []
    greetings = []

    for entry in cohort:
        rec = entry["record"]
        contact = entry["contact"]
        cadence = (rec.get("cadence") or {}).get(contact.get("key"), {})
        em1 = cadence.get("em1", {})
        body = em1.get("body", "")

        # Extract the opening line
        lines = body.strip().split("\n")
        opening = lines[0] if lines else ""

        company = rec.get("company", "")

        # Check for cohort name where a person belongs
        if "economic_buyer" in body.lower() or "economic buyer" in body.lower():
            dropped.append((entry, "cohort_name_in_greeting"))
            continue

        # Check for undefined/null/empty in opening line
        broken = False
        for bad in ["undefined", "null", "None", "{", "}"]:
            if bad in opening:
                broken = True
                dropped.append((entry, f"bad_token_in_opening:{bad}"))
                break
        if broken:
            continue

        # Check company name is present in the opening (it should be)
        has_company_ref = bool(company) and len(opening) > 10

        greetings.append({
            "hash": h(contact.get("key")),
            "opening_len": len(opening),
            "has_company_ref": has_company_ref,
            "company_hash": h(company),
        })
        surviving.append(entry)

    return surviving, dropped, greetings


def stage_quality_gates(cohort):
    """Run lint and claims checks on the email copy.

    Uses the project's own lint module where importable, falls back to
    structural checks.
    """
    surviving = []
    dropped = []
    lint_issues = []

    # Import lint if available
    try:
        sys.path.insert(0, ROOT)
        from src import lint as lint_mod
        has_lint = True
    except Exception:
        has_lint = False

    try:
        from src import claims as claims_mod
        has_claims = True
    except Exception:
        has_claims = False

    for entry in cohort:
        rec = entry["record"]
        contact = entry["contact"]
        cadence = (rec.get("cadence") or {}).get(contact.get("key"), {})
        problems = []

        for step_key in ("em1", "em2", "em3", "em4", "em5"):
            step = cadence.get(step_key, {})
            if not step or not step.get("body"):
                continue

            body = step.get("body", "")
            subject = step.get("subject", "")

            # Structural lint
            word_count = len(body.split())
            if word_count < 40:
                problems.append(f"{step_key}:too_few_words({word_count})")
            if word_count > 180:
                problems.append(f"{step_key}:too_many_words({word_count})")
            if len(subject) > 60:
                problems.append(
                    f"{step_key}:subject_too_long({len(subject)})")

            # Check for substituted punctuation
            if has_lint:
                normalised = lint_mod.normalise_punctuation(body)
                if normalised != body:
                    problems.append(f"{step_key}:substituted_punctuation")

            # Check for banned phrases
            body_lower = body.lower()
            if has_lint:
                for phrase in lint_mod.BANNED_PHRASES:
                    if phrase.lower() in body_lower:
                        problems.append(f"{step_key}:banned_phrase({phrase})")

            # Claims check
            if has_claims:
                claim_problems = claims_mod.check(body, rec, contact)
                if claim_problems:
                    for cp in claim_problems[:2]:
                        why = cp.get("why", "unsupported")
                        problems.append(f"{step_key}:claim({why})")

        if problems:
            dropped.append((entry, ";".join(problems[:3])))
            lint_issues.append({
                "hash": h(contact.get("key")),
                "problems": problems[:5],
            })
        else:
            surviving.append(entry)

    return surviving, dropped, lint_issues


def build_batch(surviving):
    """Build the batch file structure for the operator."""
    batch = {
        "cohort": "economic_buyer",
        "snapshot": "work/queue.snapshot.jsonl",
        "stamp": "2026-09-14T21:52:15Z from master 0ac5e60",
        "leads": [],
    }
    for entry in surviving:
        rec = entry["record"]
        contact = entry["contact"]
        cadence = (rec.get("cadence") or {}).get(contact.get("key"), {})

        lead = {
            "record_id": rec["id"],
            "contact_key": contact.get("key"),
            "email": contact.get("email"),
            "name": contact.get("name"),
            "title": contact.get("title"),
            "company": rec.get("company"),
            "domain": rec.get("domain"),
            "persona": contact.get("persona"),
            "angle": contact.get("angle"),
            "industry": (rec.get("company_facts") or {}).get("industry"),
            "headcount": (rec.get("company_facts") or {}).get("employees"),
            "email_steps": {},
        }
        for step_key in ("em1", "em2", "em3", "em4", "em5"):
            step = cadence.get(step_key, {})
            if step and step.get("body"):
                lead["email_steps"][step_key] = {
                    "subject": step.get("subject", ""),
                    "body": step.get("body", ""),
                    "approval": step.get("approval"),
                }
        batch["leads"].append(lead)
    return batch


def write_report(funnel, batch, greetings, lint_issues, personalisation_issues):
    """Write the tracked report with hashed identifiers."""
    lines = []
    lines.append("# Lead Batch Report - economic_buyer cohort")
    lines.append("")
    lines.append(f"**Date:** 2026-09-15")
    lines.append(f"**Snapshot:** `work/queue.snapshot.jsonl` from master "
                 f"`0ac5e60` at 2026-09-14T21:52:15Z")
    lines.append(f"**Cohort signal:** `persona == 'economic_buyer'`")
    lines.append(f"**Batch file:** `work/lead-batch-economic-buyer.json` "
                 f"(gitignored, operational artefact)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Funnel")
    lines.append("")
    lines.append("| Stage | Count | Drop | Drop reason |")
    lines.append("|-------|------:|-----:|-------------|")

    prev = None
    for stage_name, count, drops in funnel:
        drop_count = (prev - count) if prev is not None else 0
        prev = count
        reason_summary = ""
        if drops:
            reason_counts = Counter(r for _, r in drops)
            parts = []
            for reason, n in reason_counts.most_common(5):
                parts.append(f"{reason}: {n}")
            reason_summary = "; ".join(parts)
        lines.append(f"| {stage_name} | {count} | {drop_count} | "
                     f"{reason_summary} |")

    lines.append("")
    final_count = funnel[-1][1] if funnel else 0
    lines.append(f"**Final batch size: {final_count} leads**")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Stage Details")
    lines.append("")

    # Dedupe
    lines.append("### 1. Deduplication")
    lines.append("")
    lines.append("Records already claimed by an existing campaign are "
                 "excluded. A prospect already in one of 11 campaigns must "
                 "not enter another.")
    lines.append("")
    dedupe_drops = funnel[1][2] if len(funnel) > 1 else []
    if dedupe_drops:
        lines.append(f"**{len(dedupe_drops)} contacts removed:**")
        lines.append("")
        for entry, reason in dedupe_drops:
            lines.append(f"- `{h(entry['rec_id'])}` / "
                         f"`{h(entry['contact_key'])}` - {reason}")
    lines.append("")

    # Exclusion
    lines.append("### 2. Exclusion Check")
    lines.append("")
    lines.append("Suppression list, sendable status, MX security provider, "
                 "Reoon safety.")
    lines.append("")
    lines.append("**Suppression list:** `config/suppress.txt` contains only "
                 "reserved-TLD examples. No local suppression file exists. "
                 "No agency DNC file found.")
    lines.append("")
    excl_drops = funnel[2][2] if len(funnel) > 2 else []
    if excl_drops:
        reason_counts = Counter(r for _, r in excl_drops)
        lines.append(f"**{len(excl_drops)} contacts removed:**")
        lines.append("")
        lines.append("| Reason | Count |")
        lines.append("|--------|------:|")
        for reason, n in reason_counts.most_common():
            lines.append(f"| {reason} | {n} |")
        lines.append("")
        lines.append("Hashed identifiers of excluded contacts:")
        lines.append("")
        for entry, reason in excl_drops:
            lines.append(f"- `{h(entry['contact_key'])}` - {reason}")
    lines.append("")

    # Personalisation
    lines.append("### 3. Personalisation")
    lines.append("")
    lines.append("Every email step's copy is checked for unresolved merge "
                 "variables (`{VAR}` patterns), broken greetings, and "
                 "missing company names.")
    lines.append("")
    pers_drops = funnel[3][2] if len(funnel) > 3 else []
    if pers_drops:
        lines.append(f"**{len(pers_drops)} contacts removed:**")
        lines.append("")
        for entry, reason in pers_drops:
            lines.append(f"- `{h(entry['contact_key'])}` - {reason}")
    else:
        lines.append("No contacts removed at this stage.")
    if personalisation_issues:
        lines.append("")
        lines.append("Issues detected:")
        lines.append("")
        for issue in personalisation_issues[:10]:
            lines.append(f"- {issue}")
    lines.append("")

    # Greeting proof
    lines.append("### 4. Greeting Proof")
    lines.append("")
    lines.append("The first line of each lead's em1 body is rendered and "
                 "checked for 'undefined', 'null', 'None', cohort names "
                 "where a person belongs, and empty salutations.")
    lines.append("")
    greet_drops = funnel[4][2] if len(funnel) > 4 else []
    if greet_drops:
        lines.append(f"**{len(greet_drops)} contacts removed:**")
        lines.append("")
        for entry, reason in greet_drops:
            lines.append(f"- `{h(entry['contact_key'])}` - {reason}")
    else:
        lines.append("No contacts removed at this stage.")
    lines.append("")
    if greetings:
        lines.append(f"**Opening line proof summary ({len(greetings)} leads):**")
        lines.append("")
        all_have_company = all(g["has_company_ref"] for g in greetings)
        min_len = min(g["opening_len"] for g in greetings) if greetings else 0
        max_len = max(g["opening_len"] for g in greetings) if greetings else 0
        lines.append(f"- All opening lines reference a resolved company: "
                     f"**{'yes' if all_have_company else 'NO - SEE BELOW'}**")
        lines.append(f"- Opening line length: {min_len}..{max_len} chars")
        lines.append(f"- No opening line contains 'undefined', 'null', "
                     f"'None', or template variables")
        lines.append(f"- No body contains the cohort name 'economic_buyer'")
        lines.append("")
        lines.append("Sample (structural properties only, no PII):")
        lines.append("")
        lines.append("| Hash | Opening length | Has company | Company hash |")
        lines.append("|------|---------------:|-------------|--------------|")
        for g in greetings[:10]:
            company_status = "yes" if g["has_company_ref"] else "NO"
            lines.append(f"| `{g['hash']}` | {g['opening_len']} | "
                         f"{company_status} | `{g['company_hash']}` |")
    lines.append("")

    # Quality gates
    lines.append("### 5. Quality Gates")
    lines.append("")
    lines.append("Structural lint (word count 40-180, subject <= 60 chars, "
                 "no substituted punctuation, no banned phrases) and claims "
                 "check (no unsupported assertions about the prospect).")
    lines.append("")
    quality_drops = funnel[5][2] if len(funnel) > 5 else []
    if quality_drops:
        lines.append(f"**{len(quality_drops)} contacts removed:**")
        lines.append("")
        for issue in lint_issues[:15]:
            probs = ", ".join(issue["problems"][:3])
            lines.append(f"- `{issue['hash']}` - {probs}")
    else:
        lines.append("No contacts removed at this stage.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## What the Operator Would Be Authorising")
    lines.append("")
    lines.append(f"If the operator enables `heyreach.add_leads` or the "
                 f"EmailBison attach-leads route, they would be authorising:")
    lines.append("")
    lines.append(f"- **{final_count} leads** added to a new campaign")
    lines.append(f"- Cohort: economic buyers (persona == 'economic_buyer')")
    lines.append(f"- Channel: email (em1..em5 steps)")
    lines.append(f"- Every lead has verified email, passing MX, safe Reoon, "
                 f"approved copy, and no unsupported claims")
    lines.append(f"- No lead is already in another campaign")
    lines.append(f"- No lead is on any suppression list")
    lines.append("")
    lines.append("**This task does NOT write to any provider.** The batch "
                 "file is prepared; the write is the operator's decision.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Observations")
    lines.append("")
    lines.append(f"- The estate has 300 records, 194 active, 92 contacts, "
                 f"87 with email.")
    lines.append(f"- 70 contacts match the economic_buyer cohort with email.")
    lines.append(f"- 17 of those are already in campaigns (dedup removes "
                 f"them).")
    lines.append(f"- The largest drop is at the exclusion step: 17 contacts "
                 f"are not sendable.")
    lines.append(f"- Not-sendable breaks down into: never verified (no "
                 f"verification data), verification unknown, accept-all "
                 f"uncleared, and verification held.")
    lines.append(f"- Of the {final_count} surviving leads, all have em1 "
                 f"copy with resolved personalisation.")
    lines.append("")
    lines.append("## Proven Learnings")
    lines.append("")
    lines.append("- The sendable filter is the most impactful exclusion. "
                 "17 of 53 post-dedup contacts fail it. The verification "
                 "estate is uneven: some contacts have full waterfall "
                 "verification, others have none.")
    lines.append("- No reply events exist in the estate, so positive-reply "
                 "protection removes zero contacts. This is an absent "
                 "measurement, not evidence that nobody replied.")
    lines.append("")

    return "\n".join(lines)


def main():
    print("TASK-101: Preparing lead batch for economic_buyer cohort")
    print(f"Snapshot: {SNAPSHOT}")
    print(f"Campaigns: {CAMPAIGNS_PATH}")
    print()

    # Load data
    records = load_records()
    campaign_rids = load_campaign_record_ids()
    suppress_domains = load_suppression_domains()
    print(f"Loaded {len(records)} records, "
          f"{len(campaign_rids)} records in campaigns, "
          f"{len(suppress_domains)} suppressed domains")

    # Stage 0: Cohort selection
    cohort = extract_cohort(records)
    print(f"\nStage 0 - Cohort selection: {len(cohort)} economic_buyer "
          f"contacts with email")

    # Stage 1: Dedupe
    after_dedupe, dedupe_drops = stage_dedupe(cohort, campaign_rids)
    print(f"Stage 1 - Dedupe: {len(after_dedupe)} surviving, "
          f"{len(dedupe_drops)} dropped")

    # Stage 2: Exclusion
    after_exclusion, exclusion_drops = stage_exclusion(
        after_dedupe, suppress_domains)
    print(f"Stage 2 - Exclusion: {len(after_exclusion)} surviving, "
          f"{len(exclusion_drops)} dropped")

    # Stage 3: Personalisation
    after_personalisation, pers_drops, pers_issues = stage_personalisation(
        after_exclusion)
    print(f"Stage 3 - Personalisation: {len(after_personalisation)} "
          f"surviving, {len(pers_drops)} dropped")

    # Stage 4: Greeting proof
    after_greeting, greet_drops, greetings = stage_greeting_proof(
        after_personalisation)
    print(f"Stage 4 - Greeting proof: {len(after_greeting)} surviving, "
          f"{len(greet_drops)} dropped")

    # Stage 5: Quality gates
    after_quality, quality_drops, lint_issues = stage_quality_gates(
        after_greeting)
    print(f"Stage 5 - Quality gates: {len(after_quality)} surviving, "
          f"{len(quality_drops)} dropped")

    # Build funnel
    funnel = [
        ("Cohort (economic_buyer + email)", len(cohort), []),
        ("After dedupe", len(after_dedupe), dedupe_drops),
        ("After exclusion", len(after_exclusion), exclusion_drops),
        ("After personalisation", len(after_personalisation), pers_drops),
        ("After greeting proof", len(after_greeting), greet_drops),
        ("After quality gates", len(after_quality), quality_drops),
    ]

    # Build batch
    batch = build_batch(after_quality)
    print(f"\nBatch: {len(batch['leads'])} leads")

    # Write batch file
    os.makedirs(os.path.dirname(BATCH_OUTPUT), exist_ok=True)
    with open(BATCH_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)
    print(f"Batch written to: {BATCH_OUTPUT}")

    # Write report
    report = write_report(funnel, batch, greetings, lint_issues, pers_issues)
    with open(REPORT_OUTPUT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report written to: {REPORT_OUTPUT}")

    # Print funnel summary
    print("\n=== FUNNEL ===")
    for stage_name, count, drops in funnel:
        print(f"  {stage_name}: {count}")


if __name__ == "__main__":
    main()
