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


# ------------------------------------------------------------------------- C7
#
# ONE PATTERN FOR A CHANGE WITH SEVERAL CLAUSES, AND THE PATTERNED CLAUSE
# LICENSED THE REST. `0300` measured this on the real bytes of the continuity
# log and filed it rather than building it, because the paragraph-shaped gap
# filed beside it had zero callers. This one has one the day it is written:
# entry 3's change has TWO clauses - correct the figure, and drop the
# inference that the worktree is gone - and satisfying either licensed
# SATISFIED for both.
#
# AND THE SAME ENTRY CARRIED THE INDEPENDENCE DEFECT. Its quote needle is
# `now.split(",")[0]`, which was `it now holds 64 files`, which was its
# `defect` pattern character for character over the same single file. Two
# searches wearing one name, so RELOCATE - quote gone, defect present - was
# unreachable for it by construction.


class ClausePatterns(Estate, unittest.TestCase):
    """SATISFIED requires EVERY clause of a change to come back empty.

    A change with two clauses is not made because one of them was. The list
    is the registry's way of saying so, and a single-pattern entry keeps its
    exact previous semantics so the two live single-clause rows do not move.
    """

    def rec(self, **over):
        entry = {"figure": "count", "path": "DOC.md", "line": 3,
                 "now": "it says the wrong thing",
                 "change": "say the right thing instead",
                 "defect": (r"the first wrong thing",
                            r"the second wrong thing"),
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

    def test_one_clause_left_is_not_satisfied(self):
        """THE CONTROL. Clause A is gone, clause B is still in the document.
        A reader must not be told the change was made."""
        self.doc("DOC.md", "one", "two",
                 "the second wrong thing is still here")
        row = self.standing(self.rec())
        self.assertEqual(row["quote_state"], contested.BROKEN)
        self.assertIs(row["defect_present"], True)
        self.assertEqual(row["standing"], contested.RELOCATE)
        self.assertTrue(row["recommends_an_edit"])
        # Each clause is reported on its own, so the reader is told WHICH
        # clause survived rather than only that something did.
        self.assertEqual([c["pattern"] for c in row["clauses"]],
                         [r"the first wrong thing", r"the second wrong thing"])
        self.assertEqual([c["present"] for c in row["clauses"]],
                         [False, True])
        self.assertEqual(row["clauses"][1]["lines"], ["DOC.md:3"])
        self.assertEqual(row["clauses"][0]["lines"], [])

    def test_the_other_clause_left_is_also_not_satisfied(self):
        """Symmetry, so the test above is about the clause and not about
        which position in the list it happens to occupy."""
        self.doc("DOC.md", "one", "two",
                 "the first wrong thing is still here")
        row = self.standing(self.rec())
        self.assertIs(row["defect_present"], True)
        self.assertEqual(row["standing"], contested.RELOCATE)
        self.assertEqual([c["present"] for c in row["clauses"]],
                         [True, False])

    def test_every_clause_empty_is_satisfied(self):
        """Both clauses gone and the quote gone is the only state that
        reaches the page's one green cell."""
        self.doc("DOC.md", "one", "two", "it now says the right thing")
        row = self.standing(self.rec())
        self.assertEqual(row["quote_state"], contested.BROKEN)
        self.assertIs(row["defect_present"], False)
        self.assertEqual(row["standing"], contested.SATISFIED)
        self.assertFalse(row["recommends_an_edit"])
        self.assertEqual([c["present"] for c in row["clauses"]],
                         [False, False])

    def test_a_single_pattern_entry_keeps_its_exact_semantics(self):
        """No new behaviour for the shape that already existed. A string
        `defect` is one clause, `searched_for` is that string unchanged, and
        the aggregate fields carry the same values they always did."""
        self.doc("DOC.md", "one", "two",
                 "a sentence carrying the wrong thing, worded differently")
        row = self.standing(self.rec(defect=r"the wrong thing"))
        self.assertEqual(row["standing"], contested.RELOCATE)
        self.assertEqual(row["searched_for"], r"the wrong thing")
        self.assertEqual(row["defect_lines"], ["DOC.md:3"])
        self.assertEqual(row["defect_in"], ["DOC.md"])
        self.assertEqual(len(row["clauses"]), 1)

    def test_an_unreadable_place_refuses_for_every_clause(self):
        """Fail closed, unchanged: a place that cannot be opened cannot
        license SATISFIED, and it does not license it for the clause that
        happened to be clean in the place that did open either."""
        self.doc("DOC.md", "one", "two", "it now says the right thing")
        row = self.standing(self.rec(also=("GONE.md",), places=2))
        self.assertIs(row["defect_present"], None)
        self.assertEqual(row["standing"], contested.UNDETERMINED)
        self.assertTrue(all(c["present"] is None for c in row["clauses"]))

    def test_an_empty_clause_list_is_undetermined(self):
        """An absent pattern is a refusal and so is a list of none. Nothing
        to search for cannot mean every search came back empty - which is
        exactly what `all()` over an empty list would say."""
        self.doc("DOC.md", "one", "two", "it now says the right thing")
        row = self.standing(self.rec(defect=()))
        self.assertIs(row["defect_present"], None)
        self.assertEqual(row["standing"], contested.UNDETERMINED)
        self.assertEqual(row["clauses"], [])

    def test_no_new_standing_vocabulary(self):
        """`0266`'s rule. The clause list answers with the four words the
        page already renders and adds none."""
        self.assertEqual(set(contested.RECOMMENDATION_TEXT),
                         {contested.STANDS, contested.SATISFIED,
                          contested.RELOCATE, contested.UNDETERMINED})


class EntryThreeSearchesTwice(Estate, unittest.TestCase):
    """The live continuity-log entry, whose two searches were one search.

    Measured by `0300`: the quote needle and the `defect` pattern were the
    same string over the same single file, so RELOCATE was unreachable for
    this row by construction. The entry is addressed here, not the mechanism
    only - a mechanism with no entry using it is this repository's named
    defect.
    """

    def entry(self):
        for item in contested.RECOMMENDATIONS:
            if item["path"].startswith("CONTINUITY-LOG-"):
                return item
        self.fail("no continuity-log entry in the registry")

    def standing(self, entry):
        saved = contested.RECOMMENDATIONS
        contested.RECOMMENDATIONS = (entry,)
        try:
            return contested.recommendations({"root": self.root})[0]
        finally:
            contested.RECOMMENDATIONS = saved

    def clauses(self, entry):
        defect = entry.get("defect")
        return [defect] if isinstance(defect, str) else list(defect or ())

    def test_entry_three_carries_more_than_one_clause(self):
        """Its change has two clauses in its own words: correct the figure,
        and drop the inference. The registry now says so."""
        self.assertGreaterEqual(len(self.clauses(self.entry())), 2)

    def test_no_clause_is_the_quote_needle(self):
        """THE INDEPENDENCE INVARIANT, asserted on the entry's data rather
        than on the mechanism's wording. The needle is what `recommendations`
        actually searches for, so it is derived the same way here."""
        entry = self.entry()
        needle = entry["now"].split(",")[0]
        for pattern in self.clauses(entry):
            self.assertNotEqual(pattern, needle)
            # Nor a superstring of it: a clause that contains the needle
            # cannot be present when the needle is absent, which is the
            # state RELOCATE is.
            self.assertNotIn(needle, pattern)

    def test_relocate_is_reachable_for_entry_three(self):
        """The reachability proof, on a synthetic document at the entry's own
        relative path - the real one is a registry target and is never
        written by this lane.

        The quote is reworded away; the inference the change also drops is
        still there. Before the clause list this row could not reach
        RELOCATE from any document.
        """
        entry = self.entry()
        self.doc(entry["path"], "a heading",
                 "name and that worktree is **gone**: it holds few files, so")
        row = self.standing(entry)
        self.assertEqual(row["quote_state"], contested.BROKEN)
        self.assertIs(row["defect_present"], True)
        self.assertEqual(row["standing"], contested.RELOCATE)

    def test_entry_three_is_satisfied_only_when_both_clauses_go(self):
        """And the control on the test above: the same reworded line with
        the inference dropped too reads satisfied, so RELOCATE there was
        about the surviving clause and not about the fixture's shape."""
        entry = self.entry()
        self.doc(entry["path"], "a heading",
                 "name, and that worktree is present: it holds 64 files in "
                 "its top level and 2,681 in the tree, so")
        row = self.standing(entry)
        self.assertEqual(row["quote_state"], contested.BROKEN)
        self.assertIs(row["defect_present"], False)
        self.assertEqual(row["standing"], contested.SATISFIED)


class TheClausesAreRendered(Estate, unittest.TestCase):
    """A clause computed correctly that nothing prints is the defect this
    repository keeps rediscovering, so both consumers are asserted."""

    def rec(self):
        return {"figure": "count", "path": "DOC.md", "line": 3,
                "now": "it says the wrong thing",
                "change": "say the right thing instead",
                "defect": (r"the first wrong thing",
                           r"the second wrong thing"),
                "places": 1, "owner": "the operator"}

    def test_describe_names_every_clause_and_its_state(self):
        self.doc("DOC.md", "one", "two",
                 "the second wrong thing is still here")
        row = self.two_documents("101", "38")
        data = contested.contested(root=self.root, figures=(row,))
        saved = contested.RECOMMENDATIONS
        contested.RECOMMENDATIONS = (self.rec(),)
        try:
            text = contested.describe(data)
        finally:
            contested.RECOMMENDATIONS = saved
        self.assertIn("the first wrong thing", text)
        self.assertIn("the second wrong thing", text)
        # And which of the two survived, not merely that both were searched.
        self.assertIn("clause 2 of 2", text)

    def test_the_page_names_every_clause(self):
        self.doc("DOC.md", "one", "two",
                 "the second wrong thing is still here")
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
        self.assertIn("the first wrong thing", html)
        self.assertIn("the second wrong thing", html)
        self.assertIn("every clause must be empty", html)


# ------------------------------------------------ a target that crosses a line
#
# `0300` measured this page's ONLY fail-open and declined to build the fix,
# because the shape had no caller. The caller is the defect itself: the search
# is `pattern.search(line)` over `splitlines()`, so a target wrapped over two
# lines cannot match, and the page read that unmatchable clause as a clause
# somebody had removed. Three fixture forms, the wording in ONE form each:
#
#   on one line            RELOCATE                correct, and loud
#   wrapped over two       APPEARS SATISFIED       the wrong green
#   no pattern named       UNDETERMINED            correct refusal
#
# The middle row is the one these tests exist for. It is the same family as a
# check that fires correctly while the gate reading it reports clean: the only
# green cell this page has, over a document that still carries the prose.
#
# AND THE ANTI-WIDENING CONTROL IS HALF OF THE CLASS. A guard that refused
# every absence would close the fail-open and destroy the state, so a target
# that is genuinely nowhere - in neither form - must still reach SATISFIED.


class AWrappedTargetNeverReadsSatisfied(Estate, unittest.TestCase):
    """A clause whose match would cross a line break is NOT absent.

    The line walk can only ever answer "I did not find it on any one line",
    and for a wrapped target that answer is not a proof of absence. So the
    negative is checked against the place as a soft-wrapped reader presents
    it, and a hit there - with no hit on any single line - is the refusal
    this registry already has for a shape it cannot express.
    """

    TARGET = r"the worktree is gone"

    def rec(self, **over):
        entry = {"figure": "count", "path": "DOC.md", "line": 3,
                 "now": "it says the wrong thing",
                 "change": "say the right thing instead",
                 "defect": self.TARGET, "places": 1,
                 "owner": "the operator"}
        entry.update(over)
        return entry

    def standing(self, entry):
        saved = contested.RECOMMENDATIONS
        contested.RECOMMENDATIONS = (entry,)
        try:
            return contested.recommendations({"root": self.root})[0]
        finally:
            contested.RECOMMENDATIONS = saved

    # ------------------------------------------------- the three 0300 forms

    def test_the_one_line_form_is_unchanged(self):
        """FORM 1, and the control on the next test: the same wording on one
        line still RELOCATEs, so a refusal there is about the line break and
        not about anything else in the fixture."""
        self.doc("DOC.md", "a heading", "a paragraph",
                 "and so the worktree is gone, which is")
        row = self.standing(self.rec())
        self.assertEqual(row["quote_state"], contested.BROKEN)
        self.assertIs(row["defect_present"], True)
        self.assertEqual(row["standing"], contested.RELOCATE)
        self.assertEqual(row["clauses"][0]["lines"], ["DOC.md:3"])

    def test_the_wrapped_form_is_not_satisfied(self):
        """FORM 2. THE FAIL-OPEN. The same wording, wrapped over two lines,
        reached APPEARS SATISFIED with the prose still in the document."""
        self.doc("DOC.md", "a heading", "a paragraph",
                 "and so the worktree is", "gone, which is")
        row = self.standing(self.rec())
        self.assertEqual(row["quote_state"], contested.BROKEN)
        self.assertNotEqual(row["standing"], contested.SATISFIED)
        self.assertEqual(row["standing"], contested.UNDETERMINED)
        self.assertIs(row["defect_present"], None)
        self.assertIs(row["clauses"][0]["present"], None)
        # And it recommends an edit, because a row that concluded nothing
        # must not be a row a reader can close.
        self.assertTrue(row["recommends_an_edit"])

    def test_the_no_pattern_form_is_unchanged(self):
        """FORM 3. The refusal that was already correct, asserted here so
        this class carries all three forms and not only the one that
        moved."""
        self.doc("DOC.md", "a heading", "a paragraph",
                 "and so the worktree is gone, which is")
        row = self.standing(self.rec(defect=None))
        self.assertIs(row["defect_present"], None)
        self.assertEqual(row["standing"], contested.UNDETERMINED)
        self.assertEqual(row["clauses"], [])

    # ------------------------------------------------- it is not merely wide

    def test_a_target_that_is_genuinely_nowhere_is_still_satisfied(self):
        """THE ANTI-WIDENING CONTROL, and the reason the guard is a second
        search rather than a rule about patterns.

        A guard that refused every absence would have closed the fail-open
        by deleting the state. This document carries the wording in NEITHER
        form, so its absence IS provable from a line walk.
        """
        self.doc("DOC.md", "a heading", "a paragraph",
                 "and the worktree is present, holding its files, which is")
        row = self.standing(self.rec())
        self.assertEqual(row["quote_state"], contested.BROKEN)
        self.assertIs(row["defect_present"], False)
        self.assertEqual(row["standing"], contested.SATISFIED)
        self.assertIs(row["clauses"][0]["present"], False)
        self.assertFalse(row["recommends_an_edit"])

    def test_the_continuation_line_may_be_indented(self):
        """A wrapped markdown sentence is reflowed, so its continuation may
        carry leading whitespace. Joining the raw lines would leave two
        spaces where the pattern has one and the refusal would not fire -
        which would be the fail-open surviving behind the fix."""
        self.doc("DOC.md", "a heading", "a paragraph",
                 "  and so the worktree is", "      gone, which is")
        row = self.standing(self.rec())
        self.assertIs(row["defect_present"], None)
        self.assertEqual(row["standing"], contested.UNDETERMINED)

    def test_the_guard_defends_only_the_negative(self):
        """A clause found on a real line in one place is PRESENT, not
        unresolved, even where another place carries it wrapped. RELOCATE is
        the louder state and the guard must not quieten it into a refusal
        that names no line."""
        self.doc("DOC.md", "a heading", "a paragraph",
                 "and so the worktree is gone, which is")
        self.doc("OTHER.md", "the worktree is", "gone as well")
        row = self.standing(self.rec(also=("OTHER.md",), places=2))
        self.assertIs(row["clauses"][0]["present"], True)
        self.assertIs(row["defect_present"], True)
        self.assertEqual(row["standing"], contested.RELOCATE)
        self.assertEqual(row["clauses"][0]["lines"], ["DOC.md:3"])

    def test_one_wrapped_clause_refuses_the_whole_row(self):
        """`0310`'s rule in the other direction. SATISFIED needs every
        clause empty, so a row cannot be satisfied by the clauses whose
        absence it could prove while one clause's absence is unprovable."""
        self.doc("DOC.md", "a heading",
                 "the first wrong", "thing is wrapped here")
        row = self.standing(self.rec(
            defect=(r"the second wrong thing", r"the first wrong thing")))
        self.assertEqual([c["present"] for c in row["clauses"]],
                         [False, None])
        self.assertIs(row["defect_present"], None)
        self.assertEqual(row["standing"], contested.UNDETERMINED)

    def test_a_wrapped_clause_names_no_line(self):
        """It is a refusal, not a relocation. The aggregate fields a reader
        acts on stay empty, because this page did not find the target on a
        line and must not print one."""
        self.doc("DOC.md", "a heading", "a paragraph",
                 "and so the worktree is", "gone, which is")
        row = self.standing(self.rec())
        self.assertEqual(row["defect_lines"], [])
        self.assertEqual(row["defect_in"], [])
        self.assertEqual(row["clauses"][0]["lines"], [])

    def test_no_new_standing_vocabulary(self):
        """`0266`'s rule again. The wrapped case answers with a word the
        page already renders, and adds none."""
        self.assertEqual(set(contested.RECOMMENDATION_TEXT),
                         {contested.STANDS, contested.SATISFIED,
                          contested.RELOCATE, contested.UNDETERMINED})

    # -------------------------------------------------- and a reader sees it

    def test_describe_prints_the_refusal_not_the_green(self):
        """A refusal computed correctly that nothing prints is this
        repository's named defect, so the terminal consumer is asserted."""
        self.doc("DOC.md", "a heading", "a paragraph",
                 "and so the worktree is", "gone, which is")
        data = contested.contested(root=self.root,
                                   figures=(self.two_documents("101", "38"),))
        saved = contested.RECOMMENDATIONS
        contested.RECOMMENDATIONS = (self.rec(),)
        try:
            text = contested.describe(data)
        finally:
            contested.RECOMMENDATIONS = saved
        self.assertIn("UNDETERMINED - NOT SATISFIED", text)
        self.assertNotIn("APPEARS SATISFIED", text)

    def test_the_page_prints_the_refusal_not_the_green(self):
        """And the HTML consumer, which is the one a person reads.

        THE ASSERTION IS HEAD-LOCAL TO THE VERDICT TAG rather than over the
        page. A plain `assertNotIn("APPEARS SATISFIED")` fails on the panel's
        own standing footnote, which explains what the green cell means and
        must keep saying so - a test that cannot tell the page's explanation
        of a state from the page awarding it is a test about prose.
        """
        self.doc("DOC.md", "a heading", "a paragraph",
                 "and so the worktree is", "gone, which is")
        data = contested.contested(root=self.root,
                                   figures=(self.two_documents("101", "38"),))
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
        self.assertIn('<span class="tag warn">UNDETERMINED - NOT SATISFIED',
                      html)
        self.assertNotIn('<span class="tag pass">APPEARS SATISFIED', html)
        # AND THE CONTROL ON THAT PAIR OF STRINGS, so neither assertion is
        # passing because the markup it names is not how this page renders a
        # verdict at all. The same fixture with the target genuinely nowhere
        # must produce the exact green span the line above forbids.
        self.doc("DOC.md", "a heading", "a paragraph",
                 "and the worktree is present, holding its files, which is")
        saved = contested.RECOMMENDATIONS
        contested.RECOMMENDATIONS = (self.rec(),)
        try:
            data["recommendations"] = contested.recommendations(data)
        finally:
            contested.RECOMMENDATIONS = saved
        green = pages.contested_figures(data)
        self.assertIn('<span class="tag pass">APPEARS SATISFIED', green)


if __name__ == "__main__":
    unittest.main()
