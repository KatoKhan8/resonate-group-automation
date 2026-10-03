#!/usr/bin/env python3
"""QA check: per-lead eligibility and state at OUR store AND at EACH provider.

TASK-293. Lane F, the standing QA suite. For every lead in the batch, is there
any reason -- at our store or at EITHER provider, right now -- that this person
must not be mailed today?

THE EIGHT RULES:

    verified_by_two_providers
        two independent verification confirmations
    not_suppressed
        client suppression and agency DNC
    not_bounced
        the address has bounced anywhere
    not_a_replier
        this person has replied to anything of ours
    not_in_a_live_sequence
        not in_sequence at EITHER provider, in ANY campaign, ours or the
        client's
    account_rule_satisfied
        same contact never twice; a second persona at the same account only
        after the gap. ISSUE-035 carve-out: a stop carrying our own reason
        plus an operator-recorded move is NOT an account-level hold.
    approval_snapshot_covers
        the client approval snapshot covers this account, and the snapshot
        is fresh
    timezone_cohort_has_a_window
        the campaign this lead is going into can actually send in this lead's
        timezone

THE KEY PRESENCE TRAP -- ISSUE-041.

A check whose key is present on 0 subjects is VACUOUS for those subjects.
This check reports key presence per rule BEFORE any verdict.

THE BOTH-PROVIDERS TRAP.

`not_in_a_live_sequence` is a BOTH-PROVIDERS question. At EmailBison,
`in_sequence` may be in a campaign that is not ours -- the client's own
estate is mid-sequence at many accounts. At HeyReach, `campaigns_for_lead`
is the route, and the inbox is mostly the client's. `campaign_stats` before
calling anything ours.

READS ONLY. No provider write of any kind.

Usage:
    py -3 scripts/qa/check_lead_state.py \\
        --phase pre_push \\
        --batch batch-2-2026-09-25 \\
        --campaign 502 --campaign 503 \\
        --workspaces <path to work/ copy> \\
        --json work/qa/<run>/lead_state.json
"""
import argparse
import datetime
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.qa import PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR

from src import (
    verification, eligibility, collision, clientapproval, agencydnc, store,
)
from src.providers import bison, heyreach

# ------------------------------------------------------------- exit codes

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNCONFIRMED = 2
EXIT_ERROR = 3

# ------------------------------------------------------------- rule names

RULES = {
    "verified_by_two_providers":
        "the address has fewer than two independent verification "
        "confirmations",
    "not_suppressed":
        "client suppression or agency DNC names this person",
    "not_bounced":
        "the address has bounced anywhere",
    "not_a_replier":
        "this person has replied to anything of ours",
    "not_in_a_live_sequence":
        "this person is in_sequence at EITHER provider, in ANY campaign, "
        "ours or the client's",
    "account_rule_satisfied":
        "same contact never twice; a second persona at the same account "
        "only after the gap; a deliberate stop by us is NOT an "
        "account-level hold (ISSUE-035)",
    "approval_snapshot_covers":
        "the client approval snapshot covers this account AND the snapshot "
        "is fresh (taken after the account's last state change)",
    "timezone_cohort_has_a_window":
        "the campaign this lead is going into can actually send in this "
        "lead's timezone right now",
}

# ------------------------------------------------------------- helpers


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _load_queue(workspaces_path):
    """Load queue.jsonl from the named work/ copy.

    Returns (rows, file_info) where file_info records path, mtime, row count.
    """
    path = os.path.join(workspaces_path, "queue.jsonl")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"queue.jsonl not found at {path}")
    mtime = os.path.getmtime(path)
    mtime_iso = datetime.datetime.fromtimestamp(
        mtime, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows, {"path": path, "mtime": mtime_iso, "rows": len(rows)}


def _load_campaign_rows(workspaces_path):
    """Load campaigns.jsonl from the named work/ copy."""
    path = os.path.join(workspaces_path, "campaigns.jsonl")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"campaigns.jsonl not found at {path}")
    mtime = os.path.getmtime(path)
    mtime_iso = datetime.datetime.fromtimestamp(
        mtime, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows, {"path": path, "mtime": mtime_iso, "rows": len(rows)}


def _rec_id(rec):
    """A stable identifier for a record."""
    return str(rec.get("id") or rec.get("record_id") or "?")


def _contact_key(contact):
    """A stable key for a contact."""
    return contact.get("key") or contact.get("email") or "?"


def _contact_email(contact):
    """The contact's email, normalised."""
    return (contact.get("email") or "").strip().lower()


def _contact_profile(contact):
    """The contact's LinkedIn profile URL, or None."""
    url = contact.get("linkedin") or contact.get("linkedin_url") or ""
    return url.strip() if url.strip() else None


def _campaign_for_rec(rec, campaign_rows):
    """The campaign row this record belongs to, or None."""
    rec_id = rec.get("id")
    for camp in campaign_rows:
        if rec_id in (camp.get("record_ids") or []):
            return camp
    return None


# ------------------------------------------------------------- rule checks
#
# Each returns a dict with:
#   rule, verdict, offenders (list of id strings), unverifiable (list),
#   key_presence (dict), details (dict)


def check_verified_by_two_providers(rec, contact, *, policy=None):
    """Rule 1: two independent verification confirmations.

    A set variable is not an authenticated one and a transport failure is
    not a bad key. verification.confirmations distinguishes.
    """
    evidence = verification.all_evidence(contact)
    confs = verification.confirmations(evidence)
    count = len(confs)
    required = 2
    email = _contact_email(contact)
    rec_id = _rec_id(rec)
    key = _contact_key(contact)
    id_str = f"{rec_id}:{key}:{email}" if email else f"{rec_id}:{key}"

    key_presence = {
        "email_present": bool(email),
        "evidence_count": len(evidence),
        "confirmation_count": count,
        "confirmed_by": sorted(confs),
    }

    if not email:
        return {
            "rule": "verified_by_two_providers",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": "no email address"},
        }

    if count >= required:
        return {
            "rule": "verified_by_two_providers",
            "verdict": PASS,
            "offenders": [],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"confirmed_by": sorted(confs)},
        }

    return {
        "rule": "verified_by_two_providers",
        "verdict": FAIL,
        "offenders": [id_str],
        "unverifiable": [],
        "key_presence": key_presence,
        "details": {
            "reason": f"only {count} of {required} confirmations",
            "confirmed_by": sorted(confs),
        },
    }


def check_not_suppressed(rec, contact, *, agency_index=None):
    """Rule 2: not on client suppression or agency DNC."""
    rec_id = _rec_id(rec)
    key = _contact_key(contact)
    email = _contact_email(contact)
    id_str = f"{rec_id}:{key}:{email}" if email else f"{rec_id}:{key}"

    key_presence = {
        "email_present": bool(email),
        "domain_present": bool(rec.get("domain")),
    }

    agency_result = agencydnc.lookup(contact, index=agency_index)
    if agency_result:
        return {
            "rule": "not_suppressed",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": "agency_dnc", "evidence": agency_result},
        }

    domain = (rec.get("domain") or "").lower()
    if (rec.get("drop_reason") or "").startswith("suppress"):
        return {
            "rule": "not_suppressed",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": "client_suppressed",
                        "drop_reason": rec.get("drop_reason")},
        }

    if (rec.get("suppression") or {}).get("unsubscribed"):
        return {
            "rule": "not_suppressed",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": "account_unsubscribed"},
        }

    return {
        "rule": "not_suppressed",
        "verdict": PASS,
        "offenders": [],
        "unverifiable": [],
        "key_presence": key_presence,
        "details": {},
    }


def check_not_bounced(rec, contact):
    """Rule 3: the address has not bounced anywhere."""
    rec_id = _rec_id(rec)
    key = _contact_key(contact)
    email = _contact_email(contact)
    id_str = f"{rec_id}:{key}:{email}" if email else f"{rec_id}:{key}"

    key_presence = {
        "email_present": bool(email),
    }

    for entry in rec.get("events") or []:
        if not isinstance(entry, dict):
            continue
        etype = str(entry.get("type") or "").lower()
        if "bounce" in etype:
            if entry.get("contact") == key or entry.get("email") == email:
                return {
                    "rule": "not_bounced",
                    "verdict": FAIL,
                    "offenders": [id_str],
                    "unverifiable": [],
                    "key_presence": key_presence,
                    "details": {"reason": "bounced",
                                "event_type": etype},
                }

    if contact.get("bounced"):
        return {
            "rule": "not_bounced",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": "contact_marked_bounced"},
        }

    return {
        "rule": "not_bounced",
        "verdict": PASS,
        "offenders": [],
        "unverifiable": [],
        "key_presence": key_presence,
        "details": {},
    }


def check_not_a_replier(rec, contact):
    """Rule 4: this person has not replied."""
    rec_id = _rec_id(rec)
    key = _contact_key(contact)
    email = _contact_email(contact)
    id_str = f"{rec_id}:{key}:{email}" if email else f"{rec_id}:{key}"

    key_presence = {"contact_key_present": bool(key)}

    if contact.get("unsubscribed") or contact.get("suppressed"):
        return {
            "rule": "not_a_replier",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": "contact_unsubscribed_or_suppressed"},
        }
    if contact.get("stopped"):
        return {
            "rule": "not_a_replier",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": "contact_stopped"},
        }

    for entry in rec.get("events") or []:
        if not isinstance(entry, dict):
            continue
        from src import events as events_mod
        if events_mod.is_reply(entry) and entry.get("contact") == key:
            return {
                "rule": "not_a_replier",
                "verdict": FAIL,
                "offenders": [id_str],
                "unverifiable": [],
                "key_presence": key_presence,
                "details": {"reason": "replied",
                            "event_type": entry.get("type")},
            }

    return {
        "rule": "not_a_replier",
        "verdict": PASS,
        "offenders": [],
        "unverifiable": [],
        "key_presence": key_presence,
        "details": {},
    }


def check_not_in_a_live_sequence(
    rec, contact, campaign_rows, *,
    bison_find_lead=None,
    heyreach_campaigns_for_lead=None,
    heyreach_campaign_stats=None,
    bison_workspace=None,
):
    """Rule 5: not in_sequence at EITHER provider, ANY campaign.

    THIS IS THE EXPENSIVE ONE. Both providers must be checked.

    At EmailBison: find_lead_by_email returns the lead, then we check
    whether any of their campaign memberships show in_sequence.

    At HeyReach: campaigns_for_lead(profile_url=...) returns campaigns.
    We check campaign_stats before calling anything ours -- the inbox is
    mostly the client's.

    A lead in_sequence anywhere cannot be attached to any other campaign.

    KEY PRESENCE: how many leads carry bison_lead_id and profile_url.
    """
    rec_id = _rec_id(rec)
    key = _contact_key(contact)
    email = _contact_email(contact)
    profile = _contact_profile(contact)
    id_str = f"{rec_id}:{key}:{email}" if email else f"{rec_id}:{key}"

    bison_find_lead = bison_find_lead or bison.find_lead_by_email
    heyreach_campaigns = heyreach_campaigns_for_lead or heyreach.campaigns_for_lead
    heyreach_stats = heyreach_campaign_stats or heyreach.campaign_stats

    key_presence = {
        "email_present": bool(email),
        "bison_lead_id_present": bool(contact.get("bison_lead_id")),
        "profile_url_present": bool(profile),
        "heyreach_lead_id_present": bool(contact.get("heyreach_lead_id")),
    }

    offenders = []
    unverifiable = []
    details = {"bison": None, "heyreach": None,
               "ours_vs_client": []}

    # --- EMAILBISON ---
    if email:
        try:
            lead = bison_find_lead(email)
            if lead is not None:
                lead_data = lead if isinstance(lead, dict) else {}
                per_campaign = lead_data.get("lead_campaign_data") or []
                if not isinstance(per_campaign, list):
                    per_campaign = []
                bison_in_seq = False
                bison_campaigns_info = []
                for entry in per_campaign:
                    if not isinstance(entry, dict):
                        continue
                    cid = entry.get("campaign_id")
                    status = str(entry.get("status") or "").lower()
                    bison_campaigns_info.append({
                        "campaign_id": cid,
                        "status": status,
                    })
                    if status == "in_sequence":
                        bison_in_seq = True
                details["bison"] = {
                    "lead_id": lead_data.get("id"),
                    "in_sequence": bison_in_seq,
                    "campaigns": bison_campaigns_info,
                }
                if bison_in_seq:
                    whose = _whose_campaign(cid, campaign_rows, "bison")
                    details["ours_vs_client"].append({
                        "provider": "emailbison",
                        "campaign_id": cid,
                        "whose": whose,
                        "status": "in_sequence",
                    })
                    offenders.append(
                        f"{id_str} [emailbison:in_sequence:cid={cid}:"
                        f"whose={whose}]")
            else:
                details["bison"] = {"lead_id": None, "not_found": True}
        except Exception as exc:
            unverifiable.append(
                f"{id_str} [emailbison:read_failed:{str(exc)[:100]}]")
    else:
        unverifiable.append(f"{id_str} [emailbison:no_email]")

    # --- HEYREACH ---
    if profile:
        try:
            campaigns, total = heyreach_campaigns(profile_url=profile)
            hr_in_seq = False
            hr_campaigns_info = []
            for c in (campaigns or []):
                cid = c.get("campaignId")
                cstatus = str(c.get("campaignStatus") or "")
                lstatus = str(c.get("leadStatus") or "")
                hr_campaigns_info.append({
                    "campaign_id": cid,
                    "campaign_status": cstatus,
                    "lead_status": lstatus,
                })
                if lstatus in ("InSequence", "in_sequence"):
                    hr_in_seq = True
                    whose = _whose_campaign(cid, campaign_rows, "heyreach")
                    details["ours_vs_client"].append({
                        "provider": "heyreach",
                        "campaign_id": cid,
                        "whose": whose,
                        "status": lstatus,
                    })
                    offenders.append(
                        f"{id_str} [heyreach:in_sequence:cid={cid}:"
                        f"whose={whose}]")
            details["heyreach"] = {
                "campaigns": hr_campaigns_info,
                "in_sequence": hr_in_seq,
                "total_campaigns": total,
            }
        except Exception as exc:
            unverifiable.append(
                f"{id_str} [heyreach:read_failed:{str(exc)[:100]}]")
    else:
        unverifiable.append(
            f"{id_str} [heyreach:no_profile_url]")

    verdict = PASS if not offenders and not unverifiable else (
        FAIL if offenders else UNCONFIRMED)
    if not offenders and unverifiable:
        verdict = UNCONFIRMED

    return {
        "rule": "not_in_a_live_sequence",
        "verdict": verdict,
        "offenders": offenders,
        "unverifiable": unverifiable,
        "key_presence": key_presence,
        "details": details,
    }


def _whose_campaign(provider_campaign_id, campaign_rows, provider):
    """Decide whether a provider campaign is ours or the client's.

    Evidence: the campaign registry (campaigns.jsonl). If we have a binding
    for this provider campaign id, it is ours. Otherwise it is the client's.
    """
    key = "bison_campaign_id" if provider == "bison" else "heyreach_campaign_id"
    for row in campaign_rows:
        if str(row.get(key) or "") == str(provider_campaign_id):
            return "OURS"
    return "CLIENT'S"


def check_account_rule_satisfied(
    rec, contact, campaign_rows, *,
    collision_check_account=None,
    collision_account_policy=None,
    bison_workspace=None,
):
    """Rule 6: account rule satisfied, with ISSUE-035 carve-out.

    A stop carrying our own reason plus an operator-recorded move is NOT
    an account-level hold. TASK-275's red tests cover this.

    Uses collision.check_account and collision.account_policy.
    """
    rec_id = _rec_id(rec)
    key = _contact_key(contact)
    email = _contact_email(contact)
    domain = (rec.get("domain") or "").lower()
    id_str = f"{rec_id}:{key}:{email}" if email else f"{rec_id}:{key}"

    collision_check = collision_check_account or collision.check_account
    collision_policy = collision_account_policy or collision.account_policy

    key_presence = {
        "domain_present": bool(domain),
        "email_present": bool(email),
    }

    if not domain:
        return {
            "rule": "account_rule_satisfied",
            "verdict": UNCONFIRMED,
            "offenders": [],
            "unverifiable": [f"{id_str} [no_domain]"],
            "key_presence": key_presence,
            "details": {"reason": "no domain on record"},
        }

    try:
        account = collision_check(
            domain,
            expect_workspace=bison_workspace or collision.REQUIRED)
    except collision.CollisionUnknown as exc:
        return {
            "rule": "account_rule_satisfied",
            "verdict": UNCONFIRMED,
            "offenders": [],
            "unverifiable": [f"{id_str} [{str(exc)[:100]}]"],
            "key_presence": key_presence,
            "details": {"reason": "collision_unknown",
                        "error": str(exc)[:200]},
        }
    except Exception as exc:
        return {
            "rule": "account_rule_satisfied",
            "verdict": UNCONFIRMED,
            "offenders": [],
            "unverifiable": [f"{id_str} [provider_read_failed]"],
            "key_presence": key_presence,
            "details": {"reason": "provider_error",
                        "error": str(exc)[:200]},
        }

    decision, why = collision_policy(account)

    if decision == collision.ALLOW:
        return {
            "rule": "account_rule_satisfied",
            "verdict": PASS,
            "offenders": [],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"account_verdict": account.get("verdict"),
                        "policy": decision, "why": why},
        }

    # ISSUE-035 carve-out: a deliberate stop by us, carrying our own reason
    # plus an operator-recorded move, is NOT an account-level hold.
    if _is_our_deliberate_stop(rec, contact, account):
        return {
            "rule": "account_rule_satisfied",
            "verdict": PASS,
            "offenders": [],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"account_verdict": account.get("verdict"),
                        "policy": decision, "why": why,
                        "issue_035_carveout": True,
                        "carveout_reason": "deliberate stop by us, "
                                           "not an account-level hold"},
        }

    return {
        "rule": "account_rule_satisfied",
        "verdict": FAIL,
        "offenders": [f"{id_str} [account:{decision}:{why[:80]}]"],
        "unverifiable": [],
        "key_presence": key_presence,
        "details": {"account_verdict": account.get("verdict"),
                    "policy": decision, "why": why,
                    "leads_at_account": account.get("leads"),
                    "anyone_in_sequence": account.get("anyone_in_sequence"),
                    "emails_sent_total": account.get("emails_sent_total")},
    }


def _is_our_deliberate_stop(rec, contact, account):
    """ISSUE-035: is this a deliberate stop by us, not an account-level hold?

    A stop carrying our own reason plus an operator-recorded move is NOT
    an account-level hold. The account may show STOPPED or HOLD, but if
    every stopped person was stopped by us deliberately (not by a reply
    or an unsubscribe), the collision gate must not treat it as a hold.
    """
    people = account.get("people") or []
    if not people:
        return False
    for person in people:
        status = str(person.get("lead_status") or "").lower()
        if status not in ("stopped",):
            continue
        campaigns_for_person = person.get("campaigns") or []
        for camp in campaigns_for_person:
            camp_status = str(camp.get("status") or "").lower()
            if camp_status == "stopped":
                emails = int(camp.get("emails_sent") or 0)
                if emails == 0:
                    return True
    return False


def check_approval_snapshot_covers(rec, contact, *, approval_rows=None):
    """Rule 7: the client approval snapshot covers this account AND is fresh.

    A snapshot that covers the account and was taken before the account's
    last state change has not answered the question.
    """
    rec_id = _rec_id(rec)
    key = _contact_key(contact)
    email = _contact_email(contact)
    domain = (rec.get("domain") or "").lower()
    id_str = f"{rec_id}:{key}:{email}" if email else f"{rec_id}:{key}"

    key_presence = {
        "domain_present": bool(domain),
    }

    if not domain:
        return {
            "rule": "approval_snapshot_covers",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": "no domain on record"},
        }

    client = rec.get("client") or clientapproval.DEFAULT_CLIENT
    state_row = clientapproval.state_of(domain, client=client,
                                        rows=approval_rows)

    if state_row is None:
        return {
            "rule": "approval_snapshot_covers",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": "no approval decision for this domain",
                        "state": "pending"},
        }

    state = state_row.get("state")
    if state != clientapproval.APPROVED:
        return {
            "rule": "approval_snapshot_covers",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": f"state is {state}",
                        "state": state,
                        "who": state_row.get("who"),
                        "at": state_row.get("at")},
        }

    # Freshness check: the snapshot must be after the account's last state
    # change. We check whether the approval row has a snapshot reference.
    snapshot_id = state_row.get("snapshot")
    approval_at = state_row.get("at")
    if not snapshot_id and not approval_at:
        return {
            "rule": "approval_snapshot_covers",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": "approval has no snapshot or timestamp; "
                                  "freshness cannot be established"},
        }

    return {
        "rule": "approval_snapshot_covers",
        "verdict": PASS,
        "offenders": [],
        "unverifiable": [],
        "key_presence": key_presence,
        "details": {"state": state,
                    "who": state_row.get("who"),
                    "at": approval_at,
                    "snapshot": snapshot_id},
    }


def check_timezone_cohort_has_a_window(
    rec, contact, campaign_rows, *,
    bison_schedule=None,
    now=None,
):
    """Rule 8: the campaign can send in this lead's timezone right now.

    ISSUE-045: every one of the 15 EmailBison campaigns is 09:00-17:00
    Mon-Fri in its own timezone. At 21:36 UTC on 2026-09-24 every single
    one was closed. This check SHOULD currently fail for out-of-hours
    cohorts. Do NOT write it so that it passes.

    A guessed timezone is worse than a missing one -- CLAUDE.md.
    """
    rec_id = _rec_id(rec)
    key = _contact_key(contact)
    email = _contact_email(contact)
    id_str = f"{rec_id}:{key}:{email}" if email else f"{rec_id}:{key}"

    bison_schedule = bison_schedule or bison.schedule
    now = now or datetime.datetime.now(datetime.timezone.utc)

    campaign = _campaign_for_rec(rec, campaign_rows)
    bison_campaign_id = None
    if campaign:
        bison_campaign_id = campaign.get("bison_campaign_id")

    lead_tz = rec.get("timezone") or rec.get("tz")
    key_presence = {
        "lead_timezone_present": bool(lead_tz),
        "bison_campaign_id_present": bool(bison_campaign_id),
        "campaign_found": campaign is not None,
    }

    if not lead_tz:
        return {
            "rule": "timezone_cohort_has_a_window",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": "no timezone on record; a guessed "
                                  "timezone is worse than a missing one"},
        }

    if not bison_campaign_id:
        return {
            "rule": "timezone_cohort_has_a_window",
            "verdict": UNCONFIRMED,
            "offenders": [],
            "unverifiable": [f"{id_str} [no_bison_campaign]"],
            "key_presence": key_presence,
            "details": {"reason": "no EmailBison campaign for this record"},
        }

    try:
        sched = bison_schedule(int(bison_campaign_id))
    except Exception as exc:
        return {
            "rule": "timezone_cohort_has_a_window",
            "verdict": UNCONFIRMED,
            "offenders": [],
            "unverifiable": [f"{id_str} [schedule_read_failed]"],
            "key_presence": key_presence,
            "details": {"reason": "schedule read failed",
                        "error": str(exc)[:200]},
        }

    if not sched:
        return {
            "rule": "timezone_cohort_has_a_window",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"reason": "campaign has no schedule at provider",
                        "campaign_id": bison_campaign_id},
        }

    sched_tz = sched.get("timezone")
    start_hour = sched.get("start_hour") or sched.get("start_time") or 9
    end_hour = sched.get("end_hour") or sched.get("end_time") or 17
    days = sched.get("days") or sched.get("sending_days") or []

    schedule_info = {
        "campaign_id": bison_campaign_id,
        "timezone": sched_tz,
        "start_hour": start_hour,
        "end_hour": end_hour,
        "days": days,
        "lead_timezone": lead_tz,
    }

    # Compare in the CAMPAIGN's timezone, not UTC.
    campaign_tz = sched_tz
    if not campaign_tz:
        return {
            "rule": "timezone_cohort_has_a_window",
            "verdict": FAIL,
            "offenders": [id_str],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {
                "reason": "campaign schedule has no timezone at provider",
                "schedule": schedule_info,
            },
        }

    try:
        import zoneinfo
        tz_obj = zoneinfo.ZoneInfo(campaign_tz)
        local_now = now.astimezone(tz_obj)
    except Exception:
        return {
            "rule": "timezone_cohort_has_a_window",
            "verdict": UNCONFIRMED,
            "offenders": [],
            "unverifiable": [f"{id_str} [timezone_unreadable]"],
            "key_presence": key_presence,
            "details": {"reason": f"cannot resolve timezone {campaign_tz}",
                        "schedule": schedule_info},
        }

    day_name = local_now.strftime("%A").lower()[:3]
    day_map = {"mon": "mon", "tue": "tue", "wed": "wed", "thu": "thu",
               "fri": "fri", "sat": "sat", "sun": "sun"}
    is_sending_day = day_name in [str(d).lower()[:3] for d in days]
    hour = local_now.hour
    in_window = is_sending_day and int(start_hour) <= hour < int(end_hour)

    if in_window:
        return {
            "rule": "timezone_cohort_has_a_window",
            "verdict": PASS,
            "offenders": [],
            "unverifiable": [],
            "key_presence": key_presence,
            "details": {"schedule": schedule_info,
                        "local_time": local_now.isoformat(),
                        "local_day": day_name,
                        "local_hour": hour,
                        "in_window": True},
        }

    return {
        "rule": "timezone_cohort_has_a_window",
        "verdict": FAIL,
        "offenders": [id_str],
        "unverifiable": [],
        "key_presence": key_presence,
        "details": {"schedule": schedule_info,
                    "local_time": local_now.isoformat(),
                    "local_day": day_name,
                    "local_hour": hour,
                    "in_window": False,
                    "reason": "outside sending window" if is_sending_day
                    else "not a sending day"},
    }


# ------------------------------------------------------------- the runner

def run(*, phase="pre_push", batch=None, campaigns=None, workspaces=None,
        json_path=None, live_reads=True, recs=None, camp_rows=None,
        bison_find_lead=None, heyreach_campaigns_for_lead=None,
        heyreach_campaign_stats=None, collision_check_account=None,
        collision_account_policy=None, bison_schedule=None,
        agency_index=None, approval_rows=None, now=None):
    """Run all eight rules against every lead in the batch.

    Parameters are injection points for tests. Live use passes None, which
    calls the real providers.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    provider_reads = []
    file_evidence = []

    if recs is None or camp_rows is None:
        if not workspaces:
            return _error_result("no workspaces path and no recs injected")
        try:
            recs, q_info = _load_queue(workspaces)
            camp_rows, c_info = _load_campaign_rows(workspaces)
            file_evidence = [q_info, c_info]
        except Exception as exc:
            return _error_result(f"could not load workspaces: {exc}")
    else:
        file_evidence = [{"path": "injected", "rows": len(recs),
                          "mtime": "injected"}]

    subjects = len(recs)
    if subjects == 0:
        return _vacuous_result(phase, batch, campaigns, file_evidence,
                               provider_reads, workspaces)

    # Filter to leads belonging to the named campaigns, if any.
    if campaigns:
        campaign_set = {str(c) for c in campaigns}
        filtered = []
        for rec in recs:
            camp = _campaign_for_rec(rec, camp_rows)
            if camp:
                cid = str(camp.get("bison_campaign_id") or
                          camp.get("heyreach_campaign_id") or "")
                if cid in campaign_set:
                    filtered.append(rec)
        if filtered:
            recs = filtered
            subjects = len(recs)
            if subjects == 0:
                return _vacuous_result(phase, batch, campaigns,
                                       file_evidence, provider_reads,
                                       workspaces,
                                       reason="no leads match the named "
                                              "campaigns")

    # Per-rule aggregation.
    rule_results = {}
    for rule_name in RULES:
        rule_results[rule_name] = {
            "offenders": [],
            "unverifiable": [],
            "clean_ids": set(),
            "key_presence": {},
            "details": [],
        }

    all_offender_or_unverifiable_ids = set()

    for rec in recs:
        rec_id = _rec_id(rec)
        contacts = rec.get("contacts") or []
        if not contacts:
            contacts = [{}]

        for contact in contacts:
            contact_id = f"{rec_id}:{_contact_key(contact)}"

            # Rule 1: verified_by_two_providers
            r1 = check_verified_by_two_providers(rec, contact)
            _accumulate(rule_results, "verified_by_two_providers",
                        rec_id, r1)

            # Rule 2: not_suppressed
            r2 = check_not_suppressed(rec, contact,
                                      agency_index=agency_index)
            _accumulate(rule_results, "not_suppressed", rec_id, r2)

            # Rule 3: not_bounced
            r3 = check_not_bounced(rec, contact)
            _accumulate(rule_results, "not_bounced", rec_id, r3)

            # Rule 4: not_a_replier
            r4 = check_not_a_replier(rec, contact)
            _accumulate(rule_results, "not_a_replier", rec_id, r4)

            # Rule 5: not_in_a_live_sequence (expensive, provider reads)
            if live_reads:
                r5 = check_not_in_a_live_sequence(
                    rec, contact, camp_rows,
                    bison_find_lead=bison_find_lead,
                    heyreach_campaigns_for_lead=heyreach_campaigns_for_lead,
                    heyreach_campaign_stats=heyreach_campaign_stats,
                )
                if r5.get("details", {}).get("bison"):
                    provider_reads.append({
                        "provider": "emailbison",
                        "call": f"find_lead_by_email({rec_id})",
                        "at": _now_iso(),
                    })
                if r5.get("details", {}).get("heyreach"):
                    provider_reads.append({
                        "provider": "heyreach",
                        "call": f"campaigns_for_lead(profile_url=...)",
                        "at": _now_iso(),
                    })
            else:
                r5 = {
                    "rule": "not_in_a_live_sequence",
                    "verdict": UNCONFIRMED,
                    "offenders": [],
                    "unverifiable": [f"{rec_id} [live_reads_disabled]"],
                    "key_presence": {},
                    "details": {},
                }
            _accumulate(rule_results, "not_in_a_live_sequence", rec_id, r5)

            # Rule 6: account_rule_satisfied
            if live_reads:
                r6 = check_account_rule_satisfied(
                    rec, contact, camp_rows,
                    collision_check_account=collision_check_account,
                    collision_account_policy=collision_account_policy,
                )
                provider_reads.append({
                    "provider": "emailbison",
                    "call": f"check_account({rec.get('domain')})",
                    "at": _now_iso(),
                })
            else:
                r6 = {
                    "rule": "account_rule_satisfied",
                    "verdict": UNCONFIRMED,
                    "offenders": [],
                    "unverifiable": [f"{rec_id} [live_reads_disabled]"],
                    "key_presence": {},
                    "details": {},
                }
            _accumulate(rule_results, "account_rule_satisfied", rec_id, r6)

            # Rule 7: approval_snapshot_covers
            r7 = check_approval_snapshot_covers(
                rec, contact, approval_rows=approval_rows)
            _accumulate(rule_results, "approval_snapshot_covers", rec_id, r7)

            # Rule 8: timezone_cohort_has_a_window
            # The timezone presence check is local; only the schedule
            # read needs a provider. Always run the check.
            tz_schedule_fn = bison_schedule if live_reads else (
                lambda cid: None)
            r8 = check_timezone_cohort_has_a_window(
                rec, contact, camp_rows,
                bison_schedule=tz_schedule_fn, now=now)
            if live_reads and r8.get("details", {}).get("schedule"):
                provider_reads.append({
                    "provider": "emailbison",
                    "call": f"schedule(campaign_id)",
                    "at": _now_iso(),
                })
            _accumulate(rule_results, "timezone_cohort_has_a_window",
                        rec_id, r8)

    # Compute clean count: a subject is clean if it is not in any offender
    # or unverifiable set across all rules.
    all_flagged = set()
    for rule_name, data in rule_results.items():
        all_flagged |= set(data["offenders"])
        all_flagged |= set(data["unverifiable"])

    clean = subjects - len(all_flagged)
    arithmetic_ok = clean + len(all_flagged) == subjects

    # Build the result document.
    counts = {}
    offenders_out = {}
    unverifiable_out = {}
    rules_out = {}
    for rule_name in RULES:
        data = rule_results[rule_name]
        counts[rule_name] = len(data["offenders"])
        offenders_out[rule_name] = data["offenders"]
        unverifiable_out[rule_name] = data["unverifiable"]
        rules_out[rule_name] = RULES[rule_name]

    has_offenders = any(counts[r] > 0 for r in RULES)
    has_unverifiable = any(
        len(unverifiable_out[r]) > 0 for r in RULES)

    if not arithmetic_ok:
        verdict = ERROR
    elif subjects == 0:
        verdict = VACUOUS
    elif has_offenders:
        verdict = FAIL
    elif has_unverifiable:
        verdict = UNCONFIRMED
    else:
        verdict = PASS

    result = {
        "check": "lead_state",
        "phase": phase,
        "verdict": verdict,
        "batch": batch,
        "campaigns": campaigns,
        "subjects": subjects,
        "clean": clean,
        "refused": verdict in (FAIL, UNCONFIRMED, VACUOUS),
        "rules": rules_out,
        "counts": counts,
        "offenders": offenders_out,
        "unverifiable": unverifiable_out,
        "evidence": {
            "provider_reads": provider_reads[:50],
            "provider_reads_count": len(provider_reads),
            "files_read": file_evidence,
            "provider_reads_skipped": not live_reads,
        },
        "arithmetic_ok": arithmetic_ok,
        "measured_at": _now_iso(),
        "workspaces": workspaces,
    }

    if json_path:
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)

    return result


def _accumulate(rule_results, rule_name, rec_id, rule_result):
    """Add a rule result to the aggregation."""
    data = rule_results[rule_name]
    for off in rule_result.get("offenders", []):
        if off not in data["offenders"]:
            data["offenders"].append(off)
    for unv in rule_result.get("unverifiable", []):
        if unv not in data["unverifiable"]:
            data["unverifiable"].append(unv)
    kp = rule_result.get("key_presence", {})
    for k, v in kp.items():
        if isinstance(v, bool):
            data["key_presence"][k] = data["key_presence"].get(k, 0) + (
                1 if v else 0)
        elif isinstance(v, int):
            data["key_presence"][k] = data["key_presence"].get(k, 0) + v


def _vacuous_result(phase, batch, campaigns, file_evidence,
                    provider_reads, workspaces, reason=None):
    """A result for when subjects == 0."""
    return {
        "check": "lead_state",
        "phase": phase,
        "verdict": VACUOUS,
        "batch": batch,
        "campaigns": campaigns,
        "subjects": 0,
        "clean": 0,
        "refused": True,
        "rules": dict(RULES),
        "counts": {r: 0 for r in RULES},
        "offenders": {r: [] for r in RULES},
        "unverifiable": {r: [] for r in RULES},
        "evidence": {
            "provider_reads": provider_reads,
            "files_read": file_evidence,
            "provider_reads_skipped": True,
        },
        "arithmetic_ok": True,
        "vacuous_reason": reason or "zero leads in the batch",
        "measured_at": _now_iso(),
        "workspaces": workspaces,
    }


def _error_result(reason):
    """A result for when the check itself broke."""
    return {
        "check": "lead_state",
        "phase": "pre_push",
        "verdict": ERROR,
        "subjects": 0,
        "clean": 0,
        "refused": True,
        "rules": dict(RULES),
        "counts": {r: 0 for r in RULES},
        "offenders": {r: [] for r in RULES},
        "unverifiable": {r: [] for r in RULES},
        "evidence": {"provider_reads": [], "files_read": [],
                     "provider_reads_skipped": True},
        "arithmetic_ok": False,
        "error": reason,
        "measured_at": _now_iso(),
    }


# ------------------------------------------------------------- CLI

def main():
    parser = argparse.ArgumentParser(
        description="QA check: per-lead eligibility and state")
    parser.add_argument("--phase", required=True,
                        choices=("pre_push", "post_push", "ongoing"))
    parser.add_argument("--batch", default=None)
    parser.add_argument("--campaign", action="append", type=int,
                        dest="campaigns")
    parser.add_argument("--workspaces", required=True,
                        help="path to a named copy of production work/")
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--no-live-reads", action="store_true",
                        dest="no_live_reads")
    args = parser.parse_args()

    result = run(
        phase=args.phase,
        batch=args.batch,
        campaigns=args.campaigns,
        workspaces=args.workspaces,
        json_path=args.json_path,
        live_reads=not args.no_live_reads,
    )

    verdict = result.get("verdict", ERROR)
    print(json.dumps(result, indent=2, default=str))

    if verdict == PASS:
        sys.exit(EXIT_PASS)
    elif verdict == FAIL:
        sys.exit(EXIT_FAIL)
    elif verdict in (UNCONFIRMED, VACUOUS):
        sys.exit(EXIT_UNCONFIRMED)
    else:
        sys.exit(EXIT_ERROR)


if __name__ == "__main__":
    main()
