"""The QA runner: invoke checks, validate results, render the table.

Usage:
    py -3 scripts/qa/run.py --phase pre_push --workspaces <path> \\
        [--batch <id>] [--campaign <id> ...] [--json <dir>]

Contract: docs/QA-LANE-F-CONTRACT-2026-09-25.md §§3-6.
"""
import argparse
import datetime
import importlib
import json
import os
import sys
import traceback

# Ensure the repo root is importable when run as a script.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from scripts.qa import (                          # noqa: E402
    ALL_VERDICTS, CHECKS, ERROR, FAIL, PASS, PHASES, PHASE_REFUSAL,
    UNCONFIRMED, VACUOUS, VERDICT_EXIT, checks_for_phase, exit_code,
    worst_verdict,
)

NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


# ---------------------------------------------------------------- result
# validation (contract §4 — the five invariants)

def _validate_result(result):
    """Assert the five invariants of contract §4 on a check result.

    Returns (verdict, reason) where verdict is ERROR and reason names the
    broken invariant, or (None, None) if the result is well-formed.
    """
    # Invariant 1: offenders and unverifiable hold IDS, never counts or "..."
    for container_name in ("offenders", "unverifiable"):
        container = result.get(container_name) or {}
        for rule_id, ids in container.items():
            if not isinstance(ids, list):
                return ERROR, (
                    "%s.%s is %s, not a list of ids"
                    % (container_name, rule_id, type(ids).__name__))
            for item in ids:
                text = str(item).strip()
                if not text or text == "..." or text.startswith("…"):
                    return ERROR, (
                        "%s.%s contains a non-id value: %r"
                        % (container_name, rule_id, item))
                # A pure integer is a count, not an id.
                try:
                    int(text)
                    return ERROR, (
                        "%s.%s contains a count, not an id: %r"
                        % (container_name, rule_id, item))
                except (ValueError, TypeError):
                    pass
                # An id must not contain whitespace — "7 leads" is not an id.
                if any(c.isspace() for c in text):
                    return ERROR, (
                        "%s.%s contains a phrase, not an id: %r"
                        % (container_name, rule_id, item))

    # Invariant 4: rules, counts, offenders keys agree in both directions.
    # Checked BEFORE arithmetic so key mismatches are reported cleanly.
    rules = result.get("rules") or {}
    counts = result.get("counts") or {}
    offenders = result.get("offenders") or {}
    unverifiable = result.get("unverifiable") or {}
    if set(rules.keys()) != set(counts.keys()):
        return ERROR, (
            "rules keys and counts keys disagree: rules=%s counts=%s"
            % (sorted(rules.keys()), sorted(counts.keys())))
    for rule_key in rules:
        if rule_key not in offenders:
            return ERROR, (
                "rule %r is in rules but not in offenders" % rule_key)
    for key in offenders:
        if key not in rules:
            return ERROR, (
                "offender key %r is not in rules" % key)
    for key in counts:
        actual = len(offenders.get(key) or [])
        if counts[key] != actual:
            return ERROR, (
                "counts[%r] = %d but |offenders[%r]| = %d"
                % (key, counts[key], key, actual))

    # Invariant 2: arithmetic closes.
    subjects = result.get("subjects")
    clean = result.get("clean")
    if subjects is None or clean is None:
        return ERROR, "result is missing 'subjects' or 'clean'"
    all_offending = set()
    for ids in offenders.values():
        all_offending.update(ids)
    for ids in unverifiable.values():
        all_offending.update(ids)
    expected = clean + len(all_offending)
    if expected != subjects:
        return ERROR, (
            "arithmetic does not close: clean(%d) + |offending(%d)| = %d, "
            "but subjects = %d" % (clean, len(all_offending), expected,
                                   subjects))

    # Invariant 3: subjects == 0 is VACUOUS, never PASS.
    verdict = result.get("verdict")
    if subjects == 0 and verdict not in (VACUOUS, ERROR):
        return ERROR, (
            "subjects == 0 but verdict is %s, not VACUOUS" % verdict)

    # Invariant 5: rule sentences are rendered from this run's parameters.
    # We cannot assert this structurally without knowing the check, but we
    # can assert the sentences are non-empty strings.
    for rule_key, sentence in rules.items():
        if not isinstance(sentence, str) or not sentence.strip():
            return ERROR, (
                "rules[%r] is not a rendered sentence: %r"
                % (rule_key, sentence))

    return None, None


def _not_implemented_result(check_id, phase, reason="module not found"):
    """A result for a check whose module does not exist."""
    return {
        "check": check_id,
        "phase": phase,
        "verdict": NOT_IMPLEMENTED,
        "subjects": 0,
        "clean": 0,
        "refused": False,
        "rules": {},
        "counts": {},
        "offenders": {},
        "unverifiable": {},
        "evidence": {"not_implemented": reason},
        "measured_at": _utcnow(),
        "error": "check module is not implemented",
    }


def _vacuous_result(check_id, phase, reason):
    """A result for a check with zero subjects."""
    return {
        "check": check_id,
        "phase": phase,
        "verdict": VACUOUS,
        "subjects": 0,
        "clean": 0,
        "refused": True,
        "rules": {},
        "counts": {},
        "offenders": {},
        "unverifiable": {},
        "evidence": {"vacuous_reason": reason},
        "measured_at": _utcnow(),
    }


# ---------------------------------------------------------------- runner

def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _run_id():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H-%MZ")


def _load_check(module_name):
    """Import a check module from scripts/qa/. Returns the module or None."""
    try:
        return importlib.import_module("scripts.qa." + module_name)
    except ImportError:
        return None


def run_phase(phase, *, batch=None, campaigns=None, workspaces=None,
              json_dir=None, extra_checks=None):
    """Run every blocking check for a phase. Returns (worst_verdict, results).

    `extra_checks` is a list of (check_id, module_name, blocking) tuples
    appended to the registry for this run only — used by tests to rig a
    failing check without editing CHECKS.
    """
    if phase not in PHASES:
        raise ValueError("unknown phase %r; expected one of %s"
                         % (phase, PHASES))

    registry = list(checks_for_phase(phase, blocking_only=True))
    if extra_checks:
        registry.extend(extra_checks)

    results = []
    for check_id, module_name, blocking in registry:
        mod = _load_check(module_name)
        if mod is None:
            result = _not_implemented_result(check_id, phase)
            results.append(result)
            continue

        try:
            kwargs = {"phase": phase}
            if batch is not None:
                kwargs["batch"] = batch
            if campaigns is not None:
                kwargs["campaigns"] = campaigns
            if workspaces is not None:
                kwargs["workspaces"] = workspaces
            result = mod.run(**kwargs)
        except Exception as exc:
            result = {
                "check": check_id,
                "phase": phase,
                "verdict": ERROR,
                "subjects": 0,
                "clean": 0,
                "refused": False,
                "rules": {},
                "counts": {},
                "offenders": {},
                "unverifiable": {},
                "evidence": {},
                "measured_at": _utcnow(),
                "error": "%s: %s" % (type(exc).__name__, exc),
                "traceback": traceback.format_exc(),
            }

        # Validate the result against the five invariants.
        err_verdict, err_reason = _validate_result(result)
        if err_verdict is not None:
            result["verdict"] = ERROR
            result["validation_error"] = err_reason

        results.append(result)

    # Write per-check JSON files.
    if json_dir:
        os.makedirs(json_dir, exist_ok=True)
        for result in results:
            path = os.path.join(json_dir, "%s.json" % result["check"])
            with open(path, "w") as f:
                json.dump(result, f, indent=2)

    verdicts = [r["verdict"] for r in results]
    # NOT_IMPLEMENTED is an error condition — a check that should exist but
    # doesn't. Map it to ERROR for the worst-verdict calculation.
    mapped = [ERROR if v == NOT_IMPLEMENTED else v for v in verdicts]
    worst = worst_verdict(mapped) if mapped else VACUOUS
    return worst, results


# ---------------------------------------------------------------- table
# renderer (contract §6)

def render_table(results, *, phase, batch=None, campaigns=None,
                 commit=None, workspaces_path=None):
    """Render the QA table. One renderer for Slack and refusal text."""
    measured = _utcnow()
    total_subjects = sum(r.get("subjects", 0) for r in results)

    # Header
    refused = any(
        r["verdict"] in PHASE_REFUSAL.get(phase, set()) for r in results)
    status = "REFUSED" if refused else "CLEARED"
    header_parts = ["QA"]
    if batch:
        header_parts.append(str(batch))
    header_parts.append(phase)
    header_parts.append(status)
    header = " · ".join(header_parts)

    lines = [header]

    # Sub-header
    sub_parts = []
    if campaigns:
        sub_parts.append("campaigns %s" % ", ".join(str(c) for c in campaigns))
    sub_parts.append("%d leads" % total_subjects)
    if commit:
        sub_parts.append("commit %s" % commit)
    sub_parts.append(measured)
    lines.append(" · ".join(sub_parts))
    lines.append("")

    # Table header
    lines.append("%-20s %-12s %5s %6s  %s"
                 % ("check", "verdict", "subj", "clean", "offending"))

    # Rows — every registered check gets a row.
    for r in results:
        check_id = r.get("check", "?")
        verdict = r.get("verdict", "?")
        subjects = r.get("subjects", 0)
        clean = r.get("clean", 0)

        if verdict == NOT_IMPLEMENTED:
            offending = "not implemented"
        elif verdict == VACUOUS:
            reason = (r.get("evidence") or {}).get("vacuous_reason", "")
            offending = reason or "no subjects"
        elif verdict == PASS:
            offending = "-"
        else:
            # Summarise offenders by rule.
            offenders = r.get("offenders") or {}
            parts = []
            for rule_key, ids in sorted(offenders.items()):
                if ids:
                    parts.append("%d %s" % (len(ids), rule_key))
            offending = ", ".join(parts) if parts else "-"

        lines.append("%-20s %-12s %5d %6d  %s"
                     % (check_id, verdict, subjects, clean, offending))

    # Checks that did not run (different phase) get a row too.
    ran_ids = {r.get("check") for r in results}
    for check_id, module_name, ph, blocking in CHECKS:
        if check_id in ran_ids:
            continue
        if ph == phase:
            continue
        lines.append("%-20s %-12s %5s %6s  %s"
                     % (check_id, "-", "-", "-", "%s, not run" % ph))

    lines.append("")

    # Footer
    if refused:
        lines.append("REFUSED. Nothing was written to either provider.")
    else:
        lines.append("CLEARED. All blocking checks passed.")

    if workspaces_path:
        lines.append("workspaces: %s" % workspaces_path)

    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the QA suite for a phase.")
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--batch")
    parser.add_argument("--campaign", action="append", type=str)
    parser.add_argument("--workspaces", required=True,
                        help="path to a copy of production work/")
    parser.add_argument("--json", dest="json_dir",
                        help="directory for per-check JSON output")
    parser.add_argument("--table", action="store_true",
                        help="render the table to stdout")
    parser.add_argument("--commit", help="commit sha for the table header")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.workspaces):
        print("ERROR: --workspaces path does not exist: %s"
              % args.workspaces, file=sys.stderr)
        return 3

    run_id = _run_id()
    json_dir = args.json_dir or os.path.join("work", "qa", run_id)

    worst, results = run_phase(
        args.phase,
        batch=args.batch,
        campaigns=args.campaign,
        workspaces=args.workspaces,
        json_dir=json_dir,
    )

    # Write TABLE.md
    table = render_table(
        results,
        phase=args.phase,
        batch=args.batch,
        campaigns=args.campaign,
        commit=args.commit,
        workspaces_path=args.workspaces,
    )
    table_path = os.path.join(json_dir, "TABLE.md")
    os.makedirs(json_dir, exist_ok=True)
    with open(table_path, "w") as f:
        f.write(table)

    if args.table:
        print(table)

    code = exit_code(worst)
    return code


if __name__ == "__main__":
    sys.exit(main())
