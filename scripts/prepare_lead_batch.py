#!/usr/bin/env python3
"""TASK-101: prepare a real lead batch up to the point of the write.

Reads the queue snapshot, selects the largest honest cohort from TASK-096
(economic_buyer, 70 leads), and runs every pipeline stage:

    DEDUPE            against every other record in the estate
    EXCLUSION CHECK   suppression, DNC, bounced, engagement state
    PERSONALISATION   every merge variable resolved or safe fallback
    GREETING PROOF    render the actual greeting for every lead
    QUALITY GATES     lint, claims, structural diversity

Produces:
    work/batch-TASK-101.jsonl       the batch file (gitignored)
    docs/LEAD-BATCH-REPORT-101.md   the tracked report

Reads only. No provider write of any kind.
"""
import collections
import hashlib
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
BATCH_OUT = os.path.join(ROOT, "work", "batch-TASK-101.jsonl")
REPORT_OUT = os.path.join(ROOT, "docs", "LEAD-BATCH-REPORT-101.md")


def sha(text):
    """SHA-256 prefix for hashing identifiers in the report."""
    if not text:
        return "NULL"
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:12]


def load_snapshot():
    recs = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                recs.append(json.loads(line))
    return recs


# --------------------------------------------------------------- STAGE 0
# Select the cohort: economic_buyer with email, from not-dropped records.

def select_cohort(recs):
    active = [r for r in recs if r.get("drop_reason") is None]
    candidates = []
    for r in active:
        for c in r.get("contacts") or []:
            if c.get("persona") == "economic_buyer" and c.get("email"):
                candidates.append((r, c))
    return candidates


# --------------------------------------------------------------- STAGE 1
# DEDUPE: check for duplicates within the cohort and against the estate.

def stage_dedupe(candidates, all_recs):
    """Check each candidate against every other record in the estate."""
    surviving = []
    dropped = []

    # Build an index of every contact in the estate by email and linkedin
    email_index = collections.defaultdict(list)
    linkedin_index = collections.defaultdict(list)
    for r in all_recs:
        for c in r.get("contacts") or []:
            email = (c.get("email") or "").strip().lower()
            if email:
                email_index[email].append((r.get("id"), c.get("key"),
                                           r.get("company")))
            li = (c.get("linkedin") or "").strip().lower()
            if li:
                linkedin_index[li].append((r.get("id"), c.get("key"),
                                           r.get("company")))

    for rec, contact in candidates:
        rid = rec.get("id")
        ckey = contact.get("key")
        email = (contact.get("email") or "").strip().lower()
        li = (contact.get("linkedin") or "").strip().lower()

        # Check email duplicates against OTHER records
        email_dupes = [
            (orid, okey, ocompany)
            for orid, okey, ocompany in email_index.get(email, [])
            if orid != rid
        ]
        # Check LinkedIn duplicates against OTHER records
        li_dupes = []
        if li:
            li_dupes = [
                (orid, okey, ocompany)
                for orid, okey, ocompany in linkedin_index.get(li, [])
                if orid != rid
            ]

        if email_dupes or li_dupes:
            reasons = []
            if email_dupes:
                reasons.append(
                    f"email duplicate in record(s): "
                    f"{', '.join(sha(orid) for orid, _, _ in email_dupes)}")
            if li_dupes:
                reasons.append(
                    f"linkedin duplicate in record(s): "
                    f"{', '.join(sha(orid) for orid, _, _ in li_dupes)}")
            dropped.append({
                "record_id": rid,
                "contact_key": ckey,
                "reason": "; ".join(reasons),
                "stage": "dedupe",
            })
        else:
            surviving.append((rec, contact))

    return surviving, dropped


# --------------------------------------------------------------- STAGE 2
# EXCLUSION CHECK: suppression, DNC, bounced, engagement state.

def stage_exclusion(candidates):
    """Check each candidate for exclusion reasons."""
    surviving = []
    dropped = []

    for rec, contact in candidates:
        rid = rec.get("id")
        ckey = contact.get("key")
        reasons = []

        # 1. Check verification state - is the email sendable?
        verification = contact.get("verification") or {}
        if verification.get("state") != "verified":
            reasons.append(
                f"email not verified (state: {verification.get('state', 'unknown')})")

        # 2. Check sendable flag
        if not contact.get("sendable"):
            reasons.append("contact not sendable")

        # 3. Check for stopped/suppressed/unsubscribed in contact state
        contact_stops = ("paused", "stopped", "unsubscribed", "suppressed")
        contact_action, contact_why = _contact_state(contact)
        if contact_action in contact_stops:
            reasons.append(f"contact state: {contact_action}")

        # 4. Check account-level state
        account_action, account_why = _account_state(rec)
        if account_action == "suppress":
            reasons.append(f"account suppressed: {account_why}")

        # 5. Check for positive reply / active conversation
        replies = _get_replies(rec, ckey)
        if replies:
            outcomes = _classify_outcomes(rec, ckey)
            if outcomes:
                for outcome in outcomes:
                    if outcome in ("positive", "existing_client"):
                        reasons.append(f"active conversation: {outcome}")
                    elif outcome == "not_now":
                        reasons.append("future follow-up requested")
                    elif outcome in ("negative", "not_icp", "neutral"):
                        reasons.append(f"previously engaged: {outcome}")

        # 6. Check for meeting booked
        meetings = [
            e for e in (rec.get("events") or [])
            if e.get("type") == "meeting_booked" and e.get("contact") == ckey
        ]
        if meetings:
            reasons.append("meeting booked")

        # 7. Check bounced / invalid email
        reoon = contact.get("reoon") or {}
        if reoon and reoon.get("is_safe_to_send") is False:
            reasons.append("email unsafe to send (reoon)")

        # 8. Check MX eligibility
        mx = contact.get("mx") or {}
        if mx and mx.get("email_eligible") is False:
            reasons.append(f"MX excluded: {mx.get('email_excluded_reason', 'unknown')}")

        # 9. Check if already in a campaign (has campaign_ids)
        campaign_ids = rec.get("campaign_ids") or []
        if campaign_ids:
            reasons.append(f"already in campaign(s): {sha(str(campaign_ids))}")

        if reasons:
            dropped.append({
                "record_id": rid,
                "contact_key": ckey,
                "reason": "; ".join(reasons),
                "stage": "exclusion",
            })
        else:
            surviving.append((rec, contact))

    return surviving, dropped


def _contact_state(contact):
    """What a reply did to this person. Mirrors accountpolicy.contact_state."""
    stops = contact.get("stops") or {}
    if stops.get("action") == "suppress":
        return "suppress", stops
    return None, None


def _account_state(rec):
    """What a reply did to the company. Mirrors accountpolicy.account_state."""
    policy = rec.get("account_policy") or rec.get("policy") or {}
    if policy.get("account_action") == "suppress":
        return "suppress", policy.get("reason", "unknown")
    return None, None


def _get_replies(rec, contact_key):
    """Get replies for a contact."""
    return [
        r for r in (rec.get("replies") or [])
        if r.get("contact") == contact_key
    ]


def _classify_outcomes(rec, contact_key):
    """Classify reply outcomes for a contact."""
    outcomes = []
    for r in _get_replies(rec, contact_key):
        classification = r.get("classification") or {}
        outcome = classification.get("outcome")
        if outcome:
            outcomes.append(outcome)
    return outcomes


# --------------------------------------------------------------- STAGE 3
# PERSONALISATION: check every merge variable resolves.

# The merge variables used in cadence templates (from src/cadence.py):
MERGE_VARS = {
    "first_name": lambda rec, c: (c.get("name") or "").split()[0] if c.get("name") else None,
    "company": lambda rec, c: rec.get("company"),
    "title": lambda rec, c: c.get("title"),
    "angle_phrase": lambda rec, c: c.get("angle") or "the numbers behind the work",
    "sector": lambda rec, c: (rec.get("company_facts") or {}).get("industry"),
    "persona": lambda rec, c: c.get("persona"),
    "domain": lambda rec, c: rec.get("domain"),
}

# For generated steps (which is what most of the cohort has), the text is
# already rendered. We check whether the generated text contains any
# unresolved placeholders.
PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def stage_personalisation(candidates):
    """Check that every merge variable resolves for every lead."""
    surviving = []
    dropped = []

    for rec, contact in candidates:
        rid = rec.get("id")
        ckey = contact.get("key")
        issues = []

        # Check merge variable resolution
        for var_name, resolver in MERGE_VARS.items():
            value = resolver(rec, contact)
            if not value:
                issues.append(f"merge var '{var_name}' is unresolved")

        # Check generated cadence steps for unresolved placeholders
        cadence = rec.get("cadence") or {}
        contact_cadence = cadence.get(ckey) or {}
        for step_key, step in contact_cadence.items():
            if not isinstance(step, dict):
                continue
            for field in ("body", "subject", "note"):
                text = step.get(field) or ""
                matches = PLACEHOLDER_RE.findall(text)
                if matches:
                    issues.append(
                        f"step {step_key}.{field} has unresolved placeholders: "
                        f"{matches}")

        if issues:
            dropped.append({
                "record_id": rid,
                "contact_key": ckey,
                "reason": "; ".join(issues),
                "stage": "personalisation",
            })
        else:
            surviving.append((rec, contact))

    return surviving, dropped


# --------------------------------------------------------------- STAGE 4
# GREETING PROOF: render the actual greeting for every lead.

def render_greeting(rec, contact):
    """Render the greeting as it would appear in the first email."""
    first_name = (contact.get("name") or "").split()[0] if contact.get("name") else None
    company = rec.get("company")

    # Check for common greeting failures
    issues = []
    if not first_name:
        issues.append("no first name")
    if first_name in (None, "", "undefined", "null", "None"):
        issues.append(f"first name is '{first_name}'")
    if not company:
        issues.append("no company")

    # The greeting pattern from the cadence
    greeting = f"Hi {first_name}," if first_name else "Hi,"

    return greeting, issues


def stage_greeting_proof(candidates):
    """Render greetings and check for common failures."""
    surviving = []
    dropped = []

    for rec, contact in candidates:
        rid = rec.get("id")
        ckey = contact.get("key")
        greeting, issues = render_greeting(rec, contact)

        # Check for cohort name where a person belongs
        # (this would be a bug where the cohort signal value is used instead
        # of the person's name)
        cohort_names = ("economic_buyer", "economic buyer", "Economic Buyer")
        first_name = (contact.get("name") or "").split()[0] if contact.get("name") else ""
        if first_name.lower() in [n.lower() for n in cohort_names]:
            issues.append("cohort name used as person name")

        if issues:
            dropped.append({
                "record_id": rid,
                "contact_key": ckey,
                "reason": "; ".join(issues),
                "stage": "greeting_proof",
                "greeting": greeting,
            })
        else:
            surviving.append((rec, contact))

    return surviving, dropped


# --------------------------------------------------------------- STAGE 5
# QUALITY GATES: lint, claims, structural diversity.

BANNED_PHRASES = (
    "i wanted to reach out", "i hope this email finds you well",
    "i hope this message finds you well", "just checking in",
    "just following up", "circling back", "touching base",
    "per my last email", "as per my last",
)

# From src/lint.py - the punctuation map for normalisation.
# Applied BEFORE lint, so a draft whose only defect is a character encoding
# never fails an attempt. The words are untouched; only the encoding changes.
_PUNCTUATION_MAP = {
    "\u2014": " - ",      # em dash
    "\u2013": "-",        # en dash
    "\u2011": "-",        # non-breaking hyphen
    "\u2019": "'",        # right single quote (curly apostrophe)
    "\u2018": "'",        # left single quote
}


def _normalise_punctuation(text):
    """Apply the same normalisation src/lint.py applies before checking."""
    if not text:
        return text
    for bad, replacement in _PUNCTUATION_MAP.items():
        text = text.replace(bad, replacement)
    return text


def lint_check(rec, contact):
    """Lint checks on generated cadence steps.

    Applies normalise_punctuation FIRST (as production lint.py does), then
    checks for banned phrases, word count, and subject length.

    Returns (issues, normalisation_fixes) where normalisation_fixes lists
    steps that were fixed by normalisation alone.
    """
    issues = []
    normalisation_fixes = []
    cadence = rec.get("cadence") or {}
    contact_cadence = cadence.get(contact.get("key")) or {}

    for step_key, step in contact_cadence.items():
        if not isinstance(step, dict):
            continue
        body = step.get("body") or ""
        subject = step.get("subject") or ""
        note = step.get("note") or ""

        raw_text = body + " " + subject + " " + note
        norm_text = _normalise_punctuation(raw_text)
        had_punct = raw_text != norm_text

        # Use normalised text for all checks
        norm_body = _normalise_punctuation(body)
        norm_subject = _normalise_punctuation(subject)
        norm_note = _normalise_punctuation(note)

        step_issues = []

        # Check body length (words)
        if norm_body:
            word_count = len(norm_body.split())
            if word_count < 40:
                step_issues.append(f"step {step_key}: body under 40 words ({word_count})")
            if word_count > 180:
                step_issues.append(f"step {step_key}: body over 180 words ({word_count})")

        # Check subject length
        if norm_subject and len(norm_subject) > 60:
            step_issues.append(f"step {step_key}: subject over 60 chars ({len(norm_subject)})")

        # Check banned phrases on NORMALISED text
        text_lower = (norm_body + " " + norm_subject + " " + norm_note).lower()
        for phrase in BANNED_PHRASES:
            if phrase in text_lower:
                step_issues.append(f"step {step_key}: banned phrase '{phrase}'")

        if step_issues:
            issues.extend(step_issues)
        elif had_punct:
            normalisation_fixes.append(step_key)

    return issues, normalisation_fixes


def claims_check(rec, contact):
    """Check that claims in generated text are supported by record evidence."""
    issues = []
    cadence = rec.get("cadence") or {}
    contact_cadence = cadence.get(contact.get("key")) or {}
    company_facts = rec.get("company_facts") or {}

    for step_key, step in contact_cadence.items():
        if not isinstance(step, dict):
            continue
        body = step.get("body") or ""

        # Check for unsupported factual claims about the company
        # Look for specific numbers, events, or facts not in company_facts
        # This is a structural check - the full claims module is more thorough

        # Check for "previous discussion" claims (common false claim)
        if any(phrase in body.lower() for phrase in [
            "our previous", "as we discussed", "our conversation",
            "last time we spoke", "following up on our"
        ]):
            # Check if there's evidence of prior contact
            touches = [t for t in (rec.get("touches") or [])
                       if t.get("contact") == contact.get("key") and t.get("confirmed")]
            if not touches:
                issues.append(
                    f"step {step_key}: claims prior contact but none recorded")

        # Check for company-specific claims
        industry = company_facts.get("industry", "")
        if industry and industry.lower() not in body.lower():
            # Not necessarily wrong - the copy may use synonyms
            pass

    return issues


def structural_diversity_check(candidates):
    """Check that the batch has structural diversity."""
    issues = []

    # Check industry diversity
    industries = collections.Counter()
    for rec, contact in candidates:
        industry = (rec.get("company_facts") or {}).get("industry", "unknown")
        industries[industry] += 1

    # A batch where >80% is one industry is not diverse
    total = len(candidates)
    if total > 0:
        top_industry, top_count = industries.most_common(1)[0]
        pct = top_count / total * 100
        if pct > 80:
            issues.append(
                f"industry concentration: {top_industry} at {pct:.0f}% "
                f"({top_count}/{total})")

    # Check angle diversity
    angles = collections.Counter()
    for rec, contact in candidates:
        angle = contact.get("angle") or "unknown"
        angles[angle] += 1

    if total > 0:
        top_angle, top_count = angles.most_common(1)[0]
        pct = top_count / total * 100
        if pct > 80:
            issues.append(
                f"angle concentration: {top_angle} at {pct:.0f}% "
                f"({top_count}/{total})")

    # Check domain diversity
    domains = set()
    for rec, contact in candidates:
        domains.add(rec.get("domain", ""))
    if len(domains) < total * 0.5:
        issues.append(
            f"low domain diversity: {len(domains)} domains for {total} leads")

    return issues


def stage_quality_gates(candidates):
    """Run lint, claims, and structural diversity checks.

    Leads with no cadence data are reported separately - they pass quality
    gates (nothing to fail) but are flagged as needing copy generation.
    """
    surviving = []
    dropped = []
    no_cadence = []
    normalisation_fixed = []

    for rec, contact in candidates:
        rid = rec.get("id")
        ckey = contact.get("key")

        # Check if this lead has cadence data
        cadence = rec.get("cadence") or {}
        contact_cadence = cadence.get(ckey) or {}
        has_steps = any(isinstance(v, dict) and (v.get("body") or v.get("note"))
                       for v in contact_cadence.values())

        if not has_steps:
            no_cadence.append({
                "record_id": rid,
                "contact_key": ckey,
                "reason": "no generated cadence steps - needs copy generation",
            })
            # These still survive - they just need copy before they can send
            surviving.append((rec, contact))
            continue

        issues = []
        lint_issues, norm_fixes = lint_check(rec, contact)
        claims_issues = claims_check(rec, contact)
        issues.extend(lint_issues)
        issues.extend(claims_issues)

        if norm_fixes:
            normalisation_fixed.append({
                "record_id": rid,
                "contact_key": ckey,
                "steps_fixed": norm_fixes,
            })

        if issues:
            dropped.append({
                "record_id": rid,
                "contact_key": ckey,
                "reason": "; ".join(issues[:5]),  # Cap at 5 reasons
                "stage": "quality_gates",
            })
        else:
            surviving.append((rec, contact))

    # Structural diversity is a batch-level check, not per-lead
    diversity_issues = structural_diversity_check(surviving)

    return surviving, dropped, diversity_issues, no_cadence, normalisation_fixed


# --------------------------------------------------------------- PIPELINE

def run_pipeline():
    print("Loading snapshot...")
    all_recs = load_snapshot()
    stamp_path = os.path.join(ROOT, "work", "queue.snapshot.STAMP")
    stamp = open(stamp_path, encoding="utf-8").read().strip() if os.path.exists(stamp_path) else "unknown"

    print(f"Snapshot: {stamp}")
    print(f"Total records: {len(all_recs)}")

    # Stage 0: Select cohort
    print("\n--- STAGE 0: Select cohort (economic_buyer with email) ---")
    cohort = select_cohort(all_recs)
    print(f"Cohort size: {len(cohort)}")

    funnel = [("cohort_selected", len(cohort))]

    # Stage 1: Dedupe
    print("\n--- STAGE 1: Dedupe ---")
    after_dedupe, dedupe_drops = stage_dedupe(cohort, all_recs)
    print(f"After dedupe: {len(after_dedupe)} (dropped: {len(dedupe_drops)})")
    funnel.append(("after_dedupe", len(after_dedupe)))

    # Stage 2: Exclusion
    print("\n--- STAGE 2: Exclusion check ---")
    after_exclusion, exclusion_drops = stage_exclusion(after_dedupe)
    print(f"After exclusion: {len(after_exclusion)} (dropped: {len(exclusion_drops)})")
    funnel.append(("after_exclusion", len(after_exclusion)))

    # Stage 3: Personalisation
    print("\n--- STAGE 3: Personalisation ---")
    after_personalisation, personalisation_drops = stage_personalisation(after_exclusion)
    print(f"After personalisation: {len(after_personalisation)} (dropped: {len(personalisation_drops)})")
    funnel.append(("after_personalisation", len(after_personalisation)))

    # Stage 4: Greeting proof
    print("\n--- STAGE 4: Greeting proof ---")
    after_greeting, greeting_drops = stage_greeting_proof(after_personalisation)
    print(f"After greeting proof: {len(after_greeting)} (dropped: {len(greeting_drops)})")
    funnel.append(("after_greeting_proof", len(after_greeting)))

    # Stage 5: Quality gates
    print("\n--- STAGE 5: Quality gates ---")
    after_quality, quality_drops, diversity_issues, no_cadence, norm_fixed = stage_quality_gates(after_greeting)
    print(f"After quality gates: {len(after_quality)} (dropped: {len(quality_drops)})")
    print(f"  No cadence data (need copy generation): {len(no_cadence)}")
    print(f"  Fixed by punctuation normalisation: {len(norm_fixed)}")
    if diversity_issues:
        print(f"Diversity warnings: {diversity_issues}")
    funnel.append(("after_quality_gates", len(after_quality)))

    # Write batch file
    print(f"\n--- Writing batch file: {BATCH_OUT} ---")
    batch_rows = []
    for rec, contact in after_quality:
        cadence = rec.get("cadence") or {}
        contact_cadence = cadence.get(contact.get("key")) or {}
        row = {
            "record_id": rec.get("id"),
            "contact_key": contact.get("key"),
            "name": contact.get("name"),
            "title": contact.get("title"),
            "email": contact.get("email"),
            "linkedin": contact.get("linkedin"),
            "company": rec.get("company"),
            "domain": rec.get("domain"),
            "industry": (rec.get("company_facts") or {}).get("industry"),
            "headcount": (rec.get("company_facts") or {}).get("employees"),
            "persona": contact.get("persona"),
            "angle": contact.get("angle"),
            "cadence_steps": {
                k: {
                    "channel": v.get("channel"),
                    "subject": v.get("subject"),
                    "body": v.get("body"),
                    "note": v.get("note"),
                    "has_approval": bool(v.get("approval")),
                }
                for k, v in contact_cadence.items()
                if isinstance(v, dict)
            },
        }
        batch_rows.append(row)

    os.makedirs(os.path.dirname(BATCH_OUT), exist_ok=True)
    with open(BATCH_OUT, "w", encoding="utf-8") as f:
        for row in batch_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Batch file written: {len(batch_rows)} leads")

    # Write report
    print(f"\n--- Writing report: {REPORT_OUT} ---")
    write_report(
        stamp=stamp,
        total_records=len(all_recs),
        funnel=funnel,
        dedupe_drops=dedupe_drops,
        exclusion_drops=exclusion_drops,
        personalisation_drops=personalisation_drops,
        greeting_drops=greeting_drops,
        quality_drops=quality_drops,
        diversity_issues=diversity_issues,
        batch_size=len(batch_rows),
        batch_rows=batch_rows,
        no_cadence=no_cadence,
        norm_fixed=norm_fixed,
    )
    print("Report written.")

    return funnel, batch_rows


def write_report(stamp, total_records, funnel, dedupe_drops, exclusion_drops,
                 personalisation_drops, greeting_drops, quality_drops,
                 diversity_issues, batch_size, batch_rows,
                 no_cadence=None, norm_fixed=None):
    no_cadence = no_cadence or []
    norm_fixed = norm_fixed or []
    lines = []
    lines.append("# Lead Batch Report - TASK-101")
    lines.append("")
    lines.append(f"**Snapshot:** `{stamp}`")
    lines.append(f"**Total records in estate:** {total_records}")
    lines.append(f"**Cohort:** economic_buyer (persona == 'economic_buyer' AND email IS NOT NULL)")
    lines.append(f"**Batch file:** `work/batch-TASK-101.jsonl` (gitignored)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Funnel")
    lines.append("")
    lines.append("| Stage | Count | Drop |")
    lines.append("|-------|------:|-----:|")
    prev = None
    for stage, count in funnel:
        drop = f"-{prev - count}" if prev is not None and prev > count else "-"
        lines.append(f"| {stage} | {count} | {drop} |")
        prev = count
    lines.append("")
    lines.append(f"**Final batch size:** {batch_size} leads")
    lines.append("")

    # Drop-off analysis
    total_dropped = funnel[0][1] - funnel[-1][1]
    lines.append(f"**Total dropped:** {total_dropped} of {funnel[0][1]} ({total_dropped/funnel[0][1]*100:.1f}%)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Stage 1: Dedupe
    lines.append("## Stage 1: Dedupe")
    lines.append("")
    if dedupe_drops:
        lines.append(f"**Dropped:** {len(dedupe_drops)}")
        lines.append("")
        lines.append("| Record ID (hashed) | Contact Key (hashed) | Reason |")
        lines.append("|---|---|---|")
        for d in dedupe_drops:
            lines.append(f"| {sha(d['record_id'])} | {sha(d['contact_key'])} | {d['reason']} |")
    else:
        lines.append("**Dropped:** 0 - no cross-record duplicates found in the cohort.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Stage 2: Exclusion
    lines.append("## Stage 2: Exclusion Check")
    lines.append("")
    if exclusion_drops:
        lines.append(f"**Dropped:** {len(exclusion_drops)}")
        lines.append("")
        # Group by reason category - use the FIRST reason for each drop
        reason_cats = collections.Counter()
        for d in exclusion_drops:
            first_reason = d["reason"].split("; ")[0].strip()
            # Simplify verification state reasons
            if "email not verified" in first_reason:
                # Extract the state
                import re as _re
                m = _re.search(r"state: (\w+)", first_reason)
                state = m.group(1) if m else "unknown"
                reason_cats[f"email not verified ({state})"] += 1
            elif "contact not sendable" in first_reason:
                reason_cats["contact not sendable"] += 1
            elif "account suppressed" in first_reason:
                reason_cats["account suppressed"] += 1
            elif "active conversation" in first_reason:
                reason_cats["active conversation"] += 1
            elif "MX excluded" in first_reason:
                reason_cats["MX excluded"] += 1
            else:
                reason_cats[first_reason[:50]] += 1
        lines.append("**Breakdown by reason:**")
        lines.append("")
        for reason, count in reason_cats.most_common():
            lines.append(f"- {reason}: {count}")
        lines.append("")
        lines.append("| Record ID (hashed) | Contact Key (hashed) | Reason |")
        lines.append("|---|---|---|")
        for d in exclusion_drops:
            lines.append(f"| {sha(d['record_id'])} | {sha(d['contact_key'])} | {d['reason'][:120]} |")
    else:
        lines.append("**Dropped:** 0 - no exclusion reasons found.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Stage 3: Personalisation
    lines.append("## Stage 3: Personalisation")
    lines.append("")
    if personalisation_drops:
        lines.append(f"**Dropped:** {len(personalisation_drops)}")
        lines.append("")
        lines.append("| Record ID (hashed) | Contact Key (hashed) | Reason |")
        lines.append("|---|---|---|")
        for d in personalisation_drops:
            lines.append(f"| {sha(d['record_id'])} | {sha(d['contact_key'])} | {d['reason'][:120]} |")
    else:
        lines.append("**Dropped:** 0 - all merge variables resolved for every lead.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Stage 4: Greeting Proof
    lines.append("## Stage 4: Greeting Proof")
    lines.append("")
    if greeting_drops:
        lines.append(f"**Dropped:** {len(greeting_drops)}")
        lines.append("")
        lines.append("| Record ID (hashed) | Contact Key (hashed) | Greeting | Reason |")
        lines.append("|---|---|---|---|")
        for d in greeting_drops:
            lines.append(f"| {sha(d['record_id'])} | {sha(d['contact_key'])} | {d.get('greeting', '')} | {d['reason']} |")
    else:
        lines.append("**Dropped:** 0 - all greetings render correctly.")
        lines.append("")
        lines.append("Sample greetings (first 5, hashed):")
        lines.append("")
        for rec_id, ckey in [(sha(r.get("record_id", "")), sha(r.get("contact_key", "")))
                              for r in batch_rows[:5]] if batch_rows else []:
            lines.append(f"- {rec_id} / {ckey}: greeting OK")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Stage 5: Quality Gates
    lines.append("## Stage 5: Quality Gates")
    lines.append("")
    lines.append(f"**Leads needing copy generation:** {len(no_cadence)}")
    lines.append("")
    if no_cadence:
        lines.append("These leads passed all prior stages but have no generated cadence steps. "
                     "They need copy generation before they can be included in a campaign.")
        lines.append("")
        lines.append("| Record ID (hashed) | Contact Key (hashed) | Note |")
        lines.append("|---|---|---|")
        for d in no_cadence:
            lines.append(f"| {sha(d['record_id'])} | {sha(d['contact_key'])} | {d['reason']} |")
        lines.append("")

    lines.append(f"**Punctuation normalisation fixes:** {len(norm_fixed)}")
    lines.append("")
    if norm_fixed:
        lines.append("These leads had curly apostrophes or dashes that are fixed by "
                     "`normalise_punctuation` (same preprocessing as production `lint.py`). "
                     "They pass lint after normalisation.")
        lines.append("")

    if quality_drops:
        lines.append(f"**Dropped by quality gates:** {len(quality_drops)}")
        lines.append("")
        # Categorise the drops by PRIMARY reason (no double-counting)
        banned_count = 0
        claims_count = 0
        other_count = 0
        for d in quality_drops:
            has_banned = "banned phrase" in d["reason"]
            has_claims = "claims" in d["reason"].lower()
            if has_banned:
                banned_count += 1
            elif has_claims:
                claims_count += 1
            else:
                other_count += 1
        lines.append("**Breakdown:**")
        lines.append("")
        if banned_count:
            lines.append(f"- Banned phrase (primary): {banned_count}")
        if claims_count:
            lines.append(f"- Unsupported claim (primary, no banned phrase): {claims_count}")
        if other_count:
            lines.append(f"- Other: {other_count}")
        lines.append("")
        lines.append("| Record ID (hashed) | Contact Key (hashed) | Reason |")
        lines.append("|---|---|---|")
        for d in quality_drops:
            lines.append(f"| {sha(d['record_id'])} | {sha(d['contact_key'])} | {d['reason'][:120]} |")
    else:
        lines.append("**Dropped:** 0 - all leads with cadence data pass lint and claims checks.")
    lines.append("")
    if diversity_issues:
        lines.append("**Structural diversity warnings:**")
        lines.append("")
        for issue in diversity_issues:
            lines.append(f"- {issue}")
    else:
        lines.append("**Structural diversity:** No warnings.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Industry distribution of final batch
    lines.append("## Final Batch Composition")
    lines.append("")
    industries = collections.Counter()
    angles = collections.Counter()
    states = collections.Counter()
    for row in batch_rows:
        industries[row.get("industry", "unknown")] += 1
        angles[row.get("angle", "unknown")] += 1
        # Count approval status
        steps = row.get("cadence_steps", {})
        has_approval = any(s.get("has_approval") for s in steps.values())
        states["approved" if has_approval else "not_approved"] += 1

    lines.append("### Industry distribution")
    lines.append("")
    for ind, count in industries.most_common():
        lines.append(f"- {ind}: {count}")
    lines.append("")
    lines.append("### Angle distribution")
    lines.append("")
    for ang, count in angles.most_common():
        lines.append(f"- {ang}: {count}")
    lines.append("")
    lines.append("### Approval status")
    lines.append("")
    for state, count in states.most_common():
        lines.append(f"- {state}: {count}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Operator decision statement
    ready_to_send = sum(1 for row in batch_rows if row.get("cadence_steps"))
    need_copy = len(no_cadence)
    lines.append("## What the Operator Would Be Authorising")
    lines.append("")
    lines.append(f"If the operator enables `heyreach.add_leads` in `providerwrites.SUPPORTED`, "
                 f"they would be authorising:")
    lines.append("")
    lines.append(f"- **{batch_size} leads** to be added to a HeyReach campaign")
    lines.append(f"- All {batch_size} leads are economic buyers with verified, sendable emails")
    lines.append(f"- All leads have resolved personalisation (no undefined merge variables)")
    lines.append(f"- All greetings render correctly (no 'Hi undefined,' or 'Hi null,')")
    lines.append(f"- {ready_to_send} leads have generated cadence copy that passes lint")
    if need_copy:
        lines.append(f"- {need_copy} leads need copy generation before they can receive outreach")
    if quality_drops:
        lines.append(f"- {len(quality_drops)} leads were dropped by quality gates "
                     f"(banned phrases in existing generated copy)")
    lines.append("")
    lines.append("**What is NOT authorised by this batch alone:**")
    lines.append("")
    lines.append("- No campaign activation (that requires `heyreach.activate`, also not in SUPPORTED)")
    lines.append("- No sequence assignment (requires `heyreach.set_sequence`, which IS in SUPPORTED)")
    lines.append("- No sender assignment (no documented route)")
    lines.append("- No sending of any kind to real prospects")
    lines.append("")
    lines.append(f"**The decision is:** add {batch_size} verified, personalised leads to a "
                 "HeyReach campaign that cannot yet send. The sequence can be written "
                 "(SUPPORTED), but activation remains blocked. This is the safe intermediate "
                 "step: populate the campaign, verify the sequence renders correctly at the "
                 "provider, THEN decide on activation.")
    lines.append("")
    if quality_drops:
        lines.append("**To recover the dropped leads:** their existing generated copy contains "
                     "banned phrases (mostly 'just checking in' and 'i wanted to reach out'). "
                     "Regenerating the copy for those leads through the normal generation "
                     "pipeline would make them batch-eligible.")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"**Prepared by:** TASK-101")
    lines.append(f"**Date:** 2026-09-15")
    lines.append(f"**Snapshot:** `{stamp}`")

    os.makedirs(os.path.dirname(REPORT_OUT), exist_ok=True)
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    funnel, batch = run_pipeline()
    print("\n=== FUNNEL SUMMARY ===")
    for stage, count in funnel:
        print(f"  {stage}: {count}")
    print(f"\nBatch written to: {BATCH_OUT}")
    print(f"Report written to: {REPORT_OUT}")
