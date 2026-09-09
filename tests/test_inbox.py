"""The Inbox, grouped by what a reply still needs.

Two defects it was built to fix, and the first one is the reason the second
mattered. The tabs named five of the nine classifications, so a reply
classified `out_of_office` or `not_now` was reachable only under All - and
`not_now` had just been added, which is exactly how a category goes missing:
somebody adds one and nobody remembers the list that was typed out by hand.

And nothing said what a reply needed. A flat list sorted by time asks an
operator to work out for themselves which of forty rows is still their job.

Both answers are derived. A reply stops needing attention when it is
matched, classified and read - not when a flag is set - and the tabs are
built from `replies.CATEGORIES` so a category added later cannot go missing
the same way.
"""
import unittest

from tests.webbase import WebTest

from src import replies as reply_model
from src.web import api, pages


class WhatAReplyNeeds(unittest.TestCase):

    def row(self, **kw):
        base = {"matched": True, "classification": "neutral", "handled": None}
        base.update(kw)
        return base

    def test_an_unmatched_reply_needs_somebody(self):
        self.assertEqual(api.needs_attention(self.row(matched=False)),
                         api.NEEDS_UNMATCHED)

    def test_an_unclassified_reply_needs_somebody(self):
        self.assertEqual(
            api.needs_attention(self.row(classification="unknown")),
            api.NEEDS_CLASSIFYING)

    def test_an_unread_positive_needs_somebody(self):
        self.assertEqual(
            api.needs_attention(self.row(classification="positive")),
            api.NEEDS_READING)

    def test_a_read_positive_does_not(self):
        self.assertIsNone(api.needs_attention(
            self.row(classification="positive", handled="2026-09-01")))

    def test_an_ordinary_classified_reply_does_not(self):
        for classification in ("neutral", "negative", "out_of_office",
                               "not_now", "unsubscribe"):
            with self.subTest(classification=classification):
                self.assertIsNone(
                    api.needs_attention(self.row(classification=classification)))

    def test_the_three_reasons_are_different_sentences(self):
        """Different jobs. A single "unread" flag would flatten them, and
        "nobody knows who this is" is not the same work as "nobody has
        looked"."""
        self.assertEqual(len({api.NEEDS_UNMATCHED, api.NEEDS_CLASSIFYING,
                              api.NEEDS_READING}), 3)


class TheTabs(unittest.TestCase):

    def test_every_canonical_category_gets_one(self):
        """Typed out by hand, this list lost `out_of_office` and `not_now`.
        Built from the vocabulary, it cannot."""
        categories = [{"kind": name, "count": 0}
                      for name in reply_model.CATEGORIES]
        html = pages.reply_tabs(categories, None)
        for name in reply_model.CATEGORIES:
            with self.subTest(kind=name):
                self.assertIn(f"kind={name}", html)

    def test_each_one_says_what_it_means(self):
        """`account_do_not_contact` is a code. "Company asked us to stop"
        is what it means."""
        categories = [{"kind": "account_do_not_contact", "count": 3}]
        html = pages.reply_tabs(categories, None)
        self.assertIn("Company asked us to stop", html)
        self.assertNotIn("account_do_not_contact<", html)

    def test_a_count_is_shown_only_when_there_is_one(self):
        html = pages.reply_tabs([{"kind": "positive", "count": 4},
                                 {"kind": "negative", "count": 0}], None)
        self.assertIn("Positive (4)", html)
        self.assertIn("Negative</a>", html)

    def test_the_current_tab_is_marked(self):
        html = pages.reply_tabs([{"kind": "positive", "count": 1}], "positive")
        self.assertIn("btn primary", html)


class TheInbox(WebTest):

    def inbox(self, kind=None):
        from src import repo as repo_module
        repo = repo_module.Repo.for_user("ops@productive.test", "productive")
        return api.reply_inbox(repo, kind)

    def test_it_lists_every_reply_and_counts_them_by_kind(self):
        found = self.inbox()
        self.assertEqual(found["total"], len(found["rows"]))
        self.assertEqual(sum(found["counts"].values()), found["total"])

    def test_filtering_narrows_the_list_but_not_the_counts(self):
        """The tabs have to keep showing what is in the other tabs.

        A second classification is seeded first. The fictional estate holds
        only positive replies, so filtering to positive is indistinguishable
        from not filtering at all - which is how this test passed while the
        counts were being narrowed along with the rows.
        """
        from src import events, store
        recs = store.load()
        target = next(r for r in recs
                      if r.get("client") == "productive" and r.get("contacts"))
        key = target["contacts"][0]["key"]
        stamp = "2026-09-04T11:00:00+00:00"
        events.record(target, events.REPLY_RECEIVED, contact_key=key,
                      channel="email", at=stamp)
        events.record(target, events.REPLY_CLASSIFIED, contact_key=key,
                      channel="email", at=stamp, classification="negative")
        store.save(recs)
        try:
            everything = self.inbox()
            self.assertGreater(len(everything["counts"]), 1,
                               "two classifications are present now")
            positive = self.inbox("positive")
            self.assertEqual(positive["counts"], everything["counts"],
                             "a filter must not narrow the other tabs")
            self.assertLess(len(positive["rows"]), len(everything["rows"]))
            self.assertTrue(all(r["classification"] == "positive"
                                for r in positive["rows"]))
        finally:
            for rec in recs:
                if rec["id"] == target["id"]:
                    rec["events"] = [e for e in rec["events"]
                                     if e.get("at") != stamp]
            store.save(recs)

    def test_the_attention_list_is_a_subset_that_needs_somebody(self):
        found = self.inbox()
        self.assertTrue(found["attention"])
        for row in found["attention"]:
            with self.subTest(who=row["contact_key"]):
                self.assertTrue(row["needs"])
                self.assertIsNotNone(api.needs_attention(row))

    def test_a_reply_that_named_a_date_carries_it(self):
        """The link between a message read last week and the row that
        becomes due next month."""
        from src import events, store
        recs = store.load()
        target = next(r for r in recs
                      if r.get("client") == "productive" and r.get("contacts"))
        contact = target["contacts"][0]["key"]
        events.record(target, events.REPLY_RECEIVED, contact_key=contact,
                      channel="email", at="2026-09-01T09:00:00+00:00")
        events.record(target, events.NOT_NOW_RECORDED, contact_key=contact,
                      at="2026-09-01T09:00:00+00:00",
                      return_date="2026-11-02", return_status="resolved")
        store.save(recs)
        try:
            rows = [r for r in self.inbox()["rows"]
                    if r["contact_key"] == contact and r.get("follow_up")]
            self.assertTrue(rows)
            self.assertEqual(rows[0]["follow_up"]["return_date"], "2026-11-02")
        finally:
            for rec in recs:
                if rec["id"] == target["id"]:
                    rec["events"] = [
                        e for e in rec["events"]
                        if e.get("at") != "2026-09-01T09:00:00+00:00"]
            store.save(recs)

    def test_the_page_shows_the_grouping(self):
        session = self.signin("ops@productive.test")
        status, body, _ = session.get("/replies")
        self.assertEqual(status, 200)
        self.assertIn("<h1>Inbox</h1>", body)
        self.assertIn("Needs attention", body)
        self.assertIn("kind=out_of_office", body)
        self.assertIn("kind=not_now", body)

    def test_a_viewer_cannot_read_the_inbox(self):
        session = self.signin("client@productive.test")
        self.assertEqual(session.get("/replies")[0], 403)

    def test_another_workspace_is_another_inbox(self):
        from src import repo as repo_module
        mine = api.reply_inbox(
            repo_module.Repo.for_user("ops@productive.test", "productive"))
        theirs = api.reply_inbox(
            repo_module.Repo.for_user("ops@demo-client.test", "demo-client"))
        mine_ids = {(r["record_id"], r["at"]) for r in mine["rows"]}
        their_ids = {(r["record_id"], r["at"]) for r in theirs["rows"]}
        self.assertFalse(mine_ids & their_ids)


class WhatAReplyCarries(WebTest):
    """A filter beside the tabs, not one of them.

    The tabs ask what a reply was read as. A referral is recorded from the
    evidence rather than from the winning category, so a referral inside a
    polite refusal is classified `negative` - and its tab would never show
    it. That is the whole reason this is a separate control, and the tests
    below are mostly about the two questions staying apart.
    """

    SEP = "2026-09-08T09:00:00+00:00"

    def setUp(self):
        super().setUp()
        from src import events, repo as repo_module, replies, store

        self.repo = repo_module.Repo.for_user("ops@productive.test",
                                              "productive")
        recs = self.repo.records()
        self.rec = next(r for r in recs if r.get("contacts"))
        self.who = self.rec["contacts"][0]["key"]
        # The receipt first. `replies.apply` writes the verdict beside a
        # reply that arrived; the arrival itself is `events.apply`'s, and
        # the Inbox lists arrivals - so classifying without one produces a
        # verdict for a message that is not in any list.
        events.record(self.rec, events.REPLY_RECEIVED, contact_key=self.who,
                      channel="email", at=self.SEP)
        # A refusal that hands us on. Classified `negative`; carries a
        # referral. The exact shape no tab can show.
        replies.apply(self.rec, self.who,
                      "Not interested - please try Priya Nair.",
                      at=self.SEP, channel="email")
        self.repo.save_records([self.rec])
        store.load()

    def inbox(self, **kw):
        return api.reply_inbox(self.repo, **kw)

    def mine(self, rows):
        return [r for r in rows
                if r["contact_key"] == self.who and r["at"] == self.SEP]

    def test_the_reply_is_classified_negative(self):
        row = self.mine(self.inbox()["rows"])[0]
        self.assertEqual(row["classification"], "negative")

    def test_and_it_carries_a_referral(self):
        row = self.mine(self.inbox()["rows"])[0]
        self.assertEqual(row["referral"]["named"], "Priya Nair")
        self.assertTrue(row["referral"]["needs_a_person"])

    def test_the_referral_tab_does_not_contain_it(self):
        """The reason the filter exists, stated as a test rather than as a
        comment."""
        self.assertEqual(self.mine(self.inbox(kind="referral")["rows"]), [])

    def test_the_filter_does(self):
        self.assertEqual(len(self.mine(self.inbox(carries="referral")["rows"])),
                         1)

    def test_a_reply_carrying_nothing_is_not_in_it(self):
        found = self.inbox(carries="referral")["rows"]
        self.assertTrue(all(r.get("referral") for r in found))
        self.assertLess(len(found), self.inbox()["total"])

    def test_the_two_filters_compose(self):
        """A referral inside a refusal is findable as both at once."""
        both = self.inbox(kind="negative", carries="referral")["rows"]
        self.assertEqual(len(self.mine(both)), 1)
        self.assertTrue(all(r["classification"] == "negative" for r in both))

    def test_the_count_survives_any_filter(self):
        """The control that would widen the list again has to keep saying
        how much it would widen it by.

        Compared against a *different* filter, not against itself: counting
        the referrals in `carries=referral`'s own output gives the same
        number whether it counts everything or only what is shown, so that
        comparison proves nothing. On the `positive` tab it differs.
        """
        everything = self.inbox()["referrals"]
        self.assertGreater(everything, 0)
        self.assertEqual(self.inbox(kind="positive")["referrals"], everything)
        self.assertEqual(self.inbox(carries="referral")["referrals"],
                         everything)

    def test_an_unknown_filter_value_narrows_nothing(self):
        """A parameter nobody implemented must not quietly empty a list."""
        self.assertEqual(len(self.inbox(carries="whatever")["rows"]),
                         len(self.inbox()["rows"]))

    def test_the_page_offers_it_and_names_who_was_pointed_at(self):
        session = self.signin("ops@productive.test")
        status, body, _ = session.get("/replies")
        self.assertEqual(status, 200)
        self.assertIn("carries=referral", body)
        self.assertIn("Carries a referral", body)
        self.assertIn("Priya Nair", body)

    def test_the_filter_can_be_turned_off_again(self):
        session = self.signin("ops@productive.test")
        status, body, _ = session.get("/replies?carries=referral")
        self.assertEqual(status, 200)
        # The chip is its own off switch when it is on.
        self.assertIn('href="/replies"', body)

    def test_the_work_queue_links_at_it(self):
        from src import tasks

        rows = tasks.collect("productive", recs=self.repo.records(),
                             config=self.repo.config())
        referral_rows = [r for r in rows if r["kind"] == tasks.REVIEW_REFERRAL]
        self.assertTrue(referral_rows)
        self.assertEqual(referral_rows[0]["where"], "/replies?carries=referral")


if __name__ == "__main__":
    unittest.main()
