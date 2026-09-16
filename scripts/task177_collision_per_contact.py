#!/usr/bin/env python3
"""TASK-177: Per-contact collision check against the provider.

Runs check 7 from bison_prewrite_check.py against every contact in the
17-contact canary cohort, not just the campaign. Reports per-contact:
  - prior contact count at the provider
  - on which domain
  - whether the contact's own email appears in the provider's leads
  - per-campaign breakdown (emails_sent, status, in_sequence)

READ-ONLY. No POST, no PATCH, no PUT, no DELETE.

All PII is hashed before printing. No email address, person name,
company name, or domain appears in output.
"""
import hashlib
import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_CLAUDE = r"C:\Users\Zvonimir\Desktop\resonate-group-automation"

SNAPSHOT = os.path.join(_PROJECT_ROOT, "work", "queue.snapshot.jsonl")

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


def _hash(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _setup_data_access():
    """Point store/campaigns/clients at canonical data in Claude's worktree."""
    for env_key, subpath in [
        ("QUEUE", os.path.join("work", "queue.jsonl")),
        ("CAMPAIGNS", os.path.join("work", "campaigns.jsonl")),
        ("CLIENTS_DIR", os.path.join("config", "clients")),
    ]:
        full = os.path.join(_CLAUDE, subpath)
        if os.path.exists(full):
            os.environ.setdefault(env_key, full)
    env_file = os.path.join(_PROJECT_ROOT, "config", ".env")
    if os.path.exists(env_file):
        from src.providers import load_env
        load_env(env_file)


def load_cohort():
    """Load the 17 cohort contacts from the snapshot."""
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    cohort = []
    for rec in records:
        domain = str(rec.get("domain") or "").strip().lower()
        if domain in ALL_ALLOW:
            contacts = rec.get("contacts") or []
            for c in contacts:
                v = c.get("verification") or {}
                if c.get("email_verified") or v.get("state") == "verified":
                    cohort.append({
                        "rec_id": rec.get("id"),
                        "domain": domain,
                        "email": c.get("email", ""),
                        "name": c.get("name", ""),
                        "persona": c.get("persona"),
                        "angle": c.get("angle"),
                        "company": rec.get("company", ""),
                    })
    return cohort


def check_domain(domain, workspace_id):
    """Run collision.leads_for_domain for one domain. Returns (rows, error)."""
    from src import collision
    try:
        rows = collision.leads_for_domain(
            domain, expect_workspace=workspace_id)
        return rows, None
    except collision.CollisionUnknown as e:
        return None, f"CollisionUnknown: {e}"
    except Exception as e:
        return None, f"Exception: {e}"


def analyse_contact(email, domain_rows):
    """Check if a specific email appears in the domain's leads.

    Returns (found, touch_info) where touch_info is from collision.touches_of.
    """
    from src import collision
    email_norm = email.strip().lower()
    for row in (domain_rows or []):
        if not isinstance(row, dict):
            continue
        row_email = str(row.get("email") or "").strip().lower()
        if row_email == email_norm:
            return True, collision.touches_of(row)
    return False, None


def main():
    _setup_data_access()

    # Need the workspace id for the collision check
    from src.providers import bison
    try:
        ws = bison.bound_workspace()
        workspace_id = ws.get("id")
    except Exception as e:
        print(f"ERROR: cannot read bound workspace: {e}")
        sys.exit(1)

    print(f"Workspace id: {_hash(workspace_id)} (hashed)")
    print()

    cohort = load_cohort()
    print(f"Cohort size: {len(cohort)}")
    print()

    # Group by domain to avoid redundant provider calls
    domains = {}
    for c in cohort:
        d = c["domain"]
        if d not in domains:
            domains[d] = []
        domains[d].append(c)

    print(f"Unique domains: {len(domains)}")
    print()

    # Check each domain against the provider
    domain_results = {}
    for domain in sorted(domains.keys()):
        domain_hash = _hash(domain)
        rows, error = check_domain(domain, workspace_id)
        if error:
            domain_results[domain] = {
                "error": error,
                "rows": None,
                "lead_count": None,
            }
            print(f"Domain {_hash(domain)}: ERROR - {error}")
        else:
            domain_results[domain] = {
                "error": None,
                "rows": rows,
                "lead_count": len(rows),
            }
            # Summarise the domain
            from src import collision
            total_emails = 0
            in_seq = 0
            for row in rows:
                info = collision.touches_of(row)
                total_emails += info["emails_sent"]
                if info["in_sequence"]:
                    in_seq += 1
            print(f"Domain {domain_hash}: {len(rows)} lead(s), "
                  f"{total_emails} total email(s), {in_seq} in_sequence")

    print()
    print("=" * 72)
    print("PER-CONTACT RESULTS")
    print("=" * 72)
    print()

    # Now check each contact
    results = []
    zero_prior = 0
    some_prior = 0
    undetermined = 0

    for idx, contact in enumerate(cohort, 1):
        domain = contact["domain"]
        email = contact["email"]
        dr = domain_results[domain]

        contact_hash = _hash(contact["name"])
        domain_hash = _hash(domain)
        email_hash = _hash(email)
        rec_id_hash = _hash(contact["rec_id"])

        if dr["error"]:
            # Could not check the domain -> UNDETERMINED
            undetermined += 1
            results.append({
                "idx": idx,
                "rec_id_hash": rec_id_hash,
                "contact_hash": contact_hash,
                "domain_hash": domain_hash,
                "email_hash": email_hash,
                "persona": contact["persona"],
                "angle": contact["angle"],
                "status": "UNDETERMINED",
                "reason": dr["error"],
                "prior_emails": None,
                "in_sequence": None,
                "campaigns": None,
            })
            print(f"  #{idx:2d} rec={rec_id_hash} contact={contact_hash} "
                  f"domain={domain_hash}")
            print(f"       persona={contact['persona']} angle={contact['angle']}")
            print(f"       STATUS: UNDETERMINED - {dr['error']}")
            print()
            continue

        found, touch_info = analyse_contact(email, dr["rows"])
        if found:
            prior = touch_info["emails_sent"]
            in_seq = touch_info["in_sequence"]
            campaigns = touch_info["campaigns"]
            if prior > 0 or in_seq:
                some_prior += 1
                status = "FAIL"
            else:
                zero_prior += 1
                status = "PASS"
            results.append({
                "idx": idx,
                "rec_id_hash": rec_id_hash,
                "contact_hash": contact_hash,
                "domain_hash": domain_hash,
                "email_hash": email_hash,
                "persona": contact["persona"],
                "angle": contact["angle"],
                "status": status,
                "reason": (f"{prior} prior email(s)"
                           + (", in_sequence" if in_seq else "")
                           + f", {len(campaigns)} campaign(s)"),
                "prior_emails": prior,
                "in_sequence": in_seq,
                "campaigns": campaigns,
            })
            print(f"  #{idx:2d} rec={rec_id_hash} contact={contact_hash} "
                  f"domain={domain_hash}")
            print(f"       persona={contact['persona']} angle={contact['angle']}")
            print(f"       STATUS: {status} - {prior} prior email(s), "
                  f"in_sequence={in_seq}, {len(campaigns)} campaign(s)")
            # Show per-campaign detail
            for camp in campaigns:
                cid = camp.get("campaign_id")
                cstatus = camp.get("status")
                csent = camp.get("emails_sent", 0)
                creplies = camp.get("replies", 0)
                print(f"         campaign={_hash(str(cid))} status={cstatus} "
                      f"sent={csent} replies={creplies}")
            print()
        else:
            zero_prior += 1
            results.append({
                "idx": idx,
                "rec_id_hash": rec_id_hash,
                "contact_hash": contact_hash,
                "domain_hash": domain_hash,
                "email_hash": email_hash,
                "persona": contact["persona"],
                "angle": contact["angle"],
                "status": "PASS",
                "reason": "no lead at this address in provider's estate",
                "prior_emails": 0,
                "in_sequence": False,
                "campaigns": [],
            })
            print(f"  #{idx:2d} rec={rec_id_hash} contact={contact_hash} "
                  f"domain={domain_hash}")
            print(f"       persona={contact['persona']} angle={contact['angle']}")
            print(f"       STATUS: PASS - not found in provider's leads")
            print()

    print("=" * 72)
    print("THREE NUMBERS")
    print("=" * 72)
    print(f"  Zero prior provider contact: {zero_prior}")
    print(f"  Some prior provider contact:  {some_prior}")
    print(f"  Undetermined (check failed):  {undetermined}")
    print(f"  Total:                        {zero_prior + some_prior + undetermined}")
    print()

    # Persona=None contacts
    print("=" * 72)
    print("PERSONA=NONE CONTACTS")
    print("=" * 72)
    persona_none = [r for r in results if r["persona"] is None]
    print(f"  Count: {len(persona_none)}")
    for r in persona_none:
        print(f"    #{r['idx']:2d} rec={r['rec_id_hash']} "
              f"contact={r['contact_hash']} domain={r['domain_hash']} "
              f"status={r['status']}")
    print()

    # Surviving cohort
    print("=" * 72)
    print("SURVIVING COHORT (PASS only)")
    print("=" * 72)
    survivors = [r for r in results if r["status"] == "PASS"]
    print(f"  Count: {len(survivors)}")
    for r in survivors:
        persona_label = r["persona"] if r["persona"] else "None"
        print(f"    #{r['idx']:2d} rec={r['rec_id_hash']} "
              f"persona={persona_label} angle={r['angle']} "
              f"domain={r['domain_hash']}")
    print()

    # Survivors with persona (the "ten" from the task)
    survivors_with_persona = [r for r in survivors if r["persona"] is not None]
    print(f"  Survivors with persona (own angle): {len(survivors_with_persona)}")
    for r in survivors_with_persona:
        print(f"    #{r['idx']:2d} rec={r['rec_id_hash']} "
              f"persona={r['persona']} angle={r['angle']}")
    print()

    # Write JSON results for the deliverable
    output = {
        "workspace_hash": _hash(workspace_id),
        "cohort_size": len(cohort),
        "unique_domains": len(domains),
        "three_numbers": {
            "zero_prior": zero_prior,
            "some_prior": some_prior,
            "undetermined": undetermined,
        },
        "persona_none_count": len(persona_none),
        "persona_none_contacts": [
            {"idx": r["idx"], "rec_id_hash": r["rec_id_hash"],
             "domain_hash": r["domain_hash"]}
            for r in persona_none
        ],
        "survivors": [
            {"idx": r["idx"], "rec_id_hash": r["rec_id_hash"],
             "contact_hash": r["contact_hash"], "domain_hash": r["domain_hash"],
             "persona": r["persona"], "angle": r["angle"],
             "status": r["status"], "reason": r["reason"]}
            for r in survivors
        ],
        "all_results": [
            {"idx": r["idx"], "rec_id_hash": r["rec_id_hash"],
             "contact_hash": r["contact_hash"], "domain_hash": r["domain_hash"],
             "persona": r["persona"], "angle": r["angle"],
             "status": r["status"], "reason": r["reason"],
             "prior_emails": r["prior_emails"],
             "in_sequence": r["in_sequence"]}
            for r in results
        ],
    }
    json_path = os.path.join(_PROJECT_ROOT, "scripts",
                             "task177_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"JSON results written to {json_path}")


if __name__ == "__main__":
    raise SystemExit(main())
