"""The 487 recovery write goes through the door, or not at all.

TASK 0072. `scripts/resume_487.py` performed the authorized resume with a
direct `bison.resume_campaign` call inside its own `providers.allow_writes`
scope. The opt-in at the entry point is correct and stays - it is door A,
and the incident of 2026-09-20 is exactly why a library must never open it
for itself. But the VERB also skipped door B - `providerwrites.perform`,
the sink that owns ownership, the TASK-331 suppression revalidation, the
staging guard, the write ledger and the read-back classification.

INVARIANT, not sentence: whenever this script reaches the provider resume
verb, the call happens INSIDE `providerwrites.perform(EMAIL_RESUME)`, and
the attempt leaves a door ledger row. An open `allow_writes` scope says the
operator consented to a transport; it is not evidence that the write passed
the door.

No network, no provider call, no live resume: `bison` is patched at the
module seam and `providerwrites.perform` is wrapped around the real one, so
the door's own guards still run against a temporary estate. The script's
five conditions (window, truth, once, copy, membership) are supplied as
passing gates here - they are pinned by their own module - so the write
itself can be observed.
"""
import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import campaigns, providerwrites           # noqa: E402
from src.providers import bison                     # noqa: E402
from tests.campaignbase import CampaignTest        # noqa: E402

from scripts import resume_487                      # noqa: E402

CANONICAL = "productive-email-control-v3"


class _DoorHarness(CampaignTest):
    """A temporary estate plus a redirected provider-write ledger."""

    def setUp(self):
        super().setUp()
        self.ledger = os.path.join(self.tmp, "work", "provider-writes.jsonl")
        self._ledger_env = os.environ.get("PROVIDER_WRITES_LEDGER")
        os.environ["PROVIDER_WRITES_LEDGER"] = self.ledger
        self.addCleanup(self._restore_ledger)

    def _restore_ledger(self):
        if self._ledger_env is None:
            os.environ.pop("PROVIDER_WRITES_LEDGER", None)
        else:
            os.environ["PROVIDER_WRITES_LEDGER"] = self._ledger_env

    def ledger_rows(self):
        if not os.path.exists(self.ledger):
            return []
        with open(self.ledger, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def bind_487(self):
        """A canonical campaign row bound to provider campaign 487.

        The script hardcodes CAMPAIGN = 487; ownership resolves through the
        canonical row's `bison_campaign_id` binding, exactly as the door
        resolves it for the orchestrator's own resume path.
        """
        recs = self.seed_records()
        campaign = self.make_campaign(recs, campaign_id=CANONICAL)
        campaign["bison_campaign_id"] = str(resume_487.CAMPAIGN)
        campaigns.save([campaign])
        return campaign

    def drive_the_recovery(self, record_resume, spy):
        """Run the real `--live` path against the patched provider seam."""
        truth = ({"status": "paused"}, {"sending_paused": 10},
                 {"timezone": "Europe/Zagreb"})
        after_row = {"status": "running"}
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                mock.patch.object(resume_487, "_setup_data_access",
                                  lambda: None), \
                mock.patch.object(resume_487, "window_gate", lambda: True), \
                mock.patch.object(resume_487, "truth_gate",
                                  lambda bison_arg: truth), \
                mock.patch.object(resume_487, "copy_gate", lambda: True), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: dict(after_row)), \
                mock.patch.object(bison, "membership", lambda pid: {}), \
                mock.patch.object(bison, "resume_campaign", record_resume), \
                mock.patch.object(providerwrites, "perform", spy):
            code = resume_487.main(["--live"])
        return code, out.getvalue()


class TheResumeVerbPassesTheDoor(_DoorHarness):

    def test_the_verb_is_reached_only_inside_perform(self):
        campaign = self.bind_487()
        self.assertEqual(str(resume_487.CAMPAIGN),
                         str(campaign["bison_campaign_id"]))

        reached, state = [], {"inside_perform": False}
        real_perform = providerwrites.perform

        def spy(operation, *args, **kw):
            state["inside_perform"] = True
            try:
                return real_perform(operation, *args, **kw)
            finally:
                state["inside_perform"] = False

        def record_resume(campaign_id, expect_leads=None):
            reached.append({"campaign": campaign_id,
                            "expect_leads": expect_leads,
                            "inside_perform": state["inside_perform"]})

        code, output = self.drive_the_recovery(record_resume, spy)

        # The membership acceptance test reads {} here, so main classifies
        # UNCLASSIFIED and exits 1 in both states. The invariant under test
        # is about the write, not the verdict, so the code is not asserted.
        self.assertIn("WRITING", output)
        self.assertTrue(reached,
                        "the recovery never reached the verb; the fixture "
                        "stopped it before the write and proves nothing")
        for call in reached:
            self.assertEqual(resume_487.CAMPAIGN, call["campaign"])
            self.assertEqual(resume_487.EXPECT_LEADS, call["expect_leads"])
            self.assertTrue(
                call["inside_perform"],
                "bison.resume_campaign was called OUTSIDE "
                "providerwrites.perform: door A was open but the write "
                "bypassed the sink")
        resume_rows = [row for row in self.ledger_rows()
                       if row.get("operation") == providerwrites.EMAIL_RESUME]
        self.assertEqual(
            [CANONICAL], [row.get("campaign") for row in resume_rows],
            "the resume attempt left no door ledger row: a write that "
            "bypasses perform is invisible to the audit")
        self.assertTrue(
            resume_rows and all(row.get("outcome") == "accepted"
                                for row in resume_rows),
            "the door ledger row for the resume is not an accepted attempt: "
            + json.dumps(resume_rows))


if __name__ == "__main__":
    unittest.main()
