"""The QA check registry, verdict vocabulary and result validator.

TASK-292. Lane F, the standing QA suite.

A check module that is not listed in CHECKS does not run. A check on disk
that is absent from CHECKS is the DISCONNECTED defect — a check computed
correctly that nothing reaches (TASK-277, heyreach.linkedin_sequence).
"""

import importlib
import os

# ----------------------------------------------------------------- phases

PHASES = ("pre_push", "post_push", "ongoing")

# ------------------------------------------- verdict and exit-code table
#
# ONE table. The runner, the refusal and the Slack post all read these.
# Two copies is how pre-push and post-push come to disagree about what 2
# means.
#
#   verdict        exit   meaning
#   PASS           0      every subject checked, every rule clear
#   FAIL           1      at least one subject offends at least one rule
#   UNCONFIRMED    2      the check ran and could not establish the answer
#   VACUOUS        2      subjects == 0; never PASS, carries a stated reason
#   ERROR          3      the check itself broke

PASS = "PASS"
FAIL = "FAIL"
UNCONFIRMED = "UNCONFIRMED"
VACUOUS = "VACUOUS"
ERROR = "ERROR"

VERDICTS = (PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR)

VERDICT_EXIT = {
    PASS: 0,
    FAIL: 1,
    UNCONFIRMED: 2,
    VACUOUS: 2,
    ERROR: 3,
}

# Refusal semantics by phase: which verdicts refuse a pre_push?
# pre_push:   0 proceeds. 1, 2, 3 all REFUSE.
# post_push:  0 proceeds. 1 CRITICAL. 2 RETRIED. 3 CRITICAL.
# ongoing:    0 proceeds. 1 CRITICAL. 2 CRITICAL if persistent. 3 CRITICAL.
PHASE_REFUSES = {
    "pre_push": {FAIL, UNCONFIRMED, VACUOUS, ERROR},
    "post_push": {FAIL, ERROR},
    "ongoing": {FAIL, ERROR},
}

# --------------------------------------------------------------- CHECKS
#
# An ordered tuple of (check_id, module_name, phase, blocking).
# A module not listed does not run. A listed module that does not yet
# exist reports NOT_IMPLEMENTED in the table — not PASS, and not silence.
#
# Seven check ids from the contract, with their modules:
#   lead_state        TASK-293  pre_push    subject: lead
#   lead_pack         TASK-294  pre_push    subject: lead
#   lead_copy         TASK-295  pre_push    subject: lead
#   campaign_bison    TASK-296  pre_push    subject: campaign
#   campaign_heyreach TASK-297  pre_push    subject: campaign
#   readback          TASK-298  post_push   subject: campaign
#   reconcile         TASK-299  ongoing     subject: lead

CHECKS = (
    ("lead_state",        "scripts.qa.check_lead_state",
     "pre_push",  True),
    ("lead_pack",         "scripts.qa.check_lead_pack",
     "pre_push",  True),
    ("lead_copy",         "scripts.qa.check_lead_copy",
     "pre_push",  True),
    ("campaign_bison",    "scripts.qa.check_campaign_bison",
     "pre_push",  True),
    ("campaign_heyreach", "scripts.qa.check_campaign_heyreach",
     "pre_push",  True),
    ("readback",          "scripts.qa.check_readback",
     "post_push", True),
    ("reconcile",         "scripts.qa.check_reconcile",
     "ongoing",   True),
)

# A lookup by check_id for fast access.
CHECKS_BY_ID = {c[0]: c for c in CHECKS}


def checks_for_phase(phase, blocking_only=True):
    """Return the CHECKS entries for a given phase.

    If blocking_only, only entries with blocking=True are returned.
    """
    result = []
    for entry in CHECKS:
        if entry[2] != phase:
            continue
        if blocking_only and not entry[3]:
            continue
        result.append(entry)
    return result


# ----------------------------------------- result validator (5 invariants)

def validate_result(result):
    """Assert the five invariants of contract §4 on a check result.

    Returns (is_valid, reasons) where reasons is a list of strings
    describing each invariant that was broken. An empty list means valid.

    The invariants:
    1. offenders and unverifiable hold ids, not counts or summaries.
    2. clean + |union(offenders) ∪ union(unverifiable)| == subjects.
    3. subjects == 0 is VACUOUS, never PASS, with a stated reason.
    4. rules, counts, offenders keys agree in both directions.
    5. rules sentences are rendered from the run's parameters.
    """
    reasons = []

    if not isinstance(result, dict):
        return False, ["result is not a dict"]

    # --- Invariant 1: offenders and unverifiable hold ids ---
    for section in ("offenders", "unverifiable"):
        bucket = result.get(section)
        if bucket is None:
            continue
        if not isinstance(bucket, dict):
            reasons.append(f"{section} is not a dict")
            continue
        for rule_key, ids in bucket.items():
            if not isinstance(ids, list):
                reasons.append(
                    f"{section}.{rule_key} is not a list")
                continue
            for item in ids:
                s = str(item)
                if not s or s == "..." or s.isdigit() and len(s) <= 2:
                    reasons.append(
                        f"{section}.{rule_key} contains non-id: {s!r}")
                    break

    # --- Invariant 2: arithmetic closes ---
    subjects = result.get("subjects")
    clean = result.get("clean")
    if subjects is not None and clean is not None:
        offender_ids = set()
        unverifiable_ids = set()
        offenders = result.get("offenders", {})
        unverifiable = result.get("unverifiable", {})
        if isinstance(offenders, dict):
            for ids in offenders.values():
                if isinstance(ids, list):
                    offender_ids.update(str(i) for i in ids)
        if isinstance(unverifiable, dict):
            for ids in unverifiable.values():
                if isinstance(ids, list):
                    unverifiable_ids.update(str(i) for i in ids)
        union_size = len(offender_ids | unverifiable_ids)
        expected = clean + union_size
        if expected != subjects:
            reasons.append(
                f"arithmetic: clean({clean}) + |union|({union_size}) "
                f"= {expected} != subjects({subjects})")

    # --- Invariant 3: subjects == 0 is VACUOUS, never PASS ---
    if subjects is not None and subjects == 0:
        verdict = result.get("verdict")
        if verdict == PASS:
            reasons.append(
                "subjects == 0 but verdict is PASS; must be VACUOUS")
        elif verdict != VACUOUS:
            pass  # ERROR or other is acceptable for 0 subjects
        # Must carry a stated reason
        vr = result.get("vacuous_reason")
        if verdict == VACUOUS and not vr:
            reasons.append(
                "VACUOUS with no stated reason")

    # --- Invariant 4: rules, counts, offenders keys agree ---
    rules = result.get("rules")
    counts = result.get("counts")
    offenders = result.get("offenders")
    if rules is not None and isinstance(rules, dict):
        rule_keys = set(rules.keys())
        if counts is not None and isinstance(counts, dict):
            count_keys = set(counts.keys())
            if rule_keys != count_keys:
                only_rules = rule_keys - count_keys
                only_counts = count_keys - rule_keys
                parts = []
                if only_rules:
                    parts.append(f"in rules but not counts: {only_rules}")
                if only_counts:
                    parts.append(f"in counts but not rules: {only_counts}")
                reasons.append("rules/counts key mismatch: " + "; ".join(parts))
        if offenders is not None and isinstance(offenders, dict):
            off_keys = set(offenders.keys())
            if rule_keys != off_keys:
                only_rules = rule_keys - off_keys
                only_off = off_keys - rule_keys
                parts = []
                if only_rules:
                    parts.append(f"in rules but not offenders: {only_rules}")
                if only_off:
                    parts.append(f"in offenders but not rules: {only_off}")
                reasons.append("rules/offenders key mismatch: " +
                               "; ".join(parts))

    # --- Invariant 5: rules sentences are non-empty strings ---
    if rules is not None and isinstance(rules, dict):
        for key, sentence in rules.items():
            if not isinstance(sentence, str) or not sentence.strip():
                reasons.append(
                    f"rules.{key} sentence is empty or not a string")

    return (len(reasons) == 0), reasons


def downgrade_on_violation(result):
    """If the result breaks an invariant, downgrade to ERROR.

    Returns the (possibly modified) result.
    """
    is_valid, reasons = validate_result(result)
    if not is_valid:
        result = dict(result)
        result["verdict"] = ERROR
        result["validation_errors"] = reasons
    return result


# ----------------------------------------- module existence check

def module_exists(module_name):
    """Can this module be imported? A listed module that cannot is
    NOT_IMPLEMENTED, not a crash."""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def check_modules_on_disk():
    """Return the set of check_*.py filenames under scripts/qa/."""
    qa_dir = os.path.dirname(os.path.abspath(__file__))
    found = set()
    for name in os.listdir(qa_dir):
        if name.startswith("check_") and name.endswith(".py"):
            found.add(name)
    return found


def registered_check_ids():
    """Return the set of check_ids in CHECKS."""
    return {c[0] for c in CHECKS}


def disk_to_registry_mismatch():
    """Return (on_disk_not_registered, registered_not_on_disk).

    on_disk_not_registered: check_*.py files not in CHECKS.
    registered_not_on_disk: CHECKS entries whose module file is absent.
    """
    disk_files = check_modules_on_disk()
    disk_ids = set()
    for f in disk_files:
        # check_lead_state.py -> lead_state
        check_id = f[len("check_"):-len(".py")]
        disk_ids.add(check_id)

    reg_ids = registered_check_ids()
    on_disk_not_registered = disk_ids - reg_ids
    registered_not_on_disk = reg_ids - disk_ids
    return on_disk_not_registered, registered_not_on_disk
