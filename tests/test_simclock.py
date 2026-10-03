#!/usr/bin/env python3
"""The simulation's clock, and the proof that the real code reads it.

Phase 2 runs day 0 to day 90 one simulated day at a time through the REAL
scheduler, classifier, DNC and recontact code. That needs exactly one seam for
"now", and this module is the evidence that the seam is the one the code
actually reads - not an argument that it ought to be.

WHY `store.now()` IS THE SEAM, measured on e967271d, 2026-10-03:

    grep -rc "store\\.now()" src/                      151 calls, 78 files
    grep -rcE "datetime\\.now\\(|utcnow\\(|date\\.today\\(|time\\.time\\(" src/
                                                        75 calls, 42 files

and on the phase-2 path specifically - scheduler, reply ingest, classifier,
DNC, handoff, recontact, account policy - 16 `store.now()` calls in 11 modules
against 4 direct reads in 3. All four of those four are
`now = now or datetime.datetime.now(...)` fallbacks standing behind an
injectable `now=` parameter, so the path holds NO unconditional wall-clock read
outside `store.now()`. `replies`, `eligibility`, `revival`, `cadence`,
`bisonfactory` and `heyreachfactory` read no clock at all - they take the day
as a parameter and say so in their docstrings.

So filling the DEFAULT reaches the whole path. The alternative - threading a
`now=` through twenty modules' internals - would mean editing the send path to
run a simulation, which is a worse trade than one override in the one module
that already owns the answer.

THE CONTROL IS NOT OPTIONAL. `TheRealClockIsStillTheDefault` exists because a
date-dependent test faked two regressions in this repository: a verdict that is
a function of the wall clock is not a test of the function under it. If the
seam ever defaulted to a pinned instant, every freshness, fatigue, cooldown and
approval-window check in the system would quietly answer from it.
"""
import concurrent.futures
import datetime
import re
import unittest

from src import oooreturn, senderheadroom, store
from tests.campaignbase import CampaignTest

# Day 0 is a Thursday, day 90 is a Wednesday, so neither boundary lands on a
# weekend and `senderheadroom`'s `sending_days` cannot be what moved an answer.
DAY0 = datetime.datetime(2026, 9, 2, 9, 0, tzinfo=datetime.timezone.utc)
SPAN = 90

# `2026-09-02` + "out of the office until September 8" is the fixture
# `tests/test_oooreturn.py` already proves parses to this return date. Reusing
# its exact text and stamp keeps this module a test of the CLOCK rather than a
# second, weaker test of the date parser.
ABSENT_AT = "2026-09-02T08:14:00+00:00"
RETURN_DATE = "2026-09-08"


class Stepper:
    """A clock the simulation advances. One authority, one mutable day.

    Deliberately not a frozen instant: call sites build identity from
    `store.now()` - `f"emailbison:xchan:{store.now()}"` is in the
    cross-channel reply tests - so a clock that never moves makes
    `now()`-derived ids collide. A simulation steps the day.
    """

    def __init__(self, start=DAY0):
        self.start = start
        self.day = 0

    def __call__(self):
        return self.start + datetime.timedelta(days=self.day)

    def advance(self, days=1):
        self.day += days
        return self()


def census(finished_at, booked, sender=2736, campaign="487"):
    """A forward-book census state in `senderheadroom`'s own shape.

    `booked` is `{day_iso: rows}` for `sender`. `complete` is True and the
    walk is dated, because an incomplete or undated walk REFUSES before the
    clock is ever consulted - and a test whose answer came from the
    completeness gate would prove nothing about the clock.
    """
    return {"campaigns": {campaign: {
        "complete": True, "finished_at": finished_at,
        "by_sender_day": {f"{sender}|{day}": rows
                          for day, rows in booked.items()}}}}


class TheRealClockIsStillTheDefault(unittest.TestCase):
    """THE CONTROL. With nothing injected, nothing has changed."""

    def test_no_clock_is_installed_at_import(self):
        self.assertIsNone(
            store.clock(),
            "a module installed a clock at import time; every freshness and "
            "approval-window check in the system would answer from it")

    def test_now_still_reads_the_wall_clock(self):
        before = datetime.datetime.now(datetime.timezone.utc)
        got = store.now()
        after = datetime.datetime.now(datetime.timezone.utc)
        parsed = datetime.datetime.fromisoformat(got)
        self.assertLessEqual(before.replace(microsecond=0), parsed)
        self.assertLessEqual(parsed, after)

    def test_now_keeps_its_exact_string_contract(self):
        """Second-resolution, aware, UTC. 151 call sites store this string."""
        self.assertRegex(
            store.now(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$")

    def test_utcnow_and_now_are_the_same_instant(self):
        """Two accessors, one authority. A drift here is two clocks."""
        with store.clock_driven_by(Stepper()):
            self.assertEqual(store.now(), store.utcnow().isoformat())


class TheSeamItself(unittest.TestCase):

    def test_an_injected_clock_drives_now(self):
        stepper = Stepper()
        with store.clock_driven_by(stepper):
            self.assertEqual(store.now(), "2026-09-02T09:00:00+00:00")
            stepper.advance(SPAN)
            self.assertEqual(store.now(), "2026-12-01T09:00:00+00:00")

    def test_the_context_manager_restores_through_an_exception(self):
        class Boom(RuntimeError):
            pass

        with self.assertRaises(Boom):
            with store.clock_driven_by(Stepper()):
                raise Boom()
        self.assertIsNone(store.clock())

    def test_use_clock_returns_an_unconditional_restore(self):
        """`use_directory`'s recorded lesson, held here too.

        Two modules once wrote `if callable(restore): addCleanup(restore)` - a
        check that could never be false, so it never registered and never
        complained, and both leaked their override into every module that ran
        afterwards. The restore is returned unconditionally and is a callable,
        so that code is correct exactly where it stands.
        """
        restore = store.use_clock(Stepper())
        self.assertTrue(callable(restore))
        self.assertIsNotNone(store.clock())
        restore()
        self.assertIsNone(store.clock())

    def test_nesting_restores_the_outer_clock_not_the_wall_clock(self):
        outer, inner = Stepper(), Stepper(DAY0 + datetime.timedelta(days=10))
        with store.clock_driven_by(outer):
            with store.clock_driven_by(inner):
                self.assertEqual(store.now()[:10], "2026-09-12")
            self.assertEqual(store.now()[:10], "2026-09-02")

    def test_a_naive_datetime_is_refused(self):
        """Fail closed. Guessing a timezone on a freshness check is how a
        stale read-back looks current by up to a day."""
        with store.clock_driven_by(lambda: datetime.datetime(2026, 9, 2, 9, 0)):
            with self.assertRaises(ValueError):
                store.now()

    def test_a_non_datetime_is_refused(self):
        with store.clock_driven_by(lambda: "2026-09-02T09:00:00+00:00"):
            with self.assertRaises(TypeError):
                store.now()

    def test_the_injected_clock_survives_a_thread_pool(self):
        """THE REASON THIS IS NOT A ContextVar.

        `allow_writes` is a ContextVar and is NOT inherited by
        `ThreadPoolExecutor` workers. A simulated day that fanned out would
        read the REAL clock inside every worker and look perfectly healthy,
        and the only visible symptom would be a simulation whose freshness
        checks all passed. A module global is shared by threads in one
        process. This asserts that, rather than a comment claiming it.
        """
        with store.clock_driven_by(Stepper()):
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                seen = list(pool.map(lambda _: store.now(), range(8)))
        self.assertEqual(set(seen), {"2026-09-02T09:00:00+00:00"},
                         "a worker thread read a different clock")


class NinetyDaysMoveARecontactDecision(CampaignTest):
    """The seam reaches a real recontact verdict with no plumbing at all.

    `oooreturn.assess` is the recontact decision whose answer is a pure
    function of the day: `today_iso(today=None)` falls back to
    `store.now()[:10]` and nothing else. So this is the strongest available
    proof - no parameter is passed, the module is unmodified, and the verdict
    moves because the seam moved.
    """

    def absence(self):
        """Recorded through the REAL reply ingest, not hand-built.

        A hand-built row lets a wrong shape in through the fixture, which is
        the defect class this phase was told to avoid. `inbound.ingest` is the
        path a provider event actually takes.
        """
        from src import inbound

        row = {"id": 7001, "uuid": "uuid-7001", "type": "Tracked Reply",
               "folder": "Inbox", "from_email_address": "champ@acme.test",
               "created_at": ABSENT_AT, "date_received": ABSENT_AT,
               "text_body": "Automatic reply: out of the office until "
                            "September 8.",
               "automated_reply": True,
               "custom_variables": {"record_id": "acme",
                                    "contact_key": "acme-champ",
                                    "client": "demo"}}
        recs = self.seed_records()
        inbound.ingest({"data": [row]}, "emailbison", recs=recs,
                       config=self.config, post=lambda p, c=None: {"ok": True})
        return recs[0]

    def test_the_absence_carries_the_date_the_rest_of_this_rests_on(self):
        """Stated first: if the fixture stops carrying this date, the
        assertions below would be measuring the parser, not the clock."""
        absence = oooreturn.latest_absence(self.absence(), "acme-champ")
        self.assertEqual(absence["return_date"], RETURN_DATE)

    def test_the_verdict_moves_with_the_injected_clock(self):
        rec = self.absence()
        stepper = Stepper()
        with store.clock_driven_by(stepper):
            day0 = oooreturn.assess(rec, "acme-champ", config=self.config)
            self.assertEqual(day0["verdict"], oooreturn.NOT_YET)
            self.assertEqual(day0["why"], oooreturn.NOT_DUE)
            self.assertEqual(day0["as_of"], "2026-09-02")
            self.assertEqual(day0["days_until"], 6)

            stepper.advance(SPAN)
            day90 = oooreturn.assess(rec, "acme-champ", config=self.config)
            self.assertEqual(day90["verdict"], oooreturn.DUE)
            self.assertEqual(day90["why"], oooreturn.BACK)
            self.assertEqual(day90["as_of"], "2026-12-01")
            self.assertEqual(day90["days_since_return"], 84)

    def test_stepping_ninety_days_flips_the_verdict_on_the_recorded_date(self):
        """The phase-2 loop, in miniature: ninety-one single-day steps.

        Asserting the exact day of the flip rather than only that it flipped.
        A seam that advanced the clock but not the decision would still show
        day 0 NOT_YET and day 90 DUE if the verdict were read once and cached.
        """
        rec = self.absence()
        stepper = Stepper()
        verdicts = []
        with store.clock_driven_by(stepper):
            for _ in range(SPAN + 1):
                got = oooreturn.assess(rec, "acme-champ", config=self.config)
                verdicts.append((got["as_of"], got["verdict"]))
                stepper.advance()

        self.assertEqual(len(verdicts), SPAN + 1)
        self.assertEqual(verdicts[0], ("2026-09-02", oooreturn.NOT_YET))
        first_due = next(day for day, v in verdicts if v == oooreturn.DUE)
        self.assertEqual(first_due, RETURN_DATE)
        self.assertEqual({v for _, v in verdicts},
                         {oooreturn.NOT_YET, oooreturn.DUE})

    def test_with_no_injection_the_same_call_answers_from_the_real_clock(self):
        """The control for the case above. Today is not 2026-09-02."""
        got = oooreturn.assess(self.absence(), "acme-champ",
                               config=self.config)
        self.assertEqual(got["as_of"], store.now()[:10])
        self.assertNotEqual(got["as_of"], "2026-09-02")


class NinetyDaysMoveTheSchedulersAnswer(unittest.TestCase):
    """`senderheadroom.earliest_day` is the real scheduler: the first day a
    MAILBOX can take another row, which `docs/THE-SEND-DATE-IS-THE-MAILBOX`
    proved is what decides when a cohort goes out.

    It is fed `now=store.utcnow()` rather than reading the seam itself, and
    that is deliberate - see `TheSchedulerIsFedTheSeamDeliberately` below for
    the measurement behind it. The authority is still one: `utcnow()` and
    `now()` read the same `_CLOCK`.
    """

    ACTIVE = ("487",)
    SENDER, LIMIT = 2736, 15

    def earliest(self, state):
        return senderheadroom.earliest_day(
            state, self.SENDER, self.LIMIT, active_campaign_ids=self.ACTIVE,
            now=store.utcnow())

    def test_a_fresh_census_names_the_first_free_sending_day(self):
        """Ground truth. Thursday and Friday are full, so Monday is the day -
        exactly the 2736/327/328 pattern that made this module exist."""
        stepper = Stepper()
        state = census("2026-09-02T08:00:00+00:00",
                       {"2026-09-02": 15, "2026-09-03": 15, "2026-09-04": 15})
        with store.clock_driven_by(stepper):
            day, reason = self.earliest(state)
        self.assertEqual(day, "2026-09-07", reason)

    def test_the_answer_moves_when_the_census_moves_with_the_clock(self):
        """A simulation that re-walks the forward book each day.

        Day 0 answers Monday the 7th; day 90 answers the 1st of December,
        because by then nothing in the book is booked. The scheduler's answer
        moved 90 days because the clock did.
        """
        stepper = Stepper()
        booked = {"2026-09-02": 15, "2026-09-03": 15, "2026-09-04": 15}
        with store.clock_driven_by(stepper):
            first, _ = self.earliest(census(store.now(), booked))
            stepper.advance(SPAN)
            later, reason = self.earliest(census(store.now(), booked))

        self.assertEqual(first, "2026-09-07")
        self.assertEqual(later, "2026-12-01", reason)
        self.assertNotEqual(first, later)

    def test_a_census_that_does_not_move_goes_stale_and_the_scheduler_refuses(self):
        """A FINDING, asserted so it cannot be forgotten.

        `STALE_AFTER_HOURS` is 24, and the freshness gate is the LAST one, so
        a 90-day simulation that walks the forward book once gets ROOM for one
        simulated day and REFUSED for the remaining eighty-nine - with no
        error, because a mailbox with no provable room is an answer and not an
        exception. The simulation must re-walk the book every simulated day,
        or every send decision after day 1 is a refusal it never noticed.
        """
        stepper = Stepper()
        state = census("2026-09-02T08:00:00+00:00",
                       {"2026-09-02": 15, "2026-09-03": 15, "2026-09-04": 15})
        with store.clock_driven_by(stepper):
            fresh_day, _ = self.earliest(state)
            stepper.advance(SPAN)
            stale_day, reason = self.earliest(state)

        self.assertEqual(fresh_day, "2026-09-07")
        self.assertIsNone(stale_day)
        self.assertIn("prove FULL but not ROOM", reason)

    def test_full_is_still_provable_from_a_stale_walk(self):
        """The asymmetry the module is built on, under an injected clock: a
        walk can only undercount, so FULL survives staleness and ROOM does
        not. If this broke, the refusal above would be a bug rather than the
        safety contract."""
        stepper = Stepper()
        state = census("2026-09-02T08:00:00+00:00", {"2026-09-02": 15})
        with store.clock_driven_by(stepper):
            stepper.advance(SPAN)
            word, reason, free = senderheadroom.verdict(
                state, self.SENDER, "2026-09-02", self.LIMIT,
                active_campaign_ids=self.ACTIVE, now=store.utcnow())
        self.assertEqual(word, senderheadroom.FULL, reason)
        self.assertIsNone(free)


class TheSchedulerIsFedTheSeamDeliberately(unittest.TestCase):
    """The boundary of the seam, measured rather than assumed.

    `senderheadroom` imports no state module - not even `store` - and that is
    a property worth keeping: it is the pure primitive that answers WHEN a
    mailbox is free, and wiring the store into it to run a simulation would
    buy nothing the `now=` parameter does not already give. So the simulation
    passes `now=store.utcnow()`, and these two tests pin the consequence so a
    future change either keeps the contract or makes this fail loudly.
    """

    def test_senderheadroom_depends_on_no_state_module(self):
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(senderheadroom))
        relative = {node.module for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.level}
        self.assertEqual(
            relative, set(),
            "senderheadroom grew a dependency on a sibling module; if it now "
            "imports store, feed its clock from store.utcnow() by default and "
            "update test_the_scheduler_without_the_parameter_reads_the_wall_clock")

    def test_the_scheduler_without_the_parameter_reads_the_wall_clock(self):
        """Not a defect - the documented contract, held down.

        Omitting `now=` under an injected clock answers from TODAY. This is
        the one place on the phase-2 path where the simulation must pass the
        clock explicitly, and a simulation that forgot to would show a
        perfectly healthy scheduler answering about the real world.
        """
        state = census(store.now(), {})
        with store.clock_driven_by(Stepper()):
            day, reason = senderheadroom.earliest_day(
                state, 2736, 15, active_campaign_ids=("487",))
        self.assertIsNotNone(day, reason)
        self.assertGreater(day, "2026-09-02",
                           "the parameterless call answered from the injected "
                           "clock; the seam now reaches senderheadroom and "
                           "this test records the opposite")
        self.assertTrue(re.match(r"^\d{4}-\d{2}-\d{2}$", day))


if __name__ == "__main__":
    unittest.main()
