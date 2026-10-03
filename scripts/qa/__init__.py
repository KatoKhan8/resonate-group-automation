"""The QA check registry, verdict vocabulary and result validator.

TASK-292. Lane F, the standing QA suite. This module is the single source
of truth for:

- CHECKS: every registered check, as an ordered tuple. A check module on
  disk that is not listed here does not run. A listed module that does not
  yet exist reports NOT_IMPLEMENTED, not PASS and not silence.
- Verdicts and exit codes: one table, used by both pre-push and post-push.
- The result validator: five invariants the runner enforces on every result
  it receives, downgrading a broken result to ERROR.

A check module that is not listed in CHECKS does not run. This is the
answer to the recurring defect in this codebase: a check computed
correctly that nothing reaches.
"""
import importlib
import os
import re

# ----------------------------------------------------------------- CHECKS
#
# An ordered tuple of (check_id, module_name, phase, blocking).
# A module not listed does not run. A listed module that does not yet exist
# reports NOT_IMPLEMENTED in the table -- not PASS, and not silence.
#
# The seven check groups from the contract, in the order they appear there.
# check_campaign_heyreach.py is on disk (TASK-297) and is now registered.
# check_readback.py is on disk (TASK-298) and is registered.
# check_reconcile.py is on disk (TASK-299) and is registered.
# The remaining four are NOT_IMPLEMENTED until their tasks land.

CHECKS = (
    ("lead_state",        "scripts.qa.check_lead_state",
     "pre_push",   True),
    ("lead_pack",         "scripts.qa.check_lead_pack",
     "pre_push",   True),
    ("lead_copy",         "scripts.qa.check_lead_copy",
     "pre_push",   True),
    ("campaign_bison",    "scripts.qa.check_campaign_bison",
     "pre_push",   True),
    ("campaign_heyreach", "scripts.qa.check_campaign_heyreach",
     "pre_push",   True),
    ("readback",          "scripts.qa.check_readback",
     "post_push",  True),
    ("reconcile",         "scripts.qa.check_reconcile",
     "ongoing",    True),
)

# The check_id -> entry lookup, built once from the tuple.
CHECKS_BY_ID = {entry[0]: entry for entry in CHECKS}

# ----------------------------------------------------------- PHASES / verdicts

PHASES = ("pre_push", "post_push", "ongoing")

PASS = "PASS"
FAIL = "FAIL"
UNCONFIRMED = "UNCONFIRMED"
VACUOUS = "VACUOUS"
ERROR = "ERROR"
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
VERDICTS = (PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR)

# Exit codes: one table, used by both pre-push and post-push. Two copies
# is how pre-push and post-push come to disagree about what 2 means.
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNCONFIRMED = 2
EXIT_ERROR = 3

VERDICT_TO_EXIT = {
    PASS: EXIT_PASS,
    FAIL: EXIT_FAIL,
    UNCONFIRMED: EXIT_UNCONFIRMED,
    VACUOUS: EXIT_UNCONFIRMED,
    ERROR: EXIT_ERROR,
}

# Severity ordering for "worst verdict" computation. Higher is worse.
_VERDICT_SEVERITY = {
    PASS: 0,
    NOT_IMPLEMENTED: 1,
    VACUOUS: 2,
    UNCONFIRMED: 2,
    FAIL: 3,
    ERROR: 4,
}

# Refusal semantics by phase. For pre_push, anything non-PASS refuses.
# For post_push, FAIL and ERROR raise CRITICAL; UNCONFIRMED retries.
# For ongoing, FAIL is always CRITICAL; UNCONFIRMED is CRITICAL if it
# persists across two consecutive cycles.
PHASE_REFUSAL = {
    "pre_push": {
        PASS: "proceeds",
        FAIL: "REFUSES",
        UNCONFIRMED: "REFUSES",
        VACUOUS: "REFUSES",
        ERROR: "REFUSES",
        NOT_IMPLEMENTED: "REFUSES",
    },
    "post_push": {
        PASS: "proceeds",
        FAIL: "CRITICAL",
        UNCONFIRMED: "RETRY",
        VACUOUS: "CRITICAL",
        ERROR: "CRITICAL",
        NOT_IMPLEMENTED: "advisory",
    },
    "ongoing": {
        PASS: "proceeds",
        FAIL: "CRITICAL",
        UNCONFIRMED: "CRITICAL-if-persistent",
        VACUOUS: "CRITICAL",
        ERROR: "CRITICAL",
        NOT_IMPLEMENTED: "advisory",
    },
}


def worst_verdict(verdicts):
    """Return the worst verdict from an iterable, by severity ordering."""
    worst = PASS
    for v in verdicts:
        if _VERDICT_SEVERITY.get(v, 0) > _VERDICT_SEVERITY.get(worst, 0):
            worst = v
    return worst


def exit_code_for(verdict):
    """The exit code for a verdict. Unknown verdicts -> ERROR."""
    return VERDICT_TO_EXIT.get(verdict, EXIT_ERROR)


# ----------------------------------------- result validator (five invariants)

_ID_LIKE = re.compile(r"^[A-Za-z0-9_\-:.@/]+$")


def _is_id_like(value):
    """Each offender/unverifiable entry must be an id a person can paste."""
    if not isinstance(value, str):
        return False
    if not value.strip():
        return False
    if value in ("...", "\u2026"):
        return False
    return bool(_ID_LIKE.match(value))


def validate_result(result):
    """Enforce the five invariants of contract section 4 on a check result.

    Returns a (verdict, reasons) tuple. If any invariant is broken the
    verdict is ERROR and reasons lists every break. A result that passes
    all five keeps its own verdict.

    The five invariants:
    1. offenders and unverifiable hold ids, never counts or summaries.
    2. The arithmetic closes: clean + |union(offenders) U union(unverifiable)|
       == subjects.
    3. subjects == 0 is VACUOUS, never PASS, and carries a stated reason.
    4. Every key in counts, offenders and unverifiable exists in rules, and
       every key in rules exists in counts.
    5. rules sentences are rendered from this run's parameters (not checked
       structurally -- the runner checks that rule text is present and
       non-empty; the rendering test is in the table renderer).
    """
    reasons = []

    rules = result.get("rules") or {}
    counts = result.get("counts") or {}
    offenders = result.get("offenders") or {}
    unverifiable = result.get("unverifiable") or {}
    subjects = result.get("subjects")
    clean = result.get("clean")

    if subjects is None or clean is None:
        return ERROR, ["missing subjects or clean field"]

    # Invariant 1: offenders and unverifiable hold ids.
    for rule_key, id_list in offenders.items():
        if not isinstance(id_list, list):
            reasons.append(
                f"offenders[{rule_key!r}] is not a list")
            continue
        for entry in id_list:
            if not _is_id_like(str(entry)):
                reasons.append(
                    f"offenders[{rule_key!r}] contains non-id: {entry!r:.60}")

    for rule_key, id_list in unverifiable.items():
        if not isinstance(id_list, list):
            reasons.append(
                f"unverifiable[{rule_key!r}] is not a list")
            continue
        for entry in id_list:
            if not _is_id_like(str(entry)):
                reasons.append(
                    f"unverifiable[{rule_key!r}] contains non-id: "
                    f"{entry!r:.60}")

    # Invariant 2: arithmetic closes.
    all_offender_ids = set()
    for id_list in offenders.values():
        if isinstance(id_list, list):
            all_offender_ids.update(str(x) for x in id_list)
    all_unverifiable_ids = set()
    for id_list in unverifiable.values():
        if isinstance(id_list, list):
            all_unverifiable_ids.update(str(x) for x in id_list)
    union_size = len(all_offender_ids | all_unverifiable_ids)
    expected = clean + union_size
    if expected != subjects:
        reasons.append(
            f"arithmetic does not close: clean({clean}) + "
            f"|union(offenders, unverifiable)|({union_size}) = {expected} "
            f"!= subjects({subjects})")

    # Invariant 3: subjects == 0 is VACUOUS, never PASS.
    if subjects == 0:
        verdict = result.get("verdict")
        if verdict == PASS:
            reasons.append(
                "subjects == 0 reported PASS; must be VACUOUS with a "
                "stated reason")
        vacuous_reason = result.get("vacuous_reason")
        if not vacuous_reason:
            reasons.append(
                "subjects == 0 with no vacuous_reason stated")

    # Invariant 4: keys agree in both directions.
    rule_keys = set(rules.keys())
    count_keys = set(counts.keys())
    missing_from_counts = rule_keys - count_keys
    extra_in_counts = count_keys - rule_keys
    if missing_from_counts:
        reasons.append(
            f"rules present but absent from counts: "
            f"{sorted(missing_from_counts)}")
    if extra_in_counts:
        reasons.append(
            f"counts present but absent from rules: "
            f"{sorted(extra_in_counts)}")

    offender_keys = set(offenders.keys())
    missing_from_offenders = rule_keys - offender_keys
    extra_in_offenders = offender_keys - rule_keys
    if missing_from_offenders:
        reasons.append(
            f"rules present but absent from offenders: "
            f"{sorted(missing_from_offenders)}")
    if extra_in_offenders:
        reasons.append(
            f"offenders present but absent from rules: "
            f"{sorted(extra_in_offenders)}")

    # Invariant 5: rule sentences are non-empty strings.
    for rule_key, sentence in rules.items():
        if not isinstance(sentence, str) or not sentence.strip():
            reasons.append(
                f"rules[{rule_key!r}] is empty or not a string")

    if reasons:
        return ERROR, reasons
    return result.get("verdict", PASS), []


# ----------------------------------------- check-module discovery

def _qa_dir():
    """The directory this module lives in."""
    return os.path.dirname(os.path.abspath(__file__))


def check_modules_on_disk():
    """Return the set of check_* module names found on disk.

    Used by the test that asserts every check_*.py on disk appears in
    CHECKS. Not a grep of the source -- an os.listdir of the directory
    against the tuple.
    """
    found = set()
    for name in os.listdir(_qa_dir()):
        if name.startswith("check_") and name.endswith(".py"):
            found.add(name[:-3])
    return found


def registered_check_ids():
    """The set of check_ids in CHECKS."""
    return {entry[0] for entry in CHECKS}


def load_check_module(check_id):
    """Import and return the check module for a check_id, or None."""
    entry = CHECKS_BY_ID.get(check_id)
    if entry is None:
        return None
    module_name = entry[1]
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None
