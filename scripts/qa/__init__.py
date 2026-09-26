"""The QA check registry.

TASK-292 builds the full harness. This module exists so check_reconcile.py
is importable as ``scripts.qa.check_reconcile`` and so the registry can
name the check groups that exist.

A check module that is not listed in CHECKS does not run.
"""

CHECKS = {
    "reconcile": {
        "module": "scripts.qa.check_reconcile",
        "phase": "ongoing",
        "subject": "lead",
        "blocking": True,
    },
}

PHASES = ("pre_push", "post_push", "ongoing")

PASS = "PASS"
FAIL = "FAIL"
UNCONFIRMED = "UNCONFIRMED"
VACUOUS = "VACUOUS"
ERROR = "ERROR"
VERDICTS = (PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR)
