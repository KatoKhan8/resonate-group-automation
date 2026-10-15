r"""The suppression producer reads 40 pages where the watcher reads 400.

TASK-0130. The sibling of
`test_the_largest_campaign_is_the_one_the_agent_cannot_read.py`, which fixed
the five AGENT-side queue readers on 2026-09-23 and left the SUPPRESSION-side
producer at the default. `src/leadobserve.scheduled_rows` passes no cap, so it
takes `bison.PAGE_CAP = 40` - 600 rows - while
`scripts/bison_watch_loop.py` reads the same queue every 180s at
`bison.CAMPAIGN_QUEUE_PAGE_CAP = 400`.

## THE MEASUREMENT, 2026-10-15

Twenty watched EmailBison campaigns, row counts read off the watcher's own
heartbeat files (`work/heartbeat/bison-<id>.json`, written at 21:55-21:58Z)
and corroborated page-for-page by the completed forward-book census of
2026-10-03 (`work/forward-book-census.json`, `complete: true`):

    491   665 rows   45 pages   OVER the 40-page default
    503   500 rows   34 pages
    504   446 rows   30 pages
    505   434 rows   29 pages
    492   409 rows   28 pages

491 is the only campaign over the line today and it is the only one of the
twenty carrying a bounce that nothing has yet recorded. Every one of the four
behind it runs at exactly two scheduled rows per lead, so the default cap
makes any campaign past ~300 leads unreadable to this producer.

## WHAT IS ASSERTED, AND WHAT IS NOT

NOT the number. `PAGE_CAP` is right for what it guards - a whole-campaign
membership walk of a client campaign of 95,000 - and
`CAMPAIGN_QUEUE_PAGE_CAP` is right for a queue. What is wrong is that the
suppression producer takes the first by accident, through a default, so the
answer to "has this address bounced" depends on which code path asked.

A QUEUE LARGER THAN THE CAP MUST BE FULLY READ. The fake below refuses
exactly as `bison._paged` refuses - fifteen rows a page, raise past the cap,
never a prefix - so a caller that takes the small default fails here on row
count, and a caller that "fixes" the refusal by catching it and returning
`[]` fails here on the refusal class. Both directions are held, because a
bounce gate that cannot see the newest rows and a bounce gate that reports a
clean zero are the same defect wearing different clothes.

`tests/fakebison.py`'s `scheduled_emails` ignores `cap` altogether and never
paginates, which is why no existing fixture could have caught this.
"""
import math
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import collision                                        # noqa: E402
from src import leadobserve                                      # noqa: E402
from src import slackagentreadback as readback                    # noqa: E402
from src import store                                            # noqa: E402
from src.providers import bison                                   # noqa: E402

CAMPAIGN = "491"

#: 491 as the watcher and the census both read it on 2026-10-15/10-03. The
#: pager works in pages; 665 rows at the provider's fifteen to a page is 45,
#: and the census recorded exactly 45 pages for exactly 665 rows.
LIVE_491_ROWS = 665
LIVE_491_PAGES = 45


def _queue(rows):
    """`rows` provider-shaped scheduled-email rows, all of them bounced.

    Bounced because `record_bounces` narrows to that state, so a row count
    that survives the narrowing proves the whole queue reached the gate.
    """
    return [{"id": 900000 + i,
             "status": "bounced",
             "sequence_step_id": 1,
             "scheduled_date": "2026-09-22T13:03:00.000000Z",
             "sent_at": "2026-09-22T13:03:04.000000Z",
             "raw_message_id": f"msg-{i}",
             "email_subject": "s",
             "email_body": "<p>b</p>",
             "lead": {"id": 170000 + i,
                      "email": f"row{i}@example.test",
                      "custom_variables": []},
             "sender_email": {"id": 2736, "email": "s@example.test"},
             "campaign": {"status": "paused", "open_tracking": False}}
            for i in range(rows)]


class _Pager:
    """`bison.scheduled_emails` with the real pager's refusal contract.

    Stands in at the transport rather than at the function, so what is under
    test is the cap the caller asks for and the rows it ends up with - not a
    branch anybody can read off the source.
    """

    def __init__(self, rows=LIVE_491_ROWS):
        self.rows = _queue(rows)
        self.caps = []

    def __call__(self, campaign_id, cap=None):
        self.caps.append(cap)
        effective = cap or bison.PAGE_CAP
        pages = max(1, math.ceil(len(self.rows) / bison.PAGE_SIZE))
        if pages > effective:
            raise bison.PartialInventory(
                f"emailbison scheduled_emails: {pages} pages to walk and "
                f"this read stops at {effective}. Refusing to return "
                f"{effective * bison.PAGE_SIZE} of {len(self.rows)} as "
                f"though it were all of them")
        return list(self.rows)

    def patch(self):
        return mock.patch.object(bison, "scheduled_emails", self)


class TheProducerReadsTheWholeQueue(unittest.TestCase):
    """The defect: 491 is 45 pages and this producer stops at 40."""

    def test_scheduled_rows_reads_every_row_of_491(self):
        pager = _Pager()
        with pager.patch():
            rows = leadobserve.scheduled_rows(CAMPAIGN)
        self.assertEqual(
            len(rows), LIVE_491_ROWS,
            f"`leadobserve.scheduled_rows` saw {len(rows)} of "
            f"{LIVE_491_ROWS} rows; it asked for cap {pager.caps}")

    def test_scheduled_rows_asks_for_the_queue_cap(self):
        pager = _Pager(rows=10)
        with pager.patch():
            leadobserve.scheduled_rows(CAMPAIGN)
        self.assertEqual(pager.caps, [bison.CAMPAIGN_QUEUE_PAGE_CAP])

    def test_record_bounces_reaches_every_bounced_row(self):
        """The gate itself, dry, with no record to match - the narrowing is
        what is under test, not the matching. `waiting` is empty because
        every row is `bounced`, so an unmatched row lands in `unmatched` and
        the count there IS the count of rows that reached the gate."""
        pager = _Pager()
        with pager.patch():
            out = leadobserve.record_bounces(CAMPAIGN, recs=[], live=False)
        reached = (len(out["recorded"]) + len(out["already"])
                   + len(out["unmatched"]) + len(out["refused"]))
        self.assertEqual(
            reached, LIVE_491_ROWS,
            f"the bounce gate saw {reached} of {LIVE_491_ROWS} bounced rows")

    def test_observe_emails_asks_for_the_queue_cap(self):
        """Isolated, because this one WRITES - `store.refuse_production_write`
        stops a test reaching real client state and it is right to."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        self.addCleanup(store.use_directory(os.path.join(tmp, "work")))
        pager = _Pager(rows=10)
        with pager.patch():
            leadobserve.observe_emails(CAMPAIGN)
        self.assertEqual(pager.caps, [bison.CAMPAIGN_QUEUE_PAGE_CAP])

    def test_confirm_email_touches_asks_for_the_queue_cap(self):
        pager = _Pager(rows=10)
        with pager.patch():
            leadobserve.confirm_email_touches(CAMPAIGN, recs=[], live=False)
        self.assertEqual(pager.caps, [bison.CAMPAIGN_QUEUE_PAGE_CAP])

    def test_a_caller_supplied_queue_is_not_re_read(self):
        """The one legitimate uncapped path stays uncapped: rows somebody
        else already paid for cost no provider call at all."""
        pager = _Pager(rows=10)
        with pager.patch():
            rows = leadobserve.scheduled_rows(CAMPAIGN, queue=_queue(3))
        self.assertEqual(pager.caps, [])
        self.assertEqual(len(rows), 3)


class TheCapIsBigEnoughForTheCampaignThatNeedsIt(unittest.TestCase):

    def test_the_queue_cap_clears_the_live_page_count(self):
        """45 pages is the measurement, not a guess."""
        self.assertGreater(bison.CAMPAIGN_QUEUE_PAGE_CAP, LIVE_491_PAGES)

    def test_the_provider_default_would_not_have_been_enough(self):
        """Names the defect in one assertion: the default refuses 491."""
        self.assertLess(bison.PAGE_CAP, LIVE_491_PAGES)

    def test_the_queue_cap_stays_under_the_providers_own_offset_ceiling(self):
        """Why the cap is not simply removed.

        Offset pagination on this instance is refused with 422 beyond roughly
        500 pages - measured against campaign 352, 6,382 pages, and recorded
        in `docs/THE-23rd-IS-PROVEN-2026-09-18.md`. A walk with no cap would
        therefore hand the caller a transport-shaped `ProviderError` instead
        of the named `PartialInventory` the callers are written against.
        """
        self.assertLess(bison.CAMPAIGN_QUEUE_PAGE_CAP, 500)

    def test_the_agent_and_the_producer_use_one_number(self):
        """Two readers of one queue, one number.

        `slackagentreadback` was given 400 on 2026-09-23 and the suppression
        producer was not. A producer that can see less of a campaign than the
        agent can is a producer whose bounces the agent can see and it cannot.
        """
        self.assertEqual(readback.QUEUE_PAGE_CAP,
                         bison.CAMPAIGN_QUEUE_PAGE_CAP)


class TheRefusalSurvivesTheRaise(unittest.TestCase):
    """A bigger cap is still a cap, and past it the answer is still no.

    This is the half that must never be "fixed". The day `scheduled_rows`
    catches `PartialInventory` and returns `[]` is the day the bounce gate
    reports a campaign nobody could read as a campaign with no bounces.
    """

    def oversized(self):
        return _Pager(rows=bison.CAMPAIGN_QUEUE_PAGE_CAP * bison.PAGE_SIZE
                      + bison.PAGE_SIZE)

    def test_scheduled_rows_raises_rather_than_returning_empty(self):
        with self.oversized().patch():
            with self.assertRaises(bison.PartialInventory):
                leadobserve.scheduled_rows(CAMPAIGN)

    def test_record_bounces_raises_rather_than_reporting_no_bounces(self):
        with self.oversized().patch():
            with self.assertRaises(bison.PartialInventory):
                leadobserve.record_bounces(CAMPAIGN, recs=[], live=False)


class NoQueueReaderInSrcTakesTheMembershipDefault(unittest.TestCase):
    """The durable guard: the next reader cannot take 40 by accident.

    BEHAVIOURAL, not a grep - CLAUDE.md's rule. Each module is driven through
    its real entry point and the cap is recorded off the provider, so a reader
    added tomorrow trips this however it is spelled and a comment naming the
    function does not.

    `collision._queue_is_silent` fails CLOSED on a refusal, so its 40 is
    conservative rather than dangerous - but it means `zero_send_evidence`
    can never clear campaign 491, and a guard that can never pass is reported
    rather than left to be rediscovered.
    """

    def test_every_src_queue_reader_asks_for_the_queue_cap(self):
        wrong = {}
        for label, call in (
                ("leadobserve.scheduled_rows",
                 lambda: leadobserve.scheduled_rows(CAMPAIGN)),
                ("collision._queue_is_silent",
                 lambda: collision._queue_is_silent(CAMPAIGN)),
                ("slackagentreadback.queue",
                 lambda: readback.queue(CAMPAIGN))):
            pager = _Pager(rows=10)
            with pager.patch():
                try:
                    call()
                except Exception:                           # noqa: BLE001
                    # A reader that fails for its own reasons is not this
                    # file's subject; the cap is already recorded.
                    pass
            if pager.caps != [bison.CAMPAIGN_QUEUE_PAGE_CAP]:
                wrong[label] = pager.caps
        self.assertEqual(
            wrong, {},
            "these readers did not ask for `bison.CAMPAIGN_QUEUE_PAGE_CAP`; "
            "a reader that takes the membership default stops at 600 rows "
            "and campaign 491 is 665")


if __name__ == "__main__":
    unittest.main()
