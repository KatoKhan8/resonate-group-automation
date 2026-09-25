"""The QA harness registry: CHECKS, verdicts, phases, result validation.

TASK-292. The harness that answers two questions:
- When a pre-push check fails, does the push actually stop?
- Can the runner tell "every check passed" from "no check ran"?

The registry is the single source of truth for which checks exist, which
phase they belong to, and whether they block a push. A check module that is
not listed here does not run. A check listed here whose module does not exist
reports NOT_IMPLEMENTED in the table -- not PASS, and not silence.
"""
import os

#: The ordered registry. Each entry: (check_id, module_name, phase, blocking).
#: A module not listed does not run. A listed module that does not yet exist
#: reports NOT_IMPLEMENTED. Ship all seven so a check landing later is one
#: line and not a wiring exercise.
CHECKS = (
    ("lead_state",        "check_lead_state",        "pre_push",   True),
    ("lead_pack",         "check_lead_pack",          "pre_push",   True),
    ("lead_copy",         "check_lead_copy",          "pre_push",   True),
    ("campaign_bison",    "check_campaign_bison",     "pre_push",   True),
    ("campaign_heyreach", "check_campaign_heyreach",  "pre_push",   True),
    ("readback",          "check_readback",           "post_push",  True),
    ("reconcile",         "check_reconcile",          "ongoing",    True),
)

#: The five verdicts and their exit codes.
VERDICTS = {
    "PASS":        0,
    "FAIL":        1,
    "UNCONFIRMED": 2,
    "VACUOUS":     2,
    "ERROR":       3,
}

#: Severity ordering for "worst of" comparisons. Higher is worse.
VERDICT_SEVERITY = {
    "PASS":        0,
    "UNCONFIRMED": 1,
    "VACUOUS":     1,
    "FAIL":        2,
    "ERROR":       3,
}

#: The three phases.
PHASES = ("pre_push", "post_push", "ongoing")

#: Refusal semantics by phase: which verdicts refuse.
#: pre_push: 1 (FAIL), 2 (UNCONFIRMED/VACUOUS), 3 (ERROR) all refuse.
#: post_push: 1 raises CRITICAL, 2 is retried, 3 raises CRITICAL.
#: ongoing: 1 is ALWAYS CRITICAL, 2 is CRITICAL if persistent, 3 CRITICAL.
REFUSING_VERDICTS = {
    "pre_push":  {"FAIL", "UNCONFIRMED", "VACUOUS", "ERROR"},
    "post_push": {"FAIL", "ERROR"},
    "ongoing":   {"FAIL", "ERROR"},
}


def checks_for_phase(phase):
    """Return the CHECKS entries for a given phase."""
    return [(cid, mod, ph, blk) for cid, mod, ph, blk in CHECKS if ph == phase]


def worst_verdict(verdicts):
    """Return the worst verdict from a collection, by severity."""
    if not verdicts:
        return "VACUOUS"
    return max(verdicts, key=lambda v: VERDICT_SEVERITY.get(v, 0))


def exit_code_for(verdict):
    """The exit code for a verdict."""
    return VERDICTS.get(verdict, 3)


def validate_result(result):
    """Enforce the five invariants of contract section 4 on a check result.

    Returns (clean_result, error_message). If the result breaks an invariant,
    clean_result has verdict forced to ERROR and error_message states why.
    If the result is clean, error_message is None.

    The runner asserts these; it does not trust the check.
    """
    errors = []

    verdict = result.get("verdict", "ERROR")
    subjects = result.get("subjects", 0)
    clean = result.get("clean", 0)
    rules = result.get("rules") or {}
    counts = result.get("counts") or {}
    offenders = result.get("offenders") or {}
    unverifiable = result.get("unverifiable") or {}

    # Invariant 1: offenders and unverifiable hold ids, not counts or summaries.
    for rule_name, ids in offenders.items():
        if not isinstance(ids, list):
            errors.append(
                f"offenders[{rule_name!r}] is {type(ids).__name__}, not a list")
            continue
        for id_val in ids:
            if not isinstance(id_val, str) or not id_val.strip():
                errors.append(
                    f"offenders[{rule_name!r}] contains non-string or empty id: "
                    f"{id_val!r}")
                break
    for rule_name, ids in unverifiable.items():
        if not isinstance(ids, list):
            errors.append(
                f"unverifiable[{rule_name!r}] is {type(ids).__name__}, "
                f"not a list")
            continue
        for id_val in ids:
            if not isinstance(id_val, str) or not id_val.strip():
                errors.append(
                    f"unverifiable[{rule_name!r}] contains non-string or "
                    f"empty id: {id_val!r}")
                break

    # Invariant 2: arithmetic closes.
    # clean + |union(offenders) ∪ union(unverifiable)| == subjects
    all_offending_ids = set()
    for ids in offenders.values():
        if isinstance(ids, list):
            all_offending_ids.update(ids)
    for ids in unverifiable.values():
        if isinstance(ids, list):
            all_offending_ids.update(ids)
    expected_subjects = clean + len(all_offending_ids)
    if expected_subjects != subjects:
        errors.append(
            f"arithmetic does not close: clean({clean}) + "
            f"|offending ids|({len(all_offending_ids)}) = {expected_subjects} "
            f"but subjects = {subjects}")

    # Invariant 3: subjects == 0 is VACUOUS, never PASS.
    if subjects == 0 and verdict not in ("VACUOUS", "ERROR"):
        errors.append(
            f"subjects == 0 but verdict is {verdict!r}, not VACUOUS")
    if subjects == 0 and verdict == "PASS":
        errors.append(
            "subjects == 0 must not be PASS; a check that examined nothing "
            "established nothing")

    # Invariant 4: keys in counts, offenders, unverifiable exist in rules,
    # and every key in rules exists in counts.
    rule_keys = set(rules.keys())
    count_keys = set(counts.keys())
    offender_keys = set(offenders.keys())
    unverifiable_keys = set(unverifiable.keys())

    in_counts_not_rules = count_keys - rule_keys
    if in_counts_not_rules:
        errors.append(
            f"counts has keys not in rules: {sorted(in_counts_not_rules)}")
    in_rules_not_counts = rule_keys - count_keys
    if in_rules_not_counts:
        errors.append(
            f"rules has keys not in counts: {sorted(in_rules_not_counts)}")
    in_offenders_not_rules = offender_keys - rule_keys
    if in_offenders_not_rules:
        errors.append(
            f"offenders has keys not in rules: {sorted(in_offenders_not_rules)}")
    in_unverifiable_not_rules = unverifiable_keys - rule_keys
    if in_unverifiable_not_rules:
        errors.append(
            f"unverifiable has keys not in rules: "
            f"{sorted(in_unverifiable_not_rules)}")

    if errors:
        result = dict(result)
        result["verdict"] = "ERROR"
        result["validation_errors"] = errors
        return result, "; ".join(errors)

    return result, None


def check_modules_on_disk():
    """Return the set of check_*.py module names on disk in this directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    found = set()
    for name in os.listdir(here):
        if name.startswith("check_") and name.endswith(".py"):
            found.add(name[:-3])
    return found


def registered_module_names():
    """Return the set of module names in CHECKS."""
    return {mod for _, mod, _, _ in CHECKS}


def render_table(phase, results, *, batch=None, campaigns=None,
                 commit=None, measured_at=None, workspaces=None):
    """Render the QA table. One renderer for Slack and refusal text.

    Every registered check for the phase gets a row, including PASS, VACUOUS,
    and NOT_IMPLEMENTED. No prospect ids in the table; a path to the artefact.
    """
    verdict_label = worst_verdict([r.get("verdict", "ERROR")
                                   for r in results])
    if verdict_label in REFUSING_VERDICTS.get(phase, set()):
        header_status = "REFUSED"
    elif verdict_label == "PASS":
        header_status = "CLEARED"
    else:
        header_status = verdict_label

    campaign_str = ", ".join(str(c) for c in (campaigns or [])) or "-"
    subjects_total = sum(r.get("subjects", 0) for r in results)
    lines = []
    lines.append(
        f"QA · {batch or '-'} · {phase} · {header_status}")
    lines.append(
        f"campaigns {campaign_str} · {subjects_total} leads · "
        f"commit {commit or '-'} · {measured_at or '-'}")
    lines.append("")

    header = f"{'check':<20s} {'verdict':<12s} {'subj':>5s} {'clean':>6s}  " \
             f"offending"
    lines.append(header)

    registered = checks_for_phase(phase)
    results_by_check = {r.get("check"): r for r in results}

    for check_id, _mod, _ph, _blk in registered:
        r = results_by_check.get(check_id)
        if r is None:
            lines.append(
                f"{check_id:<20s} {'NOT_IMPLEMENTED':<12s} {'-':>5s} "
                f"{'-':>6s}  module not yet on disk")
            continue
        v = r.get("verdict", "ERROR")
        subj = r.get("subjects", 0)
        cl = r.get("clean", 0)
        offending_count = sum(
            len(ids) for ids in (r.get("offenders") or {}).values()
            if isinstance(ids, list))
        unverifiable_count = sum(
            len(ids) for ids in (r.get("unverifiable") or {}).values()
            if isinstance(ids, list))
        total_offending = offending_count + unverifiable_count

        if v == "VACUOUS":
            reason = r.get("vacuous_reason", "no subjects")
            lines.append(
                f"{check_id:<20s} {'VACUOUS':<12s} {'0':>5s} {'0':>6s}  "
                f"{reason}")
        elif v == "NOT_IMPLEMENTED":
            lines.append(
                f"{check_id:<20s} {'NOT_IMPLEMENTED':<12s} {'-':>5s} "
                f"{'-':>6s}  module not yet on disk")
        elif total_offending == 0:
            lines.append(
                f"{check_id:<20s} {v:<12s} {subj:>5d} {cl:>6d}  -")
        else:
            rule_parts = []
            for rule_name, ids in sorted(
                    (r.get("offenders") or {}).items()):
                if isinstance(ids, list) and ids:
                    rule_parts.append(
                        f"{len(ids)} {rule_name}")
            for rule_name, ids in sorted(
                    (r.get("unverifiable") or {}).items()):
                if isinstance(ids, list) and ids:
                    rule_parts.append(
                        f"{len(ids)} {rule_name} (unverifiable)")
            detail = ", ".join(rule_parts)
            lines.append(
                f"{check_id:<20s} {v:<12s} {subj:>5d} {cl:>6d}  "
                f"{total_offending} ({detail})")

    lines.append("")
    if header_status == "REFUSED":
        lines.append(
            "REFUSED. Nothing was written to either provider.")
    elif header_status == "CLEARED":
        lines.append("CLEARED. All checks passed.")
    else:
        lines.append(f"Status: {header_status}.")

    if workspaces:
        lines.append(f"offending ids: {workspaces}/TABLE.md")
    else:
        lines.append("offending ids: work/qa/<run-id>/TABLE.md")

    return "\n".join(lines)
