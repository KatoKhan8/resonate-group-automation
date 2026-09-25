"""The QA registry and shared verdict machinery.

Each check module registers itself in CHECKS with a phase. The runner
(`run.py`, TASK-292) imports this registry to discover what to execute.

A check that is not listed here does not run. This is deliberate: a check
with no registration is a check with no caller, and this codebase has
shipped that defect before (`heyreach.linkedin_sequence` had no caller).
"""

CHECKS = {
    "lead_pack": {
        "module": "scripts.qa.check_lead_pack",
        "phase": "pre_push",
        "subject": "lead",
        "blocking": True,
    },
}

PHASES = ("pre_push", "post_push", "ongoing")

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_UNCONFIRMED = "UNCONFIRMED"
VERDICT_VACUOUS = "VACUOUS"
VERDICT_ERROR = "ERROR"
