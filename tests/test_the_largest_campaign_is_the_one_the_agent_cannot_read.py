r"""The agent saw 241 of the day's 494 sends, and the half it missed was one
campaign.

MEASURED LIVE, 2026-09-23, against the provider campaign by campaign:

    495  sent=39    494  sent=69    492  sent=131
    491  sent=253   489  sent=2     451  sent=1      TOTAL 494 on 2026-09-22

Asked *what was sent yesterday*, the live agent answered out of 246 emails
over seven days and named its own floor honestly: 491's window came back
unreadable and four campaigns sat past the read cap. Every part of that
sentence was true and the number was half the day.

## THE SHAPE

`bison.scheduled_emails` walks pages and REFUSES past `PAGE_CAP = 40` rather
than returning a prefix as though it were the whole queue. That refusal is
right and it is the only reason this was a visible floor rather than a
silent undercount. Campaign 491 reached 645 rows:

    491: default cap RAISES PartialInventory: emailbison scheduled_emails:
         43 pages to walk and this read stops at 40. Refusing to return 600
         of 645 as though it were
    492: default cap OK, 394 rows
    494: default cap OK, 152 rows

Five agent-side call sites read a queue - `_week_for_domain`,
`_recent_send_domains`, `_sent_since`, `_week_activity` in
`slackagenttools`, and `campaign_by_id` in `slackagentreadback` - and NOT
ONE of them passed a cap. So the largest campaign in the estate, the one
carrying 51% of the day's sends, was unreadable to every client answer.

`scripts/hard_stop_check.py` had met the same campaign the day before and
been given `QUEUE_PAGE_CAP = 400` for it. The agent-side readers were not.
Two readers with different ideas of how much of a campaign they can see will
disagree about what was sent, so this file pins them to the same number.

## WHY THE SUITE DID NOT CATCH IT, AND WHAT THIS FILE DOES INSTEAD

Every existing test of these functions patches `bison.scheduled_emails` with
a fake, and a fake has no page cap. The page cap is not reachable by any
fixture: it lives in the provider's pager and only bites against a real
queue of a real size. So no test could have failed, and none did.

What IS testable is the WIRING - that the agent asks for a cap at all, and
that it asks for one big enough for the campaign that broke it. That is what
this file asserts, three ways:

1. the cap is passed, recorded off the real call;
2. it is large enough for 43 pages and the same number the hard stop uses;
3. a queue that outgrows even the raised cap STILL reads as unreadable,
   never as empty - because the refusal is the property, not the number.

The third is the one that must never regress. A campaign nobody could read
is not a campaign that sent nothing, and the day this file is "fixed" by
catching `PartialInventory` and returning `[]` is the day the agent starts
reporting a silent zero to a client.
"""
import datetime
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackagentreadback as readback                   # noqa: E402
from src import slackscope                                       # noqa: E402
from src import slackagenttools as tools                         # noqa: E402
from src.providers import bison                                  # noqa: E402

PACK = {"workspaces": {"alpha": {"provider_campaign_ids": ["491"]}}}

#: 491 as it actually was on the morning this was measured. The pager works
#: in pages, not rows; 645 rows at the provider's fifteen to a page is 43.
LIVE_491_ROWS = 645
LIVE_491_PAGES = 43

#: Any cutoff at all - these readers take a datetime and compare `sent_at`
#: against it. What is under test is the call, not the window.
CUTOFF = datetime.datetime(2026, 9, 16, tzinfo=datetime.timezone.utc)


class PartialInventory(Exception):
    """Stands in for the provider's own refusal, which is what a queue past
    the cap raises. The real class lives in the provider module and the
    callers catch `Exception`, so the name is all that matters here."""


class TheCapIsPassed(unittest.TestCase):
    """The defect itself: the agent asked for the default and got refused."""

    def setUp(self):
        self._pack = tools.knowledge.pack
        tools.knowledge.pack = lambda *a, **k: PACK
        self.addCleanup(setattr, tools.knowledge, "pack", self._pack)

    def recorded(self, call):
        """Run `call` and return the cap the provider was actually asked for.

        Recorded off `bison.scheduled_emails` itself, so this fails if a
        caller is added that reaches the provider directly again.
        """
        seen = []

        def scheduled_emails(campaign_id, cap=None):
            seen.append(cap)
            return []

        with mock.patch.object(bison, "scheduled_emails", scheduled_emails):
            call()
        return seen

    def test_the_helper_asks_for_a_cap(self):
        caps = self.recorded(lambda: readback.queue("491"))
        self.assertEqual(caps, [readback.QUEUE_PAGE_CAP])

    def test_campaign_by_id_asks_for_a_cap(self):
        with mock.patch.object(bison, "campaign", lambda cid: {"id": cid}):
            caps = self.recorded(lambda: readback.campaign_by_id("491"))
        self.assertEqual(caps, [readback.QUEUE_PAGE_CAP])

    def test_every_agent_side_queue_read_asks_for_a_cap(self):
        """All four `slackagenttools` readers, each by its own entry point."""
        for label, call in (
                ("_sent_since", lambda: tools._sent_since("491", CUTOFF)),
                ("_week_activity",
                 lambda: tools._week_activity("491", CUTOFF)),
                ("_recent_send_domains",
                 lambda: tools._recent_send_domains("alpha")),
                ("_week_for_domain",
                 lambda: tools._week_for_domain(
                     "alpha", "sending-domain-a.example.test"))):
            with self.subTest(reader=label):
                caps = self.recorded(call)
                self.assertTrue(caps, f"{label} never read a queue")
                self.assertEqual(set(caps), {readback.QUEUE_PAGE_CAP},
                                 f"{label} did not pass the cap")


class TheCapIsBigEnoughForTheCampaignThatBrokeIt(unittest.TestCase):

    def test_it_clears_the_live_page_count(self):
        """43 pages is the measurement, not a guess."""
        self.assertGreater(readback.QUEUE_PAGE_CAP, LIVE_491_PAGES)

    def test_it_matches_the_hard_stop(self):
        """Two readers of the same queue, one number.

        `scripts/hard_stop_check.py` chose 400 for campaign 491 on
        2026-09-22. A reader that can see more of a campaign than the hard
        stop can is a reader that will report sends the hard stop cannot
        vouch for.
        """
        import importlib.util
        path = os.path.join(ROOT, "scripts", "hard_stop_check.py")
        spec = importlib.util.spec_from_file_location("_hard_stop", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(readback.QUEUE_PAGE_CAP, module.QUEUE_PAGE_CAP)

    def test_the_provider_default_would_not_have_been_enough(self):
        """Names the defect in one assertion: the default refuses 491."""
        self.assertLess(bison.PAGE_CAP, LIVE_491_PAGES)


class TheRefusalSurvivesTheRaise(unittest.TestCase):
    """A bigger cap is still a cap, and past it the answer is still no."""

    def setUp(self):
        self._pack = tools.knowledge.pack
        tools.knowledge.pack = lambda *a, **k: PACK
        self.addCleanup(setattr, tools.knowledge, "pack", self._pack)

    def refusing(self):
        def scheduled_emails(campaign_id, cap=None):
            raise PartialInventory(
                f"emailbison scheduled_emails: {LIVE_491_PAGES * 20} pages "
                f"to walk and this read stops at {cap}")
        return mock.patch.object(bison, "scheduled_emails", scheduled_emails)

    def test_the_helper_raises_rather_than_returning_empty(self):
        with self.refusing():
            with self.assertRaises(PartialInventory):
                readback.queue("491")

    def test_a_refused_queue_is_unreadable_not_zero(self):
        """`_sent_since` returns None - the absence of an answer.

        None rather than 0 is the whole of the distinction: a week with no
        sends and a queue that could not be read are different facts, and a
        client told "0 sent" about a campaign nobody could read has been
        told something false.
        """
        with self.refusing():
            self.assertIsNone(tools._sent_since("491", CUTOFF))
            self.assertIsNone(tools._week_activity("491", CUTOFF))

    def test_campaign_by_id_reports_the_error_and_no_row_count(self):
        with mock.patch.object(bison, "campaign", lambda cid: {"id": cid}):
            with self.refusing():
                out = readback.campaign_by_id("491")
        self.assertEqual(out.get("queue_error"), "PartialInventory")
        self.assertNotIn("queue_rows", out)
        self.assertNotIn("queue_sent_rows", out)

    def test_the_domain_walk_counts_it_unreadable(self):
        with self.refusing():
            found, unreadable, capped = tools._recent_send_domains("alpha")
        self.assertEqual(unreadable, 1)
        self.assertIsNone(found)


class NoToolReadsAQueueWithoutOne(unittest.TestCase):
    """The durable guard: a fifth call site cannot be added and forgotten.

    BEHAVIOURAL, not a grep. CLAUDE.md: "Test behaviour, not the text of the
    source. Searching source for words produces a test that fails when
    somebody writes a comment." So the provider itself refuses an uncapped
    read here, and the tools are driven through their real entry points. A
    new reader that reaches `bison.scheduled_emails` directly trips this
    however it is spelled, and a comment mentioning the function does not.

    The four call sites that had this were each written by somebody with no
    reason to know the cap mattered, which is exactly how there came to be
    four.
    """

    def setUp(self):
        self._pack = tools.knowledge.pack
        tools.knowledge.pack = lambda *a, **k: PACK
        self.addCleanup(setattr, tools.knowledge, "pack", self._pack)

    def test_every_tool_that_reads_a_queue_asks_for_a_cap(self):
        uncapped = []

        def scheduled_emails(campaign_id, cap=None):
            if cap is None:
                uncapped.append(str(campaign_id))
            return []

        tool_names = [name for name in tools.REGISTRY
                      if name in ("sends_today", "sending_domains",
                                  "domain_detail", "activity_this_week",
                                  "lead_counts", "replies", "weekly_plan")]
        self.assertTrue(tool_names, "the queue-reading tools are gone")
        scope = slackscope.Scope(slackscope.INTERNAL, source="test")

        with mock.patch.object(bison, "scheduled_emails", scheduled_emails):
            for name in tool_names:
                with self.subTest(tool=name):
                    try:
                        tools.run(scope, name,
                                  "sending-domain-a.example.test")
                    except Exception:                           # noqa: BLE001
                        # A tool that fails for its own reasons is not this
                        # file's subject; an uncapped read is, and it has
                        # already been recorded by the time anything raises.
                        pass
        self.assertEqual(
            uncapped, [],
            "these reads reached the provider without a cap - read the "
            "queue through `slackagentreadback.queue`, which carries it")


if __name__ == "__main__":
    unittest.main()
