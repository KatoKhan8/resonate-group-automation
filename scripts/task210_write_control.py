"""TASK-210: Write CONTROL copy into em1-em3 for the 11 records.

Renders the CONTROL sequence (persona_pain, comparable_proof, breakup)
for each of the 11 contacts, writes it into the record's cadence,
removes stale claude approvals, and backs up the old copy.
"""

import hashlib
import json
import os
import re
import sys
import yaml

# Add parent to path so we can import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import store


def h(value):
    """SHA-256 prefix for PII hashing."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


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

# Sequence: step name, day, thread_reply, wait
STEPS = [
    ("persona_pain", "em1", 1, False, 3),
    ("comparable_proof", "em2", 5, True, 4),
    ("breakup", "em3", 21, False, 0),
]

# Lint constants
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

HOSTNAME_RE = re.compile(r"\.[a-z]{2,}$", re.I)
ANGLE_WORD_MAX = 32
FALLBACK_ANGLE_WORD = "the numbers behind the work"


def lint_check(subject, body):
    """Mirror the email-relevant subset of lint.check."""
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


def claims_check(body, company, sector):
    """Lightweight claims check."""
    issues = []
    low = body.lower()
    prior_contact_phrases = [
        "following up", "as i mentioned", "i wrote to you",
        "my last email", "my last message", "our previous",
        "i have written", "not heard back",
    ]
    for phrase in prior_contact_phrases:
        if phrase in low:
            issues.append(f"prior_contact_claim: '{phrase}'")
    operational_terms = [
        "utilisation", "margin", "capacity", "resourcing",
        "billing", "invoicing", "profitability",
    ]
    sentences = re.split(r"[.!?]\s", body)
    for sent in sentences:
        slow = sent.lower().strip()
        if not slow:
            continue
        if "?" in sent:
            continue
        if any(hedge in slow for hedge in ["if ", "whether", "might", "could",
                                            "tend to", "usually", "most teams"]):
            continue
        if "you are" in slow or "you're" in slow:
            for term in operational_terms:
                if term in slow:
                    issues.append(f"operational_assertion: '{sent.strip()[:80]}'")
                    break
    return issues


def resolve_company(rec):
    """Mirror cadence.company_name."""
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


def resolve_first_name(contact):
    name = (contact.get("name") or "").strip()
    if name:
        return name.split()[0]
    return None


def resolve_angle(contact, config):
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


def resolve_angle_word(angle, phrase, config):
    """Mirror cadence.angle_word."""
    labels = config.get("angle_labels") or {}
    label = labels.get(str(angle or "").strip().lower())
    if label and len(str(label)) <= ANGLE_WORD_MAX:
        return str(label)
    if phrase and len(phrase) <= ANGLE_WORD_MAX:
        return phrase
    return FALLBACK_ANGLE_WORD


def render_control(contact, rec, config):
    """Render the CONTROL sequence for one contact."""
    first = resolve_first_name(contact)
    if first is None:
        first = "there"

    company = resolve_company(rec)
    if company is None:
        return None, "company_unresolvable"

    angle_key, angle_phrase = resolve_angle(contact, config)
    angle_word = resolve_angle_word(angle_key, angle_phrase, config)

    facts = rec.get("company_facts") or {}
    sector = facts.get("industry") or "services"

    # Line: evidence or generic
    contact_key = contact.get("key") or h(contact.get("name", ""))
    evidence = (rec.get("evidence") or {}).get(contact_key) or []
    if evidence:
        line = str(evidence[0]).rstrip(".")
    else:
        line = (f"I work with {sector} teams on {angle_phrase}, "
                f"and I do not know how {company} handles it")

    values = {
        "first_name": first,
        "company": company,
        "angle": angle_key,
        "angle_word": angle_word,
        "angle_phrase": angle_phrase,
        "sector": sector,
        "line": line,
    }

    rendered = []
    for step_name, em_key, day, thread_reply, wait in STEPS:
        tmpl = TEMPLATES[step_name]
        subject = tmpl["subject"].format(**values)
        body = tmpl["body"].format(**values)
        rendered.append({
            "em_key": em_key,
            "step_name": step_name,
            "day": day,
            "thread_reply": thread_reply,
            "wait": wait,
            "subject": subject,
            "body": body,
        })

    return rendered, None


def main():
    # Load matched contacts
    with open("scripts/task210_matched.json", encoding="utf-8") as f:
        matched = json.load(f)

    # Load client config
    with open("config/clients/productive.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Backup file
    backup = []
    results = []

    # Use store.transaction for proper locking and guards
    with store.transaction() as recs:
        rec_by_id = {r["id"]: r for r in recs}

        for m in matched:
            rec_id = m["record_id"]
            contact_key = m["contact_key"]
            rec = rec_by_id.get(rec_id)
            if not rec:
                print(f"ERROR: record {rec_id} not found")
                continue

            # Find the contact
            contact = None
            for c in rec.get("contacts", []):
                if c.get("key") == contact_key:
                    contact = c
                    break
            if not contact:
                print(f"ERROR: contact {contact_key} not found on {rec_id}")
                continue

            # Get current cadence for this contact
            cadence = rec.get("cadence", {})
            contact_cadence = cadence.get(contact_key, {})

            # Backup em1-em3
            backup_entry = {
                "record_id": rec_id,
                "contact_key": contact_key,
                "rec_id_hash": m["rec_id_hash"],
                "contact_hash": m["contact_hash"],
                "old_steps": {},
            }
            for em_key in ["em1", "em2", "em3"]:
                old_step = contact_cadence.get(em_key, {})
                backup_entry["old_steps"][em_key] = {
                    "subject": old_step.get("subject", ""),
                    "body": old_step.get("body", ""),
                    "approval": old_step.get("approval"),
                }
            backup.append(backup_entry)

            # Render CONTROL
            rendered, error = render_control(contact, rec, config)
            if error:
                print(f"ERROR rendering for {rec_id}: {error}")
                results.append({
                    "record_id": rec_id,
                    "contact_key": contact_key,
                    "status": "ERROR",
                    "error": error,
                })
                continue

            # Write CONTROL into em1-em3
            for step in rendered:
                em_key = step["em_key"]

                # Build new step matching the stored step structure:
                # channel, generated, subject, body. No approval field.
                # thread_reply and wait_in_days are campaign-level config,
                # not stored on the record's cadence step.
                new_step = {
                    "channel": "email",
                    "generated": True,
                    "subject": step["subject"],
                    "body": step["body"],
                }
                # Do NOT set approval - the stale claude approval is removed
                contact_cadence[em_key] = new_step

            # Write back
            cadence[contact_key] = contact_cadence
            rec["cadence"] = cadence

            # Lint and claims check
            step_results = []
            for step in rendered:
                lint_fails = lint_check(step["subject"], step["body"])
                claims_issues = claims_check(step["body"],
                                             resolve_company(rec),
                                             (rec.get("company_facts") or {}).get("industry") or "services")
                step_results.append({
                    "em_key": step["em_key"],
                    "step_name": step["step_name"],
                    "lint_pass": len(lint_fails) == 0,
                    "lint_fails": lint_fails,
                    "claims_pass": len(claims_issues) == 0,
                    "claims_issues": claims_issues,
                })

            results.append({
                "record_id": rec_id,
                "contact_key": contact_key,
                "rec_id_hash": m["rec_id_hash"],
                "contact_hash": m["contact_hash"],
                "status": "OK",
                "steps": step_results,
            })

    # Transaction context manager writes the queue on exit

    # Write backup
    with open("scripts/task210_backup.json", "w", encoding="utf-8") as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)
    print(f"Wrote backup to scripts/task210_backup.json")

    print(f"Saved queue with {len(recs)} records")

    # Print results
    print()
    print("=" * 72)
    print("RESULTS")
    print("=" * 72)
    for r in results:
        if r["status"] == "ERROR":
            print(f"  {r['record_id']}: ERROR - {r.get('error')}")
        else:
            all_lint = all(s["lint_pass"] for s in r["steps"])
            all_claims = all(s["claims_pass"] for s in r["steps"])
            print(f"  {r['rec_id_hash']} / {r['contact_hash']}: "
                  f"lint={'PASS' if all_lint else 'FAIL'} "
                  f"claims={'PASS' if all_claims else 'FAIL'}")
            for s in r["steps"]:
                lint_str = ", ".join(s["lint_fails"]) if s["lint_fails"] else "-"
                claims_str = "; ".join(s["claims_issues"]) if s["claims_issues"] else "-"
                print(f"    {s['em_key']} ({s['step_name']}): "
                      f"lint=[{lint_str}] claims=[{claims_str}]")

    # Summary
    ok_count = sum(1 for r in results if r["status"] == "OK")
    err_count = sum(1 for r in results if r["status"] == "ERROR")
    all_lint_pass = all(
        all(s["lint_pass"] for s in r["steps"])
        for r in results if r["status"] == "OK"
    )
    all_claims_pass = all(
        all(s["claims_pass"] for s in r["steps"])
        for r in results if r["status"] == "OK"
    )
    print()
    print(f"OK: {ok_count}, ERROR: {err_count}")
    print(f"LINT: {'ALL PASS' if all_lint_pass else 'FAILURES'}")
    print(f"CLAIMS: {'ALL PASS' if all_claims_pass else 'ISSUES'}")


if __name__ == "__main__":
    main()
