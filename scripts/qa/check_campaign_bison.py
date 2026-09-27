#!/usr/bin/env python3
"""QA check: EmailBison campaign readiness (Lane F, TASK-296).

Eight pre-push rules verified against the live provider for every campaign
named on the command line (or every campaign in the registry when none is
named). READS ONLY - no provider write is made.

The eight rules:

    campaign_exists              by provider ID, not by name (ISSUE-036)
    step_count_matches           stored cadence_steps vs provider step keys,
                                 diffed as SETS both directions
    templates_use_only_carried_variables
                                 template {VARIABLE} names vs lead variables,
                                 both directions, per campaign
    sender_attached_and_connected  at least one sender, status Connected,
                                 workspace asserted
    schedule_and_limits_set      sending window and daily limits read back
    no_settled_blank_rows        zero settled blank rows; VACUOUS when the
                                 campaign has no scheduled rows at all
    not_paused                   provider paused state vs registry intent
    id_matches_our_registry      provider ID equals the registry's
                                 bison_campaign_id
"""
import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.providers import bison
from src import emptyrender

CHECK_NAME = "campaign_bison"
PHASE = "pre_push"

_VARIABLE_RE = re.compile(r"\{\{?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}?\}")


# ------------------------------------------------------------------ helpers

def load_campaigns_from_workspace(workspaces):
    """Read campaigns.jsonl from the named work/ copy.

    Returns ``(rows, path, mtime_iso)``.  Raises when the file is missing
    or empty so a VACUOUS subject set is never confused with a missing file.
    """
    path = os.path.join(workspaces, "campaigns.jsonl")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"no campaigns.jsonl in {workspaces}")
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"campaigns.jsonl in {workspaces} is empty")
    mtime = os.path.getmtime(path)
    from datetime import datetime, timezone
    mtime_iso = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    return rows, path, mtime_iso


def extract_template_variables(text):
    """Variable names from a template string, lowercased, as a set."""
    if not text:
        return set()
    return {m.lower() for m in _VARIABLE_RE.findall(str(text))}


def diff_step_keys(provider_keys, expected_keys):
    """Set diff of step keys, both directions.  Returns (only_a, only_b).

    THE DEFECT THIS EXISTS TO CATCH.  ``len(a) == len(b)`` compares equal
    while the sets differ: ``{1, 2, 4}`` and ``{1, 2, 3}`` both have
    length 3 but are different steps.  A half-applied sequence change
    reads as complete through a count comparison.  The set diff in both
    directions is the whole point of the check.
    """
    a, b = set(provider_keys), set(expected_keys)
    return sorted(a - b), sorted(b - a)


def campaign_senders_with_status(campaign_id):
    """Full sender objects for one campaign, including status.

    ``bison.campaign_senders`` returns only IDs.  This pages the same route
    but keeps the full row so the status field is available.
    """
    rows, page = [], 1
    while True:
        status, data = bison.request(
            "GET",
            bison.query(
                f"{bison.base()}/campaigns/{campaign_id}/sender-emails",
                {"page": page}),
            bison.headers())
        if not bison.ok(status):
            raise bison.ProviderError(
                f"campaign_senders_with_status: page {page} -> {status}")
        chunk = data.get("data") if isinstance(data, dict) else None
        if not isinstance(chunk, list):
            break
        rows.extend(chunk)
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        try:
            last = int(meta.get("last_page"))
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        page += 1
    return [r for r in rows if isinstance(r, dict)]


def _fetch_scheduled_emails(campaign_id):
    """Scheduled emails with bounded paging; reports blind on overflow."""
    try:
        return bison.scheduled_emails(
            campaign_id, cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)
    except bison.PartialInventory:
        return None


# -------------------------------------------------------------------- rules

def rule_campaign_exists(campaign_id, _row, _provider):
    """Rule 1: campaign exists by ID at the provider."""
    try:
        data = bison.campaign(campaign_id)
    except Exception as exc:
        return {"pass": False, "detail": f"provider read failed: {exc}"}
    if not data:
        return {"pass": False, "detail": "provider returned empty data"}
    return {"pass": True,
            "detail": f"campaign {campaign_id} exists at provider",
            "provider_data": data}


def rule_step_count_matches(campaign_id, row, provider):
    """Rule 2: stored cadence_steps vs provider step keys, SET diff.

    Compares the SET of provider step orders against {1, 2, ..., N} where
    N is the campaign's own stored ``cadence_steps``.  Counts match but
    keys differ is caught because {1,2,4} != {1,2,3} as sets.
    """
    stored = int(row.get("cadence_steps") or 3)
    steps = provider.get("steps") or []
    provider_orders = {s.get("order") for s in steps
                       if isinstance(s, dict) and s.get("order") is not None}
    expected = set(range(1, stored + 1))
    only_provider, only_stored = diff_step_keys(provider_orders, expected)
    ok_flag = (provider_orders == expected)
    return {
        "pass": ok_flag,
        "stored_cadence_steps": stored,
        "provider_step_count": len(steps),
        "provider_step_keys": sorted(provider_orders),
        "expected_step_keys": sorted(expected),
        "only_in_provider": only_provider,
        "only_in_stored": only_stored,
        "detail": (
            f"stored={stored} provider_keys={sorted(provider_orders)} "
            f"expected_keys={sorted(expected)}"
            + (f" only_provider={only_provider}" if only_provider else "")
            + (f" only_stored={only_stored}" if only_stored else "")),
    }


def rule_templates_use_only_carried_variables(
        campaign_id, row, provider):
    """Rule 3: template {VARIABLE} names vs lead variables, both directions.

    Extracts ``{VARIABLE}`` references from every step template the provider
    returned, lowercased.  Diffs against the union of variable names carried
    by the campaign's leads (sampled up to 50).  Both directions are
    reported: template names no lead carries (gap), and lead names no
    template references (wasted render).
    """
    steps = provider.get("steps") or []
    template_vars = set()
    per_step = {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        sv = set()
        for field in ("email_subject", "email_body"):
            sv |= extract_template_variables(step.get(field))
        per_step[str(step.get("order", "?"))] = sorted(sv)
        template_vars |= sv

    lead_vars = set()
    lead_ids = provider.get("lead_ids") or []
    for lid in lead_ids[:50]:
        try:
            lead_data = bison.lead(lid)
            lead_vars |= {k.lower()
                          for k in bison.variables_of(lead_data)}
        except Exception:
            continue

    only_template = sorted(template_vars - lead_vars)
    only_lead = sorted(lead_vars - template_vars)
    ok_flag = not only_template and not only_lead
    return {
        "pass": ok_flag,
        "template_variables": sorted(template_vars),
        "lead_variables": sorted(lead_vars),
        "only_in_templates": only_template,
        "only_in_leads": only_lead,
        "per_step_variables": per_step,
        "detail": (
            f"template_vars={sorted(template_vars)} "
            f"lead_vars={sorted(lead_vars)}"
            + (f" only_template={only_template}" if only_template else "")
            + (f" only_lead={only_lead}" if only_lead else "")),
    }


def rule_sender_attached_and_connected(
        campaign_id, row, provider):
    """Rule 4: at least one sender AND its status is Connected.

    Also asserts the workspace via ``bison.bound_workspace()`` before
    believing the sender list.  ``workspace_id`` is accepted and discarded
    by every list route; the binding route is the only way to know which
    estate a credential is reading.
    """
    sender_ids = provider.get("sender_ids") or []
    if not sender_ids:
        return {"pass": False, "detail": "no senders attached"}

    try:
        ws = bison.bound_workspace()
        workspace_asserted = True
        workspace_id = ws.get("id")
        workspace_name = ws.get("name")
    except Exception as exc:
        return {"pass": False,
                "detail": f"workspace assertion failed: {exc}"}

    senders = provider.get("sender_objects") or []
    statuses = {}
    for s in senders:
        sid = s.get("id")
        statuses[str(sid)] = s.get("status", "unknown")

    connected = [sid for sid, st in statuses.items()
                 if str(st).lower().strip() == "connected"]
    attached = len(statuses)

    if not connected:
        return {
            "pass": False,
            "attached_count": attached,
            "connected_count": 0,
            "sender_statuses": statuses,
            "workspace_id": workspace_id,
            "workspace_name": workspace_name,
            "workspace_asserted": workspace_asserted,
            "detail": (f"{attached} sender(s) attached, 0 connected; "
                       f"statuses={statuses}"),
        }

    return {
        "pass": True,
        "attached_count": attached,
        "connected_count": len(connected),
        "sender_statuses": statuses,
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "workspace_asserted": workspace_asserted,
        "detail": f"{len(connected)} connected of {attached} attached",
    }


def rule_schedule_and_limits_set(campaign_id, row, provider):
    """Rule 5: sending window and daily limits, both read back."""
    sched = provider.get("schedule") or {}
    if not sched:
        return {"pass": False, "detail": "no schedule set"}

    detail_parts = []
    for field in ("days", "start_time", "end_time", "timezone"):
        val = sched.get(field)
        if val is None or val == "":
            return {"pass": False,
                    "detail": f"schedule missing {field}",
                    "schedule": sched}
        detail_parts.append(f"{field}={val}")

    campaign_data = provider.get("campaign_data") or {}
    cap = campaign_data.get("max_emails_per_day")
    if not cap:
        return {"pass": False,
                "detail": "no daily email limit set",
                "schedule": sched}

    return {"pass": True,
            "detail": "; ".join(detail_parts) + f"; max_emails_per_day={cap}",
            "schedule": sched,
            "max_emails_per_day": cap}


def rule_no_settled_blank_rows(campaign_id, row, provider):
    """Rule 6: zero settled blank rows.

    A campaign with zero scheduled rows at all is VACUOUS, not PASS - it
    has no evidence either way (ISSUE-041 shape).
    """
    scheduled = provider.get("scheduled_emails")
    if scheduled is None:
        return {"pass": False, "vacuous": False,
                "detail": "could not read scheduled emails (queue too large?)"}
    if len(scheduled) == 0:
        return {"pass": False, "vacuous": True,
                "detail": ("VACUOUS: zero scheduled rows - no evidence "
                           "either way (ISSUE-041)")}

    found = emptyrender.scan(scheduled)
    settled_blanks = found.get("already", [])
    pending_blanks = found.get("pending", [])
    settled_ids = [e.get("row") for e in settled_blanks if e.get("row")]

    return {
        "pass": len(settled_blanks) == 0,
        "vacuous": False,
        "total_scheduled": len(scheduled),
        "settled_blank_count": len(settled_blanks),
        "pending_blank_count": len(pending_blanks),
        "settled_blank_row_ids": settled_ids,
        "detail": (f"{len(scheduled)} scheduled, "
                   f"{len(settled_blanks)} settled blank"
                   + (f" (rows: {settled_ids})" if settled_ids else "")
                   + (f", {len(pending_blanks)} pending blank"
                      if pending_blanks else "")),
    }


def rule_not_paused(campaign_id, row, provider):
    """Rule 7: campaign paused state vs registry intent.

    Checks the provider's paused/active field against the intent recorded
    for THAT campaign in the registry.  Reports which intent was used.
    """
    campaign_data = provider.get("campaign_data") or {}
    provider_status = str(
        campaign_data.get("status") or "").lower()
    is_paused = provider_status == "paused"

    pause_intent = row.get("pause")
    intent_desc = (f"pause={json.dumps(pause_intent)}"
                   if pause_intent else "no pause recorded (expect active)")

    if is_paused and not pause_intent:
        return {"pass": False,
                "provider_paused": True,
                "registry_intent": intent_desc,
                "provider_status": provider_status,
                "detail": (f"campaign is paused at provider but {intent_desc}"
                           )}
    if not is_paused and pause_intent:
        return {"pass": False,
                "provider_paused": False,
                "registry_intent": intent_desc,
                "provider_status": provider_status,
                "detail": (f"registry says paused but provider reads "
                           f"{provider_status!r}")}

    return {"pass": True,
            "provider_paused": is_paused,
            "registry_intent": intent_desc,
            "provider_status": provider_status,
            "detail": f"provider_status={provider_status}, {intent_desc}"}


def rule_id_matches(campaign_id, row, _provider):
    """Rule 8: provider ID equals the registry's bison_campaign_id."""
    stored_id = row.get("bison_campaign_id")
    if stored_id is None:
        return {"pass": False,
                "detail": "no bison_campaign_id in registry row"}
    if int(stored_id) != int(campaign_id):
        return {"pass": False,
                "detail": (f"registry says {stored_id}, "
                           f"checking {campaign_id}"),
                "stored_id": stored_id, "checked_id": campaign_id}
    return {"pass": True,
            "detail": f"ID {campaign_id} matches registry",
            "stored_id": stored_id, "checked_id": campaign_id}


# --------------------------------------------------------------- orchestrate

ALL_RULES = [
    ("campaign_exists", rule_campaign_exists),
    ("step_count_matches", rule_step_count_matches),
    ("templates_use_only_carried_variables",
     rule_templates_use_only_carried_variables),
    ("sender_attached_and_connected", rule_sender_attached_and_connected),
    ("schedule_and_limits_set", rule_schedule_and_limits_set),
    ("no_settled_blank_rows", rule_no_settled_blank_rows),
    ("not_paused", rule_not_paused),
    ("id_matches_our_registry", rule_id_matches),
]

RULE_DESCRIPTIONS = {
    "campaign_exists":
        "campaign exists by ID at the provider (ISSUE-036)",
    "step_count_matches":
        "stored cadence_steps matches provider step keys (set diff)",
    "templates_use_only_carried_variables":
        "template variables are carried by leads (both directions)",
    "sender_attached_and_connected":
        "at least one sender attached with Connected status",
    "schedule_and_limits_set":
        "sending window and daily limits are set",
    "no_settled_blank_rows":
        "zero settled blank rows in the scheduled queue",
    "not_paused":
        "campaign paused state matches registry intent",
    "id_matches_our_registry":
        "provider campaign ID matches the registry",
}


def _gather_provider_data(cid):
    """Read everything the eight rules need from the provider, once.

    Returns ``(data_dict, error_string)``.  If the campaign itself cannot
    be read the error is set and the caller short-circuits.
    """
    data = {}
    try:
        data["campaign_data"] = bison.campaign(cid)
    except Exception as exc:
        return None, f"campaign read failed: {exc}"

    for key, fn in [
        ("steps", lambda: bison.sequence_steps(cid)),
        ("schedule", lambda: bison.schedule(cid)),
        ("sender_ids", lambda: bison.campaign_senders(cid)),
        ("sender_objects", lambda: campaign_senders_with_status(cid)),
        ("lead_ids", lambda: bison.campaign_lead_ids(cid)),
    ]:
        try:
            data[key] = fn()
        except Exception:
            data[key] = None if key != "sender_objects" else []

    data["scheduled_emails"] = _fetch_scheduled_emails(cid)
    return data, None


def run(workspaces, campaign_ids=None, phase="pre_push", json_path=None):
    """Run every rule against every named campaign.

    Returns the result dict.  ``campaign_ids`` may be int or str; they are
    coerced to int for provider reads.  When *campaign_ids* is None every
    campaign in the workspace copy is checked.
    """
    rows, ws_path, ws_mtime = load_campaigns_from_workspace(workspaces)

    if campaign_ids is not None:
        target_ids = [int(c) for c in campaign_ids]
    else:
        target_ids = sorted(
            {int(r["bison_campaign_id"]) for r in rows
             if r.get("bison_campaign_id")})

    if not target_ids:
        return {
            "check": CHECK_NAME, "phase": phase,
            "verdict": "VACUOUS",
            "subjects": 0, "clean": 0, "refused": True,
            "rules": {name: desc for name, desc
                      in RULE_DESCRIPTIONS.items()},
            "counts": {name: 0 for name, _ in ALL_RULES},
            "offenders": {name: [] for name, _ in ALL_RULES},
            "unverifiable": {name: [] for name, _ in ALL_RULES},
            "evidence": {
                "provider_reads": [],
                "files_read": [{"path": ws_path, "rows": len(rows),
                                "mtime": ws_mtime}],
                "provider_reads_skipped": True,
            },
            "vacuous_reason": "no campaign IDs to check",
            "per_campaign": {},
            "workspaces": workspaces,
        }

    row_by_bison = {}
    for r in rows:
        bid = r.get("bison_campaign_id")
        if bid is not None:
            row_by_bison[int(bid)] = r

    per_campaign = {}
    any_fail = False

    for cid in sorted(target_ids):
        row = row_by_bison.get(cid, {})
        provider, err = _gather_provider_data(cid)

        if err:
            per_campaign[cid] = {
                "verdict": "UNCONFIRMED", "error": err,
                "provider_id": cid,
                "stored_bison_id": row.get("bison_campaign_id"),
            }
            continue

        if provider.get("scheduled_emails") is None:
            subjects_empty = True
        else:
            subjects_empty = False

        results = {}
        for name, fn in ALL_RULES:
            results[name] = fn(cid, row, provider)

        failed_rules = [n for n, r in results.items() if not r.get("pass")]
        if failed_rules:
            any_fail = True

        vacuous_rules = []
        for n, r in results.items():
            if r.get("vacuous"):
                vacuous_rules.append(n)

        verdict = "FAIL" if failed_rules else "PASS"
        if vacuous_rules and not failed_rules:
            verdict = "UNCONFIRMED"

        per_campaign[cid] = {
            "verdict": verdict,
            "provider_id": cid,
            "stored_bison_id": row.get("bison_campaign_id"),
            "campaign_name": (provider.get("campaign_data") or {}).get(
                "name"),
            "rules": {n: r.get("detail", "") for n, r in results.items()},
            "failed_rules": failed_rules,
            "vacuous_rules": vacuous_rules,
            "step_count": {
                "stored": results["step_count_matches"].get(
                    "stored_cadence_steps"),
                "provider_keys": results["step_count_matches"].get(
                    "provider_step_keys"),
                "expected_keys": results["step_count_matches"].get(
                    "expected_step_keys"),
                "only_provider": results["step_count_matches"].get(
                    "only_in_provider"),
                "only_stored": results["step_count_matches"].get(
                    "only_in_stored"),
            },
            "variables": {
                "template": results[
                    "templates_use_only_carried_variables"].get(
                    "template_variables"),
                "lead": results[
                    "templates_use_only_carried_variables"].get(
                    "lead_variables"),
                "only_template": results[
                    "templates_use_only_carried_variables"].get(
                    "only_in_templates"),
                "only_lead": results[
                    "templates_use_only_carried_variables"].get(
                    "only_in_leads"),
            },
            "senders": {
                "attached": results[
                    "sender_attached_and_connected"].get(
                    "attached_count", 0),
                "connected": results[
                    "sender_attached_and_connected"].get(
                    "connected_count", 0),
                "statuses": results[
                    "sender_attached_and_connected"].get(
                    "sender_statuses", {}),
                "workspace_asserted": results[
                    "sender_attached_and_connected"].get(
                    "workspace_asserted", False),
                "workspace_id": results[
                    "sender_attached_and_connected"].get(
                    "workspace_id"),
            },
            "schedule": results["schedule_and_limits_set"].get(
                "schedule"),
            "blanks": {
                "total_scheduled": results[
                    "no_settled_blank_rows"].get(
                    "total_scheduled", 0),
                "settled_blank_count": results[
                    "no_settled_blank_rows"].get(
                    "settled_blank_count", 0),
                "pending_blank_count": results[
                    "no_settled_blank_rows"].get(
                    "pending_blank_count", 0),
                "settled_blank_row_ids": results[
                    "no_settled_blank_rows"].get(
                    "settled_blank_row_ids", []),
                "vacuous": results["no_settled_blank_rows"].get(
                    "vacuous", False),
            },
        }

    n_subjects = len(target_ids)
    n_clean = sum(1 for c in per_campaign.values()
                  if c.get("verdict") == "PASS")
    offenders = {}
    for name, _ in ALL_RULES:
        ids = []
        for cid, cr in sorted(per_campaign.items()):
            if name in cr.get("failed_rules", []):
                ids.append(str(cid))
        offenders[name] = ids

    result = {
        "check": CHECK_NAME,
        "phase": phase,
        "verdict": "FAIL" if any_fail else "PASS",
        "subjects": n_subjects,
        "clean": n_clean,
        "refused": any_fail,
        "rules": dict(RULE_DESCRIPTIONS),
        "counts": {name: len(ids) for name, ids in offenders.items()},
        "offenders": offenders,
        "unverifiable": {name: [] for name, _ in ALL_RULES},
        "evidence": {
            "provider_reads": [
                {"provider": "emailbison",
                 "call": f"campaign({cid})",
                 "at": _now_iso()}
                for cid in sorted(target_ids)
            ],
            "files_read": [
                {"path": ws_path, "rows": len(rows), "mtime": ws_mtime},
            ],
            "provider_reads_skipped": False,
        },
        "per_campaign": per_campaign,
        "measured_at": _now_iso(),
        "workspaces": workspaces,
    }
    return result


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="QA check: EmailBison campaign readiness")
    parser.add_argument("--campaign", action="append", type=int,
                        help="Provider campaign ID (repeatable)")
    parser.add_argument("--workspaces", required=True,
                        help="Path to work/ copy")
    parser.add_argument("--json", dest="json_path",
                        help="Write result JSON here")
    parser.add_argument("--phase", default="pre_push")
    args = parser.parse_args(argv)

    try:
        result = run(
            workspaces=args.workspaces,
            campaign_ids=args.campaign,
            phase=args.phase,
            json_path=args.json_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(3)

    if args.json_path:
        os.makedirs(os.path.dirname(args.json_path) or ".", exist_ok=True)
        with open(args.json_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)

    print(json.dumps(result, indent=2, default=str))

    v = result["verdict"]
    if v == "PASS":
        sys.exit(0)
    elif v == "FAIL":
        sys.exit(1)
    elif v in ("UNCONFIRMED", "VACUOUS"):
        sys.exit(2)
    else:
        sys.exit(3)


if __name__ == "__main__":
    main()
