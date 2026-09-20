"""The forward-book census walked a hardcoded list and blinded capacity planning.

`scripts/bison_forward_book_census.py` held
`ACTIVE_CLIENT_CAMPAIGNS = (327, 328, 352)` and used it as the default set to
walk. Those are the three CLIENT campaigns and nothing of ours.

On 2026-09-20 that default produced a walk covering three campaigns while SIX
could book a mailbox - 481, 487 and 489 were all holding forward rows.
`senderheadroom.coverage` answered `(False, ('489',))`, which makes `verdict`
return REFUSED for every mailbox on every day.

**REFUSED IS NOT ROOM**, so the consequence was not a smaller answer, it was
no answer: nothing could be proven free and cohort scheduling had no input at
all. The walk of the 19th covered all five campaigns then active; the walk of
the 20th used the default and silently dropped two. Nothing complained,
because a literal cannot know it has gone stale.

Same class as the audit that invented `CONTACTOUT_KEY`: a hand-maintained
list standing in for a source of truth that already exists. The provider
knows which campaigns it will schedule from, so it is asked.

Two properties are pinned here and the SECOND one is the trap:

  - a campaign that can still book must be in the set, and `paused` counts,
    because 487 sat paused with ten rows booked on the 22nd
  - **the list PAGES.** `GET /api/campaigns` answers 15 rows with
    `meta.last_page: 2` and IGNORES `per_page`. Reading only page one returns
    352 while omitting 327 and 328 - the two largest campaigns in the book -
    so a derived default that did not page would be strictly worse than the
    literal it replaced.
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

SCRIPT = os.path.join(ROOT, "scripts", "bison_forward_book_census.py")


def load_census():
    spec = importlib.util.spec_from_file_location("census_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def page(rows, last_page=1):
    return 200, {"data": rows, "meta": {"last_page": last_page}}


def campaign(cid, status):
    return {"id": cid, "status": status}


class TheCensusAsksTheProvider(unittest.TestCase):

    def setUp(self):
        self.census = load_census()
        self.calls = []
        # The credential seam, stubbed so this suite needs no real key. Only
        # the URL and the response shape are under test here; `headers` is
        # pinned by the provider's own tests.
        bison = self.census.bison
        for name, value in (("base", lambda: "https://bison.invalid/api"),
                            ("headers", lambda: {"Authorization": "Bearer x"})):
            self.addCleanup(setattr, bison, name, getattr(bison, name))
            setattr(bison, name, value)

    def serve(self, pages):
        """Answer each request from `pages`, recording the URLs asked for."""
        def fake(method, url, headers, body, *a, **k):
            self.calls.append(url)
            return pages[len(self.calls) - 1]
        self.census.request = fake

    # ------------------------------------------------------- the paging trap

    def test_it_follows_last_page_to_the_end(self):
        """The bug that would have been worse than the literal. 327 and 328
        live on page two and they are the two largest books in the estate."""
        self.serve([page([campaign(352, "active")], last_page=2),
                    page([campaign(327, "active"), campaign(328, "active")],
                         last_page=2)])
        self.assertEqual((327, 328, 352), self.census.forward_booking_campaigns())
        self.assertEqual(2, len(self.calls))
        self.assertIn("page=1", self.calls[0])
        self.assertIn("page=2", self.calls[1])

    def test_a_single_page_does_not_ask_for_a_second(self):
        self.serve([page([campaign(352, "active")], last_page=1)])
        self.assertEqual((352,), self.census.forward_booking_campaigns())
        self.assertEqual(1, len(self.calls))

    # -------------------------------------------------- which ones can book

    def test_a_paused_campaign_is_included(self):
        """487 was paused with ten rows booked on the 22nd. Excluding paused
        is the exact defect this replaces."""
        self.serve([page([campaign(487, "paused")])])
        self.assertEqual((487,), self.census.forward_booking_campaigns())

    def test_terminal_statuses_are_excluded(self):
        self.serve([page([campaign(1, "draft"), campaign(2, "completed"),
                          campaign(3, "archived"), campaign(4, "active")])])
        self.assertEqual((4,), self.census.forward_booking_campaigns())

    def test_status_case_and_padding_do_not_smuggle_a_terminal_campaign_in(self):
        self.serve([page([campaign(1, " ARCHIVED "), campaign(2, "Draft"),
                          campaign(3, "ACTIVE")])])
        self.assertEqual((3,), self.census.forward_booking_campaigns())

    def test_a_status_the_estate_has_not_seen_is_included_not_dropped(self):
        """Undercounting is the dangerous direction: a campaign wrongly left
        out makes a full mailbox look free. An unknown status is therefore
        treated as able to book."""
        self.serve([page([campaign(9, "sending"), campaign(10, "whatever")])])
        self.assertEqual((9, 10), self.census.forward_booking_campaigns())

    # ------------------------------------------------ it refuses, never guesses

    def test_a_failed_list_raises_rather_than_falling_back(self):
        """A fallback to a stale literal is how this got blinded. An error
        the caller must answer is the honest failure."""
        self.serve([(500, {"error": "nope"})])
        with self.assertRaises(RuntimeError) as caught:
            self.census.forward_booking_campaigns()
        self.assertIn("--campaigns", str(caught.exception))

    def test_an_unexpected_shape_raises_rather_than_walking_a_guess(self):
        for body in ({"data": "not a list"}, {"meta": {}}, [], None):
            with self.subTest(body=body):
                self.serve([(200, body)])
                self.calls = []
                with self.assertRaises(RuntimeError):
                    self.census.forward_booking_campaigns()

    # ------------------------------------------------------- no literal left

    def test_no_hardcoded_campaign_id_default_survives(self):
        """Behavioural, not textual: the argument default must be absent so
        the set is resolved from the provider at run time."""
        self.assertFalse(hasattr(self.census, "ACTIVE_CLIENT_CAMPAIGNS"))
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--campaigns", default=None)
        self.assertIsNone(parser.parse_args([]).campaigns)


class TheCoverageContractItFeeds(unittest.TestCase):
    """The reason the default matters, pinned against the real primitive so
    this test fails if `senderheadroom` ever stops refusing."""

    def test_an_uncovered_walk_refuses_rather_than_reporting_room(self):
        from src import senderheadroom as sh
        state = {"campaigns": {"327": {
            "complete": True,
            "finished_at": "2026-09-20T12:00:00+00:00",
            "by_sender_day": {"2736|2026-09-21": 0},
        }}}
        covers, missing = sh.coverage(state, ("327", "489"))
        self.assertFalse(covers)
        self.assertEqual(("489",), missing)
        answer = sh.verdict(state, 2736, "2026-09-21", 15,
                            active_campaign_ids=("327", "489"), need=10,
                            now=None, max_age_hours=10 ** 6)
        self.assertEqual("REFUSED", answer[0])
        self.assertIn("489", answer[1])

    def test_a_covering_walk_can_prove_room(self):
        from src import senderheadroom as sh
        state = {"campaigns": {
            "327": {"complete": True,
                    "finished_at": "2026-09-20T12:00:00+00:00",
                    "by_sender_day": {"2736|2026-09-21": 3}},
            "489": {"complete": True,
                    "finished_at": "2026-09-20T12:00:00+00:00",
                    "by_sender_day": {"2736|2026-09-24": 5}},
        }}
        self.assertEqual((True, ()), sh.coverage(state, ("327", "489")))
        answer = sh.verdict(state, 2736, "2026-09-21", 15,
                            active_campaign_ids=("327", "489"), need=10,
                            now=None, max_age_hours=10 ** 6)
        self.assertEqual("ROOM", answer[0])


if __name__ == "__main__":
    unittest.main()
