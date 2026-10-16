"""The go/no-go page, and the one sentence it may never print.

WHAT THIS FILE IS FOR. TASK 0230 asked for one screen answering one question
on the morning of a first live send: can CANARY-01 send right now, and if not
what is the shortest list. Section 4 of that brief names the rule this file is
titled after - **it must be impossible for this page to render GO while any
row is UNKNOWN** - and asks for it to be pinned by name. That is
`TheSentenceThisPageMayNeverPrint` below, asserted on the guard itself and
again through the whole render.

THE INVARIANT IS DIRECTIONAL, as it is on the criteria page. A screen that
says NO-GO when the answer is GO costs the operator an afternoon. A screen
that says GO when a row is unknown sends mail to real people. So every test
that matters here asserts the second thing cannot happen:

    an absent source renders UNKNOWN and NO-GO, never GO;
    a source present and unparseable does the same, with the reason shown;
    `NOT MET` is never read as `MET` - the substring is inside the phrase;
    `NOT ANSWERABLE FROM HERE` is UNKNOWN, not MET and not dropped;
    a reading older than the threshold is STALE and STALE is not a pass;
    a reading with no establishable date is stale too, never its own words;
    two documents answering one question differently is UNKNOWN;
    a source that fails still produces its ROW, carrying UNKNOWN;
    a failed self-control poisons every row on the page.

AND THE CONTROL THAT STOPS ALL OF THAT BEING FREE. A page hard-wired to
NO-GO satisfies every line above and is worthless - and NO-GO is the answer
this page gives every real day, so no amount of looking at it would tell. So
`TheReaderIsNotBlind` requires a fixture in which every blocker is cleared to
render GO, and that same requirement runs as the page's own third control on
every render.

NOTHING HERE REACHES A PROVIDER, A NETWORK, A REAL LANE OR THE REAL OPS
ESTATE. Every document in this file is written into a temporary directory or
handed straight to a reader. One test patches `socket.socket` to raise and
then renders the page, so "it opens no socket" is a measurement rather than a
claim; another patches `open` for writing, so "it writes nothing" is too.
"""
import builtins
import datetime
import os
import shutil
import socket
import tempfile
import unittest

from src import gonogo, lanes
from src.web import api, pages
from src.web.app import permission_for
from tests.webbase import WebTest

PATH = "/admin/go-no-go"
SUPER = "root@resonate.test"
ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"

NOW = datetime.datetime(2026, 10, 16, 11, 0, 0)

#: A clock inside the staleness threshold, and one outside it. Derived from
#: `STALE_SECONDS` rather than typed, so a change to the threshold moves both
#: fixtures with it instead of silently making one of these tests vacuous.
FRESH = NOW - datetime.timedelta(seconds=gonogo.STALE_SECONDS // 2)
OLD = NOW - datetime.timedelta(seconds=gonogo.STALE_SECONDS + 600)


def stamp(when):
    return when.strftime("%Y-%m-%d %H:%M:%S")


def runbook(headline="NO", items=(), owners="", preconditions=(),
            when=None, extra=""):
    """A document in `CANARY-01-RUNBOOK-2026-10-16.md`'s own shape.

    Written out here rather than imported from the real file, so that a change
    to the runbook's layout shows up as a failure in this file instead of as a
    page that reads everything UNKNOWN and merely looks cautious.
    """
    when = when or FRESH
    lines = ["# CANARY-01 - GO / NO-GO RUNBOOK", "",
             "# %s. CANARY-01 %s SEND TODAY, %s."
             % (headline, "CANNOT" if headline == "NO" else "CAN",
                when.strftime("%Y-%m-%d")),
             ""]
    if items:
        lines.append("The shortest list of things that would change that, "
                     "each measured below:")
        lines.append("")
        for number, text in enumerate(items, start=1):
            lines.append("%d. %s" % (number, text))
        lines.append("")
    else:
        lines.append("The shortest list of things that would change that is "
                     "empty.")
        lines.append("")
    if owners:
        lines.extend([owners, ""])
    lines.extend([
        "    batch clock   local %s +0200" % stamp(when),
        "    origin/master  b1f290c84  verified",
        "",
        "## 2. PRECONDITIONS",
        "",
    ])
    for number, statement, verdict in preconditions:
        lines.append("    P%-3d %-50s %s" % (number, statement, verdict))
    lines.append("")
    for number, statement, verdict in preconditions:
        lines.extend(["### P%d - %s. **%s.**" % (number, statement, verdict),
                      "",
                      "    $ a command that verified P%d" % number,
                      "    some output",
                      ""])
    if extra:
        lines.extend([extra, ""])
    return "\n".join(lines) + "\n"


CLEARED_PRE = ((1, "the brake is in the sending tree", "MET"),
               (2, "the write door covers every send path", "MET"))


def preflight(assessed=23, cleared=0, excluded=0, not_cleared=23, when=None):
    when = when or FRESH
    return """# CANARY-01 preflight - %(day)s

**CANARY-01 IS NOT CLEARED TO SEND.**

    contacts assessed             %(assessed)d
    cleared                       %(cleared)d
    excluded                      %(excluded)d
    NOT CLEARED because UNKNOWN   %(not_cleared)d   <- the one that matters

Measured %(clock)s in `wt-fixture`, at SHA `0000000000`.
""" % {"day": when.strftime("%Y-%m-%d"), "clock": stamp(when),
       "assessed": assessed, "cleared": cleared, "excluded": excluded,
       "not_cleared": not_cleared}


def exit_criteria(verdicts=None, when=None):
    """Nine rows in the shape `src.exitcriteria`'s own parser reads."""
    when = when or FRESH
    verdicts = verdicts or {}
    rows = "\n".join(
        "    %d  a criterion     %s" % (number, verdicts.get(number, "MET"))
        for number in range(1, 10))
    return """# CANARY-01 - EXIT CRITERIA - %(day)s

Measured %(clock)s.

## 0. THE TABLE

%(rows)s
""" % {"day": when.strftime("%Y-%m-%d"), "clock": stamp(when), "rows": rows}


def decisions(tier2=(), tier3=("### 7. A decision that is not the canary's",),
              when=None, lane_sentence=True):
    when = when or FRESH
    lines = ["# DECISIONS OPEN - %s local (fixture)" % stamp(when), "",
             "## TIER 2 - the canary's own four blockers", ""]
    if lane_sentence:
        lines.extend(["**None of these can be closed by a lane.**", ""])
    for item in tier2:
        lines.extend([item, ""])
    lines.extend(["## TIER 3 - sentences only the operator can say", ""])
    for item in tier3:
        lines.extend([item, ""])
    return "\n".join(lines) + "\n"


class AnEstate:
    """A temporary ops estate, thrown away per test."""

    def setUp(self):
        super().setUp()
        self.ops = tempfile.mkdtemp(prefix="rga-gonogo-ops-")
        self.addCleanup(shutil.rmtree, self.ops, ignore_errors=True)
        previous = os.environ.get(lanes.OPS_DIR)
        os.environ[lanes.OPS_DIR] = self.ops
        self.addCleanup(self._restore, previous)

    @staticmethod
    def _restore(previous):
        if previous is None:
            os.environ.pop(lanes.OPS_DIR, None)
        else:
            os.environ[lanes.OPS_DIR] = previous

    def write(self, name, text, mtime=None):
        path = os.path.join(self.ops, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        if mtime is not None:
            stamped = mtime.timestamp()
            os.utime(path, (stamped, stamped))
        return path

    def cleared_estate(self, **kwargs):
        """All four documents, every blocker cleared."""
        self.write(gonogo.RUNBOOK,
                   runbook(headline="YES", preconditions=CLEARED_PRE,
                           **kwargs))
        self.write(gonogo.PREFLIGHT,
                   preflight(assessed=10, cleared=10, not_cleared=0, **kwargs))
        self.write(gonogo.EXIT_CRITERIA, exit_criteria(**kwargs))
        self.write(gonogo.DECISIONS, decisions(**kwargs))

    def report(self, now=None):
        return gonogo.report(now=now or NOW)

    def rows(self, now=None):
        return {row["key"]: row for row in self.report(now)["rows"]}

    def page(self, now=None):
        """The rendered HTML, through the service layer the handler uses.

        `api.go_no_go` is what the route calls and it adds the page's own
        headline and its provenance table, so rendering `gonogo.report`
        directly would be testing a payload no handler produces.
        """
        return pages.go_no_go(api.go_no_go(now=now or NOW))


# --------------------------------------------------------------------------
# The reader is not blind. Without this class every assertion in this file is
# satisfied by a page that returns NO-GO and UNKNOWN unconditionally - which
# is this lane's own B7 defect, an instrument reporting clean because it
# watched nothing, and NO-GO is what this page says on every real day.
# --------------------------------------------------------------------------

class TheReaderIsNotBlind(AnEstate, unittest.TestCase):

    def test_a_fully_cleared_estate_renders_go(self):
        """The one that stops every refusal in this file being free."""
        self.cleared_estate()
        data = self.report()
        self.assertEqual(data["verdict"], gonogo.GO,
                         "%s - %s" % (data["verdict_label"],
                                      data["verdict_why"]))
        self.assertEqual([row["key"] for row in data["blockers"]], [])
        self.assertEqual(data["shortest"], [])

    def test_a_planted_met_precondition_comes_back_met(self):
        self.cleared_estate()
        rows = self.rows()
        self.assertEqual(rows["P1"]["verdict"], gonogo.MET)
        self.assertEqual(rows["P2"]["verdict"], gonogo.MET)

    def test_a_planted_not_met_precondition_comes_back_not_met(self):
        self.write(gonogo.RUNBOOK, runbook(preconditions=(
            (1, "the brake is in the sending tree", "NOT MET"),)))
        self.cleared_estate_rest()
        rows = self.rows()
        self.assertEqual(rows["P1"]["verdict"], gonogo.NOT_MET)

    def cleared_estate_rest(self):
        """Everything except the runbook, cleared."""
        self.write(gonogo.PREFLIGHT,
                   preflight(assessed=10, cleared=10, not_cleared=0))
        self.write(gonogo.EXIT_CRITERIA, exit_criteria())
        self.write(gonogo.DECISIONS, decisions())

    def test_a_cleared_cohort_comes_back_met(self):
        self.cleared_estate()
        self.assertEqual(self.rows()["preflight:cohort"]["verdict"],
                         gonogo.MET)

    def test_every_control_passes(self):
        """Three, and the COUNT is asserted rather than dropped.

        A control silently disappearing is this page losing the thing that
        licenses it to report anything at all.
        """
        checks = gonogo.controls(now=NOW)
        self.assertEqual(len(checks), 3)
        for check in checks:
            self.assertTrue(check["ok"],
                            "%s FAILED: %s" % (check["name"],
                                               check["detail"]))

    def test_the_go_control_would_notice_a_page_wired_to_no_go(self):
        """The control has teeth, proven by breaking the thing it watches.

        `verdict_of` is replaced with one that always says NO-GO - which is
        what a hard-wired page looks like - and the third control is required
        to go FAIL. Without this the control could be passing for a reason
        that has nothing to do with GO being reachable.
        """
        original = gonogo.verdict_of
        gonogo.verdict_of = lambda *a, **k: (gonogo.NO_GO, "wired shut")
        try:
            checks = {check["name"]: check for check in
                      gonogo.controls(now=NOW)}
        finally:
            gonogo.verdict_of = original
        self.assertFalse(checks["a fully cleared fixture renders GO"]["ok"])

    def test_a_failed_control_is_reported_and_poisons_every_row(self):
        self.cleared_estate()
        original = gonogo.controls
        gonogo.controls = lambda now=None: [
            {"name": "a control that failed", "ok": False, "detail": "broken"}]
        try:
            data = self.report()
        finally:
            gonogo.controls = original
        self.assertEqual(data["verdict"], gonogo.NO_GO)
        self.assertFalse(data["controls_ok"])
        self.assertEqual(data["controls_failed"], ["a control that failed"])
        for row in data["rows"]:
            self.assertEqual(row["verdict"], gonogo.UNKNOWN, row["key"])
            self.assertIn("control", row["reason"])
        # AND THE RECORDED VERDICT IS STILL SHOWN. What is untrusted is this
        # page's reader, not the document - a poisoned row that forgot what
        # the artifact said would turn a precise statement into a shrug.
        self.assertEqual(data["rows"][0]["recorded_label"], "MET")


# --------------------------------------------------------------------------
# THE RULE THIS FILE IS NAMED AFTER. Section 4 of TASK 0230.
# --------------------------------------------------------------------------

class TheSentenceThisPageMayNeverPrint(AnEstate, unittest.TestCase):
    """GO is impossible while any row is UNKNOWN.

    Asserted twice and deliberately. Once on `verdict_of` directly, which is
    the single guard - so this test observes THAT guard firing rather than
    some other check answering first and leaving the rule looking enforced
    when it is not. Once through the whole render with a real document on
    disk, because a guard nothing calls is not a guard.
    """

    @staticmethod
    def row(verdict, key="r"):
        return {"key": key, "verdict": verdict,
                "verdict_label": gonogo.VERDICT_TEXT[verdict][0],
                "owner": gonogo.OWNER_UNSTATED, "owner_label": "not stated",
                "shortest_rank": None, "source_name": "x", "question": "q"}

    def test_one_unknown_row_among_many_met_rows_is_not_go(self):
        rows = [self.row(gonogo.MET, "a"), self.row(gonogo.MET, "b"),
                self.row(gonogo.UNKNOWN, "c")]
        verdict, why = gonogo.verdict_of(rows)
        self.assertEqual(verdict, gonogo.NO_GO)
        self.assertIn("UNKNOWN", why)

    def test_the_guard_is_the_one_that_fires(self):
        """Not a second check answering first.

        Every other refusal in `verdict_of` is given nothing to object to:
        the controls pass, the source set is complete, and the only
        non-MET row is the UNKNOWN one. If the verdict is still NO-GO, the
        UNKNOWN branch is what produced it, and the reason text names the
        count it saw.
        """
        rows = [self.row(gonogo.MET, "a"), self.row(gonogo.UNKNOWN, "b")]
        verdict, why = gonogo.verdict_of(rows, sources_ok=True,
                                         controls_ok=True)
        self.assertEqual(verdict, gonogo.NO_GO)
        self.assertIn("1 of 2 rows is UNKNOWN", why)
        self.assertNotIn("STALE", why)
        self.assertNotIn("control", why)

    def test_no_arrangement_of_rows_with_an_unknown_can_be_go(self):
        """Every mixture, exhaustively, as long as one row is UNKNOWN."""
        others = (gonogo.MET, gonogo.NOT_MET, gonogo.WITHDRAWN, gonogo.STALE)
        for first in others:
            for second in others:
                rows = [self.row(first, "a"), self.row(second, "b"),
                        self.row(gonogo.UNKNOWN, "c")]
                verdict, _ = gonogo.verdict_of(rows)
                self.assertEqual(verdict, gonogo.NO_GO,
                                 "%s + %s + UNKNOWN" % (first, second))

    def test_the_whole_render_cannot_say_go_with_an_unknown_row(self):
        """Through the real path, with one row made UNKNOWN on purpose.

        Everything else on this estate is cleared, so the render is one row
        away from GO - which is the state in which a page that rounded
        UNKNOWN up would actually be believed.
        """
        self.cleared_estate()
        self.write(gonogo.RUNBOOK, runbook(
            headline="YES",
            preconditions=((1, "the brake is in the sending tree", "MET"),
                           (2, "sending.live off for productive",
                            "NOT ANSWERABLE FROM HERE"))))
        data = self.report()
        self.assertEqual(self.rows()["P2"]["verdict"], gonogo.UNKNOWN)
        self.assertEqual(data["verdict"], gonogo.NO_GO)
        # THE BANNER ITSELF, not a substring search. "GO" appears in the
        # control panel's own name - `a fully cleared fixture renders GO` -
        # so a bare `assertNotIn("GO")` would pass or fail for reasons that
        # have nothing to do with the verdict this page printed.
        html = self.page()
        self.assertIn('<span class="tag block">NO-GO</span>', html)
        self.assertNotIn('<span class="tag pass">GO</span>', html)

    def test_the_rendered_page_shows_no_go_and_not_a_fraction(self):
        self.cleared_estate()
        self.write(gonogo.EXIT_CRITERIA, exit_criteria({3: "NOT MET"}))
        data = self.report()
        html = self.page()
        self.assertIn("NO-GO", html)
        self.assertIn("Can this send right now?", html)
        # Not "4 of 5 rows resolved". The page may count its buckets; it may
        # not present them as progress towards a pass.
        self.assertNotIn(" of 5 resolved", html)


# --------------------------------------------------------------------------
# Fail-closed reading.
# --------------------------------------------------------------------------

class AnUnreadableSourceIsNeverAPass(AnEstate, unittest.TestCase):

    def test_an_absent_source_renders_its_question_unknown(self):
        self.cleared_estate()
        os.remove(os.path.join(self.ops, gonogo.RUNBOOK))
        data = self.report()
        rows = {row["key"]: row for row in data["rows"]}
        self.assertIn("source:runbook", rows)
        self.assertEqual(rows["source:runbook"]["verdict"], gonogo.UNKNOWN)
        self.assertEqual(data["verdict"], gonogo.NO_GO)
        self.assertIn(gonogo.RUNBOOK, data["unread"])

    def test_an_absent_source_names_the_path_it_tried(self):
        """A reader told "the authority could not be read" and not told
        where it looked has been given a worry rather than an instruction."""
        self.cleared_estate()
        os.remove(os.path.join(self.ops, gonogo.PREFLIGHT))
        source = [s for s in self.report()["sources"]
                  if s["key"] == "preflight"][0]
        self.assertEqual(source["state"], gonogo.ABSENT)
        self.assertTrue(source["attempted_path"])
        self.assertIn(gonogo.PREFLIGHT, source["attempted_path"])

    def test_a_source_present_and_unparseable_renders_unknown_with_a_reason(
            self):
        self.cleared_estate()
        self.write(gonogo.RUNBOOK, gonogo.UNPARSEABLE_RUNBOOK)
        data = self.report()
        rows = {row["key"]: row for row in data["rows"]}
        self.assertEqual(rows["source:runbook"]["verdict"], gonogo.UNKNOWN)
        self.assertEqual(data["verdict"], gonogo.NO_GO)
        source = [s for s in data["sources"] if s["key"] == "runbook"][0]
        self.assertEqual(source["state"], gonogo.NO_BLOCK)
        self.assertTrue(source["reason"])
        self.assertIn("precondition", source["reason"])

    def test_an_empty_source_is_its_own_state(self):
        self.cleared_estate()
        self.write(gonogo.RUNBOOK, "")
        source = [s for s in self.report()["sources"]
                  if s["key"] == "runbook"][0]
        self.assertEqual(source["state"], gonogo.EMPTY)

    def test_a_directory_where_a_document_belongs_is_unreadable(self):
        """Neither absent nor empty, and nobody's planned state."""
        self.cleared_estate()
        os.remove(os.path.join(self.ops, gonogo.DECISIONS))
        os.makedirs(os.path.join(self.ops, gonogo.DECISIONS))
        source = [s for s in self.report()["sources"]
                  if s["key"] == "decisions"][0]
        self.assertEqual(source["state"], gonogo.UNREADABLE)
        self.assertEqual(self.report()["verdict"], gonogo.NO_GO)

    def test_an_unconfigured_estate_is_not_a_clear_board(self):
        os.environ.pop(lanes.OPS_DIR, None)
        data = self.report()
        self.assertEqual(data["ops_state"], gonogo.UNCONFIGURED)
        self.assertEqual(data["verdict"], gonogo.NO_GO)
        self.assertEqual(len(data["rows"]), len(gonogo.SOURCES))
        for row in data["rows"]:
            self.assertEqual(row["verdict"], gonogo.UNKNOWN)

    def test_every_source_that_fails_still_produces_exactly_one_row(self):
        """The silent-shrink defect, asserted by count.

        A go/no-go screen that answers four questions today and three
        tomorrow, with nothing saying which one went, is worse than one that
        answers none.
        """
        os.environ[lanes.OPS_DIR] = self.ops          # empty directory
        data = self.report()
        keys = [row["key"] for row in data["rows"]]
        for source in gonogo.SOURCES:
            self.assertIn("source:" + source["key"], keys)


class TheVerdictPhrasesFailClosed(unittest.TestCase):

    def test_not_met_is_not_read_as_met(self):
        """The substring is inside the phrase. One regex ordering away."""
        self.assertEqual(gonogo.verdict_phrase("NOT MET")[0], gonogo.NOT_MET)
        self.assertEqual(gonogo.verdict_phrase("NOT MET  (narrowed)")[0],
                         gonogo.NOT_MET)

    def test_met_is_read_as_met(self):
        self.assertEqual(gonogo.verdict_phrase("MET")[0], gonogo.MET)
        self.assertEqual(gonogo.verdict_phrase("MET. NEW.")[0], gonogo.MET)

    def test_a_phrase_this_reader_does_not_know_is_unknown(self):
        for phrase in ("NOT ANSWERABLE FROM HERE",
                       "CANNOT BE ANSWERED FROM HERE",
                       "MET-WITH-CAVEAT", "PROBABLY FINE", "CLOSED"):
            verdict, raw = gonogo.verdict_phrase(phrase)
            self.assertEqual(verdict, gonogo.UNKNOWN, phrase)
            # AND THE WORDS ARE KEPT. `CANNOT BE ANSWERED FROM HERE` is a
            # real verdict in the runbook and dropping it would leave the row
            # looking unmeasured rather than unanswerable.
            self.assertEqual(raw, phrase)

    def test_an_empty_phrase_is_unknown_with_nothing_kept(self):
        self.assertEqual(gonogo.verdict_phrase(""), (gonogo.UNKNOWN, None))
        self.assertEqual(gonogo.verdict_phrase(None), (gonogo.UNKNOWN, None))

    def test_a_precondition_row_with_no_verdict_column_is_unknown(self):
        rows = {row["number"]: row for row in gonogo.read_runbook(
            runbook(preconditions=())
            + "\n## 2. PRECONDITIONS\n\n    P4\n")["rows"]}
        self.assertEqual(rows[4]["verdict"], gonogo.UNKNOWN)


class TwoReadingsOfOneDocument(AnEstate, unittest.TestCase):
    """The runbook states every precondition twice. They are compared."""

    def test_a_table_and_a_heading_that_disagree_render_unknown(self):
        text = runbook(preconditions=((1, "the brake is in the tree",
                                       "MET"),))
        # The heading alone is rewritten, which is exactly the shape of a
        # document somebody updated in one place.
        text = text.replace("### P1 - the brake is in the tree. **MET.**",
                            "### P1 - the brake is in the tree. "
                            "**NOT MET.**")
        self.write(gonogo.RUNBOOK, text)
        self.cleared_rest()
        row = self.rows()["P1"]
        self.assertEqual(row["verdict"], gonogo.UNKNOWN)
        self.assertIn("do not agree", row["reason"])
        self.assertEqual(self.report()["verdict"], gonogo.NO_GO)

    def test_a_row_only_the_table_records_says_so(self):
        text = runbook(preconditions=((1, "the brake", "MET"),))
        text = text.replace("### P1 - the brake. **MET.**", "")
        self.write(gonogo.RUNBOOK, text)
        self.cleared_rest()
        row = self.rows()["P1"]
        self.assertEqual(row["verdict"], gonogo.MET)
        self.assertIn("no `### P1` section", row["reason"])

    def cleared_rest(self):
        self.write(gonogo.PREFLIGHT,
                   preflight(assessed=10, cleared=10, not_cleared=0))
        self.write(gonogo.EXIT_CRITERIA, exit_criteria())
        self.write(gonogo.DECISIONS, decisions())


class TwoDocumentsThatDisagree(AnEstate, unittest.TestCase):
    """The live instance, and the reason this page is worth rendering.

    The runbook's shortest list asks the operator to name which export is
    criterion 6's authority. The decisions sheet, written five hours later,
    records that question VOID. A page showing only the runbook would have
    him working an item that no longer exists.
    """

    def estate(self, void=True):
        self.write(gonogo.RUNBOOK, runbook(
            items=("**Criterion 6 needs you to name which export is the "
                   "authority.** Two exports disagree. (P1)",),
            owners="Items 1 are yours.",
            preconditions=((1, "the export authority is settled",
                            "NOT MET"),)))
        self.write(gonogo.PREFLIGHT,
                   preflight(assessed=10, cleared=10, not_cleared=0))
        self.write(gonogo.EXIT_CRITERIA, exit_criteria())
        title = ("### 8. ~~Criterion 6 - which export is the authority~~ "
                 "**VOID**") if void else (
            "### 8. Criterion 6 - which export is the authority")
        self.write(gonogo.DECISIONS, decisions(tier3=(title,)))

    def test_a_question_another_document_voided_renders_unknown(self):
        self.estate()
        row = self.rows()["shortest:1"]
        self.assertEqual(row["verdict"], gonogo.UNKNOWN)
        self.assertTrue(row["dispute"])
        self.assertEqual(row["dispute"]["criterion"], 6)
        self.assertEqual(row["dispute"]["word"], "VOID")

    def test_the_verdict_it_held_is_kept_as_history(self):
        self.estate()
        self.assertEqual(self.rows()["shortest:1"]["recorded_label"],
                         "NOT MET")

    def test_the_dispute_is_not_resolved_in_the_newer_document_s_favour(self):
        """Naming the authority is the operator's sentence, not a page's."""
        self.estate()
        row = self.rows()["shortest:1"]
        self.assertNotEqual(row["verdict"], gonogo.WITHDRAWN)
        self.assertNotEqual(row["verdict"], gonogo.MET)
        self.assertIn("operator", row["reason"])

    def test_without_the_void_the_row_keeps_its_recorded_verdict(self):
        """The control for the test above: no dispute, no downgrade."""
        self.estate(void=False)
        row = self.rows()["shortest:1"]
        self.assertEqual(row["verdict"], gonogo.NOT_MET)
        self.assertIsNone(row["dispute"])

    def test_the_page_says_so_in_words(self):
        self.estate()
        html = self.page()
        self.assertIn("two authorities disagree", html)


# --------------------------------------------------------------------------
# Age is a first-class field.
# --------------------------------------------------------------------------

class AgeIsAFirstClassField(AnEstate, unittest.TestCase):

    def test_a_reading_inside_the_threshold_keeps_its_verdict(self):
        self.cleared_estate(when=FRESH)
        rows = self.rows()
        self.assertEqual(rows["P1"]["verdict"], gonogo.MET)
        self.assertFalse(rows["P1"]["age"]["stale"])

    def test_a_reading_older_than_the_threshold_is_stale(self):
        self.cleared_estate(when=OLD)
        row = self.rows()["P1"]
        self.assertEqual(row["verdict"], gonogo.STALE)
        self.assertTrue(row["age"]["stale"])
        self.assertEqual(self.report()["verdict"], gonogo.NO_GO)

    def test_stale_is_a_different_word_from_not_met(self):
        """They lead to different actions: re-measure, not repair.

        Asserted on the reason text as well as the verdict, because the whole
        value of the distinction is in what it tells somebody to do.
        """
        self.cleared_estate(when=OLD)
        row = self.rows()["P1"]
        self.assertNotEqual(row["verdict"], gonogo.NOT_MET)
        self.assertEqual(row["verdict_label"], "STALE")
        self.assertIn("re-measure", row["reason"])
        self.assertEqual(row["recorded_label"], "MET")

    def test_the_verdict_a_stale_row_recorded_is_shown_as_history(self):
        self.cleared_estate(when=OLD)
        html = self.page()
        self.assertIn("recorded MET", html)

    def test_a_document_with_no_establishable_time_is_stale(self):
        """An undated verdict is a memory rather than a measurement.

        Both clocks are taken away: the document's own stamp and the file's
        mtime, the second by setting it into the future, which is its own
        refusal.
        """
        now = datetime.datetime(2026, 10, 16, 11, 0, 0)
        self.cleared_estate()
        text = runbook(headline="YES", preconditions=CLEARED_PRE)
        text = text.replace("batch clock   local %s" % stamp(FRESH),
                            "batch clock   local <not recorded>")
        text = "\n".join(line for line in text.splitlines()
                         if "2026-" not in line)
        self.write(gonogo.RUNBOOK, text,
                   mtime=now + datetime.timedelta(hours=5))
        row = self.rows(now)["P1"]
        self.assertIsNone(row["age"]["age_seconds"])
        self.assertTrue(row["age"]["stale"])
        self.assertNotEqual(row["verdict"], gonogo.MET)

    def test_a_stamp_in_the_future_is_not_called_fresh(self):
        got = gonogo.age_of(NOW + datetime.timedelta(hours=2),
                            gonogo.AS_OF_STAMP, NOW)
        self.assertTrue(got["in_future"])
        self.assertTrue(got["stale"])
        self.assertIsNone(got["age_seconds"])

    def test_a_document_stating_only_a_date_falls_back_to_its_mtime(self):
        """And the page SAYS it is an mtime.

        The two are different claims: a batch clock is when somebody ran a
        command, an mtime is when the bytes were last touched, which can be
        a typo fix.
        """
        self.cleared_estate()
        text = exit_criteria()
        text = text.replace("Measured %s." % stamp(FRESH),
                            "Measured %s." % FRESH.strftime("%Y-%m-%d"))
        self.write(gonogo.EXIT_CRITERIA, text, mtime=FRESH)
        source = [s for s in self.report()["sources"]
                  if s["key"] == "exit"][0]
        self.assertEqual(source["age"]["as_of_kind"], gonogo.AS_OF_MTIME)
        html = self.page()
        self.assertIn("modification time", html)

    def test_the_age_is_not_read_from_the_newest_timestamp_in_the_document(
            self):
        """The defect this bound exists for.

        The first version of this reader took the latest clock anywhere in
        the text, so a per-contact row deep inside a 107 KB preflight aged
        the whole document. A clock far below the head must not move it.
        """
        self.cleared_estate(when=OLD)
        text = preflight(assessed=10, cleared=10, not_cleared=0, when=OLD)
        text += "\n" + "\n".join("filler" for _ in range(60))
        text += "\n\n### a contact row touched at %s\n" % stamp(NOW)
        self.write(gonogo.PREFLIGHT, text, mtime=OLD)
        source = [s for s in self.report()["sources"]
                  if s["key"] == "preflight"][0]
        self.assertTrue(source["age"]["stale"])
        self.assertGreater(source["age"]["age_seconds"],
                           gonogo.STALE_SECONDS)

    def test_a_stale_row_never_overwrites_an_unknown_one(self):
        """STALE is a weaker statement and must not replace UNKNOWN.

        An UNKNOWN row has no verdict to re-read, so telling the reader to
        re-measure it is the wrong instruction.
        """
        self.cleared_estate(when=OLD)
        self.write(gonogo.RUNBOOK, runbook(
            headline="YES", when=OLD,
            preconditions=((1, "sending.live off", "UNKNOWN"),)))
        self.assertEqual(self.rows()["P1"]["verdict"], gonogo.UNKNOWN)

    def test_the_threshold_is_stated_on_the_page(self):
        self.cleared_estate(when=OLD)
        html = self.page()
        self.assertIn(gonogo.humanise(gonogo.STALE_SECONDS), html)

    def test_what_a_row_was_measured_against_is_shown(self):
        self.cleared_estate()
        row = self.rows()["P1"]
        self.assertEqual(row["against"]["origin_master"], "b1f290c84")
        self.assertIn("b1f290c84", self.page())


# --------------------------------------------------------------------------
# The shortest list, its order, and who owns each item.
# --------------------------------------------------------------------------

class TheShortestList(AnEstate, unittest.TestCase):

    ITEMS = (
        "**Your explicit `APPROVED`.** Nothing else matters until this "
        "exists.",
        "**The brake must be in the tree that would send.** (P1)",
        "**Criterion 5 bypasses the door.** (P2)",
    )
    OWNERS = ("Items 2 and 3 are construction and need nobody's permission. "
              "Items 1 are yours.")
    PRE = ((1, "the brake is in the sending tree", "NOT MET"),
           (2, "the write door covers every send path", "NOT MET"),
           (3, "the pool has free capacity", "UNKNOWN"))

    def estate(self):
        self.write(gonogo.RUNBOOK, runbook(items=self.ITEMS,
                                           owners=self.OWNERS,
                                           preconditions=self.PRE))
        self.write(gonogo.PREFLIGHT,
                   preflight(assessed=10, cleared=10, not_cleared=0))
        self.write(gonogo.EXIT_CRITERIA, exit_criteria())
        self.write(gonogo.DECISIONS, decisions())

    def test_the_runbook_s_own_order_is_kept(self):
        self.estate()
        ranked = [item for item in self.report()["shortest"]
                  if item["from_runbook_list"]]
        self.assertEqual([item["runbook_rank"] for item in ranked], [1, 2, 3])
        self.assertIn("APPROVED", ranked[0]["what"])

    def test_the_owner_split_comes_from_the_runbook_s_own_sentence(self):
        self.estate()
        rows = self.rows()
        self.assertEqual(rows["shortest:1"]["owner"], gonogo.OWNER_OPERATOR)
        self.assertEqual(rows["shortest:2"]["owner"],
                         gonogo.OWNER_CONSTRUCTION)
        self.assertEqual(rows["shortest:3"]["owner"],
                         gonogo.OWNER_CONSTRUCTION)

    def test_an_item_the_sentence_does_not_name_is_unstated_not_construction(
            self):
        """An unowned blocker is how a row sits still for a day."""
        self.write(gonogo.RUNBOOK, runbook(items=self.ITEMS, owners="",
                                           preconditions=self.PRE))
        self.write(gonogo.PREFLIGHT,
                   preflight(assessed=10, cleared=10, not_cleared=0))
        self.write(gonogo.EXIT_CRITERIA, exit_criteria())
        self.write(gonogo.DECISIONS, decisions())
        for key in ("shortest:1", "shortest:2", "shortest:3"):
            self.assertEqual(self.rows()[key]["owner"],
                             gonogo.OWNER_UNSTATED, key)

    def test_a_blocker_the_runbook_s_list_omits_is_shown_and_labelled(self):
        """P3 is NOT MET and no item in the shortest list cites it.

        That row is exactly the one a reader of the runbook's summary would
        miss, which is why the page names it rather than folding it in.
        """
        self.estate()
        data = self.report()
        self.assertIn("P3", data["omitted"])
        positions = {item["key"]: item for item in data["shortest"]}
        self.assertIn("P3", positions)
        self.assertFalse(positions["P3"]["from_runbook_list"])
        self.assertIn("NOT in the runbook", self.page())

    def test_an_item_whose_precondition_reads_met_is_a_contradiction(self):
        """The list says outstanding and the table says done.

        Both cannot be current, and this page does not pick which half of a
        document to believe.
        """
        self.write(gonogo.RUNBOOK, runbook(
            items=("**The brake must be in the tree.** (P1)",),
            owners="Items 1 are construction.",
            preconditions=((1, "the brake is in the sending tree", "MET"),)))
        self.write(gonogo.PREFLIGHT,
                   preflight(assessed=10, cleared=10, not_cleared=0))
        self.write(gonogo.EXIT_CRITERIA, exit_criteria())
        self.write(gonogo.DECISIONS, decisions())
        row = self.rows()["shortest:1"]
        self.assertEqual(row["verdict"], gonogo.UNKNOWN)
        self.assertIn("cannot both be current", row["reason"])

    def test_an_item_citing_no_precondition_says_where_its_verdict_came_from(
            self):
        self.estate()
        row = self.rows()["shortest:1"]
        self.assertEqual(row["verdict"], gonogo.NOT_MET)
        self.assertIn("cites no precondition", row["reason"])

    def test_the_authority_is_the_command_the_runbook_names(self):
        self.estate()
        self.assertEqual(self.rows()["shortest:2"]["authority"],
                         "a command that verified P1")

    def test_a_row_with_no_command_states_the_absence(self):
        self.estate()
        self.assertIsNone(self.rows()["shortest:1"]["authority"])
        self.assertIn("names no command", self.page())


class WhereTheAuthorityLives(unittest.TestCase):

    def test_each_path_is_classified_on_its_own_evidence(self):
        homes = gonogo.homes_in(
            "`src/haltfile.py` and `resonate-ops\\STOP-SENDING` and "
            "`work/queue.jsonl` and `GET /sender-emails`")
        got = {home["path"]: home["where"] for home in homes}
        self.assertEqual(got["src/haltfile.py"], gonogo.LOC_REPO)
        self.assertEqual(got["resonate-ops\\STOP-SENDING"], gonogo.LOC_OPS)
        self.assertEqual(got["work/queue.jsonl"], gonogo.LOC_PRODUCTION)
        self.assertEqual(got["GET /sender-emails"], gonogo.LOC_PROVIDER)

    def test_an_identifier_in_backticks_is_not_a_path(self):
        """`APPROVED`, `sending.live` and `STOP-SENDING` are not files."""
        for text in ("`APPROVED`", "`sending.live`", "`STOP-SENDING`",
                     "`b1f290c84`"):
            self.assertEqual(gonogo.homes_in(text), [], text)

    def test_a_row_whose_paths_disagree_is_split_not_unknown(self):
        homes = gonogo.homes_in("`src/haltfile.py` `resonate-ops\\x.md`")
        self.assertEqual(gonogo.located(homes), gonogo.LOC_SPLIT)

    def test_a_row_with_no_path_is_unstated(self):
        self.assertEqual(gonogo.located([]), gonogo.LOC_UNSTATED)

    def test_every_location_has_a_glossary_entry(self):
        """A page that renders a label it cannot explain has a blank cell."""
        for where in (gonogo.LOC_REPO, gonogo.LOC_OPS, gonogo.LOC_OPERATOR,
                      gonogo.LOC_PROVIDER, gonogo.LOC_PRODUCTION,
                      gonogo.LOC_SPLIT, gonogo.LOC_UNSTATED):
            self.assertIn(where, gonogo.LOCATION_TEXT)


class TheDecisionsSheet(AnEstate, unittest.TestCase):

    def rest(self):
        self.write(gonogo.RUNBOOK, runbook(headline="YES",
                                           preconditions=CLEARED_PRE))
        self.write(gonogo.PREFLIGHT,
                   preflight(assessed=10, cleared=10, not_cleared=0))
        self.write(gonogo.EXIT_CRITERIA, exit_criteria())

    def test_an_open_tier_two_item_is_a_blocker(self):
        self.rest()
        self.write(gonogo.DECISIONS,
                   decisions(tier2=("### 3. Run the attach command",)))
        row = self.rows()["decision:3"]
        self.assertEqual(row["verdict"], gonogo.NOT_MET)
        self.assertEqual(row["owner"], gonogo.OWNER_OPERATOR)

    def test_the_owner_comes_from_the_sheet_s_own_sentence(self):
        """Both forms of it. The live sheet writes "**None of these can be
        closed by a lane.**", and a pattern looking only for "cannot be
        closed by a lane" misses it entirely - which moved two of the four
        blockers from `operator` to `not stated`."""
        self.rest()
        self.write(gonogo.DECISIONS,
                   decisions(tier2=("### 3. Run the attach command",),
                             lane_sentence=False))
        self.assertEqual(self.rows()["decision:3"]["owner"],
                         gonogo.OWNER_UNSTATED)

    def test_a_struck_tier_two_item_is_withdrawn_not_met(self):
        self.rest()
        self.write(gonogo.DECISIONS,
                   decisions(tier2=("### 3. ~~Run the attach command~~ "
                                    "**VOID**",)))
        row = self.rows()["decision:3"]
        self.assertEqual(row["verdict"], gonogo.WITHDRAWN)
        self.assertEqual(self.report()["verdict"], gonogo.NO_GO)

    def test_an_empty_tier_two_with_items_elsewhere_is_met(self):
        """The cleared state of this source, and it is measured.

        An empty section and a reader whose pattern stopped matching are the
        same zero from inside. The discriminator is whether numbered items
        exist anywhere on the sheet.
        """
        self.rest()
        self.write(gonogo.DECISIONS, decisions())
        row = self.rows()["decision:0"]
        self.assertEqual(row["verdict"], gonogo.MET)
        self.assertIn("1 numbered items elsewhere", row["reason"])

    def test_a_sheet_with_no_numbered_item_anywhere_is_unknown(self):
        self.rest()
        self.write(gonogo.DECISIONS, decisions(tier3=()))
        rows = self.rows()
        self.assertIn("source:decisions", rows)
        self.assertEqual(rows["source:decisions"]["verdict"], gonogo.UNKNOWN)
        self.assertEqual(self.report()["verdict"], gonogo.NO_GO)

    def test_a_sheet_with_no_tier_two_heading_is_unknown(self):
        self.rest()
        self.write(gonogo.DECISIONS,
                   "# DECISIONS OPEN - %s local\n\n### 3. Something\n"
                   % stamp(FRESH))
        rows = self.rows()
        self.assertEqual(rows["source:decisions"]["verdict"], gonogo.UNKNOWN)
        source = [s for s in self.report()["sources"]
                  if s["key"] == "decisions"][0]
        self.assertIn("TIER 2", source["reason"])

    def test_an_item_s_own_measured_time_beats_the_sheet_s(self):
        """A sheet appended to at 10:55 does not make an item measured at
        08:35 two hours fresher than it is."""
        self.rest()
        self.write(gonogo.DECISIONS, decisions(
            tier2=("### 3. Run the attach command\n"
                   "- *Measured: `pilotcaps/0200` 00:30.*",)),
            mtime=FRESH)
        row = self.rows()["decision:3"]
        self.assertTrue(row["age"]["as_of"].endswith("00:30:00"))


class ThePreflight(AnEstate, unittest.TestCase):

    def rest(self):
        self.write(gonogo.RUNBOOK, runbook(headline="YES",
                                           preconditions=CLEARED_PRE))
        self.write(gonogo.EXIT_CRITERIA, exit_criteria())
        self.write(gonogo.DECISIONS, decisions())

    def test_not_cleared_because_unknown_is_unknown_not_not_met(self):
        self.rest()
        self.write(gonogo.PREFLIGHT, preflight())
        row = self.rows()["preflight:cohort"]
        self.assertEqual(row["verdict"], gonogo.UNKNOWN)
        self.assertIn("UNKNOWN is not a pass", row["reason"])

    def test_an_excluded_contact_is_not_met(self):
        self.rest()
        self.write(gonogo.PREFLIGHT,
                   preflight(assessed=10, cleared=9, excluded=1,
                             not_cleared=0))
        self.assertEqual(self.rows()["preflight:cohort"]["verdict"],
                         gonogo.NOT_MET)

    def test_a_clearance_over_an_empty_cohort_is_not_a_clearance(self):
        self.rest()
        self.write(gonogo.PREFLIGHT,
                   preflight(assessed=0, cleared=0, not_cleared=0))
        row = self.rows()["preflight:cohort"]
        self.assertEqual(row["verdict"], gonogo.UNKNOWN)
        self.assertIn("empty cohort", row["reason"])

    def test_a_missing_count_makes_the_source_unparseable(self):
        self.rest()
        text = preflight().replace("    excluded", "    removed")
        self.write(gonogo.PREFLIGHT, text)
        source = [s for s in self.report()["sources"]
                  if s["key"] == "preflight"][0]
        self.assertEqual(source["state"], gonogo.NO_BLOCK)
        self.assertIn("excluded", source["reason"])

    def test_the_counts_are_quoted_and_not_recomputed(self):
        """A number on this page that no artifact contains is a defect."""
        self.rest()
        self.write(gonogo.PREFLIGHT, preflight())
        reason = self.rows()["preflight:cohort"]["reason"]
        self.assertIn("23 of 23", reason)


class TheExitCriteriaSource(AnEstate, unittest.TestCase):

    def rest(self):
        self.write(gonogo.RUNBOOK, runbook(headline="YES",
                                           preconditions=CLEARED_PRE))
        self.write(gonogo.PREFLIGHT,
                   preflight(assessed=10, cleared=10, not_cleared=0))
        self.write(gonogo.DECISIONS, decisions())

    def test_nine_met_is_the_conjunction_met(self):
        self.rest()
        self.write(gonogo.EXIT_CRITERIA, exit_criteria())
        self.assertEqual(self.rows()["exit:nine"]["verdict"], gonogo.MET)

    def test_one_not_met_makes_the_conjunction_not_met(self):
        self.rest()
        self.write(gonogo.EXIT_CRITERIA, exit_criteria({5: "NOT MET"}))
        self.assertEqual(self.rows()["exit:nine"]["verdict"], gonogo.NOT_MET)

    def test_one_unknown_makes_the_conjunction_unknown(self):
        self.rest()
        self.write(gonogo.EXIT_CRITERIA, exit_criteria({5: "UNKNOWN"}))
        self.assertEqual(self.rows()["exit:nine"]["verdict"], gonogo.UNKNOWN)

    def test_a_partial_re_audit_cannot_settle_the_conjunction(self):
        """Three criteria re-audited is the live shape of this artifact, and
        a conjunction over three of nine is not a conjunction."""
        self.rest()
        self.write(gonogo.EXIT_CRITERIA, """# EXIT CRITERIA

Measured %s.

| # | criterion | verdict |
|---|---|---|
| 3 | li1 renders a note | **MET** |
| 5 | the write door | **MET** |
| 9 | the kill switch | **MET** |
""" % stamp(FRESH))
        row = self.rows()["exit:nine"]
        self.assertEqual(row["verdict"], gonogo.UNKNOWN)
        self.assertIn("3 rows and CANARY-01 has 9", row["reason"])

    def test_the_conjunction_is_computed_by_the_criteria_instrument(self):
        """Not reimplemented here. Two authorities for one number is this
        repository's own named defect, and the rule that UNKNOWN never
        becomes a pass is already written into `src.exitcriteria`."""
        import ast
        with open(os.path.join(os.path.dirname(__file__), "..", "src",
                               "gonogo.py"), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func,
                                                         ast.Attribute):
                if isinstance(node.func.value, ast.Name) \
                        and node.func.value.id == "exitcriteria":
                    called.add(node.func.attr)
        self.assertIn("conjunction_of", called)
        self.assertIn("verdicts_from_text", called)


# --------------------------------------------------------------------------
# What the page is not allowed to do.
# --------------------------------------------------------------------------

class ThePageMeasuresNothing(AnEstate, unittest.TestCase):

    def test_it_opens_no_socket(self):
        self.cleared_estate()
        original = socket.socket

        def refuse(*args, **kwargs):
            raise AssertionError("the go/no-go reader opened a socket")

        socket.socket = refuse
        try:
            data = self.report()
            self.page()
        finally:
            socket.socket = original
        self.assertEqual(data["verdict"], gonogo.GO)

    def test_it_writes_no_file(self):
        self.cleared_estate()
        original = builtins.open

        def guard(path, mode="r", *args, **kwargs):
            if any(flag in str(mode) for flag in ("w", "a", "x", "+")):
                raise AssertionError("the go/no-go reader wrote %s" % path)
            return original(path, mode, *args, **kwargs)

        builtins.open = guard
        try:
            self.report()
        finally:
            builtins.open = original

    def test_it_runs_no_subprocess(self):
        """No git call. What a verdict was measured against is READ out of
        the document, never checked - checking is measuring."""
        import subprocess
        originals = (subprocess.run, subprocess.Popen,
                     subprocess.check_output)

        def refuse(*args, **kwargs):
            raise AssertionError("the go/no-go reader ran a subprocess")

        subprocess.run = refuse
        subprocess.Popen = refuse
        subprocess.check_output = refuse
        try:
            self.cleared_estate()
            self.report()
        finally:
            (subprocess.run, subprocess.Popen,
             subprocess.check_output) = originals

    def test_no_home_directory_reaches_the_page(self):
        """A path on a screen is somebody's full name in a screenshot."""
        self.cleared_estate()
        self.write(gonogo.RUNBOOK, runbook(
            headline="YES", preconditions=CLEARED_PRE,
            extra="The brake lives at "
                  "`C:\\Users\\Someone\\Desktop\\resonate-ops\\STOP-SENDING`"
                  " and `C:\\Users\\Someone\\private\\notes.md`."))
        html = self.page()
        self.assertNotIn("Someone", html)
        self.assertIn("resonate-ops", html)

    def test_the_redaction_keeps_the_anchor_and_drops_the_user(self):
        self.assertEqual(
            gonogo.safe_path("C:\\Users\\Someone\\Desktop\\resonate-ops\\x"),
            "resonate-ops\\x")
        self.assertEqual(gonogo.redact("see C:\\Users\\Someone\\private"),
                         "see <home>\\private")

    def test_every_refusal_the_page_claims_is_a_sentence(self):
        for what, why in gonogo.REFUSALS:
            self.assertTrue(what and why)


class TheProvenanceIsRegistered(AnEstate, unittest.TestCase):

    def test_no_figure_on_the_page_is_unsourced(self):
        self.cleared_estate()
        data = api.go_no_go(now=NOW)
        self.assertEqual(data["provenance"]["uncovered"], 0,
                         data["provenance"].get("uncovered_paths"))

    def test_the_headline_is_one_word_and_not_a_score(self):
        self.cleared_estate()
        data = api.go_no_go(now=NOW)
        self.assertIn("CAN send", data["headline"])
        self.assertNotIn(" of ", data["headline"])


# --------------------------------------------------------------------------
# The route.
# --------------------------------------------------------------------------

class TheRouteIsSuperAdminOnly(WebTest):

    @classmethod
    def setUpClass(cls):
        cls.ops = tempfile.mkdtemp(prefix="rga-gonogo-route-")
        cls._previous_ops = os.environ.get(lanes.OPS_DIR)
        os.environ[lanes.OPS_DIR] = cls.ops
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        if cls._previous_ops is None:
            os.environ.pop(lanes.OPS_DIR, None)
        else:
            os.environ[lanes.OPS_DIR] = cls._previous_ops
        shutil.rmtree(cls.ops, ignore_errors=True)
        super().tearDownClass()

    def test_a_super_admin_gets_the_page(self):
        status, body, _ = self.signin(SUPER).get(PATH)
        self.assertEqual(status, 200)
        self.assertIn("Can this send right now?", body)

    def test_a_workspace_admin_is_refused(self):
        status, body, _ = self.signin(ADMIN).get(PATH)
        self.assertEqual(status, 404, "404 rather than 403, as /admin does")
        self.assertNotIn("Can this send right now?", body)

    def test_an_operator_is_refused(self):
        status, _body, _ = self.signin(OPERATOR).get(PATH)
        self.assertEqual(status, 404)

    def test_an_anonymous_caller_is_never_served_the_page(self):
        status, body, _ = self.anonymous().get(PATH)
        self.assertIn(status, (200, 303))
        self.assertNotIn("Can this send right now?", body)

    def test_the_route_is_not_gated_by_a_workspace_permission(self):
        """`operations.view` reaches a client-facing REVIEWER, so a
        workspace permission here would be the wrong gate entirely."""
        self.assertIsNone(permission_for(PATH))

    def test_an_empty_estate_still_renders_the_page(self):
        """NO-GO with four UNKNOWN rows, not a 500. A go/no-go screen that
        errors is a screen that gets skipped."""
        status, body, _ = self.signin(SUPER).get(PATH)
        self.assertEqual(status, 200)
        self.assertIn("NO-GO", body)
        self.assertIn("UNKNOWN", body)

    def test_the_page_is_in_the_navigation(self):
        self.assertIn(PATH, [href for href, _, _ in pages.NAV])


if __name__ == "__main__":                                  # pragma: no cover
    unittest.main()
