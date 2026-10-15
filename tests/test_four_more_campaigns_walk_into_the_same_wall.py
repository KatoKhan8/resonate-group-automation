r"""One campaign is past the queue cap and four cross it on the next step.

TASK-0150, lane `suppression`. Third in the series: TASK-0130 measured the cap
and proposed a fix it did not apply, TASK-0140 repaired the bounce stop's
verdict, and this one applies the cap at the two `src/` readers and ships the
early warning for the four campaigns behind 491.

## THE CORRECTION THAT COMES FIRST

**TASK-0130 reported that campaign 491's bounce "has never passed through
`bouncepolicy.decide` by this path and cannot, at cap 40". That is wrong, and
`TheProductionBouncePathNeverTookTheCap` below is the measurement.**

The production bounce path is
`bison_watch_loop` main loop -> `snapshot(watched, on_queue=_bounce_recorder)`
-> `snapshot` reads the queue at `bison.CAMPAIGN_QUEUE_PAGE_CAP` (400)
-> `on_queue(queue)` -> `record_bounces(id, queue=queue, live=True)`
-> `scheduled_rows(id, queue=queue)`, which iterates the rows it was HANDED
and makes **no provider call at all**.

So the 40-page default was never on that path. `bison_watch_loop.py`'s own
docstring says so in plain words - *"ZERO EXTRA PROVIDER CALLS. `snapshot` has
already paid for this queue; it hands the rows here rather than letting a
second reader walk them, which would also be a SMALLER read"*. The cap bit
only the callers that make their own read: `collision._queue_is_silent`,
`observe_emails`, and `confirm_email_touches`/`record_bounces` invoked without
`queue=`, which is the `leadobserve` CLI.

That class of test is green before the change and must stay green. It is the
control: the cap fix must not move the production path onto a second read.

## THE WALL, AND WHY THE MARGIN IS NOT A PERCENTAGE

`src/queuewall.py` assesses every campaign against EVERY reader's cap, because
TASK-0130 measured five distinct effective caps for one endpoint and a campaign
readable by the watcher can be invisible to the gate beside it.

The margin is **one more sequence step at today's lead count**. Not chosen -
it is the largest discrete jump a queue can take, it needs no lead added, and
the operator can schedule it this afternoon. The five largest campaigns sit at
exactly two scheduled rows per lead (665/333, 500/250, 446/223, 434/217,
409/206), so a third step is `rows * 3/2`, and 503, 504, 505 and 492 all cross
600 rows.

## THE ARITHMETIC IS PINNED TO THE MEASUREMENT

`TheCommittedCountsAreTheRecordedMeasurement` guards the fixture. Without it
every other class here would be asserting about a file anybody could edit, and
a wall check that agrees with its own input proves nothing.
"""
import datetime
import importlib.util
import json
import math
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import collision                                        # noqa: E402
from src import leadobserve                                      # noqa: E402
from src import queuewall                                        # noqa: E402
from src.providers import bison                                  # noqa: E402

COUNTS_FILE = os.path.join(ROOT, "docs", "state",
                           "QUEUE-COUNTS-2026-10-15.json")
CHECK = os.path.join(ROOT, "scripts", "queue_wall_check.py")

#: 491 as the watcher's heartbeat and the completed 2026-10-03 census read it.
LIVE_491_LEADS, LIVE_491_ROWS, LIVE_491_PAGES = 333, 665, 45

#: The four behind it, from the same measurement. Every one at two rows a lead.
BEHIND_491 = {503: (250, 500), 504: (223, 446), 505: (217, 434),
              492: (206, 409)}


def _check():
    spec = importlib.util.spec_from_file_location("_queue_wall_check", CHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _counts():
    with open(COUNTS_FILE, encoding="utf-8") as handle:
        return json.load(handle)


def _fresh(campaigns, days_old=0.0):
    when = (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=days_old))
    return {"measured_at": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "campaigns": campaigns}


def _row(i, status="bounced", mailbox=2736):
    return {"id": 900000 + i, "status": status,
            "sequence_step_id": 1,
            "scheduled_date": "2026-09-22T13:03:00.000000Z",
            "sent_at": "2026-09-22T13:03:04.000000Z",
            "raw_message_id": f"msg-{i}",
            "email_subject": "s", "email_body": "<p>b</p>",
            "lead": {"id": 170000 + i, "email": f"row{i}@example.test",
                     "custom_variables": []},
            "sender_email": {"id": mailbox, "email": "s@example.test"},
            "campaign": {"status": "paused", "open_tracking": False}}


class _Pager:
    """`bison.scheduled_emails` with `bison._paged`'s refusal contract."""

    def __init__(self, rows=LIVE_491_ROWS):
        self.rows = [_row(i) for i in range(rows)]
        self.caps = []

    def __call__(self, campaign_id, cap=None):
        self.caps.append(cap)
        effective = cap or bison.PAGE_CAP
        pages = max(1, math.ceil(len(self.rows) / bison.PAGE_SIZE))
        if pages > effective:
            raise bison.PartialInventory(
                f"emailbison scheduled_emails: {pages} pages to walk and this "
                f"read stops at {effective}. Refusing to return "
                f"{effective * bison.PAGE_SIZE} of {len(self.rows)} as though "
                f"it were all of them")
        return list(self.rows)


# ------------------------------------------------- the correction, as control


class TheProductionBouncePathNeverTookTheCap(unittest.TestCase):
    """GREEN BEFORE THE CHANGE AND IT MUST STAY GREEN.

    TASK-0130 concluded 491's bounce could never reach `bouncepolicy.decide`
    at cap 40. The watcher hands `record_bounces` the rows `snapshot` already
    paid for at cap 400, so that path never took 40 and the conclusion was
    wrong. These tests hold the property the cap fix must not break: the
    production path must still make NO second read.
    """

    def test_handed_rows_make_no_provider_call_at_all(self):
        rows = [_row(i) for i in range(LIVE_491_ROWS)]
        pager = _Pager()
        with mock.patch.object(bison, "scheduled_emails", pager):
            out = leadobserve.scheduled_rows(491, queue=rows)
        self.assertEqual(pager.caps, [],
                         "a handed-in queue must not be re-read")
        self.assertEqual(len(out), LIVE_491_ROWS)

    def test_all_665_rows_survive_the_trim_when_handed_in(self):
        """Not 600, and not a prefix. Every row reaches the gate."""
        rows = [_row(i) for i in range(LIVE_491_ROWS)]
        pager = _Pager()
        with mock.patch.object(bison, "scheduled_emails", pager):
            out = leadobserve.scheduled_rows(491, queue=rows)
        self.assertEqual(len(out), LIVE_491_ROWS)
        self.assertEqual({r["state"] for r in out}, {leadobserve.BOUNCED})
        self.assertEqual(pager.caps, [])

    def test_the_watcher_reads_the_queue_once_at_four_hundred(self):
        """`snapshot` hands `on_queue` the 400-cap rows, and asks once.

        By import-and-call rather than by reading the source, so it survives
        a rewrite: the pager records every cap it was asked for.
        """
        watch = importlib.util.spec_from_file_location(
            "_bison_watch_loop",
            os.path.join(ROOT, "scripts", "bison_watch_loop.py"))
        module = importlib.util.module_from_spec(watch)
        watch.loader.exec_module(module)
        pager = _Pager()
        seen = []
        with mock.patch.object(bison, "scheduled_emails", pager), \
                mock.patch.object(bison, "campaign", lambda *a, **k: {}), \
                mock.patch.object(module, "_provider_sending_plan",
                                  lambda *a, **k: None), \
                mock.patch.object(module, "_membership_states",
                                  lambda *a, **k: None):
            module.snapshot(491, on_queue=seen.append)
        self.assertEqual(pager.caps, [bison.CAMPAIGN_QUEUE_PAGE_CAP])
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(seen[0]), LIVE_491_ROWS)


# ----------------------------------------------------------- the readers' caps


class EverySrcQueueReaderAsksForTheQueueCap(unittest.TestCase):
    """The two readers TASK-0130 left on the default."""

    def test_scheduled_rows_asks_for_four_hundred(self):
        pager = _Pager()
        with mock.patch.object(bison, "scheduled_emails", pager):
            leadobserve.scheduled_rows(491)
        self.assertEqual(pager.caps, [bison.CAMPAIGN_QUEUE_PAGE_CAP])

    def test_queue_is_silent_asks_for_four_hundred(self):
        pager = _Pager()
        with mock.patch.object(bison, "scheduled_emails", pager):
            collision._queue_is_silent(491)
        self.assertEqual(pager.caps, [bison.CAMPAIGN_QUEUE_PAGE_CAP])

    def test_zero_send_evidence_can_now_reach_491s_queue(self):
        """A guard that can never pass is not a guard.

        At cap 40 this read refused 491 for ever, so `_queue_is_silent`
        returned False on every call whatever the queue held. It must now
        answer about the rows.
        """
        pager = _Pager()
        with mock.patch.object(bison, "scheduled_emails", pager):
            silent, why = collision._queue_is_silent(491)
        self.assertFalse(silent)
        self.assertNotIn("could not be read", why)
        self.assertIn("already sent", why)

    def test_the_cap_is_not_the_membership_default(self):
        """Not a default and not a removal.

        `PAGE_CAP` still guards whole-campaign membership walks, where 40 is
        right because a client campaign is thousands of pages, and the cap
        stays below the measured ~500-page 422 wall.
        """
        self.assertEqual(bison.PAGE_CAP, 40)
        self.assertGreater(bison.CAMPAIGN_QUEUE_PAGE_CAP, LIVE_491_PAGES)
        self.assertLess(bison.CAMPAIGN_QUEUE_PAGE_CAP, 500)


# ------------------------------------------------------------- the arithmetic


class TheWallArithmetic(unittest.TestCase):
    """Pages, the wall, steps and headroom, against the real numbers."""

    def test_pages_rounds_up_and_an_empty_queue_still_costs_one(self):
        self.assertEqual(queuewall.PAGE_SIZE, bison.PAGE_SIZE)
        self.assertEqual(queuewall.pages(LIVE_491_ROWS), LIVE_491_PAGES)
        self.assertEqual(queuewall.pages(600), 40)
        self.assertEqual(queuewall.pages(601), 41)
        self.assertEqual(queuewall.pages(0), 1)

    def test_the_wall_at_forty_is_six_hundred_rows(self):
        self.assertEqual(queuewall.wall_rows(40), 600)
        self.assertEqual(queuewall.wall_rows(400), 6000)

    def test_the_steps_come_out_of_the_counts(self):
        """Every one of the five biggest is two rows a lead."""
        self.assertEqual(queuewall.steps_of(LIVE_491_LEADS, LIVE_491_ROWS), 2)
        for leads, rows in BEHIND_491.values():
            self.assertEqual(queuewall.steps_of(leads, rows), 2)
        self.assertIsNone(queuewall.steps_of(0, 0))
        self.assertIsNone(queuewall.steps_of(None, 100))

    def test_the_line_is_three_hundred_leads_not_six_hundred_rows(self):
        """At two rows a lead, cap 40 makes any campaign past 300 invisible."""
        self.assertEqual(queuewall.leads_of_headroom(200, 400, 40), 100)
        self.assertEqual(queuewall.leads_of_headroom(300, 600, 40), 0)
        self.assertEqual(
            queuewall.leads_of_headroom(LIVE_491_LEADS, LIVE_491_ROWS, 40),
            -33)

    def test_one_more_step_is_rows_times_steps_plus_one_over_steps(self):
        fits, projected = queuewall.survives_one_more_step(250, 500, 40)
        self.assertEqual(projected, 750)
        self.assertFalse(fits)
        fits, projected = queuewall.survives_one_more_step(250, 500, 400)
        self.assertEqual(projected, 750)
        self.assertTrue(fits)


class TheMarginIsOneMoreSequenceStep(unittest.TestCase):
    """The real finding: four more campaigns, no lead added."""

    def test_all_four_behind_491_are_at_risk_at_cap_forty(self):
        for cid, (leads, rows) in sorted(BEHIND_491.items()):
            one = queuewall.assess_one(cid, leads, rows, 40)
            self.assertEqual(one["verdict"], queuewall.AT_RISK, cid)
            self.assertLessEqual(one["pages"], 40, cid)
            self.assertGreater(queuewall.pages(one["projected_rows"]), 40, cid)

    def test_the_projections_are_the_measured_ones(self):
        """750, 669, 651, 614 - the numbers TASK-0130 published."""
        expected = {503: 750, 504: 669, 505: 651, 492: 614}
        for cid, (leads, rows) in BEHIND_491.items():
            one = queuewall.assess_one(cid, leads, rows, 40)
            self.assertEqual(one["projected_rows"], expected[cid], cid)

    def test_none_of_them_is_at_risk_at_the_watcher_cap(self):
        """The fix moves them from AT-RISK to OK, which is the whole point."""
        for cid, (leads, rows) in BEHIND_491.items():
            one = queuewall.assess_one(cid, leads, rows,
                                       bison.CAMPAIGN_QUEUE_PAGE_CAP)
            self.assertEqual(one["verdict"], queuewall.OK, cid)

    def test_491_is_over_not_merely_at_risk(self):
        one = queuewall.assess_one(491, LIVE_491_LEADS, LIVE_491_ROWS, 40)
        self.assertEqual(one["verdict"], queuewall.OVER)
        self.assertIn("cannot read this queue at all", one["why"])


class AQueueOverACapIsNamedNotSilent(unittest.TestCase):
    """What the brief asked for: named, with its numbers and the cap."""

    def test_the_refusal_names_the_rows_the_pages_and_the_cap(self):
        one = queuewall.assess_one(491, LIVE_491_LEADS, LIVE_491_ROWS, 40)
        self.assertIn(str(LIVE_491_ROWS), one["why"])
        self.assertIn(str(LIVE_491_PAGES), one["why"])
        self.assertIn("40", one["why"])
        self.assertEqual(one["cap"], 40)
        self.assertEqual(one["wall_rows"], 600)

    def test_a_campaign_says_which_readers_cannot_see_it(self):
        """Readable by the watcher, invisible to the producer. Both named."""
        result = queuewall.assess(_fresh([
            {"campaign_id": 491, "leads": LIVE_491_LEADS,
             "rows": LIVE_491_ROWS}]))
        entry = result["campaigns"][0]
        self.assertEqual(entry["invisible_to"], ["producer-default"])
        self.assertIn("watcher", entry["readable_by"])
        self.assertEqual(entry["worst_verdict"], queuewall.OVER)

    def test_an_empty_queue_is_distinguishable_from_an_unreadable_one(self):
        """The brief's own sentence, as an assertion.

        A producer returning nothing because there is nothing, and one
        returning nothing because it refused, must not look the same.
        """
        result = queuewall.assess(_fresh([
            {"campaign_id": 484, "leads": 0, "rows": 0},
            {"campaign_id": 491, "leads": LIVE_491_LEADS,
             "rows": LIVE_491_ROWS}]))
        by_id = {c["campaign_id"]: c for c in result["campaigns"]}
        self.assertEqual(by_id[484]["worst_verdict"], queuewall.OK)
        self.assertEqual(by_id[491]["worst_verdict"], queuewall.OVER)
        self.assertEqual(by_id[484]["invisible_to"], [])
        self.assertEqual(by_id[491]["invisible_to"], ["producer-default"])


class StaleCountsAssessNothing(unittest.TestCase):
    """A stale cached provider file reading as current is the defect."""

    def test_counts_past_the_age_limit_are_refused(self):
        result = queuewall.assess(
            _fresh([{"campaign_id": 491, "leads": 333, "rows": 665}],
                   days_old=9),
            max_age_days=7)
        self.assertTrue(result["stale"])
        self.assertTrue(result["refused"])
        self.assertIn("stale", result["why"])

    def test_a_stale_run_assesses_no_campaign_at_all(self):
        """Not even a correct verdict. Nothing is reported off old counts."""
        result = queuewall.assess(
            _fresh([{"campaign_id": 491, "leads": 333, "rows": 665}],
                   days_old=9),
            max_age_days=7)
        self.assertEqual(result["campaigns"], [])
        self.assertEqual(result["by_reader"], {})

    def test_fresh_counts_are_assessed(self):
        """The control, without which the test above passes vacuously."""
        result = queuewall.assess(
            _fresh([{"campaign_id": 491, "leads": 333, "rows": 665}],
                   days_old=0.5),
            max_age_days=7)
        self.assertFalse(result["stale"])
        self.assertEqual(len(result["campaigns"]), 1)


class UnknownIsNeverOk(unittest.TestCase):
    """A campaign whose size nobody knows is not a campaign that fits."""

    def test_a_missing_row_count_is_unknown(self):
        one = queuewall.assess_one(491, 333, None, 40)
        self.assertEqual(one["verdict"], queuewall.UNKNOWN)
        self.assertIsNone(one["pages"])

    def test_unknown_refuses_the_run(self):
        result = queuewall.assess(_fresh([
            {"campaign_id": 487, "leads": 10, "rows": 20},
            {"campaign_id": 491, "leads": 333, "rows": None}]))
        self.assertTrue(result["refused"])
        by_id = {c["campaign_id"]: c for c in result["campaigns"]}
        self.assertEqual(by_id[491]["worst_verdict"], queuewall.UNKNOWN)
        self.assertEqual(by_id[487]["worst_verdict"], queuewall.OK)

    def test_unknown_is_not_in_passing(self):
        self.assertEqual(queuewall.PASSING, (queuewall.OK,))
        self.assertNotIn(queuewall.UNKNOWN, queuewall.PASSING)
        self.assertNotIn(queuewall.AT_RISK, queuewall.PASSING)
        self.assertNotIn(queuewall.OVER, queuewall.PASSING)


# ---------------------------------------------------------------- the run


class TheExitCodesAreThree(unittest.TestCase):
    """0 fits / 1 a wall / 2 could not assess, and 2 outranks 1."""

    def setUp(self):
        self.module = _check()

    def _code(self, campaigns, days_old=0.0, max_age_days=7):
        result = queuewall.assess(_fresh(campaigns, days_old),
                                  max_age_days=max_age_days)
        return self.module.exit_code(result), result

    def test_everything_fitting_exits_zero(self):
        code, result = self._code([{"campaign_id": 487, "leads": 10,
                                    "rows": 20}])
        self.assertEqual(code, 0)
        self.assertFalse(result["refused"])

    def test_a_campaign_over_a_cap_exits_one(self):
        code, _ = self._code([{"campaign_id": 491, "leads": LIVE_491_LEADS,
                               "rows": LIVE_491_ROWS}])
        self.assertEqual(code, 1)

    def test_a_campaign_at_risk_exits_one(self):
        code, _ = self._code([{"campaign_id": 503, "leads": 250,
                               "rows": 500}])
        self.assertEqual(code, 1)

    def test_stale_counts_exit_two_not_one(self):
        """CANNOT-ASSESS is not the same answer as FOUND A WALL."""
        code, _ = self._code([{"campaign_id": 491, "leads": LIVE_491_LEADS,
                               "rows": LIVE_491_ROWS}], days_old=9)
        self.assertEqual(code, 2)

    def test_unknown_outranks_a_wall(self):
        """A run holding both must report the one it could not measure."""
        code, _ = self._code([{"campaign_id": 491, "leads": LIVE_491_LEADS,
                               "rows": LIVE_491_ROWS},
                              {"campaign_id": 500, "leads": 1, "rows": None}])
        self.assertEqual(code, 2)

    def test_main_returns_the_code_it_computed(self):
        """The verdict reaches the process, not just the dict."""
        with mock.patch.object(sys, "stdout"):
            code = self.module.main(["--counts", COUNTS_FILE,
                                     "--max-age-days", "100000"])
        self.assertEqual(code, 1)

    def test_the_json_mode_carries_the_same_code(self):
        with mock.patch("sys.stdout") as out:
            code = self.module.main(["--counts", COUNTS_FILE, "--json",
                                     "--max-age-days", "100000"])
        printed = "".join(c.args[0] for c in out.write.call_args_list)
        payload = json.loads(printed)
        self.assertEqual(code, 1)
        self.assertEqual(payload["exit_code"], 1)
        self.assertTrue(payload["refused"])


class TheOneLineNamesTheCampaigns(unittest.TestCase):
    """What the operator reads at a glance."""

    def test_the_refusal_line_names_every_campaign_and_is_one_sentence(self):
        result = queuewall.assess(_fresh(
            [{"campaign_id": 491, "leads": LIVE_491_LEADS,
              "rows": LIVE_491_ROWS}]
            + [{"campaign_id": c, "leads": l, "rows": r}
               for c, (l, r) in sorted(BEHIND_491.items())]),
            max_age_days=100000)
        line = result["why"]
        self.assertEqual(line.count("\n"), 0)
        self.assertIn("491", line)
        for cid in BEHIND_491:
            self.assertIn(str(cid), line)
        self.assertIn("OVER", line)
        self.assertIn("AT-RISK", line)

    def test_a_clean_line_says_so_without_the_word_ok_alone(self):
        result = queuewall.assess(_fresh([{"campaign_id": 487, "leads": 10,
                                           "rows": 20}]))
        self.assertEqual(result["why"].count("\n"), 0)
        self.assertIn("survive one more sequence step", result["why"])
        self.assertNotIn("REFUSES", result["why"])


class TheCommittedCountsAreTheRecordedMeasurement(unittest.TestCase):
    """Guarding the fixture. Without this, everything above is circular."""

    def test_the_counts_file_holds_the_twenty_measured_campaigns(self):
        counts = _counts()
        self.assertEqual(len(counts["campaigns"]), 20)
        by_id = {c["campaign_id"]: c for c in counts["campaigns"]}
        self.assertEqual(by_id[491]["leads"], LIVE_491_LEADS)
        self.assertEqual(by_id[491]["rows"], LIVE_491_ROWS)
        for cid, (leads, rows) in BEHIND_491.items():
            self.assertEqual(by_id[cid]["leads"], leads, cid)
            self.assertEqual(by_id[cid]["rows"], rows, cid)

    def test_the_totals_are_2888_rows_202_page_reads_205_requests(self):
        """TASK-0130 published 205 and that is REQUESTS, not pages of rows.

        202 pages carry rows; three campaigns hold none, and each still costs
        one request to discover that. The two numbers are both right and they
        are not the same number.
        """
        result = queuewall.assess(_counts(), max_age_days=100000)
        self.assertEqual(result["total_rows"], 2888)
        self.assertEqual(result["total_row_pages"], 202)
        self.assertEqual(result["requests_per_pass"], 205)

    def test_the_file_names_its_source_and_denies_being_the_authority(self):
        counts = _counts()
        self.assertIn("heartbeat", counts["source"])
        self.assertIn("NOT THE AUTHORITY", counts["authority"])
        self.assertEqual(counts["page_size"], bison.PAGE_SIZE)

    def test_the_real_file_reproduces_the_finding(self):
        """End to end on the committed counts: one OVER, four AT-RISK."""
        result = queuewall.assess(_counts(), max_age_days=100000)
        producer = result["by_reader"]["producer-default"]
        self.assertEqual(producer["over"], [491])
        self.assertEqual(sorted(producer["at_risk"]), [492, 503, 504, 505])
        watcher = result["by_reader"]["watcher"]
        self.assertEqual(watcher["over"], [])
        self.assertEqual(watcher["at_risk"], [])


class TheReaderCapsAreTheMeasuredOnes(unittest.TestCase):
    """The registry describes the code, or it answers about nothing."""

    def test_the_registry_holds_the_providers_own_two_constants(self):
        caps = dict(queuewall.READER_CAPS)
        self.assertEqual(caps["producer-default"], bison.PAGE_CAP)
        self.assertEqual(caps["watcher"], bison.CAMPAIGN_QUEUE_PAGE_CAP)

    def test_the_registry_is_ordered_smallest_first(self):
        values = [cap for _name, cap in queuewall.READER_CAPS]
        self.assertEqual(values, sorted(values))
        self.assertEqual(values[0], bison.PAGE_CAP)

    def test_five_distinct_caps_were_measured_and_four_are_named(self):
        """40, 80, 200, 400 - the fifth is "whatever the caller passed"."""
        self.assertEqual(sorted(cap for _n, cap in queuewall.READER_CAPS),
                         [40, 80, 200, 400])


if __name__ == "__main__":
    unittest.main(verbosity=2)
