#!/usr/bin/env python3
"""The QA runner and table renderer.

    py -3 scripts/qa/run.py --phase pre_push --batch batch-2-2026-09-25 \\
        --campaign 502 --campaign 503 \\
        --workspaces <path to a copy of production work/>

Runs every blocking check for the phase, writes one JSON per check and a
TABLE.md, returns the worst verdict, and renders the table. The table is the
same bytes that go into the Slack post and into the push refusal - one
renderer, so the two cannot disagree.
"""
import argparse
import datetime
import importlib
import json
import os
import sys

# scripts/ is importable when the runner is invoked as a script.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from qa import (                                                    # noqa: E402
    CHECKS,
    VERDICT_EXIT,
    checks_for_phase,
    validate_result,
    worst_verdict,
)

NOT_IMPLEMENTED_VERDICT = "UNCONFIRMED"


# --------------------------------------------------------------- run one check

def load_check_module(module_name):
    """Import a check module from the scripts.qa package.

    Raises ImportError if the module does not exist - the caller turns this
    into a NOT_IMPLEMENTED row rather than a crash.
    """
    return importlib.import_module(f"qa.{module_name}")


def run_one_check(check_id, module_name, phase, **kwargs):
    """Run one check and return its result document.

    A module that does not exist reports NOT_IMPLEMENTED - not PASS, not
    silence. A module that raises reports ERROR. A result that breaks an
    invariant is downgraded to ERROR by the validator.
    """
    try:
        mod = load_check_module(module_name)
    except (ImportError, ModuleNotFoundError):
        return {
            "check": check_id,
            "phase": phase,
            "verdict": NOT_IMPLEMENTED_VERDICT,
            "subjects": 0,
            "clean": 0,
            "rules": {},
            "counts": {},
            "offenders": {},
            "unverifiable": {},
            "not_implemented": True,
            "vacuous_reason": (
                f"check module {module_name!r} is not implemented"),
            "evidence": {},
            "measured_at": _utcnow(),
        }

    run_fn = getattr(mod, "run", None)
    if run_fn is None:
        return _error_result(
            check_id, phase,
            f"module {module_name!r} has no run() function")

    try:
        result = run_fn(phase=phase, **kwargs)
    except Exception as exc:                                      # noqa: BLE001
        return _error_result(check_id, phase, f"{type(exc).__name__}: {exc}")

    if not isinstance(result, dict):
        return _error_result(check_id, phase, "run() did not return a dict")

    # Fill in defaults for optional fields the check may have omitted.
    result.setdefault("check", check_id)
    result.setdefault("phase", phase)
    result.setdefault("offenders", {})
    result.setdefault("unverifiable", {})
    result.setdefault("evidence", {})
    result.setdefault("measured_at", _utcnow())

    # Validate the five invariants. A result that breaks one is ERROR.
    ok, errors = validate_result(result)
    if not ok:
        result["verdict"] = "ERROR"
        result["invariant_errors"] = errors

    return result


def _error_result(check_id, phase, reason):
    return {
        "check": check_id,
        "phase": phase,
        "verdict": "ERROR",
        "subjects": 0,
        "clean": 0,
        "rules": {},
        "counts": {},
        "offenders": {},
        "unverifiable": {},
        "invariant_errors": [reason],
        "evidence": {},
        "measured_at": _utcnow(),
    }


def _utcnow():
    return (datetime.datetime.now(datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"))


# ----------------------------------------------------------------- the runner

def run_checks(phase, batch=None, campaigns=None, workspaces=None):
    """Run every blocking check for the phase.

    Returns (results, worst_verdict, table_text). The table is the same bytes
    that go into the Slack post and the push refusal.
    """
    checks = checks_for_phase(phase, blocking_only=True)
    kwargs = {}
    if batch:
        kwargs["batch"] = batch
    if campaigns:
        kwargs["campaigns"] = list(campaigns)
    if workspaces:
        kwargs["workspaces"] = workspaces

    results = []
    for check_id, module_name, _phase, _blocking in checks:
        result = run_one_check(check_id, module_name, phase, **kwargs)
        results.append(result)

    verdicts = [r["verdict"] for r in results]
    worst = worst_verdict(verdicts)
    table = render_table(results, phase, batch=batch, campaigns=campaigns)
    return results, worst, table


# ----------------------------------------------------------- the table renderer

def _format_offending(result):
    """The offending column: counts per rule, no ids.

    Ids go in the artefact file, not in the table. The table names the counts
    and the rule keys; a path to the file carries the ids.
    """
    counts = result.get("counts") or {}
    offenders = result.get("offenders") or {}
    parts = []
    for rule, count in sorted(counts.items()):
        if count > 0:
            parts.append(f"{count} {rule}")
    return ", ".join(parts) if parts else "-"


def _verdict_cell(result):
    """The verdict column. A check that did not run is '-', never PASS."""
    if result.get("not_implemented"):
        return "NOT_IMPL"
    return result.get("verdict", "ERROR")


def render_table(results, phase, batch=None, campaigns=None, commit=None):
    """The QA table. One renderer for Slack, for the refusal, and for the
    artefact file - so the three are the same bytes.

    Every registered check for the phase gets a row, including the ones that
    passed and the ones that were VACUOUS. A check for a different phase is
    shown as '-' with the phase named.
    """
    now = _utcnow()
    campaign_str = ", ".join(str(c) for c in (campaigns or [])) or "-"
    total_subj = sum(r.get("subjects", 0) for r in results)
    worst = worst_verdict([r.get("verdict", "ERROR") for r in results])
    header_status = "REFUSED" if worst != "PASS" else "CLEARED"

    lines = []
    lines.append(f"QA · {batch or '-'} · {phase} · {header_status}")
    lines.append(
        f"campaigns {campaign_str} · {total_subj} leads · "
        f"commit {commit or 'unknown'} · {now}")
    lines.append("")
    lines.append(
        f"{'check':<20s} {'verdict':<10s} {'subj':>5s} {'clean':>6s}  "
        f"offending")

    # One row per registered check for THIS phase, plus '-' rows for checks
    # in other phases so the table can be told apart from one where nothing
    # ran.
    shown = set()
    for r in results:
        check_id = r.get("check", "?")
        shown.add(check_id)
        v = _verdict_cell(r)
        s = r.get("subjects", 0)
        c = r.get("clean", 0)
        if r.get("not_implemented"):
            off = "module not on disk"
        elif r.get("verdict") == "VACUOUS":
            off = r.get("vacuous_reason", "no subjects")
        elif r.get("verdict") == "PASS":
            off = "-"
        else:
            off = _format_offending(r)
        lines.append(f"{check_id:<20s} {v:<10s} {s:>5d} {c:>6d}  {off}")

    # '-' rows for checks in other phases.
    for check_id, _mod, chk_phase, _blocking in CHECKS:
        if chk_phase != phase and check_id not in shown:
            lines.append(
                f"{check_id:<20s} {'-':<10s} {'-':>5s} {'-':>6s}  "
                f"{chk_phase}, not run")

    lines.append("")
    if worst != "PASS":
        lines.append(
            "REFUSED. Nothing was written to either provider.")
    else:
        lines.append("CLEARED. All checks passed.")

    return "\n".join(lines)


# ------------------------------------------------------------------ the CLI

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the QA suite for a phase.")
    parser.add_argument("--phase", required=True,
                        choices=["pre_push", "post_push", "ongoing"])
    parser.add_argument("--batch")
    parser.add_argument("--campaign", action="append")
    parser.add_argument("--workspaces", required=True,
                        help="path to a copy of production work/")
    parser.add_argument("--out",
                        help="directory for the result JSONs and TABLE.md")
    parser.add_argument("--commit", help="commit sha for the table header")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.workspaces):
        print(f"REFUSED: --workspaces {args.workspaces!r} does not exist",
              file=sys.stderr)
        return 3

    results, worst, table = run_checks(
        args.phase, batch=args.batch, campaigns=args.campaign,
        workspaces=args.workspaces)

    # Write the artefacts.
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        for r in results:
            path = os.path.join(args.out, f"{r['check']}.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(r, fh, indent=2)
                fh.write("\n")
        table_path = os.path.join(args.out, "TABLE.md")
        with open(table_path, "w", encoding="utf-8") as fh:
            fh.write(table)
            fh.write("\n")

    print(table)

    if args.out:
        print(f"\noffending ids: {args.out}/TABLE.md")

    return VERDICT_EXIT.get(worst, 3)


if __name__ == "__main__":
    raise SystemExit(main())
