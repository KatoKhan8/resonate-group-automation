"""The ONE OS authority: absence is UNKNOWN, and unreadable is not absence.

Every test here is written so that it FAILS if the module starts guessing. The
failure mode guarded against is not a crash - it is a campaign nobody recorded
being counted as ours, which inflates our measured activity and marks a
genuinely fresh lead as legacy_touched.

WHAT CHANGED ON 2026-10-02. These tests used to read a hand-maintained
declaration file, `config/resonate-os-campaigns.txt`. That file was measured to
be a strict SUBSET of `collision.os_campaign_ids()` /
`collision.our_heyreach_campaign_ids()` on both channels - 4 of 20 bison, 36 of
40 heyreach, and NOTHING in the file that the authority did not already hold -
so it was deleted and the authority is now the only answer. The properties
below are the same ones; only where the answer comes from moved.

WHY THE LEDGER IS A FIXTURE HERE RATHER THAN THE LIVE FILE. The authority reads
`work/campaigns.jsonl`, which is gitignored - so a test asserting the live
counts is green on the main checkout and red in every worktree, where `work/`
does not exist. That is a test whose colour reports the environment rather than
the code. So each class below writes a ledger holding the MEASURED ids into its
own throwaway store and asserts the real reader reads them back. A narrowing of
the reader - a status filter, a dropped field, an int/str mismatch - still fails
here, which is what the pinned counts are for.
"""
import json
import os
import tempfile
import unittest

from src import collision, osattribution, store

#: The bison campaigns the authority held when measured, 2026-10-02. Twenty.
BISON = (451, 481, 484, 485, 487, 489, 491, 492, 493, 494,
         495, 496, 497, 498, 500, 501, 503, 504, 505, 506)
#: The heyreach campaigns the authority held when measured, 2026-10-02. Forty.
HEYREACH = ("594061", "599020", "604869", "605487", "605732", "613724",
            "613725", "613726", "613727", "613728", "613729", "613730",
            "613731", "613732", "613733", "613734", "613735", "613736",
            "613737", "613738", "613739", "613740", "613741", "613742",
            "613744", "613746", "613747", "613748", "613749", "613750",
            "613751", "613752", "613753", "613754", "613755", "613756",
            "613757", "613761", "620829", "621824")
#: Declared internal by the operator, 2026-10-01. Never OS, on either channel.
INTERNAL = (274, 327, 328, 352)


class LedgerTest(unittest.TestCase):
    """Base: a throwaway store, and a ledger written into it on request."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))

    def write_ledger(self, bison=BISON, heyreach=HEYREACH):
        """The canonical rows the authority reads, and only the fields it reads.

        One row per provider campaign. `campaign_id` is present because
        `store.Snapshot` keys on it; nothing else in a real row is consulted by
        either half of the authority, so inventing more would be fiction.
        """
        rows = [{"campaign_id": f"fixture-bison-{c}", "bison_campaign_id": c,
                 "heyreach_campaign_id": None} for c in bison]
        rows += [{"campaign_id": f"fixture-heyreach-{c}",
                  "bison_campaign_id": None, "heyreach_campaign_id": c}
                 for c in heyreach]
        with open(os.path.join(self.tmp, "campaigns.jsonl"), "w",
                  encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
        return rows


class TheAuthorityHoldsExactlyWhatWasMeasured(LedgerTest):
    """The pinned counts. A narrowing of either reader fails here.

    If the operator records another campaign, update these numbers in the same
    commit and name the decision - that is the point of pinning an exact count
    rather than a floor.
    """

    def setUp(self):
        super().setUp()
        self.write_ledger()

    def test_the_bison_authority_holds_twenty_campaigns(self):
        ids, readable = collision.os_campaign_ids()
        self.assertTrue(readable)
        self.assertEqual(
            20, len(ids),
            "the bison authority held 20 campaigns when measured on "
            "2026-10-02. A different count means the reader narrowed or the "
            "fixture drifted - say which, in the commit that changes it.")

    def test_the_heyreach_authority_holds_forty_campaigns(self):
        ids, readable = collision.our_heyreach_campaign_ids()
        self.assertTrue(readable)
        self.assertEqual(40, len(ids))

    def test_487_489_and_493_are_in_the_authority(self):
        """THE CONTROL AGAINST A FUTURE NARROWING, and against this class
        passing vacuously on an empty read. 487 is the campaign `check_address`
        learned staging on; all three are live OS campaigns and a reader that
        stopped returning them would otherwise fail nothing here."""
        for campaign in (487, 489, 493):
            self.assertEqual(
                osattribution.OURS,
                osattribution.attribution("bison", campaign),
                f"bison {campaign} is an OS campaign and the authority must "
                f"still say so")

    def test_every_measured_campaign_resolves_as_ours_on_its_own_channel(self):
        for campaign in BISON:
            self.assertEqual(osattribution.OURS,
                             osattribution.attribution("bison", campaign))
        for campaign in HEYREACH:
            self.assertEqual(osattribution.OURS,
                             osattribution.attribution("heyreach", campaign))


class TheOperatorsInternalCampaignsAreNeverOurs(LedgerTest):
    def setUp(self):
        super().setUp()
        self.write_ledger()

    def test_the_four_internal_campaigns_are_unknown(self):
        """The load-bearing assertion. These four carry zero perform rows and
        are the operator's internal campaigns; reading one as OS would make its
        members look like people we have contacted."""
        for campaign in INTERNAL:
            self.assertEqual(
                osattribution.UNKNOWN,
                osattribution.attribution("bison", campaign),
                f"bison {campaign} must never read as ours")

    def test_a_campaign_nobody_recorded_is_still_unknown(self):
        self.assertEqual(osattribution.UNKNOWN,
                         osattribution.attribution("bison", 999999))

    def test_the_other_channel_is_not_the_same_campaign(self):
        """487 on bison says nothing about 487 on heyreach, and the id spaces
        genuinely overlap in neither direction."""
        self.assertEqual(osattribution.UNKNOWN,
                         osattribution.attribution("heyreach", 487))
        self.assertEqual(osattribution.UNKNOWN,
                         osattribution.attribution("bison", "599020"))


class AnUnreadableAuthorityIsUnknownAndNeverNotOurs(LedgerTest):
    """THE TEST THE READABLE FLAG EXISTS FOR.

    `campaigns.load()` yields nothing both when we own no campaigns and when
    the file cannot be read, and those two have OPPOSITE consequences. Empty
    but READ means no campaign is ours, which is correct and makes a lead cold.
    UNREADABLE collapsing to the same answer would mark every lead we have ever
    written to as never contacted and hand a full new sequence to all of them.
    """

    def make_unreadable(self):
        """A DIRECTORY where the ledger file belongs, so `open()` raises.

        Permissions are not used: `chmod` does not reliably deny the owner a
        read on Windows, so a permission-based version of this test would pass
        while proving nothing.
        """
        os.mkdir(os.path.join(self.tmp, "campaigns.jsonl"))

    def test_the_fixture_really_is_unreadable(self):
        """The control: without this, every assertion below could be passing
        because the ledger was merely empty."""
        self.make_unreadable()
        self.assertFalse(collision.os_campaign_ids()[1])
        self.assertFalse(collision.our_heyreach_campaign_ids()[1])
        self.assertFalse(osattribution.authority("bison")[1])

    def test_an_unreadable_authority_makes_an_os_campaign_unknown(self):
        self.make_unreadable()
        self.assertEqual(osattribution.UNKNOWN,
                         osattribution.attribution("bison", 487))
        self.assertEqual(osattribution.UNKNOWN,
                         osattribution.attribution("heyreach", "613724"))

    def test_an_unreadable_authority_refuses_to_disown_even_on_an_internal_claim(self):
        """`NOT_OURS` is the forbidden answer here. The ledger claim says the
        campaign is internal, but the membership that would have made it OURS
        is exactly what could not be read, so the honest verdict is UNKNOWN."""
        self.assertEqual(
            osattribution.NOT_OURS,
            osattribution.attribution("bison", 327,
                                      ledger_says="resonate_internal",
                                      authority_says=(frozenset(), True)),
            "a READ authority that does not hold it, plus a positive internal "
            "claim, is the one case that may conclude NOT_OURS")
        self.make_unreadable()
        self.assertEqual(
            osattribution.UNKNOWN,
            osattribution.attribution("bison", 327,
                                      ledger_says="resonate_internal"),
            "an UNREADABLE authority must never reach NOT_OURS")

    def test_a_positive_os_claim_still_wins_because_it_only_withholds(self):
        """The one arm above the readable check. Concluding a campaign is ours
        marks the lead legacy_touched, which withholds outreach rather than
        spending it, so it is safe without the authority."""
        self.make_unreadable()
        self.assertEqual(
            osattribution.OURS,
            osattribution.attribution("bison", 487,
                                      ledger_says="resonate_os"))


class AnEmptyButReadAuthorityIsHonestlyEmpty(LedgerTest):
    def test_nothing_is_ours_and_the_read_is_reported(self):
        ids, readable = collision.os_campaign_ids()
        self.assertTrue(readable, "a store with no campaign file reads as "
                                  "empty, not as unreadable")
        self.assertEqual(frozenset(), ids)
        self.assertEqual(osattribution.UNKNOWN,
                         osattribution.attribution("bison", 487))


class TheTwoIdTypesAreReconciledAtTheBoundary(LedgerTest):
    """Bison ids are ints and heyreach ids are strings. A caller must not have
    to know which, and `481 in {"481"}` must never decide anything."""

    def setUp(self):
        super().setUp()
        self.write_ledger()

    def test_a_bison_id_reads_the_same_as_an_int_or_a_string(self):
        for spelling in (487, "487", " 487 ", "0487"):
            self.assertEqual(
                osattribution.OURS,
                osattribution.attribution("bison", spelling),
                f"{spelling!r} is campaign 487 however the provider spelled it")

    def test_a_heyreach_id_reads_the_same_as_an_int_or_a_string(self):
        for spelling in ("599020", 599020, " 599020 "):
            self.assertEqual(osattribution.OURS,
                             osattribution.attribution("heyreach", spelling))

    def test_a_boolean_is_not_campaign_one(self):
        """`True == 1` in Python. A truthy flag arriving where an id belongs
        must not alias a campaign."""
        self.assertIsNone(osattribution._key(True))
        self.assertIsNone(osattribution._key(False))

    def test_an_unparseable_id_is_kept_rather_than_dropped(self):
        """It must not become None and read as absent - it reads as a campaign
        the authority does not hold, which is UNKNOWN."""
        self.assertEqual("not-a-number", osattribution._key("not-a-number"))
        self.assertEqual(osattribution.UNKNOWN,
                         osattribution.attribution("bison", "not-a-number"))


class TheLedgerClaimIsThreeValued(LedgerTest):
    def setUp(self):
        super().setUp()
        self.write_ledger()

    def test_a_ledger_that_could_not_answer_is_not_a_no(self):
        """None means "not asked" or "could not say". It must not read as
        NOT_OURS, because that would hide a send we made."""
        self.assertEqual(
            osattribution.UNKNOWN,
            osattribution.attribution("bison", 327, ledger_says=None))

    def test_the_authority_outranks_an_unknown_ledger(self):
        self.assertEqual(
            osattribution.OURS,
            osattribution.attribution("bison", 487, ledger_says=None))


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
            self.assertTrue(verdict)


class AMissingIdentifierIsUnknown(LedgerTest):
    def setUp(self):
        super().setUp()
        self.write_ledger()

    def test_no_campaign_id_is_unknown_not_ours(self):
        self.assertEqual(osattribution.UNKNOWN,
                         osattribution.attribution("bison", None))

    def test_no_provider_is_unknown_not_ours(self):
        self.assertEqual(osattribution.UNKNOWN,
                         osattribution.attribution(None, 487))

    def test_a_channel_this_system_does_not_write_to_is_unknown(self):
        self.assertEqual(osattribution.UNKNOWN,
                         osattribution.attribution("mailchimp", 487))
        self.assertFalse(osattribution.authority("mailchimp")[1])


if __name__ == "__main__":
    unittest.main()
