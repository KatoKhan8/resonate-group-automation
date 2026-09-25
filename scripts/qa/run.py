#!/usr/bin/env python3
"""The QA runner: run checks for a phase, write artefacts, render the table.

    py -3 scripts/qa/run.py --phase pre_push \
        --batch batch-2-2026-09-25 \
        --campaign 502 --campaign 503 \
        --workspaces <path to a copy of production work/>

The runner:
1. Imports each registered check module for the phase.
2. Calls its run() function with the shared arguments.
3. Validates the result against the five invariants.
4. Writes per-check JSON and a TABLE.md.
5. Returns the worst verdict as exit code.

A check whose module does not exist reports NOT_IMPLEMENTED.
A check whose result breaks an invariant is downgraded to ERROR.
subjects == 0 is VACUOUS, never PASS.
The exit code is the WORST verdict, not a count and not a boolean.
"""
import argparse
import datetime
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))

sys.path.insert(0, PROJECT_ROOT)

from scripts.qa import (                                          # noqa: E402
    CHECKS, VERDICTS, checks_for_phase, exit_code_for,
    render_table, validate_result, worst_verdict,
    REFUSING_VERDICTS,
)


def _run_id():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H-%MZ")


def _import_check(module_name):
    """Import a check module. Returns the module or None."""
    try:
        return importlib.import_module(f"scripts.qa.{module_name}")
    except ImportError:
        return None


def run_checks(phase, *, batch=None, campaigns=None, workspaces=None,
               json_dir=None):
    """Run every blocking check for the phase.

    Returns (results, table_text, worst). Each result is a dict.
    """
    checks = checks_for_phase(phase)
    results = []
    measured_at = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")

    for check_id, module_name, _ph, blocking in checks:
        mod = _import_check(module_name)
        if mod is None:
            results.append({
                "check": check_id,
                "phase": phase,
                "verdict": "NOT_IMPLEMENTED",
                "batch": batch,
                "campaigns": campaigns or [],
                "subjects": 0,
                "clean": 0,
                "refused": False,
                "rules": {},
                "counts": {},
                "offenders": {},
                "unverifiable": {},
                "evidence": {"module_missing": True},
                "measured_at": measured_at,
                "blocking": blocking,
            })
            continue

        try:
            raw = mod.run(phase=phase, batch=batch,
                          campaigns=campaigns or [],
                          workspaces=workspaces)
        except Exception as exc:
            results.append({
                "check": check_id,
                "phase": phase,
                "verdict": "ERROR",
                "batch": batch,
                "campaigns": campaigns or [],
                "subjects": 0,
                "clean": 0,
                "refused": blocking,
                "rules": {},
                "counts": {},
                "offenders": {},
                "unverifiable": {},
                "evidence": {"error": str(exc)},
                "measured_at": measured_at,
                "blocking": blocking,
            })
            continue

        result = dict(raw)
        result.setdefault("check", check_id)
        result.setdefault("phase", phase)
        result["blocking"] = blocking

        validated, validation_error = validate_result(result)
        if validation_error:
            validated["validation_error"] = validation_error
        results.append(validated)

    verdicts = []
    for r in results:
        v = r.get("verdict", "ERROR")
        if v == "NOT_IMPLEMENTED":
            if r.get("blocking"):
                verdicts.append("ERROR")
            else:
                verdicts.append("PASS")
        else:
            verdicts.append(v)

    worst = worst_verdict(verdicts) if verdicts else "VACUOUS"

    commit = _current_commit()
    table = render_table(
        phase, results,
        batch=batch, campaigns=campaigns,
        commit=commit, measured_at=measured_at,
        workspaces=json_dir)

    if json_dir:
        os.makedirs(json_dir, exist_ok=True)
        for r in results:
            path = os.path.join(json_dir, f"{r['check']}.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(r, fh, indent=2, default=str)
        table_path = os.path.join(json_dir, "TABLE.md")
        with open(table_path, "w", encoding="utf-8") as fh:
            fh.write(table)

    return results, table, worst


def _current_commit():
    """The current git commit, or 'unknown'."""
    try:
        import subprocess
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return "unknown"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run QA checks for a phase.")
    parser.add_argument("--phase", required=True,
                        choices=["pre_push", "post_push", "ongoing"])
    parser.add_argument("--batch", default=None)
    parser.add_argument("--campaign", action="append", default=None)
    parser.add_argument("--workspaces", required=True,
                        help="path to a copy of production work/")
    parser.add_argument("--json-dir", default=None,
                        help="where to write per-check JSON and TABLE.md")
    args = parser.parse_args(argv)

    json_dir = args.json_dir or os.path.join(
        PROJECT_ROOT, "work", "qa", _run_id())

    if not os.path.isdir(args.workspaces):
        print(f"ERROR: --workspaces path does not exist: {args.workspaces}",
              file=sys.stderr)
        return 3

    results, table, worst = run_checks(
        args.phase,
        batch=args.batch,
        campaigns=args.campaign,
        workspaces=args.workspaces,
        json_dir=json_dir)

    print(table)
    print()
    print(f"Worst verdict: {worst} (exit {exit_code_for(worst)})")
    print(f"Artefacts: {json_dir}")

    return exit_code_for(worst)


if __name__ == "__main__":
    raise SystemExit(main())
