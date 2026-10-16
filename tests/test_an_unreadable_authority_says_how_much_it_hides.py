"""An UNREADABLE lane file yields no rows. How many is no longer invisible.

WHAT THIS FILE IS FOR. `LANE-webapp.md`, TASK-0270 section 6, filed two
absence shapes and fixed neither:

    The two absence shapes above - trap 13's open START, and the UNREADABLE
    lane file's missing rows - are **filed and not fixed**: each would change
    which dispatches get asked the landing question at all, which is wider
    than this brief.

The first became `0266` and landed as `src/laneopen.py`. The second was
re-confirmed open at 21:45 that night - *"still filed and still UNDONE AND
NOT RE-QUEUED"* - and TASK-0290 is the file that was written for it.

WHAT WAS WRONG, AND WHAT WAS ALREADY RIGHT. `lane_rework` was right to
return no rows: crossing a readable log against a missing LANE file is
UNKNOWN for every cell, and the panel already prints seven UNKNOWNs against
an amber row naming which authority is missing. What it could not say was
HOW MUCH. `starts` was None as well, the lane was skipped by the estate
total, and so the dispatches behind those seven cells were absent from every
figure on the panel at once - including from `blind_spots()`, whose whole job
is to carry what the panel cannot see. One unreadable lane can hold one
dispatch or forty, and a reader deciding whether to go and look could not
tell those apart.

THE SHAPE OF THE FIX IS `0266`'s, DELIBERATELY. It does not invent a landing
verdict for work it cannot judge: `starts_not_asked` is a count, it shares no
word with `landed`, `lost` or `not_determined`, and the lane's `rows` and
`landing_tally` stay empty. An instrument that answered the landing question
off a missing authority would be the defect this one exists to refuse.

AND IT IS UNKNOWN RATHER THAN ZERO ONE LAYER DOWN. Where the LOG cannot be
read either, the count itself cannot be taken, so it is None - and the
estate total then publishes a FLOOR and says so, instead of summing the
addends that happened to be readable.

NOTHING HERE READS THE REAL ESTATE. Every log and lane file below is a
string written into a temporary directory, and no commit is read: `commits`
is handed in as `{}`.
"""
import datetime
import os
import shutil
import tempfile
import unittest

from src import lanerework as lr
from src.web import api, pages

OFFSET = 2.0
ALPHA = "alpha"
BETA = "beta"
DAY = "2026-10-16"
NOW = datetime.datetime(2026, 10, 16, 9, 0, 0)


def line(lane, clock, message, day=DAY):
    return "[%s %s] [%s] %s" % (day, clock, lane, message)


def up(lane, clock="00:00:00"):
    return line(lane, clock, "watcher up. tree=C:\\somewhere "
                             "mode=bypassPermissions timeout=90m")


class Estate(object):
    """A temporary ops root. Nothing in it is read by anything but the test."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="rga-0290-unread-")
        os.makedirs(os.path.join(self.root, "logs"))
        os.makedirs(os.path.join(self.root, "queue"))

    def log(self, lane, lines):
        path = os.path.join(self.root, "logs", "watcher-%s.log" % lane)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\ufeff" + "\n".join(lines) + "\n")

    def lane_file(self, lane, text):
        path = os.path.join(self.root, "LANE-%s.md" % lane)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def lane_file_unreadable(self, lane):
        """A DIRECTORY where the lane file should be.

        `_read_text` answers UNREADABLE for any `OSError`, and this is the
        one shape a test can produce on Windows without changing an ACL. It
        is a different state from ABSENT and both reach the same branch.
        """
        os.makedirs(os.path.join(self.root, "LANE-%s.md" % lane))

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class Base(unittest.TestCase):

    #: Three STARTs among nine lines, with a DONE, two refusals, an idle and
    #: a `watcher down.` beside them. A count that answered 9, or 4, or 1
    #: would pass against a log made only of STARTs.
    THREE_STARTS = [
        "watcher up. tree=C:\\somewhere mode=bypassPermissions timeout=90m",
        "START 0010-a.md",
        "DONE  0010-a.md -> exit0",
        "START 0020-b.md",
        "a task is already in RUNNING: 0020-b.md, not starting another",
        "a task is already in RUNNING: 0020-b.md, not starting another",
        "idle: queue empty, RUNNING empty, still polling",
        "START 0030-c.md",
        "watcher down.",
    ]

    def setUp(self):
        self.estate = Estate()
        self.addCleanup(self.estate.close)

    def busy_log(self, lane=ALPHA):
        self.estate.log(lane, [line(lane, "0%d:00:00" % index, message)
                               for index, message
                               in enumerate(self.THREE_STARTS)])

    def read(self, lane=ALPHA):
        return lr.lane_rework(self.estate.root, lane, commits={},
                              offset_hours=OFFSET, known=(ALPHA, BETA))

    def estate_data(self, lanes_wanted):
        return api.lane_rework(root=self.estate.root, now=NOW, commits={},
                               branch_lanes={},
                               lanes_wanted=list(lanes_wanted))

    def spot(self, data):
        wanted = "dispatches nothing asked the landing question"
        found = [item for item in data["blind_spots"]
                 if item["name"] == wanted]
        self.assertEqual(len(found), 1,
                         [item["name"] for item in data["blind_spots"]])
        return found[0]


class TheCountIsTakenOffTheSurvivingAuthority(Base):

    def test_an_absent_lane_file_still_counts_its_dispatches(self):
        self.busy_log()
        row = self.read()
        self.assertEqual(row["state"], lr.UNREADABLE)
        self.assertEqual(row["lane_file_state"], "absent")
        self.assertEqual(row["starts_not_asked"], 3)

    def test_an_unreadable_lane_file_counts_them_too(self):
        """ABSENT and UNREADABLE are different facts with the same
        consequence here, and the branch must not answer only one."""
        self.busy_log()
        self.estate.lane_file_unreadable(ALPHA)
        row = self.read()
        self.assertEqual(row["lane_file_state"], "unreadable")
        self.assertEqual(row["starts_not_asked"], 3)

    def test_it_counts_starts_and_not_lines(self):
        """The fixture log holds nine records and three STARTs. A count of
        lines, of events, or of DONEs would be a different number."""
        self.busy_log()
        self.assertEqual(len(self.THREE_STARTS), 9)
        self.assertEqual(self.read()["starts_not_asked"], 3)

    def test_the_figure_moves_with_the_log(self):
        """One START, not three. A constant would satisfy every assertion
        above and this is the one it cannot satisfy."""
        self.estate.log(ALPHA, [up(ALPHA), line(ALPHA, "01:00:00",
                                                "START 0010-a.md")])
        self.assertEqual(self.read()["starts_not_asked"], 1)

    def test_an_unreadable_log_makes_the_count_unknown_not_zero(self):
        """No log at all. The count cannot be taken, so it is None - a zero
        here would be the same defect one layer down."""
        row = self.read()
        self.assertEqual(row["state"], lr.UNREADABLE)
        self.assertEqual(row["log_state"], "absent")
        self.assertIsNone(row["starts_not_asked"])


class NoVerdictIsInventedForWorkNothingCanJudge(Base):
    """`0266`'s discipline, applied to the second absence shape.

    The count makes the SIZE of the silence visible. It must not make the
    silence look like an answer.
    """

    def test_the_lane_still_returns_no_rows_and_no_landing_tally(self):
        self.busy_log()
        row = self.read()
        self.assertEqual(row["rows"], [])
        self.assertEqual(row["landing_tally"], {})
        self.assertEqual(row["tally"], {})

    def test_starts_itself_stays_unknown_so_the_estate_total_is_honest(self):
        """`starts` is what the estate's denominator sums. These dispatches
        were NOT measured, so they must not join it - which is why the count
        is a separate figure rather than a value for `starts`."""
        self.busy_log()
        self.assertIsNone(self.read()["starts"])

    def test_the_count_shares_no_word_with_a_landing_verdict(self):
        """A reader who sees this number must not be able to mistake it for
        an answer about whether the work landed.

        `0266` kept `laneopen`'s vocabulary disjoint from this module's for
        the same reason, and said so in its own docstring. Here the test is
        on the VALUES the unreadable lane publishes: an integer and three
        empty containers, and not one of `landed`, `not_determined` or
        `lost` anywhere among them.
        """
        self.busy_log()
        row = self.read()
        self.assertIsInstance(row["starts_not_asked"], int)
        published = repr({key: value for key, value in row.items()
                          if key != "lane_file_mtime"})
        for verdict in lr.LANDING_ORDER:
            self.assertNotIn(verdict, published)
        # The panel's own entry is a SIZE with a denominator and carries no
        # verdict field at all. Its note does contain the word "landed" -
        # in the sentence naming the question nothing asked - and that is
        # prose rather than a token, which is why this asserts on the
        # structure instead of searching the English.
        spot = self.spot(self.estate_data([ALPHA]))
        self.assertEqual(sorted(spot), ["denominator", "name", "note",
                                        "size"])
        self.assertIsInstance(spot["size"], int)

    def test_an_empty_lane_file_is_an_authority_answering_and_is_not_here(
            self):
        """An EMPTY lane file EXISTS and holds nothing, which is an answer:
        its STARTs are NO_ENTRY rows and they ARE asked the question. The
        new figure must not fire there, or it would be counting measured
        work as unmeasured."""
        self.busy_log()
        self.estate.lane_file(ALPHA, "")
        row = self.read()
        self.assertEqual(row["state"], "present")
        self.assertEqual(row["starts"], 3)
        self.assertIsNone(row["starts_not_asked"])
        self.assertEqual(len(row["rows"]), 3)


class TheEstateTotalPublishesItOrSaysItIsAFloor(Base):

    def readable_lane(self, lane=BETA):
        """One lane with both authorities, so the estate has a numerator."""
        self.estate.log(lane, [up(lane),
                               line(lane, "01:00:00", "START 0010-a.md"),
                               line(lane, "02:00:00",
                                    "DONE  0010-a.md -> exit0")])
        self.estate.lane_file(
            lane, "## 2026-10-16 03:00 — TASK 0010 — the first run\n\nbody\n")

    def test_the_total_carries_the_dispatches_it_could_not_judge(self):
        self.busy_log()
        self.readable_lane()
        data = self.estate_data([ALPHA, BETA])
        self.assertEqual(data["starts"], 1)
        self.assertEqual(data["lanes_unknown"], 1)
        self.assertEqual(data["starts_not_asked"], 3)
        self.assertEqual(data["starts_not_asked_unknown"], 0)

    def test_the_blind_spot_prints_the_number_and_its_denominator(self):
        self.busy_log()
        self.readable_lane()
        spot = self.spot(self.estate_data([ALPHA, BETA]))
        self.assertEqual(spot["size"], 3)
        self.assertEqual(spot["denominator"],
                         "4 START line(s) this estate could read")

    def test_an_unreadable_log_makes_the_blind_spot_unknown_with_a_floor(
            self):
        """`alpha` holds three unasked dispatches and `beta` holds an
        unknown number. The sum of the readable half is a FLOOR, not a
        total, and the size becomes UNKNOWN rather than 3."""
        self.busy_log()
        data = self.estate_data([ALPHA, BETA])
        self.assertEqual(data["starts_not_asked"], 3)
        self.assertEqual(data["starts_not_asked_unknown"], 1)
        spot = self.spot(data)
        self.assertIsNone(spot["size"])
        self.assertIn("the known floor is 3", spot["note"])

    def test_nothing_unreadable_leaves_the_figure_at_zero(self):
        """Zero and no-data do not render the same, and this is the ZERO
        case: every lane was read, so no dispatch went unasked."""
        self.readable_lane()
        data = self.estate_data([BETA])
        self.assertEqual(data["starts_not_asked"], 0)
        self.assertEqual(data["starts_not_asked_unknown"], 0)
        spot = self.spot(data)
        self.assertEqual(spot["size"], 0)
        self.assertNotIn("floor", spot["note"])


class ThePanelPrintsBothStates(Base):
    """BOTH directions on the page, because a cell nobody renders is a cell
    nobody reads - and a check that cannot fail reports clean forever."""

    def html(self, lanes_wanted):
        return pages.lane_rework(self.estate_data(lanes_wanted))

    def test_the_row_says_how_many_dispatches_it_is_hiding(self):
        self.busy_log()
        html = self.html([ALPHA])
        self.assertIn("3 dispatch(es) sit in the readable log and NOT ONE "
                      "of them was asked whether its work landed", html)

    def test_the_row_says_unknown_when_the_log_is_unreadable_too(self):
        html = self.html([ALPHA])
        self.assertIn("How many dispatches that hides is UNKNOWN too",
                      html)
        self.assertNotIn("dispatch(es) sit in the readable log", html)

    def test_a_readable_lane_carries_neither_sentence(self):
        """The control. A sentence on every row would prove nothing about
        the unreadable ones."""
        self.estate.log(BETA, [up(BETA),
                               line(BETA, "01:00:00", "START 0010-a.md")])
        self.estate.lane_file(
            BETA, "## 2026-10-16 03:00 — TASK 0010 — the first run\n\nbody\n")
        html = self.html([BETA])
        self.assertNotIn("dispatch(es) sit in the readable log", html)
        self.assertNotIn("How many dispatches that hides is UNKNOWN", html)

    def test_the_seven_unknown_cells_are_still_there(self):
        """The count does not replace the UNKNOWNs. It sizes them."""
        self.busy_log()
        html = self.html([ALPHA])
        self.assertIn('<tr class="warn">', html)
        self.assertEqual(html.count('<td class="absent">UNKNOWN</td>'), 7)

    def test_the_blind_spot_list_carries_it_to_a_reader(self):
        self.busy_log()
        html = self.html([ALPHA])
        self.assertIn("dispatches nothing asked the landing question", html)
        self.assertIn("START line(s) this estate could read", html)


if __name__ == "__main__":
    unittest.main()
