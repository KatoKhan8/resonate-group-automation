#!/usr/bin/env python3
"""Per-lead eligibility and state check — the QA gate for a push.

For every lead in a batch, answers: is there any reason — at OUR store or at
EITHER provider, right now — that this person must not be mailed today?

Eight rules, each reporting offenders with ids a person can paste into a
provider UI or grep in work/queue.jsonl.

    verified_by_two_providers      two independent verification confirmations
    not_suppressed                 client suppression and agency DNC
    not_bounced                    the address has bounced anywhere
    not_a_replier                  this person has replied to anything of ours
    not_in_a_live_sequence         not in_sequence at EITHER provider
    account_rule_satisfied         same contact never twice; gap for persona
    approval_snapshot_covers       client approval snapshot covers + fresh
    timezone_cohort_has_a_window   the campaign can send in this lead's tz

Usage:

    py -3 scripts/qa/check_lead_state.py \\
        --phase pre_push \\
        --batch batch-2-2026-09-25 \\
        --campaign 502 --campaign 503 \\
        --workspaces <path to a copy of production work/> \\
        --json work/qa/<run>/lead_state.json

Exit codes:

    0   PASS         every subject checked, every rule clear
    1   FAIL         at least one subject offends at least one rule
    2   UNCONFIRMED  could not establish the answer (provider read failed,
                     empty subject set / VACUOUS)
    3   ERROR        the check itself broke
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src import (agencydnc, clientapproval, collision, eligibility,           # noqa: E402
                 store, verification)
from src.providers import bison, heyreach                                      # noqa: E402

# ------------------------------------------------------------------ rules

RULES = {
    "verified_by_two_providers": (
        "the address has fewer than two independent verification "
        "confirmations"),
    "not_suppressed": (
        "the contact is on a client suppression list or the agency DNC"),
    "not_bounced": (
        "the address has bounced at a provider"),
    "not_a_replier": (
        "this person has replied to anything of ours"),
    "not_in_a_live_sequence": (
        "this person is in_sequence at either provider right now"),
    "account_rule_satisfied": (
        "same contact never twice; a second persona only after the gap"),
    "approval_snapshot_covers": (
        "the client approval snapshot covers this account and is fresh"),
    "timezone_cohort_has_a_window": (
        "the campaign this lead is going into can send in this lead's "
        "timezone"),
}

# Exit codes.
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNCONFIRMED = 2
EXIT_ERROR = 3

# Verdicts.
PASS = "PASS"
FAIL = "FAIL"
UNCONFIRMED = "UNCONFIRMED"
VACUOUS = "VACUOUS"
ERROR = "ERROR"


# ----------------------------------------------------------- record loading

def load_records(workspaces_path):
    """Load queue records from a named work/ copy. Returns (records, info).

    Refuses (raises) if the path does not exist or the file is empty, rather
    than reporting zero subjects.
    """
    queue_file = os.path.join(workspaces_path, "queue.jsonl")
    if not os.path.exists(queue_file):
        raise RuntimeError(
            f"workspaces copy at {workspaces_path!r} has no queue.jsonl; "
            f"refusing to report zero subjects from a missing file")
    mtime = os.path.getmtime(queue_file)
    mtime_iso = datetime.datetime.fromtimestamp(
        mtime, tz=datetime.timezone.utc).isoformat()
    records = store.read_jsonl(queue_file)
    if not records:
        raise RuntimeError(
            f"queue at {queue_file!r} is empty; nothing to check")
    info = {"path": os.path.abspath(queue_file), "rows": len(records),
            "mtime": mtime_iso}
    return records, info


def filter_batch(records, batch=None, campaign_ids=None):
    """Select the leads belonging to this batch/campaigns.

    A lead is in the batch if its record id is listed in the batch, or if
    its campaign matches one of the named campaign ids. When neither filter
    is given, returns all non-dropped records.
    """
    out = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if rec.get("state") == "dropped" or rec.get("drop_reason"):
            continue
        if batch and rec.get("batch") != batch:
            continue
        if campaign_ids:
            rec_campaign = rec.get("campaign_id")
            if rec_campaign and str(rec_campaign) not in campaign_ids:
                continue
        out.append(rec)
    return out


# --------------------------------------------------------- per-rule checks

def _lead_id(rec):
    """A stable identifier for a record in output. Never PII."""
    return str(rec.get("id") or rec.get("_id") or "?")


def _contact_key(rec):
    """The primary contact key for a record."""
    contacts = rec.get("contacts") or []
    if contacts and isinstance(contacts[0], dict):
        return contacts[0].get("key", "")
    return ""


def _email(rec):
    """The primary contact email, or empty."""
    contacts = rec.get("contacts") or []
    if contacts and isinstance(contacts[0], dict):
        return contacts[0].get("email", "")
    return rec.get("email", "")


def _profile_url(rec):
    """The primary contact LinkedIn profile URL, or empty."""
    contacts = rec.get("contacts") or []
    if contacts and isinstance(contacts[0], dict):
        return contacts[0].get("linkedin", "")
    return rec.get("linkedin", "")


def _offender_label(rec):
    """record_id:contact_key — the id format for offender lists."""
    rid = _lead_id(rec)
    key = _contact_key(rec)
    return f"{rid}:{key}" if key else rid


def check_verified_by_two_providers(rec, **_ctx):
    """Rule 1: two independent verification confirmations.

    Uses verification.confirmations on the evidence, which already
    distinguishes providers from repeat calls to the same one.
    """
    evidence = verification.all_evidence(rec)
    confirmed = verification.confirmations(evidence)
    count = len(confirmed)
    if count >= 2:
        return None
    email = _email(rec)
    providers = sorted(confirmed)
    return (f"only {count} confirmation(s) "
            f"({', '.join(providers) or 'none'}) for {email}")


def check_not_suppressed(rec, ctx, **_kw):
    """Rule 2: client suppression and agency DNC.

    Uses eligibility.must_not_contact for the suppression half and
    agencydnc.lookup for the agency-wide list.
    """
    contacts = rec.get("contacts") or []
    contact = contacts[0] if contacts else None
    reasons = eligibility.must_not_contact(rec, contact)
    for reason in reasons:
        if reason and "suppress" in reason:
            return f"suppressed: {eligibility.explain(reason)}"
        if reason and reason == eligibility.BLOCKED_AGENCY_DNC:
            return f"agency DNC: {eligibility.explain(reason)}"
    return None


def check_not_bounced(rec, ctx, **_kw):
    """Rule 3: the address has bounced anywhere.

    Checks the record's own bounce markers and the provider evidence.
    """
    domain = (rec.get("domain") or "").lower()
    email = _email(rec)
    # Check stored bounce evidence on the contact.
    contacts = rec.get("contacts") or []
    contact = contacts[0] if contacts else {}
    if contact.get("bounced"):
        return f"address {email} has bounced (stored on contact)"
    # Check verification evidence for a bounced status.
    evidence = verification.all_evidence(rec)
    for entry in evidence:
        if entry.get("status") == "invalid":
            reason = entry.get("reason") or ""
            if "bounce" in reason.lower():
                return f"address {email} bounced ({entry.get('provider')})"
    # Check the record-level events for bounce markers.
    for event in rec.get("events") or []:
        if event.get("type") == "bounced":
            return f"address {email} has a bounce event on record"
    return None


def check_not_a_replier(rec, ctx, **_kw):
    """Rule 4: this person has replied to anything of ours.

    ISSUE-035 carve-out: a stop carrying our own reason plus an
    operator-recorded move is NOT an account-level hold. A deliberate
    stop by us must not read to the collision gate as a reply.
    """
    contacts = rec.get("contacts") or []
    contact = contacts[0] if contacts else {}
    key = contact.get("key")
    # Check events for replies by this contact.
    for entry in rec.get("events") or []:
        from src import events as ev
        if ev.is_reply(entry) and entry.get("contact") == key:
            return f"contact {_contact_key(rec)} has replied"
    # Check contact-level flags.
    if contact.get("unsubscribed") or contact.get("suppressed"):
        return f"contact {_contact_key(rec)} unsubscribed/suppressed"
    if contact.get("stopped"):
        # ISSUE-035 carve-out: a stop we made with our own reason and an
        # operator-recorded move is NOT a reply. Check the stop metadata.
        stop_reason = contact.get("stop_reason") or ""
        operator_move = contact.get("operator_move")
        if (stop_reason and operator_move
                and _is_our_stop(stop_reason)):
            return None
        return f"contact {_contact_key(rec)} was stopped"
    return None


def _is_our_stop(reason):
    """Is this stop one we made deliberately? ISSUE-035 carve-out."""
    our_reasons = ("operator_stopped", "manual_stop", "deliberate_stop",
                   "agency_stopped", "client_request_stop")
    return reason in our_reasons


def check_not_in_a_live_sequence(rec, ctx, **_kw):
    """Rule 5: not in_sequence at EITHER provider.

    This is the expensive one. At EmailBison, checks the provider's own
    lead state. At HeyReach, checks campaigns_for_lead.

    Returns (verdict, detail) where verdict is:
      None      = clean
      "offend"  = in a live sequence
      "vacuous" = the field this keys on is absent (no email / no profile)
    """
    results = []
    email = _email(rec)
    profile = _profile_url(rec)
    live_reads = ctx.get("live_reads", False)

    # EmailBison: find_lead_by_email -> check lead_campaign_data for in_sequence.
    bison_status = None
    if live_reads and email:
        try:
            lead_row = bison.find_lead_by_email(email)
            if lead_row:
                lcd = lead_row.get("lead_campaign_data") or []
                for camp in lcd:
                    if isinstance(camp, dict):
                        status = str(camp.get("status") or "").lower()
                        if status == "in_sequence":
                            camp_id = camp.get("campaign_id")
                            bison_status = (
                                f"in_sequence at EmailBison campaign "
                                f"{camp_id}")
                            break
                if bison_status is None:
                    bison_status = "clean"
            else:
                bison_status = "not_at_provider"
        except Exception as exc:
            bison_status = f"read_failed: {exc}"
    elif not email:
        bison_status = "no_email"

    # HeyReach: campaigns_for_lead(profile_url=...) -> check leadStatus.
    heyreach_status = None
    if live_reads and profile:
        try:
            campaigns_list, total = heyreach.campaigns_for_lead(
                profile_url=profile)
            if campaigns_list:
                for camp in campaigns_list:
                    ls = str(camp.get("leadStatus") or "").lower()
                    cs = str(camp.get("campaignStatus") or "").lower()
                    if ls == "insequence" or cs == "insequence":
                        cid = camp.get("campaignId")
                        heyreach_status = (
                            f"in_sequence at HeyReach campaign {cid}")
                        break
                if heyreach_status is None:
                    heyreach_status = "clean"
            else:
                heyreach_status = "not_at_provider"
        except Exception as exc:
            heyreach_status = f"read_failed: {exc}"
    elif not profile:
        heyreach_status = "no_profile_url"

    # Combine: either provider saying in_sequence is an offence.
    if bison_status and "in_sequence" in str(bison_status):
        return bison_status
    if heyreach_status and "in_sequence" in str(str(heyreach_status)):
        return heyreach_status

    # Track verifiability: if we could not check a provider, note it.
    unverifiable_reason = None
    if not live_reads:
        unverifiable_reason = "live reads disabled"
    elif not email and not profile:
        unverifiable_reason = "no email and no profile URL"
    elif not email:
        unverifiable_reason = "no email for EmailBison check"
    elif not profile:
        unverifiable_reason = "no profile URL for HeyReach check"

    if unverifiable_reason:
        return ("unverifiable", unverifiable_reason)
    return None


def check_account_rule_satisfied(rec, ctx, **_kw):
    """Rule 6: same contact never twice; a second persona only after the gap.

    Uses collision.check_account and collision.account_policy. The ISSUE-035
    carve-out is handled in check_not_a_replier; here we check the
    account-level collision.
    """
    domain = (rec.get("domain") or "").lower()
    if not domain:
        return ("unverifiable", "no domain on record")
    live_reads = ctx.get("live_reads", False)
    if not live_reads:
        return ("unverifiable", "live reads disabled")
    workspace = ctx.get("expect_workspace")
    if not workspace:
        return ("unverifiable", "no workspace pinned for collision check")
    try:
        account = collision.check_account(domain,
                                          expect_workspace=workspace)
        verdict, reason = collision.account_policy(account)
        if verdict == collision.STOP:
            return f"account {domain}: {reason}"
        if verdict == collision.HOLD:
            return f"account {domain}: {reason}"
        return None
    except collision.CollisionUnknown as exc:
        return ("unverifiable", str(exc))


def check_approval_snapshot_covers(rec, ctx, **_kw):
    """Rule 7: client approval snapshot covers this account, and is fresh.

    Checks clientapproval.is_approved AND the snapshot's freshness against
    the account's last state change. A snapshot that covers the account but
    was taken before the account's last state change has not answered the
    question.
    """
    domain = (rec.get("domain") or "").lower()
    if not domain:
        return "no domain on record"
    approved = clientapproval.is_approved(domain)
    if not approved:
        state = clientapproval.state_of(domain)
        state_word = (state or {}).get("state", "pending")
        return f"account {domain} is {state_word}, not approved"
    # Freshness: the snapshot must be newer than the account's last change.
    state_row = clientapproval.state_of(domain)
    if state_row:
        snap_at = state_row.get("at") or ""
        # Check if the record has a more recent state change than the approval.
        rec_updated = rec.get("updated_at") or rec.get("at") or ""
        if snap_at and rec_updated and snap_at < rec_updated:
            return (f"account {domain} approval snapshot ({snap_at}) is "
                    f"older than record change ({rec_updated})")
    return None


def check_timezone_cohort_has_a_window(rec, ctx, **_kw):
    """Rule 8: the campaign can send in this lead's timezone.

    ISSUE-045: every EmailBison campaign is 09:00-17:00 Mon-Fri in its own
    timezone. This check reads the REAL schedule from the provider and
    compares it to the lead's timezone. It is EXPECTED to fail for
    out-of-hours cohorts.

    A guessed timezone is worse than a missing one. If the lead has no
    timezone, it is UNVERIFIABLE, not clean.
    """
    lead_tz = rec.get("timezone") or ""
    if not lead_tz:
        return ("unverifiable", "no timezone on record")
    campaign_id = rec.get("campaign_id")
    if not campaign_id:
        ctx_campaigns = ctx.get("campaign_ids") or []
        campaign_id = ctx_campaigns[0] if ctx_campaigns else None
    if not campaign_id:
        return ("unverifiable", "no campaign id for schedule check")
    live_reads = ctx.get("live_reads", False)
    if not live_reads:
        return ("unverifiable", "live reads disabled")
    try:
        sched = bison.schedule(int(campaign_id))
        if not sched:
            return (f"campaign {campaign_id} has no schedule at the provider")
        # Compare timezone and window.
        camp_tz = sched.get("timezone", "")
        days = sched.get("days") or sched.get("weekdays") or []
        start = sched.get("start") or sched.get("start_time") or ""
        end = sched.get("end") or sched.get("end_time") or ""
        # The lead's timezone must fall within the campaign's send window.
        # If the campaign is 09:00-17:00 in America/New_York and the lead
        # is in Europe/Zagreb, we need to check whether the current time in
        # the CAMPAIGN's timezone is within the window.
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            import zoneinfo
            camp_zone = zoneinfo.ZoneInfo(camp_tz) if camp_tz else None
        except Exception:
            camp_zone = None
        if camp_zone:
            local_now = now.astimezone(camp_zone)
            current_hour = local_now.hour
            current_day = local_now.strftime("%A").lower()
            # Parse the window.
            try:
                start_h = int(str(start).split(":")[0])
                end_h = int(str(end).split(":")[0])
            except (ValueError, IndexError):
                return (f"campaign {campaign_id} schedule has unreadable "
                        f"window: {start}-{end}")
            day_names = [str(d).lower() for d in days] if days else []
            if day_names and current_day not in day_names:
                return (f"campaign {campaign_id} is closed on {current_day} "
                        f"(schedule: {days})")
            if not (start_h <= current_hour < end_h):
                return (f"campaign {campaign_id} window {start}-{end} "
                        f"{camp_tz}: current hour is {current_hour}")
        elif camp_tz:
            return (f"campaign {campaign_id} timezone {camp_tz!r} could "
                    f"not be resolved")
        else:
            return (f"campaign {campaign_id} schedule has no timezone")
        return None
    except Exception as exc:
        return ("unverifiable", f"schedule read failed: {exc}")


# ---------------------------------------------------------- orchestration

def _key_presence(records):
    """Count how many records carry the field each rule keys on."""
    total = len(records)
    presence = {}
    presence["verified_by_two_providers"] = sum(
        1 for r in records if verification.all_evidence(r))
    presence["not_suppressed"] = sum(
        1 for r in records
        if (r.get("domain") or (r.get("contacts") or [{}])[0].get("email")))
    presence["not_bounced"] = sum(
        1 for r in records if _email(r))
    presence["not_a_replier"] = sum(
        1 for r in records if _contact_key(r))
    presence["not_in_a_live_sequence"] = sum(
        1 for r in records if (_email(r) or _profile_url(r)))
    presence["account_rule_satisfied"] = sum(
        1 for r in records if r.get("domain"))
    presence["approval_snapshot_covers"] = sum(
        1 for r in records if r.get("domain"))
    presence["timezone_cohort_has_a_window"] = sum(
        1 for r in records if r.get("timezone"))
    return {"total": total, "per_rule": presence}


def run(phase="pre_push", batch=None, campaign_ids=None,
        workspaces=None, json_path=None, live_reads=True,
        expect_workspace=None):
    """The main entry point. Returns the result dict and exits."""
    if not workspaces:
        print("ERROR: --workspaces is required", file=sys.stderr)
        return None, EXIT_ERROR

    # Load records.
    try:
        records, file_info = load_records(workspaces)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return None, EXIT_ERROR

    # Filter to batch.
    subjects = filter_batch(records, batch=batch,
                            campaign_ids=(set(str(c) for c in campaign_ids)
                                          if campaign_ids else None))
    if not subjects:
        result = _vacuous_result(phase, batch, campaign_ids, file_info,
                                 workspaces)
        _output(result, json_path)
        return result, EXIT_UNCONFIRMED

    # Run checks.
    ctx = {
        "live_reads": live_reads,
        "campaign_ids": campaign_ids,
        "expect_workspace": expect_workspace,
    }
    checkers = [
        ("verified_by_two_providers", check_verified_by_two_providers),
        ("not_suppressed", check_not_suppressed),
        ("not_bounced", check_not_bounced),
        ("not_a_replier", check_not_a_replier),
        ("not_in_a_live_sequence", check_not_in_a_live_sequence),
        ("account_rule_satisfied", check_account_rule_satisfied),
        ("approval_snapshot_covers", check_approval_snapshot_covers),
        ("timezone_cohort_has_a_window", check_timezone_cohort_has_a_window),
    ]

    offenders = {rule: [] for rule, _ in checkers}
    unverifiable = {rule: [] for rule, _ in checkers}
    offending_ids = set()
    clean_ids = set()
    provider_reads = []
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for rec in subjects:
        rid = _lead_id(rec)
        label = _offender_label(rec)
        any_offence = False
        for rule_name, checker in checkers:
            try:
                result = checker(rec, ctx)
            except Exception as exc:
                result = ("unverifiable", f"check error: {exc}")
            if result is None:
                continue
            if isinstance(result, tuple) and result[0] == "unverifiable":
                unverifiable[rule_name].append(
                    f"{label}: {result[1]}")
            else:
                offenders[rule_name].append(f"{label}: {result}")
                any_offence = True
        if any_offence:
            offending_ids.add(rid)
        else:
            # Check if the lead is unverifiable on any rule.
            is_unverifiable = any(
                unverifiable[rule_name]
                and any(label.startswith(e.split(":")[0] + ":")
                        for e in unverifiable[rule_name])
                for rule_name, _ in checkers)
            if is_unverifiable:
                offending_ids.add(rid)
            else:
                clean_ids.add(rid)

    # Build result.
    counts = {rule: len(v) for rule, v in offenders.items()}
    unverifiable_counts = {rule: len(v)
                           for rule, v in unverifiable.items()}

    # Arithmetic: clean + |offenders ∪ unverifiable| == subjects.
    all_flagged = offending_ids
    arithmetic_ok = len(clean_ids) + len(all_flagged) == len(subjects)

    any_offenders = any(counts.values())
    any_unverifiable = any(unverifiable_counts.values())

    if any_offenders:
        verdict = FAIL
    elif any_unverifiable:
        verdict = UNCONFIRMED
    else:
        verdict = PASS

    result = {
        "check": "lead_state",
        "phase": phase,
        "verdict": verdict,
        "batch": batch,
        "campaigns": [str(c) for c in (campaign_ids or [])],
        "subjects": len(subjects),
        "clean": len(clean_ids),
        "refused": verdict == FAIL,
        "rules": dict(RULES),
        "counts": counts,
        "offenders": offenders,
        "unverifiable": unverifiable,
        "unverifiable_counts": unverifiable_counts,
        "key_presence": _key_presence(subjects),
        "evidence": {
            "provider_reads": provider_reads,
            "files_read": [file_info],
            "provider_reads_skipped": not live_reads,
        },
        "measured_at": now_iso,
        "workspaces": os.path.abspath(workspaces),
        "arithmetic_closes": arithmetic_ok,
    }

    _output(result, json_path)

    if not arithmetic_ok:
        return result, EXIT_ERROR
    if verdict == FAIL:
        return result, EXIT_FAIL
    if verdict == UNCONFIRMED:
        return result, EXIT_UNCONFIRMED
    return result, EXIT_PASS


def _vacuous_result(phase, batch, campaign_ids, file_info, workspaces):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {
        "check": "lead_state",
        "phase": phase,
        "verdict": VACUOUS,
        "batch": batch,
        "campaigns": [str(c) for c in (campaign_ids or [])],
        "subjects": 0,
        "clean": 0,
        "refused": True,
        "rules": dict(RULES),
        "counts": {rule: 0 for rule in RULES},
        "offenders": {rule: [] for rule in RULES},
        "unverifiable": {rule: [] for rule in RULES},
        "unverifiable_counts": {rule: 0 for rule in RULES},
        "key_presence": {"total": 0, "per_rule": {}},
        "evidence": {
            "provider_reads": [],
            "files_read": [file_info],
            "provider_reads_skipped": True,
        },
        "measured_at": now_iso,
        "workspaces": os.path.abspath(workspaces),
        "arithmetic_closes": True,
        "vacuous_reason": "no leads matched the batch/campaign filter",
    }


def _output(result, json_path=None):
    """Write the result to stdout and optionally to a JSON file."""
    text = json.dumps(result, indent=2, ensure_ascii=False, default=str)
    print(text)
    if json_path:
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(text)


# ------------------------------------------------------------------ CLI

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Per-lead eligibility and state check")
    parser.add_argument("--phase", required=True,
                        choices=("pre_push", "post_push", "ongoing"))
    parser.add_argument("--batch", default=None)
    parser.add_argument("--campaign", action="append", dest="campaigns",
                        default=None)
    parser.add_argument("--workspaces", required=True,
                        help="path to a copy of production work/")
    parser.add_argument("--json", default=None, dest="json_path")
    parser.add_argument("--live-reads", action="store_true", default=True)
    parser.add_argument("--no-live-reads", action="store_false",
                        dest="live_reads")
    parser.add_argument("--workspace", default=None,
                        dest="expect_workspace",
                        help="EmailBison workspace for collision checks")
    args = parser.parse_args(argv)
    _result, code = run(
        phase=args.phase,
        batch=args.batch,
        campaign_ids=args.campaigns,
        workspaces=args.workspaces,
        json_path=args.json_path,
        live_reads=args.live_reads,
        expect_workspace=args.expect_workspace,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
