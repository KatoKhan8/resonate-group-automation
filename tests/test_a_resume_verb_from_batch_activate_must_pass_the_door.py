"""The batch activator's write goes through the door, or not at all.

TASK 0072. `scripts/batch_activate.py` activated the batch campaigns with a
direct `bison.resume_campaign` call inside its own `providers.allow_writes`
scope. That opens door A - the host-side transport opt-in, which says the
OPERATOR consented - and skips door B entirely: `providerwrites.perform`,
the sink that owns ownership, the TASK-331 suppression revalidation, the
staging guard, the write ledger and the read-back classification. The one
gate written specifically to stop an unauthorized resume is the one this
path skipped.

INVARIANT, not sentence: whenever the batch activator reaches the provider
resume verb, the call happens INSIDE `providerwrites.perform(EMAIL_RESUME)`,
and the attempt leaves a door ledger row. `allow_writes` authorises the
transport; it is not evidence that the write passed the door, which is why
this test does not merely assert that the scope was open.

No network, no provider call, no live activation: `bison` is patched at the
module seam and `providerwrites.perform` is wrapped around the real one, so
the door's own guards still run against a temporary estate.
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

from src import providerwrites                      # noqa: E402
from src.providers import bison                     # noqa: E402
from tests.campaignbase import CampaignTest        # noqa: E402

from scripts import batch_activate                  # noqa: E402

PREFIX = "productive-email-batch1-"
CANONICAL = PREFIX + "alpha"


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

    def drive_the_activator(self, record_resume, spy):
        """Run the real `--live` path against the patched provider seam.

        Every patch here is a seam, never a decision: the environment loader,
        the mailbox read, the clock and the provider reads are supplied so the
        write itself can be observed. The write path - hard stops, the
        `allow_writes` scope, the verb - is the code under test and is not
        patched.
        """
        provider_row = {"status": "running", "total_leads": 2,
                        "emails_sent": 0, "bounced": 0, "unsubscribed": 0}
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                mock.patch.object(batch_activate, "load_env", lambda: None), \
                mock.patch.object(batch_activate, "mailbox_health",
                                  lambda: {}), \
                mock.patch.object(batch_activate, "ROOT", self.tmp), \
                mock.patch.object(batch_activate.time, "sleep",
                                  lambda seconds: None), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: dict(provider_row)), \
                mock.patch.object(bison, "scheduled_emails",
                                  lambda pid: []), \
                mock.patch.object(bison, "resume_campaign", record_resume), \
                mock.patch.object(providerwrites, "perform", spy):
            code = batch_activate.main(["--live"])
        return code, out.getvalue()


class TheResumeVerbPassesTheDoor(_DoorHarness):

    def test_the_verb_is_reached_only_inside_perform(self):
        recs = self.seed_records()
        campaign = self.make_campaign(recs, campaign_id=CANONICAL)
        self.assertEqual("9001", str(campaign["bison_campaign_id"]))

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

        code, output = self.drive_the_activator(record_resume, spy)

        self.assertEqual(0, code, output)
        self.assertTrue(reached,
                        "the activator never reached the verb; the fixture "
                        "stopped it before the write and proves nothing")
        for call in reached:
            self.assertEqual("9001", str(call["campaign"]))
            self.assertEqual(2, call["expect_leads"])
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
