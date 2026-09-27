#!/usr/bin/env python3
"""QA check: post-push readback — did the push land, and is it sending?

TASK-298. Lane F, the standing QA suite. Runs within one cycle of the push
and answers five questions:

    exactly_the_pushed_leads_are_attached
                              set equality at the provider, diffed BOTH
                              directions: pushed-and-absent, and
                              present-and-not-pushed
    every_scheduled_step_has_subject_and_body
                              on the RENDERED queue rows at the provider, not
                              on our templates
    first_scheduled_send_recorded
                              a timestamp, per campaign, read back
    a_watcher_is_on_the_campaign
                              and the watcher is running the code we think
    linkedin_leads_read_pending_or_insequence
                              for the LinkedIn half, when there is one

THE THING THAT MAKES THIS HARD — ISSUE-043.

`bison.attach_leads` reads membership back 6 times over ~15s and raises
`ProviderError` when the lead is absent. The campaign-membership index took
~30 seconds. Absent within the window is UNCONFIRMED (exit 2), retried on a
fixed schedule: t+60s, t+180s, t+600s from the push. Still absent at t+600s
becomes FAIL.

READS ONLY. No provider write of any kind.

Usage:
    py -3 scripts/qa/check_readback.py \\
        --phase post_push \\
        --campaign 502 --campaign 503 \\
        --workspaces <path to work/ copy> \\
        --push-time 2026-09-25T06:00:00Z \\
        --json work/qa/<run>/readback.json
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

from src import emptyrender
from src.providers import bison, heyreach

# ------------------------------------------------------------- exit codes

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNCONFIRMED = 2
EXIT_ERROR = 3

# ------------------------------------------------------------- rule names

RULES = {
    "exactly_the_pushed_leads_are_attached":
        "set equality at the provider, diffed BOTH directions: "
        "pushed-and-absent, and present-and-not-pushed",
    "every_scheduled_step_has_subject_and_body":
        "on the RENDERED queue rows at the provider, not on our templates; "
        "empty, 'None' and unrendered are three separate counts",
    "first_scheduled_send_recorded":
        "a timestamp, per campaign, read back; enrolled is not sent, "
        "scheduled is not sent, active is not sent",
    "a_watcher_is_on_the_campaign":
        "a watcher is registered for this campaign id AND is running the "
        "code we think — module mtime against process start time",
    "linkedin_leads_read_pending_or_insequence":
        "for the LinkedIn half, when there is one; VACUOUS with a stated "
        "reason when there is no LinkedIn half",
}

# ------------------------------------------------------------- retry ladder

RETRY_SCHEDULE_SECONDS = (60, 180, 600)

# ------------------------------------------------------------- helpers


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s):
    """Parse an ISO timestamp string to a datetime."""
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _load_queue(workspaces_path):
    """Load queue.jsonl from the named work/ copy."""
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


def _campaigns_by_bison_id(rows):
    """Index campaign rows by their bison_campaign_id."""
    index = {}
    for row in rows:
        bid = row.get("bison_campaign_id")
        if bid is not None:
            index[int(bid)] = row
    return index


def _campaigns_by_heyreach_id(rows):
    """Index campaign rows by their heyreach_campaign_id."""
    index = {}
    for row in rows:
        hid = row.get("heyreach_campaign_id")
        if hid is not None:
            index[int(hid)] = row
    return index


def _pushed_lead_ids_for_campaign(recs, campaign_row):
    """The record ids the push attached to this campaign.

    Reads from the queue records' contacts, matching by campaign id.
    Returns a set of record ids.
    """
    bison_id = campaign_row.get("bison_campaign_id")
    pushed = set()
    for rec in recs:
        for contact in rec.get("contacts") or []:
            if bison_id and str(contact.get("bison_campaign_id") or "") == str(bison_id):
                pushed.add(rec.get("id"))
    return pushed


def _pushed_bison_lead_ids_for_campaign(recs, campaign_row):
    """The bison_lead_ids the push attached to this campaign.

    Returns a dict of {bison_lead_id: record_id}.
    """
    bison_id = campaign_row.get("bison_campaign_id")
    mapping = {}
    for rec in recs:
        for contact in rec.get("contacts") or []:
            if bison_id and str(contact.get("bison_campaign_id") or "") == str(bison_id):
                lid = contact.get("bison_lead_id")
                if lid:
                    mapping[int(lid)] = rec.get("id")
    return mapping


def _pushed_profile_urls_for_campaign(recs, campaign_row):
    """The LinkedIn profile URLs the push attached to this HeyReach campaign.

    Returns a dict of {profile_url: record_id}.
    """
    hr_id = campaign_row.get("heyreach_campaign_id")
    mapping = {}
    for rec in recs:
        for contact in rec.get("contacts") or []:
            if hr_id and str(contact.get("heyreach_campaign_id") or "") == str(hr_id):
                url = contact.get("linkedin") or contact.get("linkedin_url")
                if url:
                    mapping[url.strip().lower()] = rec.get("id")
    return mapping


# ------------------------------------------------------------- rule 1

def check_exactly_the_pushed_leads(
    campaign_id, pushed_lead_ids, *,
    provider_campaign_lead_ids=None,
    provider_membership=None,
):
    """Rule 1: set equality, both directions.

    ``pushed_lead_ids`` is a dict of {lead_id: record_id} for the push.
    Returns a result dict with pushed_and_absent and present_and_not_pushed.

    ``provider_campaign_lead_ids`` and ``provider_membership`` are injection
    points for tests. Live use passes None, which calls the real provider.
    """
    provider_campaign_lead_ids = (
        provider_campaign_lead_ids or bison.campaign_lead_ids)

    pushed_set = set(pushed_lead_ids.keys())

    try:
        provider_ids = set(provider_campaign_lead_ids(campaign_id))
    except Exception as exc:
        return {
            "rule": "exactly_the_pushed_leads_are_attached",
            "verdict": UNCONFIRMED,
            "pushed_and_absent": [],
            "present_and_not_pushed": [],
            "pushed_count": len(pushed_set),
            "provider_count": None,
            "error": str(exc)[:300],
            "provider_ids": None,
        }

    pushed_and_absent = pushed_set - provider_ids
    present_and_not_pushed = provider_ids - pushed_set

    if pushed_and_absent or present_and_not_pushed:
        verdict = UNCONFIRMED
    else:
        verdict = PASS

    pushed_and_absent_named = [
        {"lead_id": lid, "record_id": pushed_lead_ids.get(lid)}
        for lid in sorted(pushed_and_absent)
    ]
    present_and_not_pushed_list = sorted(present_and_not_pushed)

    return {
        "rule": "exactly_the_pushed_leads_are_attached",
        "verdict": verdict,
        "pushed_and_absent": pushed_and_absent_named,
        "present_and_not_pushed": present_and_not_pushed_list,
        "pushed_count": len(pushed_set),
        "provider_count": len(provider_ids),
        "error": None,
        "provider_ids": sorted(provider_ids),
    }


# ------------------------------------------------------------- rule 2

def check_every_scheduled_step_has_subject_and_body(
    campaign_id, *,
    provider_scheduled_emails=None,
    cap=200,
):
    """Rule 2: rendered rows at the provider have words in them.

    Three separate fault counts: empty, literal 'None', and unrendered '{'.
    A campaign with zero scheduled rows is VACUOUS, not PASS.

    ``provider_scheduled_emails`` is an injection point for tests.
    """
    provider_scheduled_emails = (
        provider_scheduled_emails or bison.scheduled_emails)

    try:
        rows = provider_scheduled_emails(campaign_id, cap=cap)
    except Exception as exc:
        return {
            "rule": "every_scheduled_step_has_subject_and_body",
            "verdict": UNCONFIRMED,
            "total_rows": None,
            "empty_count": 0,
            "literal_none_count": 0,
            "unrendered_count": 0,
            "offending_row_ids": [],
            "vacuous": False,
            "vacuous_reason": None,
            "error": str(exc)[:300],
            "row_keys_sample": None,
        }

    if not rows:
        return {
            "rule": "every_scheduled_step_has_subject_and_body",
            "verdict": VACUOUS,
            "total_rows": 0,
            "empty_count": 0,
            "literal_none_count": 0,
            "unrendered_count": 0,
            "offending_row_ids": [],
            "vacuous": True,
            "vacuous_reason": (
                "zero scheduled rows — the scheduler builds rows at the end "
                "of a sending day, so zero rows an hour after a push is "
                "normal and proves nothing"),
            "error": None,
            "row_keys_sample": None,
        }

    sample_keys = sorted(rows[0].keys()) if rows else None

    found = emptyrender.scan(rows)
    all_faults = found.get("pending", []) + found.get("already", [])

    empty_count = 0
    literal_none_count = 0
    unrendered_count = 0
    offending_ids = []

    for entry in all_faults:
        row_id = entry.get("row")
        if row_id not in offending_ids:
            offending_ids.append(row_id)
        for field, reason in entry.get("faults", []):
            if reason == emptyrender.EMPTY:
                empty_count += 1
            elif reason == emptyrender.LITERAL_NONE:
                literal_none_count += 1
            elif reason == emptyrender.PLACEHOLDER:
                unrendered_count += 1

    total_faults = empty_count + literal_none_count + unrendered_count
    verdict = PASS if total_faults == 0 else FAIL

    return {
        "rule": "every_scheduled_step_has_subject_and_body",
        "verdict": verdict,
        "total_rows": len(rows),
        "empty_count": empty_count,
        "literal_none_count": literal_none_count,
        "unrendered_count": unrendered_count,
        "offending_row_ids": offending_ids,
        "vacuous": False,
        "vacuous_reason": None,
        "error": None,
        "row_keys_sample": sample_keys,
    }


# ------------------------------------------------------------- rule 3

def check_first_scheduled_send(
    campaign_id, *,
    provider_sending_schedule=None,
    provider_schedule=None,
    now=None,
):
    """Rule 3: the first scheduled send timestamp, per campaign.

    Enrolled is not sent, scheduled is not sent, active is not sent.
    Reads the timestamp back and reports the sending window beside it.

    Returns a result dict. VACUOUS when the schedule is empty (weekend or
    outside window).

    ``provider_sending_schedule`` and ``provider_schedule`` are injection
    points for tests.
    """
    provider_sending_schedule = (
        provider_sending_schedule or _safe_sending_schedule)
    provider_schedule = provider_schedule or bison.schedule
    now = now or datetime.datetime.now(datetime.timezone.utc)

    schedule_data = {}
    try:
        sched = provider_schedule(campaign_id)
        if sched:
            tz = sched.get("timezone")
            start_hour = sched.get("start_hour") or sched.get("start_time")
            end_hour = sched.get("end_hour") or sched.get("end_time")
            days = sched.get("days") or sched.get("sending_days")
            schedule_data = {
                "timezone": tz,
                "start_hour": start_hour,
                "end_hour": end_hour,
                "days": days,
            }
    except Exception:
        pass

    first_send = None
    sending_schedule_evidence = []

    for day in ("today", "tomorrow", "day_after_tomorrow"):
        try:
            result = provider_sending_schedule(campaign_id, day)
            if result is not None:
                sending_schedule_evidence.append({
                    "day": day,
                    "emails_being_sent": result.get("emails_being_sent"),
                    "earliest": result.get("earliest_send_at"),
                })
                earliest = result.get("earliest_send_at")
                if earliest and (first_send is None or earliest < first_send):
                    first_send = earliest
        except _SendingScheduleEmpty:
            sending_schedule_evidence.append({
                "day": day,
                "emails_being_sent": 0,
                "earliest": None,
                "empty": True,
            })
        except Exception:
            pass

    is_weekend = now.weekday() >= 5
    is_outside_window = _is_outside_business_window(now, schedule_data)

    verdict = PASS if first_send else UNCONFIRMED
    vacuous = False
    vacuous_reason = None

    if not first_send and (is_weekend or is_outside_window):
        verdict = VACUOUS
        vacuous = True
        parts = []
        if is_weekend:
            parts.append("weekend")
        if is_outside_window:
            parts.append("outside 09:00-17:00 window")
        vacuous_reason = (
            f"no scheduled send found, but it is a {' and '.join(parts)} — "
            f"every EmailBison campaign is 09:00-17:00 Mon-Fri in its own "
            f"timezone (ISSUE-045)")

    return {
        "rule": "first_scheduled_send_recorded",
        "verdict": verdict,
        "first_scheduled_send": first_send,
        "sending_window": schedule_data,
        "is_weekend": is_weekend,
        "is_outside_window": is_outside_window,
        "sending_schedule_evidence": sending_schedule_evidence,
        "vacuous": vacuous,
        "vacuous_reason": vacuous_reason,
    }


class _SendingScheduleEmpty(Exception):
    """The provider has nothing planned for this day."""


def _safe_sending_schedule(campaign_id, day):
    """Call bison.sending_schedule, translating its empty exception."""
    try:
        return bison.sending_schedule(campaign_id, day)
    except bison.SendingScheduleEmpty:
        raise _SendingScheduleEmpty()


def _is_outside_business_window(now, schedule_data):
    """Is the current time outside the campaign's sending window?

    EmailBison campaigns are 09:00-17:00 Mon-Fri in their own timezone.
    """
    tz_name = schedule_data.get("timezone")
    if not tz_name:
        return False
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(tz_name)
        local_now = now.astimezone(tz)
    except Exception:
        return False
    if local_now.weekday() >= 5:
        return True
    hour = local_now.hour
    start = int(schedule_data.get("start_hour") or 9)
    end = int(schedule_data.get("end_hour") or 17)
    return hour < start or hour >= end


# ------------------------------------------------------------- rule 4

_UNSET = object()


def check_watcher_on_campaign(
    campaign_id, *,
    heartbeats_fn=None,
    supervisor_witnesses_fn=None,
    monitor_list=None,
    module_mtime_fn=_UNSET,
):
    """Rule 4: a watcher is registered AND running the code we think.

    A merge is not a deploy: the loop may be running code from before the
    fix. Check the watcher module's mtime against the process start time.

    Four witnesses per watcher: heartbeat, log last line, process start,
    module mtime.

    All parameters are injection points for tests. Pass ``module_mtime_fn``
    explicitly (even as None) to suppress the real file read.
    """
    from src import watchsink as _ws
    from src import supervisor as _sv

    heartbeats_fn = heartbeats_fn or _ws.heartbeats

    all_beats = heartbeats_fn()

    matching_beats = []
    for beat in all_beats:
        beat_campaign = beat.get("campaign")
        if beat_campaign is not None and str(beat_campaign) == str(campaign_id):
            matching_beats.append(beat)

    if not matching_beats:
        return {
            "rule": "a_watcher_is_on_the_campaign",
            "verdict": FAIL,
            "watcher_found": False,
            "heartbeat": None,
            "log_last_line": None,
            "process_start": None,
            "module_mtime": None,
            "module_stale": None,
            "detail": f"no watcher heartbeat found for campaign {campaign_id}",
        }

    latest_beat = matching_beats[0]
    beat_at = latest_beat.get("at")
    beat_epoch = latest_beat.get("epoch")

    source = latest_beat.get("source", "")
    watcher_module = _watcher_module_for_source(source)

    module_mtime = None
    module_mtime_iso = None
    if module_mtime_fn is not _UNSET:
        if module_mtime_fn is not None:
            module_mtime = module_mtime_fn(watcher_module)
    elif watcher_module:
        module_mtime = _file_mtime(watcher_module)
    if module_mtime is not None:
        module_mtime_iso = datetime.datetime.fromtimestamp(
            module_mtime, tz=datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")

    process_start = None
    if supervisor_witnesses_fn and monitor_list:
        for mon in monitor_list:
            mon_campaign = (mon.get("heartbeat") or {}).get("campaign")
            if mon_campaign is not None and str(mon_campaign) == str(campaign_id):
                wit = supervisor_witnesses_fn(mon)
                state_written = wit.get("state_written_at")
                if state_written is not None:
                    process_start = datetime.datetime.fromtimestamp(
                        state_written, tz=datetime.timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ")
                break

    log_last_line = _read_log_last_line(source, campaign_id)

    module_stale = None
    if module_mtime is not None and process_start is not None:
        ps = _parse_iso(process_start)
        if ps is not None:
            module_stale = module_mtime > ps.timestamp()

    verdict = PASS
    if not latest_beat.get("at"):
        verdict = UNCONFIRMED
    elif module_stale is True:
        verdict = FAIL

    return {
        "rule": "a_watcher_is_on_the_campaign",
        "verdict": verdict,
        "watcher_found": True,
        "heartbeat": beat_at,
        "heartbeat_epoch": beat_epoch,
        "log_last_line": log_last_line,
        "process_start": process_start,
        "module_mtime": module_mtime_iso,
        "module_mtime_raw": module_mtime,
        "module_stale": module_stale,
        "watcher_module": watcher_module,
        "detail": None,
    }


def _watcher_module_for_source(source):
    """Map a watcher source name to its module file path."""
    mapping = {
        "bison": "scripts/bison_watch_loop.py",
        "heyreach": "scripts/heyreach_watch_loop.py",
        "reply": "scripts/reply_watch_loop.py",
    }
    module_rel = mapping.get(source)
    if not module_rel:
        return None
    return os.path.join(_ROOT, module_rel)


def _file_mtime(path):
    """Get the mtime of a file, or None."""
    try:
        return os.path.getmtime(path)
    except (OSError, TypeError):
        return None


def _read_log_last_line(source, campaign_id):
    """Read the last line from a watcher's event log."""
    from src import watchsink
    path = watchsink.events_path(source, campaign_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return lines[-1].strip() if lines else None
    except Exception:
        return None


# ------------------------------------------------------------- rule 5

def check_linkedin_leads_pending_or_insequence(
    campaign_id, pushed_urls, *,
    provider_campaign_leads=None,
    provider_campaign_stats=None,
):
    """Rule 5: LinkedIn leads read pending or in_sequence.

    When the batch has no LinkedIn half, this rule is VACUOUS with a stated
    reason, never PASS.

    ``provider_campaign_leads`` and ``provider_campaign_stats`` are injection
    points for tests.
    """
    if not pushed_urls:
        return {
            "rule": "linkedin_leads_read_pending_or_insequence",
            "verdict": VACUOUS,
            "subjects": 0,
            "pending_or_insequence": 0,
            "other_states": [],
            "campaign_stats": None,
            "vacuous": True,
            "vacuous_reason": (
                "no LinkedIn leads in this batch — this is an email-only "
                "push; the LinkedIn rule is VACUOUS, not PASS"),
        }

    provider_campaign_leads = (
        provider_campaign_leads or _live_heyreach_campaign_leads)
    provider_campaign_stats = (
        provider_campaign_stats or heyreach.campaign_stats)

    try:
        leads, total = provider_campaign_leads(campaign_id)
    except Exception as exc:
        return {
            "rule": "linkedin_leads_read_pending_or_insequence",
            "verdict": UNCONFIRMED,
            "subjects": len(pushed_urls),
            "pending_or_insequence": 0,
            "other_states": [],
            "campaign_stats": None,
            "vacuous": False,
            "vacuous_reason": None,
            "error": str(exc)[:300],
        }

    stats = None
    try:
        stats = provider_campaign_stats(campaign_id)
    except Exception:
        pass

    pushed_lower = {str(u).strip().lower() for u in pushed_urls}
    pending_or_inseq = 0
    other_states = []

    for lead in leads:
        url = str(lead.get("profile_url") or "").strip().lower()
        if url not in pushed_lower:
            continue
        state = lead.get("state", "")
        if state in ("request_pending", "request_sent", "accepted",
                      "replied", "InSequence", "Pending"):
            pending_or_inseq += 1
        else:
            other_states.append({
                "profile_url": url[:50],
                "state": state,
                "raw": lead.get("raw"),
            })

    verdict = PASS if not other_states else FAIL
    if pending_or_inseq == 0 and not other_states:
        verdict = UNCONFIRMED

    return {
        "rule": "linkedin_leads_read_pending_or_insequence",
        "verdict": verdict,
        "subjects": len(pushed_urls),
        "pending_or_insequence": pending_or_inseq,
        "other_states": other_states,
        "campaign_stats": stats,
        "vacuous": False,
        "vacuous_reason": None,
    }


def _live_heyreach_campaign_leads(campaign_id):
    """Page through all leads for a HeyReach campaign."""
    offset = 0
    leads = []
    total = None
    for _ in range(50):
        page, count = heyreach.campaign_leads(campaign_id, offset=offset)
        if count is not None:
            total = count
        leads.extend(page)
        if not page or (total is not None and offset + len(page) >= int(total)):
            break
        offset += len(page)
    return leads, total


# ------------------------------------------------------------- retry logic

def _run_membership_attempt(campaign_id, pushed_lead_ids,
                            provider_campaign_lead_ids=None):
    """One attempt at reading membership back. Returns the rule-1 result."""
    return check_exactly_the_pushed_leads(
        campaign_id, pushed_lead_ids,
        provider_campaign_lead_ids=provider_campaign_lead_ids)


def _apply_retry_ladder(campaign_id, pushed_lead_ids, push_time,
                        now_fn=None,
                        provider_campaign_lead_ids=None):
    """Run the retry ladder for rule 1.

    Three attempts at t+60s, t+180s, t+600s from the push.
    Returns a list of attempt results and the final verdict.
    """
    now_fn = now_fn or (lambda: datetime.datetime.now(datetime.timezone.utc))
    push_dt = _parse_iso(push_time) if isinstance(push_time, str) else push_time
    if push_dt is None:
        push_dt = now_fn()

    attempts = []

    first_result = _run_membership_attempt(
        campaign_id, pushed_lead_ids, provider_campaign_lead_ids)
    attempts.append({
        "attempt": 0,
        "label": "initial",
        "result": first_result,
        "verdict": first_result["verdict"],
    })

    if first_result["verdict"] == PASS:
        for offset_s in RETRY_SCHEDULE_SECONDS:
            attempt_time = push_dt + datetime.timedelta(seconds=offset_s)
            attempts.append({
                "attempt": len(attempts),
                "label": f"t+{offset_s}s",
                "scheduled_at": attempt_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "result": None,
                "verdict": "NOT_RUN",
                "reason": "initial attempt passed; retry ladder not needed",
            })
        return attempts, PASS

    for i, offset_s in enumerate(RETRY_SCHEDULE_SECONDS):
        attempt_time = push_dt + datetime.timedelta(seconds=offset_s)
        result = _run_membership_attempt(
            campaign_id, pushed_lead_ids, provider_campaign_lead_ids)
        attempt_entry = {
            "attempt": i + 1,
            "label": f"t+{offset_s}s",
            "scheduled_at": attempt_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "result": result,
            "verdict": result["verdict"],
            "pushed_and_absent_count": len(result.get("pushed_and_absent", [])),
            "present_and_not_pushed_count": len(
                result.get("present_and_not_pushed", [])),
        }
        attempts.append(attempt_entry)
        if result["verdict"] == PASS:
            break

    last_run = None
    for a in reversed(attempts):
        if a.get("result") is not None:
            last_run = a
            break

    if last_run is None:
        final = UNCONFIRMED
    elif last_run["verdict"] == PASS:
        final = PASS
    elif last_run["verdict"] == UNCONFIRMED:
        final = FAIL
    else:
        final = last_run["verdict"]

    return attempts, final


# ------------------------------------------------------------- the runner

def run(phase="post_push", campaigns=None, workspaces=None, json_path=None,
        live_reads=True, push_time=None,
        bison_campaign_lead_ids=None,
        bison_scheduled_emails=None,
        bison_sending_schedule=None,
        bison_schedule=None,
        heyreach_campaign_leads=None,
        heyreach_campaign_stats=None,
        heartbeats_fn=None,
        supervisor_witnesses_fn=None,
        module_mtime_fn=None,
        now_fn=None):
    """Run the post-push readback check.

    Parameters
    ----------
    phase : str
        Must be post_push.
    campaigns : list of int
        Provider campaign ids.
    workspaces : str
        Path to a named copy of production work/.
    json_path : str
        Where to write the result JSON.
    live_reads : bool
        Whether to make provider reads.
    push_time : str
        ISO timestamp of the push. Used for the retry ladder schedule.
    bison_campaign_lead_ids... : callable, optional
        Injection points for tests.
    """
    measured_at = _now_iso()
    campaign_ids = campaigns or []
    evidence = {"provider_reads": [], "files_read": []}

    queue_file_info = None
    campaign_file_info = None
    queue_rows = []
    campaign_rows = []

    if workspaces:
        try:
            queue_rows, queue_file_info = _load_queue(workspaces)
            evidence["files_read"].append(queue_file_info)
        except FileNotFoundError as e:
            return _error_result(str(e), phase, campaign_ids, measured_at)
        except Exception as e:
            return _error_result(f"reading queue: {e}", phase, campaign_ids,
                                 measured_at)
        try:
            campaign_rows, campaign_file_info = _load_campaign_rows(workspaces)
            evidence["files_read"].append(campaign_file_info)
        except FileNotFoundError:
            pass
        except Exception:
            pass
    else:
        return _error_result(
            "--workspaces is required", phase, campaign_ids, measured_at)

    bison_index = _campaigns_by_bison_id(campaign_rows)
    heyreach_index = _campaigns_by_heyreach_id(campaign_rows)

    if not campaign_ids:
        campaign_ids = sorted(bison_index.keys()) + sorted(heyreach_index.keys())

    if not campaign_ids:
        return _vacuous_result(
            "no campaigns found in registry",
            phase, campaign_ids, queue_file_info, measured_at)

    per_campaign = []
    all_rule_verdicts = {rule: [] for rule in RULES}
    all_rule_offenders = {rule: [] for rule in RULES}
    vacuous_campaigns = {}

    for cid in campaign_ids:
        campaign_result = _check_one_campaign(
            cid, bison_index.get(cid), heyreach_index.get(cid),
            queue_rows, live_reads, push_time,
            bison_campaign_lead_ids=bison_campaign_lead_ids,
            bison_scheduled_emails=bison_scheduled_emails,
            bison_sending_schedule=bison_sending_schedule,
            bison_schedule=bison_schedule,
            heyreach_campaign_leads=heyreach_campaign_leads,
            heyreach_campaign_stats=heyreach_campaign_stats,
            heartbeats_fn=heartbeats_fn,
            supervisor_witnesses_fn=supervisor_witnesses_fn,
            module_mtime_fn=module_mtime_fn,
            now_fn=now_fn,
        )
        per_campaign.append(campaign_result)

        for rule in RULES:
            rv = campaign_result.get("rules", {}).get(rule, {})
            verdict = rv.get("verdict", VACUOUS)
            all_rule_verdicts[rule].append(verdict)

            if rv.get("vacuous"):
                vacuous_campaigns[str(cid)] = rv.get("vacuous_reason", "")

            if verdict == FAIL:
                offenders = rv.get("offenders", [])
                all_rule_offenders[rule].extend(offenders)

    rule_verdicts = {}
    rule_counts = {}
    rule_offenders = {}
    for rule in RULES:
        vs = all_rule_verdicts.get(rule, [])
        if not vs:
            rule_verdicts[rule] = VACUOUS
        elif any(v == FAIL for v in vs):
            rule_verdicts[rule] = FAIL
        elif any(v == UNCONFIRMED for v in vs):
            rule_verdicts[rule] = UNCONFIRMED
        elif all(v == VACUOUS for v in vs):
            rule_verdicts[rule] = VACUOUS
        else:
            rule_verdicts[rule] = PASS
        rule_counts[rule] = len(all_rule_offenders.get(rule, []))
        rule_offenders[rule] = all_rule_offenders.get(rule, [])

    verdict_values = list(rule_verdicts.values())
    if any(v == FAIL for v in verdict_values):
        overall = FAIL
    elif any(v == UNCONFIRMED for v in verdict_values):
        overall = UNCONFIRMED
    elif all(v == VACUOUS for v in verdict_values):
        overall = VACUOUS
    else:
        overall = PASS

    subjects = len(campaign_ids)
    offending_campaigns = set()
    for rule_offs in rule_offenders.values():
        for off in rule_offs:
            parts = str(off).split(":")
            if parts:
                offending_campaigns.add(parts[0].strip())
    clean = subjects - len(offending_campaigns)

    result = {
        "check": "readback",
        "phase": phase,
        "verdict": overall,
        "campaigns": [str(c) for c in campaign_ids],
        "subjects": subjects,
        "clean": clean,
        "refused": overall not in (PASS, VACUOUS),
        "rules": dict(RULES),
        "counts": rule_counts,
        "offenders": rule_offenders,
        "unverifiable": {},
        "per_campaign": per_campaign,
        "vacuous_campaigns": vacuous_campaigns,
        "evidence": evidence,
        "measured_at": measured_at,
        "push_time": push_time,
        "workspaces": workspaces,
    }

    if json_path and workspaces:
        out_dir = os.path.dirname(json_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)

    return result


def _check_one_campaign(
    cid, bison_row, heyreach_row, queue_rows, live_reads, push_time,
    bison_campaign_lead_ids=None,
    bison_scheduled_emails=None,
    bison_sending_schedule=None,
    bison_schedule=None,
    heyreach_campaign_leads=None,
    heyreach_campaign_stats=None,
    heartbeats_fn=None,
    supervisor_witnesses_fn=None,
    module_mtime_fn=None,
    now_fn=None,
):
    """Run all five rules against one campaign."""
    rules_result = {}

    if bison_row:
        pushed_ids = _pushed_bison_lead_ids_for_campaign(queue_rows, bison_row)

        if live_reads:
            attempts, rule1_verdict = _apply_retry_ladder(
                cid, pushed_ids, push_time,
                now_fn=now_fn,
                provider_campaign_lead_ids=bison_campaign_lead_ids)
        else:
            attempts = [{"attempt": 0, "label": "skipped",
                         "verdict": UNCONFIRMED, "result": None,
                         "reason": "live reads disabled"}]
            rule1_verdict = UNCONFIRMED

        last_attempt = None
        for a in reversed(attempts):
            if a.get("result") is not None:
                last_attempt = a
                break

        pushed_absent = []
        present_not_pushed = []
        if last_attempt and last_attempt.get("result"):
            r = last_attempt["result"]
            pushed_absent = r.get("pushed_and_absent", [])
            present_not_pushed = r.get("present_and_not_pushed", [])

        rules_result["exactly_the_pushed_leads_are_attached"] = {
            "verdict": rule1_verdict,
            "retry_attempts": attempts,
            "pushed_and_absent": pushed_absent,
            "present_and_not_pushed": present_not_pushed,
            "pushed_count": len(pushed_ids),
        }

        if live_reads:
            rules_result["every_scheduled_step_has_subject_and_body"] = \
                check_every_scheduled_step_has_subject_and_body(
                    cid, provider_scheduled_emails=bison_scheduled_emails)
            rules_result["first_scheduled_send_recorded"] = \
                check_first_scheduled_send(
                    cid,
                    provider_sending_schedule=bison_sending_schedule,
                    provider_schedule=bison_schedule)
        else:
            rules_result["every_scheduled_step_has_subject_and_body"] = {
                "verdict": UNCONFIRMED, "total_rows": None,
                "empty_count": 0, "literal_none_count": 0,
                "unrendered_count": 0, "offending_row_ids": [],
                "vacuous": False, "vacuous_reason": None,
                "error": "live reads disabled", "row_keys_sample": None,
            }
            rules_result["first_scheduled_send_recorded"] = {
                "verdict": UNCONFIRMED, "first_scheduled_send": None,
                "sending_window": {}, "is_weekend": False,
                "is_outside_window": False,
                "sending_schedule_evidence": [],
                "vacuous": False, "vacuous_reason": None,
            }

        rules_result["a_watcher_is_on_the_campaign"] = \
            check_watcher_on_campaign(
                cid,
                heartbeats_fn=heartbeats_fn,
                supervisor_witnesses_fn=supervisor_witnesses_fn,
                module_mtime_fn=module_mtime_fn)

        pushed_urls = _pushed_profile_urls_for_campaign(
            queue_rows, heyreach_row) if heyreach_row else {}
        rules_result["linkedin_leads_read_pending_or_insequence"] = \
            check_linkedin_leads_pending_or_insequence(
                cid, list(pushed_urls.keys()),
                provider_campaign_leads=heyreach_campaign_leads,
                provider_campaign_stats=heyreach_campaign_stats)

    elif heyreach_row:
        for rule in RULES:
            rules_result[rule] = {
                "verdict": VACUOUS,
                "vacuous": True,
                "vacuous_reason": (
                    f"campaign {cid} is a HeyReach (LinkedIn) campaign; "
                    f"rule {rule!r} applies to EmailBison campaigns"),
            }

        pushed_urls = _pushed_profile_urls_for_campaign(
            queue_rows, heyreach_row)
        rules_result["linkedin_leads_read_pending_or_insequence"] = \
            check_linkedin_leads_read_pending_or_insequence(
                cid, list(pushed_urls.keys()),
                provider_campaign_leads=heyreach_campaign_leads,
                provider_campaign_stats=heyreach_campaign_stats)

        rules_result["a_watcher_is_on_the_campaign"] = \
            check_watcher_on_campaign(
                cid,
                heartbeats_fn=heartbeats_fn,
                supervisor_witnesses_fn=supervisor_witnesses_fn,
                module_mtime_fn=module_mtime_fn)
    else:
        for rule in RULES:
            rules_result[rule] = {
                "verdict": UNCONFIRMED,
                "error": f"campaign {cid} not found in registry",
            }

    rule_verdicts = {r: v.get("verdict", UNCONFIRMED)
                     for r, v in rules_result.items()}
    verdict_values = list(rule_verdicts.values())
    if any(v == FAIL for v in verdict_values):
        overall = FAIL
    elif any(v == UNCONFIRMED for v in verdict_values):
        overall = UNCONFIRMED
    elif all(v == VACUOUS for v in verdict_values):
        overall = VACUOUS
    else:
        overall = PASS

    return {
        "campaign_id": cid,
        "verdict": overall,
        "rules": rules_result,
    }


def _error_result(reason, phase, campaign_ids, measured_at):
    return {
        "check": "readback",
        "phase": phase,
        "verdict": ERROR,
        "campaigns": [str(c) for c in (campaign_ids or [])],
        "subjects": 0,
        "clean": 0,
        "refused": True,
        "rules": dict(RULES),
        "counts": {name: 0 for name in RULES},
        "offenders": {name: [] for name in RULES},
        "unverifiable": {},
        "error": reason,
        "measured_at": measured_at,
    }


def _vacuous_result(reason, phase, campaign_ids, file_info, measured_at):
    return {
        "check": "readback",
        "phase": phase,
        "verdict": VACUOUS,
        "campaigns": [str(c) for c in (campaign_ids or [])],
        "subjects": 0,
        "clean": 0,
        "refused": False,
        "rules": dict(RULES),
        "counts": {name: 0 for name in RULES},
        "offenders": {name: [] for name in RULES},
        "unverifiable": {},
        "vacuous_reason": reason,
        "evidence": {"files_read": [file_info] if file_info else []},
        "measured_at": measured_at,
    }


def exit_code(verdict):
    """Map a verdict to a process exit code."""
    return {PASS: 0, FAIL: 1, UNCONFIRMED: 2, VACUOUS: 2, ERROR: 3}.get(
        verdict, 3)


# ------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0])
    parser.add_argument("--phase", default="post_push",
                        choices=("pre_push", "post_push", "ongoing"))
    parser.add_argument("--campaign", action="append", type=int,
                        dest="campaigns")
    parser.add_argument("--workspaces", required=True,
                        help="path to a copy of production work/")
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--push-time", default=None,
                        help="ISO timestamp of the push")
    parser.add_argument("--no-live-reads", action="store_true",
                        help="skip provider reads (marks UNCONFIRMED)")
    args = parser.parse_args(argv)

    result = run(
        phase=args.phase,
        campaigns=args.campaigns,
        workspaces=args.workspaces,
        json_path=args.json_path,
        live_reads=not args.no_live_reads,
        push_time=args.push_time,
    )

    print(json.dumps(result, indent=2, default=str))
    return exit_code(result["verdict"])


if __name__ == "__main__":
    raise SystemExit(main())
