"""The QA refusal function for factory integration.

TASK-292. This module provides `_refuse_qa`, the function that goes inside
`bisonfactory.stage` and `heyreachfactory.stage` immediately after
`_refuse_copylint` and before the first provider call.

It raises FactoryRefused carrying the runner's own rendered table, not a
sentence written at the raise site, so a rule that did not exist when the
function was written still names itself in the refusal.

DELIVERED AS A PATCH PROPOSAL for bisonfactory.py and heyreachfactory.py.
Lane D holds bisonfactory; the production session applies the patch after
lane D lands.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.qa import run as qa_run
from scripts.qa import PHASE_REFUSAL, PASS, worst_verdict


def _refuse_qa(plan, recs, report, *, workspaces=None):
    """Run the pre-push QA suite and refuse if any blocking check fails.

    Goes inside bisonfactory.stage and heyreachfactory.stage, immediately
    after _refuse_copylint and before bison.bound_workspace() / the first
    provider call.

    Raises FactoryRefused carrying the runner's own rendered table.

    Parameters
    ----------
    plan : dict
        The campaign plan (from _plan).
    recs : list
        Queue records.
    report : dict
        The staging report being built.
    workspaces : str, optional
        Path to work/ copy. If None, uses the local work/.
    """
    campaigns = []
    campaign_id = report.get("campaign")
    if campaign_id:
        campaigns = [str(campaign_id)]

    batch = None
    for rec in (recs or []):
        b = rec.get("batch_id")
        if b:
            batch = b
            break

    results, worst, exit_code, table, output_dir = qa_run.run_phase(
        "pre_push",
        batch=batch,
        campaigns=campaigns,
        workspaces=workspaces,
    )

    report["qa"] = {
        "results": results,
        "verdict": worst,
        "exit_code": exit_code,
        "table": table,
        "output_dir": output_dir,
    }

    if worst == PASS:
        return

    refusal = PHASE_REFUSAL.get("pre_push", {}).get(worst, "REFUSE")
    if refusal == "REFUSE":
        # Import here to avoid circular imports at module level.
        # The caller (bisonfactory or heyreachfactory) has its own
        # FactoryRefused; we raise with the table as the message.
        raise _QARefused(
            f"the pre-push QA suite refuses this push:\n{table}\n"
            f"Nothing was written to either provider.",
            table=table, report=report)


class _QARefused(Exception):
    """The QA suite refused the push.

    Carries the runner's own rendered table, so a rule that did not exist
    when this function was written still names itself in the refusal.
    """

    def __init__(self, *args, table=None, report=None):
        super().__init__(*args)
        self.table = table
        self.report = report
