"""The QA suite registry: CHECKS, PHASES, verdicts, exit codes.

One table for the verdict vocabulary, one place. Two copies is how pre-push
and post-push come to disagree about what 2 means.

Contract: docs/QA-LANE-F-CONTRACT-2026-09-25.md
"""

# --- Verdict vocabulary (contract §3, §4) ---

PASS = "PASS"
FAIL = "FAIL"
UNCONFIRMED = "UNCONFIRMED"
VACUOUS = "VACUOUS"
ERROR = "ERROR"

ALL_VERDICTS = (PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR)

# Exit code mapping — one table, both phases read it.
VERDICT_EXIT = {
    PASS: 0,
    FAIL: 1,
    UNCONFIRMED: 2,
    VACUOUS: 2,
    ERROR: 3,
}

# --- Phase vocabulary ---

PHASES = ("pre_push", "post_push", "ongoing")

# Refusal semantics by phase: which verdicts REFUSE (not retry, not warn).
# pre_push: nothing has been written, so the cost of refusing is a delay.
#           1, 2, 3 all REFUSE. VACUOUS refuses (ISSUE-041).
# post_push: 1 raises CRITICAL. 2 is RETRIED (not refused). 3 raises CRITICAL.
# ongoing: 1 is ALWAYS A CRITICAL. 2 is CRITICAL if it persists two cycles.
PHASE_REFUSAL = {
    "pre_push": {FAIL, UNCONFIRMED, VACUOUS, ERROR},
    "post_push": {FAIL, ERROR},
    "ongoing": {FAIL, ERROR},
}

# --- The registry (contract §1) ---
# Ordered tuple of (check_id, module_name, phase, blocking).
# A module not listed does not run. A listed module that does not yet exist
# reports NOT_IMPLEMENTED in the table — not PASS, and not silence.
#
# A check may be marked blocking=False in a commit with a reason, which makes
# it advisory in the table and not in the refusal. That is visible in git log.
# A flag on a command line is not permitted.

CHECKS = (
    ("lead_state",        "check_lead_state",        "pre_push",   True),
    ("lead_pack",         "check_lead_pack",         "pre_push",   True),
    ("lead_copy",         "check_lead_copy",         "pre_push",   True),
    ("campaign_bison",    "check_campaign_bison",    "pre_push",   True),
    ("campaign_heyreach", "check_campaign_heyreach", "pre_push",   True),
    ("readback",          "check_readback",          "post_push",  True),
    ("reconcile",         "check_reconcile",         "ongoing",    True),
)


def checks_for_phase(phase, blocking_only=True):
    """Return the (check_id, module_name, blocking) entries for a phase."""
    result = []
    for check_id, module_name, ph, blocking in CHECKS:
        if ph != phase:
            continue
        if blocking_only and not blocking:
            continue
        result.append((check_id, module_name, blocking))
    return result


def worst_verdict(verdicts):
    """Return the worst verdict from a collection, using exit-code ordering."""
    if not verdicts:
        return VACUOUS
    return max(verdicts, key=lambda v: VERDICT_EXIT.get(v, 3))


def exit_code(verdict):
    """The exit code for a verdict."""
    return VERDICT_EXIT.get(verdict, 3)
