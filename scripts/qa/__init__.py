"""The QA check registry.

TASK-292 builds the runner and the full registry. This __init__ provides
the minimal interface check modules need to be importable and discoverable.
"""

CHECKS = {
    "campaign_bison": "scripts.qa.check_campaign_bison",
}
PHASES = ("pre_push", "post_push", "ongoing")

PASS = "PASS"
FAIL = "FAIL"
UNCONFIRMED = "UNCONFIRMED"
VACUOUS = "VACUOUS"
ERROR = "ERROR"


def register(name, module, phase, blocking=True):
    """Register a check module. Called by each check_<group>.py at import."""
    CHECKS[name] = {
        "module": module,
        "phase": phase,
        "blocking": blocking,
    }
