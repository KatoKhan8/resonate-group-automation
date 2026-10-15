#!/usr/bin/env python3
"""The resume path hands ADMIN to whoever clicked, reviewer included.

FOUND on 2026-10-15 (GLM-C, TASK 0140, on what TASK 0130 measured on the way
to its own finding). The clickable Resume button is gated by ONE permission:
POST /campaigns/resume requires the workspace permission CAMPAIGN_PAUSE
(`src/web/app.py:1378-1380`), which a workspace REVIEWER holds
(`src/workspaces.py:116-119`). `api.resume_campaign` checks that same
permission (`src/web/api.py:3212`) - and then hands the orchestrator
`role=roles.ADMIN`, hardcoded, never derived from the actor
(`src/web/api.py:3223`). The first thing `orchestrator.resume` does with that
argument is `roles.require(role, RESUME_CAMPAIGN)`: the one layer that would
refuse a reviewer is fed the one role it cannot refuse.

THE ESCALATION IS REAL, NOT APPARENT. Everything else between the click and
the provider verb is actor-blind: `campaigns.validate` checks readiness, the
suppression recheck checks the audience, the ownership default-refuse checks
the campaign, and `providerwrites.perform` never consults who is asking - `by`
is only written to the ledger. TASK 0130's committed test is the empirical
proof: a reviewer's resume reaches `bison.resume_campaign` while every
killswitch layer refuses. The role layer is the only guard positioned to
refuse this click, and the hardcode is the only reason it does not.

BORN DAY-ONE, TEETH THREE WEEKS LATER. Both ingredients are root: the
`role=roles.ADMIN` hardcode in api.py and the CAMPAIGN_PAUSE-to-REVIEWER grant
in workspaces.py each have a single pickaxe hit, commit `628723472`
(2026-09-09T21:32:34+02:00) - this path has never once consulted the actor.
Until `6ff9cc945` (2026-09-24T16:53:55+02:00, "The write ledger, the sealed
resume verb, and one log per watcher") a resume ended at the local status
change, so the escalation was inert; that commit added `_resume_at_providers`
and EMAIL_RESUME, and a reviewer's click became a provider write.

THE ASYMMETRY IT BREAKS IS DELIBERATE. `roles.GRANTS` says so in one line -
a reviewer "can stop a run, but cannot start one" - and `orchestrator.freeze`'s
docstring repeats it: stopping is easier than starting again. Pause honours it
even with its own hardcode: campaign-layer REVIEWER legitimately holds
PAUSE_CAMPAIGN (`src/web/api.py:3185` passes ADMIN where REVIEWER would do;
inert, the gate above has already decided). Resume cannot: NO campaign-layer
role both matches the population the workspace gate admits (reviewer upward)
and holds RESUME_CAMPAIGN (admin only). Passing ADMIN silently chose "everyone
the gate admits may resume". The approve path one screen over does it honestly
- `app.py:1714` passes `role=roles.REVIEWER` to `orchestrator.decide`, and
decide's own contract (`orchestrator.py:420-447`) says the server derives the
role, never the request.

THE INVARIANT IS THE BARRIER, NOT THE CODE SHAPE. A test that greps api.py for
"roles.ADMIN" fails when somebody renames a variable. This file asserts the
behaviour: a session holding only CAMPAIGN_PAUSE cannot cause a provider
resume write. It failed red from its birth at `32cb420f7` because the write
happened. TASK 0160 (2026-10-15, operator-approved) applied the fix -
`api.resume_campaign` now derives the role from the actor - and the
invariant below holds BECAUSE the role check refuses the reviewer: the
refusal itself is asserted, by exception type, by permission and by the
role the actor actually holds, so a green caused by any other layer
refusing is caught here and a green caused by every layer refusing is
caught by the control. The control below makes the same click from an actor
who IS campaign-layer admin under the same config (`U0DEMOADMIN1`,
demo.yaml's sole slack.allowed_approvers entry) and expects the transport
to be reached - green before and after the fix alike, and deliberately
loud if some GLOBAL guard (a killswitch wired into the verb, say) starts
refusing everyone, because that would be a different barrier firing first
and this file would need re-reading.

NOTHING HERE CALLS A PROVIDER. The transport and read-back are injected: the
fixture binds a synthetic provider id (9001, ours only because this test's
temp ledger row says so) and patches `bison.resume_campaign` / `bison.campaign`
blind - no file under `src/providers/*` was read to write this test. TASK
0140 committed the born-red pair and left the fix to the operator; TASK 0160
applied it (one line in api.py, nothing in roles.py or workspaces.py) and
added the refusal-reason assertions below.
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import campaigns, providerwrites, roles, workspaces as ws
from src.providers import bison
from src.repo import Repo
from src.web import api
from tests.campaignbase import CampaignTest

#: Synthetic, bound to this fixture's campaign only (as in TASK 0130's test).
#: Deliberately not one of the operator-declared internal ids (274, 327, 328,
#: 352) or a live campaign (487, 489, 493, 418...): the classifier must pass
#: it because OUR row claims it, and nothing outside this test's temp ledger
#: ever sees it.
PROVIDER = "9001"

#: The weakest role that can click Resume: a workspace REVIEWER, and - under
#: the demo client config - a campaign-layer VIEWER. `roles.role_of` reads
#: `slack.allowed_approvers` / `allowed_reviewers`; demo.yaml names only
#: U0DEMOADMIN1, so this actor is nobody at the layer the hardcode overrides.
REVIEWER = "review@demo.test"

#: Campaign-layer ADMIN under the same config (demo.yaml's sole approver),
#: seated as workspace WORKSPACE_ADMIN so the workspace gate lets the control
#: click through exactly as it lets the reviewer.
ADMIN = "U0DEMOADMIN1"

WORKSPACE = "demo"
CAMPAIGN = "c-resume-role"


class TheResumePathMayNotHandAdminToAReviewer(CampaignTest):
    """A reviewer's click and an admin's click, on one identical fixture."""

    def setUp(self):
        super().setUp()
        # The action ledger pointed at a throwaway file, never real work/.
        self.ledger_tmp = tempfile.mkdtemp(prefix="rga-resume-role-")
        self.ledger_path = os.path.join(self.ledger_tmp,
                                        "provider-writes.jsonl")
        self._old_ledger = os.environ.get(
            providerwrites.PROVIDER_WRITES_LEDGER)
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self.ledger_path
        self.addCleanup(self._restore_ledger)
        self.addCleanup(shutil.rmtree, self.ledger_tmp, ignore_errors=True)

        # One workspace, two members: the reviewer the invariant refuses and
        # the admin the control expects. Both repos are built the way the
        # request path builds them: behind a membership.
        ws.ensure(WORKSPACE, "Demo Workspace", client=WORKSPACE,
                  created_by="test")
        ws.add_user(REVIEWER, "Ines Reviewer")
        ws.assign(REVIEWER, WORKSPACE, ws.REVIEWER, actor="test")
        ws.add_user(ADMIN, "Adam Admin")
        ws.assign(ADMIN, WORKSPACE, ws.WORKSPACE_ADMIN, actor="test")
        self.repo = Repo.for_user(REVIEWER, WORKSPACE)
        self.admin_repo = Repo.for_user(ADMIN, WORKSPACE)

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
        self.assertTrue(self.admin_repo.may(ws.CAMPAIGN_PAUSE),
                        "the control cannot click Resume either; the two "
                        "clicks no longer differ only in who is asking")
        self.assertEqual(roles.role_of(self.repo.config(), REVIEWER),
                         roles.VIEWER,
                         "the reviewer is no longer campaign-layer VIEWER "
                         "under the demo config; the premise that the "
                         "hardcode overrides a refusal has moved")
        self.assertEqual(roles.role_of(self.admin_repo.config(), ADMIN),
                         roles.ADMIN,
                         "the control actor is no longer campaign-layer "
                         "ADMIN under the demo config; the control no longer "
                         "proves the path is alive for a permitted actor")
        self.assertFalse(roles.may(roles.REVIEWER, roles.RESUME_CAMPAIGN),
                         "campaign-layer REVIEWER gained RESUME_CAMPAIGN; "
                         "the deliberate asymmetry this file pins has been "
                         "deliberately removed - re-read before touching "
                         "anything")
        self.assertTrue(roles.may(roles.ADMIN, roles.RESUME_CAMPAIGN),
                        "campaign-layer ADMIN lost RESUME_CAMPAIGN; the "
                        "control below would refuse for a reason this file "
                        "does not measure")
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

    def _restore_ledger(self):
        if self._old_ledger is None:
            os.environ.pop(providerwrites.PROVIDER_WRITES_LEDGER, None)
        else:
            os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self._old_ledger

    def test_a_session_holding_only_campaign_pause_may_not_reach_the_resume_verb(self):
        """THE INVARIANT. Green because the role check refuses the reviewer.

        Born red at `32cb420f7`: the call arrived then. The 0160 fix derives
        the campaign-layer role from the actor, so the refusal now comes
        from `roles.require` inside `orchestrator.resume` - and is asserted
        below as exactly that, because a refusal by any OTHER layer would
        make this green for a reason nobody pinned.
        """
        called = []
        refused = None

        def fake_resume(pid, expect_leads=None, **kw):
            called.append((pid, expect_leads))
            return {"ok": True}

        with mock.patch.object(bison, "resume_campaign", fake_resume), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: {"status": "running"}):
            try:
                api.resume_campaign(self.repo, CAMPAIGN, by=REVIEWER)
            except api.ActionRefused as e:
                # The shape the honest world takes: the role layer's
                # NotPermitted surfaced by api.py's except clause as a 409
                # page. What matters is WHICH refusal it was.
                refused = str(e)
        self.assertEqual(
            called, [],
            "a session holding only CAMPAIGN_PAUSE reached "
            "bison.resume_campaign (calls: %r). Every other layer on this "
            "path is actor-blind; the one guard positioned to refuse this "
            "click - roles.require(role, RESUME_CAMPAIGN) in "
            "orchestrator.resume - was not fed the actor's derived role "
            "(src/web/api.py, resume_campaign): either the derivation was "
            "removed or something is handing it a constant again" % (called,))
        self.assertIsNotNone(
            refused,
            "no refusal was raised at all: the write was refused by nothing "
            "and merely failed to happen, which no layer answered for")
        self.assertIn(
            "NotPermitted", refused,
            "the refusal did not come from the role layer (a validate "
            "failure surfaces as NotReady, a global guard as something else "
            "again): %r" % (refused,))
        self.assertIn(
            "'resume_campaign'", refused,
            "the role layer refused a different permission than "
            "RESUME_CAMPAIGN: %r" % (refused,))
        self.assertIn(
            "holds role 'viewer'", refused,
            "the refusing role was not the actor's DERIVED role - somebody "
            "is feeding the orchestrator a role again instead of deriving "
            "it: %r" % (refused,))

    def test_the_same_click_from_a_campaign_layer_admin_still_reaches_the_provider(self):
        """THE CONTROL. Green today and under the honest fix alike.

        The identical fixture and the identical click, from an actor who is
        campaign-layer ADMIN under the same config: the transport IS reached.
        This proves the path the invariant test measures is alive, and that
        its refusal is about who is asking - not a dead route or a global
        guard. If THIS test ever fails red while the fixture premises above
        still hold, a global refusal has appeared on the path (a killswitch
        wired into the verb, say) and both tests need re-reading.
        """
        called = []

        def fake_resume(pid, expect_leads=None, **kw):
            called.append((pid, expect_leads))
            return {"ok": True}

        with mock.patch.object(bison, "resume_campaign", fake_resume), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: {"status": "running"}):
            try:
                api.resume_campaign(self.admin_repo, CAMPAIGN, by=ADMIN)
            except api.ActionRefused:
                # The read-back classification may still refuse after the
                # transport fired; what this control pins is the arrival.
                pass
        self.assertEqual(
            [c[0] for c in called], [PROVIDER],
            "the campaign-layer admin's click did not reach "
            "bison.resume_campaign (calls: %r) - the control is red, so "
            "either the fixture broke or a GLOBAL guard has appeared on the "
            "resume path and the invariant test's refusal is no longer about "
            "who is asking" % (called,))


if __name__ == "__main__":
    unittest.main()
