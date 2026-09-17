"""A setting was read as a counter, and a seat nobody vetted was read as absent.

Two defects in how this repository reports its own HeyReach capacity. Neither
could send a message to the wrong person; both mislead the operator who is
deciding how big the next cohort may be, which is the decision that ends in
messages being sent.

**ONE. A CONFIGURED LIMIT WAS CALLED "REMAINING".** `accountLimits` carries
twelve numbers in six `<action>Limit` / `<action>Max` pairs. Measured over all
41 seats on 2026-09-17: every `...Max` member is 40 - on every seat, including
the eight whose credential is dead and which can send nothing at all - while
every `...Limit` member varies per seat from 0 to 40 and never exceeds its Max.
A number identical across every seat in the estate is a plan ceiling. The one
that varies is the configured allowance.

The repository had them the wrong way round in two places at once, which is
why the total looked plausible:

  - `build_linkedin` stored `connectioRequestMax` as the row's `daily_limit`,
    so all 32 rostered seats recorded 40 - including `li-139699`, configured
    at 0 and unable to open a connection request at all, and `li-201959`,
    configured at 15. `senderidentity.capacity` sums that field, so the roster
    reported 1,280 requests/day against a configured 1,014. A planner reading
    it over-planned the estate by 26%.
  - `li_readiness` read `connectioRequestLimit` as remaining-today and told an
    operator "no connection requests left against today's limit". It is not
    remaining. Across all 32 rostered seats the value was byte-identical
    between 2026-09-13 and 2026-09-17 while the cooldown flags moved on four
    seats over the same window - a settled setting beside something genuinely
    volatile.

THE PROVIDER PUBLISHES NO REMAINING-TODAY FIGURE AT ALL. Fifteen keys on the
seat row, twelve numbers in `accountLimits`, and not one of the twenty-seven is
a used-today or left-today count. So remaining today is UNKNOWN, and this
repository's convention is that UNKNOWN is never silently a number.

**TWO. A SEAT NOBODY VETTED WAS INVISIBLE RATHER THAN FLAGGED.** Provider seat
`174810` is healthy, credential-valid and sitting in eight of the client's live
campaigns, and it is absent from the canonical roster. `build_linkedin` dropped
it in silence, which is the right refusal and the wrong record: it came out
indistinguishable from a seat that does not exist. Nothing could tell
"deliberately excluded" from "nobody noticed".

It was never dangerous - `executionguard` refuses any seat the canonical roster
does not name, so the gap fails closed. It was unaccountable. The gap is now
reported with each missing seat's eligibility stated in the provider's own
fields, and reporting it still does not make it usable: attestation is an
operator's decision about whose LinkedIn profile speaks to a stranger, and no
module here performs it.

THE FIXTURE IS THE MEASUREMENT. `SEATS` below is the real estate as
`POST /li_account/GetAll` returned it on 2026-09-17 - 41 seats, their health
booleans, their in-progress campaign counts and all twelve limits. No name,
email address or profile URL is carried: seat ids, health flags and numeric
limits are not PII, and nothing else from the row is needed to ask these
questions. Every total asserted here is computed from that table rather than
written down, so a test cannot agree with a number the code invented.
"""
import unittest

from src import senderidentity as si, senderinventory as inv, senders
from tests.base import ProviderTest

WS = "productive"

# The six actions, in the order the `seat()` rows list their configured values.
# The provider's misspelling of the first is deliberate and load-bearing; see
# `test_the_vendors_typo_is_the_field_name` in the write-contract suite.
ACTIONS = (("connectioRequestLimit", "connectioRequestMax"),
           ("messageLimit", "messageLimitMax"),
           ("inMailLimit", "inMailLimitMax"),
           ("profileViewLimit", "profileViewLimitMax"),
           ("followLimit", "followLimitMax"),
           ("postLikeLimit", "postLikeLimitMax"))

# Measured, not assumed: every `...Max` member on every one of the 41 seats.
CEILING = 40

COOLDOWNS = ("connectionRequest", "connectionNote", "inMail", "search")


def seat(ident, is_active, auth_valid, campaigns, configured, cooldowns=()):
    """One `/li_account/GetAll` row, minus the fields that identify a human.

    `configured` is the six `...Limit` values in `ACTIONS` order. The matching
    `...Max` is `CEILING` for all of them because that is what the provider
    returned for all of them - that uniformity is the evidence that `...Max` is
    a plan ceiling rather than a seat's allowance, so it is encoded as
    structure here rather than repeated 246 times.
    """
    limits = {}
    for (low, high), value in zip(ACTIONS, configured):
        limits[low] = value
        limits[high] = CEILING
    row = {"id": ident, "isActive": is_active, "authIsValid": auth_valid,
           "activeCampaigns": campaigns, "accountLimits": limits}
    for name in COOLDOWNS:
        row[f"{name}Cooldown"] = name in cooldowns
    return row


#                                       conn  msg  inm  view  fol  like
SEATS = [
    seat(116968,  True,  True,  8, (40, 40, 40, 40, 40, 40)),
    seat(116973,  True,  True,  8, (40, 40, 40, 39, 40, 40)),
    seat(116988,  True,  True,  8, (40, 40, 40, 40, 40, 40)),
    seat(116989,  True,  True,  8, (40, 40, 40, 40, 40, 40)),
    seat(119588,  True,  True,  8, (40, 40, 40, 40, 37, 40)),
    seat(125748,  True,  True,  8, (40, 40, 40, 40, 40, 40)),
    seat(125775,  True,  True,  8, (40, 40, 40, 40, 40, 40)),
    seat(129082,  True,  True,  8, (40, 40, 40, 39, 40, 40)),
    seat(129531,  True, False,  1, (40, 40, 40, 40, 40, 40)),
    seat(139699,  True,  True,  8, ( 0, 40, 40, 40, 40, 40)),
    seat(143105,  True,  True,  8, (25, 40, 40, 40, 40, 40),
         cooldowns=("connectionRequest",)),
    seat(156360, False, False,  0, (25, 24, 26, 25, 40, 26)),
    seat(159259,  True,  True,  8, (25, 25, 25, 25, 25, 25),
         cooldowns=("connectionRequest",)),
    seat(169600,  True,  True,  8, (23, 24, 24, 24, 23, 24)),
    seat(170308, False, False,  0, ( 5,  5,  5,  5,  5,  5)),
    seat(174332,  True,  True, 12, (40, 40, 40, 40, 40, 40)),
    seat(174742,  True,  True, 12, (40, 40, 40, 40, 40, 40)),
    seat(174748,  True,  True, 12, (40, 40, 40, 40, 40, 40)),
    seat(174797,  True,  True, 12, (40, 40, 40, 40, 40, 40)),
    seat(174803,  True,  True, 12, (40, 40, 40, 40, 40, 40)),
    # HEALTHY, IN EIGHT LIVE CLIENT CAMPAIGNS, AND NOT IN THE ROSTER.
    seat(174810,  True,  True,  8, (40, 40, 40, 40, 40, 40)),
    seat(174822,  True,  True, 12, (40, 40, 40, 40, 40, 40)),
    seat(174845,  True,  True, 12, (40, 40, 40, 40, 40, 40)),
    # The live cohort's seat. Thirteen in-progress campaigns, not twelve.
    seat(174892,  True,  True, 13, (40, 40, 40, 40, 40, 40)),
    seat(175455,  True,  True, 12, (40, 40, 40, 40, 40, 40)),
    seat(175552,  True,  True,  8, (25, 40, 40, 40, 40, 40)),
    seat(177751,  True,  True,  8, (17, 17, 40, 19, 19, 21)),
    seat(179527,  True,  True,  8, (19, 18, 20, 19, 17, 19)),
    seat(181262, False, False,  0, (15,  5,  5,  5,  5,  5)),
    seat(181653,  True,  True,  8, (22, 22, 20, 18, 21, 22),
         cooldowns=("connectionRequest",)),
    seat(181658,  True,  True,  8, (18, 17, 19, 18, 17, 20)),
    seat(186618, False, False,  0, (10, 10, 10, 10, 10, 10)),
    seat(191848,  True,  True,  8, (25, 40, 40, 40, 40, 40)),
    seat(194061, False, False,  0, ( 5,  5,  5,  5,  5,  5)),
    seat(201959,  True,  True,  8, (15,  5,  5,  5,  5,  5)),
    seat(201969, False, False,  0, (15,  5,  5,  5,  5,  5)),
    seat(201978,  True,  True,  8, (25, 40, 40, 40, 40, 40)),
    seat(208242,  True,  True, 12, (40, 40, 40, 40, 40, 40)),
    seat(208253,  True,  True,  8, (40, 40, 40, 40, 40, 40)),
    seat(210951, False, False,  0, (40, 40, 40, 40, 40, 40)),
    seat(212356,  True,  True,  8, (15, 15, 15, 15, 15, 15)),
]

BY_ID = {str(s["id"]): s for s in SEATS}

# The 32 seats a human attested, as `work/senders.jsonl` holds them. Derived
# from the estate rather than retyped: every seat the provider calls healthy,
# less `174810`, which is exactly the population the roster names and exactly
# the one seat whose exclusion nobody wrote down.
ATTESTED = sorted(str(s["id"]) for s in SEATS
                  if s["isActive"] and s["authIsValid"] and s["id"] != 174810)

# The eight unrostered seats whose absence is correct: dead at the provider.
DEAD = sorted(str(s["id"]) for s in SEATS
              if not (s["isActive"] and s["authIsValid"]))


def configured_of(ident):
    return BY_ID[str(ident)]["accountLimits"][inv.CONNECTION_LIMIT]


def ceiling_of(ident):
    return BY_ID[str(ident)]["accountLimits"][inv.CONNECTION_MAX]


CONFIGURED_TOTAL = sum(configured_of(i) for i in ATTESTED)
CEILING_TOTAL = sum(ceiling_of(i) for i in ATTESTED)


class SeatEstate(ProviderTest):
    """The 32 attested seats, built and installed as the canonical roster."""

    def setUp(self):
        super().setUp()
        self.accounts = inv.build_linkedin(WS, SEATS, approved=ATTESTED)
        si.install([si.new_sender(WS, "anna", "Anna")] + self.accounts)

    def stored(self, account_id):
        return si.account(WS, si.LINKEDIN, account_id)

    def state(self, account_id):
        return (self.stored(account_id) or {}).get("provider_state") or {}


# ===================================================================== 1 ===

class TheFixtureRecordsWhichFieldIsTheCeiling(unittest.TestCase):
    """The measurement the whole fix rests on, pinned where it can be checked."""

    def test_every_max_member_is_the_same_number_on_every_seat(self):
        """Including the eight seats that can send nothing at all.

        A per-seat allowance cannot be identical on a seat whose credential is
        dead and on a seat carrying thirteen live campaigns. A plan ceiling can.
        """
        seen = {row["accountLimits"][high]
                for row in SEATS for _low, high in ACTIONS}
        self.assertEqual(seen, {CEILING})

    def test_the_configured_member_varies_and_never_exceeds_the_ceiling(self):
        configured = {row["accountLimits"][low]
                      for row in SEATS for low, _high in ACTIONS}
        self.assertGreater(len(configured), 1)
        for row in SEATS:
            for low, high in ACTIONS:
                self.assertLessEqual(row["accountLimits"][low],
                                     row["accountLimits"][high],
                                     f"seat {row['id']} {low}")


class ASeatsDailyLimitIsWhatItIsConfiguredFor(SeatEstate):

    def test_the_stored_limit_is_the_configured_field_not_the_ceiling(self):
        for account in self.accounts:
            ident = account["provider_account_id"]
            self.assertEqual(account["daily_limit"], configured_of(ident),
                             f"seat {ident}")

    def test_the_throttled_seats_no_longer_all_read_forty(self):
        """13 of the 32 are throttled below the ceiling and used to read 40."""
        throttled = [i for i in ATTESTED if configured_of(i) != ceiling_of(i)]
        self.assertTrue(throttled)
        stored = {a["provider_account_id"]: a["daily_limit"]
                  for a in self.accounts}
        for ident in throttled:
            self.assertNotEqual(stored[ident], CEILING, f"seat {ident}")
            self.assertEqual(stored[ident], configured_of(ident))

    def test_the_seat_configured_at_zero_reads_zero_and_not_the_ceiling(self):
        """`li-139699` cannot open a connection cadence and said it could."""
        self.assertEqual(configured_of("139699"), 0)
        self.assertEqual(self.stored("li-139699")["daily_limit"], 0)

    def test_the_ceiling_is_kept_but_under_its_own_name(self):
        """Losing it would be the opposite mistake. It is simply not capacity."""
        self.assertEqual(self.state("li-201959")["connection_max"], CEILING)
        self.assertEqual(self.state("li-201959")["connection_limit"], 15)


class NothingIsCalledRemainingThatIsNotRemaining(SeatEstate):

    def test_the_refusal_for_a_zero_limit_seat_does_not_promise_a_counter(self):
        """It said "no connection requests left against today's limit".

        An operator reading that waits for midnight. The seat is configured at
        zero and will read zero tomorrow.
        """
        state, why = inv.li_readiness(self.stored("li-139699"))
        self.assertEqual(state, inv.DEGRADED)
        self.assertNotIn("remaining", why.lower())
        self.assertNotIn("left", why.lower())
        self.assertIn("configured", why.lower())

    def test_a_healthy_seats_reason_does_not_promise_one_either(self):
        _state, why = inv.li_readiness(self.stored("li-116968"))
        self.assertEqual(inv.li_readiness(self.stored("li-116968"))[0],
                         inv.READY)
        self.assertNotIn("remaining", why.lower())

    def test_no_readiness_reason_anywhere_in_the_estate_says_remaining(self):
        for account in self.accounts:
            self.assertNotIn("remaining", inv.li_readiness(account)[1].lower(),
                             account["account_id"])

    def test_remaining_today_is_reported_as_unknown_and_not_as_a_number(self):
        report = inv.reconcile_linkedin(WS, rows=SEATS, stored=self.accounts)
        self.assertEqual(report["connection_remaining_today"],
                         inv.REMAINING_UNKNOWN)
        self.assertNotIsInstance(report["connection_remaining_today"],
                                 (int, float))

    def test_the_unknown_cannot_be_summed_into_a_total_by_accident(self):
        """Why the sentinel is a word and not `None`.

        `None` survives `int(x or 0)` as a zero and `sum()` as nothing, and
        both of those read back as a measured answer. A word raises.
        """
        report = inv.reconcile_linkedin(WS, rows=SEATS, stored=self.accounts)
        with self.assertRaises(TypeError):
            report["connection_remaining_today"] + 1

    def test_the_two_capacity_numbers_are_reported_under_separate_names(self):
        report = inv.reconcile_linkedin(WS, rows=SEATS, stored=self.accounts)
        self.assertEqual(report["connection_capacity_per_day"],
                         CONFIGURED_TOTAL)
        self.assertEqual(report["connection_plan_ceiling_per_day"],
                         CEILING_TOTAL)
        self.assertNotEqual(report["connection_capacity_per_day"],
                            report["connection_plan_ceiling_per_day"])


# ===================================================================== 2 ===

class UnknownStaysUnknown(SeatEstate):
    """A limit nobody stated is not a limit of zero and not a default of 50."""

    SILENT = {"id": 999001, "isActive": True, "authIsValid": True,
              "activeCampaigns": 3, "accountLimits": {"messageLimit": 40}}

    def built_silent(self):
        return inv.build_linkedin(WS, [self.SILENT], approved=["999001"])[0]

    def test_a_limit_the_provider_did_not_state_is_none_not_zero(self):
        account = self.built_silent()
        self.assertIsNone(account["daily_limit"])
        self.assertNotEqual(account["daily_limit"], 0)

    def test_it_does_not_pick_up_the_allocators_default_of_fifty_either(self):
        """`senders.DEFAULT_DAILY_LIMIT` is the other model's assumption.

        Named rather than written as 50, so this keeps holding if it moves.
        """
        self.assertNotEqual(self.built_silent()["daily_limit"],
                            senders.DEFAULT_DAILY_LIMIT)

    def test_an_unstated_limit_is_degraded_rather_than_plannable(self):
        state, why = inv.li_readiness(self.built_silent())
        self.assertEqual(state, inv.DEGRADED)
        self.assertNotIn("remaining", why.lower())

    def test_it_contributes_nothing_and_the_total_says_so(self):
        """The unknown seat must not quietly become a 0 in a complete total."""
        si.install([si.new_sender(WS, "anna", "Anna")]
                   + self.accounts + [self.built_silent()])
        cap = si.capacity(WS)[si.LINKEDIN]
        self.assertEqual(cap["known_daily_capacity"], CONFIGURED_TOTAL)
        self.assertEqual(cap["accounts_with_no_known_limit"], 1)
        self.assertEqual(cap["accounts_with_a_known_limit"], len(ATTESTED))
        self.assertFalse(cap["complete"])

    def test_a_refresh_does_not_invent_a_limit_for_it_either(self):
        stored = [self.built_silent()]
        refreshed, _drift = inv.refresh_linkedin_state(stored, [self.SILENT])
        self.assertIsNone(refreshed[0]["daily_limit"])
        report = inv.reconcile_linkedin(WS, rows=[self.SILENT], stored=stored)
        self.assertEqual(report["seats_with_no_configured_limit"],
                         ["li-999001"])


# ===================================================================== 3 ===

class TheRosterTotalIsTheSumOfConfiguredLimits(SeatEstate):

    def test_the_roster_reports_the_configured_total(self):
        """Asserted against the fixture's own arithmetic, not a written number.

        A test that hard-coded 1,280 would have passed against the defect, and
        a test that hard-codes 1,014 goes red the day a seat is re-throttled.
        """
        cap = si.capacity(WS)[si.LINKEDIN]
        self.assertEqual(cap["known_daily_capacity"], CONFIGURED_TOTAL)
        self.assertEqual(cap["accounts"], len(ATTESTED))
        self.assertTrue(cap["complete"])

    def test_the_total_is_not_the_ceiling_the_roster_used_to_report(self):
        cap = si.capacity(WS)[si.LINKEDIN]
        self.assertEqual(CEILING_TOTAL, CEILING * len(ATTESTED))
        self.assertNotEqual(cap["known_daily_capacity"], CEILING_TOTAL)
        self.assertLess(cap["known_daily_capacity"], CEILING_TOTAL)

    def test_the_old_number_over_planned_the_estate_by_a_quarter(self):
        over = (CEILING_TOTAL - CONFIGURED_TOTAL) / CONFIGURED_TOTAL
        self.assertGreater(over, 0.25)

    def test_the_full_roster_reports_the_same_total_as_capacity_does(self):
        """`roster()` is what a screen reads; it must not disagree with it."""
        report = si.roster(WS)
        self.assertEqual(report["capacity"][si.LINKEDIN]["known_daily_capacity"],
                         CONFIGURED_TOTAL)

    def test_the_total_is_the_sum_of_the_rows_own_limits(self):
        rows = si.linkedin_accounts(WS)
        self.assertEqual(sum(r["daily_limit"] for r in rows), CONFIGURED_TOTAL)


# ===================================================================== 4 ===

class ASeatNobodyVettedIsFlaggedRatherThanInvisible(SeatEstate):

    def report(self):
        return inv.reconcile_linkedin(WS, rows=SEATS, stored=self.accounts)

    def test_every_provider_seat_the_roster_does_not_name_is_reported(self):
        listed = {s["provider_account_id"]
                  for s in self.report()["unrostered_seats"]}
        self.assertEqual(listed, set(DEAD) | {"174810"})

    def test_the_eight_dead_ones_are_reported_as_not_eligible_and_why(self):
        by_id = {s["provider_account_id"]: s
                 for s in self.report()["unrostered_seats"]}
        for ident in DEAD:
            self.assertFalse(by_id[ident]["provider_eligible"], ident)
            self.assertTrue(by_id[ident]["provider_eligibility"], ident)

    def test_the_healthy_unvetted_seat_is_singled_out(self):
        """The finding: eligible at the provider, absent from the roster."""
        report = self.report()
        self.assertEqual(report["unrostered_but_eligible"], ["174810"])
        entry = {s["provider_account_id"]: s
                 for s in report["unrostered_seats"]}["174810"]
        self.assertTrue(entry["provider_eligible"])
        self.assertEqual(entry["health"], si.HEALTH_OK)
        self.assertEqual(entry["active_campaigns"], 8)
        self.assertIn("attested", entry["why_not_usable"])

    def test_reporting_it_does_not_make_it_usable(self):
        for entry in self.report()["unrostered_seats"]:
            self.assertFalse(entry["usable"], entry["provider_account_id"])
            self.assertFalse(entry["attested"], entry["provider_account_id"])

    def test_it_is_not_reachable_through_the_canonical_roster(self):
        """`executionguard` refuses a seat the roster does not name.

        Asserted at the layer the guard reads rather than by calling it: there
        is no `li-174810` row for it to find.
        """
        self.assertIsNone(self.stored("li-174810"))
        self.assertNotIn("174810", {a["provider_account_id"]
                                    for a in si.linkedin_accounts(WS)})

    def test_a_live_reconcile_refreshes_the_roster_and_still_adds_nothing(self):
        """Refreshing state and attesting a seat are different acts."""
        before = {a["account_id"] for a in si.linkedin_accounts(WS)}
        inv.reconcile_linkedin(WS, rows=SEATS, live=True)
        after = si.linkedin_accounts(WS)
        self.assertEqual({a["account_id"] for a in after}, before)
        self.assertEqual(len(after), len(ATTESTED))
        self.assertIsNone(self.stored("li-174810"))

    def test_a_roster_seat_the_provider_has_lost_is_the_other_finding(self):
        """Not the same thing, and not reported as the same thing."""
        shrunk = [s for s in SEATS if s["id"] != 174892]
        report = inv.reconcile_linkedin(WS, rows=shrunk, stored=self.accounts)
        self.assertEqual(report["missing_at_provider"], ["li-174892"])
        self.assertNotIn("174892", {s["provider_account_id"]
                                    for s in report["unrostered_seats"]})


# ===================================================================== 5 ===

class StoredProviderStateRefreshesRatherThanDrifts(SeatEstate):
    """`li-174892.provider_state.active_campaigns` said 12; the provider says 13.

    Campaign 605732 is the thirteenth. Any capacity calculation off the stored
    roster under-counts that seat's load, which is the number that decides
    whether reusing it for a second cohort would slow the live one.
    """

    STALE_READ = "2026-09-13T09:19:42+00:00"

    def go_stale(self):
        rows = si.load()
        for i, row in enumerate(rows):
            if row.get("account_id") == "li-174892":
                rows[i] = dict(row, provider_state=dict(
                    row["provider_state"], active_campaigns=12,
                    read_at=self.STALE_READ))
        si.install(rows)

    def test_the_stale_count_is_what_the_roster_held(self):
        self.go_stale()
        self.assertEqual(self.state("li-174892")["active_campaigns"], 12)
        self.assertEqual(BY_ID["174892"]["activeCampaigns"], 13)

    def test_a_refresh_moves_it_to_provider_truth(self):
        self.go_stale()
        inv.reconcile_linkedin(WS, rows=SEATS, live=True)
        self.assertEqual(self.state("li-174892")["active_campaigns"], 13)

    def test_the_drift_is_reported_with_both_values_and_when_it_was_read(self):
        """Silently correcting it would hide that the roster had been wrong."""
        self.go_stale()
        report = inv.reconcile_linkedin(WS, rows=SEATS, stored=si.linkedin_accounts(WS))
        drift = [d for d in report["drift"]
                 if d["account_id"] == "li-174892"
                 and d["field"] == "active_campaigns"]
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0]["stored"], 12)
        self.assertEqual(drift[0]["provider"], 13)
        self.assertEqual(drift[0]["stored_at"], self.STALE_READ)
        self.assertIn("li-174892", report["drifted_accounts"])

    def test_a_dry_reconcile_reports_the_drift_and_does_not_write(self):
        self.go_stale()
        inv.reconcile_linkedin(WS, rows=SEATS, stored=si.linkedin_accounts(WS))
        self.assertEqual(self.state("li-174892")["active_campaigns"], 12)

    def test_an_unchanged_seat_reports_no_drift(self):
        """Otherwise every refresh would report the whole estate as drifted."""
        report = inv.reconcile_linkedin(WS, rows=SEATS, stored=self.accounts)
        self.assertEqual(report["drift"], [])
        self.assertEqual(report["drifted_accounts"], [])

    def test_a_refresh_does_not_touch_what_the_provider_cannot_say(self):
        """The attestation and the owner are ours, not the provider's."""
        self.go_stale()
        before = self.stored("li-174892")
        inv.reconcile_linkedin(WS, rows=SEATS, live=True)
        after = self.stored("li-174892")
        self.assertEqual(after["created_at"], before["created_at"])
        self.assertEqual(after["sender_id"], before["sender_id"])
        self.assertEqual(after["attested"], before["attested"])
        self.assertEqual(after["workspace"], WS)

    def test_a_throttled_limit_refreshes_too_and_is_named_in_the_drift(self):
        """The same mechanism, on the field defect A was actually about."""
        rows = si.load()
        for i, row in enumerate(rows):
            if row.get("account_id") == "li-212356":
                rows[i] = dict(row, daily_limit=CEILING, provider_state=dict(
                    row["provider_state"], connection_limit=CEILING))
        si.install(rows)
        report = inv.reconcile_linkedin(WS, rows=SEATS, live=True)
        self.assertEqual(self.stored("li-212356")["daily_limit"],
                         configured_of("212356"))
        fields = {d["field"] for d in report["drift"]
                  if d["account_id"] == "li-212356"}
        self.assertEqual(fields, {"connection_limit", "daily_limit"})


if __name__ == "__main__":
    unittest.main()
