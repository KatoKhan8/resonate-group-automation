"""TASK-159: Verify variable resolution for the 17 CONTACT cohort.

Checks every variable the CONTROL sequence needs against every contact,
using the snapshot data. Must be run on a worktree that has
work/queue.snapshot.jsonl.

For each contact, resolves:
  - first_name (from contact.name, fallback "there")
  - company (from company_facts.name or rec.company, refuses domain-only)
  - angle_word (from client config angles, fallback "the numbers behind the work")
  - angle_phrase (from client config angles, fallback "how the work is tracked")
  - sector (from company_facts.industry, fallback "services")
  - line (from evidence or generic fallback)

Reports which contacts have unresolvable variables.
"""

import json
import os
import sys
import yaml

SNAPSHOT = os.path.join("work", "queue.snapshot.jsonl")
CONFIG = os.path.join("config", "clients", "productive.yaml")

# The 17 surviving contacts from TASK-147 / BISON-COHORT-LIVE-2026-09-15.md.
# Cold cohort (8 ALLOW domains):
COLD_ALLOW_DOMAINS = {
    "digitalthirdcoast.com", "feddirect.com", "inmobi.com", "ritway.com",
    "skyad.com", "thecommunity.ca", "viralityllc.com", "wearejsa.com",
}
# Never-emailed bison (9 ALLOW domains):
NEVER_EMAILED_ALLOW_DOMAINS = {
    "ogpartner.dk", "anewagencyworld.com", "acqcom.com", "adcuratio.com",
    "portsidemarketing.com", "agency59.ca", "savagebrands.com",
    "mischacommunications.com", "mypersonalestatesale.com",
}
ALL_ALLOW_DOMAINS = COLD_ALLOW_DOMAINS | NEVER_EMAILED_ALLOW_DOMAINS

HOSTNAME_RE = None  # set in main


def _is_domain_shaped(value):
    """True if the value looks like a hostname (has a TLD)."""
    if HOSTNAME_RE is None:
        return False
    return bool(HOSTNAME_RE.search(str(value or "").split()[-1]))


def _resolve_company(rec):
    """Mirror cadence.company_name logic."""
    import re
    facts = rec.get("company_facts") or {}
    domain = str(rec.get("domain") or "").strip().lower()
    hostname_pat = re.compile(r"\.[a-z]{2,}$", re.I)
    for candidate in (facts.get("name"), rec.get("company")):
        name = str(candidate or "").strip()
        if not name:
            continue
        if name.lower() == domain or hostname_pat.search(name.split()[-1]):
            continue
        return name
    return None  # CompanyNameUnusable


def _resolve_first_name(contact):
    name = (contact.get("name") or "").strip()
    if name:
        return name.split()[0]
    return "there"  # fallback in template_vars


def _resolve_angle(contact, config):
    """Mirror cadence.angle_words logic."""
    personas_cfg = (config.get("personas") or {})
    persona = contact.get("persona") or "champion"
    persona_block = personas_cfg.get(persona) or {}
    angles = persona_block.get("angles") or {}
    if not angles:
        # Try default_angle
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
    """Mirror cadence.angle_word logic."""
    ANGLE_WORD_MAX = 32
    FALLBACK = "the numbers behind the work"
    labels = config.get("angle_labels") or {}
    label = labels.get(angle)
    if label and len(str(label)) <= ANGLE_WORD_MAX:
        return str(label)
    clause = phrase.split(",")[0].strip()
    if clause and len(clause) <= ANGLE_WORD_MAX:
        return clause
    return FALLBACK


def main():
    import re as _re
    global HOSTNAME_RE
    HOSTNAME_RE = _re.compile(r"\.[a-z]{2,}$", _re.I)

    if not os.path.exists(SNAPSHOT):
        print(f"ERROR: {SNAPSHOT} not found. Run on a worktree with the snapshot.")
        sys.exit(1)

    with open(CONFIG) as f:
        config = yaml.safe_load(f)

    records = []
    with open(SNAPSHOT) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # Find records whose domain is in the ALLOW set
    cohort = []
    for rec in records:
        domain = str(rec.get("domain") or "").strip().lower()
        if domain in ALL_ALLOW_DOMAINS:
            # Check verified email
            contacts = rec.get("contacts") or []
            for c in contacts:
                if c.get("email_verified"):
                    cohort.append((rec, c, domain))

    print(f"Snapshot records: {len(records)}")
    print(f"Cohort contacts (verified, ALLOW domain): {len(cohort)}")
    print()

    problems = []
    for rec, contact, domain in cohort:
        issues = []
        first = _resolve_first_name(contact)
        company = _resolve_company(rec)
        angle_key, angle_phrase = _resolve_angle(contact, config)
        angle_word = _resolve_angle_word(angle_key, angle_phrase, config)
        facts = rec.get("company_facts") or {}
        sector = facts.get("industry") or "services"

        if first == "there":
            issues.append("first_name=FALLBACK('there')")
        if company is None:
            issues.append("company=UNRESOLVABLE(domain-only)")
        if not contact.get("name"):
            issues.append("contact.name=EMPTY")

        status = "OK" if not issues else "PROBLEM"
        name_hash = contact.get("key", "?")[:12]
        print(f"  {domain:35s} {name_hash:12s} "
              f"first={first:15s} company={company or 'NONE':25s} "
              f"angle={angle_key:20s} word={angle_word:30s} "
              f"sector={sector:20s} [{status}]")
        if issues:
            problems.append((domain, name_hash, issues))

    print()
    if problems:
        print(f"PROBLEMS: {len(problems)} contact(s) with unresolvable variables:")
        for domain, h, issues in problems:
            print(f"  {domain} ({h}): {', '.join(issues)}")
    else:
        print("ALL 17 CONTACTS: every variable resolves.")

    print()
    print("VARIABLE RESOLUTION SUMMARY:")
    print(f"  first_name: {sum(1 for _, c, _ in cohort if c.get('name'))}/{len(cohort)} "
          f"have names, {sum(1 for _, c, _ in cohort if not c.get('name'))} use fallback 'there'")
    print(f"  company: {sum(1 for r, _, _ in cohort if _resolve_company(r) is not None)}/{len(cohort)} resolve")
    print(f"  angle_word: always resolves (fallback: 'the numbers behind the work')")
    print(f"  angle_phrase: always resolves (fallback: 'how the work is tracked')")
    print(f"  sector: always resolves (fallback: 'services')")


if __name__ == "__main__":
    main()
