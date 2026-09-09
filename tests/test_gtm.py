"""Why this workspace is worked the way it is.

Three properties, and every test is one of them:

**It decides nothing.** Recording a decision changes no setting, excludes
no company and blocks no send. A decision store that also enforced would
be a second configuration system quietly disagreeing with the first, and
the one nobody thinks to check when a campaign behaves oddly.

**Evidence, or an honest admission that there is none.** "Judgement,
nothing measured" is an allowed basis because it is frequently the true
answer. A required field with no honest option is a field that gets filled
with plausible-sounding fiction, and a decision that *looks* evidenced is
worse than one that admits it was a hunch.

**Superseded, never edited.** "We believed X, then we learned Y" is the
whole value of a decision log. A log showing only the current belief is a
configuration file with worse ergonomics.
"""
import os
import shutil
import tempfile
import unittest

from src import gtm, repo as repo_module, store, workspaces
from src.web import api
from tests.base import ProviderTest

WS = "productive"


class GtmTest(ProviderTest):

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-gtm-")
        self._env = {k: os.environ.get(k) for k in
                     ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES", "AUDIT",
                      "GTM", "SIGNALS", "CLIENTS_DIR", "OUT")}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")
        os.environ["OUT"] = os.path.join(self.tmp, "out")

        from src.web import demodata
        demodata.install_configs()

        workspaces.ensure(WS, "Productive", client="productive")
        workspaces.ensure("contactout", "ContactOut", client="contactout")
        for email, role in (("admin@x.test", workspaces.WORKSPACE_ADMIN),
                            ("op@x.test", workspaces.OPERATOR),
                            ("view@x.test", workspaces.VIEWER)):
            workspaces.add_user(email, email)
            workspaces.assign(email, WS, role)

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def repo(self, email="admin@x.test", workspace=WS):
        return repo_module.Repo.for_user(email, workspace)

    def decide(self, repo=None, area=gtm.TARGETING,
               decided="Stop targeting agencies under 20 people",
               why="Eleven replied and none had a budget holder", **kw):
        return api.record_decision(repo or self.repo(), area, decided, why,
                                   **kw)


class ItDecidesNothing(GtmTest):
    """The property the module exists to preserve."""

    def test_recording_a_decision_changes_no_setting(self):
        before = dict(workspaces.policy(WS))
        self.decide(policy_key="market.size_min_employees",
                    decided="Move the floor to 50 employees",
                    why="Nothing under 50 has ever booked a meeting")
        self.assertEqual(workspaces.policy(WS), before)

    def test_a_decision_about_a_setting_does_not_set_it(self):
        """The one somebody will expect to work, and it deliberately does
        not: the settings screen is the only thing that changes what the
        machine does."""
        self.decide(policy_key="sending.daily_email_volume",
                    decided="Raise the daily email volume to 90",
                    why="The senders have been warm for six weeks")
        config = self.repo().config()
        self.assertNotEqual(
            ((config.get("sending") or {}).get("daily_email_volume")), 90)

    def test_it_cannot_be_attached_to_a_setting_that_does_not_exist(self):
        with self.assertRaises(gtm.DecisionRefused):
            self.decide(policy_key="market.invented_key")


class EvidenceOrAnHonestAdmission(GtmTest):

    def test_judgement_is_allowed_and_needs_no_evidence(self):
        entry = self.decide(basis=gtm.JUDGEMENT)
        self.assertEqual(entry["basis"], gtm.JUDGEMENT)
        self.assertIsNone(entry["evidence"])

    def test_a_measured_decision_must_say_what_was_measured(self):
        """Otherwise "measured" is a word somebody picked from a dropdown."""
        with self.assertRaises(gtm.DecisionRefused) as caught:
            self.decide(basis=gtm.MEASURED)
        self.assertIn("evidence", str(caught.exception))

    def test_research_needs_a_source_too(self):
        with self.assertRaises(gtm.DecisionRefused):
            self.decide(basis=gtm.RESEARCH)

    def test_a_measured_decision_with_its_numbers_is_accepted(self):
        entry = self.decide(basis=gtm.MEASURED,
                            evidence="40 replies in Q2, 0 meetings under 20")
        self.assertIn("40 replies", entry["evidence"])

    def test_a_decision_with_no_reason_is_refused(self):
        with self.assertRaises(gtm.DecisionRefused) as caught:
            self.decide(why="dunno")
        self.assertIn("re-examined", str(caught.exception))

    def test_a_decision_with_no_substance_is_refused(self):
        with self.assertRaises(gtm.DecisionRefused):
            self.decide(decided="yes")

    def test_the_summary_separates_checkable_from_argued(self):
        """The distinction a reader needs: this can be re-examined by
        looking at data, that has to be argued again."""
        self.decide(basis=gtm.MEASURED, evidence="40 replies in Q2")
        self.decide(basis=gtm.JUDGEMENT, area=gtm.CHANNEL,
                    decided="Lead with LinkedIn in DACH",
                    why="Email reputation there is worse than ours")
        out = gtm.summarise(WS)
        self.assertEqual(out["checkable"], 1)
        self.assertEqual(out["judgement"], 1)


class SupersededNeverEdited(GtmTest):

    def test_the_old_decision_survives_with_its_original_words(self):
        first = self.decide(decided="Stop targeting agencies under 20 people",
                            why="Eleven replied and none had a budget holder")
        rows = gtm.load(WS)
        self.decide(supersedes=rows[0]["id"],
                    decided="Target agencies from 10 people upward again",
                    why="Two of the small ones became clients this quarter")
        history = gtm.history(WS)
        self.assertEqual(len(history), 2)
        old = [r for r in history if r.get("superseded_by")][0]
        self.assertEqual(old["decided"], first["decided"])
        self.assertEqual(old["why"], first["why"])

    def test_a_superseded_decision_leaves_the_current_view(self):
        self.decide()
        rows = gtm.load(WS)
        self.decide(supersedes=rows[0]["id"],
                    decided="Target agencies from 10 people upward again",
                    why="Two of the small ones became clients this quarter")
        current = gtm.current(WS)
        self.assertEqual(len(current), 1)
        self.assertIn("10 people upward", current[0]["decided"])

    def test_the_new_decision_points_back_at_what_it_replaced(self):
        self.decide()
        old_id = gtm.load(WS)[0]["id"]
        new = self.decide(supersedes=old_id,
                          decided="Target agencies from 10 people upward",
                          why="Two of the small ones became clients")
        self.assertEqual(new["supersedes"], old_id)

    def test_superseding_the_same_decision_twice_is_refused(self):
        """Otherwise the chain forks and "what do we believe now" has two
        answers."""
        self.decide()
        old_id = gtm.load(WS)[0]["id"]
        self.decide(supersedes=old_id, decided="Target from 10 people upward",
                    why="Two of the small ones became clients")
        with self.assertRaises(gtm.DecisionRefused):
            self.decide(supersedes=old_id,
                        decided="Target from 5 people upward",
                        why="Changed our minds again")

    def test_nothing_is_ever_removed_from_the_file(self):
        for index in range(3):
            self.decide(decided=f"Decision number {index} about targeting",
                        why=f"Reason number {index} for that decision")
        rows = gtm.load(WS)
        old_id = rows[0]["id"]
        self.decide(supersedes=old_id, decided="A replacement decision here",
                    why="Because the first one stopped being true")
        self.assertEqual(len(gtm.load(WS)), 4)


class SettingsWithNoReason(GtmTest):

    def test_a_changed_setting_with_no_decision_is_listed(self):
        workspaces.set_policy(WS, {"market.size_min_employees": 50},
                              actor="test")
        out = gtm.summarise(WS, workspaces.policy(WS))
        self.assertIn("market.size_min_employees", out["unexplained"])

    def test_a_changed_setting_with_a_decision_is_not(self):
        workspaces.set_policy(WS, {"market.size_min_employees": 50},
                              actor="test")
        self.decide(policy_key="market.size_min_employees",
                    decided="Move the floor to 50 employees",
                    why="Nothing under 50 has ever booked a meeting")
        out = gtm.summarise(WS, workspaces.policy(WS))
        self.assertNotIn("market.size_min_employees", out["unexplained"])

    def test_the_reason_reaches_the_settings_screen(self):
        workspaces.set_policy(WS, {"market.size_min_employees": 50},
                              actor="test")
        self.decide(policy_key="market.size_min_employees",
                    decided="Move the floor to 50 employees",
                    why="Nothing under 50 has ever booked a meeting")
        view = api.workspace_settings(self.repo())
        row = [r for r in view["editable"]
               if r["key"] == "market.size_min_employees"][0]
        self.assertIsNotNone(row["decision"])
        self.assertIn("floor to 50", row["decision"]["decided"])

    def test_a_setting_nobody_changed_is_not_called_unexplained(self):
        """Most settings are left alone. A list that named all of them
        would be a list nobody reads."""
        out = gtm.summarise(WS, workspaces.policy(WS))
        self.assertEqual(out["unexplained"], [])


class WhoMayDecide(GtmTest):

    def test_an_operator_may_not_record_one(self):
        """An operator runs the machine. This is a statement about which
        direction it is pointed."""
        with self.assertRaises(workspaces.NotPermitted):
            self.decide(self.repo("op@x.test"))

    def test_a_viewer_may_not_even_read_them(self):
        """Agency reasoning about a client, not a client-facing summary."""
        with self.assertRaises(workspaces.NotPermitted):
            api.strategy_centre(self.repo("view@x.test"))

    def test_an_operator_may_read_them(self):
        self.decide()
        out = api.strategy_centre(self.repo("op@x.test"))
        self.assertEqual(out["decisions"], 1)
        self.assertFalse(out["can_record"])

    def test_a_workspace_admin_may_do_both(self):
        self.decide()
        out = api.strategy_centre(self.repo("admin@x.test"))
        self.assertTrue(out["can_record"])


class DecisionsAreScopedToOneWorkspace(GtmTest):

    def test_another_workspace_does_not_see_them(self):
        self.decide()
        self.assertEqual(gtm.current("contactout"), [])

    def test_superseding_across_a_workspace_boundary_is_refused(self):
        """A decision from another workspace is indistinguishable from one
        that never existed."""
        self.decide()
        old_id = gtm.load(WS)[0]["id"]
        entry = gtm.decision("contactout", gtm.TARGETING,
                             decided="Something else entirely here",
                             why="For reasons of our own in this workspace")
        with self.assertRaises(gtm.DecisionRefused):
            gtm.supersede("contactout", old_id, entry)

    def test_the_decision_carries_the_workspace_that_made_it(self):
        self.assertEqual(self.decide()["workspace"], WS)

    def test_a_decision_must_name_its_workspace(self):
        entry = gtm.decision(WS, gtm.TARGETING,
                             decided="Something worth recording here",
                             why="Because it explains a real choice")
        entry["workspace"] = None
        with self.assertRaises(gtm.DecisionRefused):
            gtm.record(entry)


class WhatTheScreenIsHandled(GtmTest):

    def test_areas_come_back_grouped_even_when_empty(self):
        out = gtm.by_area(WS)
        self.assertEqual([b["area"] for b in out], list(gtm.AREAS))
        self.assertTrue(all(b["decisions"] == [] for b in out))

    def test_it_is_audited(self):
        self.decide()
        rows = workspaces.audit(WS)
        recorded = [r for r in rows if r["action"] == "gtm.decided"]
        self.assertEqual(len(recorded), 1)
        self.assertIn("agencies under 20", recorded[0]["reason"])

    def test_a_refusal_reaches_the_page_that_caused_it(self):
        """A refusal nobody can see looks like nothing happening. The
        screen was returning 400 with the reason discarded, so the form
        came back with no explanation of why."""
        from src.web import pages
        data = api.strategy_centre(self.repo())
        data["error"] = "a measured decision has to say what the evidence was"
        html = pages.strategy_centre(data, "tok")
        self.assertIn("say what the evidence was", html)
        self.assertIn("note stop", html)

    def test_the_form_reopens_when_the_decision_was_refused(self):
        """Otherwise the message points at a form that is folded away."""
        from src.web import pages
        data = api.strategy_centre(self.repo())
        self.decide()
        data = api.strategy_centre(self.repo())
        data["error"] = "something was wrong"
        self.assertIn("<details open>",
                      pages.strategy_centre(data, "tok"))

    def test_an_empty_workspace_does_not_raise(self):
        out = api.strategy_centre(self.repo())
        self.assertEqual(out["decisions"], 0)
        self.assertEqual(out["superseded"], 0)


if __name__ == "__main__":
    unittest.main()
