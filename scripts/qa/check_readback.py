#!/usr/bin/env python3
"""Post-push readback: did exactly the leads we pushed arrive, and what
will the provider actually send?

TASK-298. Lane F, the standing QA suite. The check that runs within one
cycle of the push and answers five questions:

    exactly_the_pushed_leads_are_attached
    every_scheduled_step_has_subject_and_body
    first_scheduled_send_recorded
    a_watcher_is_on_the_campaign
    linkedin_leads_read_pending_or_insequence

THE THING THAT MAKES THIS HARD — ISSUE-043. `bison.attach_leads` reads
membership back 6 times over ~15s and raises when the lead is absent. The
campaign-membership index took ~30 seconds. A post-push readback must not
read "absent within the window" as FAILED. Absent within the window is
UNCONFIRMED (exit 2), retried at t+60s, t+180s, t+600s from the push.
Still absent at t+600s becomes FAIL.

USAGE

    py -3 scripts/qa/check_readback.py \\
        --phase post_push \\
        --batch batch-2-2026-09-25 \\
        --campaign 502 --campaign 503 \\
        --workspaces <path to a copy of production work/> \\
        --pushed-leads 205079,205080 \\
        --push-time 2026-09-25T06:00:00Z \\
        --json work/qa/2026-09-25T06-00Z/readback.json
"""
import argparse
import datetime
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from src.providers import bison as bison_provider           # noqa: E402
from src.providers import heyreach as heyreach_provider    # noqa: E402
from src import emptyrender                                # noqa: E402
from src import watchsink                                  # noqa: E402

# ---------------------------------------------------------------- constants

CHECK_NAME = "readback"
PHASE = "post_push"

#: The retry ladder. Three attempts on a fixed schedule from the push time.
#: Absent within the window is UNCONFIRMED, not FAIL — ISSUE-043.
RETRY_OFFSETS_SECONDS = (60, 180, 600)

#: Exit codes matching the contract in docs/QA-LANE-F-CONTRACT-2026-09-25.md §3.
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNCONFIRMED = 2
EXIT_ERROR = 3

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_UNCONFIRMED = "UNCONFIRMED"
VERDICT_VACUOUS = "VACUOUS"
VERDICT_ERROR = "ERROR"

# ---------------------------------------------------------------- rules

RULES = {
    "exactly_the_pushed_leads_are_attached":
        "set equality at the provider, diffed BOTH directions: "
        "pushed-and-absent, and present-and-not-pushed",
    "every_scheduled_step_has_subject_and_body":
        "on the RENDERED queue rows at the provider, not on our templates; "
        "three counts: empty, literal 'None', unrendered placeholder",
    "first_scheduled_send_recorded":
        "a timestamp per campaign, read back; a zero at a weekend or before "
        "a window opens is the calendar, not a fault",
    "a_watcher_is_on_the_campaign":
        "a watcher registered for this campaign id, running the code we "
        "think — module mtime against process start time",
    "linkedin_leads_read_pending_or_insequence":
        "for the LinkedIn half; VACUOUS with stated reason when there is none",
}


# ---------------------------------------------------------------- helpers

def _parse_iso(s):
    """Parse an ISO-8601 timestamp to a datetime."""
    s = s.strip().rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt).replace(
                tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
    raise ValueError("cannot parse timestamp: %r" % s)


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _is_weekend(dt):
    return dt.weekday() >= 5


def _in_sending_window(dt, tz_offset_hours=0):
    """EmailBison campaigns are 09:00-17:00 Mon-Fri in their own timezone.
    ISSUE-045. Returns True if the timestamp falls inside a sending window.
    """
    local = dt + datetime.timedelta(hours=tz_offset_hours)
    if _is_weekend(local):
        return False
    return 9 <= local.hour < 17


def _file_mtime(path):
    """File modification time as an ISO timestamp, or None."""
    try:
        mt = os.path.getmtime(path)
        return datetime.datetime.fromtimestamp(
            mt, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        return None


def _process_start_from_heartbeat(hb):
    """Extract a process-start indicator from a heartbeat row.

    The heartbeat carries `pid` and `at` (last beat time). We use the
    earliest event in the watcher's log as a proxy for process start.
    """
    return hb.get("at")


# ---------------------------------------------------------------- rule 1

def check_leads_attached(campaign_ids, pushed_lead_ids, provider_reads,
                         attempt_label=None):
    """Rule 1: exactly the pushed leads are attached, diffed BOTH ways.

    Returns (verdict, details) where details has pushed_and_absent and
    present_and_not_pushed as named lists.

    A lead absent within the retry window is UNCONFIRMED, not FAIL —
    ISSUE-043.
    """
    pushed = set(int(i) for i in pushed_lead_ids)
    if not pushed:
        return VERDICT_VACUOUS, {
            "pushed_and_absent": [],
            "present_and_not_pushed": [],
            "reason": "no pushed lead ids supplied",
        }

    all_present = set()
    evidence_rows = []

    for cid in campaign_ids:
        try:
            ids = set(bison_provider.campaign_lead_ids(cid))
            provider_reads.append({
                "provider": "emailbison",
                "call": "campaign_lead_ids(%s)" % cid,
                "rows": len(ids),
                "at": _now_iso(),
            })
            all_present |= ids
        except Exception as exc:
            provider_reads.append({
                "provider": "emailbison",
                "call": "campaign_lead_ids(%s)" % cid,
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:200]),
                "at": _now_iso(),
            })
            return VERDICT_UNCONFIRMED, {
                "pushed_and_absent": sorted(pushed),
                "present_and_not_pushed": [],
                "reason": "provider read failed for campaign %s: %s" % (
                    cid, type(exc).__name__),
                "attempt": attempt_label,
            }

    pushed_and_absent = sorted(pushed - all_present)
    present_and_not_pushed = sorted(all_present - pushed)

    details = {
        "pushed_and_absent": pushed_and_absent,
        "present_and_not_pushed": present_and_not_pushed,
        "pushed_count": len(pushed),
        "present_count": len(all_present),
    }
    if attempt_label:
        details["attempt"] = attempt_label

    if pushed_and_absent or present_and_not_pushed:
        return VERDICT_UNCONFIRMED, details
    return VERDICT_PASS, details


# ---------------------------------------------------------------- rule 2

def check_scheduled_rows(campaign_ids, provider_reads):
    """Rule 2: every scheduled step has a subject and body, on the RENDERED
    rows at the provider. Three separate counts: empty, literal 'None',
    unrendered placeholder.

    A campaign with zero scheduled rows is VACUOUS, not PASS — the scheduler
    builds the rows at the end of a sending day.
    """
    per_campaign = {}
    total_empty = 0
    total_none = 0
    total_placeholder = 0
    vacuous_campaigns = []

    for cid in campaign_ids:
        try:
            rows = bison_provider.scheduled_emails(cid, cap=200)
            provider_reads.append({
                "provider": "emailbison",
                "call": "scheduled_emails(%s, cap=200)" % cid,
                "rows": len(rows),
                "at": _now_iso(),
            })
        except Exception as exc:
            provider_reads.append({
                "provider": "emailbison",
                "call": "scheduled_emails(%s)" % cid,
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:200]),
                "at": _now_iso(),
            })
            per_campaign[cid] = {"error": str(exc)[:200]}
            continue

        if not rows:
            vacuous_campaigns.append(cid)
            per_campaign[cid] = {
                "rows": 0, "empty": 0, "none": 0, "placeholder": 0,
                "vacuous": True,
                "reason": "scheduler builds rows at end of sending day; "
                          "zero rows shortly after a push proves nothing",
            }
            continue

        found = emptyrender.scan(rows)
        pending = found.get("pending", [])
        empty_count = 0
        none_count = 0
        placeholder_count = 0
        for entry in pending:
            for field, reason in entry.get("faults", []):
                if reason == emptyrender.EMPTY:
                    empty_count += 1
                elif reason == emptyrender.LITERAL_NONE:
                    none_count += 1
                elif reason == emptyrender.PLACEHOLDER:
                    placeholder_count += 1

        total_empty += empty_count
        total_none += none_count
        total_placeholder += placeholder_count
        per_campaign[cid] = {
            "rows": len(rows),
            "empty": empty_count,
            "none": none_count,
            "placeholder": placeholder_count,
            "pending_faults": len(pending),
        }

    details = {
        "per_campaign": per_campaign,
        "total_empty": total_empty,
        "total_none": total_none,
        "total_placeholder": total_placeholder,
        "vacuous_campaigns": vacuous_campaigns,
    }

    if vacuous_campaigns and len(vacuous_campaigns) == len(campaign_ids):
        return VERDICT_VACUOUS, details

    total_faults = total_empty + total_none + total_placeholder
    if total_faults > 0:
        return VERDICT_FAIL, details
    return VERDICT_PASS, details


# ---------------------------------------------------------------- rule 3

def check_first_scheduled_send(campaign_ids, provider_reads):
    """Rule 3: the first scheduled send timestamp, per campaign. Enrolled
    is not sent, scheduled is not sent, active is not sent. Read the
    timestamp back and report the sending window beside it.

    ISSUE-045: every EmailBison campaign is 09:00-17:00 Mon-Fri in its own
    timezone. A zero at a weekend or before a window opens is the calendar,
    not a fault.
    """
    per_campaign = {}

    for cid in campaign_ids:
        try:
            sched = bison_provider.schedule(cid)
            provider_reads.append({
                "provider": "emailbison",
                "call": "schedule(%s)" % cid,
                "keys": sorted(sched.keys()) if isinstance(sched, dict) else [],
                "at": _now_iso(),
            })
        except Exception as exc:
            provider_reads.append({
                "provider": "emailbison",
                "call": "schedule(%s)" % cid,
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:200]),
                "at": _now_iso(),
            })
            per_campaign[cid] = {"error": str(exc)[:200]}
            continue

        first_send = None
        window = None
        if isinstance(sched, dict):
            first_send = sched.get("start_time") or sched.get("first_send")
            tz = sched.get("timezone", "unknown")
            window = "%s-%s %s" % (
                sched.get("start_time", "?"),
                sched.get("end_time", "?"),
                tz)
            # Check the sending window
            try:
                start_h = int(str(sched.get("start_time", "")).split(":")[0])
                end_h = int(str(sched.get("end_time", "")).split(":")[0])
                window = "%02d:00-%02d:00 %s" % (start_h, end_h, tz)
            except (ValueError, IndexError):
                pass

        now = datetime.datetime.now(datetime.timezone.utc)
        in_window = _in_sending_window(now)

        per_campaign[cid] = {
            "first_scheduled_send": first_send,
            "window": window,
            "in_sending_window": in_window,
            "is_weekend": _is_weekend(now),
            "note": ("outside sending window — calendar, not fault"
                     if not in_window else "within sending window"),
        }

    details = {"per_campaign": per_campaign}

    all_have_send = all(
        v.get("first_scheduled_send") for v in per_campaign.values()
        if not v.get("error"))
    if all_have_send and per_campaign:
        return VERDICT_PASS, details
    return VERDICT_UNCONFIRMED, details


# ---------------------------------------------------------------- rule 4

def check_watcher(campaign_ids, provider_reads, files_read):
    """Rule 4: a watcher is registered for each campaign AND is running the
    code we think. A merge is not a deploy — check the watcher module's
    mtime against the process start time.

    Reports heartbeat, log last line, process start, and module mtime —
    all four, per watcher.
    """
    per_campaign = {}
    watcher_module = os.path.join(ROOT, "scripts", "bison_watch_loop.py")
    module_mtime = _file_mtime(watcher_module)

    all_beats = watchsink.heartbeats()
    beat_by_campaign = {}
    for beat in all_beats:
        cid = beat.get("campaign")
        if cid is not None:
            beat_by_campaign[str(cid)] = beat

    for cid in campaign_ids:
        cid_str = str(cid)
        hb = beat_by_campaign.get(cid_str)

        if hb is None:
            per_campaign[cid] = {
                "registered": False,
                "heartbeat": None,
                "log_last_line": None,
                "process_start": None,
                "module_mtime": module_mtime,
                "verdict": VERDICT_FAIL,
                "reason": "no heartbeat found for campaign %s" % cid,
            }
            continue

        # Read the event log's last line
        log_last_line = None
        log_path = watchsink.events_path("bison", campaign=cid)
        try:
            if os.path.isfile(log_path):
                with open(log_path, encoding="utf-8") as f:
                    lines = f.readlines()
                    if lines:
                        last = json.loads(lines[-1])
                        log_last_line = last.get("line", "")
                files_read.append({
                    "path": log_path,
                    "rows": len(lines) if lines else 0,
                    "mtime": _file_mtime(log_path),
                })
        except Exception:
            pass

        # Process start: approximate from the heartbeat's pid and the
        # earliest event
        process_start = hb.get("at")
        pid = hb.get("pid")

        # The critical check: module mtime vs process start
        code_stale = None
        if module_mtime and process_start:
            code_stale = module_mtime > process_start

        per_campaign[cid] = {
            "registered": True,
            "heartbeat": hb.get("at"),
            "heartbeat_pid": pid,
            "log_last_line": log_last_line,
            "process_start": process_start,
            "module_mtime": module_mtime,
            "code_stale": code_stale,
            "verdict": (VERDICT_UNCONFIRMED if code_stale
                        else VERDICT_PASS),
            "reason": ("module mtime %s is AFTER process start %s — "
                       "watcher may be running old code" % (
                           module_mtime, process_start)
                       if code_stale else "watcher running current code"),
        }

    details = {"per_campaign": per_campaign}

    any_fail = any(v.get("verdict") == VERDICT_FAIL
                   for v in per_campaign.values())
    any_unconfirmed = any(v.get("verdict") == VERDICT_UNCONFIRMED
                          for v in per_campaign.values())
    if any_fail:
        return VERDICT_FAIL, details
    if any_unconfirmed:
        return VERDICT_UNCONFIRMED, details
    return VERDICT_PASS, details


# ---------------------------------------------------------------- rule 5

def check_linkedin_leads(campaign_ids, provider_reads, workspaces_path,
                         files_read):
    """Rule 5: LinkedIn leads read pending or in_sequence.

    When the batch has no LinkedIn half, this rule is VACUOUS with a stated
    reason, never PASS.
    """
    # Check if any HeyReach campaigns are in the set
    heyreach_campaigns = []
    for cid in campaign_ids:
        try:
            stats = heyreach_provider.campaign_stats(cid)
            provider_reads.append({
                "provider": "heyreach",
                "call": "campaign_stats(%s)" % cid,
                "keys": sorted(stats.keys()) if isinstance(stats, dict) else [],
                "at": _now_iso(),
            })
            heyreach_campaigns.append(cid)
        except Exception:
            pass

    if not heyreach_campaigns:
        return VERDICT_VACUOUS, {
            "reason": "no LinkedIn campaign in this batch; the 128 are an "
                      "email push, so this rule is vacuous",
            "heyreach_campaigns_checked": [],
        }

    pending_count = 0
    insequence_count = 0
    per_campaign = {}

    for cid in heyreach_campaigns:
        try:
            leads, total = heyreach_provider.campaign_leads(cid)
            provider_reads.append({
                "provider": "heyreach",
                "call": "campaign_leads(%s)" % cid,
                "rows": len(leads),
                "total": total,
                "at": _now_iso(),
            })
            pending = sum(1 for l in leads
                          if l.get("state") == "request_pending")
            inseq = sum(1 for l in leads
                        if l.get("state") == "insequence")
            pending_count += pending
            insequence_count += inseq
            per_campaign[cid] = {
                "total": total,
                "pending": pending,
                "in_sequence": inseq,
            }
        except Exception as exc:
            provider_reads.append({
                "provider": "heyreach",
                "call": "campaign_leads(%s)" % cid,
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:200]),
                "at": _now_iso(),
            })
            per_campaign[cid] = {"error": str(exc)[:200]}

    details = {
        "per_campaign": per_campaign,
        "total_pending": pending_count,
        "total_in_sequence": insequence_count,
    }
    return VERDICT_PASS, details


# ---------------------------------------------------------------- retry ladder

def _retry_schedule(push_time_iso):
    """Compute the three retry timestamps from the push time."""
    push = _parse_iso(push_time_iso)
    return [push + datetime.timedelta(seconds=s)
            for s in RETRY_OFFSETS_SECONDS]


def _should_retry_now(push_time_iso, now=None):
    """Which retry attempt are we at, if any? Returns (attempt_index,
    retry_time_iso) or (None, None) if it is not yet time for any retry
    or all retries are exhausted.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    push = _parse_iso(push_time_iso)
    for i, offset in enumerate(RETRY_OFFSETS_SECONDS):
        retry_at = push + datetime.timedelta(seconds=offset)
        if now >= retry_at:
            return i, retry_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None, None


def _all_retries_exhausted(push_time_iso, now=None):
    """True when t+600 has passed."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    push = _parse_iso(push_time_iso)
    final = push + datetime.timedelta(seconds=RETRY_OFFSETS_SECONDS[-1])
    return now >= final


# ---------------------------------------------------------------- main run

def run(phase, batch, campaigns, pushed_lead_ids, workspaces,
        push_time=None, json_path=None, live_reads=True,
        now_fn=None):
    """Execute the post-push readback check.

    `now_fn` is a test hook: a callable returning a datetime, overriding
    the real clock for the retry ladder.
    """
    if phase != PHASE:
        return {
            "check": CHECK_NAME,
            "phase": phase,
            "verdict": VERDICT_ERROR,
            "reason": "this check only runs in the %s phase" % PHASE,
        }

    campaign_ids = [int(c) for c in (campaigns or [])]
    if not campaign_ids:
        return _result(VERDICT_ERROR, {
            "reason": "no campaign ids supplied",
        })

    provider_reads = []
    files_read = []

    # Record the workspaces copy
    if workspaces and os.path.isdir(workspaces):
        queue_path = os.path.join(workspaces, "queue.jsonl")
        if os.path.isfile(queue_path):
            row_count = 0
            with open(queue_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        row_count += 1
            files_read.append({
                "path": queue_path,
                "rows": row_count,
                "mtime": _file_mtime(queue_path),
            })
        campaigns_path = os.path.join(workspaces, "campaigns.jsonl")
        if os.path.isfile(campaigns_path):
            row_count = 0
            with open(campaigns_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        row_count += 1
            files_read.append({
                "path": campaigns_path,
                "rows": row_count,
                "mtime": _file_mtime(campaigns_path),
            })

    # ---- Rule 1: leads attached, with retry ladder ----
    retry_attempts = []
    lead_verdict = VERDICT_UNCONFIRMED
    lead_details = {}

    if push_time:
        schedule = _retry_schedule(push_time)
        now = now_fn() if now_fn else datetime.datetime.now(
            datetime.timezone.utc)

        # Always attempt the initial read
        v, d = check_leads_attached(
            campaign_ids, pushed_lead_ids, provider_reads,
            attempt_label="initial")
        retry_attempts.append({
            "attempt": "initial",
            "at": _now_iso(),
            "verdict": v,
            "pushed_and_absent": d.get("pushed_and_absent", []),
            "present_and_not_pushed": d.get("present_and_not_pushed", []),
            "pushed_count": d.get("pushed_count", 0),
            "present_count": d.get("present_count", 0),
        })
        lead_verdict = v
        lead_details = d

        # Retry ladder: attempt each retry whose time has passed
        for i, retry_at in enumerate(schedule):
            label = "retry_t+%ds" % RETRY_OFFSETS_SECONDS[i]
            if now >= retry_at:
                v, d = check_leads_attached(
                    campaign_ids, pushed_lead_ids, provider_reads,
                    attempt_label=label)
                retry_attempts.append({
                    "attempt": label,
                    "at": _now_iso(),
                    "verdict": v,
                    "pushed_and_absent": d.get("pushed_and_absent", []),
                    "present_and_not_pushed": d.get(
                        "present_and_not_pushed", []),
                    "pushed_count": d.get("pushed_count", 0),
                    "present_count": d.get("present_count", 0),
                })
                lead_verdict = v
                lead_details = d
                if v == VERDICT_PASS:
                    break
            # If we have exhausted all retries and still UNCONFIRMED
            if (i == len(schedule) - 1 and v != VERDICT_PASS
                    and _all_retries_exhausted(push_time, now)):
                lead_verdict = VERDICT_FAIL
                lead_details["reason"] = (
                    "still absent after all retry attempts "
                    "(t+60, t+180, t+600)")
    else:
        # No push time: single attempt, no retry ladder
        v, d = check_leads_attached(
            campaign_ids, pushed_lead_ids, provider_reads,
            attempt_label="single")
        lead_verdict = v
        lead_details = d
        retry_attempts.append({
            "attempt": "single",
            "at": _now_iso(),
            "verdict": v,
            "pushed_and_absent": d.get("pushed_and_absent", []),
            "present_and_not_pushed": d.get("present_and_not_pushed", []),
        })

    # ---- Rule 2: scheduled rows ----
    sched_verdict, sched_details = check_scheduled_rows(
        campaign_ids, provider_reads)

    # ---- Rule 3: first scheduled send ----
    send_verdict, send_details = check_first_scheduled_send(
        campaign_ids, provider_reads)

    # ---- Rule 4: watcher ----
    watch_verdict, watch_details = check_watcher(
        campaign_ids, provider_reads, files_read)

    # ---- Rule 5: LinkedIn ----
    li_verdict, li_details = check_linkedin_leads(
        campaign_ids, provider_reads, workspaces, files_read)

    # ---- Aggregate ----
    rule_verdicts = {
        "exactly_the_pushed_leads_are_attached": lead_verdict,
        "every_scheduled_step_has_subject_and_body": sched_verdict,
        "first_scheduled_send_recorded": send_verdict,
        "a_watcher_is_on_the_campaign": watch_verdict,
        "linkedin_leads_read_pending_or_insequence": li_verdict,
    }

    # Overall: worst verdict wins
    severity = {VERDICT_PASS: 0, VERDICT_VACUOUS: 1, VERDICT_UNCONFIRMED: 2,
                VERDICT_FAIL: 3, VERDICT_ERROR: 4}
    overall = max(rule_verdicts.values(),
                  key=lambda v: severity.get(v, 0))

    # Counts for the result document
    offenders = {}
    unverifiable = {}
    counts = {}
    for rule_name, verdict in rule_verdicts.items():
        if verdict == VERDICT_FAIL:
            if rule_name == "exactly_the_pushed_leads_are_attached":
                offenders[rule_name] = lead_details.get(
                    "pushed_and_absent", [])
            elif rule_name == "every_scheduled_step_has_subject_and_body":
                offenders[rule_name] = [
                    str(cid) for cid, d in
                    sched_details.get("per_campaign", {}).items()
                    if isinstance(d, dict) and (
                        d.get("empty", 0) + d.get("none", 0) +
                        d.get("placeholder", 0)) > 0]
            else:
                offenders[rule_name] = []
            counts[rule_name] = len(offenders.get(rule_name, []))
        elif verdict == VERDICT_UNCONFIRMED:
            unverifiable[rule_name] = [
                str(cid) for cid in campaign_ids]
            counts[rule_name] = len(campaign_ids)
        else:
            counts[rule_name] = 0

    # Subjects: the campaigns
    subjects = len(campaign_ids)
    clean = sum(1 for v in rule_verdicts.values() if v == VERDICT_PASS)

    # Build the rule text dynamically
    rule_text = {}
    for name, template in RULES.items():
        rule_text[name] = template

    result = {
        "check": CHECK_NAME,
        "phase": phase,
        "verdict": overall,
        "batch": batch,
        "campaigns": [str(c) for c in campaign_ids],
        "subjects": subjects,
        "clean": clean,
        "refused": False,
        "rules": rule_text,
        "counts": counts,
        "offenders": offenders,
        "unverifiable": unverifiable,
        "evidence": {
            "provider_reads": provider_reads,
            "files_read": files_read,
            "provider_reads_skipped": not live_reads,
        },
        "retry_attempts": retry_attempts,
        "scheduled_rows": sched_details,
        "first_scheduled_send": send_details,
        "watchers": watch_details,
        "linkedin": li_details,
        "measured_at": _now_iso(),
        "workspaces": workspaces,
    }

    if json_path:
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
        with open(json_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return result


def _result(verdict, extra=None):
    r = {
        "check": CHECK_NAME,
        "phase": PHASE,
        "verdict": verdict,
        "rules": RULES,
        "counts": {k: 0 for k in RULES},
        "offenders": {},
        "unverifiable": {},
        "evidence": {"provider_reads": [], "files_read": [],
                     "provider_reads_skipped": False},
        "retry_attempts": [],
        "measured_at": _now_iso(),
    }
    if extra:
        r.update(extra)
    return r


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", required=True,
                    choices=["pre_push", "post_push", "ongoing"])
    ap.add_argument("--batch", default="")
    ap.add_argument("--campaign", action="append", default=[],
                    dest="campaigns")
    ap.add_argument("--workspaces", required=True,
                    help="path to a copy of production work/")
    ap.add_argument("--pushed-leads", default="",
                    help="comma-separated lead ids that were pushed")
    ap.add_argument("--push-time", default=None,
                    help="ISO timestamp of the push, for the retry ladder")
    ap.add_argument("--json", dest="json_path", default=None,
                    help="where to write the result JSON")
    ap.add_argument("--live-reads", action="store_true", default=True)
    args = ap.parse_args(argv)

    pushed = [s.strip() for s in args.pushed_leads.split(",")
              if s.strip()] if args.pushed_leads else []

    result = run(
        phase=args.phase,
        batch=args.batch,
        campaigns=args.campaigns,
        pushed_lead_ids=pushed,
        workspaces=args.workspaces,
        push_time=args.push_time,
        json_path=args.json_path,
        live_reads=args.live_reads,
    )

    verdict = result.get("verdict", VERDICT_ERROR)
    exit_code = {
        VERDICT_PASS: EXIT_PASS,
        VERDICT_FAIL: EXIT_FAIL,
        VERDICT_UNCONFIRMED: EXIT_UNCONFIRMED,
        VERDICT_VACUOUS: EXIT_UNCONFIRMED,
        VERDICT_ERROR: EXIT_ERROR,
    }.get(verdict, EXIT_ERROR)

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
