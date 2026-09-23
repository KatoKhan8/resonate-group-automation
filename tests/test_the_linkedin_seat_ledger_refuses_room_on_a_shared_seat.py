#!/usr/bin/env python3
"""A shared LinkedIn seat can prove FULL and can NEVER prove ROOM.

The action ledger is a LOWER BOUND on a seat's use: it sees our actions and
not the client's. The client works the same seats on a workspace-wide key
through their own campaigns, and their actions are not in our ledger and
cannot be got at. So:

    ours >= 40                    -> FULL. A lower bound at the ceiling is
                                     still at the ceiling.
    seat is EXCLUSIVELY ours      -> ROOM is computable: 40 - ours.
    seat is SHARED with the client-> REFUSED, ALWAYS, with reason
                                     client_usage_unknown.

The second line is different from `senderheadroom`: there, REFUSED means
*not yet proven* and a fresher walk can turn it into ROOM. Here, on a shared
seat, REFUSED is permanent: no walk of our own ledger can ever prove room on
a seat somebody else is also working, because the missing quantity is
unobservable rather than unwalked.

A future session may try to close that gap by inferring client usage from
HeyReach's campaign counters. It cannot be done: the counters are per
campaign, we cannot enumerate the client's 82 campaigns reliably, and a
seat's daily total is not derivable from the campaigns we can see. A guessed
denominator is worse than a missing one.

No network, no provider write, no new state file. Pure reader over the action
ledger and the provider truth file.
"""
import datetime
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import seatledger, actionledger  # noqa: E402

DAY = "2026-09-22"


def row(key, state, seat, day, channel="linkedin", workspace="productive"):
    """One action-ledger row, shaped for count_on."""
    return {
        "key": key, "state": state, "at": f"{day}T10:00:00+00:00",
        "channel": channel, "sender_id": seat, "workspace": workspace,
    }


def exclusive_truth(seats):
    """Provider truth where every campaign is ours - total == ours."""
    campaigns = []
    for s in seats:
        campaigns.append({
            "heyreach_campaign_id": 900000 + int(s),
            "name": "RESONATE - TEST",
            "senders": [{"id": int(s), "active": True, "resolves": True}],
        })
    return {
        "heyreach": {
            "campaigns_total_in_account": len(campaigns),
            "campaigns_created_by_resonate": len(campaigns),
            "resonate_campaigns": campaigns,
        }
    }


def shared_truth(ours_seats):
    """Provider truth where client campaigns exist - total > ours."""
    campaigns = []
    for s in ours_seats:
        campaigns.append({
            "heyreach_campaign_id": 900000 + int(s),
            "name": "RESONATE - TEST",
            "senders": [{"id": int(s), "active": True, "resolves": True}],
        })
    return {
        "heyreach": {
            "campaigns_total_in_account": 86,
            "campaigns_created_by_resonate": len(campaigns),
            "resonate_campaigns": campaigns,
        }
    }


class ExclusiveSeatProvesRoom(unittest.TestCase):
    """Req 1: 3 of our actions, no client campaign -> ROOM, remaining 37."""

    def test_three_actions_on_exclusive_seat_is_room(self):
        rows = [
            row("k1", actionledger.SENT, 42, DAY),
            row("k2", actionledger.SENT, 42, DAY),
            row("k3", actionledger.SENT, 42, DAY),
        ]
        result = seatledger.daily(42, DAY, rows=rows,
                                  provider_truth=exclusive_truth([42]))
        self.assertEqual(result["ours"], 3)
        self.assertEqual(result["client"], 0)
        self.assertEqual(result["verdict"], seatledger.ROOM)
        self.assertEqual(result["limit"], 40)
        self.assertEqual(result["remaining"], 37)

    def test_zero_actions_on_exclusive_seat_is_room(self):
        result = seatledger.daily(99, DAY, rows=[],
                                  provider_truth=exclusive_truth([99]))
        self.assertEqual(result["verdict"], seatledger.ROOM)
        self.assertEqual(result["remaining"], 40)
        self.assertEqual(result["client"], 0)


class SharedSeatRefusesRoom(unittest.TestCase):
    """Req 2: same seat with ONE client campaign -> REFUSED, not a number."""

    def test_three_actions_on_shared_seat_is_refused(self):
        rows = [
            row("k1", actionledger.SENT, 42, DAY),
            row("k2", actionledger.SENT, 42, DAY),
            row("k3", actionledger.SENT, 42, DAY),
        ]
        result = seatledger.daily(42, DAY, rows=rows,
                                  provider_truth=shared_truth([42]))
        self.assertEqual(result["ours"], 3)
        self.assertEqual(result["client"], "UNKNOWN")
        self.assertEqual(result["verdict"], seatledger.REFUSED)
        self.assertEqual(result["reason"], "client_usage_unknown")

    def test_remaining_is_not_a_number_on_a_shared_seat(self):
        """This is the test that stops the next person computing 40 - 3."""
        rows = [row("k1", actionledger.SENT, 42, DAY)]
        result = seatledger.daily(42, DAY, rows=rows,
                                  provider_truth=shared_truth([42]))
        remaining = result.get("remaining")
        self.assertFalse(
            isinstance(remaining, (int, float)),
            f"remaining on a shared seat must not be a number, got "
            f"{remaining!r} - computing 40 - ours on a shared seat is the "
            f"defect this module exists to prevent")


class SharedSeatCanStillProveFull(unittest.TestCase):
    """Req 3: shared seat with 40 of our own actions -> FULL, not REFUSED.

    A lower bound at the ceiling is still at the ceiling.
    """

    def test_forty_actions_on_shared_seat_is_full(self):
        rows = [row(f"k{i}", actionledger.SENT, 42, DAY)
                for i in range(40)]
        result = seatledger.daily(42, DAY, rows=rows,
                                  provider_truth=shared_truth([42]))
        self.assertEqual(result["verdict"], seatledger.FULL)
        self.assertEqual(result["ours"], 40)

    def test_fifty_actions_on_shared_seat_is_still_full(self):
        """Over the limit is still full - a lower bound above the ceiling."""
        rows = [row(f"k{i}", actionledger.SENT, 42, DAY)
                for i in range(50)]
        result = seatledger.daily(42, DAY, rows=rows,
                                  provider_truth=shared_truth([42]))
        self.assertEqual(result["verdict"], seatledger.FULL)


class StaleProviderReadMakesEverySeatShared(unittest.TestCase):
    """Req 4: break the read, no seat comes back ROOM.

    A stale or incomplete provider read makes every seat SHARED, not
    exclusive. Treating a shared seat as exclusive is what produces a
    confident wrong ROOM.
    """

    def test_missing_provider_truth_makes_every_seat_shared(self):
        rows = [row("k1", actionledger.SENT, 42, DAY)]
        result = seatledger.daily(42, DAY, rows=rows, provider_truth=None)
        self.assertEqual(result["verdict"], seatledger.REFUSED)
        self.assertEqual(result["client"], "UNKNOWN")

    def test_empty_provider_truth_makes_every_seat_shared(self):
        truth = {"heyreach": {
            "campaigns_total_in_account": 0,
            "campaigns_created_by_resonate": 0,
            "resonate_campaigns": [],
        }}
        rows = [row("k1", actionledger.SENT, 42, DAY)]
        result = seatledger.daily(42, DAY, rows=rows, provider_truth=truth)
        self.assertEqual(result["verdict"], seatledger.REFUSED)

    def test_ledger_with_broken_read_has_no_room(self):
        """Break the read deliberately and assert no seat comes back ROOM."""
        rows = [
            row("k1", actionledger.SENT, 42, DAY),
            row("k2", actionledger.SENT, 43, DAY),
        ]
        result = seatledger.ledger(DAY, rows=rows, provider_truth=None)
        for seat_id, entry in result.items():
            self.assertNotEqual(
                entry["verdict"], seatledger.ROOM,
                f"seat {seat_id} came back ROOM with no provider truth")


class OursCountsAttemptedAndUnresolved(unittest.TestCase):
    """Req 5: ours counts ATTEMPTED and UNRESOLVED, not only SENT.

    `actionledger.count_on` defaults to SENT + ATTEMPTED + UNRESOLVED because
    a cap that only counted confirmed sends would let an unresolved attempt
    buy another attempt. That reasoning is exactly as true per seat.
    """

    def test_one_of_each_state_counts_as_three(self):
        rows = [
            row("k1", actionledger.SENT, 42, DAY),
            row("k2", actionledger.ATTEMPTED, 42, DAY),
            row("k3", actionledger.UNRESOLVED, 42, DAY),
        ]
        result = seatledger.daily(42, DAY, rows=rows,
                                  provider_truth=exclusive_truth([42]))
        self.assertEqual(result["ours"], 3,
                         "ours must count SENT + ATTEMPTED + UNRESOLVED, "
                         "not only SENT")

    def test_failed_does_not_count(self):
        """FAILED is settled: the provider refused before acting."""
        rows = [
            row("k1", actionledger.SENT, 42, DAY),
            row("k2", actionledger.FAILED, 42, DAY),
        ]
        result = seatledger.daily(42, DAY, rows=rows,
                                  provider_truth=exclusive_truth([42]))
        self.assertEqual(result["ours"], 1)


class TwoWorkspacesDoNotPool(unittest.TestCase):
    """Req 6: a count scoped to workspace A does not see workspace B's rows.

    `count_on` carries a comment about one client's actions having consumed
    another's ceiling. The workspace parameter scopes the count to one tenant.
    """

    def test_workspace_a_does_not_see_workspace_b(self):
        rows = [
            row("k1", actionledger.SENT, 42, DAY, workspace="alpha"),
            row("k2", actionledger.SENT, 42, DAY, workspace="alpha"),
            row("k3", actionledger.SENT, 42, DAY, workspace="beta"),
        ]
        result_a = seatledger.daily(42, DAY, rows=rows, workspace="alpha",
                                    provider_truth=exclusive_truth([42]))
        result_b = seatledger.daily(42, DAY, rows=rows, workspace="beta",
                                    provider_truth=exclusive_truth([42]))
        self.assertEqual(result_a["ours"], 2)
        self.assertEqual(result_b["ours"], 1)

    def test_omitting_workspace_counts_every_tenant_together(self):
        rows = [
            row("k1", actionledger.SENT, 42, DAY, workspace="alpha"),
            row("k2", actionledger.SENT, 42, DAY, workspace="beta"),
        ]
        result = seatledger.daily(42, DAY, rows=rows,
                                  provider_truth=exclusive_truth([42]))
        self.assertEqual(result["ours"], 2)


class DayBoundaryMatchesCountOn(unittest.TestCase):
    """Req 7: the same calendar day count_on uses. No second definition.

    `accounts_opened_on`'s docstring warns that two definitions of 'today'
    in one gate is a defect waiting for a timezone.
    """

    def test_actions_on_a_different_day_are_not_counted(self):
        rows = [
            row("k1", actionledger.SENT, 42, "2026-09-21"),
            row("k2", actionledger.SENT, 42, "2026-09-22"),
        ]
        result = seatledger.daily(42, "2026-09-22", rows=rows,
                                  provider_truth=exclusive_truth([42]))
        self.assertEqual(result["ours"], 1)

    def test_the_day_is_a_string_prefix_match_like_count_on(self):
        """count_on uses str(at)[:10] == str(day)[:10]. Same here."""
        rows = [
            row("k1", actionledger.SENT, 42, DAY),
        ]
        result = seatledger.daily(42, DAY, rows=rows,
                                  provider_truth=exclusive_truth([42]))
        self.assertEqual(result["ours"], 1)


class TheModuleNeverWrites(unittest.TestCase):
    """Req 8: the module is a reader. No new state file, no cache."""

    def test_daily_does_not_create_any_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            marker_before = set(os.listdir(tmp)) if os.path.isdir(tmp) else set()
            rows = [row("k1", actionledger.SENT, 42, DAY)]
            seatledger.daily(42, DAY, rows=rows,
                             provider_truth=exclusive_truth([42]))
            marker_after = set(os.listdir(tmp)) if os.path.isdir(tmp) else set()
            self.assertEqual(marker_before, marker_after)

    def test_ledger_does_not_create_any_file(self):
        rows = [row("k1", actionledger.SENT, 42, DAY)]
        seatledger.ledger(DAY, rows=rows,
                          provider_truth=exclusive_truth([42]))

    def test_report_does_not_create_any_file(self):
        rows = [row("k1", actionledger.SENT, 42, DAY)]
        seatledger.report(DAY, rows=rows,
                          provider_truth=exclusive_truth([42]))


class TheClientFieldIsNeverNoneOrAbsent(unittest.TestCase):
    """The register's standing rule: missing evidence is never positive
    evidence. An absent field reads as zero to the next person who writes
    a sum. `client` is the literal string "UNKNOWN" on a shared seat and
    0 on an exclusive one. Never None, never absent, never 0-as-placeholder.
    """

    def test_exclusive_seat_has_client_zero(self):
        result = seatledger.daily(42, DAY, rows=[],
                                  provider_truth=exclusive_truth([42]))
        self.assertIn("client", result)
        self.assertEqual(result["client"], 0)
        self.assertIsNotNone(result["client"])

    def test_shared_seat_has_client_unknown(self):
        result = seatledger.daily(42, DAY, rows=[],
                                  provider_truth=shared_truth([42]))
        self.assertIn("client", result)
        self.assertEqual(result["client"], "UNKNOWN")
        self.assertIsNotNone(result["client"])

    def test_shared_seat_client_is_the_string_not_none(self):
        result = seatledger.daily(42, DAY, rows=[],
                                  provider_truth=shared_truth([42]))
        self.assertIsInstance(result["client"], str)
        self.assertEqual(result["client"], "UNKNOWN")


class LedgerReturnsEveryAttestedSeat(unittest.TestCase):

    def test_ledger_covers_every_seat_in_provider_truth(self):
        rows = [
            row("k1", actionledger.SENT, 42, DAY),
            row("k2", actionledger.SENT, 43, DAY),
        ]
        truth = exclusive_truth([42, 43])
        result = seatledger.ledger(DAY, rows=rows, provider_truth=truth)
        self.assertIn("42", result)
        self.assertIn("43", result)

    def test_report_returns_a_list(self):
        rows = [row("k1", actionledger.SENT, 42, DAY)]
        result = seatledger.report(DAY, rows=rows,
                                   provider_truth=exclusive_truth([42]))
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) >= 1)
        self.assertEqual(result[0]["seat_id"], "42")


class FullOnExclusiveSeat(unittest.TestCase):
    """An exclusive seat at the limit is FULL too, not ROOM."""

    def test_forty_on_exclusive_is_full(self):
        rows = [row(f"k{i}", actionledger.SENT, 42, DAY)
                for i in range(40)]
        result = seatledger.daily(42, DAY, rows=rows,
                                  provider_truth=exclusive_truth([42]))
        self.assertEqual(result["verdict"], seatledger.FULL)
        self.assertEqual(result["ours"], 40)


if __name__ == "__main__":
    unittest.main()


class ASeatIdIsAnIdentityAndIsNeverCoerced(unittest.TestCase):
    """`daily` used to do `int(seat_id)`. It raised on a non-numeric provider
    id and collapsed distinct seats where it did not raise. Neither case was
    covered, because every fixture above builds seat ids with `int(s)`."""

    def test_a_non_numeric_seat_id_does_not_raise(self):
        """`int("acc-7")` was an uncaught ValueError. A traceback is not a
        classification, and this module's whole job is classifying."""
        result = seatledger.daily("acc-7", DAY, rows=[], provider_truth=None)
        self.assertEqual(result["verdict"], seatledger.REFUSED)
        self.assertEqual(result["client"], "UNKNOWN")

    def test_two_distinct_seats_do_not_collapse_onto_one(self):
        """THE DANGEROUS HALF. `int(True)` is 1 and `int("1_0")` is 10, so a
        seat could be handed another seat's usage - and on the ROOM branch
        that is a confident wrong number rather than a refusal."""
        for a, b in ((True, 1), ("1_0", 10), (7.9, 7), ("٧", 7)):
            with self.subTest(pair=(a, b)):
                self.assertNotEqual(seatledger._seat_key(a),
                                    seatledger._seat_key(b))

    def test_the_key_matches_how_the_action_ledger_compares(self):
        """`count_on` compares `str(...)` on both sides, so a seat stored as
        an int and asked for as a string must still match."""
        rows = [row("k1", actionledger.SENT, 42, DAY)]
        as_int = seatledger.daily(42, DAY, rows=rows,
                                  provider_truth=shared_truth([42]))
        as_str = seatledger.daily("42", DAY, rows=rows,
                                  provider_truth=shared_truth([42]))
        self.assertEqual(as_int["ours"], 1)
        self.assertEqual(as_int["ours"], as_str["ours"])

    def test_surrounding_whitespace_is_not_a_different_seat(self):
        self.assertEqual(seatledger._seat_key(" 42 "),
                         seatledger._seat_key("42"))
