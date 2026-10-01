"""Ownership is three-state. "Not provably ours" is not "the client's".

THE DEFECT, measured 2026-10-01. `provider_truth.owned_by_resonate` returned a
BOOLEAN and the caller wrote
``"owner": "resonate" if owned_by_resonate(...) else "client_or_other"``, so
every campaign that was not PROVABLY ours was recorded as the CLIENT'S. That
is inference from absence, and for one measurable class it is simply false:

  * `work/campaigns.jsonl` - the claimed-ids source - begins 2026-09-02.
  * EmailBison 274 (created 2026-04-08), 327 and 328 (2026-04-23) and 352
    (2026-05-13) therefore CANNOT be in it.
  * Their names do not start with "RESONATE", the only prefix in
    `RESONATE_PREFIXES`, so the fallback misses them too. Two carry the
    OPERATOR'S OWN first name.
  * The provider exposes no owner, creator, user, team or tenant field on a
    campaign, and all of them share the single workspace
    `bison.bound_workspace()` returns. Ownership is genuinely unknowable from
    the provider for these.

Four campaigns carrying tens of thousands of sends were reported as the
client's, and reasoning built on top of that ("the client is mid-sequence at
this account") inherited it as fact.

THE BOUNDARY THESE TESTS PIN. Absence from the ledger is evidence only across
the span in which the ledger was keeping records. At or after the ledger's own
earliest entry, unclaimed and unprefixed means positively not ours, which in a
one-workspace account is `client_or_other`. Before it, the ledger could not
have recorded the campaign and its silence says nothing: UNKNOWN. No readable
creation date, or no readable ledger start: UNKNOWN. Nothing keys off a month,
an id range, the operator's name or a status.

Every test here drives the real entry points - `campaign_owner`,
`ledger_earliest_entry`, `read_emailbison_campaigns`, `_bison_owner_counts` -
because the seam was never the risk; the wiring is.
"""
import os
import sys
import unittest
from unittest import mock

from src.providers import bison

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import provider_truth  # noqa: E402

#: The production ledger's earliest readable `created_at`, measured
#: 2026-10-01 over all 69 rows of `work/campaigns.jsonl`.
LEDGER_START = "2026-09-02T11:55:20+00:00"

#: The real name, verbatim from `docs/state/PROVIDER-CAMPAIGNS.json`. It
#: carries the operator's own first name and no RESONATE prefix, which is
#: exactly why the prefix fallback could not save it.
NAME_274 = "FIXED - PRODUCTIVE - MARKETING AGENCY - USA - ZVONIMIR APRIL 8TH CLEAN"


class TheRegressionCase(unittest.TestCase):
    """EmailBison 274, exactly as it exists at the provider."""

    def test_274_is_unknown_and_specifically_not_the_clients(self):
        """Id 274, the real name, created 2026-04-08, absent from a ledger
        whose earliest entry is 2026-09-02. The ledger did not exist when
        this campaign was made, so its silence is not an accusation."""
        owner = provider_truth.campaign_owner(
            NAME_274, 274, claimed_ids=set(),
            created_at="2026-04-08T00:00:00.000000Z",
            ledger_start=LEDGER_START)
        self.assertEqual(owner, provider_truth.OWNER_UNKNOWN)
        self.assertNotEqual(
            owner, provider_truth.OWNER_CLIENT,
            "274 was recorded as the client's on no evidence - the "
            "boolean-ownership defect is back")
        self.assertNotEqual(owner, provider_truth.OWNER_OURS,
                            "274 is not claimable either")

    def test_the_other_three_pre_ledger_campaigns_are_unknown_too(self):
        """327 and 328 (2026-04-23) and 352 (2026-05-13). Same reason."""
        for cid, name, created in (
                (327, "FIXED - MARKETING AGENCY - USA - ZVONIMIR APRIL 22nd "
                      "- new approach", "2026-04-23T00:00:00Z"),
                (328, "FIXED -  MARKETING AGENCY - eu - ZVONIMIR APRIL 22nd "
                      "- new approach", "2026-04-23T00:00:00Z"),
                (352, "HeyReach Connection Campaign",
                 "2026-05-13T11:09:12.000000Z")):
            with self.subTest(campaign=cid):
                self.assertEqual(
                    provider_truth.campaign_owner(
                        name, cid, set(), created_at=created,
                        ledger_start=LEDGER_START),
                    provider_truth.OWNER_UNKNOWN)

    def test_the_whole_report_records_unknown_for_274(self):
        """End to end through `read_emailbison_campaigns`: the WRITTEN entry
        says unknown, and it carries the created_at its verdict rests on."""
        rows = [{"id": 274, "name": NAME_274, "status": "archived",
                 "created_at": "2026-04-08T00:00:00.000000Z"}]
        with mock.patch.object(bison, "list_all_campaigns",
                               return_value=(rows, 1)):
            with mock.patch.object(bison, "campaign_lead_count",
                                   return_value=7):
                result = provider_truth.read_emailbison_campaigns(
                    claimed_bison_ids=frozenset(),
                    ledger_start=LEDGER_START)
        entry = result["campaigns"][0]
        self.assertEqual(entry["owner"], provider_truth.OWNER_UNKNOWN)
        self.assertNotEqual(entry["owner"], provider_truth.OWNER_CLIENT)
        self.assertEqual(entry["created_at"], "2026-04-08T00:00:00.000000Z")


class TheTwoPositiveControls(unittest.TestCase):
    """The paths that made campaigns ours before must still make them ours."""

    def test_a_campaign_in_the_ledger_is_ours(self):
        """503: no RESONATE prefix, in the ledger from the 09-25 factory run.
        The ledger decides FIRST and the prefix is only a fallback."""
        owner = provider_truth.campaign_owner(
            "PRODUCTIVE-USEast-MktgAdv-HCunknown-PackFact-FounderCEO-20260925",
            503, claimed_ids={503, 504, 505},
            created_at="2026-09-25T12:00:15.000000Z",
            ledger_start=LEDGER_START)
        self.assertEqual(owner, provider_truth.OWNER_OURS)

    def test_a_ledger_claim_wins_even_with_no_date_at_all(self):
        """491-498 and 500 carry a NULL created_at in the ledger. The claim
        is by id and does not need a date; a dateless claimed campaign must
        not fall through to unknown."""
        owner = provider_truth.campaign_owner(
            "RESONATE - PRODUCTIVE - EMAIL - US-HOURS", 491,
            claimed_ids={491}, created_at=None, ledger_start=None)
        self.assertEqual(owner, provider_truth.OWNER_OURS)

    def test_a_resonate_prefixed_campaign_absent_from_the_ledger_is_ours(self):
        """The documented fallback: our factory made it and never registered
        it. 487/489 were RESONATE-prefixed and missed by every human reading
        a snapshot that already had them. This must not regress, and it must
        not regress to UNKNOWN either - the prefix is affirmative evidence."""
        owner = provider_truth.campaign_owner(
            "RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS", 487,
            claimed_ids=set(), created_at="2026-09-17T06:25:21.000000Z",
            ledger_start=LEDGER_START)
        self.assertEqual(owner, provider_truth.OWNER_OURS)

    def test_the_prefix_wins_before_the_ledger_start_too(self):
        """A RESONATE-prefixed campaign older than the ledger is still ours.
        The date rule only ever arbitrates CLIENT vs UNKNOWN; it may not
        demote a campaign the prefix already claims."""
        owner = provider_truth.campaign_owner(
            "RESONATE - SOMETHING OLD", 9, claimed_ids=set(),
            created_at="2026-04-01T00:00:00Z", ledger_start=LEDGER_START)
        self.assertEqual(owner, provider_truth.OWNER_OURS)


class WhereTheClientBoundarySits(unittest.TestCase):
    """Case (d): plainly after the ledger's start, unclaimed, unprefixed."""

    def test_after_the_ledger_start_unclaimed_and_unprefixed_is_the_client(self):
        """DECIDED: client_or_other, and here is the reasoning.

        Campaigns 423 and 424 were created 2026-09-03, one day after the
        ledger's earliest entry. By then our factory was writing a ledger row
        for every campaign it created and kept doing so continuously through
        2026-09-30 - 69 rows, no gap in the id sequence it claims. A campaign
        the provider holds from inside that span which our own write path
        never recorded is therefore positively not ours: the silence of a
        ledger that WAS keeping records is evidence, where the silence of one
        that did not yet exist is not.

        The account is a single workspace - `bison.bound_workspace()` returns
        {'id': 10, 'name': 'PRODUCTIVE'} and there is no second one - so
        not-ours there means the client or whoever else holds the credential,
        which is exactly what `client_or_other` has always named. The verdict
        is not "the client" on its own and never was.

        The alternative, calling this UNKNOWN too, would make the state
        unfalsifiable: nothing could ever be anybody's but ours, and a report
        in which every row reads unknown tells an operator nothing. The cost
        of being wrong here is also bounded in a way the old defect's was
        not - a campaign wrongly called the client's inside the ledger's own
        lifetime indicts a gap in OUR write path, which is a bug we would
        want surfaced, whereas 274 indicted a client over a period we simply
        were not present for.
        """
        owner = provider_truth.campaign_owner(
            "PRODUCTIVE - SOFTWARE DEVELOPMENT - NOT CONNECTED - JELENA",
            423, claimed_ids=set(), created_at="2026-09-03T08:00:00.000000Z",
            ledger_start=LEDGER_START)
        self.assertEqual(owner, provider_truth.OWNER_CLIENT)

    def test_the_boundary_is_inclusive_at_the_ledgers_own_stamp(self):
        """A campaign created in the same instant as the ledger's first entry
        is inside the covered span. Asserted so the comparison cannot drift
        from >= to > unnoticed."""
        self.assertEqual(
            provider_truth.campaign_owner("whatever", 1, set(),
                                          created_at=LEDGER_START,
                                          ledger_start=LEDGER_START),
            provider_truth.OWNER_CLIENT)
        self.assertEqual(
            provider_truth.campaign_owner("whatever", 1, set(),
                                          created_at="2026-09-02T11:55:19+00:00",
                                          ledger_start=LEDGER_START),
            provider_truth.OWNER_UNKNOWN)

    def test_the_two_stamp_formats_compare_correctly(self):
        """The provider emits `...000000Z`, the ledger emits `+00:00`. A
        boundary that only works when both sides share a format is a bug
        waiting for the next provider."""
        self.assertEqual(
            provider_truth.campaign_owner(
                "x", 1, set(), created_at="2026-09-03T08:00:00.000000Z",
                ledger_start="2026-09-02T11:55:20+00:00"),
            provider_truth.OWNER_CLIENT)
        self.assertEqual(
            provider_truth.campaign_owner(
                "x", 1, set(), created_at="2026-09-01T08:00:00.000000Z",
                ledger_start="2026-09-02T11:55:20+00:00"),
            provider_truth.OWNER_UNKNOWN)


class AnUnreadableDateIsNeverAVerdict(unittest.TestCase):
    """Invariant 0: an unreadable authority is UNKNOWN, never a verdict."""

    def test_no_creation_date_is_unknown(self):
        for created in (None, "", "not a date", "0000", []):
            with self.subTest(created_at=created):
                self.assertEqual(
                    provider_truth.campaign_owner(
                        "some client campaign", 1, set(), created_at=created,
                        ledger_start=LEDGER_START),
                    provider_truth.OWNER_UNKNOWN)

    def test_no_ledger_start_is_unknown(self):
        """An absent or unreadable ledger dates nothing, so it accuses
        nobody. This is also what the default argument gives you."""
        for start in (None, "", "garbage"):
            with self.subTest(ledger_start=start):
                self.assertEqual(
                    provider_truth.campaign_owner(
                        "some client campaign", 1, set(),
                        created_at="2026-09-20T00:00:00Z", ledger_start=start),
                    provider_truth.OWNER_UNKNOWN)
        self.assertEqual(
            provider_truth.campaign_owner("some client campaign", 1, set()),
            provider_truth.OWNER_UNKNOWN)


class TheLedgerStartIsDerived(unittest.TestCase):
    """`ledger_earliest_entry` reads the ledger; nobody types the date in."""

    def test_earliest_readable_stamp_wins_and_nulls_do_not_spoil_it(self):
        """9 of 69 production rows carry a null created_at. They must not
        make the ledger undatable, and they must not become the minimum."""
        claims = [
            {"created_at": None},
            {"created_at": "2026-09-13T08:36:04+00:00"},
            {"created_at": LEDGER_START},
            {"created_at": "not a date"},
            {"created_at": "2026-09-30T17:22:26+00:00"},
        ]
        start = provider_truth.ledger_earliest_entry(claims)
        self.assertIsNotNone(start)
        self.assertEqual(start.isoformat(), LEDGER_START)

    def test_an_empty_or_undatable_ledger_yields_none(self):
        self.assertIsNone(provider_truth.ledger_earliest_entry([]))
        self.assertIsNone(provider_truth.ledger_earliest_entry(None))
        self.assertIsNone(provider_truth.ledger_earliest_entry(
            [{"created_at": None}, {"created_at": "junk"}]))

    def test_a_datetime_ledger_start_is_accepted_as_well_as_a_string(self):
        """`main` passes the datetime `ledger_earliest_entry` returns, and
        the tests pass strings. Both must work or the production path and the
        tested path are different code."""
        start = provider_truth.ledger_earliest_entry(
            [{"created_at": LEDGER_START}])
        self.assertEqual(
            provider_truth.campaign_owner("x", 1, set(),
                                          created_at="2026-09-20T00:00:00Z",
                                          ledger_start=start),
            provider_truth.OWNER_CLIENT)


class TheHistogramCountsTheThirdState(unittest.TestCase):
    """Case (e): the third state reaches the report, not just the function."""

    CAMPAIGNS = [
        {"owner": provider_truth.OWNER_OURS},
        {"owner": provider_truth.OWNER_OURS},
        {"owner": provider_truth.OWNER_CLIENT},
        {"owner": provider_truth.OWNER_UNKNOWN},
        {"owner": provider_truth.OWNER_UNKNOWN},
        {"owner": provider_truth.OWNER_UNKNOWN},
    ]

    def test_unknown_is_its_own_bucket(self):
        counts = provider_truth._bison_owner_counts(self.CAMPAIGNS)
        self.assertEqual(counts[provider_truth.OWNER_UNKNOWN], 3)
        self.assertEqual(counts[provider_truth.OWNER_CLIENT], 1)
        self.assertEqual(counts[provider_truth.OWNER_OURS], 2)

    def test_unknown_is_not_folded_into_either_neighbour(self):
        """The failure mode being guarded: three unknowns silently added to
        client_or_other, which is what the old code did by construction."""
        counts = provider_truth._bison_owner_counts(self.CAMPAIGNS)
        self.assertNotEqual(counts[provider_truth.OWNER_CLIENT], 4)
        self.assertNotEqual(counts[provider_truth.OWNER_OURS], 5)
        self.assertEqual(sum(counts.values()), len(self.CAMPAIGNS))

    def test_all_three_buckets_are_always_present_even_at_zero(self):
        """A reader finding no `unknown` key cannot tell "none are unknown"
        from "this file predates the third state"."""
        counts = provider_truth._bison_owner_counts(
            [{"owner": provider_truth.OWNER_OURS}])
        for state in provider_truth.OWNER_STATES:
            self.assertIn(state, counts)
        self.assertEqual(counts[provider_truth.OWNER_UNKNOWN], 0)
        self.assertEqual(counts[provider_truth.OWNER_CLIENT], 0)

    def test_the_histogram_counts_what_the_reader_actually_wrote(self):
        """Wired end to end: the mix of campaigns that produced the defect -
        one ours, one pre-ledger, one in-span - histogrammed from the entries
        `read_emailbison_campaigns` itself produced."""
        rows = [
            {"id": 274, "name": NAME_274, "status": "archived",
             "created_at": "2026-04-08T00:00:00.000000Z"},
            {"id": 423, "name": "PRODUCTIVE - SOMETHING", "status": "draft",
             "created_at": "2026-09-03T08:00:00.000000Z"},
            {"id": 487, "name": "RESONATE - PRODUCTIVE - EMAIL - ZAGREB",
             "status": "paused", "created_at": "2026-09-17T06:25:21.000000Z"},
        ]
        with mock.patch.object(bison, "list_all_campaigns",
                               return_value=(rows, 3)):
            with mock.patch.object(bison, "campaign_lead_count",
                                   return_value=1):
                result = provider_truth.read_emailbison_campaigns(
                    frozenset(), LEDGER_START)
        counts = provider_truth._bison_owner_counts(result["campaigns"])
        self.assertEqual(counts, {provider_truth.OWNER_OURS: 1,
                                  provider_truth.OWNER_CLIENT: 1,
                                  provider_truth.OWNER_UNKNOWN: 1})


class TheBooleanPredicateStillMeansOnlyWhatItSays(unittest.TestCase):
    """`owned_by_resonate` survives for the HeyReach filter, and no caller
    may read its False as "the client's" again."""

    def test_it_is_a_bool_and_tracks_ours(self):
        self.assertIs(
            provider_truth.owned_by_resonate("RESONATE - X", 9, set()), True)
        self.assertIs(
            provider_truth.owned_by_resonate("x", 503, {503}), True)
        self.assertIs(
            provider_truth.owned_by_resonate(NAME_274, 274, set()), False)

    def test_false_is_not_the_client_verdict(self):
        """The exact substitution that caused the defect: False fed straight
        into a two-way ternary. The predicate says nothing about the client,
        and `campaign_owner` is the only thing that may answer that."""
        self.assertFalse(
            provider_truth.owned_by_resonate(NAME_274, 274, set()))
        self.assertEqual(
            provider_truth.campaign_owner(NAME_274, 274, set(),
                                          created_at="2026-04-08T00:00:00Z",
                                          ledger_start=LEDGER_START),
            provider_truth.OWNER_UNKNOWN)

    def test_the_bison_reader_does_not_use_the_boolean(self):
        """Behavioural, not textual: if `read_emailbison_campaigns` still
        went through the predicate, patching `campaign_owner` would have no
        effect on what it writes."""
        rows = [{"id": 274, "name": NAME_274, "status": "archived",
                 "created_at": "2026-04-08T00:00:00.000000Z"}]
        with mock.patch.object(provider_truth, "campaign_owner",
                               return_value="SENTINEL") as spy:
            with mock.patch.object(bison, "list_all_campaigns",
                                   return_value=(rows, 1)):
                with mock.patch.object(bison, "campaign_lead_count",
                                       return_value=1):
                    result = provider_truth.read_emailbison_campaigns(
                        frozenset(), LEDGER_START)
        self.assertEqual(result["campaigns"][0]["owner"], "SENTINEL")
        self.assertTrue(spy.called)


class TheProviderCarriesTheDate(unittest.TestCase):
    """The date the boundary needs has to survive the provider's trim."""

    def test_list_all_campaigns_keeps_created_at(self):
        """`bison.list_all_campaigns` trims the raw row. A trim that dropped
        created_at would make every unclaimed campaign unknown forever -
        safe, but blind."""
        raw = [{"id": 274, "name": NAME_274, "status": "archived",
                "created_at": "2026-04-08T00:00:00.000000Z",
                "uuid": "irrelevant", "emails_sent": 0}]
        with mock.patch.object(bison, "_paged", return_value=(raw, 1)):
            rows, total = bison.list_all_campaigns()
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["created_at"], "2026-04-08T00:00:00.000000Z")
        self.assertNotIn("uuid", rows[0], "the trim must stay a trim")


if __name__ == "__main__":
    unittest.main()
