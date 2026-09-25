"""The QA refusal function: raises FactoryRefused when checks fail.

This module provides the `refuse` function that is proposed as a patch for
`bisonfactory.stage` and `heyreachfactory.stage`. It runs the QA checks,
validates results, and raises FactoryRefused carrying the runner's own
rendered table -- not a sentence written at the raise site.

PATCH PROPOSAL: this function's logic is proposed to be inlined into
bisonfactory._refuse_qa and called from stage() immediately after
_refuse_copylint. See the task result block for the exact patch.
"""
import datetime
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from scripts.qa import (                                     # noqa: E402
    render_table, validate_result, worst_verdict,
    REFUSING_VERDICTS, checks_for_phase,
)


class _FakeFactoryRefused(Exception):
    """Stand-in for bisonfactory.FactoryRefused.

    The real patch imports FactoryRefused from the factory module. This
    stand-in lets the refusal logic be tested and demonstrated without
    importing the factory (which triggers provider module loads).
    """
    pass


def refuse(*, plan, recs, report, phase, batch=None, campaigns=None,
           workspaces=None, check_results=None,
           factory_refused_cls=None):
    """Run QA checks and refuse the push if any blocking check fails.

    If check_results is provided, use those directly (for testing).
    Otherwise, import and run the checks via run_checks.

    Raises FactoryRefused carrying the rendered table if any blocking
    pre_push check fails. Returns None if all clear.

    The refusal text is the RUNNER'S OWN TABLE, not a sentence written here.
    """
    exc_cls = factory_refused_cls or _FakeFactoryRefused

    if check_results is None:
        from scripts.qa.run import run_checks
        json_dir = None
        if workspaces:
            json_dir = os.path.join(workspaces, "qa",
                                    datetime.datetime.now(
                                        datetime.timezone.utc).strftime(
                                        "%Y-%m-%dT%H-%MZ"))
        check_results, _, _ = run_checks(
            phase, batch=batch, campaigns=campaigns,
            workspaces=workspaces, json_dir=json_dir)

    if phase not in REFUSING_VERDICTS:
        return None

    refusing = REFUSING_VERDICTS[phase]
    any_refused = False
    for r in check_results:
        v = r.get("verdict", "ERROR")
        if v in refusing and r.get("blocking", True):
            any_refused = True
            break

    if not any_refused:
        return None

    measured_at = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    table = render_table(
        phase, check_results,
        batch=batch, campaigns=campaigns,
        measured_at=measured_at,
        workspaces=workspaces)

    offending_detail = _render_offending_ids(check_results)

    report["qa"] = {"results": check_results, "table": table,
                    "refused": True}

    raise exc_cls(
        "the QA suite refuses this push, and it runs before any provider "
        "write so nothing has reached the estate:\n%s\n%s\n"
        "Nothing was written to either provider."
        % (table, offending_detail))


def _render_offending_ids(results):
    """Render the offending ids and rule names for the refusal text.

    The TABLE omits ids (they go to Slack). The refusal text includes them
    so the operator reading the FactoryRefused exception sees exactly which
    records and which rules fired.
    """
    lines = []
    for r in results:
        v = r.get("verdict", "ERROR")
        if v in ("PASS", "NOT_IMPLEMENTED"):
            continue
        offenders = r.get("offenders") or {}
        unverifiable = r.get("unverifiable") or {}
        rules = r.get("rules") or {}
        for rule_name, ids in sorted(offenders.items()):
            if isinstance(ids, list) and ids:
                rule_text = rules.get(rule_name, rule_name)
                lines.append(
                    f"  {r.get('check', '?')}/{rule_name} "
                    f"({rule_text}): {', '.join(ids)}")
        for rule_name, ids in sorted(unverifiable.items()):
            if isinstance(ids, list) and ids:
                rule_text = rules.get(rule_name, rule_name)
                lines.append(
                    f"  {r.get('check', '?')}/{rule_name} "
                    f"({rule_text}) [unverifiable]: {', '.join(ids)}")
    if lines:
        return "offending ids:\n" + "\n".join(lines)
    return ""
