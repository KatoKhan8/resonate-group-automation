"""Preconditions 3 and 4: the seat, and the daily cap.

PRECONDITION 3 - THE SEAT. A campaign may only go from a seat attested to a
NAMED human, and the operator names that human in the GO. `_owner_for`
already refused a seat with no roster row and a seat with no attested owner;
what it could not refuse is a seat that resolves cleanly to the WRONG human,
because nothing told it which human was authorised. A campaign on the wrong
seat is NO-GO, not a warning.

PRECONDITION 4 - THE CAP, from provider measurement rather than from a
quote. Measured 2026-10-03 against the live HeyReach estate:

    TOTAL_SEATS 41   MAXES [40]   AUTHVALID_TRUE 33 FALSE 8
    LIMITS [5, 10, 15, 17, 18, 19, 22, 23, 25, 40]

`connectioRequestMax` is 40 on all 41 seats. HeyReach policy is 30. Day one
of the pilot is 5. The smallest always wins.
"""
import unittest

from src import executionguard, linkedincap


def seat(seat_id="116968", auth=True, active=True, cooldown=None,
         limit=40, maximum=40):
    row = {"id": seat_id, "authIsValid": auth, "isActive": active,
           "someLimits": {linkedincap.PROVIDER_LIMIT_FIELD: limit,
                          linkedincap.PROVIDER_MAX_FIELD: maximum}}
    for field in linkedincap.COOLDOWN_FIELDS:
        row[field] = False
    for field in (cooldown or ()):
        row[field] = True
    return row


# --------------------------------------------------------------- the seat

class TheNamedSeatOwner(unittest.TestCase):
    """`executionguard.require_named_seat_owner`, driven directly."""

    def test_the_right_human_passes(self):
        campaign = {"client": "productive",
                    executionguard.SEAT_OWNER_KEY: "li_mina_ruzicic"}
        self.assertEqual(
            executionguard.require_named_seat_owner(
                campaign, "linkedin", "li_mina_ruzicic"),
            "li_mina_ruzicic")

    def test_the_wrong_human_is_REFUSED_not_warned(self):
        """THE PRECONDITION. A mismatch raises; it does not return a flag."""
        campaign = {"client": "productive",
                    executionguard.SEAT_OWNER_KEY: "li_mina_ruzicic"}
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            executionguard.require_named_seat_owner(
                campaign, "linkedin", "li_luka_nikolic")
        self.assertEqual(caught.exception.gate, "sender")
        self.assertIn("WRONG SEAT", caught.exception.why)

    def test_naming_nobody_is_refused(self):
        """Fails closed. An unnamed seat is not an implicitly approved one."""
        with self.assertRaises(executionguard.SeatNotNamed) as caught:
            executionguard.require_named_seat_owner(
                {"client": "productive"}, "linkedin", "li_mina_ruzicic")
        self.assertEqual(caught.exception.gate, "sender")

    def test_a_blank_name_is_not_a_name(self):
        for empty in ("", "   ", None, 0, [], {}):
            with self.assertRaises(executionguard.NotAuthorized, msg=empty):
                executionguard.require_named_seat_owner(
                    {executionguard.SEAT_OWNER_KEY: empty},
                    "linkedin", "li_mina_ruzicic")

    def test_a_non_string_name_cannot_accidentally_match(self):
        """A list containing the right id must not pass.

        `in`-style or truthiness-style checks are how this kind of guard
        fails open; asserted so a future rewrite cannot reintroduce one.
        """
        with self.assertRaises(executionguard.NotAuthorized):
            executionguard.require_named_seat_owner(
                {executionguard.SEAT_OWNER_KEY: ["li_mina_ruzicic"]},
                "linkedin", "li_mina_ruzicic")

    def test_email_is_untouched_by_this_rule(self):
        """The asymmetry is deliberate: an email sender is a mailbox."""
        self.assertEqual(
            executionguard.require_named_seat_owner({}, "email", "human-487"),
            "human-487")

    def test_the_refusal_carries_the_gate_trace(self):
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            executionguard.require_named_seat_owner(
                {executionguard.SEAT_OWNER_KEY: "a"}, "linkedin", "b",
                gates=("tenancy", "approval", "readback"))
        self.assertEqual(caught.exception.passed,
                         ("tenancy", "approval", "readback"))


# ---------------------------------------------------------------- the cap

class TheMeasuredNumbers(unittest.TestCase):
    def test_the_provider_hard_ceiling_is_the_measured_forty(self):
        self.assertEqual(linkedincap.PROVIDER_HARD_CEILING, 40)

    def test_the_policy_ceiling_is_thirty(self):
        self.assertEqual(linkedincap.PROVIDER_POLICY_CEILING, 30)

    def test_day_one_is_five(self):
        self.assertEqual(linkedincap.PILOT_DAY_ONE, 5)

    def test_the_misspelled_provider_fields_are_preserved(self):
        """HeyReach's own typo. Correcting it reads the wrong key."""
        self.assertEqual(linkedincap.PROVIDER_MAX_FIELD, "connectioRequestMax")
        self.assertEqual(linkedincap.PROVIDER_LIMIT_FIELD,
                         "connectioRequestLimit")


class TheSmallestCeilingWins(unittest.TestCase):
    def test_day_one_beats_policy_and_the_provider(self):
        self.assertEqual(linkedincap.day_one_cap(seat()),
                         linkedincap.PILOT_DAY_ONE)

    def test_a_seat_configured_below_day_one_wins_over_day_one(self):
        """A seat set to 3 gets 3, not 5. The smallest always wins."""
        self.assertEqual(linkedincap.day_one_cap(seat(limit=3)), 3)

    def test_measured_spend_reduces_the_cap(self):
        """38 of 40 already spent leaves 2, not 5."""
        self.assertEqual(linkedincap.day_one_cap(seat(), spent_today=38), 2)

    def test_a_seat_at_its_ceiling_gets_nothing(self):
        self.assertEqual(linkedincap.day_one_cap(seat(), spent_today=40), 0)

    def test_spend_beyond_the_ceiling_does_not_go_negative(self):
        self.assertEqual(linkedincap.day_one_cap(seat(), spent_today=99), 0)

    def test_the_cap_never_exceeds_five_however_generous_the_seat(self):
        self.assertLessEqual(
            linkedincap.day_one_cap(seat(limit=40, maximum=40)), 5)


class ASeatThatDropsOut(unittest.TestCase):
    def test_auth_invalid_drops_out(self):
        with self.assertRaises(linkedincap.SeatUnusable) as caught:
            linkedincap.day_one_cap(seat(auth=False))
        self.assertIn("authIsValid", caught.exception.why)

    def test_cooldown_drops_out(self):
        with self.assertRaises(linkedincap.SeatUnusable) as caught:
            linkedincap.day_one_cap(
                seat(cooldown=("connectionRequestCooldown",)))
        self.assertIn("cooldown", caught.exception.why)

    def test_inactive_drops_out(self):
        with self.assertRaises(linkedincap.SeatUnusable):
            linkedincap.day_one_cap(seat(active=False))

    def test_a_dropped_seat_does_not_stop_the_batch(self):
        """The operator's rule: NO-GO for that seat, not for the batch."""
        seats = [seat("A"), seat("B", auth=False),
                 seat("C", cooldown=("inMailCooldown",)), seat("D")]
        spent = {s: 0 for s in ('A', 'B', 'C', 'D')}
        assignment, dropped = linkedincap.allocate(
            seats, list(range(10)), spent_by_seat=spent)
        self.assertEqual(sorted(assignment), ["A", "D"])
        self.assertEqual(sorted(s for s, _why in dropped), ["B", "C"])
        # Two surviving seats at the day-one cap of 5 carry all ten.
        self.assertEqual(sum(len(v) for v in assignment.values()), 10)
        self.assertEqual(len(assignment["A"]), 5)
        self.assertEqual(len(assignment["D"]), 5)


class HeadroomIsNotInvented(unittest.TestCase):
    """The provider publishes no remaining-today counter. Checked on all 41."""

    def test_unmeasured_spend_is_reported_as_unmeasured(self):
        self.assertFalse(linkedincap.headroom_is_known(None))

    def test_measured_spend_is_reported_as_measured(self):
        self.assertTrue(linkedincap.headroom_is_known(0))

    def test_zero_is_measured_and_is_not_confused_with_unknown(self):
        """0 spent is a fact; not asking is not. They must not collapse."""
        self.assertTrue(linkedincap.headroom_is_known(0))
        self.assertNotEqual(linkedincap.UNKNOWN, 0)

    def test_a_seat_with_no_stated_limit_reports_unknown_not_zero(self):
        bare = {"id": "X", "authIsValid": True, "isActive": True}
        self.assertEqual(linkedincap.configured_limit(bare),
                         linkedincap.UNKNOWN)
        self.assertEqual(linkedincap.provider_max(bare), linkedincap.UNKNOWN)

    def test_an_unstated_limit_still_caps_at_day_one(self):
        bare = {"id": "X", "authIsValid": True, "isActive": True}
        for field in linkedincap.COOLDOWN_FIELDS:
            bare[field] = False
        self.assertEqual(linkedincap.day_one_cap(bare),
                         linkedincap.PILOT_DAY_ONE)


class AllocationGoesToTheFreestSeats(unittest.TestCase):
    def test_twenty_candidates_across_four_seats_respects_the_cap(self):
        seats = [seat(s) for s in ("A", "B", "C", "D")]
        assignment, dropped = linkedincap.allocate(
            seats, list(range(20)),
            spent_by_seat={s: 0 for s in ('A', 'B', 'C', 'D')})
        self.assertEqual(dropped, [])
        for seat_id, got in assignment.items():
            self.assertLessEqual(len(got), 5, seat_id)
        self.assertEqual(sum(len(v) for v in assignment.values()), 20)

    def test_nobody_is_assigned_twice(self):
        seats = [seat(s) for s in ("A", "B", "C", "D")]
        assignment, _ = linkedincap.allocate(
            seats, list(range(20)),
            spent_by_seat={s: 0 for s in ('A', 'B', 'C', 'D')})
        everyone = [c for got in assignment.values() for c in got]
        self.assertEqual(len(everyone), len(set(everyone)))

    def test_more_candidates_than_capacity_leaves_them_unassigned(self):
        """It must not exceed a cap to make the numbers come out."""
        assignment, _ = linkedincap.allocate(
            [seat("A")], list(range(20)), spent_by_seat={"A": 0})
        self.assertEqual(sum(len(v) for v in assignment.values()), 5)

    def test_allocation_is_stable_across_runs(self):
        seats = [seat(s) for s in ("A", "B", "C", "D")]
        spent = {s: 0 for s in ('A', 'B', 'C', 'D')}
        first, _ = linkedincap.allocate(
            seats, list(range(20)), spent_by_seat=spent)
        second, _ = linkedincap.allocate(
            seats, list(range(20)), spent_by_seat=spent)
        self.assertEqual(first, second)

    def test_a_seat_with_more_measured_headroom_is_filled_first(self):
        seats = [seat("LOW", limit=2), seat("HIGH", limit=40)]
        assignment, _ = linkedincap.allocate(
            seats, list(range(3)), spent_by_seat={"LOW": 0, "HIGH": 0})
        self.assertEqual(len(assignment["HIGH"]), 2)
        self.assertEqual(len(assignment["LOW"]), 1)


if __name__ == "__main__":
    unittest.main()


class UnknownIsNotHeadroom(unittest.TestCase):
    """Invariant 0, applied to the number the pilot is sized against.

    VERIFIED AT THE PROVIDER 2026-10-03, not inherited from a task note.
    The HeyReach seat object carries 24 fields; every numeric one is a
    LIMIT or a MAX. There is no used-today counter on any route, so today's
    spend must be derived - and the only derivation available counts
    conversations, while an unaccepted connection request creates none. The
    derivation therefore cannot see the quantity being capped, and its
    undercount is unbounded.
    """

    def test_an_unmeasured_seat_drops_out_by_default(self):
        assignment, dropped = linkedincap.allocate([seat("A")], [1, 2, 3])
        self.assertEqual(assignment, {})
        self.assertEqual([s for s, _why in dropped], ["A"])
        self.assertIn("UNKNOWN is not headroom", dropped[0][1])

    def test_an_unmeasured_seat_is_not_quietly_given_the_day_one_five(self):
        """The failure mode this exists to stop.

        `day_one_cap` returns 5 for an unmeasured seat, and that is correct
        for a cap. Turning that 5 into an ALLOCATION asserts the seat has 5
        free, which nothing measured.
        """
        self.assertEqual(linkedincap.day_one_cap(seat("A")), 5)
        assignment, _dropped = linkedincap.allocate([seat("A")], [1, 2, 3])
        self.assertEqual(sum(len(v) for v in assignment.values()), 0)

    def test_a_measured_zero_is_headroom_and_an_absent_one_is_not(self):
        measured, _ = linkedincap.allocate([seat("A")], [1, 2, 3],
                                           spent_by_seat={"A": 0})
        absent, _ = linkedincap.allocate([seat("A")], [1, 2, 3])
        self.assertEqual(sum(len(v) for v in measured.values()), 3)
        self.assertEqual(sum(len(v) for v in absent.values()), 0)

    def test_a_partially_measured_estate_places_only_on_measured_seats(self):
        seats = [seat("A"), seat("B"), seat("C")]
        assignment, dropped = linkedincap.allocate(
            seats, list(range(12)), spent_by_seat={"B": 0})
        self.assertEqual(sorted(assignment), ["B"])
        self.assertEqual(len(assignment["B"]), 5)
        self.assertEqual(sorted(s for s, _w in dropped), ["A", "C"])

    def test_the_escape_hatch_exists_and_is_not_the_default(self):
        """`require_measured=False` is available and must be asked for."""
        opened, _ = linkedincap.allocate([seat("A")], [1, 2, 3],
                                         require_measured=False)
        self.assertEqual(sum(len(v) for v in opened.values()), 3)
