#!/usr/bin/env python3
"""S8: the staging track becomes canonical records, campaigns and approvals.

    py -3 scripts/batch1_build.py --plan          # what it would build
    py -3 scripts/batch1_build.py --write         # write records + campaigns
    py -3 scripts/batch1_build.py --stats         # the batch stats block

WRITES NOTHING TO ANY PROVIDER. It writes canonical state only, and
`bisonfactory.stage` is what talks to EmailBison afterwards - which is the
whole point of this script existing.

## WHY THIS EXISTS AT ALL

The 24k track ran S1 -> S3 -> S4b -> S5 -> S6 -> S7 into JOURNALS. The push
path builds from RECORDS: `bisonfactory._plan` reads a record's contacts and
its approved cadence steps, and `executionguard` checks an approval
fingerprint against the exact words a payload carries. So a journal row
cannot be pushed, and the gap between the two is this script.

The alternative - writing leads straight to the provider from the journal -
would put every lead on the wire with none of tenancy, approval, collision,
suppression, copy, claims, fatigue or sender ever running. That is not a
shortcut, it is the whole safety model.

## THE THREE THINGS IT WRITES

    records     one per ACCOUNT, carrying the contacts that passed S5 with
                their verification pair, their MX decision and the S3
                evidence behind the ICP verdict
    cadence     em1/em2/em3 per contact, holding S7's rendered words, then
                APPROVED through `approve.approve_step` so the fingerprint is
                computed by the same code the guard checks it with
    campaigns   one canonical row per attested human, naming that human's
                single healthiest mailbox, with a window that matches its
                cohort

## TIMEZONE COHORTS ARE CAMPAIGN-SHAPED, NOT LEAD-SHAPED

EmailBison schedules ONE window per campaign, so a cohort mixing New York and
Berlin mails somebody in the middle of their night whatever the lead says.
Condition 3 of the grant asks for recipient-local windows and grouped
cohorts, so each campaign carries one cohort and one window:

    us      America/New_York   09:00-17:00   - the window 489 already uses
    uk      Europe/London      09:00-17:00
    eu      Europe/Zagreb      09:00-17:00

**Australia is HELD OUT of batch 1.** Thirteen leads is not a campaign, and
the grant says no inferred timezone where the country spans several. They
wait for a cohort of their own rather than being mailed at 03:00 local.

## THE PACING RULE DECIDES THE SIZE, NOT THE SUPPLY

Enrolled-but-unsent per campaign stays at or below three days of that
campaign's first-step capacity. Single-mailbox tonight: 15/day x 3 = 45 per
campaign, 360 across eight. 495 leads carry copy; the rest wait in the
reservoir, which is what a reservoir is for.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (approve, campaigns, clients, clientapproval as ca,  # noqa: E402
                 identity, store)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")
SOURCE_CSV = os.path.join(ROOT, "work", "Productive",
                          "productive_ICP_safe_to_send (1).csv")

CLIENT = "productive"

#: The grant, named as the approver. `approval.is_accountable_approver`
#: requires an address, and the parenthetical carries the provenance.
APPROVER = ("zvonimir@resonategroup.co "
            "(operator authorisation 2026-09-21 batch 1)")

#: 15 first-step sends per mailbox per day, three days of backlog.
PER_CAMPAIGN = 45
PER_MAILBOX_DAY = 15

COHORTS = {
    "us": {"countries": {"United States"},
           "window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                               "friday"],
                      "start": "09:00", "end": "17:00",
                      "timezone": "America/New_York"},
           "campaigns": 5},
    "uk": {"countries": {"United Kingdom", "Ireland"},
           "window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                               "friday"],
                      "start": "09:00", "end": "17:00",
                      "timezone": "Europe/London"},
           "campaigns": 2},
    "eu": {"countries": {"Germany", "Sweden", "France", "Finland",
                         "Netherlands", "Denmark", "Norway", "Belgium",
                         "Austria", "Switzerland", "Poland", "Spain",
                         "Italy", "Croatia", "Portugal", "Czechia"},
           "window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                               "friday"],
                      "start": "09:00", "end": "17:00",
                      "timezone": "Europe/Zagreb"},
           "campaigns": 1},
}

STEP_KEYS = ("em1", "em2", "em3")


def _jsonl(path):
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_inputs():
    icp = {}
    for row in _jsonl(os.path.join(STAGE, "s3-icp.jsonl")):
        icp[str(row.get("domain", "")).lower()] = row
    verify = {}
    for row in _jsonl(os.path.join(STAGE, "s5-verify.jsonl")):
        verify[str(row.get("email", "")).lower()] = row
    with open(os.path.join(ROOT, "work", "mx-cache.json"),
              encoding="utf-8") as handle:
        mx = {k.lower(): v for k, v in json.load(handle).items()}
    copy = {}
    for row in _jsonl(os.path.join(STAGE, "s7-copy.jsonl")):
        if row.get("state") == "rendered":
            copy[str(row.get("email", "")).lower()] = row["variables"]
    import csv
    people = {}
    with open(SOURCE_CSV, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            email = (row.get("Work Email") or "").strip().lower()
            if email and email not in people:
                people[email] = row
    return icp, verify, mx, copy, people


def cohort_of(country):
    for name, spec in COHORTS.items():
        if country in spec["countries"]:
            return name
    return None


def attested_mailboxes():
    """Each attested human's single healthiest mailbox by lifetime bounce.

    Condition 2, single-mailbox branch. The three excluded identities carry
    no attestation, so they cannot appear here even as a fallback - the
    register's row exists so nobody reads their 51 mailboxes as capacity.
    """
    rows = _jsonl(os.path.join(ROOT, "work", "senders.jsonl"))
    accounts = {r.get("account_id"): r for r in rows
                if r.get("kind") == "email_account"}
    per = collections.defaultdict(list)
    for row in rows:
        if (row.get("kind") == "ownership_attestation"
                and row.get("channel") == "email"):
            account = accounts.get(row.get("account_id"))
            if account:
                per[row.get("sender_id")].append(account)
    chosen = {}
    for human, mailboxes in per.items():
        scored = []
        for mailbox in mailboxes:
            state = mailbox.get("provider_state") or {}
            sent = state.get("emails_sent_count") or 0
            bounced = state.get("bounced_count") or 0
            rate = (bounced / sent) if sent else 9.0
            scored.append((rate, -sent, mailbox))
        scored.sort(key=lambda t: (t[0], t[1]))
        rate, _, mailbox = scored[0]
        chosen[human] = {
            "provider_account_id": str(mailbox.get("provider_account_id")),
            "account_id": mailbox.get("account_id"),
            "bounce_rate": rate,
            "mailboxes_attested": len(mailboxes),
        }
    return chosen


def select(copy, icp, people):
    """The leads batch 1 will carry, per cohort, under the pacing rule."""
    by_cohort = collections.defaultdict(list)
    held = collections.Counter()
    for email, variables in sorted(copy.items()):
        domain = email.split("@")[-1].lower()
        country = (icp.get(domain) or {}).get("country") or "unknown"
        cohort = cohort_of(country)
        if cohort is None:
            held[f"no campaign window for this cohort: {country}"] += 1
            continue
        if not ca.is_approved(domain, CLIENT):
            held["client approval not approved"] += 1
            continue
        by_cohort[cohort].append((email, variables, country))
    plan, spill = {}, collections.Counter()
    for cohort, entries in by_cohort.items():
        cap = COHORTS[cohort]["campaigns"] * PER_CAMPAIGN
        plan[cohort] = entries[:cap]
        if len(entries) > cap:
            spill[cohort] = len(entries) - cap
    return plan, held, spill


def build_records(selection, icp, verify, mx, people):
    """One record per account, contacts attached, copy not yet approved."""
    records = {}
    for cohort, entries in selection.items():
        for email, variables, country in entries:
            domain = email.split("@")[-1].lower()
            person = people.get(email) or {}
            row = icp.get(domain) or {}
            record_id = domain.replace(".", "-")
            record = records.get(record_id)
            if record is None:
                record = {
                    "id": record_id,
                    "lane": "domains",
                    "client": CLIENT,
                    "company": (person.get("Company") or "").strip() or domain,
                    "domain": domain,
                    "context": "",
                    "signal": row.get("reason") or "",
                    "state": "verified",
                    "drop_reason": None,
                    "batch": "batch-1-2026-09-21",
                    "cohort": cohort,
                    "company_facts": {
                        "name": (person.get("Company") or "").strip() or domain,
                        "domain": domain,
                        "employees": row.get("employees"),
                        "industry": row.get("industry"),
                        "country": row.get("country"),
                        "research_outcome": "supplier list, ICP re-verified",
                    },
                    "contacts": [],
                    "excluded": [],
                    "diagnosis": None,
                    "hook": None,
                    "cadence": {},
                    "stages": {},
                    "events": [],
                    "log": [],
                }
                records[record_id] = record
            name = " ".join(x for x in [(person.get("First Name") or "").strip(),
                                        (person.get("Last Name") or "").strip()]
                            if x)
            contact = {
                "name": name,
                "first_name": (person.get("First Name") or "").strip(),
                "last_name": (person.get("Last Name") or "").strip(),
                "title": variables.get("title"),
                "email": email,
                "email_source": "supplier list, independently verified",
                "persona": variables.get("persona"),
                "angle": variables.get("angle"),
                "verdict": "valid",
                "sendable": True,
                "primary": not record["contacts"],
                "linkedin": (person.get("Url") or "").strip() or None,
                "mx": mx.get(domain) or {},
                "verification": _verification(verify.get(email) or {}),
            }
            contact["key"] = identity.contact_key(
                contact, existing=[c.get("key") for c in record["contacts"]])
            record["contacts"].append(contact)
            record["cadence"][contact["key"]] = {
                "em1": {"channel": "email", "template": "persona_pain",
                        "generated": True,
                        "subject": variables["subject_1"],
                        "body": variables["body_1"]},
                "em2": {"channel": "email", "template": "comparable_proof",
                        "generated": True,
                        "subject": variables["subject_1"],
                        "body": variables["body_2"]},
                "em3": {"channel": "email", "template": "breakup",
                        "generated": True,
                        "subject": variables["subject_1"],
                        "body": variables["body_3"]},
            }
    return records


def _verification(row):
    """The S5 verdict, in the shape the record carries.

    The PAIR is the evidence: two independent providers, both fresh, which is
    condition 1. A supplier's own "Verified" column is not one of them and
    never enters here.
    """
    pair = list(row.get("pair") or ())
    return {
        "state": row.get("state"),
        "sendable": bool(row.get("sendable")),
        "reason": row.get("reason"),
        "stopped": None,
        "at": row.get("at"),
        "confirmations": row.get("confirmations"),
        "evidence": [{"provider": name, "status": "valid",
                      "at": row.get("at")} for name in pair],
    }


def assign(selection, records, mailboxes):
    """Which campaign each record belongs to. One cohort per campaign."""
    humans = sorted(mailboxes, key=lambda h: (-mailboxes[h]["mailboxes_attested"],
                                              h))
    slots = []
    for cohort, spec in COHORTS.items():
        for _ in range(spec["campaigns"]):
            slots.append(cohort)
    plan = collections.OrderedDict()
    for human, cohort in zip(humans, slots):
        plan[human] = {"cohort": cohort, "record_ids": [], "leads": 0}
    # AN ACCOUNT IS NOT SPLIT ACROSS CAMPAIGNS. Two people at one company
    # hearing from two different senders in the same week is the thing
    # account-based outreach exists to avoid, so the unit assigned here is
    # the account and the per-campaign cap is checked against the leads it
    # brings with it.
    #
    # THE CAP IS PER CAMPAIGN, which is what the pacing rule actually says:
    # enrolled-but-unsent per campaign at or below three days of THAT
    # campaign's first-step capacity. Capping the cohort total instead let a
    # campaign reach 49 while another sat at 41 - the same 360 in aggregate
    # and a four-day backlog on one of them.
    by_account = collections.OrderedDict()
    for cohort, entries in selection.items():
        for email, _variables, _country in entries:
            record_id = email.split("@")[-1].lower().replace(".", "-")
            by_account.setdefault((cohort, record_id), []).append(email)
    spilled = collections.Counter()
    for (cohort, record_id), emails in by_account.items():
        targets = [h for h in plan if plan[h]["cohort"] == cohort]
        room = [h for h in targets
                if plan[h]["leads"] + len(emails) <= PER_CAMPAIGN]
        if not room:
            spilled[cohort] += len(emails)
            continue
        human = min(room, key=lambda h: plan[h]["leads"])
        plan[human]["record_ids"].append(record_id)
        plan[human]["leads"] += len(emails)
    return plan, spilled


def campaign_row(human, spec, mailbox):
    slug = f"productive-email-batch1-{human}"
    return {
        "campaign_id": slug,
        "client": CLIENT,
        "name": (f"RESONATE - PRODUCTIVE - EMAIL - "
                 f"{spec['cohort'].upper()}-HOURS - BATCH1 - {human.upper()}"),
        "status": "approved",
        "created_by": "operator",
        "batch_id": "batch-1-2026-09-21",
        "lanes": ["domains"],
        "personas": [],
        "geos": [],
        "record_ids": spec["record_ids"],
        "daily_volume": {"email": PER_MAILBOX_DAY, "linkedin": 0},
        "senders": {"email": [{"provider_account_id":
                               mailbox["provider_account_id"],
                               "account_id": mailbox["account_id"]}],
                    "linkedin": []},
        "sending_window": COHORTS[spec["cohort"]]["window"],
        "bison_campaign_id": None,
        "heyreach_campaign_id": None,
        "launch": {"state": "not_launched", "at": None},
        "pause": None,
        "log": [], "events": [],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args(argv)

    icp, verify, mx, copy, people = load_inputs()
    mailboxes = attested_mailboxes()
    selection, held, spill = select(copy, icp, people)
    records = build_records(selection, icp, verify, mx, people)
    plan, spilled = assign(selection, records, mailboxes)

    total = sum(len(v) for v in selection.values())
    print(f"\nBATCH 1  client={CLIENT}\n")
    print(f"  leads with rendered copy      {len(copy)}")
    print(f"  selected under the pacing rule {total}")
    print(f"  accounts                      {len(records)}")
    for reason, count in held.most_common():
        print(f"  held: {reason[:50].ljust(50)} {count}")
    for cohort, count in spill.items():
        print(f"  reservoir ({cohort}): {count} over the cohort cap, waiting")
    for cohort, count in spilled.items():
        print(f"  reservoir ({cohort}): {count} more, every campaign in that "
              f"cohort is at its {PER_CAMPAIGN}-lead pacing cap")
    print("\n  campaigns")
    for human, spec in plan.items():
        mailbox = mailboxes[human]
        print(f"    {human:10s} {spec['cohort']:3s} "
              f"{spec['leads']:>4} leads  {len(spec['record_ids']):>4} accounts  "
              f"mailbox {mailbox['provider_account_id']:>5} "
              f"bounce {mailbox['bounce_rate'] * 100:.2f}%")

    if not args.write:
        print("\n  PLAN ONLY. Nothing was written. Pass --write.")
        return 0

    assigned = {rid for spec in plan.values() for rid in spec["record_ids"]}
    records = {k: v for k, v in records.items() if k in assigned}
    existing = {r.get("id") for r in store.load()}
    clash = existing & set(records)
    if clash:
        print(f"\n  REFUSED: {len(clash)} of these accounts are already in the "
              f"store, which is the double-enrolment risk condition 5 names. "
              f"First few: {sorted(clash)[:5]}")
        return 1

    with store.transaction() as current:
        for record in records.values():
            current.append(record)
    print(f"\n  wrote {len(records)} records")

    approved, refused = 0, collections.Counter()
    recs = {r.get("id"): r for r in store.load()}
    config = clients.load(CLIENT)
    updated = []
    for record_id, record in recs.items():
        if record_id not in records:
            continue
        for contact in record.get("contacts") or []:
            for step_key in STEP_KEYS:
                why = approve.why_not(record, contact["key"], step_key,
                                      config=config)
                if why:
                    refused[str(why)[:60]] += 1
                    continue
                approve.approve_step(record, contact["key"], step_key,
                                     by=APPROVER, config=config)
                approved += 1
        updated.append(record)
    with store.transaction() as current:
        by_id = {r.get("id"): i for i, r in enumerate(current)}
        for record in updated:
            if record.get("id") in by_id:
                current[by_id[record["id"]]] = record
    print(f"  approved {approved} steps")
    for reason, count in refused.most_common(8):
        print(f"    refused: {reason} x{count}")

    rows = campaigns.load()
    have = {r.get("campaign_id") for r in rows}
    written = 0
    for human, spec in plan.items():
        row = campaign_row(human, spec, mailboxes[human])
        if row["campaign_id"] in have:
            continue
        rows.append(row)
        written += 1
    campaigns.save(rows)
    print(f"  wrote {written} campaign rows")
    print("\n  Canonical only. No provider write has happened.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
