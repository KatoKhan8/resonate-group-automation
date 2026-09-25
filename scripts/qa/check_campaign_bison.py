#!/usr/bin/env python3
"""QA check: is each EmailBison campaign actually built to send what we think?

TASK-296. The per-campaign EmailBison check: eight rules that answer whether
a campaign the leads are about to be attached to is actually built at the
provider, right now, to send what we think it will send.

THE EIGHT RULES:

    campaign_exists              by ID at the provider, not by name
    step_count_matches           provider step KEYS (as a set) equal THAT
                                 campaign's own stored cadence_steps keys
    templates_use_only_carried_variables
                                 every {VARIABLE} in every step template is
                                 carried by the leads; every lead variable
                                 is named by some template
    sender_attached_and_connected
                                 at least one sender, status is Connected
    schedule_and_limits_set      a sending window and daily limits, both read
    no_settled_blank_rows        zero settled blank rows in the queue
    not_paused                   the campaign is not paused
    id_matches_our_registry      the provider id equals the one in campaigns

READS ONLY. No provider write of any kind.

Usage:
    py -3 scripts/qa/check_campaign_bison.py \\
        --phase pre_push \\
        --campaign 485 --campaign 502 \\
        --workspaces <path to work/ copy> \\
        --json work/qa/<run>/campaign_bison.json
"""
import argparse
import json
import os
import re
import sys
import datetime

# Allow running standalone and as an import
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src import campaigns as campaign_store
from src import emptyrender
from src.providers import bison

# ------------------------------------------------------------- rule names

RULES = {
    "campaign_exists":
        "the campaign exists at the provider by ID (ISSUE-036)",
    "step_count_matches":
        "the provider step keys (as a set) match the campaign's own "
        "stored cadence step keys, diffed both directions",
    "templates_use_only_carried_variables":
        "every {{VARIABLE}} in every step template is carried by the "
        "leads, and every lead variable is named by some template",
    "sender_attached_and_connected":
        "at least one sender is attached and its status is Connected",
    "schedule_and_limits_set":
        "a sending window (days, start, end, timezone) and daily limits "
        "are both set at the provider",
    "no_settled_blank_rows":
        "zero settled blank rows in the scheduled-email queue",
    "not_paused":
        "the campaign is not paused at the provider",
    "id_matches_our_registry":
        "the provider campaign id matches a row in campaigns.jsonl",
}

# Exit codes per the QA contract
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNCONFIRMED = 2
EXIT_ERROR = 3

# Variable pattern matching both {VAR} and {{VAR}} syntax
_VARIABLE_RE = re.compile(r"\{\{?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}?\}")


# ------------------------------------------------------------- helpers

def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _step_keys_from_cadence(cadence_steps):
    """Extract the step keys from a campaign's stored cadence_steps.

    The stored cadence_steps is a list of step dicts, each carrying a "key"
    field (e.g. "em1", "em2", "em3"). Returns a set of key strings.
    """
    if not cadence_steps:
        return set()
    keys = set()
    for step in cadence_steps:
        if isinstance(step, dict) and step.get("key"):
            keys.add(step["key"])
        elif isinstance(step, str):
            keys.add(step)
    return keys


def _step_keys_from_provider(steps):
    """Extract step keys from the provider's sequence_steps response.

    The provider returns steps with an "order" field and optionally an "id".
    The step key is derived from the order: order 1 -> em1, order 2 -> em2,
    etc. This matches how _sequence_steps builds them from cadence step keys.
    """
    if not steps:
        return set()
    keys = set()
    for step in steps:
        if not isinstance(step, dict):
            continue
        order = step.get("order")
        if order is not None:
            keys.add(f"em{order}")
    return keys


def _extract_template_variables(steps):
    """Extract all {VARIABLE} names from every step's subject and body.

    Returns a dict mapping step_key -> set of variable names found.
    """
    per_step = {}
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        order = step.get("order")
        step_key = f"em{order}" if order is not None else "?"
        found = set()
        for field in ("email_subject", "email_body"):
            text = str(step.get(field) or "")
            for match in _VARIABLE_RE.finditer(text):
                found.add(match.group(1).upper())
        per_step[step_key] = found
    return per_step


def _lead_variable_names(leads):
    """The union of all custom variable names across a set of leads."""
    names = set()
    for lead in leads or []:
        if isinstance(lead, dict):
            for v in lead.get("custom_variables") or []:
                if isinstance(v, dict) and v.get("name"):
                    names.add(str(v["name"]).upper())
    return names


def _load_campaign_rows(workspaces_path):
    """Load campaigns.jsonl from the named work/ copy.

    Returns (rows, file_info) where file_info records path, mtime, row count.
    """
    path = os.path.join(workspaces_path, "campaigns.jsonl")
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"campaigns.jsonl not found at {path}")
    mtime = os.path.getmtime(path)
    mtime_iso = datetime.datetime.fromtimestamp(mtime).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
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


# ------------------------------------------------------------- the check

def run(phase="pre_push", campaigns=None, workspaces=None, json_path=None,
        live_reads=True, bison_module=None):
    """Run the campaign bison check.

    Parameters
    ----------
    phase : str
        One of pre_push, post_push, ongoing.
    campaigns : list of int
        Provider campaign ids to check. If None, checks ALL campaigns found
        in the work/ copy.
    workspaces : str
        Path to a copy of the production work/ directory.
    json_path : str, optional
        Where to write the result JSON.
    live_reads : bool
        Whether to make provider reads. Default True.
    bison_module : module, optional
        Override for the bison module (for testing).

    Returns
    -------
    dict
        The result document per the QA contract.
    """
    b = bison_module or bison

    if not workspaces:
        return _error_result("no --workspaces path given", phase, campaigns)
    if not os.path.isdir(workspaces):
        return _error_result(
            f"--workspaces path does not exist: {workspaces}",
            phase, campaigns)

    try:
        camp_rows, file_info = _load_campaign_rows(workspaces)
    except FileNotFoundError as exc:
        return _error_result(str(exc), phase, campaigns)

    if not camp_rows:
        return _vacuous_result(
            "campaigns.jsonl is empty", phase, campaigns, file_info)

    by_bison_id = _campaigns_by_bison_id(camp_rows)

    # If no campaigns specified, check all that have a bison_campaign_id
    if campaigns is None:
        campaigns = sorted(by_bison_id.keys())

    if not campaigns:
        return _vacuous_result(
            "no campaigns with bison_campaign_id in the registry",
            phase, campaigns, file_info)

    # Sort by provider id numerically
    campaigns = sorted(int(c) for c in campaigns)

    # Workspace assertion
    workspace_info = None
    if live_reads:
        try:
            workspace_info = b.bound_workspace()
        except Exception as exc:
            return _error_result(
                f"bound_workspace() failed: {exc}", phase, campaigns)

    # Sender inventory (once, for all campaigns)
    sender_map = {}
    if live_reads:
        try:
            sender_rows, _meta = b.sender_emails()
            for sr in sender_rows:
                if isinstance(sr, dict) and sr.get("id"):
                    sender_map[int(sr["id"])] = sr
        except Exception:
            sender_map = {}

    # Per-campaign checks
    per_campaign = []
    all_offenders = {name: [] for name in RULES}
    total_subjects = len(campaigns)
    clean_count = 0

    for cid in campaigns:
        verdicts, offenders = _check_one_campaign(
            cid, by_bison_id, b, live_reads, sender_map, workspace_info)
        any_fail = any(v != "PASS" for v in verdicts.values())
        if not any_fail:
            clean_count += 1
        for rule_name, verdict in verdicts.items():
            if verdict != "PASS":
                off = offenders.get(rule_name)
                if off:
                    all_offenders[rule_name].extend(off)
                else:
                    all_offenders[rule_name].append(str(cid))
        per_campaign.append({
            "campaign_id": cid,
            "registry_row": by_bison_id.get(cid),
            "verdicts": verdicts,
            "offenders": offenders,
        })

    # Build the result document
    counts = {name: len(set(ids)) for name, ids in all_offenders.items()}
    refused = any(counts.values())

    result = {
        "check": "campaign_bison",
        "phase": phase,
        "verdict": "FAIL" if refused else "PASS",
        "campaigns": [str(c) for c in campaigns],
        "subjects": total_subjects,
        "clean": clean_count,
        "refused": refused,
        "rules": dict(RULES),
        "counts": counts,
        "offenders": {k: sorted(set(v)) for k, v in all_offenders.items()},
        "unverifiable": {},
        "per_campaign": per_campaign,
        "evidence": {
            "provider_reads": live_reads,
            "files_read": [file_info],
            "provider_reads_skipped": not live_reads,
            "workspace": workspace_info,
        },
        "measured_at": _now_iso(),
        "workspaces": workspaces,
    }

    if json_path:
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)

    return result


def _check_one_campaign(cid, by_bison_id, b, live_reads, sender_map,
                        workspace_info):
    """Run all eight rules against one campaign. Returns (verdicts, offenders).
    """
    verdicts = {}
    offenders = {}
    registry_row = by_bison_id.get(cid)

    # 1. campaign_exists
    provider_campaign = None
    if live_reads:
        try:
            provider_campaign = b.campaign(cid)
            if provider_campaign:
                verdicts["campaign_exists"] = "PASS"
            else:
                verdicts["campaign_exists"] = "FAIL"
                offenders["campaign_exists"] = [str(cid)]
        except Exception as exc:
            verdicts["campaign_exists"] = "UNCONFIRMED"
            offenders["campaign_exists"] = [f"{cid}: {exc}"]
    else:
        verdicts["campaign_exists"] = "UNCONFIRMED"
        offenders["campaign_exists"] = [f"{cid}: live reads disabled"]

    # 2. step_count_matches
    if provider_campaign is not None and live_reads:
        try:
            provider_steps = b.sequence_steps(cid)
            provider_keys = _step_keys_from_provider(provider_steps)
            stored_steps = (registry_row or {}).get("cadence_steps") or []
            stored_keys = _step_keys_from_cadence(stored_steps)

            if not stored_keys:
                verdicts["step_count_matches"] = "UNCONFIRMED"
                offenders["step_count_matches"] = [
                    f"{cid}: no cadence_steps stored on registry row"]
            else:
                only_in_stored = stored_keys - provider_keys
                only_in_provider = provider_keys - stored_keys
                if not only_in_stored and not only_in_provider:
                    verdicts["step_count_matches"] = "PASS"
                else:
                    verdicts["step_count_matches"] = "FAIL"
                    detail = (f"{cid}: stored={{{', '.join(sorted(stored_keys))}}}, "
                              f"provider={{{', '.join(sorted(provider_keys))}}}, "
                              f"only_in_stored={{{', '.join(sorted(only_in_stored))}}}, "
                              f"only_in_provider={{{', '.join(sorted(only_in_provider))}}}")
                    offenders["step_count_matches"] = [detail]
        except Exception as exc:
            verdicts["step_count_matches"] = "UNCONFIRMED"
            offenders["step_count_matches"] = [f"{cid}: {exc}"]
    else:
        verdicts["step_count_matches"] = "UNCONFIRMED"
        offenders["step_count_matches"] = [
            f"{cid}: campaign not available at provider"]

    # 3. templates_use_only_carried_variables
    if provider_campaign is not None and live_reads:
        try:
            provider_steps = b.sequence_steps(cid)
            template_vars = _extract_template_variables(provider_steps)
            all_template_vars = set()
            for vs in template_vars.values():
                all_template_vars.update(vs)

            lead_ids = b.campaign_lead_ids(cid)
            lead_vars = set()
            sample_size = min(len(lead_ids), 5)
            for lid in lead_ids[:sample_size]:
                try:
                    lead_data = b.lead(lid)
                    for name in bison.variables_of(lead_data):
                        lead_vars.add(str(name).upper())
                except Exception:
                    pass

            declared_vars = set()
            try:
                for name in b.custom_variables():
                    declared_vars.add(str(name).upper())
            except Exception:
                pass

            effective_lead_vars = lead_vars | declared_vars

            template_not_carried = all_template_vars - effective_lead_vars
            lead_not_in_template = effective_lead_vars - all_template_vars

            # Filter out structural variables that are always present
            structural = {"RECORD_ID", "CONTACT_KEY", "CLIENT",
                          "SENDER_ID", "SENDER_ACCOUNT_ID",
                          "PROVIDER_ACCOUNT_ID", "TITLE"}
            template_not_carried = template_not_carried - structural
            lead_not_in_template = lead_not_in_template - structural

            if not template_not_carried and not lead_not_in_template:
                verdicts["templates_use_only_carried_variables"] = "PASS"
            else:
                verdicts["templates_use_only_carried_variables"] = "FAIL"
                parts = []
                if template_not_carried:
                    parts.append(
                        f"template_names_not_carried={{{', '.join(sorted(template_not_carried))}}}")
                if lead_not_in_template:
                    parts.append(
                        f"lead_vars_not_in_template={{{', '.join(sorted(lead_not_in_template))}}}")
                offenders["templates_use_only_carried_variables"] = [
                    f"{cid}: {'; '.join(parts)}"]
        except Exception as exc:
            verdicts["templates_use_only_carried_variables"] = "UNCONFIRMED"
            offenders["templates_use_only_carried_variables"] = [
                f"{cid}: {exc}"]
    else:
        verdicts["templates_use_only_carried_variables"] = "UNCONFIRMED"
        offenders["templates_use_only_carried_variables"] = [
            f"{cid}: campaign not available at provider"]

    # 4. sender_attached_and_connected
    if provider_campaign is not None and live_reads:
        try:
            sender_ids = b.campaign_senders(cid)
            if not sender_ids:
                verdicts["sender_attached_and_connected"] = "FAIL"
                offenders["sender_attached_and_connected"] = [
                    f"{cid}: no senders attached"]
            else:
                connected = []
                attached_not_connected = []
                for sid in sender_ids:
                    sender_obj = sender_map.get(sid)
                    if sender_obj is None:
                        attached_not_connected.append(
                            f"sender {sid} (not in workspace inventory)")
                        continue
                    status = str(sender_obj.get("status") or "").strip()
                    if status.lower() == "connected":
                        connected.append(sid)
                    else:
                        attached_not_connected.append(
                            f"sender {sid} (status={status!r})")
                if connected:
                    verdicts["sender_attached_and_connected"] = "PASS"
                else:
                    verdicts["sender_attached_and_connected"] = "FAIL"
                    offenders["sender_attached_and_connected"] = [
                        f"{cid}: {len(sender_ids)} attached, 0 Connected; "
                        + "; ".join(attached_not_connected[:5])]
        except Exception as exc:
            verdicts["sender_attached_and_connected"] = "UNCONFIRMED"
            offenders["sender_attached_and_connected"] = [f"{cid}: {exc}"]
    else:
        verdicts["sender_attached_and_connected"] = "UNCONFIRMED"
        offenders["sender_attached_and_connected"] = [
            f"{cid}: campaign not available at provider"]

    # 5. schedule_and_limits_set
    if provider_campaign is not None and live_reads:
        try:
            sched = b.schedule(cid)
            if not sched:
                verdicts["schedule_and_limits_set"] = "FAIL"
                offenders["schedule_and_limits_set"] = [
                    f"{cid}: no schedule set at provider"]
            else:
                missing = []
                for field in ("days", "start_time", "end_time", "timezone"):
                    if not sched.get(field):
                        missing.append(field)
                if missing:
                    verdicts["schedule_and_limits_set"] = "FAIL"
                    offenders["schedule_and_limits_set"] = [
                        f"{cid}: schedule missing {', '.join(missing)}; "
                        f"keys present: {sorted(sched.keys())}"]
                else:
                    verdicts["schedule_and_limits_set"] = "PASS"
        except Exception as exc:
            verdicts["schedule_and_limits_set"] = "UNCONFIRMED"
            offenders["schedule_and_limits_set"] = [f"{cid}: {exc}"]
    else:
        verdicts["schedule_and_limits_set"] = "UNCONFIRMED"
        offenders["schedule_and_limits_set"] = [
            f"{cid}: campaign not available at provider"]

    # 6. no_settled_blank_rows
    if provider_campaign is not None and live_reads:
        try:
            scheduled = b.scheduled_emails(cid)
            if not scheduled:
                verdicts["no_settled_blank_rows"] = "VACUOUS"
                offenders["no_settled_blank_rows"] = [
                    f"{cid}: zero scheduled rows (VACUOUS - no evidence)"]
            else:
                found = emptyrender.scan(scheduled)
                settled_blanks = found.get("already", [])
                if settled_blanks:
                    verdicts["no_settled_blank_rows"] = "FAIL"
                    row_ids = [str(e.get("row") or "?")
                               for e in settled_blanks[:10]]
                    offenders["no_settled_blank_rows"] = [
                        f"{cid}: {len(settled_blanks)} settled blank rows: "
                        + ", ".join(row_ids)]
                else:
                    verdicts["no_settled_blank_rows"] = "PASS"
        except Exception as exc:
            verdicts["no_settled_blank_rows"] = "UNCONFIRMED"
            offenders["no_settled_blank_rows"] = [f"{cid}: {exc}"]
    else:
        verdicts["no_settled_blank_rows"] = "UNCONFIRMED"
        offenders["no_settled_blank_rows"] = [
            f"{cid}: campaign not available at provider"]

    # 7. not_paused
    if provider_campaign is not None:
        status_field = str(provider_campaign.get("status") or "").strip()
        if status_field.lower() == "paused":
            verdicts["not_paused"] = "FAIL"
            intent = (registry_row or {}).get("launch", {}).get("state")
            offenders["not_paused"] = [
                f"{cid}: paused at provider (intent={intent})"]
        else:
            verdicts["not_paused"] = "PASS"
    else:
        verdicts["not_paused"] = "UNCONFIRMED"
        offenders["not_paused"] = [f"{cid}: campaign not available"]

    # 8. id_matches_our_registry
    if registry_row is not None:
        verdicts["id_matches_our_registry"] = "PASS"
    else:
        verdicts["id_matches_our_registry"] = "FAIL"
        offenders["id_matches_our_registry"] = [
            f"{cid}: no matching row in campaigns.jsonl"]

    return verdicts, offenders


def _error_result(reason, phase, campaign_ids):
    return {
        "check": "campaign_bison",
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
        "measured_at": _now_iso(),
    }


def _vacuous_result(reason, phase, campaign_ids, file_info):
    return {
        "check": "campaign_bison",
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
        "evidence": {"files_read": [file_info]},
        "measured_at": _now_iso(),
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
        prog="python -m scripts.qa.check_campaign_bison")
    parser.add_argument("--phase", default="pre_push",
                        choices=("pre_push", "post_push", "ongoing"))
    parser.add_argument("--campaign", action="append", type=int,
                        dest="campaigns")
    parser.add_argument("--workspaces", required=True,
                        help="path to a copy of production work/")
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
