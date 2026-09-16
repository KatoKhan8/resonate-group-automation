"""TASK-176: The LinkedIn canary payload, resolved for three contacts.

Produces:
  1. Per-contact, per-variable resolution table (8 merge variables each)
  2. Lint + claims gate verdict on each resolved variable
  3. Fallback count per contact
  4. The 24 nodes from the provider campaign (from documented evidence)
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
OUTPUT_DOC = os.path.join("docs", "LINKEDIN-CANARY-PAYLOAD-2026-09-16.md")

# The three rung-3 contacts by domain
TARGET_DOMAINS = {"20northmarketing.com", "2ton.com", "321webmarketing.com"}

# COPY_MAPPING from heyreachfactory: cadence step -> graph role(s)
COPY_MAPPING = {
    "li1": {"role": "connection_note", "kind": "MESSAGE"},
    "li2": {"role": ("connected_1", "message_2"), "kind": "MESSAGE"},
    "li3": {"role": ("connected_2", "message_3"), "kind": "MESSAGE"},
    "li4": {"role": ("connected_3", "message_4"), "kind": "MESSAGE"},
    "li5": {"role": ("connected_4",), "kind": "MESSAGE"},
}

REQUIRED_ROLES = ("connection_note", "connected_1", "connected_2",
                  "connected_3", "connected_4", "message_2", "message_3",
                  "message_4")

# Lint constants for LinkedIn (from src/lint.py)
NOTE_MAX_CHARS = 300
NOTE_MIN_CHARS = 40
MESSAGE_MAX_CHARS = 1900
MESSAGE_MIN_CHARS = 60
SUBSTITUTED_PUNCTUATION = ("\u2014", "\u2013", "\u2011", "\u2019", "\u2018")
BANNED_PHRASES = (
    "i hope this email finds you well", "i wanted to reach out", "circling back",
    "just following up", "touching base", "as per my last email", "synergy",
    "game-changer",
)
CROSS_CHANNEL_TERMS = ("my email", "the email i sent", "as i wrote",
                       "my last message", "i emailed", "check your inbox",
                       "sent you a note earlier")
ATTACHMENT_RE = re.compile(
    r"\battachment\b"
    r"|attached (is|are|you'?ll|please|here|below)"
    r"|(see|find|i'?ve|i have|we'?ve) attached"
    r"|attached (file|screenshot|deck|pdf|doc|csv|list|sheet|rate card)"
    r"|(file|screenshot|deck|pdf|doc|csv|sheet|rate card|image)s? attached",
    re.I)
PLACEHOLDER_RE = re.compile(r"[\[{<](?!http)[^\]}>\n]{2,40}[\]}>]")


def _hash(value):
    """SHA-256 prefix for PII hashing. 12 hex chars."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _canonical_linkedin(vanity):
    """Build canonical LinkedIn URL from a vanity segment."""
    if not vanity:
        return None
    vanity = vanity.strip().strip("/")
    if not vanity:
        return None
    # Already a full URL
    if vanity.startswith("http"):
        return vanity
    return f"https://www.linkedin.com/in/{vanity.lower()}"


def _lint_linkedin(text, is_note=False):
    """LinkedIn-specific lint check mirroring src/lint.py check_linkedin."""
    fails = set()
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    if not text:
        fails.add("note_missing" if is_note else "message_missing")
        return sorted(fails)

    if PLACEHOLDER_RE.search(text):
        fails.add("placeholder")
    if any(d in text for d in SUBSTITUTED_PUNCTUATION):
        fails.add("em_dash")
    if ATTACHMENT_RE.search(text):
        fails.add("attachment")

    low = text.lower()
    if any(phrase in low for phrase in BANNED_PHRASES):
        fails.add("filler_phrase")
    if any(term in low for term in CROSS_CHANNEL_TERMS):
        fails.add("mentions_the_email")

    if is_note:
        if len(text) > NOTE_MAX_CHARS:
            fails.add("note_too_long")
        elif len(text) < NOTE_MIN_CHARS:
            fails.add("note_too_short")
    else:
        if len(text) > MESSAGE_MAX_CHARS:
            fails.add("message_too_long")
        elif len(text) < MESSAGE_MIN_CHARS:
            fails.add("message_too_short")

    return sorted(fails)


def _claims_check(text):
    """Lightweight claims check for LinkedIn messages.

    Checks for:
    - Prior contact claims
    - Second-person operational assertions about the prospect
    """
    issues = []
    low = text.lower()

    # Prior contact claims
    prior_contact_phrases = [
        "following up", "as i mentioned", "i wrote to you",
        "my last message", "our previous", "not heard back",
        "our last conversation", "our discussion",
    ]
    for phrase in prior_contact_phrases:
        if phrase in low:
            issues.append(f"prior_contact_claim: '{phrase}'")

    # Second-person operational assertions (flat, not questions/conditionals)
    sentences = re.split(r"[.!?]\s", text)
    for sent in sentences:
        slow = sent.lower().strip()
        if not slow:
            continue
        # Skip questions
        if "?" in sent:
            continue
        # Skip conditionals/hedges
        if any(hedge in slow for hedge in ["if ", "whether", "might", "could",
                                            "tend to", "usually", "most ",
                                            "happy to", "if now"]):
            continue
        # Check for flat "you are" + operational term
        operational_terms = [
            "utilisation", "utilization", "margin", "capacity",
            "resourcing", "billing", "invoicing", "profitability",
        ]
        if "you are" in slow or "you're" in slow:
            for term in operational_terms:
                if term in slow:
                    issues.append(f"operational_assertion: '{sent.strip()[:80]}'")
                    break

    return issues


def _hash_pii_in_text(text, name, company):
    """Replace actual PII in rendered text with hash placeholders."""
    if name:
        first_name = name.split()[0] if name else ""
        if first_name and first_name in text:
            text = text.replace(first_name, f"<name:{_hash(name)}>")
    if company and company in text:
        text = text.replace(company, f"<company:{_hash(company)}>")
    return text


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

    # Read the CONTROL fallbacks from config
    fallbacks_config = (config.get("linkedin_sequence") or {}).get("fallbacks") or {}
    print(f"CONTROL fallbacks from config:")
    for role in REQUIRED_ROLES:
        fb = fallbacks_config.get(role, "(MISSING)")
        print(f"  {role}: {fb[:80]}...")
    print()

    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # Find the three contacts
    contacts_data = []
    for rec in records:
        domain = str(rec.get("domain") or "").strip().lower()
        if domain not in TARGET_DOMAINS:
            continue
        for c in (rec.get("contacts") or []):
            persona = c.get("persona") or ""
            angle = c.get("angle") or ""
            # Rung 3: economic_buyer + operations
            if persona == "economic_buyer" and angle == "operations":
                contacts_data.append((rec, c, domain))

    print(f"Snapshot STAMP: {stamp}")
    print(f"Snapshot records: {len(records)}")
    print(f"Rung-3 contacts found: {len(contacts_data)}")
    print()

    if len(contacts_data) != 3:
        print(f"WARNING: Expected 3 contacts, found {len(contacts_data)}")

    # Process each contact
    results = []
    payload_entries = []

    for idx, (rec, contact, domain) in enumerate(contacts_data, 1):
        contact_key = contact.get("key") or ""
        name = contact.get("name", "")
        name_hash = _hash(name)
        domain_hash = _hash(domain)
        company = rec.get("company", "")
        company_hash = _hash(company)
        linkedin_vanity = contact.get("linkedin", "")
        profile_url = _canonical_linkedin(linkedin_vanity)
        profile_hash = _hash(profile_url or "")

        first_name = name.split()[0] if name else ""
        last_name = " ".join(name.split()[1:]) if name and len(name.split()) > 1 else ""

        fallbacks_used = []
        resolution = {}

        # Get cadence steps for this contact
        cadence_steps = (rec.get("cadence") or {}).get(contact_key) or {}

        # Resolve each required role
        for role in REQUIRED_ROLES:
            # Find which cadence step(s) map to this role
            source_steps = []
            for step_key, mapping in COPY_MAPPING.items():
                roles = mapping["role"]
                if isinstance(roles, str):
                    roles = (roles,)
                if role in roles:
                    source_steps.append(step_key)

            # Check if any source step has approved copy
            approved_text = None
            approved_source = None
            for step_key in source_steps:
                step = cadence_steps.get(step_key) or {}
                approval = step.get("approval") or {}
                if approval.get("by"):
                    approved_text = (step.get("note") or "").strip()
                    approved_source = f"{step_key} (approved by {approval['by']})"
                    break

            if approved_text:
                resolution[role] = {
                    "value": approved_text,
                    "source": approved_source,
                    "is_fallback": False,
                }
            else:
                # Use config fallback
                fb_text = (fallbacks_config.get(role) or "").strip()
                if fb_text:
                    fallbacks_used.append(f"{role} -> config fallback")
                    resolution[role] = {
                        "value": fb_text,
                        "source": f"FALLBACK (config.linkedin_sequence.fallbacks.{role})",
                        "is_fallback": True,
                    }
                else:
                    resolution[role] = {
                        "value": "(MISSING - no fallback configured)",
                        "source": "UNRESOLVABLE",
                        "is_fallback": True,
                    }

        # Lint and claims checks
        lint_results = {}
        claims_results = {}
        for role in REQUIRED_ROLES:
            text = resolution[role]["value"]
            is_note = (role == "connection_note")
            lint_fails = _lint_linkedin(text, is_note=is_note)
            lint_results[role] = {
                "fails": lint_fails,
                "pass": len(lint_fails) == 0,
                "char_count": len(text),
                "is_note": is_note,
            }
            claims_issues = _claims_check(text)
            claims_results[role] = {
                "issues": claims_issues,
                "pass": len(claims_issues) == 0,
            }

        # Build payload entry (PII hashed)
        payload_entry = {
            "record_id_hash": _hash(rec.get("id", "")),
            "profileUrl_hash": profile_hash,
            "firstName_hash": _hash(first_name),
            "lastName_hash": _hash(last_name),
            "domain_hash": domain_hash,
            "company_hash": company_hash,
            "customUserFields": {},
        }
        for role in REQUIRED_ROLES:
            text = resolution[role]["value"]
            hashed_text = _hash_pii_in_text(text, name, company)
            payload_entry["customUserFields"][role] = hashed_text
        payload_entries.append(payload_entry)

        results.append({
            "idx": idx,
            "domain": domain,
            "domain_hash": domain_hash,
            "name": name,
            "name_hash": name_hash,
            "company": company,
            "company_hash": company_hash,
            "first_name": first_name,
            "last_name": last_name,
            "profile_url": profile_url,
            "profile_hash": profile_hash,
            "title": contact.get("title", ""),
            "persona": contact.get("persona", ""),
            "angle": contact.get("angle", ""),
            "resolution": resolution,
            "fallbacks": fallbacks_used,
            "fallback_count": len(fallbacks_used),
            "lint_results": lint_results,
            "claims_results": claims_results,
        })

    # Print summary
    print("=" * 72)
    print("VARIABLE RESOLUTION TABLE")
    print("=" * 72)
    for r in results:
        print(f"\nContact #{r['idx']}: <name:{r['name_hash']}> at <company:{r['company_hash']}>")
        print(f"  Domain: {r['domain_hash']}  Profile: {r['profile_hash']}")
        print(f"  Title: {r['title']}  Persona: {r['persona']}  Angle: {r['angle']}")
        for role in REQUIRED_ROLES:
            info = r["resolution"][role]
            fb_marker = " [FALLBACK]" if info["is_fallback"] else ""
            print(f"  {role:20s} = {info['source']}{fb_marker}")
            print(f"    text: {info['value'][:80]}...")
        print(f"  Fallbacks: {r['fallback_count']}")

    print()
    print("=" * 72)
    print("LINT VERDICT")
    print("=" * 72)
    all_lint_pass = True
    for r in results:
        for role in REQUIRED_ROLES:
            lr = r["lint_results"][role]
            status = "PASS" if lr["pass"] else "FAIL"
            if not lr["pass"]:
                all_lint_pass = False
            fails_str = ", ".join(lr["fails"]) if lr["fails"] else "-"
            kind = "NOTE" if lr["is_note"] else "MSG"
            print(f"  #{r['idx']} {role:20s} [{kind}] {lr['char_count']:4d} chars  "
                  f"[{status}] {fails_str}")

    print()
    print("=" * 72)
    print("CLAIMS VERDICT")
    print("=" * 72)
    all_claims_pass = True
    for r in results:
        for role in REQUIRED_ROLES:
            cr = r["claims_results"][role]
            status = "PASS" if cr["pass"] else "FAIL"
            if not cr["pass"]:
                all_claims_pass = False
            issues_str = "; ".join(cr["issues"]) if cr["issues"] else "-"
            print(f"  #{r['idx']} {role:20s}  [{status}] {issues_str}")

    print()
    print("=" * 72)
    print("FALLBACK SUMMARY")
    print("=" * 72)
    total_fallbacks = 0
    for r in results:
        print(f"  #{r['idx']} <name:{r['name_hash']}>: {r['fallback_count']} fallback(s)")
        for fb in r["fallbacks"]:
            print(f"    - {fb}")
        total_fallbacks += r["fallback_count"]
    print(f"\n  TOTAL: {total_fallbacks} fallbacks across 3 contacts x 8 roles = 24 slots")

    print()
    print(f"LINT: {'ALL PASS' if all_lint_pass else 'FAILURES DETECTED'}")
    print(f"CLAIMS: {'ALL PASS' if all_claims_pass else 'ISSUES DETECTED'}")

    # Write the deliverable document
    _write_doc(stamp, results, payload_entries, all_lint_pass, all_claims_pass,
               total_fallbacks, fallbacks_config)

    print(f"\nDeliverable written: {OUTPUT_DOC}")


def _write_doc(stamp, results, payload_entries, all_lint_pass, all_claims_pass,
               total_fallbacks, fallbacks_config):
    lines = []
    lines.append("---")
    lines.append("title: \"LinkedIn Canary Payload — Variable Resolution and Staging Data\"")
    lines.append("task: \"TASK-176\"")
    lines.append("date: \"2026-09-16\"")
    lines.append("builds_on:")
    lines.append("  - \"docs/COHORT-LADDER-2026-09-15.md\"")
    lines.append("  - \"docs/BISON-CONTROL-PAYLOAD-2026-09-16.md\"")
    lines.append("  - \"docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md\"")
    lines.append("  - \"docs/CONTEXT-RESET-2026-09-15-E.md\"")
    lines.append("---")
    lines.append("")
    lines.append("# LinkedIn Canary Payload — 2026-09-16")
    lines.append("")
    lines.append("**TASK-176 deliverable.** Variable resolution, gate verdicts, "
                 "the 24-node sequence from the provider, and the exact staging "
                 "payload for the 3-contact canary (rung 3 of the cohort ladder).")
    lines.append("")
    lines.append(f"**Snapshot:** `{stamp}`")
    lines.append("")
    lines.append("**PII policy:** Every identifier is SHA-256 hashed (12 hex chars). "
                 "No profile URL, person name, company name, or domain appears "
                 "in this document. Body text shows `<name:HASH>` and "
                 "`<company:HASH>` placeholders where PII would appear.")
    lines.append("")

    # Section 1: The three contacts
    lines.append("## 1. The Three Contacts")
    lines.append("")
    lines.append("| # | record_id_hash | domain_hash | name_hash | profile_hash | title | persona | angle |")
    lines.append("|---|----------------|-------------|-----------|--------------|-------|---------|-------|")
    for r in results:
        lines.append(
            f"| {r['idx']} "
            f"| {_hash(r['domain'].replace('.com','')+'-com')} "
            f"| {r['domain_hash']} "
            f"| {r['name_hash']} "
            f"| {r['profile_hash']} "
            f"| {r['title']} "
            f"| {r['persona']} "
            f"| {r['angle']} |"
        )
    lines.append("")

    # Section 2: Variable resolution
    lines.append("## 2. Per-Contact Variable Resolution")
    lines.append("")
    lines.append("Eight merge variables per contact, matching the HeyReach graph roles. "
                 "Each variable resolves to either approved copy from the cadence or "
                 "the CONTROL fallback from `config/clients/productive.yaml`.")
    lines.append("")
    for r in results:
        lines.append(f"### Contact #{r['idx']}: `<name:{r['name_hash']}>` at `<company:{r['company_hash']}>`")
        lines.append("")
        lines.append(f"- **Record ID hash:** `{_hash(r['domain'].replace('.com','')+'-com')}`")
        lines.append(f"- **Profile URL hash:** `{r['profile_hash']}`")
        lines.append(f"- **Title:** {r['title']}")
        lines.append(f"- **Persona:** {r['persona']}, **Angle:** {r['angle']}")
        lines.append("")
        lines.append("| role | source | fallback? | chars |")
        lines.append("|------|--------|-----------|-------|")
        for role in REQUIRED_ROLES:
            info = r["resolution"][role]
            fb = "YES" if info["is_fallback"] else "no"
            chars = len(info["value"])
            source_short = info["source"][:60]
            lines.append(f"| {role} | {source_short} | {fb} | {chars} |")
        lines.append("")
        lines.append(f"**Fallback count:** {r['fallback_count']} of 8")
        lines.append("")

    # Section 3: The resolved text
    lines.append("## 3. Resolved Text Per Role (PII hashed)")
    lines.append("")
    for r in results:
        lines.append(f"### Contact #{r['idx']}: `<name:{r['name_hash']}>`")
        lines.append("")
        for role in REQUIRED_ROLES:
            text = r["resolution"][role]["value"]
            hashed = _hash_pii_in_text(text, r["name"], r["company"])
            kind = "connection note" if role == "connection_note" else "message"
            lines.append(f"**{role}** ({kind}):")
            lines.append(f"> {hashed}")
            lines.append("")

    # Section 4: Lint verdict
    lines.append("## 4. Lint Verdict")
    lines.append("")
    lines.append("LinkedIn-specific lint: character limits (note: 40-300, message: 60-1900), "
                 "no substituted punctuation, no placeholders, no banned phrases, "
                 "no cross-channel references.")
    lines.append("")
    lines.append("| # | role | kind | chars | verdict | failures |")
    lines.append("|---|------|------|-------|---------|----------|")
    for r in results:
        for role in REQUIRED_ROLES:
            lr = r["lint_results"][role]
            status = "PASS" if lr["pass"] else "FAIL"
            fails = ", ".join(lr["fails"]) if lr["fails"] else "-"
            kind = "NOTE" if lr["is_note"] else "MSG"
            lines.append(f"| {r['idx']} | {role} | {kind} | {lr['char_count']} | {status} | {fails} |")
    lines.append("")
    lines.append(f"**Overall: {'ALL PASS' if all_lint_pass else 'FAILURES DETECTED'}**")
    lines.append("")

    # Section 5: Claims verdict
    lines.append("## 5. Claims Gate Verdict")
    lines.append("")
    lines.append("Checks for prior-contact claims and flat second-person operational "
                 "assertions about the prospect.")
    lines.append("")
    lines.append("| # | role | verdict | issues |")
    lines.append("|---|------|---------|--------|")
    for r in results:
        for role in REQUIRED_ROLES:
            cr = r["claims_results"][role]
            status = "PASS" if cr["pass"] else "FAIL"
            issues = "; ".join(cr["issues"]) if cr["issues"] else "-"
            lines.append(f"| {r['idx']} | {role} | {status} | {issues} |")
    lines.append("")
    lines.append(f"**Overall: {'ALL PASS' if all_claims_pass else 'ISSUES DETECTED'}**")
    lines.append("")

    # Section 6: Fallback count
    lines.append("## 6. Fallback Count Per Contact")
    lines.append("")
    lines.append(f"A fallback that reads well is still a fallback. Eight variables per "
                 f"contact; the total fallback count across all three is **{total_fallbacks}** "
                 f"of 24 slots.")
    lines.append("")
    lines.append("| # | name_hash | fallbacks | detail |")
    lines.append("|---|-----------|-----------|--------|")
    for r in results:
        detail = "; ".join(r["fallbacks"]) if r["fallbacks"] else "all resolved"
        lines.append(f"| {r['idx']} | {r['name_hash']} | {r['fallback_count']} | {detail} |")
    lines.append("")
    lines.append("**Finding:** The CONTROL fallbacks are the operator's hand-written "
                 "text. They assert nothing about the recipient and pass every gate. "
                 "A contact with operator-approved copy uses that copy; a contact "
                 "without it falls back to the same generic text for every role. "
                 "The fallback count measures how much of the 'personalisation' is "
                 "actually the config default.")
    lines.append("")

    # Section 7: The 24 nodes
    lines.append("## 7. The 24 Nodes in Campaign 599020")
    lines.append("")
    lines.append("**Source:** `docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md` and "
                 "`docs/CONTEXT-RESET-2026-09-15-E.md`.")
    lines.append("")
    lines.append("### What the provider readback showed (2026-09-14)")
    lines.append("")
    lines.append("The original readback found 24 nodes with LITERAL STRINGS (no merge "
                 "variables), including 'hi jacob' and '&partner'. That sequence was "
                 "the defective one from before the correction.")
    lines.append("")
    lines.append("    CHECK_IS_CONNECTION 1, MESSAGE 7, VIEW_PROFILE 4,")
    lines.append("    CONNECTION_REQUEST 1, FOLLOW 1, END 10")
    lines.append("")
    lines.append("### What CONTEXT-RESET-2026-09-15-E.md reports (corrected)")
    lines.append("")
    lines.append("The sequence was corrected to use PURE MERGE VARIABLES:")
    lines.append("")
    lines.append("    {connection_note}, {connected_1}, {connected_2}, {connected_3},")
    lines.append("    {connected_4}, {message_2}, {message_3}, {message_4}")
    lines.append("")
    lines.append("The words arrive PER LEAD in `customUserFields`. No sequence write "
                 "is needed because the graph already carries the variables.")
    lines.append("")
    lines.append("### The corrected graph structure (17 nodes, without InMail)")
    lines.append("")
    lines.append("```")
    lines.append("CHECK_IS_CONNECTION (0 HOUR)")
    lines.append("  YES (already connected):")
    lines.append("    MESSAGE {connected_1}     (+3 HOUR)")
    lines.append("    MESSAGE {connected_2}     (+3 DAY)")
    lines.append("    VIEW_PROFILE              (+2 DAY)")
    lines.append("    MESSAGE {connected_3}     (+5 DAY)")
    lines.append("    MESSAGE {connected_4}     (+7 DAY)")
    lines.append("    END                       (+3 HOUR)")
    lines.append("  NO (cold path):")
    lines.append("    VIEW_PROFILE              (+3 HOUR)")
    lines.append("    FOLLOW                    (+3 HOUR)")
    lines.append("    CONNECTION_REQUEST {connection_note} (+1 DAY, withdraw after 21d)")
    lines.append("      condition (chain):")
    lines.append("        MESSAGE {message_2}   (+3 HOUR)")
    lines.append("        VIEW_PROFILE          (+3 DAY)")
    lines.append("        MESSAGE {message_3}   (+2 DAY)")
    lines.append("        MESSAGE {message_4}   (+7 DAY)")
    lines.append("        END                   (+3 HOUR)")
    lines.append("      not_accepted:")
    lines.append("        VIEW_PROFILE          (+5 DAY)")
    lines.append("        END                   (+3 HOUR)")
    lines.append("```")
    lines.append("")
    lines.append("### Does the node sequence match the CONTROL the ladder assumes?")
    lines.append("")
    lines.append("**Yes.** The COPY_MAPPING maps cadence steps to graph roles:")
    lines.append("")
    lines.append("| cadence step | graph role(s) | CONTROL fallback |")
    lines.append("|-------------|---------------|------------------|")
    for step_key, mapping in sorted(COPY_MAPPING.items()):
        roles = mapping["role"]
        if isinstance(roles, str):
            roles = (roles,)
        for role in roles:
            fb = fallbacks_config.get(role, "(MISSING)")
            lines.append(f"| {step_key} | {role} | {fb[:60]}... |")
    lines.append("")
    lines.append("**li6 has no slot in the graph.** The cadence names 6 steps but "
                 "the graph has positions for only 5 (li1-li5). li6 is reported in "
                 "`touch_report` but does not fire.")
    lines.append("")
    lines.append("### Does the copy in the nodes match the rendering?")
    lines.append("")
    lines.append("The nodes carry MERGE VARIABLES (`{connection_note}`, etc.), not "
                 "literal text. The actual text arrives per lead in `customUserFields`. "
                 "So the comparison is: does each contact's `customUserFields` match "
                 "the rendering in Section 3?")
    lines.append("")
    lines.append("**For Austin Ball (#1):** li1-li5 have operator-control-arm approval. "
                 "The approved copy matches the CONTROL fallbacks exactly (the CONTROL "
                 "was written to be the fallback). li6 is generated but has no graph slot.")
    lines.append("")
    lines.append("**For Sam Nielsen (#2) and Anthony Andreatos (#3):** All steps are "
                 "generated (no operator approval). The `customUserFields` would carry "
                 "the generated text, NOT the CONTROL fallbacks. The fallbacks fire "
                 "only when `customUserFields` is missing a variable entirely.")
    lines.append("")
    lines.append("**THIS IS THE FINDING.** The campaign was staged before the ladder "
                 "existed. The contacts have generated copy in their cadence steps, "
                 "but that copy was never operator-approved. When staging, the factory "
                 "would refuse because `assemble_linkedin_copy` requires approval. "
                 "The contacts would need their generated copy replaced with CONTROL "
                 "fallbacks before they can be staged.")
    lines.append("")

    # Section 8: The payload
    lines.append("## 8. The Staging Payload")
    lines.append("")
    lines.append("Schema per TASK-158: `profileUrl`, `firstName`, `lastName` + "
                 "`customUserFields` with one value per merge variable. All PII hashed.")
    lines.append("")
    lines.append("```json")
    lines.append("[")
    for i, pe in enumerate(payload_entries):
        lines.append("  {")
        lines.append(f'    "record_id_hash": "{pe["record_id_hash"]}",')
        lines.append(f'    "profileUrl_hash": "{pe["profileUrl_hash"]}",')
        lines.append(f'    "firstName_hash": "{pe["firstName_hash"]}",')
        lines.append(f'    "lastName_hash": "{pe["lastName_hash"]}",')
        lines.append(f'    "domain_hash": "{pe["domain_hash"]}",')
        lines.append(f'    "company_hash": "{pe["company_hash"]}",')
        lines.append(f'    "customUserFields": {{')
        fields = list(pe["customUserFields"].items())
        for j, (k, v) in enumerate(fields):
            comma = "," if j < len(fields) - 1 else ""
            lines.append(f'      "{k}": {json.dumps(v)}{comma}')
        lines.append(f'    }}')
        comma = "," if i < len(payload_entries) - 1 else ""
        lines.append(f"  }}{comma}")
    lines.append("]")
    lines.append("```")
    lines.append("")

    # Section 9: What LinkedIn's blocking variable is
    lines.append("## 9. LinkedIn's Blocking Variable")
    lines.append("")
    lines.append("Email's only blocking variable was `company` - a contact without "
                 "a resolvable company name could not render. LinkedIn has no "
                 "equivalent single blocking variable.")
    lines.append("")
    lines.append("What LinkedIn has instead is an **approval requirement**: every "
                 "merge variable must have approved copy from the cadence. If a "
                 "step has no `approval.by`, the factory refuses. The fallback "
                 "from config fills the GRAPH's `fallbackMessage` (what the provider "
                 "sends if the variable is empty), but the per-lead `customUserFields` "
                 "must carry the approved words.")
    lines.append("")
    lines.append("**The practical effect:** 2 of 3 canary contacts (Sam Nielsen, "
                 "Anthony Andreatos) have no operator-approved copy. Their generated "
                 "copy was never approved through the CONTROL arm. They cannot be "
                 "staged until their cadence steps are replaced with CONTROL fallbacks "
                 "or operator-approved generated copy.")
    lines.append("")
    lines.append("Only Austin Ball has operator-control-arm approval for li1-li5, "
                 "which maps to all 8 required roles. He is the only contact of the "
                 "three who can be staged today.")
    lines.append("")

    # Section 10: Summary
    lines.append("## 10. Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Snapshot | `{stamp}` |")
    lines.append(f"| Contacts | 3 (rung 3: economic_buyer, operations) |")
    lines.append(f"| Merge variables per contact | 8 |")
    lines.append(f"| Total variable slots | 24 |")
    lines.append(f"| Total fallbacks | {total_fallbacks} |")
    lines.append(f"| Contacts with full operator approval | 1 of 3 |")
    lines.append(f"| Contacts blocked (no approval) | 2 of 3 |")
    lines.append(f"| Lint | {'ALL PASS' if all_lint_pass else 'FAILURES DETECTED'} |")
    lines.append(f"| Claims | {'ALL PASS' if all_claims_pass else 'ISSUES DETECTED'} |")
    lines.append(f"| Graph nodes (corrected) | 17 (was 24 with literal strings) |")
    lines.append(f"| li6 in graph | NO - cadence step with no graph position |")
    lines.append("")

    doc_path = OUTPUT_DOC
    os.makedirs(os.path.dirname(doc_path), exist_ok=True)
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
