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
    # TASK-298, registered on integration. The module was merged from
    # origin/qwen-worker-r9 @ ac4190cd, which declares exactly these three
    # values for it. Registering it is not optional: the docstring above says
    # a check module that is not listed here does not run, so merging the
    # file without this entry is the DISCONNECTED defect - a check computed
    # correctly that nothing reaches.
    "readback": {
        "module": "scripts.qa.check_readback",
        "phase": "post_push",
        "subject": "campaign",
        "blocking": True,
    },
}

# NOT REGISTERED, and recorded rather than guessed: scripts/qa/
# check_campaign_heyreach.py is on master (TASK-297, integrated in the first
# pass) and is absent from CHECKS, so by the rule above it does not run in the
# harness. It is argparse-gated and runnable standalone, so it is not dead -
# but it is not in the suite either. Its phase, subject and blocking values
# were never declared anywhere, and inventing them here would be a
# configuration nobody asked for. Whoever owns TASK-292's runner should
# declare them.

PHASES = ("pre_push", "post_push", "ongoing")

PASS = "PASS"
FAIL = "FAIL"
UNCONFIRMED = "UNCONFIRMED"
VACUOUS = "VACUOUS"
ERROR = "ERROR"
VERDICTS = (PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR)
