"""A figure two named authorities give differently is CONTESTED, never a number.

WHY THIS FILE EXISTS. This lane produced three corrections in two sessions and
left all three sitting beside the figure they contradict: "101 unpushed" against
38 truly unreachable, local `master` called "diverged" against a measured `0 1`,
and a clone called "64 files" against 2,681. The estate's standing prohibition is
that no number is repeated without its denominator and its conditions, and a page
that prints ONE of two disagreeing figures breaks it silently.

THE TWO FAILURE DIRECTIONS, AND BOTH ARE TESTED HERE.

The obvious one is resolving a contest - picking the newer measurement, the
majority, or this lane's own. `TASK-0240`'s section 9 was falsified by a reading
taken SIXTY MINUTES EARLIER, so recency is not a tiebreak in this estate's own
history, and `ARecencyIsNotATiebreak` below is the test that holds it.

The other is B7's shape in reverse: **an instrument that always says CONTESTED
sees nothing and reports it as caution.** `AgreementIsReachable` is why the
CONTESTED rows mean anything, and `OneAuthorityIsNotAgreement` is why a lone
reading is not laundered into a settled one.

AND THE AUTHORITY STRINGS ARE READ, NOT TYPED. `suppression/0210` is the citation
in this estate that was typed. Every value here comes out of the file and the line
the claim cites, and `ACitationThatDoesNotHold` proves all three failure states
produce something VISIBLE rather than a blank beside a number.

NOTHING HERE READS THE REAL ESTATE. Every authority document is a string this
module writes into a temporary directory. The three real rows are measured by
`webapp-0280-controls.py`, which reads them and writes nothing.
"""
import os
import re
import shutil
import tempfile
import unittest

from src import contested
from src.web import api, pages


def figure(key="count", question="How many?", claims=()):
    return {"key": key, "question": question,
            "why_it_matters": "because two documents say different things",
            "claims": list(claims)}


def claim(label, path, line, pattern=r"COUNT\s*:\s*(?P<value>\d+)",
          quote="COUNT", denominator="a stated denominator",
          condition="a stated condition", stamp=r"read at (?P<stamp>\S+)"):
    return {"label": label, "path": path, "line": line, "pattern": pattern,
            "quote": quote, "denominator": denominator,
            "condition": condition, "stamp": stamp}


class Estate:
    """A temporary ops estate holding synthetic authority documents."""

    def setUp(self):
        super().setUp()
        self.root = tempfile.mkdtemp(prefix="rga-contested-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def doc(self, name, *lines):
        path = os.path.join(self.root, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines) + "\n")
        return path

    def read(self, *figures):
        return contested.contested(root=self.root, figures=figures)

    def one(self, *figures):
        return self.read(*figures)["figures"][0]

    def two_documents(self, first, second, stamp_a="2026-10-16T09:00:00Z",
                      stamp_b="2026-10-16T11:00:00Z"):
        """Two documents, each stating one COUNT, on line 3 of each."""
        self.doc("A.txt", "read at " + stamp_a, "", "COUNT : %s" % first)
        self.doc("B.txt", "read at " + stamp_b, "", "COUNT : %s" % second)
        return figure(claims=(claim("authority A", "A.txt", 3),
                              claim("authority B", "B.txt", 3)))


# ------------------------------------------------------------------ C1 and C2


class ContestedFires(Estate, unittest.TestCase):
    """C1. Two authorities, two values, and nothing picks between them."""

    def test_two_different_values_are_contested(self):
        row = self.one(self.two_documents("101", "38"))
        self.assertEqual(row["verdict"], contested.CONTESTED)
        self.assertEqual(row["values"], ["101", "38"])
        # AND NO SINGLE VALUE IS OFFERED. A downstream caller must not be
        # able to read a number off a row that has two.
        self.assertIsNone(row["value"])
        self.assertTrue(row["blocks_arithmetic"])

    def test_both_values_carry_their_own_denominator_and_condition(self):
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : 101")
        self.doc("B.txt", "read at 2026-10-16T11:00:00Z", "", "COUNT : 38")
        row = self.one(figure(claims=(
            claim("the name check", "A.txt", 3,
                  denominator="581 local names against 518 remote",
                  condition="a name absent from the remote"),
            claim("reachability", "B.txt", 3,
                  denominator="the same 581 local names",
                  condition="a commit no remote ref reaches"))))
        first, second = row["claims"]
        self.assertEqual(first["value"], "101")
        self.assertIn("581 local names", first["denominator"])
        self.assertIn("name absent", first["condition"])
        self.assertEqual(second["value"], "38")
        self.assertIn("no remote ref reaches", second["condition"])
        # The stamp comes out of the file too, and is not this page's clock.
        self.assertEqual(first["stamp"], "2026-10-16T09:00:00Z")
        self.assertEqual(second["stamp"], "2026-10-16T11:00:00Z")

    def test_a_three_way_contest_keeps_all_three(self):
        """The real `unreachable_branches` row has three: 101, 100 and 38."""
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : 101")
        self.doc("B.txt", "read at 2026-10-16T10:00:00Z", "", "COUNT : 100")
        self.doc("C.txt", "read at 2026-10-16T11:00:00Z", "", "COUNT : 38")
        row = self.one(figure(claims=(claim("A", "A.txt", 3),
                                      claim("B", "B.txt", 3),
                                      claim("C", "C.txt", 3))))
        self.assertEqual(row["verdict"], contested.CONTESTED)
        self.assertEqual(row["values"], ["100", "101", "38"])
        self.assertEqual(row["claims_read"], 3)
        self.assertEqual(row["claims_cited"], 3)

    def test_a_non_numeric_disagreement_is_contested_too(self):
        """`unpushed` against `BEHIND/contained, not ahead`. A word is a
        value: the local-`master` row has no number in it at all."""
        self.doc("rules.md", "moved 00:13 today, unpushed")
        self.doc("walk.log", "local master is BEHIND and not ahead")
        row = self.one(figure(claims=(
            claim("the standing rules", "rules.md", 1,
                  pattern=r"moved 00:13 today, (?P<value>\w+)",
                  quote="moved 00:13", stamp=None),
            claim("the object walk", "walk.log", 1,
                  pattern=r"local master is (?P<value>[A-Za-z ]+)",
                  quote="local master is", stamp=None))))
        self.assertEqual(row["verdict"], contested.CONTESTED)
        self.assertEqual(row["claims"][0]["value"], "unpushed")
        self.assertIn("BEHIND", row["claims"][1]["value"])


class AgreementIsReachable(Estate, unittest.TestCase):
    """C2. WITHOUT THIS THE WHOLE PAGE IS WORTHLESS.

    An instrument that always answers CONTESTED sees nothing and reports it
    as caution - B7's shape, in the opposite direction from usual. Two
    agreeing authorities must produce a plain value.
    """

    def test_two_agreeing_authorities_are_not_contested(self):
        row = self.one(self.two_documents("2681", "2681"))
        self.assertEqual(row["verdict"], contested.AGREED)
        self.assertEqual(row["value"], "2681")
        self.assertEqual(row["values"], ["2681"])
        self.assertFalse(row["blocks_arithmetic"])

    def test_formatting_is_not_a_disagreement(self):
        """`2,681` and `2681` are one value. A thousands separator is
        formatting, and reporting it as a contest would be an instrument
        crying wolf at its own punctuation."""
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "",
                 "COUNT : 2,681")
        self.doc("B.txt", "read at 2026-10-16T11:00:00Z", "", "COUNT : 2681")
        row = self.one(figure(claims=(
            claim("A", "A.txt", 3, pattern=r"COUNT\s*:\s*(?P<value>[\d,]+)"),
            claim("B", "B.txt", 3,
                  pattern=r"COUNT\s*:\s*(?P<value>[\d,]+)"))))
        self.assertEqual(row["verdict"], contested.AGREED)
        # AND BOTH ARE PRINTED AS WRITTEN. Normalisation is what they are
        # compared by, never what is shown.
        self.assertEqual([c["value"] for c in row["claims"]],
                         ["2,681", "2681"])

    def test_a_case_difference_IS_a_disagreement(self):
        """Not every difference is formatting. Two documents using different
        words for one relation is exactly the thing this page shows."""
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "",
                 "COUNT : unpushed")
        self.doc("B.txt", "read at 2026-10-16T11:00:00Z", "",
                 "COUNT : UNPUSHED")
        row = self.one(figure(claims=(
            claim("A", "A.txt", 3, pattern=r"COUNT\s*:\s*(?P<value>\w+)"),
            claim("B", "B.txt", 3, pattern=r"COUNT\s*:\s*(?P<value>\w+)"))))
        self.assertEqual(row["verdict"], contested.CONTESTED)

    def test_agreement_publishes_how_many_were_read(self):
        """Agreement among two of three is not agreement among three."""
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : 7")
        self.doc("B.txt", "read at 2026-10-16T11:00:00Z", "", "COUNT : 7")
        row = self.one(figure(claims=(claim("A", "A.txt", 3),
                                      claim("B", "B.txt", 3),
                                      claim("gone", "missing.txt", 3))))
        self.assertEqual(row["verdict"], contested.AGREED)
        self.assertEqual(row["claims_read"], 2)
        self.assertEqual(row["claims_cited"], 3)
        self.assertEqual(row["unreadable"], ["missing.txt"])


class OneAuthorityIsNotAgreement(Estate, unittest.TestCase):
    """C3. A single-authority figure is not silently promoted."""

    def test_one_readable_authority_is_single_and_not_agreed(self):
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : 42")
        row = self.one(figure(claims=(claim("A", "A.txt", 3),)))
        self.assertEqual(row["verdict"], contested.SINGLE)
        self.assertNotEqual(row["verdict"], contested.AGREED)
        self.assertEqual(row["value"], "42")
        self.assertIn("UNCONFIRMED", row["verdict_label"])

    def test_one_readable_and_one_broken_is_still_single(self):
        """A claim that could not be read has NOT agreed with anything. The
        trap is that `{None, '42'}` has one non-None member, so a reader
        comparing a set of values after dropping the Nones would call this
        agreement."""
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : 42")
        self.doc("B.txt", "nothing this claim quotes is in here")
        row = self.one(figure(claims=(claim("A", "A.txt", 3),
                                      claim("B", "B.txt", 1))))
        self.assertEqual(row["verdict"], contested.SINGLE)
        self.assertEqual(row["claims_read"], 1)
        self.assertEqual(row["claims_cited"], 2)
        self.assertIsNone(row["claims"][1]["value"])

    def test_no_readable_authority_is_unknown_and_not_zero(self):
        row = self.one(figure(claims=(claim("gone", "nope.txt", 1),)))
        self.assertEqual(row["verdict"], contested.UNKNOWN)
        self.assertIsNone(row["value"])
        self.assertEqual(row["values"], [])
        self.assertTrue(row["blocks_arithmetic"])


class ARecencyIsNotATiebreak(Estate, unittest.TestCase):
    """THE DEFECT THE BRIEF IS ABOUT. Newer is not righter.

    `TASK-0240`'s own section 9 was falsified by a reading taken sixty
    minutes EARLIER, so a page resolving a contest by recency would have
    resolved this estate's own history the wrong way.
    """

    def test_the_newer_reading_does_not_win(self):
        row = self.one(self.two_documents(
            "101", "38", stamp_a="2026-10-16T09:00:00Z",
            stamp_b="2026-10-16T23:59:59Z"))
        self.assertEqual(row["verdict"], contested.CONTESTED)
        self.assertIsNone(row["value"])

    def test_the_order_is_not_by_stamp(self):
        """The control on the test above: swap the stamps, and the published
        order does not move. An order by recency is a preference by recency
        wearing a different word."""
        first = self.one(self.two_documents(
            "101", "38", stamp_a="2026-10-16T09:00:00Z",
            stamp_b="2026-10-16T23:00:00Z"))
        second = self.one(self.two_documents(
            "101", "38", stamp_a="2026-10-16T23:00:00Z",
            stamp_b="2026-10-16T09:00:00Z"))
        self.assertEqual(first["values"], second["values"])
        self.assertEqual([c["label"] for c in first["claims"]],
                         [c["label"] for c in second["claims"]])

    def test_a_missing_stamp_does_not_lose_the_claim(self):
        """A source that states no read-time is a source with no read-time,
        and this page will not date it from an mtime - which would be a fact
        about the last writer, not about the measurement."""
        self.doc("A.txt", "COUNT : 101")
        self.doc("B.txt", "read at 2026-10-16T11:00:00Z", "", "COUNT : 38")
        row = self.one(figure(claims=(claim("A", "A.txt", 1),
                                      claim("B", "B.txt", 3))))
        self.assertEqual(row["verdict"], contested.CONTESTED)
        self.assertIsNone(row["claims"][0]["stamp"])
        self.assertEqual(row["claims"][0]["value"], "101")


# ---------------------------------------------------------------------- C5


class ACitationThatDoesNotHold(Estate, unittest.TestCase):
    """C5. The authority strings are READ, not typed - and a citation that
    fails is VISIBLE rather than blank.

    `suppression/0210` is the citation in this estate that was typed. Every
    value here comes out of the file and the line the claim names, so a
    deliberately wrong path cannot produce a plausible number.
    """

    def test_a_wrong_path_is_a_named_failure_and_takes_no_value(self):
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : 101")
        row = self.one(figure(claims=(
            claim("A", "A.txt", 3),
            claim("typed by hand", "does/not/exist.txt", 3))))
        bad = row["claims"][1]
        self.assertEqual(bad["state"], contested.UNREADABLE)
        self.assertIsNone(bad["value"])
        self.assertEqual(bad["path"], "does/not/exist.txt")
        # The sentence names the failure and says no value was taken, so a
        # reader is not left with an empty cell to interpret.
        self.assertIn("is not there", bad["state_why"])
        self.assertIn("no value", bad["state_why"])
        self.assertIn("AUTHORITY UNREADABLE", bad["state_label"])
        # AND IT IS ON THE PAGE, not swallowed. A blank cell beside a number
        # is indistinguishable from a measurement of nothing.
        data = self.read(figure(claims=(
            claim("A", "A.txt", 3),
            claim("typed by hand", "does/not/exist.txt", 3))))
        self.assertEqual(len(data["citation_failures"]), 1)
        self.assertEqual(data["citation_failures"][0]["path"],
                         "does/not/exist.txt")

    def test_text_nowhere_in_the_file_is_broken_and_takes_no_value(self):
        self.doc("A.txt", "this file says nothing about any count")
        row = self.one(figure(claims=(claim("A", "A.txt", 1),)))
        self.assertEqual(row["claims"][0]["state"], contested.BROKEN)
        self.assertIsNone(row["claims"][0]["value"])
        self.assertEqual(row["verdict"], contested.UNKNOWN)

    def test_a_drifted_line_takes_the_value_and_shows_both_numbers(self):
        """THE EXPECTED CASE, not the exceptional one. Every document this
        page cites is appended to, so a line number in a citation decays -
        the real `CONTINUITY-LOG` citation had already moved from 1365 to
        1367 when this was written."""
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "", "a new line",
                 "another new line", "COUNT : 101")
        row = self.one(figure(claims=(claim("A", "A.txt", 3),)))
        found = row["claims"][0]
        self.assertEqual(found["state"], contested.DRIFTED)
        self.assertEqual(found["cited_line"], 3)
        self.assertEqual(found["found_line"], 5)
        self.assertEqual(found["value"], "101")
        self.assertEqual(row["drifted"], ["A.txt:3 -> 5"])

    def test_the_cited_line_is_preferred_over_a_later_match(self):
        """A citation that HOLDS is worth more than one that is merely
        recoverable, so the cited line is tried first and a match there is
        READ rather than DRIFTED."""
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : 101",
                 "COUNT : 999")
        row = self.one(figure(claims=(claim("A", "A.txt", 3),)))
        self.assertEqual(row["claims"][0]["state"], contested.READ)
        self.assertEqual(row["claims"][0]["value"], "101")

    def test_the_quoted_line_travels_so_a_reader_can_check_it(self):
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : 101")
        row = self.one(figure(claims=(claim("A", "A.txt", 3),)))
        self.assertEqual(row["claims"][0]["line_text"], "COUNT : 101")

    def test_every_citation_state_has_words(self):
        for state in (contested.READ, contested.DRIFTED, contested.BROKEN,
                      contested.UNREADABLE):
            self.assertIn(state, contested.CITATION_TEXT)
            self.assertIn(state, pages.CITATION_KIND)
        for verdict in (contested.CONTESTED, contested.AGREED,
                        contested.SINGLE, contested.UNKNOWN):
            self.assertIn(verdict, contested.FIGURE_TEXT)
            self.assertIn(verdict, pages.CONTEST_KIND)


# ---------------------------------------------------------------------- C4


class NoDownstreamArithmetic(Estate, unittest.TestCase):
    """C4. The sum REFUSES and names the row that blocked it.

    A total that quietly took one value off a contested row would launder the
    contest into a settled figure one layer down, and the figure would then
    be repeated without the conditions that make it mean two things.
    """

    def test_a_contested_figure_blocks_the_total_and_is_named(self):
        data = self.read(figure(key="contested_one",
                                claims=self.two_documents("101", "38")
                                ["claims"]),
                         figure(key="clean_one", claims=()))
        # Rebuild properly: two figures, one contested and one agreed.
        self.doc("C.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : 5")
        self.doc("D.txt", "read at 2026-10-16T11:00:00Z", "", "COUNT : 5")
        data = self.read(
            figure(key="contested_one",
                   claims=(claim("A", "A.txt", 3), claim("B", "B.txt", 3))),
            figure(key="clean_one",
                   claims=(claim("C", "C.txt", 3), claim("D", "D.txt", 3))))
        total = contested.total(data, ["contested_one", "clean_one"])
        self.assertFalse(total["computed"])
        self.assertIsNone(total["value"])
        self.assertEqual(total["blocked_by"], ["contested_one"])
        self.assertIn("contested_one", total["why"])
        self.assertIn("CONTESTED", total["why"])

    def test_a_total_over_agreeing_figures_computes(self):
        """THE CONTROL. Without it the refusal above passes against a `total`
        that can never compute anything at all."""
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : 5")
        self.doc("B.txt", "read at 2026-10-16T11:00:00Z", "", "COUNT : 5")
        self.doc("C.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : 7")
        self.doc("D.txt", "read at 2026-10-16T11:00:00Z", "", "COUNT : 7")
        data = self.read(
            figure(key="five",
                   claims=(claim("A", "A.txt", 3), claim("B", "B.txt", 3))),
            figure(key="seven",
                   claims=(claim("C", "C.txt", 3), claim("D", "D.txt", 3))))
        total = contested.total(data, ["five", "seven"])
        self.assertTrue(total["computed"])
        self.assertEqual(total["value"], 12)
        self.assertEqual(total["addends"], 2)

    def test_an_unknown_figure_blocks_it_too(self):
        data = self.read(figure(key="gone",
                                claims=(claim("x", "nope.txt", 1),)))
        total = contested.total(data, ["gone"])
        self.assertFalse(total["computed"])
        self.assertEqual(total["blocked_by"], ["gone"])

    def test_a_non_numeric_figure_is_refused_by_name(self):
        """`BEHIND/contained, not ahead` is a perfectly good answer and is
        not an addend. Refused, and named as not-a-number rather than as a
        contest, because they need different repairs."""
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : no")
        self.doc("B.txt", "read at 2026-10-16T11:00:00Z", "", "COUNT : no")
        data = self.read(figure(key="words", claims=(
            claim("A", "A.txt", 3, pattern=r"COUNT\s*:\s*(?P<value>\w+)"),
            claim("B", "B.txt", 3,
                  pattern=r"COUNT\s*:\s*(?P<value>\w+)"))))
        total = contested.total(data, ["words"])
        self.assertFalse(total["computed"])
        self.assertEqual(total["not_numeric"], ["words"])
        self.assertEqual(total["blocked_by"], [])

    def test_a_figure_this_page_does_not_have_is_refused(self):
        data = self.read(figure(key="five", claims=()))
        total = contested.total(data, ["nothing_like_this"])
        self.assertFalse(total["computed"])
        self.assertEqual(total["missing"], ["nothing_like_this"])

    def test_a_total_over_single_authority_rows_says_so(self):
        """It computes - a lone reading renders as itself - and the rows it
        rests on are named as unconfirmed, so a reader is not told the sum
        was corroborated."""
        self.doc("A.txt", "read at 2026-10-16T09:00:00Z", "", "COUNT : 5")
        data = self.read(figure(key="five",
                                claims=(claim("A", "A.txt", 3),)))
        total = contested.total(data, ["five"])
        self.assertTrue(total["computed"])
        self.assertEqual(total["value"], 5)
        self.assertEqual(total["unconfirmed"], ["five"])


# ------------------------------------------------------------- the page itself


class ThePageShowsBothValues(Estate, unittest.TestCase):
    """EXISTENCE IS NOT FUNCTION. A reader computing a contest correctly, in
    front of a page that prints one number, is this repository's recurring
    defect."""

    def rendered(self, first="101", second="38"):
        data = api.contested_figures(root=self.root) \
            if False else None
        row = self.two_documents(first, second)
        data = contested.contested(root=self.root, figures=(row,))
        data["recommendations"] = []
        data["worked_total"] = contested.total(
            data, [item["key"] for item in data["figures"]])
        data["unrecognised_verdicts"] = []
        data["unrecognised_citation_states"] = []
        return data, pages.contested_figures(data)

    def test_both_numbers_are_on_the_page(self):
        _data, html = self.rendered()
        self.assertIn(">101<", html)
        self.assertIn(">38<", html)
        self.assertIn("CONTESTED", html)

    def test_the_refusal_is_rendered_as_executed(self):
        """Not a paragraph promising a refusal - the sum attempted and
        declining, with the row that blocked it named."""
        _data, html = self.rendered()
        self.assertIn("REFUSED", html)
        self.assertIn("no arithmetic on this page uses one", html)
        self.assertIn("none at all", html)

    def test_an_agreeing_figure_renders_a_plain_value(self):
        """Asserted on the VERDICT TAG, not on the word anywhere on the page.
        `CONTESTED` is also a tile label in the head, which is there whether
        the count is 0 or 3 - so a bare `assertNotIn` here would fail on a
        correctly agreeing page, and would have."""
        _data, html = self.rendered("2681", "2681")
        self.assertIn('<span class="tag pass">AGREED</span>', html)
        self.assertNotIn('<span class="tag block">CONTESTED</span>', html)
        # And the tile that counts them says zero rather than vanishing.
        self.assertIn(">0</div><div class=\"k\">CONTESTED</div>", html)

    def test_no_authority_path_goes_into_a_code_chip(self):
        """He pastes fenced content as commands. The path is prose."""
        _data, html = self.rendered()
        chips = re.findall(r"<code>(.*?)</code>", html, re.S)
        for chip in chips:
            self.assertNotIn(".txt", chip)
        self.assertIn("read from A.txt:3", html)

    def test_an_unconfigured_estate_is_not_an_empty_table(self):
        data = contested.contested(root=None, figures=())
        if data["state"] == "present":                    # pragma: no cover
            self.skipTest("the environment names an estate")
        html = pages.contested_figures(data)
        self.assertIn("not available", html)
        self.assertIn("NOT", html)


class TheReaderWritesNothing(Estate, unittest.TestCase):
    """It opens the operator's standing documents. It must not be able to
    touch one: two are under an mtime guard and one outranks every brief."""

    def test_a_render_changes_no_byte_and_no_mtime(self):
        row = self.two_documents("101", "38")
        before = {}
        for name in ("A.txt", "B.txt"):
            path = os.path.join(self.root, name)
            with open(path, "rb") as handle:
                before[name] = (handle.read(), os.path.getmtime(path))
        data = contested.contested(root=self.root, figures=(row,))
        data["recommendations"] = contested.recommendations(data)
        data["worked_total"] = contested.total(data, ["count"])
        data["unrecognised_verdicts"] = []
        data["unrecognised_citation_states"] = []
        pages.contested_figures(data)
        contested.describe(data)
        self.assertEqual(sorted(os.listdir(self.root)), ["A.txt", "B.txt"])
        for name in ("A.txt", "B.txt"):
            path = os.path.join(self.root, name)
            with open(path, "rb") as handle:
                self.assertEqual(handle.read(), before[name][0])
            self.assertEqual(os.path.getmtime(path), before[name][1])


class TheRouteIsOnTheApp(unittest.TestCase):
    """A page nothing serves is a page nobody reads."""

    def test_the_route_is_registered_and_super_admin(self):
        import inspect

        from src.web import app as app_module
        source = inspect.getsource(app_module)
        self.assertIn('path == "/admin/contested"', source)
        where = source.index('path == "/admin/contested"')
        # The guard inside the 400 characters after the branch, which is the
        # window `test_every_admin_route_is_super_admin` reads.
        self.assertIn("_require_super_admin", source[where:where + 400])
        self.assertIn("pages.contested_figures", source[where:where + 400])



# ------------------------------------------------------------------------- C6
#
# A BROKEN QUOTE IS TWO SITUATIONS AND THE PAGE RENDERED THEM AS ONE.
# Found by re-reading this page's own live output at 21:50 on 2026-10-16:
# between `0280` landing and that minute, the scheduled run applied the
# `local_master` recommendation to BOTH its places, and the page went on
# offering the edit with a red `CITATION BROKEN` chip beside it. Safe - the
# broken quote took no value and named no line - and still the wrong reading,
# on a page whose entire purpose is that a reader can tell one state from
# another.


class RecommendationStanding(Estate, unittest.TestCase):
    """SATISFIED needs TWO searches to come back empty, and nothing else
    reaches it. The quote says WHERE to edit; the defect pattern says whether
    there is anything left to edit; absence of the first is never read as
    absence of the second."""

    def rec(self, **over):
        entry = {"figure": "count", "path": "DOC.md", "line": 3,
                 "now": "it says the wrong thing",
                 "change": "say the right thing instead",
                 "defect": r"the wrong thing",
                 "places": 1, "owner": "the operator"}
        entry.update(over)
        return entry

    def standing(self, entry):
        saved = contested.RECOMMENDATIONS
        contested.RECOMMENDATIONS = (entry,)
        try:
            return contested.recommendations({"root": self.root})[0]
        finally:
            contested.RECOMMENDATIONS = saved

    def test_a_quote_still_in_the_document_stands(self):
        """Present text outranks every argument about it, and the defect
        pattern is not even consulted - so a row whose quote is there STANDS
        even when the defect pattern would not match."""
        self.doc("DOC.md", "one", "two", "it says the wrong thing")
        row = self.standing(self.rec(defect=r"NOTHING THAT MATCHES"))
        self.assertEqual(row["standing"], contested.STANDS)
        self.assertEqual(row["quote_state"], contested.READ)
        self.assertTrue(row["recommends_an_edit"])
        self.assertEqual(row["quote_found_line"], 3)

    def test_both_searches_empty_appears_satisfied(self):
        """The real live case: the quote is gone and so is the wording the
        change existed to remove."""
        self.doc("DOC.md", "one", "two", "it now says the right thing")
        row = self.standing(self.rec())
        self.assertEqual(row["quote_state"], contested.BROKEN)
        self.assertIs(row["defect_present"], False)
        self.assertEqual(row["standing"], contested.SATISFIED)
        self.assertFalse(row["recommends_an_edit"])
        # It never claims to have watched the change happen, and it says
        # what it searched for so the reader can judge the search.
        self.assertIn("did NOT watch", row["standing_why"])
        self.assertEqual(row["searched_for"], r"the wrong thing")

    def test_a_gone_quote_with_the_defect_still_there_is_not_satisfied(self):
        """THE CONTROL ON C6. The quote moved out of reach - reworded, or the
        citation was always wrong - while the defect is still in the
        document. Satisfied is the one state that must not fire here."""
        self.doc("DOC.md", "one", "two",
                 "a sentence carrying the wrong thing, worded differently")
        row = self.standing(self.rec())
        self.assertEqual(row["quote_state"], contested.BROKEN)
        self.assertIs(row["defect_present"], True)
        self.assertEqual(row["standing"], contested.RELOCATE)
        self.assertTrue(row["recommends_an_edit"])
        self.assertEqual(row["defect_lines"], ["DOC.md:3"])

    def test_a_document_quoting_the_defect_is_not_satisfied(self):
        """MEASURED, NOT IMAGINED. `CONTINUITY.md` still contains
        'divergence unexplained' at :856 - itself QUOTING the standing rules
        in order to say they are wrong. A loose pattern matches that
        correcting quotation and reports the defect present. That is the
        wrong answer in the SAFE direction, and the precision of the pattern
        is therefore a measurement rather than a matter of taste.

        Shaped on the live case: the full quote is GONE from the document,
        while a loose word out of it survives in a sentence that exists to
        say the old wording was wrong. The first fixture I wrote put the
        whole quote inside the correcting sentence, and that row correctly
        read STANDS - present text outranks everything - which is a
        different situation and not this one."""
        self.doc("DOC.md", "one", "two",
                 "an earlier header was wrong about this and the log says so")
        loose = self.standing(self.rec(defect=r"wrong"))
        self.assertEqual(loose["quote_state"], contested.BROKEN)
        self.assertEqual(loose["standing"], contested.RELOCATE)
        self.assertEqual(loose["defect_lines"], ["DOC.md:3"])
        # The precise form - the ASSERTION rather than any mention of it -
        # is absent, and only then does the row read satisfied. Same bytes,
        # same quote state, different pattern.
        precise = self.standing(self.rec(defect=r"it says the wrong thing"))
        self.assertEqual(precise["quote_state"], contested.BROKEN)
        self.assertEqual(precise["standing"], contested.SATISFIED)

    def test_an_entry_naming_no_defect_is_undetermined(self):
        """An absent pattern is a refusal. Nothing to search for cannot mean
        the search came back empty."""
        self.doc("DOC.md", "one", "two", "it now says the right thing")
        row = self.standing(self.rec(defect=None))
        self.assertEqual(row["quote_state"], contested.BROKEN)
        self.assertIs(row["defect_present"], None)
        self.assertEqual(row["standing"], contested.UNDETERMINED)
        self.assertTrue(row["recommends_an_edit"])
        self.assertIn("never reported as the change having been made",
                      row["standing_why"])

    def test_an_unreadable_document_is_undetermined(self):
        """Invariant 0 on this page: an authority that cannot be read is
        UNKNOWN, and UNKNOWN never becomes 'somebody fixed it'."""
        row = self.standing(self.rec(path="NOT-THERE.md"))
        self.assertEqual(row["quote_state"], contested.UNREADABLE)
        self.assertEqual(row["standing"], contested.UNDETERMINED)
        self.assertTrue(row["recommends_an_edit"])

    def test_a_two_place_change_is_not_satisfied_by_one_place(self):
        """The live `local_master` row is a TWO-place change. One place clean
        and the other still carrying the wording is not a change that has
        been made."""
        self.doc("DOC.md", "one", "two", "it now says the right thing")
        self.doc("OTHER.md", "still it says the wrong thing here")
        row = self.standing(self.rec(also=("OTHER.md",), places=2))
        self.assertIs(row["defect_present"], True)
        self.assertEqual(row["standing"], contested.RELOCATE)
        self.assertEqual(row["defect_in"], ["OTHER.md"])
        # And with the second place cleaned too it reads satisfied - so the
        # assertion above is about the second place and not about the shape
        # of the fixture.
        self.doc("OTHER.md", "this one is fine now")
        self.assertEqual(self.standing(self.rec(also=("OTHER.md",),
                                                places=2))["standing"],
                         contested.SATISFIED)

    def test_an_unreadable_second_place_is_undetermined(self):
        """A second place that cannot be opened cannot license SATISFIED for
        the row, even when the first place is clean."""
        self.doc("DOC.md", "one", "two", "it now says the right thing")
        row = self.standing(self.rec(also=("GONE.md",), places=2))
        self.assertIs(row["defect_present"], None)
        self.assertEqual(row["standing"], contested.UNDETERMINED)

    def test_every_standing_has_a_word_and_a_colour(self):
        """Three vocabularies on this page now, and a standing the module
        has not named must arrive at the renderer as unrecognised rather
        than coloured by whichever map answers first."""
        for state in (contested.STANDS, contested.SATISFIED,
                      contested.RELOCATE, contested.UNDETERMINED):
            self.assertIn(state, contested.RECOMMENDATION_TEXT)
            self.assertIn(state, pages.STANDING_KIND)
        # SATISFIED is the only green one: a standing recommendation is
        # amber, a lost line with the defect still there is red, and an
        # unreadable document is amber rather than green.
        self.assertEqual(pages.STANDING_KIND[contested.SATISFIED], "pass")
        self.assertEqual(pages.STANDING_KIND[contested.RELOCATE], "block")
        self.assertNotEqual(pages.STANDING_KIND[contested.UNDETERMINED],
                            "pass")
        # And the two vocabularies share no word, so a reader cannot confuse
        # a citation state for a standing.
        self.assertFalse(set(contested.RECOMMENDATION_TEXT)
                         & set(contested.CITATION_TEXT))

    def test_the_standing_is_rendered_on_the_page(self):
        """A column computed correctly that nothing renders is this
        repository's recurring defect, so the chip is asserted on the HTML."""
        self.doc("DOC.md", "one", "two", "it now says the right thing")
        row = self.two_documents("101", "38")
        data = contested.contested(root=self.root, figures=(row,))
        saved = contested.RECOMMENDATIONS
        contested.RECOMMENDATIONS = (self.rec(),)
        try:
            data["recommendations"] = contested.recommendations(data)
        finally:
            contested.RECOMMENDATIONS = saved
        data["worked_total"] = contested.total(data, ["count"])
        data["unrecognised_verdicts"] = []
        data["unrecognised_citation_states"] = []
        html = pages.contested_figures(data)
        self.assertIn("APPEARS SATISFIED", html)
        self.assertIn("Is it still needed", html)
        self.assertIn("searched for: the wrong thing", html)

if __name__ == "__main__":
    unittest.main()
