#!/usr/bin/env python3
"""The QA runner and table renderer.

TASK-292. Lane F, the standing QA suite.

Usage:
    py -3 scripts/qa/run.py --phase pre_push \\
        --batch batch-2-2026-09-25 \\
        --campaign 502 --campaign 503 \\
        --workspaces <path to work/ copy>

Runs every blocking check for the phase, writes per-check JSON and a
TABLE.md, returns the worst verdict, and renders the table.

The runner asserts the five invariants of contract section 4 on every
result it receives, and downgrades a result that breaks one to ERROR.
It does not trust the check.

A check whose module is listed in CHECKS but does not yet exist reports
NOT_IMPLEMENTED in the table -- not PASS, and not silence.

There is no --skip-qa, no --force, no environment variable that disables
a blocking check. The only escape is blocking=False in CHECKS, in a
commit.
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

from scripts.qa import (
    CHECKS, CHECKS_BY_ID, PHASES,
    PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR, NOT_IMPLEMENTED,
    VERDICT_TO_EXIT, PHASE_REFUSAL,
    worst_verdict, exit_code_for, validate_result,
    load_check_module,
)

# ------------------------------------------------------------- helpers


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _run_id():
    """A timestamp-based run id for the artefact directory."""
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H-%MZ")


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


# ------------------------------------------------------------- NOT_IMPLEMENTED

def _not_implemented_result(check_id, phase):
    """The result for a check whose module does not exist yet."""
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
        "not_implemented": True,
        "vacuous_reason": "check module not yet implemented",
        "measured_at": _now_iso(),
    }


# ------------------------------------------------------------- the runner

def run_phase(phase, *, batch=None, campaigns=None, workspaces=None,
              live_reads=True, out_dir=None):
    """Run every registered check for a phase.

    Returns (results, table_text, worst).
    results is a list of result dicts, one per registered check for the
    phase (including NOT_IMPLEMENTED ones).
    table_text is the rendered table.
    worst is the worst verdict across all checks.
    """
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase!r}; expected one of {PHASES}")

    results = []
    for check_id, module_name, check_phase, blocking in CHECKS:
        if check_phase != phase:
            continue

        mod = load_check_module(check_id)
        if mod is None:
            result = _not_implemented_result(check_id, phase)
        else:
            result = _invoke_check(mod, check_id, phase,
                                   batch=batch, campaigns=campaigns,
                                   workspaces=workspaces,
                                   live_reads=live_reads)
            # Validate the result against the five invariants.
            validated_verdict, reasons = validate_result(result)
            if validated_verdict == ERROR and reasons:
                result["verdict"] = ERROR
                result["validation_errors"] = reasons

        results.append(result)

    # The worst verdict across all checks for this phase.
    verdicts = [r["verdict"] for r in results]
    worst = worst_verdict(verdicts) if verdicts else VACUOUS

    # If no check ran at all (empty results), that is VACUOUS, not PASS.
    if not results:
        worst = VACUOUS

    table_text = render_table(results, phase, worst,
                              batch=batch, campaigns=campaigns)

    # Write artefacts if out_dir is given.
    if out_dir:
        _ensure_dir(out_dir)
        for r in results:
            path = os.path.join(out_dir, f"{r['check']}.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(r, fh, indent=2, default=str)
        table_path = os.path.join(out_dir, "TABLE.md")
        with open(table_path, "w", encoding="utf-8") as fh:
            fh.write(table_text)

    return results, table_text, worst


def _invoke_check(mod, check_id, phase, *, batch=None, campaigns=None,
                  workspaces=None, live_reads=True):
    """Call a check module's run() function and normalise the result."""
    try:
        result = mod.run(
            phase=phase,
            batch=batch,
            campaigns=campaigns or [],
            workspaces=workspaces,
            live_reads=live_reads,
        )
    except Exception as exc:
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
            "error": str(exc)[:500],
            "measured_at": _now_iso(),
        }

    # Ensure the result has the canonical shape.
    result.setdefault("check", check_id)
    result.setdefault("phase", phase)
    result.setdefault("measured_at", _now_iso())
    return result


# ------------------------------------------------------------- table renderer

def render_table(results, phase, worst, *, batch=None, campaigns=None,
                 commit=None):
    """Render the QA table. One renderer used by both the Slack post and
    the refusal text, so they are the same bytes.

    Every registered check gets a row. No prospect ids in the table; a
    path to the artefact.
    """
    commit = commit or _current_commit()
    now = _now_iso()

    header_phase = phase
    header_worst = _table_verdict_label(worst, phase)

    lines = []
    campaign_str = ", ".join(str(c) for c in (campaigns or [])) or "-"
    batch_str = batch or "-"
    subj_total = sum(r.get("subjects", 0) for r in results)

    lines.append(
        f"QA \u00b7 {batch_str} \u00b7 {header_phase} \u00b7 {header_worst}")
    lines.append(
        f"campaigns {campaign_str} \u00b7 {subj_total} leads \u00b7 "
        f"commit {commit} \u00b7 {now}")
    lines.append("")

    # Header row.
    lines.append(f"{'check':<20s} {'verdict':<14s} {'subj':>5s} "
                 f"{'clean':>6s}  offending")

    for r in results:
        check_id = r.get("check", "?")
        verdict = r.get("verdict", "?")
        subjects = r.get("subjects", 0)
        clean = r.get("clean", 0)

        if verdict == NOT_IMPLEMENTED:
            offending = "not yet implemented"
        elif verdict == PASS:
            offending = "-"
        elif r.get("not_implemented"):
            offending = "not yet implemented"
        elif subjects == 0:
            offending = r.get("vacuous_reason") or "no subjects"
        else:
            offending = _offending_summary(r)

        v_display = verdict
        lines.append(f"{check_id:<20s} {v_display:<14s} {subjects:>5d} "
                     f"{clean:>6d}  {offending}")

    # Checks registered for OTHER phases get a row too, marked as not run.
    for check_id, module_name, check_phase, blocking in CHECKS:
        if check_phase == phase:
            continue
        already_listed = any(r.get("check") == check_id for r in results)
        if already_listed:
            continue
        lines.append(f"{check_id:<20s} {'-':<14s} {'-':>5s} "
                     f"{'-':>6s}  {check_phase}, not run")

    lines.append("")

    if worst in (FAIL, ERROR, VACUOUS, UNCONFIRMED) and phase == "pre_push":
        lines.append(
            "REFUSED. Nothing was written to either provider.")
    elif worst == NOT_IMPLEMENTED:
        lines.append(
            "NOT_IMPLEMENTED checks present; no verdict can be trusted.")
    elif worst == PASS:
        lines.append("CLEARED. All checks passed.")
    else:
        lines.append(f"verdict: {worst}")

    return "\n".join(lines)


def _table_verdict_label(verdict, phase):
    """The label for the table header."""
    refusal = PHASE_REFUSAL.get(phase, {}).get(verdict)
    if refusal == "REFUSES":
        return "REFUSED"
    if verdict == PASS:
        return "CLEARED"
    if verdict == NOT_IMPLEMENTED:
        return "INCOMPLETE"
    return verdict


def _offending_summary(result):
    """Summarise offenders for the table: counts per rule, no ids."""
    offenders = result.get("offenders") or {}
    counts = result.get("counts") or {}
    parts = []
    for rule_key in sorted(offenders.keys()):
        id_list = offenders[rule_key]
        n = len(id_list) if isinstance(id_list, list) else counts.get(rule_key, 0)
        if n > 0:
            parts.append(f"{n} {rule_key}")
    if not parts:
        return "-"
    return ", ".join(parts)


def _current_commit():
    """The current git commit short hash, or 'unknown'."""
    try:
        import subprocess
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, cwd=_ROOT)
        return out.decode().strip()
    except Exception:
        return "unknown"


# ------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="QA suite runner (Lane F)")
    parser.add_argument("--phase", required=True,
                        choices=PHASES,
                        help="Which phase to run")
    parser.add_argument("--batch", default=None,
                        help="Batch id")
    parser.add_argument("--campaign", action="append", default=None,
                        help="Campaign id (repeatable)")
    parser.add_argument("--workspaces", required=False, default=None,
                        help="Path to a copy of production work/")
    parser.add_argument("--no-live-reads", action="store_true",
                        help="Disable provider reads")
    parser.add_argument("--out-dir", default=None,
                        help="Where to write per-check JSON and TABLE.md")

    args = parser.parse_args(argv)

    out_dir = args.out_dir
    if not out_dir:
        out_dir = os.path.join(_ROOT, "work", "qa", _run_id())

    results, table_text, worst = run_phase(
        args.phase,
        batch=args.batch,
        campaigns=args.campaign,
        workspaces=args.workspaces,
        live_reads=not args.no_live_reads,
        out_dir=out_dir,
    )

    print(table_text)
    print()
    print(f"artefacts: {out_dir}")

    return exit_code_for(worst)


if __name__ == "__main__":
    sys.exit(main())
