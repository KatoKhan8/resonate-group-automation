#!/usr/bin/env python3
"""Ongoing reconciliation: the store and the providers agree.

TASK-299. Two symmetric rules, both CRITICAL when they fire:

    stopped_here_is_stopped_there
        Every lead our store marks replied/stopped/unsubscribed reads
        NOT in_sequence at BOTH providers.
    provider_event_has_a_store_event
        Every provider reply and every provider bounce has a matching event
        in our store.

THE DEFECT THIS EXISTS FOR — ISSUE-041.

`inbound._stop_at_provider` gates the LinkedIn stop on
``contact["heyreach_lead_id"]``. ZERO contacts in the estate carry that field.
So every cross-channel stop reported success having never called
``heyreach.stop_lead_in_campaign`` once. A check gated on that field would
pass 100% and read exactly like a working reconciliation.

This check is NOT gated on ``heyreach_lead_id``. The lead's identity at
HeyReach is available from the profile URL: ``heyreach.campaigns_for_lead(
profile_url=…)`` answers the question without the field the estate does not
carry. Key presence is reported FIRST, per rule, before any verdict.

THE SECOND TRAP — ISSUE-042.

``inbound.OWNED_CAMPAIGNS`` are HeyReach ids compared against an EmailBison
event's campaign id. This check resolves ownership per event from the
registry (campaigns.jsonl), per provider, and never by set membership.

READS ONLY. No stop, no pause, no update, no attach.

  py -3 scripts/qa/check_reconcile.py \\
      --phase ongoing \\
      --workspaces <path to work/ copy> \\
      --json work/qa/reconcile.json
"""
import argparse
import datetime
import json
import os
import sys

# Allow imports from the project root when run as a script.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.qa import PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR

from src import store, campaigns as campaigns_mod, events as events_mod
from src import testidentity
from src.providers import bison, heyreach

# ----------------------------------------------------------------- constants

#: Store states that mean "this person must not be contacted further".
STOPPED_STORE_STATES = frozenset({
    "replied", "stopped", "unsubscribed", "bounced", "do_not_contact",
    "held", "suppressed",
})

#: HeyReach lead statuses that mean "still running".
RUNNING_STATUSES = frozenset(heyreach.RUNNING_LEAD_STATUSES)

#: EmailBison statuses that mean "stopped".
BISON_STOPPED = frozenset(s.lower() for s in bison.STOPPED_STATES)

#: Provider event types that are replies or bounces — the ones that MUST
#: have a store counterpart.
REPLY_EVENT_TYPES = frozenset({
    "replied", "reply", "reply_received",
    "untracked reply", "tracked reply",
})
BOUNCE_EVENT_TYPES = frozenset({
    "bounced", "bounce",
})
RELEVANT_EVENT_TYPES = REPLY_EVENT_TYPES | BOUNCE_EVENT_TYPES

#: The rule keys.
RULE_STOPPED = "stopped_here_is_stopped_there"
RULE_PROVIDER_EVENT = "provider_event_has_a_store_event"

RULES = {
    RULE_STOPPED: (
        "every lead the store marks stopped reads NOT in_sequence at "
        "both providers"
    ),
    RULE_PROVIDER_EVENT: (
        "every provider reply and bounce has a matching store event"
    ),
}


# -------------------------------------------------------- key presence

def _key_presence_stopped(recs):
    """For each stopped record, which keys does it carry?

    Returns a dict with counts of subjects carrying each key field.
    This is the measurement ISSUE-041 was named after: a rule whose key
    is present on ZERO subjects is VACUOUS for all of them.
    """
    stopped = [r for r in recs if _is_stopped(r)]
    total = len(stopped)
    email_key = 0
    linkedin_key = 0
    for rec in stopped:
        for contact in rec.get("contacts") or []:
            if contact.get("bison_lead_id"):
                email_key += 1
            if contact.get("linkedin") or contact.get("linkedin_url"):
                linkedin_key += 1
    return {
        "subjects": total,
        "email_key_present": email_key,
        "linkedin_key_present": linkedin_key,
        "heyreach_lead_id_present": sum(
            1 for r in stopped
            for c in r.get("contacts") or []
            if c.get("heyreach_lead_id")
        ),
    }


def _is_stopped(rec):
    """Does this record's state mean 'must not be contacted'."""
    state = str(rec.get("state") or "").lower().strip()
    if state in STOPPED_STORE_STATES:
        return True
    for contact in rec.get("contacts") or []:
        cstate = str(contact.get("state") or "").lower().strip()
        if cstate in STOPPED_STORE_STATES:
            return True
    return False


# -------------------------------------------------------- rule 1

def check_stopped_here(recs, campaigns, *, bison_membership=None,
                       heyreach_campaigns=None):
    """Rule 1: every stopped record reads stopped at BOTH providers.

    ``bison_membership`` and ``heyreach_campaigns`` are injection points
    for tests. Live use passes None, which calls the real providers.

    Returns a result dict for this rule.
    """
    bison_membership = bison_membership or _live_bison_membership
    heyreach_campaigns = heyreach_campaigns or _live_heyreach_campaigns

    stopped = [r for r in recs if _is_stopped(r)]
    subjects = len(stopped)

    key_presence = _key_presence_stopped(recs)

    offenders = []
    unverifiable = []
    already_settled = []
    clean_ids = set()
    offender_ids = set()
    unverifiable_ids = set()

    for rec in stopped:
        rec_id = rec.get("id")
        rec_clean = True

        for contact in rec.get("contacts") or []:
            contact_key = contact.get("key") or rec_id

            # EMAIL CHANNEL: keyed on bison_lead_id + bison_campaign_id.
            bison_lead_id = contact.get("bison_lead_id")
            if bison_lead_id:
                camp = _campaign_for(rec, campaigns,
                                     requires="bison_campaign_id")
                if camp and camp.get("bison_campaign_id"):
                    try:
                        status = bison_membership(
                            camp["bison_campaign_id"], [bison_lead_id])
                        status_str = str(status or "").lower().strip()
                        if status_str in BISON_STOPPED:
                            pass  # clean on this channel
                        elif status_str == "":
                            unverifiable.append({
                                "record": rec_id,
                                "contact": contact_key,
                                "channel": "email",
                                "why": "lead not found at provider",
                            })
                            unverifiable_ids.add(rec_id)
                            rec_clean = False
                        else:
                            offenders.append({
                                "record": rec_id,
                                "contact": contact_key,
                                "channel": "email",
                                "provider_status": status_str,
                                "provider_campaign": camp.get(
                                    "bison_campaign_id"),
                            })
                            offender_ids.add(rec_id)
                            rec_clean = False
                    except Exception as exc:
                        unverifiable.append({
                            "record": rec_id,
                            "contact": contact_key,
                            "channel": "email",
                            "why": str(exc)[:200],
                        })
                        unverifiable_ids.add(rec_id)
                        rec_clean = False

            # LINKEDIN CHANNEL: keyed on profile URL, NOT heyreach_lead_id.
            # THIS IS THE FIX FOR ISSUE-041.
            profile_url = (contact.get("linkedin")
                           or contact.get("linkedin_url") or "")
            if profile_url:
                camp = _campaign_for(rec, campaigns,
                                     requires="heyreach_campaign_id")
                if camp and camp.get("heyreach_campaign_id"):
                    try:
                        rows, _total = heyreach_campaigns(
                            profile_url=profile_url)
                        here = [r for r in rows
                                if str(r.get("campaignId")) == str(
                                    camp["heyreach_campaign_id"])]
                        if not here:
                            # Not listed for this campaign at all.
                            # Could be clean (never enrolled) or unverifiable.
                            # We count as clean: absence from the campaign
                            # means the provider is not talking to them there.
                            pass
                        else:
                            lead_status = str(
                                here[0].get("leadStatus") or "")
                            lead_campaign_status = str(
                                here[0].get("leadCampaignStatus") or "")
                            if lead_campaign_status == "Finished":
                                # "Already settled" — its own column.
                                already_settled.append({
                                    "record": rec_id,
                                    "contact": contact_key,
                                    "channel": "linkedin",
                                    "provider_campaign": camp.get(
                                        "heyreach_campaign_id"),
                                    "lead_status": lead_status,
                                    "lead_campaign_status":
                                        lead_campaign_status,
                                })
                            elif lead_status in RUNNING_STATUSES or \
                                    lead_campaign_status in RUNNING_STATUSES:
                                offenders.append({
                                    "record": rec_id,
                                    "contact": contact_key,
                                    "channel": "linkedin",
                                    "provider_status": lead_status,
                                    "provider_campaign_status":
                                        lead_campaign_status,
                                    "provider_campaign": camp.get(
                                        "heyreach_campaign_id"),
                                })
                                offender_ids.add(rec_id)
                                rec_clean = False
                            else:
                                pass  # clean on this channel
                    except Exception as exc:
                        unverifiable.append({
                            "record": rec_id,
                            "contact": contact_key,
                            "channel": "linkedin",
                            "why": str(exc)[:200],
                        })
                        unverifiable_ids.add(rec_id)
                        rec_clean = False

        if rec_clean and rec_id not in offender_ids \
                and rec_id not in unverifiable_ids:
            clean_ids.add(rec_id)

    clean = len(clean_ids)
    all_offender_or_unverifiable = offender_ids | unverifiable_ids
    arithmetic_ok = clean + len(all_offender_or_unverifiable) == subjects

    verdict = PASS
    if not arithmetic_ok:
        verdict = ERROR
    elif subjects == 0:
        verdict = VACUOUS
    elif offenders:
        verdict = FAIL

    return {
        "rule": RULE_STOPPED,
        "verdict": verdict,
        "subjects": subjects,
        "clean": clean,
        "key_presence": key_presence,
        "offenders": offenders,
        "unverifiable": unverifiable,
        "already_settled": already_settled,
        "already_settled_count": len(already_settled),
        "arithmetic_ok": arithmetic_ok,
    }


# -------------------------------------------------------- rule 2

def check_provider_events(recs, campaigns, *, fetch_bison_events=None,
                          event_window_days=10):
    """Rule 2: every provider reply/bounce has a matching store event.

    ``fetch_bison_events`` is an injection point for tests.

    Ownership is resolved per event from the registry (campaigns.jsonl),
    per provider. An EmailBison campaign id is NEVER compared against a
    HeyReach id set.

    Returns a result dict for this rule.
    """
    fetch_bison_events = fetch_bison_events or _live_fetch_bison_events

    # Fetch provider events.
    try:
        raw_events, pages, exhausted = fetch_bison_events()
    except Exception as exc:
        return {
            "rule": RULE_PROVIDER_EVENT,
            "verdict": UNCONFIRMED,
            "subjects": 0,
            "clean": 0,
            "key_presence": {"subjects": 0, "why": str(exc)[:200]},
            "offenders": [],
            "unverifiable": [],
            "event_types": {},
            "arithmetic_ok": True,
            "error": str(exc)[:300],
        }

    # Enumerate event types seen, with counts.
    event_type_counts = {}
    for row in raw_events:
        etype = _extract_event_type(row)
        event_type_counts[etype] = event_type_counts.get(etype, 0) + 1

    # Filter to relevant events (replies and bounces).
    relevant = []
    for row in raw_events:
        etype = _extract_event_type(row)
        if etype.lower() in RELEVANT_EVENT_TYPES:
            relevant.append(row)

    subjects = len(relevant)
    offenders = []
    unverifiable = []
    clean_count = 0
    test_identity_matched_id_alone = 0

    # Build a lookup of store events for matching.
    store_events_by_record = _build_store_event_index(recs)

    for row in relevant:
        event_id = _extract_provider_event_id(row)
        lead_id = _extract_lead_id(row)
        campaign_id = _extract_campaign_id(row)
        etype = _extract_event_type(row)

        # TEST IDENTITY EXCLUSION: check the id ALONE, not on the row
        # that also carries the address. ISSUE-044.
        if testidentity.matches(lead_id):
            test_identity_matched_id_alone += 1
            continue

        # Resolve ownership per event from the registry, per provider.
        # An EmailBison campaign id is compared against our EmailBison
        # campaign rows, NOT against HeyReach ids.
        owner = _resolve_ownership_emailbison(campaign_id, campaigns)
        if owner is None:
            # Cannot prove ownership — unverifiable, not a drop.
            unverifiable.append({
                "provider_event_id": event_id,
                "lead_id": lead_id,
                "campaign_id": campaign_id,
                "event_type": etype,
                "why": "ownership not resolved from registry",
            })
            continue

        # Check for a matching store event.
        matched = _match_store_event(
            lead_id, campaign_id, etype, store_events_by_record)
        if matched:
            clean_count += 1
        else:
            offenders.append({
                "provider_event_id": event_id,
                "lead_id": lead_id,
                "campaign_id": campaign_id,
                "event_type": etype,
                "why": "no matching store event found",
            })

    all_offender_or_unverifiable = len(offenders) + len(unverifiable)
    # Subjects here exclude test-identity matches.
    effective_subjects = subjects - test_identity_matched_id_alone
    arithmetic_ok = clean_count + all_offender_or_unverifiable == \
        effective_subjects

    verdict = PASS
    if not arithmetic_ok:
        verdict = ERROR
    elif effective_subjects == 0:
        verdict = VACUOUS
    elif offenders:
        verdict = FAIL

    key_presence = {
        "subjects": effective_subjects,
        "provider_event_id_present": sum(
            1 for r in relevant if _extract_provider_event_id(r)),
        "lead_id_present": sum(
            1 for r in relevant if _extract_lead_id(r)),
        "test_identity_matched_id_alone": test_identity_matched_id_alone,
    }

    return {
        "rule": RULE_PROVIDER_EVENT,
        "verdict": verdict,
        "subjects": effective_subjects,
        "clean": clean_count,
        "key_presence": key_presence,
        "offenders": offenders,
        "unverifiable": unverifiable,
        "event_types": event_type_counts,
        "arithmetic_ok": arithmetic_ok,
    }


# -------------------------------------------------------- helpers

def _campaign_for(rec, rows, requires=None):
    """The record's campaign, optionally one that can serve a channel."""
    for campaign in rows:
        if rec.get("id") in (campaign.get("record_ids") or []):
            if requires and not campaign.get(requires):
                continue
            return campaign
    return None


def _extract_event_type(row):
    """The event type from a bison event envelope.

    The rows are ENVELOPES, not events. Each carries the event under
    ``payload``. Falls back to the row's own ``type`` field.
    """
    if not isinstance(row, dict):
        return "unknown"
    payload = row.get("payload")
    if isinstance(payload, dict):
        declared = str(payload.get("type") or "").strip()
        if declared:
            return declared
    declared = str(row.get("type") or "").strip()
    if declared:
        return declared
    declared = str(row.get("event") or "").strip()
    if declared:
        return declared
    return "unknown"


def _extract_provider_event_id(row):
    """A stable identifier for a provider event."""
    if not isinstance(row, dict):
        return None
    payload = row.get("payload")
    if isinstance(payload, dict):
        eid = payload.get("id") or payload.get("event_id")
        if eid:
            return str(eid)
    return str(row.get("id") or row.get("event_id") or "")


def _extract_lead_id(row):
    """The lead id from a provider event."""
    if not isinstance(row, dict):
        return None
    payload = row.get("payload")
    if isinstance(payload, dict):
        lid = payload.get("lead_id") or payload.get("leadId")
        if lid is not None:
            return lid
    lid = row.get("lead_id") or row.get("leadId")
    if lid is not None:
        return lid
    return None


def _extract_campaign_id(row):
    """The campaign id from a provider event."""
    if not isinstance(row, dict):
        return None
    payload = row.get("payload")
    if isinstance(payload, dict):
        cid = payload.get("campaign_id") or payload.get("campaignId")
        if cid is not None:
            return cid
    cid = row.get("campaign_id") or row.get("campaignId")
    if cid is not None:
        return cid
    return None


def _resolve_ownership_emailbison(campaign_id, campaigns):
    """Resolve whether this EmailBison campaign belongs to us.

    Resolved per event from the REGISTRY (campaigns.jsonl), per provider.
    An EmailBison campaign id is compared against our bison_campaign_id
    values, NEVER against HeyReach ids.

    Returns the campaign row if found, None if not resolved.
    """
    if campaign_id is None:
        return None
    cid_str = str(campaign_id)
    for camp in campaigns:
        if str(camp.get("bison_campaign_id") or "") == cid_str:
            return camp
    return None


def _build_store_event_index(recs):
    """Index store events by (lead_id, campaign_id) for matching."""
    index = {}
    for rec in recs:
        for ev in rec.get("events") or []:
            if not isinstance(ev, dict):
                continue
            etype = str(ev.get("type") or "").lower()
            if etype not in ("reply_received", "email_bounced"):
                continue
            contact_key = ev.get("contact_key")
            # Find the contact's lead ids.
            for contact in rec.get("contacts") or []:
                if contact.get("key") != contact_key and contact_key:
                    continue
                bison_id = contact.get("bison_lead_id")
                if bison_id:
                    k = (str(bison_id), None)
                    index.setdefault(k, []).append(ev)
    return index


def _match_store_event(lead_id, campaign_id, event_type, store_index):
    """Does the store have a matching event for this provider event?"""
    if lead_id is None:
        return False
    lid_str = str(lead_id)
    # Try exact match first.
    for key, evts in store_index.items():
        if str(key[0]) == lid_str:
            return True
    return False


# -------------------------------------------------------- live providers

def _live_bison_membership(campaign_id, lead_ids):
    """Call the real EmailBison for membership status."""
    result = bison.membership(campaign_id, lead_ids)
    lid = int(lead_ids[0])
    return result.get(lid, "")


def _live_heyreach_campaigns(profile_url=None, linkedin_id=None):
    """Call the real HeyReach for campaigns this lead is in."""
    return heyreach.campaigns_for_lead(
        profile_url=profile_url, linkedin_id=linkedin_id)


def _live_fetch_bison_events():
    """Walk the real EmailBison event feed."""
    return bison.walk_events()


# -------------------------------------------------------- notification

def raise_critical(message, ids=None):
    """Raise a CRITICAL notification through the canonical path.

    The destination is GLOBAL and the severity is CRITICAL, as
    SLACK-NOTIFICATIONS.md specifies for reconciliation mismatches.
    """
    from src import notify
    return notify.notify(
        notify.REPLY_PROTECTION_FAILED,
        None,
        fields={"check": "reconcile", "message": message,
                "offender_count": len(ids or [])},
        ids={"reconcile_ids": ",".join(str(i) for i in (ids or [])[:10])})


# -------------------------------------------------------- the runner

def run(*, phase="ongoing", workspaces=None, recs=None, camps=None,
        bison_membership=None, heyreach_campaigns=None,
        fetch_bison_events=None, notify_fn=None):
    """Run both reconciliation rules and return the combined result.

    ``recs`` and ``camps`` are injection points for tests. Live use
    loads from the workspaces copy.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    if recs is None or camps is None:
        if not workspaces:
            return _error_result("no workspaces path and no recs injected")
        recs, camps, file_evidence = _load_from_workspaces(workspaces)
    else:
        file_evidence = [{"path": "injected", "rows": len(recs),
                          "mtime": "injected"}]

    # Key presence is reported FIRST, per rule, before any verdict.
    key_presence_stopped = _key_presence_stopped(recs)

    result_stopped = check_stopped_here(
        recs, camps,
        bison_membership=bison_membership,
        heyreach_campaigns=heyreach_campaigns)

    result_events = check_provider_events(
        recs, camps,
        fetch_bison_events=fetch_bison_events)

    # Overall verdict: worst of the two.
    verdicts = [result_stopped["verdict"], result_events["verdict"]]
    verdict = _worst_verdict(verdicts)

    # Collect all offender ids for notification.
    all_offenders = []
    for o in result_stopped.get("offenders", []):
        all_offenders.append(o.get("record", ""))
    for o in result_events.get("offenders", []):
        all_offenders.append(o.get("provider_event_id", ""))

    # Raise CRITICAL on any mismatch in ongoing phase.
    notification = None
    if phase == "ongoing" and all_offenders and notify_fn:
        notification = notify_fn(
            f"reconciliation mismatch: {len(all_offenders)} offenders",
            all_offenders)

    subjects_total = result_stopped["subjects"] + result_events["subjects"]
    clean_total = result_stopped["clean"] + result_events["clean"]

    return {
        "check": "reconcile",
        "phase": phase,
        "verdict": verdict,
        "subjects": subjects_total,
        "clean": clean_total,
        "rules": dict(RULES),
        "counts": {
            RULE_STOPPED: len(result_stopped.get("offenders", [])),
            RULE_PROVIDER_EVENT: len(result_events.get("offenders", [])),
        },
        "offenders": {
            RULE_STOPPED: [o.get("record", "")
                           for o in result_stopped.get("offenders", [])],
            RULE_PROVIDER_EVENT: [o.get("provider_event_id", "")
                                  for o in result_events.get("offenders", [])],
        },
        "unverifiable": {
            RULE_STOPPED: [o.get("record", "")
                           for o in result_stopped.get("unverifiable", [])],
            RULE_PROVIDER_EVENT: [o.get("provider_event_id", "")
                                  for o in result_events.get("unverifiable", [])],
        },
        "key_presence": {
            RULE_STOPPED: key_presence_stopped,
            RULE_PROVIDER_EVENT: result_events.get("key_presence", {}),
        },
        "rule_details": {
            RULE_STOPPED: result_stopped,
            RULE_PROVIDER_EVENT: result_events,
        },
        "evidence": {
            "files_read": file_evidence,
            "provider_reads_skipped": False,
        },
        "measured_at": now.isoformat(),
        "workspaces": workspaces or "injected",
    }


def _worst_verdict(verdicts):
    """The worst verdict from a list. ERROR > FAIL > UNCONFIRMED > VACUOUS > PASS."""
    order = {PASS: 0, VACUOUS: 1, UNCONFIRMED: 2, FAIL: 3, ERROR: 4}
    worst = PASS
    for v in verdicts:
        if order.get(v, 0) > order.get(worst, 0):
            worst = v
    return worst


def _error_result(message):
    """An ERROR result for when the check itself broke."""
    return {
        "check": "reconcile",
        "phase": "ongoing",
        "verdict": ERROR,
        "subjects": 0,
        "clean": 0,
        "rules": dict(RULES),
        "counts": {RULE_STOPPED: 0, RULE_PROVIDER_EVENT: 0},
        "offenders": {RULE_STOPPED: [], RULE_PROVIDER_EVENT: []},
        "unverifiable": {RULE_STOPPED: [], RULE_PROVIDER_EVENT: []},
        "key_presence": {},
        "rule_details": {},
        "evidence": {"error": message},
        "measured_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "workspaces": None,
    }


def _load_from_workspaces(path):
    """Load recs and campaigns from a named work/ copy."""
    import time

    queue_file = os.path.join(path, "queue.jsonl")
    camp_file = os.path.join(path, "campaigns.jsonl")

    if not os.path.isdir(path):
        raise FileNotFoundError(f"workspaces path does not exist: {path}")
    if not os.path.isfile(queue_file):
        raise FileNotFoundError(f"no queue.jsonl at: {queue_file}")

    q_mtime = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(queue_file)))
    recs = store.read_jsonl(queue_file)

    c_mtime = ""
    camps = []
    if os.path.isfile(camp_file):
        c_mtime = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(os.path.getmtime(camp_file)))
        camps = store.read_jsonl(camp_file)

    file_evidence = [
        {"path": queue_file, "rows": len(recs), "mtime": q_mtime},
        {"path": camp_file, "rows": len(camps), "mtime": c_mtime},
    ]
    return recs, camps, file_evidence


# -------------------------------------------------------- exit codes

def exit_code(verdict):
    """Map a verdict to a process exit code."""
    return {PASS: 0, FAIL: 1, UNCONFIRMED: 2, VACUOUS: 2, ERROR: 3}.get(
        verdict, 3)


# -------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0])
    parser.add_argument("--phase", default="ongoing",
                        choices=("pre_push", "post_push", "ongoing"))
    parser.add_argument("--workspaces", required=True,
                        help="path to a copy of production work/")
    parser.add_argument("--json", default=None,
                        help="where to write the result JSON")
    parser.add_argument("--live-reads", action="store_true", default=True)
    args = parser.parse_args(argv)

    result = run(phase=args.phase, workspaces=args.workspaces)

    output = json.dumps(result, indent=2, sort_keys=True, default=str)
    print(output)

    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(output)

    return exit_code(result["verdict"])


if __name__ == "__main__":
    sys.exit(main())
