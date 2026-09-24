"""The Monday dry run's findings. The schedule itself is tested elsewhere.

`test_the_monday_report_can_be_stopped.py` already covers the decision: the
hour, the window, the stop, the refusal to post an unpreviewed document.
That machinery was sound when it was walked on 2026-09-24 for Monday
2026-09-28.

These are the three things the dry run found that nothing was watching:

  1. **The loop was in no supervision table.** It would have fired for the
     first time on 2026-09-28 only if somebody started it by hand, and a
     reboot would have removed it again.
  2. **The PDF's cover was dated by the BUILD, not by the Monday.** The
     filename used `monday`; the cover used `report["read_at"]`.
  3. **Nothing checked the client document against the client backstop.**
     It is the one artefact here that goes to a client unmediated.
"""
import importlib.util
import os
import re
import unittest
import zlib

from src import slackscope
from src import weeklyreportpdf
from src import weeklyreportwatch as watch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STREAM = re.compile(rb"stream\r?\n(.*?)endstream", re.S)
SHOWN = re.compile(rb"\(((?:\\.|[^()\\])*)\)", re.S)


def pdf_text(raw):
    """The VISIBLE text of a PDF, decompressed.

    A byte search against a Flate-compressed PDF is the unfalsifiable check
    this repository already has on its lesson list: `assertNotIn(b"name")`
    passes because the bytes are deflated, not because the name is absent.
    So the streams are inflated first and the text operators read out.
    """
    chunks = []
    for match in STREAM.finditer(raw):
        blob = match.group(1)
        try:
            blob = zlib.decompress(blob)
        except Exception:                                       # noqa: BLE001
            pass
        chunks.append(blob)
    joined = b"\n".join(chunks)
    return b" ".join(m.group(1) for m in SHOWN.finditer(joined)).decode(
        "latin-1")


def loop():
    spec = importlib.util.spec_from_file_location(
        "weekly_report_loop",
        os.path.join(ROOT, "scripts", "weekly_report_loop.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def monitors():
    spec = importlib.util.spec_from_file_location(
        "start_monitors", os.path.join(ROOT, "scripts", "start_monitors.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: `weekly_report`'s shape, small but real - `build` refuses anything
#: without `accounts`, which is the contract worth keeping.
REPORT = {
    "workspace": "alpha",
    "read_at": "2026-09-24T13:56:00Z",
    "accounts": {"untouched": 0, "sequenced": 1, "engaged": 0,
                 "replied": 13, "meeting": 0, "won": 0, "lost": 0,
                 "do_not_contact": 7, "unanswerable": 1522},
}


class TestTheLoopIsSupervised(unittest.TestCase):
    """It would have fired for the first time on a Monday nobody started."""

    def test_it_is_in_the_monitors_table(self):
        table = dict(monitors().MONITORS)
        self.assertIn(
            "weekly-report", table,
            "the Monday report loop is in no supervision table, so it is "
            "not started on boot, not restarted, and never reported by "
            "--status. That is how `digest_loop` and `slack_followup_loop` "
            "were both found not running.")
        argv = table["weekly-report"]
        self.assertIn("scripts/weekly_report_loop.py", argv)

    def test_its_interval_lands_inside_the_stop_window(self):
        """The preview is due at 07:30 and the post at 08:00, and `decide`
        REFUSES to post if the preview never ran. An interval longer than
        the window can skip straight past 07:30 into a refusal."""
        argv = dict(monitors().MONITORS)["weekly-report"]
        interval = int(argv[argv.index("--interval") + 1])
        window = ((watch.POST_HOUR * 60 + watch.POST_MINUTE)
                  - (watch.PREVIEW_HOUR * 60 + watch.PREVIEW_MINUTE)) * 60
        self.assertLess(
            interval, window,
            "a %ds interval against a %ds window can tick before 07:30 and "
            "again after 08:00, and the report then refuses to post - "
            "correctly, and for a reason nobody intended."
            % (interval, window))


class TestThePdfIsDatedByItsMonday(unittest.TestCase):
    """The filename used `monday`; the cover used the build time."""

    def test_the_period_names_the_monday_not_the_build_day(self):
        raw = weeklyreportpdf.build(
            REPORT, "Alpha",
            meta={"period": "The week to 2026-09-28"})
        body = pdf_text(raw)
        self.assertIn("The week to 2026-09-28", body)
        self.assertNotIn(
            "The week to 2026-09-24", body,
            "the cover is dated by when the PDF was built. On a Monday "
            "that ticks on time the two agree and nothing shows; on a "
            "retried or late Monday the client gets the wrong week.")

    def test_the_default_still_falls_back_to_the_build_time(self):
        """THE CONTROL. If `build` ignored `meta` the test above would pass
        for the wrong reason - so this proves the default is different."""
        body = pdf_text(weeklyreportpdf.build(REPORT, "Alpha"))
        self.assertIn("The week to 2026-09-24", body)

    def test_the_loop_passes_the_monday_through(self):
        """BEHAVIOUR, not a grep: build the real thing and read the cover."""
        module = loop()
        target = os.path.join(module.REPORT_DIR, "weekly-alpha-2026-09-28.pdf")
        self.addCleanup(lambda: os.path.exists(target) and os.remove(target))
        path, size = module._write_pdf("alpha", "Alpha", REPORT, "2026-09-28")
        self.assertGreater(size, 0)
        with open(path, "rb") as handle:
            body = pdf_text(handle.read())
        self.assertIn("The week to 2026-09-28", body)
        self.assertIn("weekly:alpha:2026-09-28", body,
                      "the document does not say which report it is, and a "
                      "person is going to attach it by hand")


class TestTheClientDocumentPassesTheClientBackstop(unittest.TestCase):
    """The one artefact here that reaches a client unmediated."""

    def scope(self):
        return slackscope.Scope(slackscope.CLIENT, workspace="alpha",
                                source="test")

    def test_nothing_in_it_may_not_reach_the_client(self):
        body = pdf_text(weeklyreportpdf.build(REPORT, "Alpha"))
        self.scope().check_outbound(body)

    def test_the_control_the_same_check_refuses_a_planted_term(self):
        """Without this, the test above passes on an empty extraction."""
        body = pdf_text(weeklyreportpdf.build(REPORT, "Alpha"))
        self.assertGreater(len(body), 500,
                           "almost no text came out of the PDF, so the "
                           "check above inspected nothing")
        with self.assertRaises(Exception):
            self.scope().check_outbound(body + " Qwen is reviewing this.")


class TestTheUnplaceableAccountsAreNotReadAsUntouched(unittest.TestCase):
    """The ledger write-back is production's and still missing, so the
    report DEGRADES. What it must never do is quietly call 1,522 accounts
    untouched."""

    def test_the_figure_is_named_and_caveated(self):
        body = pdf_text(weeklyreportpdf.build(REPORT, "Alpha"))
        self.assertIn("1,522", body)
        self.assertIn("NOT a count of untouched accounts", body)

    def test_untouched_is_still_reported_as_its_own_zero(self):
        body = pdf_text(weeklyreportpdf.build(REPORT, "Alpha"))
        self.assertIn("Untouched", body)


if __name__ == "__main__":
    unittest.main()
