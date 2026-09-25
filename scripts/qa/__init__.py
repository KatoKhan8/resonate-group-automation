"""The QA check registry.

Each check module registers itself in CHECKS with its phase and whether it
is blocking. The runner (TASK-292) imports this and iterates CHECKS to
decide what to run for a given phase.
"""

CHECKS = {
    "lead_state": {
        "module": "scripts.qa.check_lead_state",
        "phase": "pre_push",
        "blocking": True,
        "subject": "lead",
    },
}

PHASES = ("pre_push", "post_push", "ongoing")

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_UNCONFIRMED = "UNCONFIRMED"
VERDICT_VACUOUS = "VACUOUS"
VERDICT_ERROR = "ERROR"
