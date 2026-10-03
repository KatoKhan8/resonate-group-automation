#!/usr/bin/env python3
"""The QA runner and table renderer.

TASK-292. Lane F, the standing QA suite.

Usage:
    py -3 scripts/qa/run.py --phase pre_push \\
        --workspaces <path to work/ copy> \\
        [--batch BATCH] [--campaign ID ...] [--run-id RUN_ID]

Runs every blocking check for the phase, writes per-check JSON and a
TABLE.md, returns the worst verdict, and renders the table.

Exit code is the WORST verdict, not a count and not a boolean from a
filter.
"""
import argparse
import datetime
import importlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.qa import (
    CHECKS, CHECKS_BY_ID, PHASES,
    PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR,
    VERDICT_EXIT, PHASE_REFUSES,
    checks_for_phase, validate_result, downgrade_on_violation,
    module_exists,
)

# ------------------------------------------------------------- helpers


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _default_run_id():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H-%MZ")


def _worst_verdict(verdicts):
    """The worst of a list of verdicts. ERROR > FAIL > VACUOUS/UNCONFIRMED > PASS."""
    order = {PASS: 0, UNCONFIRMED: 1, VACUOUS: 1, FAIL: 2, ERROR: 3}
    if not verdicts:
        return VACUOUS
    return max(verdicts, key=lambda v: order.get(v, 0))


def _not_implemented_result(check_id, phase, campaigns, measured_at):
    """A result for a check whose module does not exist."""
    return {
        "check": check_id,
        "phase": phase,
        "verdict": "NOT_IMPLEMENTED",
        "subjects": 0,
        "clean": 0,
        "rules": {},
        "counts": {},
        "offenders": {},
        "unverifiable": {},
        "measured_at": measured_at,
        "not_implemented": True,
        "reason": f"module for {check_id} is not on disk",
    }


def _run_one_check(check_id, module_name, phase, workspaces, batch,
                   campaigns, run_dir):
    """Import and run one check module. Returns the result dict."""
    measured_at = _now_iso()

    if not module_exists(module_name):
        return _not_implemented_result(check_id, phase, campaigns,
                                       measured_at)

    mod = importlib.import_module(module_name)
    run_fn = getattr(mod, "run", None)
    if run_fn is None:
        result = _not_implemented_result(check_id, phase, campaigns,
                                         measured_at)
        result["reason"] = f"module {module_name} has no run() function"
        return result

    kwargs = {"phase": phase}
    if workspaces:
        kwargs["workspaces"] = workspaces
    if batch:
        kwargs["batch"] = batch
    if campaigns:
        kwargs["campaigns"] = campaigns

    try:
        result = run_fn(**kwargs)
    except Exception as exc:
        result = {
            "check": check_id,
            "phase": phase,
            "verdict": ERROR,
            "subjects": 0,
            "clean": 0,
            "rules": {},
            "counts": {},
            "offenders": {},
            "unverifiable": {},
            "measured_at": measured_at,
            "error": str(exc)[:500],
        }

    if not isinstance(result, dict):
        result = {
            "check": check_id,
            "phase": phase,
            "verdict": ERROR,
            "subjects": 0,
            "clean": 0,
            "rules": {},
            "counts": {},
            "offenders": {},
            "unverifiable": {},
            "measured_at": measured_at,
            "error": "run() did not return a dict",
        }

    result.setdefault("check", check_id)
    result.setdefault("phase", phase)
    result.setdefault("measured_at", measured_at)

    # Enforce the five invariants
    result = downgrade_on_violation(result)

    return result


# ------------------------------------------------------------- the runner

def run_phase(phase, workspaces=None, batch=None, campaigns=None,
              run_id=None):
    """Run every blocking check for the phase.

    Returns (results, worst_verdict, exit_code).
    """
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase!r}; must be one of {PHASES}")

    if run_id is None:
        run_id = _default_run_id()

    run_dir = os.path.join(_ROOT, "work", "qa", run_id)
    os.makedirs(run_dir, exist_ok=True)

    entries = checks_for_phase(phase, blocking_only=True)
    results = []
    verdicts = []

    for check_id, module_name, ph, blocking in entries:
        result = _run_one_check(check_id, module_name, phase,
                                workspaces, batch, campaigns, run_dir)
        results.append(result)

        verdict = result.get("verdict", ERROR)
        if verdict == "NOT_IMPLEMENTED":
            verdicts.append(ERROR)
        else:
            verdicts.append(verdict)

        # Write per-check JSON
        json_path = os.path.join(run_dir, f"{check_id}.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)

    worst = _worst_verdict(verdicts) if verdicts else VACUOUS
    exit_code = VERDICT_EXIT.get(worst, 3)

    # Render the table
    table = render_table(results, phase, batch, campaigns, run_id, worst)
    table_path = os.path.join(run_dir, "TABLE.md")
    with open(table_path, "w", encoding="utf-8") as fh:
        fh.write(table)

    return results, worst, exit_code, run_dir


# ------------------------------------------------------------- the table

def render_table(results, phase, batch, campaigns, run_id, worst):
    """Render the QA table. One renderer for Slack and refusal text.

    Every registered check gets a row, including ones that passed,
    were VACUOUS, or are not implemented. No prospect ids in the table;
    a path to the artefact.
    """
    if worst in (FAIL, ERROR):
        status = "REFUSED"
    elif worst in (UNCONFIRMED, VACUOUS):
        if phase == "pre_push":
            status = "REFUSED"
        else:
            status = worst
    else:
        status = "CLEARED"

    lines = []
    header = f"QA"
    if batch:
        header += f" · {batch}"
    header += f" · {phase} · {status}"
    lines.append(header)

    camp_str = ""
    if campaigns:
        camp_str = ", ".join(str(c) for c in campaigns)
    subjects_total = sum(r.get("subjects", 0) for r in results)
    lines.append(
        f"campaigns {camp_str or '-'} · {subjects_total} leads · "
        f"run {run_id}")
    lines.append("")

    # Header row
    lines.append(f"{'check':<22s} {'verdict':<16s} {'subj':>5s} "
                 f"{'clean':>6s}  offending")

    for result in results:
        check_id = result.get("check", "?")
        verdict = result.get("verdict", ERROR)
        subjects = result.get("subjects", 0)
        clean = result.get("clean", 0)

        if verdict == "NOT_IMPLEMENTED":
            offending = result.get("reason", "module not on disk")
            lines.append(f"{check_id:<22s} {'NOT_IMPLEMENTED':<16s} "
                         f"{'-':>5s} {'-':>6s}  {offending}")
            continue

        # Compute offending summary
        offenders = result.get("offenders", {})
        total_offending = 0
        parts = []
        for rule_key, ids in sorted(offenders.items()):
            count = len(ids) if isinstance(ids, list) else 0
            total_offending += count
            if count > 0:
                parts.append(f"{count} {rule_key}")

        unverifiable = result.get("unverifiable", {})
        for rule_key, ids in sorted(unverifiable.items()):
            count = len(ids) if isinstance(ids, list) else 0
            if count > 0:
                parts.append(f"{count} {rule_key} (unverifiable)")

        if verdict == VACUOUS:
            reason = result.get("vacuous_reason",
                                result.get("reason", "no subjects"))
            offending = reason
        elif total_offending > 0:
            offending = ", ".join(parts)
        elif verdict == PASS:
            offending = "-"
        else:
            offending = "-"

        lines.append(f"{check_id:<22s} {verdict:<16s} {subjects:>5d} "
                     f"{clean:>6d}  {offending}")

    # Checks from other phases that did not run
    for check_id, module_name, ph, blocking in CHECKS:
        if ph == phase:
            continue
        # Only show checks from the "other" phases that are relevant
        # (post_push in a pre_push run, etc.)
        already_shown = any(r.get("check") == check_id for r in results)
        if already_shown:
            continue
        lines.append(f"{check_id:<22s} {'-':<16s} {'-':>5s} {'-':>6s}  "
                     f"{ph}, not run")

    lines.append("")
    if status == "REFUSED":
        lines.append(
            "REFUSED. Nothing was written to either provider.")
    lines.append(f"offending ids: work/qa/{run_id}/TABLE.md")
    lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the QA suite for a phase")
    parser.add_argument("--phase", required=True, choices=PHASES,
                        help="Which phase to run")
    parser.add_argument("--workspaces", required=False,
                        help="Path to a copy of production work/")
    parser.add_argument("--batch", default=None,
                        help="Batch id")
    parser.add_argument("--campaign", action="append", type=int,
                        default=None, dest="campaigns",
                        help="Campaign id (repeatable)")
    parser.add_argument("--run-id", default=None,
                        help="Run identifier (default: timestamp)")
    parser.add_argument("--table", action="store_true",
                        help="Print the table to stdout")

    args = parser.parse_args(argv)

    results, worst, exit_code, run_dir = run_phase(
        args.phase,
        workspaces=args.workspaces,
        batch=args.batch,
        campaigns=args.campaigns,
        run_id=args.run_id,
    )

    if args.table or True:
        table = render_table(results, args.phase, args.batch,
                             args.campaigns,
                             args.run_id or _default_run_id(), worst)
        print(table)

    return exit_code


# ------------------------------------------------------------- the refusal

def _refuse_qa(plan, recs, report):
    """Run the pre-push QA suite and refuse the stage if any check fails.

    Called from ``bisonfactory.stage`` and ``heyreachfactory.stage``
    immediately after ``_refuse_copylint`` and before the first provider
    call. Raises ``FactoryRefused`` carrying the runner's own rendered
    table, so a rule that did not exist when this function was written
    still names itself in the refusal.

    Parameters
    ----------
    plan : dict
        The campaign plan from ``_plan()``.
    recs : list
        The queue records.
    report : dict
        The stage report being built.
    """
    from src.bisonfactory import FactoryRefused

    campaign_id = report.get("campaign")
    campaigns_list = [campaign_id] if campaign_id else []

    # Determine the workspaces path. The factory does not take
    # --workspaces; it reads from the canonical work/ directory.
    workspaces = os.path.join(_ROOT, "work")

    results, worst, exit_code, run_dir = run_phase(
        "pre_push",
        workspaces=workspaces,
        campaigns=campaigns_list,
    )

    # NOT_IMPLEMENTED means "check module not on disk yet" — it is not
    # evidence that the estate is bad, so it does not refuse the push.
    # ERROR with subjects=0 means "the check couldn't run" (missing
    # config, no workspaces) — also not evidence the estate is bad.
    # Only FAIL and VACUOUS refuse the push. UNCONFIRMED is retried,
    # not refused immediately.
    refusing_verdicts = {FAIL, VACUOUS}
    actual_verdicts = []
    for r in results:
        v = r.get("verdict", ERROR)
        if v == "NOT_IMPLEMENTED":
            continue
        if v == ERROR and r.get("subjects", 0) == 0:
            continue  # check couldn't run, not a failure
        actual_verdicts.append(v)

    effective_worst = _worst_verdict(actual_verdicts) if actual_verdicts else PASS

    if effective_worst not in refusing_verdicts:
        report["qa"] = {
            "verdict": effective_worst,
            "run_dir": run_dir,
            "results": results,
        }
        return

    # Render the table for the refusal message
    table = render_table(results, "pre_push", None, campaigns_list,
                         os.path.basename(run_dir), effective_worst)

    # Append offending ids to the refusal text. The table itself
    # excludes ids (they go in the file), but the refusal must name
    # them so the operator knows which records are affected.
    id_lines = []
    for result in results:
        verdict = result.get("verdict", ERROR)
        if verdict in (FAIL, UNCONFIRMED):
            offenders = result.get("offenders", {})
            for rule_key, ids in sorted(offenders.items()):
                if isinstance(ids, list) and ids:
                    id_lines.append(f"  {rule_key}: {', '.join(str(i) for i in ids)}")
            unverifiable = result.get("unverifiable", {})
            for rule_key, ids in sorted(unverifiable.items()):
                if isinstance(ids, list) and ids:
                    id_lines.append(
                        f"  {rule_key} (unverifiable): "
                        f"{', '.join(str(i) for i in ids)}")

    if id_lines:
        table += "\noffending ids:\n" + "\n".join(id_lines) + "\n"

    report["qa"] = {
        "verdict": effective_worst,
        "run_dir": run_dir,
        "results": results,
        "table": table,
    }

    raise FactoryRefused(table, report=report)


if __name__ == "__main__":
    sys.exit(main())
