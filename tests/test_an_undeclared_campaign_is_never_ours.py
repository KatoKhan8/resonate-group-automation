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


class TheShippedDeclarationIsExactlyWhatTheOperatorDecided(unittest.TestCase):
    """The real config, as committed.

    OPERATOR DECISION, Zvonimir, 2026-10-02: every campaign carrying rows in
    the provider-write (perform) ledger is Resonate OS. 274, 327, 328 and 352
    are NOT - they carry zero perform rows and stay operator-declared internal.
    Derived from `docs/CAMPAIGN-TABLE-2026-10-02.md`: 40 campaigns, every one
    resolved to a canonical row, zero orphans.

    This test exists so that a FORTY-FIRST entry added by inference rather than
    by a new operator decision fails here. If the operator declares another
    campaign, update these numbers in the same commit and name the decision -
    that is the whole point of pinning an exact set rather than a floor.
    """

    #: The provider ids the operator declared on 2026-10-02.
    BISON = {"481", "491", "497", "500"}
    HEYREACH_COUNT = 36
    #: Declared internal by the operator on 2026-10-01. Never OS.
    NOT_OURS = ("274", "327", "328", "352")

    def setUp(self):
        self.real = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "resonate-os-campaigns.txt")
        self.assertTrue(os.path.isfile(self.real), self.real)
        self.declared = osattribution.declared(self.real)

    def test_the_declaration_holds_exactly_forty_campaigns(self):
        self.assertEqual(
            40, len(self.declared),
            "the operator declared 40 campaigns on 2026-10-02. A different "
            "count means somebody added or removed one - say whose decision "
            "that was, in the commit that changes this number.")

    def test_the_four_bison_campaigns_are_the_declared_ones(self):
        self.assertEqual(
            self.BISON, {c for p, c in self.declared if p == "bison"})

    def test_thirty_six_heyreach_campaigns_are_declared(self):
        self.assertEqual(
            self.HEYREACH_COUNT,
            len([1 for p, _ in self.declared if p == "heyreach"]))

    def test_the_operator_declared_internal_campaigns_are_not_ours(self):
        """The load-bearing assertion. These four carry zero perform rows and
        are the operator's internal campaigns; declaring one of them OS would
        make its members look like people we have contacted."""
        for campaign in self.NOT_OURS:
            self.assertEqual(
                osattribution.UNKNOWN,
                osattribution.attribution("bison", campaign,
                                          file_path=self.real),
                f"bison {campaign} must never read as ours")

    def test_a_campaign_nobody_declared_is_still_unknown(self):
        self.assertEqual(
            osattribution.UNKNOWN,
            osattribution.attribution("bison", "999999", file_path=self.real))

    def test_every_declared_entry_resolves_as_ours(self):
        """A control on the test itself: if `declared` returned an empty set
        this class would pass vacuously, so assert the positive direction too."""
        self.assertTrue(self.declared)
        for provider, campaign in self.declared:
            self.assertEqual(
                osattribution.OURS,
                osattribution.attribution(provider, campaign,
                                          file_path=self.real))


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
