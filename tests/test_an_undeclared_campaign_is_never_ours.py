"""The declared-OS list: absence is UNKNOWN, in either direction.

Every test here is written so that it FAILS if the module starts guessing.
The failure mode this guards against is not a crash - it is a campaign nobody
declared being counted as ours, which would inflate our measured activity and
would mark a genuinely fresh lead as legacy_touched.
"""
import os
import tempfile
import unittest

from src import osattribution


def write(lines):
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8", newline="\n")
    handle.write("\n".join(lines) + "\n")
    handle.close()
    return handle.name


class AMissingFileIsAnEmptyDeclaration(unittest.TestCase):
    def test_a_missing_file_is_empty_rather_than_an_error(self):
        missing = os.path.join(tempfile.mkdtemp(), "not-written-yet.txt")
        self.assertEqual(osattribution.declared(missing), set())

    def test_and_nothing_is_ours_under_an_empty_declaration(self):
        missing = os.path.join(tempfile.mkdtemp(), "not-written-yet.txt")
        self.assertEqual(
            osattribution.attribution("bison", "274", file_path=missing),
            osattribution.UNKNOWN)


class TheShippedFileIsEmptyUntilTheOperatorMarksIt(unittest.TestCase):
    """The real config, as committed. If somebody fills it in by inference
    rather than by operator decision, this test is the one that notices."""

    def test_the_committed_declaration_is_still_empty(self):
        real = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "resonate-os-campaigns.txt")
        self.assertTrue(os.path.isfile(real), real)
        self.assertEqual(
            osattribution.declared(real), set(),
            "config/resonate-os-campaigns.txt is no longer empty. Only the "
            "operator declares a campaign ours. If this is a real operator "
            "decision, update this test in the same commit and say whose "
            "decision it was.")


class ADeclarationIsReadExactly(unittest.TestCase):
    def test_a_declared_campaign_is_ours(self):
        path = write(["# comment", "", "bison 274  # declared", "heyreach 599020"])
        self.assertEqual(osattribution.declared(path),
                         {("bison", "274"), ("heyreach", "599020")})
        self.assertEqual(
            osattribution.attribution("bison", "274", file_path=path),
            osattribution.OURS)

    def test_an_undeclared_campaign_in_a_populated_file_is_unknown(self):
        path = write(["bison 274"])
        self.assertEqual(
            osattribution.attribution("bison", "999999", file_path=path),
            osattribution.UNKNOWN)

    def test_the_other_provider_is_not_the_same_campaign(self):
        """274 on bison says nothing about 274 on heyreach."""
        path = write(["bison 274"])
        self.assertEqual(
            osattribution.attribution("heyreach", "274", file_path=path),
            osattribution.UNKNOWN)

    def test_an_integer_id_reads_the_same_as_its_string(self):
        path = write(["bison 274"])
        self.assertEqual(
            osattribution.attribution("bison", 274, file_path=path),
            osattribution.OURS)


class AnUnreadableLineRefusesRatherThanSkips(unittest.TestCase):
    """A silently skipped line is the worst outcome: the operator believes a
    campaign is declared and it is not."""

    def test_a_one_word_line_refuses(self):
        path = write(["bison"])
        with self.assertRaises(osattribution.MalformedDeclaration):
            osattribution.declared(path)

    def test_an_unknown_provider_refuses(self):
        path = write(["emailbison 274"])
        with self.assertRaises(osattribution.MalformedDeclaration):
            osattribution.declared(path)

    def test_a_canonical_row_id_refuses_because_it_is_the_wrong_namespace(self):
        path = write(["bison productive-email-batch1-jakov"])
        with self.assertRaises(osattribution.MalformedDeclaration):
            osattribution.declared(path)


class TheLedgerWinsWithoutADeclaration(unittest.TestCase):
    def test_the_ledger_claiming_it_makes_it_ours_with_no_entry(self):
        empty = write(["# nothing declared"])
        self.assertEqual(
            osattribution.attribution("bison", "497", ledger_says="resonate_os",
                                      file_path=empty),
            osattribution.OURS)

    def test_the_ledger_calling_it_internal_makes_it_not_ours(self):
        empty = write(["# nothing declared"])
        self.assertEqual(
            osattribution.attribution("bison", "327",
                                      ledger_says="resonate_internal",
                                      file_path=empty),
            osattribution.NOT_OURS)

    def test_a_ledger_that_could_not_answer_is_not_a_no(self):
        """None means "not asked" or "could not say". It must not read as
        NOT_OURS, because that would hide a send we made."""
        empty = write(["# nothing declared"])
        self.assertEqual(
            osattribution.attribution("bison", "327", ledger_says=None,
                                      file_path=empty),
            osattribution.UNKNOWN)

    def test_a_declaration_outranks_an_unknown_ledger(self):
        path = write(["bison 327"])
        self.assertEqual(
            osattribution.attribution("bison", "327", ledger_says=None,
                                      file_path=path),
            osattribution.OURS)


class ThereIsNoBooleanOnThisSurface(unittest.TestCase):
    """UNKNOWN must not be collapsible by accident. A caller writing
    `if attribution(...)` would treat every verdict as true, so the three
    verdicts are distinct non-empty strings and none of them is a bool."""

    def test_the_three_verdicts_are_distinct(self):
        self.assertEqual(
            len({osattribution.OURS, osattribution.NOT_OURS,
                 osattribution.UNKNOWN}), 3)

    def test_no_verdict_is_a_boolean(self):
        for verdict in (osattribution.OURS, osattribution.NOT_OURS,
                        osattribution.UNKNOWN):
            self.assertNotIsInstance(verdict, bool)
            self.assertIsInstance(verdict, str)


class AMissingIdentifierIsUnknown(unittest.TestCase):
    def test_no_campaign_id_is_unknown_not_ours(self):
        path = write(["bison 274"])
        self.assertEqual(
            osattribution.attribution("bison", None, file_path=path),
            osattribution.UNKNOWN)

    def test_no_provider_is_unknown_not_ours(self):
        path = write(["bison 274"])
        self.assertEqual(
            osattribution.attribution(None, "274", file_path=path),
            osattribution.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
