"""What a client sees when we give them an account.

The client cut used to borrow the operator's tiles. Those say
"multichannel", "email only" and "held" - internal channel eligibility -
beside "review" and "rejected", which are this system's private opinion of
somebody's company. All true, none of it addressed to the reader, and
"rejected: 34" in front of a client is a sentence nobody wants to have to
explain.

It now shows the funnel, in the words `report.FUNNEL_LABEL` already uses for
the client report - so the screen and the PDF describe one number one way.

The bar this file holds: could a client be given VIEWER access without
anybody having to explain away internals?
"""
import unittest

from tests.webbase import WebTest

from src import report
from src.web import api, pages


class TheWords(unittest.TestCase):

    def test_the_labels_are_the_client_reports_labels(self):
        """One vocabulary across the screen and the PDF. A second copy here
        would drift, and a client would read one number described two ways."""
        for stage in api.CLIENT_FUNNEL:
            self.assertIn(stage, report.FUNNEL_LABEL, stage)

    def test_the_internal_stages_are_left_out(self):
        """`approved to send: 40` beside `confirmed sent: 0` is a pair of
        numbers that needs a paragraph, not a tile."""
        for internal in ("selected", "approved", "active"):
            self.assertNotIn(internal, api.CLIENT_FUNNEL)

    def test_the_order_is_the_order_the_work_happens(self):
        positions = [report.FUNNEL.index(stage) for stage in api.CLIENT_FUNNEL]
        self.assertEqual(positions, sorted(positions))


class Rendering(unittest.TestCase):

    def funnel(self, contacted=0, replied=0):
        return {"stages": [{"stage": "contacted", "label": "Confirmed sent",
                            "count": contacted},
                           {"stage": "replied", "label": "Replied",
                            "count": replied}],
                "contacted": contacted, "replied": replied}

    def test_a_rate_carries_both_of_its_numbers(self):
        """A percentage on its own is a claim the reader cannot check."""
        html = pages.client_funnel(self.funnel(contacted=40, replied=6))
        self.assertIn("6 replies", html)
        self.assertIn("40 confirmed sends", html)

    def test_it_does_not_call_a_count_of_sends_a_count_of_people(self):
        """The funnel counts `push_marked` events, so thirteen sends can
        have reached twelve people. Saying "13 people" is a claim a client
        would believe and we could not support."""
        html = pages.client_funnel(self.funnel(contacted=40, replied=6))
        self.assertNotIn("40 people", html)

    def test_nothing_sent_says_so_rather_than_showing_a_bare_zero(self):
        html = pages.client_funnel(self.funnel(contacted=0, replied=0))
        self.assertIn("Nothing has been sent", html)
        self.assertIn("research and preparation", html)

    def test_no_funnel_at_all_explains_itself(self):
        self.assertIn("Nothing yet", pages.client_funnel(None))
        self.assertIn("Nothing yet", pages.client_funnel({"stages": []}))


class WhatTheClientActuallyGets(WebTest):

    def body(self, email):
        session = self.signin(email)
        status, body, _ = session.get("/")
        self.assertEqual(status, 200)
        return body.split('<div class="wrap">', 1)[1]

    def test_the_funnel_is_there_in_client_words(self):
        body = self.body("client@productive.test")
        for label in ("Domains uploaded", "ICP qualified", "Contacts found",
                      "Confirmed sent", "Replied"):
            with self.subTest(label=label):
                self.assertIn(label, body)

    def test_the_operators_channel_jargon_is_gone(self):
        body = self.body("client@productive.test")
        for jargon in ("multichannel", "email only", "linkedin only",
                       "rejected"):
            with self.subTest(jargon=jargon):
                self.assertNotIn(jargon, body)

    def test_the_operator_still_has_their_own_tiles(self):
        """The client cut is a different screen, not a smaller one - and
        removing the operator's counts would be the wrong trade."""
        body = self.body("ops@productive.test")
        self.assertIn("multichannel", body)

    def test_the_funnel_is_not_computed_for_the_operator(self):
        """It reaches into approval, cadence and lint. The operator's page
        does not show it, so it should not pay for it."""
        from src import repo as repo_module
        operator = repo_module.Repo.for_user("ops@productive.test",
                                             "productive")
        self.assertIsNone(api.dashboard(operator)["funnel"])
        viewer = repo_module.Repo.for_user("client@productive.test",
                                           "productive")
        self.assertIsNotNone(api.dashboard(viewer)["funnel"])

    def test_the_counts_are_canonical_not_decorative(self):
        from src import repo as repo_module
        viewer = repo_module.Repo.for_user("client@productive.test",
                                           "productive")
        funnel = api.dashboard(viewer)["funnel"]
        counts = {row["stage"]: row["count"] for row in funnel["stages"]}
        self.assertEqual(counts["contacted"], funnel["contacted"])
        # The funnel narrows: nobody replies who was never contacted.
        self.assertLessEqual(counts["replied"], counts["contacted"])
        self.assertLessEqual(counts["positive"], counts["replied"])

    def test_a_client_is_never_told_a_planned_touch_was_sent(self):
        """`contacted` is confirmed sends only. If this ever counts
        approved or prepared work, a client is being told something
        happened that did not."""
        from src import repo as repo_module
        viewer = repo_module.Repo.for_user("client@productive.test",
                                           "productive")
        funnel = api.dashboard(viewer)["funnel"]
        counts = {row["stage"]: row["count"] for row in funnel["stages"]}
        self.assertEqual(report.FUNNEL_LABEL["contacted"], "Confirmed sent")
        self.assertLessEqual(counts["contacted"], counts["contactable"])


if __name__ == "__main__":
    unittest.main()
