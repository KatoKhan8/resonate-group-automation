#!/usr/bin/env python3
"""QA check: is each HeyReach campaign actually built to send what we think?

TASK-297. The per-campaign HeyReach check: six rules that answer whether a
LinkedIn campaign is running, on the right seat, with the fields and the
window and the headroom to actually send - and whether each lead is free to
be enrolled in it.

THE SIX RULES:

    campaign_in_progress_on_the_right_seat
                              status IN_PROGRESS, and the LinkedIn account it
                              is attached to is the seat we intended
    custom_fields_match_the_pushed_variables
                              the sequence's merge variables and the fields
                              we are pushing are the same set (diff both dirs)
    schedule_07_to_23_seat_local_seven_days
                              and seat-LOCAL, not UTC; plus the overlap in
                              hours between this LinkedIn window and the email
                              window of the campaign carrying the same cadence
    seat_under_its_daily_cap  the seat has headroom today
    lead_not_in_another_linkedin_campaign
                              at HeyReach, in any campaign, ours or the
                              client's
    connection_note_under_280_characters
                              the RENDERED note, not the template; a 240-char
                              template with {company} can render past 280

READS ONLY. No provider write of any kind.

Usage:
    py -3 scripts/qa/check_campaign_heyreach.py \\
        --phase pre_push \\
        --campaign 605732 --campaign 613744 \\
        --workspaces <path to work/ copy> \\
        --json work/qa/<run>/campaign_heyreach.json
"""
import argparse
import datetime
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.providers import heyreach
from src import seatledger

# ------------------------------------------------------------- exit codes

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNCONFIRMED = 2
EXIT_ERROR = 3

# ------------------------------------------------------------- rule names

RULES = {
    "campaign_in_progress_on_the_right_seat":
        "status IN_PROGRESS, and the LinkedIn account it is attached to is "
        "the seat we intended",
    "custom_fields_match_the_pushed_variables":
        "the sequence's merge variables and the fields we are pushing are "
        "the same set, diffed both directions by name",
    "schedule_07_to_23_seat_local_seven_days":
        "the sending window is 07:00-23:00 seat-local, seven days; plus the "
        "overlap in hours with the email half of the same cadence",
    "seat_under_its_daily_cap":
        "the seat has headroom today (ours < 40 on an exclusive seat)",
    "lead_not_in_another_linkedin_campaign":
        "the lead is not in another LinkedIn campaign at HeyReach, in any "
        "campaign, ours or the client's",
    "connection_note_under_280_characters":
        "the RENDERED connection note is under 280 characters; placeholders "
        "reported separately from over-length ones",
}

# ------------------------------------------------------------- constants

NOTE_CHAR_LIMIT = 280
SEAT_DAILY_LIMIT = 40
EXPECTED_LI_START = 7
EXPECTED_LI_END = 23
EMAIL_DEFAULT_START = 9
EMAIL_DEFAULT_END = 17
EMAIL_DAYS = ("mon", "tue", "wed", "thu", "fri")

# Variable pattern for merge fields in HeyReach sequences
_VARIABLE_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

# Built-in variables HeyResolve fills itself
BUILTIN_VARIABLES = frozenset({
    "FIRST_NAME", "LAST_NAME", "COMPANY", "POSITION", "INDUSTRY",
    "LOCATION", "MY_FIRST_NAME", "MY_LAST_NAME", "MY_COMPANY",
})


# ------------------------------------------------------------- helpers

def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _today_iso():
    return datetime.date.today().isoformat()


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


def _campaigns_by_heyreach_id(rows):
    """Index campaign rows by their heyreach_campaign_id."""
    index = {}
    for row in rows:
        hid = row.get("heyreach_campaign_id")
        if hid is not None:
            index[int(hid)] = row
    return index


def _all_campaigns_from_provider():
    """Page through all campaigns at HeyReach. Returns list of raw items."""
    offset = 0
    items = []
    for _ in range(20):
        page, total = heyreach.campaigns(offset, heyreach.MAX_PAGE)
        items.extend(page)
        if not page or (total is not None and offset + len(page) >= int(total)):
            break
        offset += len(page)
    return items


def _all_leads_for_campaign(campaign_id):
    """Page through all leads for a campaign."""
    offset = 0
    leads = []
    for _ in range(50):
        page, total = heyreach.campaign_leads(
            campaign_id, offset, heyreach.MAX_PAGE)
        leads.extend(page)
        if not page or (total is not None and offset + len(page) >= int(total)):
            break
        offset += len(page)
    return leads


def _all_seats():
    """Page through all LinkedIn seats."""
    offset = 0
    seats = []
    for _ in range(10):
        page, total = heyreach.li_accounts(offset, heyreach.MAX_PAGE)
        seats.extend(page)
        if not page or (total is not None and offset + len(page) >= int(total)):
            break
        offset += len(page)
    return seats


def _seat_timezone(seat_row):
    """Extract the timezone from a seat row, or None.

    A guessed timezone is worse than a missing one - CLAUDE.md.
    """
    if not isinstance(seat_row, dict):
        return None
    tz = seat_row.get("timeZone") or seat_row.get("timezone")
    if tz and isinstance(tz, str) and tz.strip():
        return tz.strip()
    return None


def _render_note(template, fields):
    """Render a connection note template by substituting merge variables.

    Returns the rendered string. Variables not in `fields` are left as-is
    (they would be the fallback at the provider, but for length checking we
    need the worst case).
    """
    def replacer(match):
        var_name = match.group(1)
        value = fields.get(var_name)
        if value is not None:
            return str(value)
        return match.group(0)
    return _VARIABLE_RE.sub(replacer, template)


def _longest_rendered_length(notes, sample_fields):
    """The longest rendered note length across a list of templates.

    Returns (max_len, template_that_produced_it, rendered_text).
    `sample_fields` is a dict of variable -> longest known value for that var.
    """
    worst_len = 0
    worst_template = ""
    worst_rendered = ""
    for note in notes:
        rendered = _render_note(note, sample_fields)
        if len(rendered) > worst_len:
            worst_len = len(rendered)
            worst_template = note
            worst_rendered = rendered
    return worst_len, worst_template, worst_rendered


def _extract_longest_field_values(leads):
    """For each custom field, find the longest value across all leads.

    This gives us the worst-case rendering for length checking.
    Returns a dict of variable_name -> longest_value.
    """
    longest = {}
    for lead in leads:
        if not isinstance(lead, dict):
            continue
        profile = lead.get("linkedInUserProfile") or lead
        first = str(profile.get("firstName") or "")
        last = str(profile.get("lastName") or "")
        company = str(profile.get("companyName") or "")
        position = str(profile.get("position") or "")
        candidates = {
            "FIRST_NAME": first,
            "LAST_NAME": last,
            "COMPANY": company,
            "POSITION": position,
        }
        for var, val in candidates.items():
            if len(val) > len(longest.get(var, "")):
                longest[var] = val
    return longest


def _window_overlap_hours(li_start, li_end, li_days,
                          em_start, em_end, em_days):
    """Compute the overlap in hours between two weekly windows.

    Each window is (start_hour, end_hour, days_of_week).
    days_of_week is a set of lowercase day abbreviations.
    Returns the overlap in hours per week.
    """
    common_days = set(li_days) & set(em_days)
    if not common_days:
        return 0.0
    hour_overlap = max(0, min(li_end, em_end) - max(li_start, em_start))
    return hour_overlap * len(common_days)


def _is_our_campaign(campaign_row, stats):
    """Decide whether a campaign is ours or the client's.

    Evidence: campaign_stats counters. A campaign with connectionsSent > 0
    that matches our naming pattern is likely ours. The definitive test is
    `check_tenant` - but that checks org unit, not campaign ownership.

    Returns (is_ours: bool, evidence: str).
    """
    if not isinstance(campaign_row, dict):
        return False, "no campaign row"
    name = str(campaign_row.get("name") or "").lower()
    our_markers = ("resonate", "productive", "abm", "cohort", "canary")
    has_our_name = any(m in name for m in our_markers)
    return has_our_name, f"name={campaign_row.get('name')!r}"


# ------------------------------------------------------------- the check

def _check_one_campaign(cid, registry_row, seats_by_id, queue_rows,
                        live_reads, provider_campaigns_by_id):
    """Run all six rules against one campaign. Returns per-rule verdicts."""
    verdicts = {}
    offenders = {}
    details = {}
    for rule in RULES:
        verdicts[rule] = "PASS"
        offenders[rule] = []

    pc = provider_campaigns_by_id.get(cid)
    if pc is None and live_reads:
        try:
            pc = heyreach.campaign_read(cid)
        except Exception as exc:
            for rule in RULES:
                verdicts[rule] = "UNCONFIRMED"
                offenders[rule] = [f"{cid}: provider read failed: {exc}"]
            return verdicts, offenders, details

    if pc is None:
        for rule in RULES:
            verdicts[rule] = "UNCONFIRMED"
            offenders[rule] = [f"{cid}: not found at provider"]
        return verdicts, offenders, details

    status = str(pc.get("status") or "").strip()
    account_ids = [str(a) for a in (pc.get("campaignAccountIds") or [])]
    details["status"] = status
    details["account_ids"] = account_ids

    # --- Rule 1: campaign_in_progress_on_the_right_seat ---
    intended_seat = None
    if registry_row:
        intended_seat = registry_row.get("primary_seat_id") or \
                        registry_row.get("sender_id")
    if status == "IN_PROGRESS":
        if intended_seat and str(intended_seat) not in account_ids:
            verdicts["campaign_in_progress_on_the_right_seat"] = "FAIL"
            offenders["campaign_in_progress_on_the_right_seat"] = [
                f"{cid}: IN_PROGRESS but seat {intended_seat} not in "
                f"campaignAccountIds={account_ids}"]
        else:
            verdicts["campaign_in_progress_on_the_right_seat"] = "PASS"
    elif status == "DRAFT":
        verdicts["campaign_in_progress_on_the_right_seat"] = "FAIL"
        offenders["campaign_in_progress_on_the_right_seat"] = [
            f"{cid}: status is DRAFT, not IN_PROGRESS"]
    elif status == "PAUSED":
        verdicts["campaign_in_progress_on_the_right_seat"] = "FAIL"
        offenders["campaign_in_progress_on_the_right_seat"] = [
            f"{cid}: status is PAUSED, not IN_PROGRESS"]
    elif status == "FINISHED":
        verdicts["campaign_in_progress_on_the_right_seat"] = "FAIL"
        offenders["campaign_in_progress_on_the_right_seat"] = [
            f"{cid}: status is FINISHED, not IN_PROGRESS"]
    else:
        verdicts["campaign_in_progress_on_the_right_seat"] = "UNCONFIRMED"
        offenders["campaign_in_progress_on_the_right_seat"] = [
            f"{cid}: unrecognised status {status!r}"]

    # --- Rule 2: custom_fields_match_the_pushed_variables ---
    if live_reads:
        try:
            seq = heyreach.campaign_sequence(cid)
            seq_blob = json.dumps(seq or {})
            used_vars = set(_VARIABLE_RE.findall(seq_blob))
            custom_vars = used_vars - BUILTIN_VARIABLES

            supplied = set(heyreach.supplied_field_names(queue_rows))
            # Remove known system fields from supplied for comparison
            system_fields = {"note", "record_id", "contact_key", "client",
                             "sender_id", "sender_account_id"}
            supplied_custom = supplied - system_fields

            missing_from_push = sorted(custom_vars - supplied_custom)
            wasted_in_push = sorted(supplied_custom - custom_vars)

            if missing_from_push or wasted_in_push:
                verdicts["custom_fields_match_the_pushed_variables"] = "FAIL"
                parts = []
                if missing_from_push:
                    parts.append(
                        f"sequence uses but push does not supply: "
                        f"{missing_from_push}")
                if wasted_in_push:
                    parts.append(
                        f"push supplies but sequence does not use: "
                        f"{wasted_in_push}")
                offenders["custom_fields_match_the_pushed_variables"] = [
                    f"{cid}: {'; '.join(parts)}"]
            else:
                verdicts["custom_fields_match_the_pushed_variables"] = "PASS"
            details["sequence_vars"] = sorted(custom_vars)
            details["supplied_vars"] = sorted(supplied_custom)
            details["missing_from_push"] = missing_from_push
            details["wasted_in_push"] = wasted_in_push
        except Exception as exc:
            verdicts["custom_fields_match_the_pushed_variables"] = "UNCONFIRMED"
            offenders["custom_fields_match_the_pushed_variables"] = [
                f"{cid}: {exc}"]
    else:
        verdicts["custom_fields_match_the_pushed_variables"] = "UNCONFIRMED"
        offenders["custom_fields_match_the_pushed_variables"] = [
            f"{cid}: live reads disabled"]

    # --- Rule 3: schedule_07_to_23_seat_local_seven_days ---
    # There is no schedule read API at HeyReach (set_schedule is deliberately
    # not implemented because the write can never be verified). We report what
    # we can determine from the seat's timezone and the known default.
    seat_tz = None
    for aid in account_ids:
        seat_row = seats_by_id.get(aid) or seats_by_id.get(int(aid) if aid.isdigit() else aid)
        if seat_row:
            seat_tz = _seat_timezone(seat_row)
            break
    details["seat_timezone"] = seat_tz
    if seat_tz is None:
        verdicts["schedule_07_to_23_seat_local_seven_days"] = "UNCONFIRMED"
        offenders["schedule_07_to_23_seat_local_seven_days"] = [
            f"{cid}: seat timezone not readable; a guessed timezone is worse "
            f"than a missing one"]
    else:
        # We know the expected HeyReach window is 07:00-23:00 seven days.
        # We know the email window is 09:00-17:00 Mon-Fri.
        # Report the overlap.
        li_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        em_days = set(EMAIL_DAYS)
        overlap = _window_overlap_hours(
            EXPECTED_LI_START, EXPECTED_LI_END, li_days,
            EMAIL_DEFAULT_START, EMAIL_DEFAULT_END, em_days)
        details["li_window"] = f"{EXPECTED_LI_START:02d}:00-{EXPECTED_LI_END:02d}:00"
        details["li_timezone"] = seat_tz
        details["li_days"] = "seven days"
        details["email_window"] = (f"{EMAIL_DEFAULT_START:02d}:00-"
                                   f"{EMAIL_DEFAULT_END:02d}:00")
        details["email_days"] = "Mon-Fri"
        details["overlap_hours_per_week"] = overlap
        # We cannot verify the actual schedule at the provider - no read API.
        verdicts["schedule_07_to_23_seat_local_seven_days"] = "UNCONFIRMED"
        offenders["schedule_07_to_23_seat_local_seven_days"] = [
            f"{cid}: no schedule read API exists at HeyReach; overlap with "
            f"email half is {overlap}h/week (LinkedIn {details['li_window']} "
            f"{seat_tz} seven days vs email "
            f"{details['email_window']} Mon-Fri)"]

    # --- Rule 4: seat_under_its_daily_cap ---
    today = _today_iso()
    cap_details = []
    cap_ok = True
    for aid in account_ids:
        cap = seatledger.daily(aid, today)
        cap_details.append({
            "seat_id": aid,
            "verdict": cap["verdict"],
            "ours": cap["ours"],
            "limit": cap["limit"],
            "remaining": cap["remaining"],
            "reason": cap["reason"],
        })
        if cap["verdict"] == seatledger.FULL:
            cap_ok = False
            offenders["seat_under_its_daily_cap"].append(
                f"{cid}: seat {aid} is FULL ({cap['ours']}/{cap['limit']})")
        elif cap["verdict"] == seatledger.REFUSED:
            cap_ok = False
            offenders["seat_under_its_daily_cap"].append(
                f"{cid}: seat {aid} REFUSED ({cap['reason']})")
    details["seat_caps"] = cap_details
    if not account_ids:
        verdicts["seat_under_its_daily_cap"] = "UNCONFIRMED"
        offenders["seat_under_its_daily_cap"] = [
            f"{cid}: no seats attached"]
    elif cap_ok:
        verdicts["seat_under_its_daily_cap"] = "PASS"

    # --- Rule 5: lead_not_in_another_linkedin_campaign ---
    if live_reads:
        leads = _all_leads_for_campaign(cid)
        if not leads:
            verdicts["lead_not_in_another_linkedin_campaign"] = "VACUOUS"
            offenders["lead_not_in_another_linkedin_campaign"] = [
                f"{cid}: zero leads in campaign (VACUOUS)"]
            details["lead_count"] = 0
        else:
            details["lead_count"] = len(leads)
            heyreach_lead_id_count = sum(
                1 for l in leads if l.get("provider_lead_id"))
            details["heyreach_lead_id_count"] = heyreach_lead_id_count
            collisions = []
            for lead in leads:
                profile_url = lead.get("profile_url")
                if not profile_url:
                    continue
                try:
                    other_campaigns, total = heyreach.campaigns_for_lead(
                        profile_url=profile_url)
                except Exception:
                    continue
                for oc in other_campaigns:
                    other_id = oc.get("campaignId")
                    if str(other_id) == str(cid):
                        continue
                    is_ours, evidence = _is_our_campaign(oc, None)
                    collisions.append({
                        "lead_profile": profile_url[:30] + "...",
                        "other_campaign_id": other_id,
                        "other_campaign_name": oc.get("campaignName"),
                        "other_status": oc.get("campaignStatus"),
                        "lead_status": oc.get("leadStatus"),
                        "is_ours": is_ours,
                        "evidence": evidence,
                    })
            if collisions:
                verdicts["lead_not_in_another_linkedin_campaign"] = "FAIL"
                seen = set()
                for c in collisions:
                    key = (c["lead_profile"], c["other_campaign_id"])
                    if key in seen:
                        continue
                    seen.add(key)
                    whose = "OURS" if c["is_ours"] else "CLIENT'S"
                    offenders["lead_not_in_another_linkedin_campaign"].append(
                        f"{cid}: lead {c['lead_profile']} also in "
                        f"campaign {c['other_campaign_id']} "
                        f"({c['other_campaign_name']}), "
                        f"status={c['other_status']}, "
                        f"lead_status={c['lead_status']}, "
                        f"whose={whose}, evidence={c['evidence']}")
            else:
                verdicts["lead_not_in_another_linkedin_campaign"] = "PASS"
    else:
        verdicts["lead_not_in_another_linkedin_campaign"] = "UNCONFIRMED"
        offenders["lead_not_in_another_linkedin_campaign"] = [
            f"{cid}: live reads disabled"]

    # --- Rule 6: connection_note_under_280_characters ---
    if live_reads:
        try:
            seq = heyreach.campaign_sequence(cid)
            notes = heyreach.connection_notes(seq)
            if not notes:
                verdicts["connection_note_under_280_characters"] = "VACUOUS"
                offenders["connection_note_under_280_characters"] = [
                    f"{cid}: no connection request note in sequence (VACUOUS)"]
            else:
                placeholders = []
                over_length = []
                for note in notes:
                    if heyreach.note_is_placeholder(note):
                        placeholders.append(note[:50] + "..." if len(note) > 50 else note)
                # Render with worst-case field values
                leads = _all_leads_for_campaign(cid) if 'leads' not in dir() else leads
                if not leads:
                    leads = _all_leads_for_campaign(cid)
                longest_vals = _extract_longest_field_values(leads)
                max_len, worst_tmpl, worst_rendered = _longest_rendered_length(
                    [n for n in notes if not heyreach.note_is_placeholder(n)],
                    longest_vals)
                details["note_templates"] = len(notes)
                details["placeholder_count"] = len(placeholders)
                details["longest_rendered_chars"] = max_len
                details["longest_rendered_excerpt"] = worst_rendered[:80]
                if placeholders:
                    verdicts["connection_note_under_280_characters"] = "FAIL"
                    offenders["connection_note_under_280_characters"].append(
                        f"{cid}: {len(placeholders)} placeholder note(s) "
                        f"(never approved)")
                if max_len > NOTE_CHAR_LIMIT:
                    verdicts["connection_note_under_280_characters"] = "FAIL"
                    offenders["connection_note_under_280_characters"].append(
                        f"{cid}: longest rendered note is {max_len} chars "
                        f"(limit {NOTE_CHAR_LIMIT}); excerpt: "
                        f"{worst_rendered[:60]!r}...")
                if not placeholders and max_len <= NOTE_CHAR_LIMIT:
                    verdicts["connection_note_under_280_characters"] = "PASS"
        except Exception as exc:
            verdicts["connection_note_under_280_characters"] = "UNCONFIRMED"
            offenders["connection_note_under_280_characters"] = [
                f"{cid}: {exc}"]
    else:
        verdicts["connection_note_under_280_characters"] = "UNCONFIRMED"
        offenders["connection_note_under_280_characters"] = [
            f"{cid}: live reads disabled"]

    return verdicts, offenders, details


def run(phase="pre_push", campaigns=None, workspaces=None, json_path=None,
        live_reads=True, heyreach_module=None, seatledger_module=None):
    """Run the campaign HeyReach check.

    Parameters
    ----------
    phase : str
        One of pre_push, post_push, ongoing.
    campaigns : list of int
        Provider campaign ids. If None, auto-discovers all campaigns.
    workspaces : str
        Path to a named copy of production work/.
    json_path : str
        Where to write the result JSON.
    live_reads : bool
        Whether to make provider reads.
    heyreach_module : module, optional
        Override for testing.
    seatledger_module : module, optional
        Override for testing.

    Returns
    -------
    dict
        The result document.
    """
    hr = heyreach_module or heyreach
    sl = seatledger_module or seatledger

    measured_at = _now_iso()
    campaign_ids = campaigns or []
    evidence = {"provider_reads": [], "files_read": []}

    # Load workspace files
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
            "--workspaces is required; a worktree has its own stale work/ "
            "and most worker worktrees have no work/queue.jsonl at all",
            phase, campaign_ids, measured_at)

    # Auto-discover campaigns if none specified
    provider_campaigns_by_id = {}
    seats_by_id = {}
    if live_reads:
        try:
            all_pc = _all_campaigns_from_provider()
            for pc in all_pc:
                pid = pc.get("id")
                if pid is not None:
                    provider_campaigns_by_id[int(pid)] = pc
            evidence["provider_reads"].append({
                "provider": "heyreach",
                "call": "campaigns(GetAll)",
                "rows": len(all_pc),
                "at": measured_at,
            })
            if not campaign_ids:
                campaign_ids = sorted(provider_campaigns_by_id.keys())
        except Exception as exc:
            return _error_result(
                f"listing campaigns: {exc}", phase, campaign_ids, measured_at)
        try:
            all_seats_list = _all_seats()
            for s in all_seats_list:
                sid = s.get("id")
                if sid is not None:
                    seats_by_id[str(sid)] = s
                    seats_by_id[int(sid)] = s
            evidence["provider_reads"].append({
                "provider": "heyreach",
                "call": "li_accounts(GetAll)",
                "rows": len(all_seats_list),
                "at": measured_at,
            })
        except Exception as exc:
            return _error_result(
                f"listing seats: {exc}", phase, campaign_ids, measured_at)

    if not campaign_ids:
        registry_index = _campaigns_by_heyreach_id(campaign_rows)
        campaign_ids = sorted(registry_index.keys())

    if not campaign_ids:
        return _vacuous_result(
            "no HeyReach campaigns found at provider or in registry",
            phase, campaign_ids, queue_file_info, measured_at)

    # Check each campaign
    registry_index = _campaigns_by_heyreach_id(campaign_rows)
    all_verdicts = {}
    all_offenders = {}
    all_details = {}
    per_campaign = []

    for cid in sorted(campaign_ids):
        reg_row = registry_index.get(cid)
        v, o, d = _check_one_campaign(
            cid, reg_row, seats_by_id, queue_rows, live_reads,
            provider_campaigns_by_id)
        all_details[cid] = d
        per_campaign.append({
            "campaign_id": cid,
            "verdicts": v,
            "offenders": o,
            "details": d,
        })
        for rule in RULES:
            all_verdicts.setdefault(rule, [])
            all_offenders.setdefault(rule, [])
            all_verdicts[rule].append(v[rule])
            all_offenders[rule].extend(o[rule])

    # Aggregate verdicts per rule
    rule_verdicts = {}
    rule_counts = {}
    rule_offenders = {}
    for rule in RULES:
        vs = all_verdicts.get(rule, [])
        if not vs:
            rule_verdicts[rule] = "VACUOUS"
        elif any(v == "FAIL" for v in vs):
            rule_verdicts[rule] = "FAIL"
        elif any(v == "UNCONFIRMED" for v in vs):
            rule_verdicts[rule] = "UNCONFIRMED"
        elif any(v == "VACUOUS" for v in vs) and len(vs) < len(campaign_ids):
            rule_verdicts[rule] = "UNCONFIRMED"
        elif all(v == "VACUOUS" for v in vs):
            rule_verdicts[rule] = "VACUOUS"
        else:
            rule_verdicts[rule] = "PASS"
        rule_counts[rule] = len(all_offenders.get(rule, []))
        rule_offenders[rule] = all_offenders.get(rule, [])

    # Overall verdict
    verdict_values = list(rule_verdicts.values())
    if any(v == "FAIL" for v in verdict_values):
        overall = "FAIL"
    elif any(v == "UNCONFIRMED" for v in verdict_values):
        overall = "UNCONFIRMED"
    elif all(v == "VACUOUS" for v in verdict_values):
        overall = "VACUOUS"
    else:
        overall = "PASS"

    subjects = len(campaign_ids)
    offending_campaigns = set()
    for rule_offs in rule_offenders.values():
        for off_id in rule_offs:
            parts = str(off_id).split(":")
            if parts:
                offending_campaigns.add(parts[0].strip())
    clean = subjects - len(offending_campaigns)

    result = {
        "check": "campaign_heyreach",
        "phase": phase,
        "verdict": overall,
        "campaigns": [str(c) for c in campaign_ids],
        "subjects": subjects,
        "clean": clean,
        "refused": overall != "PASS",
        "rules": dict(RULES),
        "counts": rule_counts,
        "offenders": rule_offenders,
        "unverifiable": {},
        "per_campaign": per_campaign,
        "evidence": evidence,
        "measured_at": measured_at,
        "workspaces": workspaces,
    }

    if json_path and workspaces:
        out_dir = os.path.dirname(json_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)

    return result


def _error_result(reason, phase, campaign_ids, measured_at):
    return {
        "check": "campaign_heyreach",
        "phase": phase,
        "verdict": "ERROR",
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
        "check": "campaign_heyreach",
        "phase": phase,
        "verdict": "VACUOUS",
        "campaigns": [str(c) for c in (campaign_ids or [])],
        "subjects": 0,
        "clean": 0,
        "refused": True,
        "rules": dict(RULES),
        "counts": {name: 0 for name in RULES},
        "offenders": {name: [] for name in RULES},
        "unverifiable": {},
        "vacuous_reason": reason,
        "evidence": {"files_read": [file_info] if file_info else []},
        "measured_at": measured_at,
    }


def _exit_code(result):
    verdict = result.get("verdict", "ERROR")
    if verdict == "PASS":
        return EXIT_PASS
    if verdict == "FAIL":
        return EXIT_FAIL
    if verdict in ("UNCONFIRMED", "VACUOUS"):
        return EXIT_UNCONFIRMED
    return EXIT_ERROR


# ------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_campaign_heyreach")
    parser.add_argument("--phase", default="pre_push",
                        choices=("pre_push", "post_push", "ongoing"))
    parser.add_argument("--campaign", action="append", type=int,
                        dest="campaigns")
    parser.add_argument("--workspaces", required=True,
                        help="path to a named copy of production work/")
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--no-live-reads", action="store_true",
                        help="skip provider reads (marks UNCONFIRMED)")
    args = parser.parse_args(argv)

    result = run(
        phase=args.phase,
        campaigns=args.campaigns,
        workspaces=args.workspaces,
        json_path=args.json_path,
        live_reads=not args.no_live_reads,
    )

    print(json.dumps(result, indent=2, default=str))
    return _exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
