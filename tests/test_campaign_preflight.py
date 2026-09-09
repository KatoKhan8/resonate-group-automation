"""Who could actually receive something, before anybody approves it.

The campaign page has always listed the seventeen checks about the campaign
itself - approved, linted, senders mapped, credentials present. What it never
showed is the audience. A reviewer approving a campaign where eighteen of
forty contacts are held for verification is approving something other than
what they think, and "campaign cannot run" is not a sentence anybody can act
on.

Two things this must not become. It must not be a second opinion about
eligibility - the reasons come from `eligibility.decide`, which is the only
authority on the question. And it must not invent prose: `eligibility.HUMAN`
already holds a sentence per code, with a test asserting the map is complete,
so a code that reaches a screen raw is a bug rather than a gap here.
"""
import unittest

from tests.webbase import WebTest

from src import eligibility, store


class Preflight(WebTest):

    def repo(self, email="ops@productive.test", workspace="productive"):
        from src import repo as repo_module
        return repo_module.Repo.for_user(email, workspace)

    def preflight(self, campaign_id="uk-digital"):
        from src.web import api
        return api.campaign_preflight(self.repo(), campaign_id)

    def test_an_unknown_campaign_is_none_rather_than_an_error(self):
        self.assertIsNone(self.preflight("no-such-campaign"))

    def test_it_counts_the_audience(self):
        found = self.preflight()
        self.assertGreater(found["accounts"], 0)
        self.assertGreater(found["contacts"], 0)

    def test_the_verdicts_account_for_every_contact(self):
        """A contact is eligible, held, blocked or skipped. If these stop
        adding up, somebody is missing from the screen."""
        found = self.preflight()
        self.assertEqual(sum(found["verdicts"].values()), found["contacts"])

    def test_eligible_is_the_eligible_verdict_and_not_a_second_count(self):
        found = self.preflight()
        self.assertEqual(found["eligible"],
                         found["verdicts"][eligibility.ELIGIBLE])

    def test_every_reason_carries_a_sentence_not_a_code(self):
        """`eligibility.HUMAN` is where the prose lives. A raw code on a
        screen is this system printing its internals at somebody."""
        for reason in self.preflight()["reasons"]:
            with self.subTest(code=reason["code"]):
                self.assertEqual(reason["human"],
                                 eligibility.HUMAN[reason["code"]])
                self.assertNotEqual(reason["human"], reason["code"])

    def test_blocked_and_held_are_kept_apart(self):
        """Different jobs, not different severities. A block needs a
        different contact; a hold needs one more thing to happen."""
        kinds = {r["kind"] for r in self.preflight()["reasons"]}
        self.assertTrue(kinds <= {"blocked", "held", "skipped"}, kinds)

    def test_the_commonest_reason_is_first(self):
        counts = [r["count"] for r in self.preflight()["reasons"]]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_it_carries_the_campaign_level_checks_too(self):
        found = self.preflight()
        self.assertTrue(found["checks"])
        self.assertIn("campaign approved", found["blockers"])

    def test_nothing_is_written(self):
        import copy
        before = copy.deepcopy(store.load())
        self.preflight()
        self.assertEqual(store.load(), before)

    def test_it_is_scoped_to_the_campaigns_own_records(self):
        """A pre-flight that counted the whole workspace would tell a
        reviewer about people this campaign will never touch."""
        from src import campaigns as campaign_store
        found = self.preflight()
        campaign = next(c for c in campaign_store.load()
                        if c.get("campaign_id") == "uk-digital")
        self.assertEqual(found["accounts"],
                         len(campaign.get("record_ids") or []))


class OnThePage(WebTest):

    def test_a_reviewer_sees_the_audience_before_the_checklist(self):
        session = self.signin("review@productive.test")
        status, body, _ = session.get("/campaigns/uk-digital")
        self.assertEqual(status, 200)
        self.assertIn("Before you approve", body)
        self.assertLess(body.index("Before you approve"),
                        body.index("Launch checklist"),
                        "who it reaches comes before whether it is tidy")

    def test_the_reasons_are_readable_on_the_page(self):
        session = self.signin("review@productive.test")
        _, body, _ = session.get("/campaigns/uk-digital")
        self.assertIn("nobody has approved this campaign yet", body)

    def test_a_viewer_cannot_reach_it(self):
        session = self.signin("client@productive.test")
        self.assertEqual(session.get("/campaigns/uk-digital")[0], 403)

    def test_it_says_approving_changes_none_of_it(self):
        """The gate runs again at send time. A reviewer should not read
        this as a promise."""
        session = self.signin("review@productive.test")
        _, body, _ = session.get("/campaigns/uk-digital")
        self.assertIn("the same gate runs again", body)



class TheApprovalsQueue(WebTest):
    """A reviewer decides here, so the audience has to be here.

    The number needs care. "How many could receive this" is circular on
    this screen - the answer is nobody, because it has not been approved,
    which is the thing the reader is deciding. So the count sets the
    approval gate aside and answers the question actually being asked:
    once approved, how many are still stopped by something else.
    """

    def queue(self):
        from src import repo as repo_module
        from src.web import api
        repo = repo_module.Repo.for_user("review@productive.test",
                                         "productive")
        return api.approval_queue(repo)["campaigns"]

    def test_every_campaign_carries_its_audience(self):
        for row in self.queue():
            with self.subTest(campaign=row["campaign_id"]):
                self.assertIsNotNone(row["audience"])
                self.assertGreater(row["audience"]["contacts"], 0)

    def test_the_approval_gate_is_set_aside_from_the_count(self):
        """Otherwise every unapproved campaign reads 0 and the column says
        nothing at all."""
        for row in self.queue():
            audience = row["audience"]
            with self.subTest(campaign=row["campaign_id"]):
                self.assertEqual(audience["eligible"], 0,
                                 "nothing is eligible before approval")
                self.assertGreater(audience["eligible_if_approved"], 0)

    def test_it_never_promises_more_than_the_audience(self):
        for row in self.queue():
            audience = row["audience"]
            with self.subTest(campaign=row["campaign_id"]):
                self.assertLessEqual(audience["eligible_if_approved"],
                                     audience["contacts"])

    def test_other_blockers_still_reduce_it(self):
        """A contact stopped for a second reason must not be counted as
        ready merely because the approval gate was excluded."""
        rows = self.queue()
        reduced = [r for r in rows
                   if r["audience"]["eligible_if_approved"]
                   < r["audience"]["contacts"]]
        self.assertTrue(reduced, "the estate has contacts stopped for "
                                 "reasons other than approval")

    def test_the_page_shows_it(self):
        session = self.signin("review@productive.test")
        status, body, _ = session.get("/approvals")
        self.assertEqual(status, 200)
        self.assertIn("who it reaches", body)
        self.assertIn("once approved", body)
        self.assertIn("stopped by something else", body)

    def test_a_viewer_still_cannot_read_the_queue(self):
        session = self.signin("client@productive.test")
        self.assertEqual(session.get("/approvals")[0], 403)

if __name__ == "__main__":
    unittest.main()
