"""The contact outreach screen reports the state the engine computed.

`api.outreach` emits, per step, `status`, `blocked_by`, `eligible` and
`eligibility_reasons`. `api.contact_outreach` - the only reader - asked for
`state`, `would_send` and `why`. None of those three keys exists, so:

    "state":      step.get("state") or "planned"   ->  always "planned"
    "would_send": step.get("would_send")           ->  always None
    "why":        step.get("why")                  ->  always None

and `pages.py` then hardcoded `tag("planned", "")` besides. The eligibility
verdict is computed correctly at `api.py:2112` and thrown away one function
later, so a suppressed contact's steps rendered identically to a clean one's,
on the screen an operator opens to decide what to do about that contact.

Nothing was ever sent wrongly - `push` refuses, and `eligibility` is what it
refuses on. This is the failure this repository keeps producing: a value
computed correctly with no consumer. It survived because nothing tested
`contact_outreach` at all.

The last test is the one that matters: the two screens must not disagree.
"""
import os
import unittest

from src import accountpolicy, eligibility, repo as repo_module
from src import store, workspaces
from src.web import api
from tests.campaignbase import CampaignTest, CLIENT

OP = "op@outreach.test"


class TheOutreachViewReportsRealState(CampaignTest):

    def setUp(self):
        super().setUp()
        self._overrides = {k: os.environ.get(k) for k in
                           ("QUEUE",) + store.STATE_OVERRIDES}
        # CampaignTest moves only QUEUE, CAMPAIGNS and OUT; the workspace and
        # audit files would otherwise be the real ones.
        store.use_directory(os.path.join(self.tmp, "work"))
        workspaces.ensure(CLIENT, "Client", client=CLIENT)
        workspaces.add_user(OP, "Op")
        workspaces.assign(OP, CLIENT, workspaces.OPERATOR)
        self.repo = repo_module.Repo.for_user(OP, CLIENT)

        self.recs = self.approved_campaign()
        self.rec = store.load()[0]
        self.rid = self.rec["id"]
        self.key = self.rec["contacts"][0]["key"]

    def tearDown(self):
        for key, value in self._overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        super().tearDown()

    def view(self):
        return api.contact_outreach(self.repo, self.rid, self.key)

    def steps(self):
        return (self.view() or {}).get("planned") or []

    # ----------------------------------------------------------- the defect

    def test_the_state_is_not_the_literal_word_planned_for_every_step(self):
        states = {s["state"] for s in self.steps()}
        self.assertTrue(states, "no steps to report on")
        self.assertNotEqual(states, {"planned"})

    def test_the_view_reports_the_status_the_engine_computed(self):
        """The producer/consumer contract, asserted rather than assumed."""
        produced = api.outreach(self.repo, self.rid, self.key)
        self.assertTrue(produced["steps"])
        self.assertEqual([s["status"] for s in produced["steps"]],
                         [s["state"] for s in self.steps()])

    def test_would_send_carries_the_eligibility_verdict(self):
        produced = api.outreach(self.repo, self.rid, self.key)
        self.assertEqual([s["eligible"] for s in produced["steps"]],
                         [s["would_send"] for s in self.steps()])

    def test_a_reason_is_a_sentence_rather_than_a_code(self):
        produced = api.outreach(self.repo, self.rid, self.key)
        pairs = [(s.get("eligibility_reasons") or [], c["why"])
                 for s, c in zip(produced["steps"], self.steps())]
        spoken = [(reasons, why) for reasons, why in pairs if reasons]
        self.assertTrue(spoken, "no step had anything to explain")
        for reasons, why in spoken:
            self.assertEqual(why, eligibility.explain(reasons[0]))

    # ------------------------------------------------ what an operator sees

    def test_a_suppressed_contact_does_not_render_like_a_clean_one(self):
        """The operator-facing claim, and the reason any of this matters."""
        before = [(s["state"], s["would_send"]) for s in self.steps()]
        self.assertTrue(before)
        self.assertTrue(any(w for _, w in before), "nothing to suppress")

        # The canonical path, so the stored shape is the one the product
        # writes - `_suppress_contact` records a dict, not a bare True.
        rec = store.get(self.rid)
        accountpolicy.apply_reply(rec, self.key,
                                  outcome=accountpolicy.UNSUBSCRIBE)
        store.save([rec])

        after = [(s["state"], s["would_send"]) for s in self.steps()]
        self.assertNotEqual(before, after)
        self.assertFalse(any(w for _, w in after),
                         "a suppressed contact still reports a sendable step")


if __name__ == "__main__":
    unittest.main()
