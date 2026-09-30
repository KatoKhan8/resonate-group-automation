"""The QA check registry, verdict vocabulary and result validator.

TASK-292 builds the full harness. This module is the single source of truth
for:

- CHECKS: the ordered registry of every check group, its module, phase and
  whether it blocks the push. A check module not listed here does not run.
- VERDICTS and EXIT_CODES: the five verdict values and their exit codes,
  in ONE table so pre-push and post-push cannot disagree about what 2 means.
- validate_result: the five invariants of contract §4, enforced by the runner
  on every result it receives. A result that breaks one is downgraded to ERROR.

A check module that is not listed in CHECKS does not run. This is deliberate:
a check with no registration is a check with no caller.
"""
import collections
import datetime
import os
import re

# ----------------------------------------------------------------- registry
#
# An ordered tuple of (check_id, module_name, phase, blocking).
# A module listed here that does not yet exist reports NOT_IMPLEMENTED
# in the table — not PASS, and not silence.

CheckEntry = collections.namedtuple(
    "CheckEntry", ["check_id", "module", "phase", "blocking"])

CHECKS = (
    CheckEntry("lead_state",        "scripts.qa.check_lead_state",
               "pre_push",  True),
    CheckEntry("lead_pack",         "scripts.qa.check_lead_pack",
               "pre_push",  True),
    CheckEntry("lead_copy",         "scripts.qa.check_lead_copy",
               "pre_push",  True),
    CheckEntry("campaign_bison",    "scripts.qa.check_campaign_bison",
               "pre_push",  True),
    CheckEntry("campaign_heyreach", "scripts.qa.check_campaign_heyreach",
               "pre_push",  True),
    CheckEntry("readback",          "scripts.qa.check_readback",
               "post_push", True),
    CheckEntry("reconcile",         "scripts.qa.check_reconcile",
               "ongoing",   True),
)

CHECK_IDS = tuple(c.check_id for c in CHECKS)
CHECK_BY_ID = {c.check_id: c for c in CHECKS}

PHASES = ("pre_push", "post_push", "ongoing")

# ------------------------------------------- verdict and exit-code vocabulary
#
# ONE table. Pre-push and post-push read the same mapping.

PASS        = "PASS"
FAIL        = "FAIL"
UNCONFIRMED = "UNCONFIRMED"
VACUOUS     = "VACUOUS"
ERROR       = "ERROR"
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

VERDICTS = (PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR)

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNCONFIRMED = 2
EXIT_ERROR = 3

VERDICT_TO_EXIT = {
    PASS:        EXIT_PASS,
    FAIL:        EXIT_FAIL,
    UNCONFIRMED: EXIT_UNCONFIRMED,
    VACUOUS:     EXIT_UNCONFIRMED,
    ERROR:       EXIT_ERROR,
    NOT_IMPLEMENTED: EXIT_ERROR,
}

# Refusal semantics by phase.
# pre_push:   0 proceeds. 1, 2, 3 all REFUSE THE PUSH.
# post_push:  0 proceeds. 1 raises CRITICAL. 2 is RETRIED. 3 raises CRITICAL.
# ongoing:    0 proceeds. 1 is ALWAYS A CRITICAL. 2 is CRITICAL if persistent.
#
# The runner's own exit code is the WORST of its checks.

PHASE_REFUSAL = {
    "pre_push": {
        PASS: "proceed",
        FAIL: "REFUSE",
        UNCONFIRMED: "REFUSE",
        VACUOUS: "REFUSE",
        ERROR: "REFUSE",
    },
    "post_push": {
        PASS: "proceed",
        FAIL: "CRITICAL",
        UNCONFIRMED: "RETRY",
        VACUOUS: "CRITICAL",
        ERROR: "CRITICAL",
    },
    "ongoing": {
        PASS: "proceed",
        FAIL: "CRITICAL",
        UNCONFIRMED: "CRITICAL if persistent",
        VACUOUS: "CRITICAL",
        ERROR: "CRITICAL",
    },
}

# Worst-verdict ordering. Higher index = worse.
_VERDICT_SEVERITY = {
    PASS: 0,
    NOT_IMPLEMENTED: 1,
    VACUOUS: 2,
    UNCONFIRMED: 2,
    FAIL: 3,
    ERROR: 4,
}


def worst_verdict(verdicts):
    """Return the worst verdict from an iterable.

    The runner's own verdict is the worst of its checks, not a count and
    not a boolean from a filter.
    """
    best = PASS
    for v in verdicts:
        if _VERDICT_SEVERITY.get(v, 99) > _VERDICT_SEVERITY.get(best, 0):
            best = v
    return best


# ---------------------------------------- the five invariants (contract §4)
#
# The runner asserts these on every result it receives. A result that breaks
# one is downgraded to ERROR. It does not trust the check.

# Invariant 1: offenders and unverifiable hold ids, never counts, never "..."
_ID_LIKE = re.compile(r"^[A-Za-z0-9_\-:.@/]+$")


def _looks_like_id(value):
    """Does this value look like an identifier a person could paste?

    Rejects counts ("7"), summaries ("7 leads"), truncation ("..."),
    and empty strings.
    """
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if not value:
        return False
    if value.isdigit():
        return False
    if "lead" in value.lower() and value.split()[0].isdigit():
        return False
    if value in ("...", "…", "-"):
        return False
    return True


def validate_invariant_1_ids(result):
    """Offenders and unverifiable hold ids, never counts or summaries."""
    problems = []
    for key in ("offenders", "unverifiable"):
        bucket = result.get(key)
        if not isinstance(bucket, dict):
            continue
        for rule, values in bucket.items():
            if not isinstance(values, list):
                problems.append(
                    f"{key}.{rule} is not a list")
                continue
            for v in values:
                if not _looks_like_id(v):
                    problems.append(
                        f"{key}.{rule} contains non-id: {v!r}")
    return problems


def validate_invariant_2_arithmetic(result):
    """clean + |union(offenders) ∪ union(unverifiable)| == subjects."""
    subjects = result.get("subjects")
    clean = result.get("clean")
    if subjects is None or clean is None:
        return []
    offenders = result.get("offenders") or {}
    unverifiable = result.get("unverifiable") or {}
    all_ids = set()
    for rule, values in offenders.items():
        if isinstance(values, list):
            all_ids.update(values)
    for rule, values in unverifiable.items():
        if isinstance(values, list):
            all_ids.update(values)
    expected = clean + len(all_ids)
    if expected != subjects:
        return [
            f"arithmetic does not close: clean({clean}) + "
            f"|union(offenders) ∪ union(unverifiable)|({len(all_ids)}) = "
            f"{expected}, but subjects = {subjects}"]
    return []


def validate_invariant_3_vacuous(result):
    """subjects == 0 is VACUOUS, never PASS, and carries a stated reason."""
    subjects = result.get("subjects")
    if subjects is not None and subjects == 0:
        verdict = result.get("verdict")
        if verdict == PASS:
            return ["subjects == 0 but verdict is PASS; must be VACUOUS"]
        reason = result.get("vacuous_reason")
        if not reason:
            return ["subjects == 0 but no vacuous_reason stated"]
    return []


def validate_invariant_4_keys_agree(result):
    """Every key in counts, offenders, unverifiable exists in rules and vice versa."""
    rules = result.get("rules") or {}
    counts = result.get("counts") or {}
    offenders = result.get("offenders") or {}
    unverifiable = result.get("unverifiable") or {}
    problems = []
    all_result_keys = set(counts.keys()) | set(offenders.keys()) | set(unverifiable.keys())
    for key in all_result_keys:
        if key not in rules:
            problems.append(f"key {key!r} in counts/offenders/unverifiable but not in rules")
    for key in rules:
        if key not in counts:
            problems.append(f"rule {key!r} not in counts")
    return problems


def validate_invariant_5_rule_sentences(result):
    """Rule sentences are rendered from this run's parameters.

    We cannot fully verify this without knowing the parameters, but we can
    check that rule sentences are present and non-empty.
    """
    rules = result.get("rules") or {}
    problems = []
    for key, sentence in rules.items():
        if not sentence or not isinstance(sentence, str):
            problems.append(f"rule {key!r} has empty or non-string sentence")
    return problems


def validate_result(result):
    """Assert all five invariants. Returns a list of problems.

    A result that breaks any invariant is downgraded to ERROR by the runner.
    """
    problems = []
    problems.extend(validate_invariant_1_ids(result))
    problems.extend(validate_invariant_2_arithmetic(result))
    problems.extend(validate_invariant_3_vacuous(result))
    problems.extend(validate_invariant_4_keys_agree(result))
    problems.extend(validate_invariant_5_rule_sentences(result))
    return problems
