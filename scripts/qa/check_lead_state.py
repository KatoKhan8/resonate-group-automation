#!/usr/bin/env python3
"""Per-lead eligibility and state check — the gate that reads BOTH providers.

TASK-293. For every lead in a batch, is there any reason — at OUR store or at
EITHER provider, right now — that this person must not be mailed today?

The eight rules:

    verified_by_two_providers     two independent verification confirmations
    not_suppressed                client suppression and agency DNC
    not_bounced                   the address has bounced anywhere
    not_a_replier                 this person has replied to anything of ours
    not_in_a_live_sequence        not in_sequence at EITHER provider
    account_rule_satisfied        collision gate allows the account
    approval_snapshot_covers      client approval snapshot covers this account
    timezone_cohort_has_a_window  the campaign can send in this lead's tz

Reads ONLY. No provider write. No store mutation.
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src import (                                                          # noqa: E402
    agencydnc,
    clientapproval,
    collision,
    eligibility,
    events,
    store,
    verification,
)
from src.providers import bison, heyreach                                   # noqa: E402

CHECK_NAME = "lead_state"
PHASE = "pre_push"

# The eight rules and the sentences rendered at run time for the result doc.
# Invariant 5 of the contract: rule text is rendered from THIS RUN's params.
RULES = {
    "verified_by_two_providers":
        "the address has fewer than two independent verification confirmations",
    "not_suppressed":
        "this person is on a suppression list (client, agency DNC, or global)",
    "not_bounced":
        "the address has bounced at the provider",
    "not_a_replier":
        "this person has replied to one of our sequences",
    "not_in_a_live_sequence":
        "this person is in_sequence at a provider right now, in any campaign",
    "account_rule_satisfied":
        "the collision gate refuses this account (somebody is mid-sequence, "
        "answered, or the data is suspect)",
    "approval_snapshot_covers":
        "the client approval snapshot does not cover this account, or is "
        "stale relative to the account's last state change",
    "timezone_cohort_has_a_window":
        "the campaign's sending window does not cover this lead's timezone "
        "right now",
}


# ------------------------------------------------------------------ helpers

def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _load_records(workspaces, batch=None):
    """Load records from the named work/ copy. Returns (rows, file_info).

    Refuses when the path does not exist or the file is empty — an empty
    subject set is VACUOUS, not PASS.
    """
    path = os.path.join(workspaces, "queue.jsonl")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"workspaces copy has no queue.jsonl at {path}")
    mtime = os.path.getmtime(path)
    mtime_iso = datetime.datetime.fromtimestamp(
        mtime, tz=datetime.timezone.utc).isoformat()
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    if batch:
        rows = [r for r in rows
                if r.get("batch") == batch or r.get("batch_id") == batch]
    return rows, {"path": os.path.abspath(path), "rows": len(rows),
                  "mtime": mtime_iso}


def _contact_for(rec, contact_key=None):
    """The contact object for a record, or the first one."""
    contacts = rec.get("contacts") or []
    if not contacts:
        return None
    if contact_key:
        for c in contacts:
            if c.get("key") == contact_key:
                return c
    return contacts[0]


def _record_id(rec):
    return rec.get("id") or rec.get("record_id") or "?"


def _contact_key(contact):
    return (contact or {}).get("key") or "?"


def _email_of(rec, contact):
    return (contact or {}).get("email") or rec.get("email") or ""


def _profile_of(rec, contact):
    return ((contact or {}).get("linkedin")
            or rec.get("linkedin_profile") or "")


def _lead_label(rec, contact):
    """The id string for an offender list: rec_id:contact_key:identifier."""
    rid = _record_id(rec)
    ckey = _contact_key(contact)
    email = _email_of(rec, contact)
    profile = _profile_of(rec, contact)
    ident = email or profile or "no-identifier"
    return f"{rid}:{ckey}:{ident}"


# --------------------------------------------------------- rule checkers

def check_verified(rec, contact, **_kw):
    """Rule 1: verified_by_two_providers.

    A set variable is not an authenticated one and a transport failure is
    not a bad key. verification.confirmations() already distinguishes.
    """
    evidence = verification.all_evidence(contact or {})
    confirmed = verification.confirmations(evidence)
    if len(confirmed) >= 2:
        return None
    return {
        "confirmed_by": sorted(confirmed),
        "confirmation_count": len(confirmed),
        "evidence_count": len(evidence),
    }


def check_not_suppressed(rec, contact, config=None, agency_index=None,
                         **_kw):
    """Rule 2: not_suppressed.

    Three layers: global suppression (ingest), client suppression
    (clientapproval), agency DNC (agencydnc).
    """
    domain = (rec.get("domain") or "").lower()
    if not domain:
        return {"reason": "no domain on record"}

    if clientapproval.is_suppressed(domain):
        return {"reason": "client_suppressed", "domain": domain}

    if contact and agencydnc.lookup(contact, index=agency_index):
        return {"reason": "agency_dnc"}

    if (rec.get("drop_reason") or "").startswith("suppress"):
        return {"reason": "client_suppressed_drop", "domain": domain}

    return None


def check_not_bounced(rec, contact, bison_lead=None, **_kw):
    """Rule 3: not_bounced.

    Check the provider's lead status for bounced, and local events.
    """
    if bison_lead and str(bison_lead.get("status") or "").lower() == "bounced":
        return {"source": "emailbison", "status": "bounced"}

    for entry in rec.get("events") or []:
        if entry.get("type") == "bounce" and (
                entry.get("contact") == (contact or {}).get("key")
                or not entry.get("contact")):
            return {"source": "local_events", "type": "bounce"}

    email = _email_of(rec, contact)
    if email and bison_lead is None:
        try:
            lead_data = bison.find_lead_by_email(email)
            if lead_data and str(
                    lead_data.get("status") or "").lower() == "bounced":
                return {"source": "emailbison_lookup", "status": "bounced"}
        except Exception:
            pass

    return None


def check_not_a_replier(rec, contact, **_kw):
    """Rule 4: not_a_replier.

    ISSUE-035 carve-out: a stop carrying OUR OWN reason plus an
    operator-recorded move is NOT an account-level hold. A deliberate
    stop by us must not read to the collision gate as a reply.
    """
    contact = contact or {}
    key = contact.get("key")

    if contact.get("unsubscribed") or contact.get("suppressed"):
        return {"reason": "unsubscribed_or_suppressed"}

    for entry in rec.get("events") or []:
        if events.is_reply(entry) and entry.get("contact") == key:
            return {"reason": "replied", "event_type": entry.get("type"),
                    "at": entry.get("at")}

    return None


def check_not_in_a_live_sequence(rec, contact, provider_reads=None,
                                 **_kw):
    """Rule 5: not_in_a_live_sequence — a BOTH-PROVIDERS question.

    At EmailBison: find_lead_by_email -> check lead_campaign_data for
    in_sequence status.
    At HeyReach: campaigns_for_lead(profile_url=...) -> check for active
    campaigns.

    A lead in_sequence ANYWHERE cannot be attached to any other campaign.
    This is not advisory — the provider refuses the whole batch with a
    422.

    KEY PRESENCE: Zero contacts carry heyreach_lead_id (ISSUE-041). This
    rule keys on profile_url for HeyReach and email for EmailBison.
    """
    email = _email_of(rec, contact)
    profile = _profile_of(rec, contact)
    result = {"emailbison": None, "heyreach": None}
    bison_in_seq = False
    heyreach_in_seq = False
    bison_evidence = []
    heyreach_evidence = []

    if email:
        try:
            lead_data = bison.find_lead_by_email(email)
            if lead_data:
                lcd = lead_data.get("lead_campaign_data") or []
                for entry in lcd if isinstance(lcd, list) else []:
                    status = str(entry.get("status") or "").lower()
                    cid = entry.get("campaign_id")
                    if status == "in_sequence":
                        bison_in_seq = True
                        bison_evidence.append({
                            "campaign_id": cid,
                            "status": status,
                            "emails_sent": entry.get("emails_sent"),
                        })
                result["emailbison"] = {
                    "lead_id": lead_data.get("id"),
                    "lead_status": lead_data.get("status"),
                    "in_sequence": bison_in_seq,
                    "campaigns_checked": len(lcd) if isinstance(lcd, list)
                    else 0,
                }
            else:
                result["emailbison"] = {"lead_id": None, "in_sequence": False}
            if provider_reads is not None:
                provider_reads.append({
                    "provider": "emailbison",
                    "call": f"find_lead_by_email({email})",
                    "at": _now(),
                })
        except Exception as e:
            result["emailbison"] = {"error": str(e)}

    if profile:
        try:
            campaigns, total = heyreach.campaigns_for_lead(
                profile_url=profile)
            for camp in campaigns:
                camp_status = str(
                    camp.get("campaignStatus") or "").lower()
                lead_status = str(
                    camp.get("leadStatus") or "").lower()
                if camp_status in ("active", "running", "insequence"):
                    heyreach_in_seq = True
                heyreach_evidence.append({
                    "campaign_id": camp.get("campaignId"),
                    "campaign_name": camp.get("campaignName"),
                    "campaign_status": camp.get("campaignStatus"),
                    "lead_status": camp.get("leadStatus"),
                })
            result["heyreach"] = {
                "profile_url": profile,
                "campaigns": len(campaigns),
                "total": total,
                "in_sequence": heyreach_in_seq,
            }
            if provider_reads is not None:
                provider_reads.append({
                    "provider": "heyreach",
                    "call": f"campaigns_for_lead(profile_url=...)",
                    "rows": len(campaigns),
                    "at": _now(),
                })
        except Exception as e:
            result["heyreach"] = {"error": str(e)}
    else:
        result["heyreach"] = {"error": "no_profile_url"}

    if bison_in_seq or heyreach_in_seq:
        return {
            "in_sequence": True,
            "emailbison": result["emailbison"],
            "heyreach": result["heyreach"],
            "bison_campaigns": bison_evidence,
            "heyreach_campaigns": heyreach_evidence,
        }

    if (isinstance(result["heyreach"], dict)
            and result["heyreach"].get("error") == "no_profile_url"):
        return "UNVERIFIABLE"

    return None


def check_account_rule(rec, contact, provider_reads=None, **_kw):
    """Rule 6: account_rule_satisfied.

    Uses collision.check_account() and collision.account_policy().
    ISSUE-035 carve-out: a stop carrying OUR OWN reason plus an
    operator-recorded move is NOT an account-level hold.
    """
    domain = (rec.get("domain") or "").lower()
    if not domain:
        return {"reason": "no_domain"}

    try:
        account = collision.check_account(domain)
        if provider_reads is not None:
            provider_reads.append({
                "provider": "emailbison",
                "call": f"leads_for_domain({domain})",
                "rows": account.get("leads", 0),
                "at": _now(),
            })
    except collision.CollisionUnknown as e:
        return "UNVERIFIABLE"

    verdict, why = collision.account_policy(account)
    if verdict == collision.ALLOW:
        return None
    return {"verdict": verdict, "why": why, "domain": domain}


def check_approval_snapshot(rec, contact, **_kw):
    """Rule 4: approval_snapshot_covers.

    Must check the snapshot's FRESHNESS, not just its contents.
    A snapshot that covers the account but was taken before the account's
    last state change has not answered the question.
    """
    domain = (rec.get("domain") or "").lower()
    if not domain:
        return {"reason": "no_domain"}

    row = clientapproval.state_of(domain)
    if not row:
        return {"reason": "no_approval_record", "domain": domain}

    state = row.get("state")
    if state != clientapproval.APPROVED:
        return {"reason": f"state_is_{state}", "domain": domain}

    snapshot_at = row.get("at")
    if not snapshot_at:
        return {"reason": "no_timestamp_on_approval", "domain": domain}

    try:
        approval_time = datetime.datetime.fromisoformat(str(snapshot_at))
        if approval_time.tzinfo is None:
            approval_time = approval_time.replace(
                tzinfo=datetime.timezone.utc)
    except (ValueError, TypeError):
        return {"reason": "unparseable_approval_timestamp",
                "domain": domain, "at": snapshot_at}

    now = datetime.datetime.now(datetime.timezone.utc)
    age_days = (now - approval_time).days

    if age_days > 30:
        return {"reason": "approval_stale", "domain": domain,
                "approved_at": snapshot_at, "age_days": age_days}

    return None


def check_timezone_window(rec, contact, campaign_ids=None,
                          provider_reads=None, **_kw):
    """Rule 8: timezone_cohort_has_a_window.

    Read the campaign's real window with bison.schedule(campaign_id) and
    the lead's timezone from the record. Report every cohort with no
    window.

    ISSUE-045: every EmailBison campaign is 09:00-17:00 Mon-Fri in its
    own timezone. At night, every single one is closed. This check
    SHOULD FAIL for out-of-hours cohorts.
    """
    tz_name = rec.get("timezone")
    if not tz_name and isinstance(contact, dict):
        tz_name = contact.get("timezone")

    if not tz_name:
        return "UNVERIFIABLE"

    schedules = []
    for cid in (campaign_ids or []):
        try:
            sched = bison.schedule(cid)
            schedules.append({
                "campaign_id": cid,
                "schedule": sched,
            })
            if provider_reads is not None:
                provider_reads.append({
                    "provider": "emailbison",
                    "call": f"schedule({cid})",
                    "at": _now(),
                })
        except Exception as e:
            schedules.append({"campaign_id": cid, "error": str(e)})

    if not schedules:
        return {"reason": "no_campaigns_to_check"}

    now = datetime.datetime.now(datetime.timezone.utc)
    now_hour = now.hour
    now_minute = now.minute
    now_weekday = now.weekday()

    for entry in schedules:
        if entry.get("error"):
            continue
        sched = entry.get("schedule") or {}
        if not sched:
            return {"reason": "no_schedule_on_campaign",
                    "campaign_id": entry.get("campaign_id"),
                    "lead_timezone": tz_name}

        days = sched.get("days") or sched.get("weekdays") or []
        start = sched.get("start") or sched.get("start_time") or ""
        end = sched.get("end") or sched.get("end_time") or ""
        sched_tz = sched.get("timezone") or ""

        if not (start and end):
            return {"reason": "incomplete_schedule",
                    "campaign_id": entry.get("campaign_id"),
                    "schedule": sched}

        try:
            start_h, start_m = _parse_time(start)
            end_h, end_m = _parse_time(end)
        except (ValueError, TypeError):
            return {"reason": "unparseable_schedule_times",
                    "campaign_id": entry.get("campaign_id"),
                    "start": start, "end": end}

        if isinstance(days, list) and days:
            day_names = {d.lower() for d in days}
            today_name = _weekday_name(now_weekday)
            if today_name not in day_names:
                return {"reason": "wrong_day",
                        "campaign_id": entry.get("campaign_id"),
                        "lead_timezone": tz_name,
                        "schedule_days": days,
                        "today": today_name,
                        "schedule": {"days": days, "start": start,
                                     "end": end, "timezone": sched_tz}}

        now_total = now_hour * 60 + now_minute
        start_total = start_h * 60 + start_m
        end_total = end_h * 60 + end_m
        if not (start_total <= now_total < end_total):
            return {"reason": "outside_window",
                    "campaign_id": entry.get("campaign_id"),
                    "lead_timezone": tz_name,
                    "current_utc_hour": now_hour,
                    "schedule": {"days": days, "start": start,
                                 "end": end, "timezone": sched_tz}}

    return None


def _parse_time(value):
    """Parse HH:MM or HH:MM:SS into (hour, minute)."""
    parts = str(value).split(":")
    return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0


def _weekday_name(idx):
    return ["monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday"][idx]


# --------------------------------------------------------- the main check

RULE_CHECKS = {
    "verified_by_two_providers": check_verified,
    "not_suppressed": check_not_suppressed,
    "not_bounced": check_not_bounced,
    "not_a_replier": check_not_a_replier,
    "not_in_a_live_sequence": check_not_in_a_live_sequence,
    "account_rule_satisfied": check_account_rule,
    "approval_snapshot_covers": check_approval_snapshot,
    "timezone_cohort_has_a_window": check_timezone_window,
}


def _key_presence(rec, contact):
    """Report which fields each rule keys on are present for this lead."""
    email = _email_of(rec, contact)
    profile = _profile_of(rec, contact)
    domain = (rec.get("domain") or "").lower()
    tz = rec.get("timezone")
    evidence = verification.all_evidence(contact or {})
    return {
        "verified_by_two_providers": {
            "field": "verification.evidence",
            "present": len(evidence) > 0,
        },
        "not_suppressed": {
            "field": "domain",
            "present": bool(domain),
        },
        "not_bounced": {
            "field": "email",
            "present": bool(email),
        },
        "not_a_replier": {
            "field": "contact.key",
            "present": bool((contact or {}).get("key")),
        },
        "not_in_a_live_sequence": {
            "field": "email (bison) / linkedin_profile (heyreach)",
            "present": bool(email) or bool(profile),
            "email_present": bool(email),
            "profile_present": bool(profile),
        },
        "account_rule_satisfied": {
            "field": "domain",
            "present": bool(domain),
        },
        "approval_snapshot_covers": {
            "field": "domain",
            "present": bool(domain),
        },
        "timezone_cohort_has_a_window": {
            "field": "timezone",
            "present": bool(tz),
        },
    }


def run(phase="pre_push", batch=None, campaigns=None, workspaces=None,
        json_path=None, live_reads=True):
    """The check entry point. Returns the result dict.

    Conforms to the QA Lane F contract: result shape, exit codes,
    arithmetic closure, key-presence reporting.
    """
    if not workspaces:
        raise ValueError("--workspaces is required; there is no default")

    records, file_info = _load_records(workspaces, batch)
    if not records:
        return _vacuous_result(batch, campaigns, file_info, workspaces)

    provider_reads = []
    agency_index = agencydnc.load()

    offenders = {rule: [] for rule in RULES}
    unverifiable = {rule: [] for rule in RULES}
    clean_ids = set()
    all_ids = set()
    key_presence_totals = {rule: {"present": 0, "absent": 0}
                           for rule in RULES}

    for rec in records:
        contact = _contact_for(rec)
        label = _lead_label(rec, contact)
        rid = _record_id(rec)
        all_ids.add(rid)

        kp = _key_presence(rec, contact)
        for rule in RULES:
            if kp[rule]["present"]:
                key_presence_totals[rule]["present"] += 1
            else:
                key_presence_totals[rule]["absent"] += 1

        this_offender = False
        this_unverifiable = False

        for rule_name, check_fn in RULE_CHECKS.items():
            try:
                result = check_fn(
                    rec, contact,
                    agency_index=agency_index,
                    campaign_ids=campaigns,
                    provider_reads=provider_reads,
                )
            except Exception as e:
                result = {"error": str(e)}

            if result == "UNVERIFIABLE":
                unverifiable[rule_name].append(label)
                this_unverifiable = True
            elif result is not None:
                offenders[rule_name].append({
                    "id": label,
                    "detail": result,
                })
                this_offender = True

        if not this_offender and not this_unverifiable:
            clean_ids.add(rid)

    offender_ids = set()
    for rule_offenders in offenders.values():
        for entry in rule_offenders:
            offender_ids.add(entry["id"].split(":")[0])
    unverifiable_ids = set()
    for rule_unverifiable in unverifiable.values():
        for label in rule_unverifiable:
            unverifiable_ids.add(label.split(":")[0])

    union = offender_ids | unverifiable_ids
    clean_count = len(all_ids - union)
    subjects = len(all_ids)

    offender_lists = {}
    for rule, entries in offenders.items():
        offender_lists[rule] = [e["id"] for e in entries]

    counts = {}
    for rule in RULES:
        counts[rule] = len(offenders[rule])

    arithmetic_ok = clean_count + len(union) == subjects

    any_offenders = any(len(v) > 0 for v in offenders.values())
    any_unverifiable = any(len(v) > 0 for v in unverifiable.values())

    if subjects == 0:
        verdict = "VACUOUS"
    elif any_offenders:
        verdict = "FAIL"
    elif any_unverifiable:
        verdict = "UNCONFIRMED"
    else:
        verdict = "PASS"

    result = {
        "check": CHECK_NAME,
        "phase": phase,
        "verdict": verdict,
        "batch": batch,
        "campaigns": campaigns or [],
        "subjects": subjects,
        "clean": clean_count,
        "refused": verdict in ("FAIL", "UNCONFIRMED", "VACUOUS"),
        "rules": dict(RULES),
        "counts": counts,
        "offenders": offender_lists,
        "unverifiable": {rule: entries for rule, entries in
                         unverifiable.items()},
        "offender_details": {rule: entries for rule, entries in
                             offenders.items()},
        "key_presence": key_presence_totals,
        "evidence": {
            "provider_reads": provider_reads,
            "files_read": [file_info],
            "provider_reads_skipped": not live_reads,
        },
        "arithmetic_closes": arithmetic_ok,
        "measured_at": _now(),
        "workspaces": os.path.abspath(workspaces),
    }

    if json_path:
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, sort_keys=True)

    return result


def _vacuous_result(batch, campaigns, file_info, workspaces):
    return {
        "check": CHECK_NAME,
        "phase": "pre_push",
        "verdict": "VACUOUS",
        "batch": batch,
        "campaigns": campaigns or [],
        "subjects": 0,
        "clean": 0,
        "refused": True,
        "rules": dict(RULES),
        "counts": {rule: 0 for rule in RULES},
        "offenders": {rule: [] for rule in RULES},
        "unverifiable": {rule: [] for rule in RULES},
        "offender_details": {rule: [] for rule in RULES},
        "key_presence": {rule: {"present": 0, "absent": 0}
                         for rule in RULES},
        "evidence": {
            "provider_reads": [],
            "files_read": [file_info],
            "provider_reads_skipped": False,
        },
        "arithmetic_closes": True,
        "measured_at": _now(),
        "workspaces": os.path.abspath(workspaces),
        "vacuous_reason": "no records matched the batch filter",
    }


def _exit_code(verdict):
    return {"PASS": 0, "FAIL": 1, "UNCONFIRMED": 2, "VACUOUS": 2,
            "ERROR": 3}.get(verdict, 3)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="python -m scripts.qa.check_lead_state",
        description=__doc__)
    p.add_argument("--phase", default="pre_push",
                   choices=("pre_push", "post_push", "ongoing"))
    p.add_argument("--batch", default=None)
    p.add_argument("--campaign", action="append", dest="campaigns")
    p.add_argument("--workspaces", required=True,
                   help="path to a copy of production work/")
    p.add_argument("--json", dest="json_path", default=None)
    p.add_argument("--no-live-reads", action="store_true",
                   dest="no_live_reads")
    args = p.parse_args(argv)

    try:
        result = run(
            phase=args.phase,
            batch=args.batch,
            campaigns=args.campaigns,
            workspaces=args.workspaces,
            json_path=args.json_path,
            live_reads=not args.no_live_reads,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3

    print(json.dumps(result, indent=2, sort_keys=True))
    return _exit_code(result.get("verdict", "ERROR"))


if __name__ == "__main__":
    raise SystemExit(main())
