"""The QA registry: CHECKS, PHASES, verdicts.

TASK-292 owns the harness. Each check module conforms to the contract in
``docs/QA-LANE-F-CONTRACT-2026-09-25.md`` and is listed here by name.
A check module that is not registered does not run — deliberate, because
a check with no caller is a check that does nothing (``CLAUDE.md``:
"Existence is not function").
"""

CHECKS = {
    "lead_copy": {
        "module": "scripts.qa.check_lead_copy",
        "phase": "pre_push",
        "blocking": True,
        "subject": "lead",
    },
}

PHASES = ("pre_push", "post_push", "ongoing")

VERDICTS = ("PASS", "FAIL", "UNCONFIRMED", "VACUOUS", "ERROR")
