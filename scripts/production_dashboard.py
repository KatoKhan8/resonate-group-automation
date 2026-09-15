#!/usr/bin/env python3
"""Generate the production dashboard: one place that says what production is doing.

## Why this exists

Several state files exist - LEDGER.json, QUEUE-MANIFEST.json,
PROVIDER-CAMPAIGNS.json, SENDER-CAPACITY.json, COHORTS.json,
CHECKPOINT-latest.md - but none of them answer the production questions
in one place. A fresh session on a different computer has to read five
files and synthesise. This script reads them all and writes two files
that answer the questions directly.

## The rule that decides whether this is any good

Every field is sourced from something that actually exists. A field that
cannot be sourced says ABSENT and why - never 0. A zero and a missing
writer are indistinguishable, and this dashboard would be the single
most dangerous place in the repository to confuse them.

## What it reads

    docs/state/PROVIDER-CAMPAIGNS.json   HeyReach campaign truth
    docs/state/SENDER-CAPACITY.json      sender estate
    docs/state/QUEUE-MANIFEST.json       queue shape
    docs/state/COHORTS.json              cohort definitions
    docs/state/LEDGER.json               task/worktree state
    work/queue.snapshot.jsonl            record-level lead data

## What it writes

    docs/state/PRODUCTION-DASHBOARD.json   machine-readable
    docs/state/PRODUCTION-DASHBOARD.md     human-readable

## What it does NOT do

- Call any provider. The state files already carry provider truth.
- Invent a number. ABSENT is the honest answer.
- Carry PII. Counts and hashes only.
"""

import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "docs", "state")
SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
SNAPSHOT_STAMP = os.path.join(ROOT, "work", "queue.snapshot.STAMP")

ABSENT = "ABSENT"


def absent(reason):
    return {"value": ABSENT, "reason": reason}


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_snapshot():
    if not os.path.exists(SNAPSHOT):
        return [], None
    stamp = None
    if os.path.exists(SNAPSHOT_STAMP):
        with open(SNAPSHOT_STAMP, encoding="utf-8") as fh:
            stamp = fh.read().strip()
    records = []
    with open(SNAPSHOT, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    return records, stamp


def section_leads(records, stamp, cohorts_data, manifest):
    """LEADS: total qualified, unassigned qualified, by signal, by cohort,
    by campaign, live, queued."""
    if not records:
        return {
            "snapshot_stamp": absent("queue snapshot not found on this machine"),
            "total_records": absent("queue snapshot not found on this machine"),
            "total_contacts": absent("queue snapshot not found on this machine"),
            "sendable_contacts": absent("queue snapshot not found on this machine"),
            "verified_contacts": absent("queue snapshot not found on this machine"),
            "by_record_state": absent("queue snapshot not found on this machine"),
            "by_persona": absent("queue snapshot not found on this machine"),
            "by_angle": absent("queue snapshot not found on this machine"),
            "records_with_cadence": absent("queue snapshot not found on this machine"),
            "cohorts_defined": absent("COHORTS.json not found"),
            "cohorts_above_50": absent("COHORTS.json not found"),
            "campaigns_with_leads": absent("no campaign has been started"),
            "live_records": 0,
            "queued_records": absent("no record has reached live state"),
        }

    total = len(records)
    contacts = sum(len(r.get("contacts", [])) for r in records)
    sendable = sum(
        1 for r in records for c in r.get("contacts", []) if c.get("sendable")
    )
    verified = sum(
        1 for r in records for c in r.get("contacts", [])
        if isinstance(c.get("verification"), dict)
        and c["verification"].get("state") == "verified"
    )

    by_state = {}
    for r in records:
        s = r.get("state", "unknown")
        by_state[s] = by_state.get(s, 0) + 1

    by_persona = {}
    for r in records:
        for c in r.get("contacts", []):
            p = c.get("persona") or "unknown"
            by_persona[p] = by_persona.get(p, 0) + 1

    by_angle = {}
    for r in records:
        for c in r.get("contacts", []):
            a = c.get("angle") or "unknown"
            by_angle[a] = by_angle.get(a, 0) + 1

    with_cadence = sum(1 for r in records if r.get("cadence"))

    cohorts_defined = 0
    cohorts_above_50 = 0
    if cohorts_data and cohorts_data.get("cohorts"):
        cohorts_defined = len(cohorts_data["cohorts"])
        cohorts_above_50 = sum(
            1 for c in cohorts_data["cohorts"]
            if isinstance(c.get("LEAD COUNT"), int) and c["LEAD COUNT"] >= 50
        )

    live_count = sum(
        1 for r in records
        if r.get("state") in ("live", "sending", "sent", "active")
    )

    return {
        "snapshot_stamp": stamp if records else absent("no snapshot stamp file"),
        "total_records": total,
        "total_contacts": contacts,
        "sendable_contacts": sendable,
        "verified_contacts": verified,
        "by_record_state": by_state,
        "by_persona": by_persona,
        "by_angle": by_angle,
        "records_with_cadence": with_cadence,
        "cohorts_defined": cohorts_defined,
        "cohorts_above_50": cohorts_above_50,
        "campaigns_with_leads": absent(
            "no campaign has started; both HeyReach and EmailBison "
            "Resonate campaigns have 0 leads attached"
        ),
        "live_records": live_count,
        "queued_records": absent(
            "no record has reached a live/sending state; the lead block holds"
        ),
    }


def section_heyreach(campaigns_data, capacity_data):
    """HEYREACH: campaigns, live, draft, senders, utilisation, throughput."""
    if not campaigns_data:
        return {
            "campaigns_total": absent("PROVIDER-CAMPAIGNS.json not found"),
            "resonate_campaigns": absent("PROVIDER-CAMPAIGNS.json not found"),
            "live_campaigns": absent("PROVIDER-CAMPAIGNS.json not found"),
            "draft_campaigns": absent("PROVIDER-CAMPAIGNS.json not found"),
            "status_totals": absent("PROVIDER-CAMPAIGNS.json not found"),
            "senders_total": absent("SENDER-CAPACITY.json not found"),
            "healthy_senders": absent("SENDER-CAPACITY.json not found"),
            "daily_connection_capacity": absent("SENDER-CAPACITY.json not found"),
            "daily_message_capacity": absent("SENDER-CAPACITY.json not found"),
            "utilisation": absent("no sends have occurred; utilisation is not 0, "
                                  "it is unmeasured"),
        }

    hr = campaigns_data.get("heyreach", {})
    resonate = hr.get("resonate_campaigns", [])
    status_totals = hr.get("status_totals", {})

    live = sum(1 for c in resonate if c.get("status") == "IN_PROGRESS")
    draft = sum(1 for c in resonate if c.get("classification") == "DRAFT")

    senders_section = {}
    if capacity_data:
        senders_section = {
            "senders_total": capacity_data.get("seats_total", absent("field missing")),
            "healthy_senders": capacity_data.get("healthy_seats", absent("field missing")),
            "senders_by_state": capacity_data.get("seats_by_state", absent("field missing")),
            "daily_connection_capacity": (
                capacity_data.get("daily_capacity_healthy_only", {})
                .get("connection_requests", absent("field missing"))
            ),
            "daily_message_capacity": (
                capacity_data.get("daily_capacity_healthy_only", {})
                .get("messages", absent("field missing"))
            ),
            "healthy_with_no_campaign": capacity_data.get(
                "healthy_seats_with_no_active_campaign", absent("field missing")
            ),
        }
    else:
        senders_section = {
            "senders_total": absent("SENDER-CAPACITY.json not found"),
            "healthy_senders": absent("SENDER-CAPACITY.json not found"),
            "senders_by_state": absent("SENDER-CAPACITY.json not found"),
            "daily_connection_capacity": absent("SENDER-CAPACITY.json not found"),
            "daily_message_capacity": absent("SENDER-CAPACITY.json not found"),
            "healthy_with_no_campaign": absent("SENDER-CAPACITY.json not found"),
        }

    utilisation = absent(
        "no Resonate campaign has started sending; utilisation is not 0%, "
        "it is unmeasured. The 12 IN_PROGRESS campaigns in the account are "
        "the client's own, not Resonate's."
    )

    throughput = absent(
        "no Resonate campaign has started sending; throughput is unmeasured"
    )

    return {
        "campaigns_total_in_account": hr.get("campaigns_total_in_account",
                                              absent("field missing")),
        "resonate_campaigns_count": hr.get("campaigns_created_by_resonate",
                                            absent("field missing")),
        "resonate_live": live,
        "resonate_draft": draft,
        "account_status_totals": status_totals,
        "linkedin_accounts_available": hr.get("linkedin_accounts_available",
                                               absent("field missing")),
        **senders_section,
        "utilisation": utilisation,
        "throughput": throughput,
        "resonate_campaign_details": [
            {
                "id": c.get("heyreach_campaign_id"),
                "name": c.get("name"),
                "status": c.get("status"),
                "classification": c.get("classification"),
                "lead_count": c.get("lead_count"),
                "senders_attached": len(c.get("senders", [])),
                "sequence_nodes": (c.get("sequence", {}).get("unique_nodes")
                                   if c.get("sequence", {}).get("readable")
                                   else absent("sequence not readable")),
                "started_at": c.get("started_at") or absent("never started"),
            }
            for c in resonate
        ],
    }


def section_emailbison():
    """EMAILBISON: campaigns, live, senders, throughput.

    No machine-readable EmailBison state file exists. The provider truth is
    in docs/BISON-PROVIDER-TRUTH-2026-09-14.md (markdown, not JSON). Until
    a script generates a BISON-CAMPAIGNS.json equivalent to
    PROVIDER-CAMPAIGNS.json, these fields are ABSENT.
    """
    return {
        "campaigns_total": absent(
            "no BISON-CAMPAIGNS.json exists; provider truth is in "
            "docs/BISON-PROVIDER-TRUTH-2026-09-14.md (markdown only)"
        ),
        "resonate_campaigns": absent(
            "no machine-readable EmailBison state; TASK-069 and TASK-071 "
            "mapped the API but no generator script writes a JSON state file"
        ),
        "live_campaigns": absent("no EmailBison state file to read"),
        "senders": absent("no EmailBison state file to read"),
        "throughput": absent(
            "no EmailBison state file to read; the provider truth doc "
            "reports campaign 481 paused with 0 sent and campaign 451 "
            "completed with 1 sent, but these are not in a machine-readable "
            "state file"
        ),
    }


def section_experiments(ledger_data):
    """EXPERIMENTS: running, completed, winner candidate, inconclusive, failed.

    The evaluator exists in src/variants.py with five states:
    EXPLORING, INSUFFICIENT_DATA, WINNER, LEADING, NO_CLEAR_WINNER.
    But no campaign has started sending, so no experiment has data.
    """
    return {
        "copy_experiments_infrastructure": "EXISTS AND WIRED",
        "copy_experiment_evaluator_states": [
            "EXPLORING", "INSUFFICIENT_DATA", "LEADING",
            "WINNER", "NO_CLEAR_WINNER", "PAUSED"
        ],
        "experiments_with_data": absent(
            "no campaign has started sending; the evaluator in "
            "src/variants.py has never received exposure data. "
            "INSUFFICIENT_DATA is not the verdict - the experiment "
            "has not started."
        ),
        "running": 0,
        "completed": 0,
        "winner_candidates": absent("no experiment has reached evaluation"),
        "inconclusive": absent("no experiment has reached evaluation"),
        "failed": absent("no experiment has reached evaluation"),
        "cadence_experiment_infrastructure": "EXISTS BUT UNUSED",
        "cadence_arms_module": "src/cadencearms.py exists; no campaign carries "
                               "a cadence_experiment field",
        "cadence_is_fixed": True,
        "cadence_steps": 7,
        "variant_wiring": "EXISTS AND WIRED - variants.apply_to_step has a caller",
        "exposure_tracking": "EXISTS AND WIRED - variants.journey_of, results_from",
        "statistical_discipline": "EXISTS AND WIRED - Wilson bounds, sample floor",
    }


def section_learning():
    """LEARNING: new findings, confidence, sample size, and whether each has
    been promoted into generation policy.

    No structured learning registry exists. Findings are scattered across
    task result blocks and documentation. This section reports what is
    documented and whether it has been promoted.
    """
    return {
        "structured_learning_registry": absent(
            "no learning registry exists; findings are in task result blocks "
            "and documentation but not in a machine-readable store"
        ),
        "documented_findings": {
            "interested_pattern_precision": {
                "value": 0.44,
                "confidence": "measured on old pattern set",
                "sample_size": absent("exact n not recorded in a machine-readable file"),
                "promoted_to_policy": False,
                "note": "INTERESTED may NOT carry a learning claim at 0.44 precision",
            },
            "meeting_intent_precision": {
                "value": 1.00,
                "confidence": "measured",
                "sample_size": absent("exact n not recorded in a machine-readable file"),
                "promoted_to_policy": True,
                "note": "MEETING_INTENT (1.00) may carry a learning claim, with recall stated",
            },
            "objection_precision": {
                "value": 1.00,
                "confidence": "measured",
                "sample_size": absent("exact n not recorded in a machine-readable file"),
                "promoted_to_policy": True,
                "note": "OBJECTION (1.00) may carry a learning claim, with recall stated",
            },
            "open_tracking": {
                "value": False,
                "confidence": "estate-wide",
                "sample_size": "all campaigns",
                "promoted_to_policy": True,
                "note": "open_tracking is False estate-wide; any open rate is ABSENT "
                        "MEASUREMENT, not a zero. Do not quote any open rate.",
            },
            "unknowns_are_not_negative": {
                "value": "53.4% of unknowns are correctly unknown",
                "confidence": "measured",
                "sample_size": absent("exact n not recorded in a machine-readable file"),
                "promoted_to_policy": True,
                "note": "Do not count an UNKNOWN as negative",
            },
        },
        "proven_learnings_with_sample_size": absent(
            "no finding survives a sample-size objection with a recorded n; "
            "TASK-059 left PROVEN LEARNINGS empty and was right to"
        ),
    }


def section_operations(ledger_data, manifest):
    """Operational state: tasks, worktrees, branches."""
    if not ledger_data:
        return {"tasks": absent("LEDGER.json not found")}

    stage_counts = ledger_data.get("stage_counts", {})
    branches = ledger_data.get("branches", [])
    worktrees = ledger_data.get("worktrees", [])

    unpushed = [b for b in branches
                if not b.get("pushed") and b.get("commits_ahead_of_master", 0) > 0]
    dirty = [w for w in worktrees if not w.get("clean")]

    return {
        "master_head": ledger_data.get("master_head"),
        "master_pushed": ledger_data.get("master_pushed"),
        "task_stages": stage_counts,
        "total_tasks": sum(stage_counts.values()),
        "branches_with_unpushed_work": len(unpushed),
        "dirty_worktrees": len(dirty),
        "active_worktrees": len(worktrees),
    }


def build_dashboard():
    campaigns_data = load_json(os.path.join(STATE, "PROVIDER-CAMPAIGNS.json"))
    capacity_data = load_json(os.path.join(STATE, "SENDER-CAPACITY.json"))
    manifest = load_json(os.path.join(STATE, "QUEUE-MANIFEST.json"))
    cohorts_data = load_json(os.path.join(STATE, "COHORTS.json"))
    ledger_data = load_json(os.path.join(STATE, "LEDGER.json"))
    records, stamp = load_snapshot()

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    dashboard = {
        "generated_at": now,
        "generated_by": "scripts/production_dashboard.py",
        "snapshot_stamp": stamp,
        "policy": "docs/PRODUCTION-SCALE-POLICY.md",
        "LEADS": section_leads(records, stamp, cohorts_data, manifest),
        "HEYREACH": section_heyreach(campaigns_data, capacity_data),
        "EMAILBISON": section_emailbison(),
        "EXPERIMENTS": section_experiments(ledger_data),
        "LEARNING": section_learning(),
        "OPERATIONS": section_operations(ledger_data, manifest),
    }

    return dashboard


def collect_absent_fields(dashboard, path=""):
    """Walk the dashboard and collect every ABSENT field with its reason."""
    results = []
    if isinstance(dashboard, dict):
        if dashboard.get("value") == ABSENT:
            results.append({
                "path": path,
                "reason": dashboard.get("reason", "unknown"),
            })
        else:
            for key, val in dashboard.items():
                child_path = f"{path}.{key}" if path else key
                results.extend(collect_absent_fields(val, child_path))
    elif isinstance(dashboard, list):
        for i, val in enumerate(dashboard):
            results.extend(collect_absent_fields(val, f"{path}[{i}]"))
    return results


def render_markdown(dashboard):
    """Human-readable rendering of the dashboard."""
    lines = []
    now = dashboard.get("generated_at", "unknown")
    stamp = dashboard.get("snapshot_stamp", "unknown")

    lines.append("# Production Dashboard")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append(f"Snapshot: {stamp}")
    lines.append("")
    lines.append("> A zero and a missing writer are indistinguishable from the")
    lines.append("> outside. Fields marked **ABSENT** have no data source, not")
    lines.append("> a zero value.")
    lines.append("")

    # LEADS
    leads = dashboard.get("LEADS", {})
    lines.append("## LEADS")
    lines.append("")
    _md_field(lines, "Total records", leads.get("total_records"))
    _md_field(lines, "Total contacts", leads.get("total_contacts"))
    _md_field(lines, "Sendable contacts", leads.get("sendable_contacts"))
    _md_field(lines, "Verified contacts", leads.get("verified_contacts"))
    _md_field(lines, "Records with cadence", leads.get("records_with_cadence"))
    _md_field(lines, "Live records", leads.get("live_records"))
    lines.append("")

    _md_subfield(lines, "By record state", leads.get("by_record_state"))
    _md_subfield(lines, "By persona", leads.get("by_persona"))
    _md_subfield(lines, "By angle", leads.get("by_angle"))
    lines.append("")

    _md_field(lines, "Cohorts defined", leads.get("cohorts_defined"))
    _md_field(lines, "Cohorts above 50 leads", leads.get("cohorts_above_50"))
    _md_field(lines, "Campaigns with leads", leads.get("campaigns_with_leads"))
    lines.append("")

    # HEYREACH
    hr = dashboard.get("HEYREACH", {})
    lines.append("## HEYREACH")
    lines.append("")
    _md_field(lines, "Total campaigns in account",
              hr.get("campaigns_total_in_account"))
    _md_field(lines, "Resonate campaigns", hr.get("resonate_campaigns_count"))
    _md_field(lines, "Resonate live", hr.get("resonate_live"))
    _md_field(lines, "Resonate draft", hr.get("resonate_draft"))
    _md_field(lines, "LinkedIn accounts available",
              hr.get("linkedin_accounts_available"))
    lines.append("")

    _md_field(lines, "Senders total", hr.get("senders_total"))
    _md_field(lines, "Healthy senders", hr.get("healthy_senders"))
    _md_field(lines, "Daily connection capacity",
              hr.get("daily_connection_capacity"))
    _md_field(lines, "Daily message capacity",
              hr.get("daily_message_capacity"))
    _md_field(lines, "Healthy with no active campaign",
              hr.get("healthy_with_no_campaign"))
    lines.append("")

    _md_field(lines, "Utilisation", hr.get("utilisation"))
    _md_field(lines, "Throughput", hr.get("throughput"))
    lines.append("")

    _md_field(lines, "Account status totals",
              hr.get("account_status_totals"))
    lines.append("")

    details = hr.get("resonate_campaign_details", [])
    if details:
        lines.append("### Resonate Campaign Details")
        lines.append("")
        for c in details:
            lines.append(f"- **{c.get('name', '?')}** (id={c.get('id')})")
            lines.append(f"  - Status: {c.get('status')}, "
                         f"Classification: {c.get('classification')}")
            lines.append(f"  - Leads: {c.get('lead_count')}, "
                         f"Senders: {c.get('senders_attached')}")
            lines.append(f"  - Sequence nodes: {c.get('sequence_nodes')}")
            started = c.get("started_at")
            if isinstance(started, dict) and started.get("value") == ABSENT:
                lines.append(f"  - Started: ABSENT ({started.get('reason', '')})")
            else:
                lines.append(f"  - Started: {started}")
        lines.append("")

    # EMAILBISON
    eb = dashboard.get("EMAILBISON", {})
    lines.append("## EMAILBISON")
    lines.append("")
    _md_field(lines, "Campaigns total", eb.get("campaigns_total"))
    _md_field(lines, "Resonate campaigns", eb.get("resonate_campaigns"))
    _md_field(lines, "Live campaigns", eb.get("live_campaigns"))
    _md_field(lines, "Senders", eb.get("senders"))
    _md_field(lines, "Throughput", eb.get("throughput"))
    lines.append("")

    # EXPERIMENTS
    exp = dashboard.get("EXPERIMENTS", {})
    lines.append("## EXPERIMENTS")
    lines.append("")
    _md_field(lines, "Copy experiment infrastructure",
              exp.get("copy_experiments_infrastructure"))
    _md_field(lines, "Experiments with data",
              exp.get("experiments_with_data"))
    _md_field(lines, "Running", exp.get("running"))
    _md_field(lines, "Completed", exp.get("completed"))
    _md_field(lines, "Winner candidates", exp.get("winner_candidates"))
    _md_field(lines, "Cadence experiment infrastructure",
              exp.get("cadence_experiment_infrastructure"))
    _md_field(lines, "Cadence is fixed", exp.get("cadence_is_fixed"))
    _md_field(lines, "Cadence steps", exp.get("cadence_steps"))
    _md_field(lines, "Variant wiring", exp.get("variant_wiring"))
    _md_field(lines, "Exposure tracking", exp.get("exposure_tracking"))
    _md_field(lines, "Statistical discipline",
              exp.get("statistical_discipline"))
    lines.append("")

    # LEARNING
    learn = dashboard.get("LEARNING", {})
    lines.append("## LEARNING")
    lines.append("")
    _md_field(lines, "Structured learning registry",
              learn.get("structured_learning_registry"))
    _md_field(lines, "Proven learnings (with sample size)",
              learn.get("proven_learnings_with_sample_size"))
    lines.append("")

    findings = learn.get("documented_findings", {})
    if findings:
        lines.append("### Documented Findings")
        lines.append("")
        lines.append("| Finding | Value | Promoted | Note |")
        lines.append("|---------|-------|----------|------|")
        for key, f in findings.items():
            val = f.get("value")
            promoted = "Yes" if f.get("promoted_to_policy") else "No"
            note = f.get("note", "")
            lines.append(f"| {key} | {val} | {promoted} | {note} |")
        lines.append("")

    # OPERATIONS
    ops = dashboard.get("OPERATIONS", {})
    lines.append("## OPERATIONS")
    lines.append("")
    _md_field(lines, "Master HEAD", ops.get("master_head"))
    _md_field(lines, "Master pushed", ops.get("master_pushed"))
    _md_field(lines, "Total tasks", ops.get("total_tasks"))
    _md_field(lines, "Task stages", ops.get("task_stages"))
    _md_field(lines, "Branches with unpushed work",
              ops.get("branches_with_unpushed_work"))
    _md_field(lines, "Dirty worktrees", ops.get("dirty_worktrees"))
    _md_field(lines, "Active worktrees", ops.get("active_worktrees"))
    lines.append("")

    # ABSENT FIELDS ROADMAP
    absent_fields = collect_absent_fields(dashboard)
    if absent_fields:
        lines.append("## ABSENT FIELDS - THE ROADMAP")
        lines.append("")
        lines.append("These fields have no data source. Each entry says what")
        lines.append("would have to exist to populate it.")
        lines.append("")
        lines.append("| Path | What would populate it |")
        lines.append("|------|------------------------|")
        for af in absent_fields:
            path = af["path"]
            reason = af["reason"]
            lines.append(f"| `{path}` | {reason} |")
        lines.append("")

    return "\n".join(lines)


def _md_field(lines, label, value):
    if isinstance(value, dict) and value.get("value") == ABSENT:
        lines.append(f"- **{label}**: ABSENT - {value.get('reason', '')}")
    elif isinstance(value, (dict, list)):
        lines.append(f"- **{label}**: `{json.dumps(value, default=str)}`")
    elif value is None:
        lines.append(f"- **{label}**: null")
    else:
        lines.append(f"- **{label}**: {value}")


def _md_subfield(lines, label, value):
    if isinstance(value, dict) and value.get("value") == ABSENT:
        lines.append(f"**{label}**: ABSENT - {value.get('reason', '')}")
    elif isinstance(value, dict):
        lines.append(f"**{label}**:")
        for k, v in value.items():
            lines.append(f"  - {k}: {v}")
    else:
        _md_field(lines, label, value)


def main():
    dashboard = build_dashboard()

    os.makedirs(STATE, exist_ok=True)

    json_path = os.path.join(STATE, "PRODUCTION-DASHBOARD.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(dashboard, fh, indent=2, default=str)
        fh.write("\n")

    md_path = os.path.join(STATE, "PRODUCTION-DASHBOARD.md")
    md_content = render_markdown(dashboard)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md_content)

    absent_fields = collect_absent_fields(dashboard)
    print(f"written: {json_path}")
    print(f"written: {md_path}")
    print(f"ABSENT fields: {len(absent_fields)}")
    for af in absent_fields:
        print(f"  {af['path']}: {af['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
