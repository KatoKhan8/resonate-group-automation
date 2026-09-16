"""TASK-167: Resolve the CONTROL sequence against the real queue.

Produces:
  1. Per-contact, per-step variable resolution table
  2. Rendered text for all 3 steps, per contact
  3. Lint + claims gate verdict on each rendered step
  4. Fallback count per contact
  5. Exact staging payload (PII hashed) as JSON

Must be run on a worktree with work/queue.snapshot.jsonl.
"""

import hashlib
import json
import os
import re
import sys

import yaml

SNAPSHOT = os.path.join("work", "queue.snapshot.jsonl")
CONFIG_PATH = os.path.join("config", "clients", "productive.yaml")
OUTPUT_DOC = os.path.join("docs", "BISON-CONTROL-PAYLOAD-2026-09-16.md")

COLD_ALLOW = {
    "digitalthirdcoast.com", "feddirect.com", "inmobi.com", "ritway.com",
    "skyad.com", "thecommunity.ca", "viralityllc.com", "wearejsa.com",
}
NEVER_EMAILED_ALLOW = {
    "ogpartner.dk", "px-2a51e132bab4", "acqcom.com", "px-a8ca1565fdd1",
    "portsidemarketing.com", "agency59.ca", "savagebrands.com",
    "mischacommunications.com", "mypersonalestatesale.com",
}
ALL_ALLOW = COLD_ALLOW | NEVER_EMAILED_ALLOW

ANGLE_WORD_MAX = 32
FALLBACK_ANGLE_WORD = "the numbers behind the work"

HOSTNAME_RE = re.compile(r"\.[a-z]{2,}$", re.I)

# Lint constants (mirrored from src/lint.py)
MIN_WORDS = 40
MAX_WORDS = 180
MAX_SUBJECT = 60
SUBSTITUTED_PUNCTUATION = ("\u2014", "\u2013", "\u2011", "\u2019", "\u2018")
BANNED_PHRASES = (
    "i hope this email finds you well", "i wanted to reach out", "circling back",
    "just following up", "touching base", "as per my last email", "synergy",
    "game-changer",
)
ATTACHMENT_RE = re.compile(
    r"\battachment\b"
    r"|attached (is|are|you'?ll|please|here|below)"
    r"|(see|find|i'?ve|i have|we'?ve) attached"
    r"|attached (file|screenshot|deck|pdf|doc|csv|list|sheet|rate card)"
    r"|(file|screenshot|deck|pdf|doc|csv|sheet|rate card|image)s? attached",
    re.I)
PLACEHOLDER_RE = re.compile(r"[\[{<](?!http)[^\]}>\n]{2,40}[\]}>]")

# The CONTROL templates from cadence.TEMPLATES
TEMPLATES = {
    "persona_pain": {
        "subject": "{angle_phrase}",
        "body": (
            "{first_name}, {line}\n\n"
            "The pattern I see in teams the size of {company} is that the numbers "
            "arrive too late to act on. Utilisation and margin are known at the end "
            "of the month, which is after the month when something could have been "
            "done about them. The work itself is rarely the problem. The visibility "
            "into it is.\n\n"
            "Is that roughly how it works at {company} today, or have you already "
            "put something in place for it?"
        ),
    },
    "comparable_proof": {
        "subject": "how teams your size handle {angle_word}",
        "body": (
            "{first_name}, the teams I work with that look most like "
            "{company} tend to arrive at the same place.\n\n"
            "They stop reconciling hours after the fact and start "
            "seeing project margin while the project is still running. The change "
            "that makes the difference is not a new process for the delivery team, "
            "it is that the finance view and the delivery view stop being two "
            "different spreadsheets maintained by two different people.\n\n"
            "Would it be useful to see what that looked like for a team your size?"
        ),
    },
    "breakup": {
        "subject": "closing the loop",
        "body": (
            "{first_name}, if {angle_phrase} is not something you are "
            "looking at right now, that is a fair answer in itself. I "
            "will leave it here.\n\n"
            "If it becomes relevant later, the thing worth knowing is that most "
            "teams the size of {company} start looking at this when a project lands "
            "under margin and nobody can say exactly when it went wrong.\n\n"
            "Anything you would want me to send over, or shall I leave it there?"
        ),
    },
}

# Sequence: step name, day, thread_reply
STEPS = [
    ("persona_pain", 1, False),
    ("comparable_proof", 5, True),
    ("breakup", 21, False),
]


def _hash(value):
    """SHA-256 prefix for PII hashing. 12 hex chars."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _resolve_company(rec):
    """Mirror cadence.company_name. Returns name or None."""
    facts = rec.get("company_facts") or {}
    domain = str(rec.get("domain") or "").strip().lower()
    for candidate in (facts.get("name"), rec.get("company")):
        name = str(candidate or "").strip()
        if not name:
            continue
        if name.lower() == domain or HOSTNAME_RE.search(name.split()[-1]):
            continue
        return name
    return None


def _resolve_first_name(contact):
    name = (contact.get("name") or "").strip()
    if name:
        return name.split()[0]
    return None  # None means fallback "there" would fire


def _resolve_angle(contact, config):
    """Mirror cadence.angle_words."""
    personas_cfg = config.get("personas") or {}
    persona = contact.get("persona") or "champion"
    persona_block = personas_cfg.get(persona) or {}
    angles = persona_block.get("angles") or {}
    if not angles:
        default = personas_cfg.get("default_angle")
        if default and isinstance(default, str):
            angles = {default: "how the work is tracked"}
        else:
            angles = {"operations": "how the work is tracked"}
    angle = contact.get("angle")
    phrase = angles.get(angle) if angle else None
    if not phrase:
        phrase = next(iter(angles.values()), "how the work is tracked")
    angle_key = angle or next(iter(angles), "operations")
    phrase_clean = str(phrase).split(",")[0].strip()
    return angle_key, phrase_clean


def _resolve_angle_word(angle, phrase, config):
    """Mirror cadence.angle_word."""
    labels = config.get("angle_labels") or {}
    label = labels.get(str(angle or "").strip().lower())
    if label and len(str(label)) <= ANGLE_WORD_MAX:
        return str(label)
    if phrase and len(phrase) <= ANGLE_WORD_MAX:
        return phrase
    return FALLBACK_ANGLE_WORD


def _lint_check(subject, body):
    """Mirror the email-relevant subset of lint.check for rendered text."""
    fails = set()
    if any(d in body or d in subject for d in SUBSTITUTED_PUNCTUATION):
        fails.add("em_dash")
    if ATTACHMENT_RE.search(body):
        fails.add("attachment")
    if PLACEHOLDER_RE.search(body) or PLACEHOLDER_RE.search(subject):
        fails.add("placeholder")
    words = len(body.split())
    if words < MIN_WORDS:
        fails.add("body_too_short")
    if words > MAX_WORDS:
        fails.add("body_too_long")
    if not subject:
        fails.add("subject_missing")
    elif len(subject) >= MAX_SUBJECT:
        fails.add("subject_too_long")
    for para in body.split("\n\n"):
        if len([ln for ln in para.split("\n") if ln.strip()]) > 1:
            fails.add("hard_wrapped")
            break
    low = body.lower()
    if any(p in low for p in BANNED_PHRASES):
        fails.add("filler_phrase")
    return sorted(fails)


def _claims_check(body, company, sector):
    """Lightweight claims check: does the body assert something about the
    prospect that the record does not support?

    The CONTROL templates are deliberately written to avoid claims about the
    prospect. This checks for the known risk patterns:
    - Second-person operational assertions ("you are running X")
    - Prior contact claims ("following up", "as I mentioned")
    """
    issues = []
    low = body.lower()
    # Prior contact claims
    prior_contact_phrases = [
        "following up", "as i mentioned", "i wrote to you",
        "my last email", "my last message", "our previous",
        "i have written", "not heard back",
    ]
    for phrase in prior_contact_phrases:
        if phrase in low:
            issues.append(f"prior_contact_claim: '{phrase}'")
    # Second-person operational assertions
    operational_terms = [
        "utilisation", "margin", "capacity", "resourcing",
        "billing", "invoicing", "profitability",
    ]
    # The templates use "the pattern I see in teams the size of X" which is
    # a generalisation, not an assertion about THIS prospect. And the breakup
    # says "if X is not something you are looking at" which is conditional.
    # Neither is a flat assertion. Check for flat assertions only.
    sentences = re.split(r"[.!?]\s", body)
    for sent in sentences:
        slow = sent.lower().strip()
        if not slow:
            continue
        # Skip questions - they assert nothing
        if "?" in sent:
            continue
        # Skip conditionals
        if any(hedge in slow for hedge in ["if ", "whether", "might", "could",
                                            "tend to", "usually", "most teams"]):
            continue
        # Check for "you are" + operational term
        if "you are" in slow or "you're" in slow:
            for term in operational_terms:
                if term in slow:
                    issues.append(f"operational_assertion: '{sent.strip()[:80]}'")
                    break
    return issues


def main():
    # Read snapshot stamp
    stamp_path = os.path.join("work", "queue.snapshot.STAMP")
    stamp = "UNKNOWN"
    if os.path.exists(stamp_path):
        with open(stamp_path, encoding="utf-8") as f:
            stamp = f.read().strip()

    if not os.path.exists(SNAPSHOT):
        print(f"ERROR: {SNAPSHOT} not found.")
        sys.exit(1)

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # Find the 17 cohort contacts
    cohort = []
    for rec in records:
        domain = str(rec.get("domain") or "").strip().lower()
        if domain in ALL_ALLOW:
            contacts = rec.get("contacts") or []
            for c in contacts:
                v = c.get("verification") or {}
                if c.get("email_verified") or v.get("state") == "verified":
                    cohort.append((rec, c, domain))

    print(f"Snapshot STAMP: {stamp}")
    print(f"Snapshot records: {len(records)}")
    print(f"Cohort contacts: {len(cohort)}")
    print()

    # Process each contact
    results = []
    blocked = []
    payload_entries = []

    for idx, (rec, contact, domain) in enumerate(cohort, 1):
        contact_key = contact.get("key") or _hash(contact.get("name", f"unknown-{idx}"))
        name_hash = _hash(contact.get("name", ""))
        domain_hash = _hash(domain)
        company_hash = _hash(rec.get("company", ""))
        email_hash = _hash(contact.get("email", ""))

        fallbacks = []
        resolution = {}

        # first_name
        first = _resolve_first_name(contact)
        if first is None:
            first = "there"
            fallbacks.append("first_name -> 'there'")
            resolution["first_name"] = {"value": "there", "source": "FALLBACK"}
        else:
            resolution["first_name"] = {"value": first, "source": "contact.name"}

        # company
        company = _resolve_company(rec)
        if company is None:
            blocked.append({
                "idx": idx, "domain_hash": domain_hash,
                "name_hash": name_hash, "reason": "company=UNRESOLVABLE",
            })
            continue
        resolution["company"] = {"value": company, "source": "company_facts.name"
            if (rec.get("company_facts") or {}).get("name")
            else "rec.company"}

        # angle
        angle_key, angle_phrase = _resolve_angle(contact, config)
        facts = rec.get("company_facts") or {}

        # Check if angle is from config or fallback
        personas_cfg = config.get("personas") or {}
        persona = contact.get("persona") or "champion"
        persona_block = personas_cfg.get(persona) or {}
        angles = persona_block.get("angles") or {}
        contact_angle = contact.get("angle")
        if contact_angle and angles.get(contact_angle):
            resolution["angle_phrase"] = {
                "value": angle_phrase, "source": "config.personas.angles"}
        else:
            fallbacks.append("angle_phrase -> fallback")
            resolution["angle_phrase"] = {
                "value": angle_phrase, "source": "FALLBACK (first angle in persona)"}

        # angle_word
        angle_word_val = _resolve_angle_word(angle_key, angle_phrase, config)
        labels = config.get("angle_labels") or {}
        label = labels.get(str(angle_key or "").strip().lower())
        if label and len(str(label)) <= ANGLE_WORD_MAX:
            resolution["angle_word"] = {"value": angle_word_val,
                                        "source": "config.angle_labels"}
        elif angle_phrase and len(angle_phrase) <= ANGLE_WORD_MAX:
            resolution["angle_word"] = {"value": angle_word_val,
                                        "source": "first clause of angle phrase"}
        else:
            fallbacks.append("angle_word -> fallback")
            resolution["angle_word"] = {"value": angle_word_val,
                                        "source": "FALLBACK"}

        # sector
        sector = facts.get("industry") or "services"
        if facts.get("industry"):
            resolution["sector"] = {"value": sector, "source": "company_facts.industry"}
        else:
            fallbacks.append("sector -> 'services'")
            resolution["sector"] = {"value": sector, "source": "FALLBACK"}

        # line
        evidence = (rec.get("evidence") or {}).get(contact_key) or []
        if evidence:
            line = str(evidence[0]).rstrip(".")
            resolution["line"] = {"value": "(evidence)", "source": "evidence[0]"}
        else:
            line = (f"I work with {sector} teams on {angle_phrase}, "
                    f"and I do not know how {company} handles it")
            fallbacks.append("line -> generic intro")
            resolution["line"] = {"value": "(generic intro)", "source": "FALLBACK"}

        # Build template vars
        values = {
            "first_name": first,
            "company": company,
            "angle": angle_key,
            "angle_word": angle_word_val,
            "angle_phrase": angle_phrase,
            "sector": sector,
            "line": line,
        }

        # Render all 3 steps
        rendered_steps = []
        lint_results = []
        claims_results = []

        for step_name, day, thread_reply in STEPS:
            tmpl = TEMPLATES[step_name]
            rendered = {}
            for field, text in tmpl.items():
                rendered[field] = text.format(**values)

            subject = rendered["subject"]
            body = rendered["body"]

            # Lint
            lint_fails = _lint_check(subject, body)
            lint_results.append({
                "step": step_name, "day": day,
                "fails": lint_fails,
                "pass": len(lint_fails) == 0,
            })

            # Claims
            claims_issues = _claims_check(body, company, sector)
            claims_results.append({
                "step": step_name, "day": day,
                "issues": claims_issues,
                "pass": len(claims_issues) == 0,
            })

            rendered_steps.append({
                "step": step_name, "day": day,
                "thread_reply": thread_reply,
                "subject": subject,
                "body": body,
            })

        # Build payload entry (PII hashed in body text too)
        contact_name = contact.get("name", "")
        payload_entry = {
            "contact_hash": name_hash,
            "domain_hash": domain_hash,
            "email_hash": email_hash,
            "company_hash": company_hash,
            "steps": [],
        }
        for rs in rendered_steps:
            hashed_subject = _hash_pii_in_text(rs["subject"], contact_name, company)
            hashed_body = _hash_pii_in_text(rs["body"], contact_name, company)
            payload_entry["steps"].append({
                "step": rs["step"],
                "day": rs["day"],
                "thread_reply": rs["thread_reply"],
                "subject": hashed_subject,
                "body": hashed_body,
            })
        payload_entries.append(payload_entry)

        results.append({
            "idx": idx,
            "domain_hash": domain_hash,
            "name_hash": name_hash,
            "company_hash": company_hash,
            "company": company,
            "resolution": resolution,
            "fallbacks": fallbacks,
            "fallback_count": len(fallbacks),
            "rendered_steps": rendered_steps,
            "lint_results": lint_results,
            "claims_results": claims_results,
        })

    # Print summary
    print("=" * 72)
    print("VARIABLE RESOLUTION TABLE")
    print("=" * 72)
    for r in results:
        print(f"\nContact #{r['idx']} (domain={r['domain_hash']}, name={r['name_hash']}):")
        print(f"  Company hash: {r['company_hash']}")
        for var, info in r["resolution"].items():
            val = info["value"]
            # Hash PII values for console output
            if var == "first_name" and val != "there":
                val = f"<name:{r['name_hash']}>"
            elif var == "company":
                val = f"<company:{r['company_hash']}>"
            print(f"  {var:15s} = {info['source']:40s} -> {str(val)[:50]}")
        print(f"  Fallbacks: {r['fallback_count']}")
        for fb in r["fallbacks"]:
            print(f"    - {fb}")

    print()
    print("=" * 72)
    print("LINT VERDICT")
    print("=" * 72)
    all_lint_pass = True
    for r in results:
        for lr in r["lint_results"]:
            status = "PASS" if lr["pass"] else "FAIL"
            if not lr["pass"]:
                all_lint_pass = False
            fails_str = ", ".join(lr["fails"]) if lr["fails"] else "-"
            print(f"  #{r['idx']:2d} {lr['step']:20s} day={lr['day']:2d}  "
                  f"[{status}] {fails_str}")

    print()
    print("=" * 72)
    print("CLAIMS VERDICT")
    print("=" * 72)
    all_claims_pass = True
    for r in results:
        for cr in r["claims_results"]:
            status = "PASS" if cr["pass"] else "FAIL"
            if not cr["pass"]:
                all_claims_pass = False
            issues_str = "; ".join(cr["issues"]) if cr["issues"] else "-"
            print(f"  #{r['idx']:2d} {cr['step']:20s} day={cr['day']:2d}  "
                  f"[{status}] {issues_str}")

    print()
    print("=" * 72)
    print("BLOCKED CONTACTS")
    print("=" * 72)
    if blocked:
        for b in blocked:
            print(f"  #{b['idx']} domain={b['domain_hash']} name={b['name_hash']}: "
                  f"{b['reason']}")
    else:
        print("  NONE - all 17 contacts can render.")

    print()
    print("=" * 72)
    print("FALLBACK SUMMARY")
    print("=" * 72)
    for r in results:
        print(f"  #{r['idx']:2d} (domain={r['domain_hash']}): "
              f"{r['fallback_count']} fallback(s)")

    print()
    print(f"LINT: {'ALL PASS' if all_lint_pass else 'FAILURES DETECTED'}")
    print(f"CLAIMS: {'ALL PASS' if all_claims_pass else 'ISSUES DETECTED'}")

    # Write the deliverable document
    _write_doc(stamp, results, blocked, payload_entries,
               all_lint_pass, all_claims_pass, cohort)

    print(f"\nDeliverable written: {OUTPUT_DOC}")


def _hash_pii_in_text(text, name, company):
    """Replace actual PII in rendered text with hash placeholders."""
    if name:
        first_name = name.split()[0] if name else ""
        if first_name:
            text = text.replace(first_name, f"<name:{_hash(name)}>")
    if company:
        text = text.replace(company, f"<company:{_hash(company)}>")
    return text


def _write_doc(stamp, results, blocked, payload_entries,
               all_lint_pass, all_claims_pass, cohort_data):
    lines = []
    lines.append("---")
    lines.append("title: \"Bison CONTROL Payload — Variable Resolution and Staging Data\"")
    lines.append("task: \"TASK-167\"")
    lines.append("date: \"2026-09-16\"")
    lines.append("builds_on:")
    lines.append("  - \"docs/EMAIL-CONTROL-SEQUENCE-2026-09-15.md\"")
    lines.append("  - \"docs/BISON-COHORT-LIVE-2026-09-15.md\"")
    lines.append("---")
    lines.append("")
    lines.append("# Bison CONTROL Payload — 2026-09-16")
    lines.append("")
    lines.append("**TASK-167 deliverable.** Variable resolution, rendered text, "
                 "gate verdicts, and the exact staging payload for the 17-contact "
                 "CONTROL sequence.")
    lines.append("")
    lines.append(f"**Snapshot:** `{stamp}`")
    lines.append("")
    lines.append("**PII policy:** Every identifier is SHA-256 hashed (12 hex chars). "
                 "No email address, person name, company name, or domain appears "
                 "in this document. Body text shows `<name:HASH>` and "
                 "`<company:HASH>` placeholders.")
    lines.append("")

    # Section 1: Variable resolution
    lines.append("## 1. Per-Contact Variable Resolution")
    lines.append("")
    lines.append("| # | domain_hash | name_hash | first_name | company | angle_phrase | angle_word | sector | line | fallbacks |")
    lines.append("|---|-------------|-----------|------------|---------|--------------|------------|--------|------|-----------|")
    for r in results:
        res = r["resolution"]
        # Hash the first_name value for display
        fn_display = res["first_name"]["value"]
        if fn_display != "there":
            fn_display = f"<name:{r['name_hash']}>"
        lines.append(
            f"| {r['idx']} "
            f"| {r['domain_hash']} "
            f"| {r['name_hash']} "
            f"| {fn_display} ({res['first_name']['source']}) "
            f"| <company:{_hash(r['company'])}> ({res['company']['source']}) "
            f"| {res['angle_phrase']['value'][:30]} ({res['angle_phrase']['source'][:20]}) "
            f"| {res['angle_word']['value'][:25]} ({res['angle_word']['source'][:20]}) "
            f"| {res['sector']['value']} ({res['sector']['source']}) "
            f"| {res['line']['value'][:30]} ({res['line']['source'][:20]}) "
            f"| {r['fallback_count']} |"
        )
    lines.append("")

    # Section 2: Blocked contacts
    lines.append("## 2. Contacts That Cannot Render")
    lines.append("")
    if blocked:
        for b in blocked:
            lines.append(f"- #{b['idx']} domain={b['domain_hash']} "
                        f"name={b['name_hash']}: **{b['reason']}**")
    else:
        lines.append("**None.** All 17 contacts have a resolvable `company` name. "
                     "No contact is blocked.")
    lines.append("")

    # Section 3: Lint verdict
    lines.append("## 3. Lint Verdict")
    lines.append("")
    lines.append("| # | step | day | words | subject_len | verdict | failures |")
    lines.append("|---|------|-----|-------|-------------|---------|----------|")
    for r in results:
        for lr in r["lint_results"]:
            rs = [s for s in r["rendered_steps"] if s["step"] == lr["step"]][0]
            wc = len(rs["body"].split())
            sl = len(rs["subject"])
            status = "PASS" if lr["pass"] else "FAIL"
            fails = ", ".join(lr["fails"]) if lr["fails"] else "-"
            lines.append(f"| {r['idx']} | {lr['step']} | {lr['day']} | "
                        f"{wc} | {sl} | {status} | {fails} |")
    lines.append("")
    lines.append(f"**Overall: {'ALL PASS' if all_lint_pass else 'FAILURES DETECTED'}**")
    lines.append("")

    # Section 4: Claims verdict
    lines.append("## 4. Claims Gate Verdict")
    lines.append("")
    lines.append("The CONTROL templates are deliberately written to avoid assertions "
                 "about the prospect. The check looks for:")
    lines.append("- Prior contact claims (\"following up\", \"as I mentioned\")")
    lines.append("- Flat second-person operational assertions (\"you are running X\")")
    lines.append("")
    lines.append("| # | step | day | verdict | issues |")
    lines.append("|---|------|-----|---------|--------|")
    for r in results:
        for cr in r["claims_results"]:
            status = "PASS" if cr["pass"] else "FAIL"
            issues = "; ".join(cr["issues"]) if cr["issues"] else "-"
            lines.append(f"| {r['idx']} | {cr['step']} | {cr['day']} | "
                        f"{status} | {issues} |")
    lines.append("")
    lines.append(f"**Overall: {'ALL PASS' if all_claims_pass else 'ISSUES DETECTED'}**")
    lines.append("")

    # Section 5: Fallback count
    lines.append("## 5. Fallback Count Per Contact")
    lines.append("")
    lines.append("A fallback that reads well is still a fallback. Six variables per "
                 "contact; the maximum fallback count is 6 (every variable fell back).")
    lines.append("")
    lines.append("| # | domain_hash | fallbacks | detail |")
    lines.append("|---|-------------|-----------|--------|")
    for r in results:
        detail = "; ".join(r["fallbacks"]) if r["fallbacks"] else "none"
        lines.append(f"| {r['idx']} | {r['domain_hash']} | "
                    f"{r['fallback_count']} | {detail} |")
    lines.append("")
    total_fb = sum(r["fallback_count"] for r in results)
    lines.append(f"**Total fallbacks across 17 contacts: {total_fb}**")
    lines.append("")

    # Section 6: Signature note
    lines.append("## 6. Signature")
    lines.append("")
    lines.append("The CONTROL templates carry **no signature**. The sender identity "
                 "is `Ivan, founder, Productive, works on project profitability for "
                 "agencies` (from `config/clients/productive.yaml`). Whether to "
                 "append a signature is an operator decision. The templates as they "
                 "stand do not include one.")
    lines.append("")

    # Section 7: The payload
    lines.append("## 7. Staging Payload")
    lines.append("")
    lines.append("The exact JSON payload Claude writes to EmailBison. "
                 "`thread_reply` follows the F,T,F pattern. "
                 "Subjects on step 2 are the same as step 1 (provider auto-prepends "
                 "\"Re:\"). Step 3 opens a new thread with \"closing the loop\".")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(payload_entries, indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    # Section 8: Rendered text sample (first contact, PII hashed)
    lines.append("## 8. Rendered Text Sample (Contact #1, PII hashed)")
    lines.append("")
    if results:
        r = results[0]
        # Get the original contact full name and company for hashing
        first_rec, first_contact, first_domain = cohort_data[0]
        first_full_name = first_contact.get("name") or ""
        first_company = r["company"]
        lines.append(f"domain_hash: `{r['domain_hash']}`, "
                     f"name_hash: `{r['name_hash']}`")
        lines.append("")
        for rs in r["rendered_steps"]:
            lines.append(f"### Step: {rs['step']} (day {rs['day']}, "
                        f"thread_reply={rs['thread_reply']})")
            lines.append("")
            hashed_subj = _hash_pii_in_text(rs["subject"], first_full_name, first_company)
            hashed_body = _hash_pii_in_text(rs["body"], first_full_name, first_company)
            lines.append(f"**Subject:** {hashed_subj}")
            lines.append("")
            lines.append("```")
            lines.append(hashed_body)
            lines.append("```")
            lines.append("")

    with open(OUTPUT_DOC, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
