"""Advanced reporting: every breakdown the brief names, with its denominator.

The rule this file protects is the one that separates a report from a claim:
**every rate has an inspectable numerator and denominator**, and no stage is
invented where the source data does not exist. A percentage on its own is a
sentence somebody has to trust; a pair is one they can check.
"""
from src import repo as repo_module
from src.web import api
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"
VIEWER = "client@productive.test"


class EveryNamedBreakdownExists(WebTest):
    """One test rather than fifteen, because the list is the assertion."""

    NAMED = (
        "persona",          # reply rate / positive reply rate by persona
        "vertical",         # ... by vertical
        "subvertical",
        "employee_band",    # ... by company size
        "country", "region", "timezone",   # ... by geography
        "angle",            # ... by outreach angle
        "icp_tier",         # ICP tier vs performance
        "mode",             # multichannel vs email-only vs LinkedIn-only
        "personalization",  # personalisation strategy vs performance
        "mx_provider", "mx_category",      # MX / security distribution
        "verifier",         # verification-provider outcomes
        "email_source",     # the ContactOut-first waterfall
        "batch", "industry", "icp_status",
        # Account intelligence, joined from the same `assess` the account
        # screen reads rather than recomputed for the report.
        "priority_tier", "live_signal", "outreach_state",
    )

    def test_every_dimension_the_brief_names_is_available(self):
        available = {key for key, _ in api.DIMENSIONS}
        missing = [d for d in self.NAMED if d not in available]
        self.assertEqual(missing, [], f"dimensions not offered: {missing}")

    def test_each_one_groups_without_erroring(self):
        session = self.signin(OPERATOR)
        for dimension in self.NAMED:
            status, body, _ = session.get(f"/reporting?dimension={dimension}")
            self.assertEqual(status, 200, dimension)
            self.assertNotIn("Something went wrong", body, dimension)

    def test_each_one_can_also_be_compared(self):
        session = self.signin(OPERATOR)
        for dimension in self.NAMED:
            status, body, _ = session.get(f"/compare?dimension={dimension}")
            self.assertEqual(status, 200, dimension)
            self.assertNotIn("Something went wrong", body, dimension)


class EveryRateCarriesItsDenominator(WebTest):

    def repo(self):
        return repo_module.Repo.for_user(OPERATOR, "productive")

    def test_a_rate_is_a_pair_not_a_number(self):
        data = api.analytics(self.repo(), "persona")
        for name, pair in data["totals"]["rates"].items():
            self.assertIsInstance(pair, tuple, name)
            self.assertEqual(len(pair), 2, name)
            numerator, denominator = pair
            self.assertLessEqual(numerator, denominator, name)

    def test_every_row_of_a_breakdown_carries_its_own_pair(self):
        data = api.analytics(self.repo(), "vertical")
        self.assertTrue(data["breakdown"])
        for row in data["breakdown"]:
            for name, pair in row["rates"].items():
                self.assertEqual(len(pair), 2, f'{row["value"]}/{name}')

    def test_the_sample_size_is_on_every_row(self):
        """A tiny sample must not be presentable as a conclusion."""
        data = api.analytics(self.repo(), "employee_band")
        self.assertTrue(data["breakdown"])
        for row in data["breakdown"]:
            self.assertIn("contacts", row)
            self.assertIn("companies", row)

    def test_the_denominators_are_visible_on_the_page(self):
        session = self.signin(OPERATOR)
        _, body, _ = session.get("/reporting?dimension=persona")
        # A rendered rate shows "n of d" beside it, not a bare percentage.
        self.assertRegex(body, r"\d+\s+of\s+\d+")


class NoStageIsInvented(WebTest):

    def test_the_funnel_stops_where_the_data_does(self):
        """Nothing has been sent, so contacted, replied and meetings are not
        conjured from the stages that do exist."""
        session = self.signin(OPERATOR)
        _, body, _ = session.get("/reporting")
        self.assertIn("cannot", body.lower())

    def test_a_metric_this_system_cannot_know_says_why(self):
        repo = self.repo() if hasattr(self, "repo") else \
            repo_module.Repo.for_user(OPERATOR, "productive")
        data = api.reporting(repo)
        self.assertTrue(data["unavailable"],
                        "nothing is reported as unavailable, which cannot be "
                        "true in a build that has never sent")
        for metric, why in data["unavailable"].items():
            self.assertTrue(why, f"{metric} is unavailable with no reason")


class TheClientFacingCutIsNarrowedOnTheServer(WebTest):

    def test_a_client_dimension_list_excludes_the_vendor_stack(self):
        client_keys = {k for k, _ in api.CLIENT_DIMENSIONS}
        for vendor in ("mx_provider", "mx_category", "email_source",
                       "verifier"):
            self.assertNotIn(vendor, client_keys)

    def test_how_we_rank_accounts_is_an_operator_dimension(self):
        """A client reads which of their accounts we may work. How we
        ordered the rest is internal method, the same as how the copy was
        built."""
        client_keys = {k for k, _ in api.CLIENT_DIMENSIONS}
        for internal in ("priority_tier", "live_signal"):
            self.assertNotIn(internal, client_keys)
            self.assertIn(internal, {k for k, _ in api.DIMENSIONS})

    def test_whether_we_may_write_to_a_company_is_a_client_fact(self):
        """"We are not contacting these, and here is why" is an outcome,
        not a method."""
        self.assertIn("outreach_state",
                      {k for k, _ in api.CLIENT_DIMENSIONS})

    def test_personalisation_is_an_operator_dimension_not_a_client_one(self):
        """It names how the copy was built, which is internal method."""
        client_keys = {k for k, _ in api.CLIENT_DIMENSIONS}
        self.assertNotIn("personalization", client_keys)
        self.assertIn("personalization", {k for k, _ in api.DIMENSIONS})


class OneReplyIsOneReply(WebTest):
    """The dashboard and the client report must agree, and they did not.

    `replies.classify` writes three events for one message: the receipt, the
    classifier's verdict, and - when that verdict is positive - the positive
    signal. `workspace_card` counted the receipt *and* the verdict as
    replies, and the verdict *and* the signal as positives, so two replies
    were reported as four on a screen a client can open, while their PDF,
    counting arrivals, said two.

    Nothing caught it: `workspace_card` had tenancy tests and no arithmetic
    ones, and `reply_rows` had none at all.
    """

    def metrics(self):
        return api.workspace_card(OPERATOR, "productive")["metrics"]

    def counted(self):
        from src import report

        return report.for_client("productive")

    def rows(self):
        return api.reply_rows(repo_module.Repo.for_user(OPERATOR,
                                                        "productive"))

    def test_the_dashboard_and_the_report_count_the_same_replies(self):
        self.assertEqual(self.metrics()["replies"], self.counted()["replies"])

    def test_and_the_same_positive_replies(self):
        self.assertEqual(self.metrics()["positive_replies"],
                         self.counted()["positive_replies"])

    def test_a_reply_appears_in_the_inbox_once(self):
        """Twice, once labelled "unknown", is how it read before."""
        seen = [(r["record_id"], r["contact_key"], r["channel"], r["at"])
                for r in self.rows()]
        self.assertEqual(len(seen), len(set(seen)), seen)

    def test_the_row_count_is_the_reply_count(self):
        self.assertEqual(len(self.rows()), self.counted()["replies"])

    def test_a_classified_reply_keeps_its_verdict(self):
        """Folding the verdict onto the receipt must not lose it."""
        rows = self.rows()
        self.assertTrue(rows, "the demo estate should carry replies")
        positive = [r for r in rows if r["classification"] == "positive"]
        self.assertEqual(len(positive), self.counted()["positive_replies"])

    def test_filtering_by_kind_still_works(self):
        repo = repo_module.Repo.for_user(OPERATOR, "productive")
        self.assertEqual(
            [r["at"] for r in api.reply_rows(repo, kind="positive")],
            [r["at"] for r in self.rows() if r["classification"] == "positive"])
