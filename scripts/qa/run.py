#!/usr/bin/env python3
"""The QA runner: runs checks for a phase, validates results, renders the table.

TASK-292. The runner:

- Imports every registered check for the requested phase.
- Runs it.
- Validates the result against the five invariants of contract §4.
- Writes per-check JSON and a TABLE.md.
- Returns the worst verdict.

The table renderer is ONE function used by both the Slack post and the
refusal text, so they are the same bytes.

Usage:
    py -3 scripts/qa/run.py --phase pre_push \\
        --batch batch-2-2026-09-25 \\
        --campaign 502 --campaign 503 \\
        --workspaces <path to work/ copy>
"""
import argparse
import datetime
import importlib
import json
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.qa import (
    CHECKS, CHECK_BY_ID, CHECK_IDS, PHASES,
    PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR, NOT_IMPLEMENTED,
    VERDICT_TO_EXIT, PHASE_REFUSAL,
    EXIT_ERROR,
    worst_verdict, validate_result,
)


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _run_id():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H-%MZ")


def _load_check_module(module_name):
    """Import a check module by dotted name. Returns the module or None."""
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def _not_implemented_result(check_id, phase):
    """The result for a check whose module does not exist."""
    return {
        "check": check_id,
        "phase": phase,
        "verdict": NOT_IMPLEMENTED,
        "subjects": 0,
        "clean": 0,
        "rules": {},
        "counts": {},
        "offenders": {},
        "unverifiable": {},
        "vacuous_reason": "check module not yet implemented",
        "measured_at": _now_iso(),
        "not_implemented": True,
    }


def _error_result(check_id, phase, message):
    """The result for a check that broke."""
    return {
        "check": check_id,
        "phase": phase,
        "verdict": ERROR,
        "subjects": 0,
        "clean": 0,
        "rules": {},
        "counts": {},
        "offenders": {},
        "unverifiable": {},
        "vacuous_reason": None,
        "error": message,
        "measured_at": _now_iso(),
    }


def run_phase(phase, *, batch=None, campaigns=None, workspaces=None,
              run_id=None, output_dir=None, extra_kwargs=None):
    """Run every blocking check for the phase.

    Returns (results_list, worst_verdict_str, exit_code).
    """
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase!r}; expected one of {PHASES}")

    run_id = run_id or _run_id()
    if output_dir is None:
        output_dir = os.path.join(_ROOT, "work", "qa", run_id)
    os.makedirs(output_dir, exist_ok=True)

    extra_kwargs = extra_kwargs or {}
    results = []
    verdicts = []

    for entry in CHECKS:
        if entry.phase != phase:
            continue
        if not entry.blocking:
            continue

        check_id = entry.check_id
        module = _load_check_module(entry.module)

        if module is None:
            result = _not_implemented_result(check_id, phase)
        else:
            try:
                kwargs = {"phase": phase}
                if batch:
                    kwargs["batch"] = batch
                if campaigns:
                    kwargs["campaigns"] = campaigns
                if workspaces:
                    kwargs["workspaces"] = workspaces
                kwargs.update(extra_kwargs)
                result = module.run(**kwargs)
            except Exception as exc:
                result = _error_result(check_id, phase, f"{exc}\n{traceback.format_exc()}")

        # Validate the result against the five invariants.
        if not result.get("not_implemented"):
            problems = validate_result(result)
            if problems:
                result["verdict"] = ERROR
                result["validation_problems"] = problems

        verdict = result.get("verdict", ERROR)
        verdicts.append(verdict)
        results.append(result)

        # Write per-check JSON.
        json_path = os.path.join(output_dir, f"{check_id}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)

    worst = worst_verdict(verdicts) if verdicts else VACUOUS
    exit_code = VERDICT_TO_EXIT.get(worst, EXIT_ERROR)

    # Render the table.
    table = render_table(results, phase=phase, batch=batch,
                         campaigns=campaigns, run_id=run_id,
                         workspaces=workspaces)

    # Write TABLE.md.
    table_path = os.path.join(output_dir, "TABLE.md")
    with open(table_path, "w", encoding="utf-8") as f:
        f.write(table)

    return results, worst, exit_code, table, output_dir


# --------------------------------------------------------- the table renderer
#
# ONE renderer used by both the Slack post and the refusal text, so they
# are the same bytes. Every registered check gets a row.

def render_table(results, *, phase="pre_push", batch=None, campaigns=None,
                 run_id=None, workspaces=None):
    """Render the QA table.

    One row per registered check for this phase. Checks from other phases
    get a row with '-' and the phase named.

    No prospect ids in the table; a path to the artefact.
    """
    commit = _current_commit()
    now = _now_iso()
    campaign_str = ", ".join(str(c) for c in (campaigns or [])) or "-"
    batch_str = batch or "-"

    # Determine overall status.
    verdicts = [r.get("verdict", ERROR) for r in results]
    worst = worst_verdict(verdicts) if verdicts else VACUOUS
    phase_refusal = PHASE_REFUSAL.get(phase, {})
    action = phase_refusal.get(worst, "REFUSE")
    if worst == PASS:
        status_line = "CLEARED"
    elif action == "REFUSE":
        status_line = "REFUSED"
    elif action == "CRITICAL":
        status_line = "CRITICAL"
    elif action == "RETRY":
        status_line = "RETRY"
    else:
        status_line = str(action).upper()

    # Count total subjects.
    total_subjects = sum(r.get("subjects", 0) for r in results)

    lines = []
    lines.append(
        f"QA · {batch_str} · {phase} · {status_line}")
    lines.append(
        f"campaigns {campaign_str} · {total_subjects} leads · "
        f"commit {commit} · {now}")
    lines.append("")

    # Header row.
    lines.append(
        f"{'check':<22} {'verdict':<16} {'subj':>5} {'clean':>6}  offending")
    lines.append("-" * 80)

    # One row per registered check for this phase.
    results_by_check = {r.get("check"): r for r in results}
    for entry in CHECKS:
        if entry.phase != phase:
            # Checks from other phases: '-' row.
            lines.append(
                f"{entry.check_id:<22} {'-':<16} {'-':>5} {'-':>6}  "
                f"{entry.phase}, not run")
            continue

        result = results_by_check.get(entry.check_id)
        if result is None:
            lines.append(
                f"{entry.check_id:<22} {'-':<16} {'-':>5} {'-':>6}  "
                f"not run")
            continue

        verdict = result.get("verdict", ERROR)
        subjects = result.get("subjects", 0)
        clean = result.get("clean", 0)
        offending = _offending_summary(result)
        lines.append(
            f"{entry.check_id:<22} {verdict:<16} {subjects:>5} {clean:>6}  "
            f"{offending}")

    lines.append("")

    # Footer.
    if worst != PASS:
        lines.append(
            f"REFUSED. Nothing was written to either provider.")
    if run_id:
        lines.append(f"offending ids: work/qa/{run_id}/TABLE.md")
    if workspaces:
        lines.append(f"workspaces: {workspaces}")

    return "\n".join(lines) + "\n"


def _offending_summary(result):
    """Summarise offenders for the table. Counts in the channel, ids in file."""
    offenders = result.get("offenders") or {}
    if not offenders:
        vacuous_reason = result.get("vacuous_reason")
        if result.get("verdict") == VACUOUS and vacuous_reason:
            return vacuous_reason
        if result.get("not_implemented"):
            return "not yet implemented"
        if result.get("verdict") == NOT_IMPLEMENTED:
            return "not yet implemented"
        return "-"

    parts = []
    total = 0
    for rule, ids in offenders.items():
        count = len(ids) if isinstance(ids, list) else 0
        total += count
        if count > 0:
            parts.append(f"{count} {rule}")
    if not parts:
        return "-"
    return f"{total} ({', '.join(parts)})"


def _current_commit():
    """The current commit SHA, short."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=_ROOT)
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# --------------------------------------------------------- CLI entry point

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="QA runner: run checks for a phase and render the table.")
    parser.add_argument("--phase", required=True, choices=PHASES,
                        help="Which phase to run.")
    parser.add_argument("--batch", default=None,
                        help="Batch id.")
    parser.add_argument("--campaign", action="append", default=None,
                        help="Campaign id (repeatable).")
    parser.add_argument("--workspaces", required=True,
                        help="Path to a copy of production work/.")
    parser.add_argument("--run-id", default=None,
                        help="Override the run id.")
    parser.add_argument("--table", action="store_true",
                        help="Print the table to stdout.")
    args = parser.parse_args(argv)

    results, worst, exit_code, table, output_dir = run_phase(
        args.phase,
        batch=args.batch,
        campaigns=args.campaign,
        workspaces=args.workspaces,
        run_id=args.run_id,
    )

    if args.table or True:
        print(table)

    print(f"Verdict: {worst} (exit {exit_code})")
    print(f"Artefacts: {output_dir}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
