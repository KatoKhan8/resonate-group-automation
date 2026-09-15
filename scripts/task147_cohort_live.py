#!/usr/bin/env python3
"""TASK-147: Resolve the EmailBison cohort against the live-ish snapshot.

Four questions:
  1. Who is actually cold on email right now?
  2. Were the bison_lead_id contacts ever actually EMAILED?
  3. What does the account-collision rule do to the email cohort?
  4. What cohorts fall out?

Reads work/queue.snapshot.jsonl (550 records).
Quotes the snapshot stamp on every number.
Calls bison.lead() (READ ONLY) for each bison_lead_id contact.
Calls collision.check_account() (READ ONLY) for each unique domain in the
cold cohort.

No writes. No provider mutations. No generation.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import bison  # noqa: E402
from src import collision  # noqa: E402

SNAPSHOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "work", "queue.snapshot.jsonl")
STAMP_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "work", "queue.snapshot.STAMP")


def load_stamp():
    if os.path.exists(STAMP_FILE):
        with open(STAMP_FILE, encoding="utf-8") as f:
            return f.read().strip()
    return "unknown"


def load_records():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def contact_has_verified_email(contact):
    v = contact.get("verification") or {}
    return v.get("state") == "verified"


def contact_has_bison(contact):
    return contact.get("bison_lead_id") is not None


def record_has_verified_email(rec):
    return any(contact_has_verified_email(c) for c in rec.get("contacts", []))


def record_has_bison(rec):
    return any(contact_has_bison(c) for c in rec.get("contacts", []))


def record_has_reply(rec):
    for entry in rec.get("log", []):
        step = (entry.get("step") or "").lower()
        note = (entry.get("note") or "").lower()
        if "reply" in step or "replied" in note:
            return True
    return False


def partition_records(records):
    """Four-way partition at the RECORD level (same as TASK-145)."""
    cold = []           # verified email, no bison_lead_id
    prior_outreach = [] # bison_lead_id present, no reply evidence
    bison_with_reply = []  # bison_lead_id AND reply evidence
    unverified = []     # no verified email, no bison_lead_id

    for rec in records:
        v = record_has_verified_email(rec)
        b = record_has_bison(rec)
        r = record_has_reply(rec)

        if b and r:
            bison_with_reply.append(rec)
        elif b:
            prior_outreach.append(rec)
        elif v:
            cold.append(rec)
        else:
            unverified.append(rec)

    return cold, prior_outreach, bison_with_reply, unverified


def get_bison_contacts(rec):
    """Yield (contact, bison_lead_id) for contacts with a bison_lead_id."""
    for c in rec.get("contacts", []):
        bid = c.get("bison_lead_id")
        if bid is not None:
            yield c, bid


def check_lead_send_status(lead_id):
    """READ ONLY: did this lead ever receive an email?

    Uses GET /leads/{id} which returns overall_stats.emails_sent and
    lead_campaign_data[].emails_sent per campaign.
    """
    try:
        data = bison.lead(lead_id)
    except Exception as e:
        return {"lead_id": lead_id, "error": str(e)}

    overall = data.get("overall_stats") or {}
    emails_sent = int(overall.get("emails_sent") or 0)

    campaigns = []
    for lcd in data.get("lead_campaign_data") or []:
        campaigns.append({
            "campaign_id": lcd.get("campaign_id"),
            "status": lcd.get("status"),
            "emails_sent": int(lcd.get("emails_sent") or 0),
            "replies": int(lcd.get("replies") or 0),
            "interested": bool(lcd.get("interested")),
        })

    return {
        "lead_id": lead_id,
        "overall_emails_sent": emails_sent,
        "overall_replies": int(overall.get("replies") or 0),
        "campaigns": campaigns,
        "lead_status": data.get("status"),
        "email": data.get("email"),
    }


def run_question_1(records, stamp):
    """Who is actually cold on email, right now?"""
    cold, prior, bison_reply, unverified = partition_records(records)
    total = len(records)

    print("=" * 72)
    print("QUESTION 1: Who is actually cold on email?")
    print(f"Snapshot stamp: {stamp}")
    print(f"Total records: {total}")
    print("=" * 72)
    print()
    print(f"  Cold email (verified, no bison_lead_id):    {len(cold):>4}")
    print(f"  Prior outreach (bison_lead_id, no reply):   {len(prior):>4}")
    print(f"  Bison with reply evidence:                  {len(bison_reply):>4}")
    print(f"  Unverified, neither:                        {len(unverified):>4}")
    print(f"  SUM:                                        {len(cold)+len(prior)+len(bison_reply)+len(unverified):>4}")
    print()

    # Contact-level counts
    cold_contacts = 0
    prior_contacts = 0
    for rec in cold:
        for c in rec.get("contacts", []):
            if contact_has_verified_email(c):
                cold_contacts += 1
    for rec in prior:
        for c in rec.get("contacts", []):
            if contact_has_bison(c):
                prior_contacts += 1

    print(f"  Cold contacts (verified, no bison):         {cold_contacts:>4}")
    print(f"  Prior outreach contacts (bison_lead_id):    {prior_contacts:>4}")
    print()

    return cold, prior, bison_reply, unverified


def run_question_2(prior_records, stamp):
    """Were the bison_lead_id contacts ever actually EMAILED?"""
    print("=" * 72)
    print("QUESTION 2: Were the bison_lead_id contacts ever EMAILED?")
    print(f"Snapshot stamp: {stamp}")
    print("=" * 72)
    print()

    leads_to_check = []
    for rec in prior_records:
        for contact, bid in get_bison_contacts(rec):
            leads_to_check.append({
                "record_id": rec.get("id"),
                "domain": rec.get("domain"),
                "contact_name": contact.get("name"),
                "email": contact.get("email"),
                "bison_lead_id": bid,
            })

    print(f"  Contacts with bison_lead_id to check: {len(leads_to_check)}")
    print()

    results = []
    never_emailed = []
    actually_emailed = []
    errors = []

    for i, item in enumerate(leads_to_check):
        bid = item["bison_lead_id"]
        sys.stdout.write(f"  Checking lead {bid} ({i+1}/{len(leads_to_check)})... ")
        sys.stdout.flush()
        result = check_lead_send_status(bid)
        result["record_id"] = item["record_id"]
        result["domain"] = item["domain"]
        result["contact_name"] = item["contact_name"]
        result["contact_email"] = item["email"]
        results.append(result)

        if "error" in result:
            errors.append(result)
            print(f"ERROR: {result['error']}")
        elif result["overall_emails_sent"] == 0:
            never_emailed.append(result)
            print(f"NEVER EMAILED (overall_emails_sent=0)")
        else:
            actually_emailed.append(result)
            print(f"EMAILED: {result['overall_emails_sent']} email(s)")

        # Small delay to avoid hammering the API
        if i < len(leads_to_check) - 1:
            time.sleep(0.3)

    print()
    print(f"  SUMMARY:")
    print(f"    Never emailed:     {len(never_emailed):>3}")
    print(f"    Actually emailed:  {len(actually_emailed):>3}")
    print(f"    Errors:            {len(errors):>3}")
    print()

    if actually_emailed:
        print("  Actually emailed contacts:")
        for r in actually_emailed:
            camps = ", ".join(
                f"cmp={c['campaign_id']} sent={c['emails_sent']} "
                f"status={c['status']}"
                for c in r["campaigns"] if c["emails_sent"] > 0
            )
            print(f"    {r['contact_name']:30} lead={r['lead_id']} "
                  f"emails={r['overall_emails_sent']} [{camps}]")
        print()

    if never_emailed:
        print("  Never-emailed contacts (effectively cold):")
        for r in never_emailed:
            camps = ", ".join(
                f"cmp={c['campaign_id']} status={c['status']} "
                f"sent={c['emails_sent']}"
                for c in r["campaigns"]
            )
            print(f"    {r['contact_name']:30} lead={r['lead_id']} "
                  f"domain={r['domain']} [{camps}]")
        print()

    return results, never_emailed, actually_emailed, errors


def run_question_3(cold_records, stamp):
    """What does the account-collision rule do to the email cohort?"""
    print("=" * 72)
    print("QUESTION 3: Account-collision rule on the cold email cohort")
    print(f"Snapshot stamp: {stamp}")
    print("=" * 72)
    print()

    # Get workspace ID
    try:
        ws = bison.bound_workspace()
        workspace_id = (ws or {}).get("id")
        print(f"  EmailBison workspace: {workspace_id} ({(ws or {}).get('name', '?')})")
    except Exception as e:
        print(f"  WARNING: could not read workspace binding: {e}")
        workspace_id = None

    if workspace_id is None:
        print("  CANNOT proceed without workspace binding.")
        return {}

    # Collect unique domains from cold cohort
    domains = {}
    for rec in cold_records:
        d = rec.get("domain")
        if d:
            if d not in domains:
                domains[d] = []
            domains[d].append(rec.get("id"))

    print(f"  Unique domains in cold cohort: {len(domains)}")
    print()

    verdicts = {}
    allow_count = 0
    stop_count = 0
    hold_count = 0
    error_count = 0
    allow_records = 0
    stop_records = 0
    hold_records = 0

    domain_list = sorted(domains.keys())
    for i, domain in enumerate(domain_list):
        rec_ids = domains[domain]
        sys.stdout.write(f"  Checking {domain} ({i+1}/{len(domain_list)})... ")
        sys.stdout.flush()
        try:
            account = collision.check_account(
                domain, expect_workspace=workspace_id)
            verdict, why = collision.account_policy(account)
            verdicts[domain] = (verdict, why, account)
            print(f"{verdict} - {why}")
        except collision.CollisionUnknown as e:
            verdicts[domain] = (collision.HOLD, f"unreadable: {e}", None)
            print(f"HOLD - unreadable: {e}")
        except Exception as e:
            verdicts[domain] = (collision.HOLD, f"error: {e}", None)
            print(f"ERROR: {e}")
            error_count += 1
            continue

        if verdict == collision.ALLOW:
            allow_count += 1
            allow_records += len(rec_ids)
        elif verdict == collision.STOP:
            stop_count += 1
            stop_records += len(rec_ids)
        else:
            hold_count += 1
            hold_records += len(rec_ids)

        if i < len(domain_list) - 1:
            time.sleep(0.2)

    print()
    print(f"  DOMAIN-LEVEL SUMMARY:")
    print(f"    ALLOW:  {allow_count:>3} domains ({allow_records} records)")
    print(f"    STOP:   {stop_count:>3} domains ({stop_records} records)")
    print(f"    HOLD:   {hold_count:>3} domains ({hold_records} records)")
    print(f"    ERROR:  {error_count:>3} domains")
    print()

    # Count surviving contacts
    total_cold_contacts = 0
    surviving_contacts = 0
    for rec in cold_records:
        d = rec.get("domain")
        for c in rec.get("contacts", []):
            if contact_has_verified_email(c) and not contact_has_bison(c):
                total_cold_contacts += 1
                if d and d in verdicts and verdicts[d][0] == collision.ALLOW:
                    surviving_contacts += 1

    print(f"  CONTACT-LEVEL:")
    print(f"    Total cold contacts:       {total_cold_contacts}")
    print(f"    Surviving account check:   {surviving_contacts}")
    print(f"    Rejected at account level: {total_cold_contacts - surviving_contacts}")
    print()

    return verdicts


def run_question_4(cold_records, prior_records, never_emailed, stamp):
    """What cohorts fall out?"""
    print("=" * 72)
    print("QUESTION 4: What cohorts fall out?")
    print(f"Snapshot stamp: {stamp}")
    print("=" * 72)
    print()

    # Combine cold + never-emailed (they are both effectively cold)
    cold_contact_count = 0
    for rec in cold_records:
        for c in rec.get("contacts", []):
            if contact_has_verified_email(c) and not contact_has_bison(c):
                cold_contact_count += 1

    never_emailed_count = len(never_emailed)

    print(f"  Cold-email contacts (verified, no bison):     {cold_contact_count}")
    print(f"  Never-emailed bison contacts (effectively cold): {never_emailed_count}")
    print(f"  Combined addressable cohort:                  {cold_contact_count + never_emailed_count}")
    print()

    # Check what dimensions are actually populated
    print("  DIMENSION COVERAGE (across all 550 records):")
    dimensions = {
        "industry": 0,
        "employees": 0,
        "employee_range": 0,
        "revenue": 0,
        "signal": 0,
        "angle": 0,
        "persona": 0,
        "headcount_signal": 0,
    }
    for rec in cold_records:
        cf = rec.get("company_facts") or {}
        for dim in dimensions:
            val = cf.get(dim)
            if val is not None and val != "" and val != 0:
                dimensions[dim] += 1

    total = len(cold_records) if cold_records else 1
    for dim, count in sorted(dimensions.items()):
        pct = 100 * count / total if total else 0
        print(f"    {dim:25} {count:>4}/{total} ({pct:.0f}%)")
    print()

    # Contact-level dimension coverage
    print("  CONTACT-LEVEL DIMENSION COVERAGE (cold cohort contacts):")
    contact_dims = {
        "title": 0,
        "persona": 0,
        "angle": 0,
        "linkedin": 0,
    }
    total_contacts = 0
    for rec in cold_records:
        for c in rec.get("contacts", []):
            if contact_has_verified_email(c) and not contact_has_bison(c):
                total_contacts += 1
                for dim in contact_dims:
                    val = c.get(dim)
                    if val is not None and val != "":
                        contact_dims[dim] += 1

    for dim, count in sorted(contact_dims.items()):
        pct = 100 * count / total_contacts if total_contacts else 0
        print(f"    {dim:25} {count:>4}/{total_contacts} ({pct:.0f}%)")
    print()

    # ICP flag distribution
    print("  ICP FLAG DISTRIBUTION (cold cohort records):")
    icp_counts = {}
    for rec in cold_records:
        cf = rec.get("company_facts") or {}
        flags = cf.get("icp_flags") or []
        for flag in flags:
            icp_counts[flag] = icp_counts.get(flag, 0) + 1
    for flag, count in sorted(icp_counts.items(), key=lambda x: -x[1]):
        print(f"    {count:>4}  {flag}")
    print()

    # Signal distribution
    print("  SIGNAL DISTRIBUTION (cold cohort records):")
    signal_counts = {}
    for rec in cold_records:
        sig = rec.get("signal") or "(none)"
        signal_counts[sig] = signal_counts.get(sig, 0) + 1
    for sig, count in sorted(signal_counts.items(), key=lambda x: -x[1]):
        print(f"    {count:>4}  {sig[:80]}")
    print()

    # State distribution
    print("  STATE DISTRIBUTION (cold cohort records):")
    state_counts = {}
    for rec in cold_records:
        st = rec.get("state") or "(none)"
        state_counts[st] = state_counts.get(st, 0) + 1
    for st, count in sorted(state_counts.items(), key=lambda x: -x[1]):
        print(f"    {count:>4}  {st}")
    print()


def main():
    stamp = load_stamp()
    print(f"TASK-147: EmailBison cohort resolved against live snapshot")
    print(f"Snapshot stamp: {stamp}")
    print()

    records = load_records()
    print(f"Loaded {len(records)} records from snapshot")
    print()

    # Q1: Partition
    cold, prior, bison_reply, unverified = run_question_1(records, stamp)

    # Q2: Provider-side send check for bison_lead_id contacts
    results, never_emailed, actually_emailed, errors = run_question_2(prior, stamp)

    # Q3: Account collision on cold cohort
    verdicts = run_question_3(cold, stamp)

    # Q4: Cohort proposal
    run_question_4(cold, prior, never_emailed, stamp)

    # Write JSON results for the report
    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "task147_results.json")
    summary = {
        "stamp": stamp,
        "total_records": len(records),
        "q1": {
            "cold_records": len(cold),
            "prior_outreach_records": len(prior),
            "bison_with_reply_records": len(bison_reply),
            "unverified_records": len(unverified),
        },
        "q2": {
            "checked": len(results),
            "never_emailed": len(never_emailed),
            "actually_emailed": len(actually_emailed),
            "errors": len(errors),
            "details": [
                {
                    "lead_id": r["lead_id"],
                    "contact_name": r.get("contact_name"),
                    "domain": r.get("domain"),
                    "overall_emails_sent": r.get("overall_emails_sent", -1),
                    "campaigns": r.get("campaigns", []),
                    "error": r.get("error"),
                }
                for r in results
            ],
        },
        "q3": {
            "domains_checked": len(verdicts),
            "allow": sum(1 for v in verdicts.values() if v[0] == collision.ALLOW),
            "stop": sum(1 for v in verdicts.values() if v[0] == collision.STOP),
            "hold": sum(1 for v in verdicts.values() if v[0] == collision.HOLD),
        },
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Results written to {out_path}")


if __name__ == "__main__":
    main()
