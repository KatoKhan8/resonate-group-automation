#!/usr/bin/env python3
"""The sentence behind the Resume button names a guard that is not wired.

FOUND on 2026-10-15 (GLM-C, TASK 0130, building on pilotcaps 0040/0050 and
glm-b 0080). `src/web/app.py:1624-1630`, the docstring of the handler behind
POST /campaigns/pause and POST /campaigns/resume - the clickable Pause and
Resume buttons - still says, word for word:

    Pause or resume. Neither of these sends anything or starts sending.

    Resuming does not launch: `orchestrator.resume` re-runs every check and
    puts a campaign back into whatever state it was stopped from, and
    `push.run(live=True)` still raises underneath it.

The first half of the second paragraph is true: `orchestrator.resume` runs
`campaigns.validate`, all eighteen checks, and a campaign that fails one is
refused before anything else happens (the control at the bottom of this file
pins that half so it cannot rot silently either).

The last clause is the false sentence. `push.run(live=True)` does still
raise - and nothing on this path calls `push.run`. Resuming asks the
provider directly: `orchestrator.resume` -> `_resume_at_providers` ->
`providerwrites.perform(EMAIL_RESUME)` -> `bison.resume_campaign`. EMAIL_RESUME
carries `facing=False`, so `perform` never runs `executionguard.revalidate`,
which is the only route to `killswitch.require`; no layer of the chain names
a workspace, so `sending.live` is never read either. The three barriers the
operator's CLAUDE.md counts on - refuses in code, `sending.live` false, no
valid stored approval - are absent from this path one layer at a time, which
is what pilotcaps 0050 measured and this file re-measures at the exact
function the button's handler calls.

The sentence was TRUE when it was written. Until `6ff9cc945`
(2026-09-24, "The write ledger, the sealed resume verb, and one log per
watcher") `orchestrator.resume` ended at the local status change and never
touched a provider, so `push.run`'s refusal really was what stood underneath.
That commit added `_resume_at_providers` and EMAIL_RESUME; nobody walked back
to app.py's docstring (`git log -L` shows it untouched since the root commit
`628723472`, 2026-09-09).

THE INVARIANT IS THE BARRIER, NOT THE SENTENCE. A test that greps the
docstring fails when somebody writes a comment. This test asserts the
behaviour the sentence promises: while every killswitch layer refuses - the
build refuses in code and this workspace has never set `sending.live` - a
resume that passes every check may not reach the provider's resume verb.
It was born red because the call arrived. It is green since TASK 0160
(2026-10-15): the role layer now refuses this reviewer one step before the
verb. THE KILLSWITCH GAP ITSELF IS NOT CLOSED - a campaign-layer admin's
identical click still reaches the transport with every killswitch layer
refusing, which is exactly what the control in
`test_the_resume_path_may_not_hand_admin_to_a_reviewer` pins. Read a green
here as "the weakest actor is refused", never as "the button is guarded".

Level: `api.resume_campaign` is exactly what the handler calls
(`app.py:1632-1635`: `run = ... api.resume_campaign`; `run(repo,
fields.get("campaign_id"), by=session["email"])`). The route, the session
and the CSRF check sit above it and add no guard; the session permission for
this route is CAMPAIGN_PAUSE, which a REVIEWER holds. The signed-in user
here is a reviewer on purpose - it is the weakest role that can click the
button, and `roles.REVIEWER` does not even carry RESUME_CAMPAIGN. Until
TASK 0160 (2026-10-15) `api.resume_campaign` passed `role=roles.ADMIN` to
the orchestrator, so the role layer could not refuse this click either;
since 0160 it derives the role from the actor, and that derivation is what
refuses the click now - the missing killswitch stays missing for an actor
the config names.

NOTHING HERE CALLS A PROVIDER. The transport and read-back are injected: the
fixture binds a synthetic provider id (9001, ours only because this test's
ledger row says so) and patches `bison.resume_campaign` / `bison.campaign`,
so the write leaves this process. The socket-level door
(`providers.refuse_unauthorized_write`, the one barrier pilotcaps 0040 found
universal) sits below the patched seam and is not what this file measures.
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import campaigns, killswitch, providerwrites, push, workspaces as ws
from src.providers import bison
from src.repo import Repo
from src.web import api
from tests.campaignbase import CampaignTest

#: Synthetic, bound to this fixture's campaign only (as in
#: tests/test_a_resume_leaves_a_ledger_row.py). Deliberately not one of the
#: operator-declared internal ids (274, 327, 328, 352) or a live campaign
#: (487, 489, 493, 418...): the classifier must pass it because OUR row
#: claims it, and nothing outside this test's temp ledger ever sees it.
PROVIDER = "9001"

#: The weakest role that can click Resume. CAMPAIGN_PAUSE is granted to
#: REVIEWER; RESUME_CAMPAIGN is not - the click survives that asymmetry only
#: because `api.resume_campaign` hardcodes `role=roles.ADMIN`.
REVIEWER = "review@demo.test"

WORKSPACE = "demo"
CAMPAIGN = "c-resume-button"


class TheResumeButtonCannotOutrunTheKillswitch(CampaignTest):
    """A reviewer's click, on a campaign that passes every check."""

    def setUp(self):
        super().setUp()
        # The action ledger pointed at a throwaway file, never real work/.
        self.ledger_tmp = tempfile.mkdtemp(prefix="rga-resume-button-")
        self.ledger_path = os.path.join(self.ledger_tmp,
                                        "provider-writes.jsonl")
        self._old_ledger = os.environ.get(
            providerwrites.PROVIDER_WRITES_LEDGER)
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self.ledger_path
        self.addCleanup(self._restore_ledger)
        self.addCleanup(shutil.rmtree, self.ledger_tmp, ignore_errors=True)

        # A workspace, and a reviewer in it, so the repo below is built the
        # way the request path builds it: behind a membership.
        ws.ensure(WORKSPACE, "Demo Workspace", client=WORKSPACE,
                  created_by="test")
        ws.add_user(REVIEWER, "Ines Reviewer")
        ws.assign(REVIEWER, WORKSPACE, ws.REVIEWER, actor="test")
        self.repo = Repo.for_user(REVIEWER, WORKSPACE)

        # A campaign that would launch: drafted, approved, sender-mapped,
        # provider-bound, paused by hand. The pause is planted rather than
        # performed (pausing is itself a provider write since 09cf9b7c8 and
        # is not what this file measures); the resume is the real path.
        campaign, recs, _ = self.approved_campaign(campaign_id=CAMPAIGN)
        campaign["status"] = campaigns.PAUSED
        campaign["pause"] = {"since": "2026-10-01T00:00:00Z",
                             "by": "fixture", "reason": "paused for a test"}
        self.save_campaign(campaign)

        # THE PREMISES, asserted so this file fails loudly as a fixture and
        # not quietly as a green no-op if the world moves again.
        self.assertTrue(self.repo.may(ws.CAMPAIGN_PAUSE),
                        "the reviewer cannot click Resume; this test no "
                        "longer measures the button's path")
        verdict = campaigns.validate(CAMPAIGN, recs, self.repo.config(),
                                     ignore_status=True)
        self.assertTrue(verdict["ok"],
                        "fixture does not pass every check: %s"
                        % (verdict["blockers"],))
        self.assertTrue(providerwrites.is_supported(providerwrites.EMAIL_RESUME),
                        "EMAIL_RESUME left SUPPORTED; this test no longer "
                        "measures a provider resume")
        self.assertEqual(providerwrites.classify_campaign("email", PROVIDER),
                         providerwrites.RESONATE_OS,
                         "fixture is not resonate_os; the resume would be a "
                         "refusal, not a write")
        # Every killswitch layer refuses, measured not assumed.
        self.assertTrue(hasattr(push, "LiveSendNotEnabled"),
                        "push no longer refuses in code; the killswitch's "
                        "global layer changed shape and this premise - the "
                        "one CLAUDE.md counts as barrier one - needs "
                        "re-reading")
        self.assertFalse(killswitch.workspace_state(WORKSPACE)["sending"],
                         "sending.live is on for this workspace; barrier "
                         "two is not refusing")
        self.assertFalse(killswitch.state(workspace=WORKSPACE)["sending"],
                         "the killswitch permits; nothing this file asserts "
                         "about refusal can hold")

    def _restore_ledger(self):
        if self._old_ledger is None:
            os.environ.pop(providerwrites.PROVIDER_WRITES_LEDGER, None)
        else:
            os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self._old_ledger

    def test_a_resume_that_passes_every_check_may_not_reach_the_provider(self):
        """THE INVARIANT. Green since the 0160 role fix: the role layer
        refuses this reviewer before the verb. The killswitch gap it was
        born red on remains open for campaign-layer admins - see the
        module docstring and the control in
        test_the_resume_path_may_not_hand_admin_to_a_reviewer."""
        called = []

        def fake_resume(pid, expect_leads=None, **kw):
            called.append((pid, expect_leads))
            return {"ok": True}

        with mock.patch.object(bison, "resume_campaign", fake_resume), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: {"status": "running"}):
            try:
                api.resume_campaign(self.repo, CAMPAIGN, by=REVIEWER)
            except api.ActionRefused:
                # The shape the honest world takes: a refusal surfaced to
                # the browser as a 409 page. The invariant is below either
                # way.
                pass
        self.assertEqual(
            called, [],
            "the resume behind the button reached bison.resume_campaign "
            "(calls: %r) while every killswitch layer refuses: the build "
            "refuses in code and sending.live has never been set for this "
            "workspace. The docstring's promise - that push.run(live=True) "
            "'still raises underneath it' - is true of push.run and "
            "irrelevant here: nothing on this path calls it." % (called,))

    def test_a_failed_check_still_stops_the_resume_before_the_provider(self):
        """The TRUE half of the sentence, pinned so it cannot rot unnoticed.

        `orchestrator.resume` re-runs every check; a campaign that fails one
        is refused and the provider is not asked. Since TASK 0160 this
        reviewer is refused one step earlier still - `roles.require` runs
        before validate in `orchestrator.resume` - so for THIS actor the
        control no longer distinguishes the two refusals; what it still pins
        is that a failed-check resume raises a refusal and the transport is
        never reached. The check-refusal itself is measured for an actor the
        client config does name, at orchestrator level, in
        `test_orchestration.py`
        (`test_resuming_re_checks_everything_rather_than_trusting_the_pause`).
        """
        campaign = campaigns.require(CAMPAIGN)
        campaign["approval"] = None          # "campaign approved" fails
        self.save_campaign(campaign)
        called = []
        with mock.patch.object(bison, "resume_campaign",
                               lambda pid, expect_leads=None, **kw:
                               called.append(pid) or {"ok": True}), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: {"status": "running"}):
            with self.assertRaises(api.ActionRefused):
                api.resume_campaign(self.repo, CAMPAIGN, by=REVIEWER)
        self.assertEqual(called, [],
                         "a resume that failed a check reached the provider")


if __name__ == "__main__":
    unittest.main()
