"""Mid-sequence STOPs only on a campaign the OS authority holds.

OPERATOR DECISION, Zvonimir, 2026-10-02: "STOP na mid-sequence samo ako je
sekvenca na OS kampanji po tom autoritetu." `account_policy` used to STOP on
"somebody at this account is mid-sequence right now" without ever asking whose
campaign it was, so a lead sitting in one of the operator's own internal
campaigns - 274, 327, 328, 352 - refused our outreach at that account until a
campaign nobody intends to stop stopped.

THE TWO TESTS THE OPERATOR NAMED ARE `ANonOsSequenceDoesNotBlock` AND
`AnOsSequenceStillStops`. The first fails if a non-OS sequence is treated as a
block. The second exists because the first on its own only proves the gate can
be loosened, which is not the same as proving it still bites.

EVERY ACCOUNT HERE IS ASSEMBLED THROUGH `collision.touches_of`, NOT BY HAND.
That is deliberate and it is the other half of this change: the reader bug being
fixed was a reader that asked the PERSON for a flat `campaign_id`, and a
hand-built fixture would have let the same wrong shape in through the test. The
`campaigns` list in each person below is built by the production function that
builds it in production.
"""
import json
import os
import tempfile
import unittest

from src import collision, store

#: In the authority as measured 2026-10-02. 487 is paused, which is irrelevant
#: here - a paused CAMPAIGN can still hold an `in_sequence` MEMBERSHIP, and
#: ownership is the only question this arm asks.
OURS = 487
#: Operator-declared internal, 2026-10-01. ~209,000 emails, never ours.
THEIRS = 352
#: The twenty bison campaigns the authority held when measured.
AUTHORITY = frozenset({451, 481, 484, 485, 487, 489, 491, 492, 493, 494,
                       495, 496, 497, 498, 500, 501, 503, 504, 505, 506})


def membership(campaign_id, status, sent=1, replies=0, opens=0,
               interested=False):
    """One row of the provider's `lead_campaign_data`, in its own shape."""
    return {"campaign_id": campaign_id, "status": status, "emails_sent": sent,
            "replies": replies, "opens": opens, "interested": interested}


def lead(email, memberships, sent=1, replies=0, status="active"):
    """One RAW EmailBison lead row, as the provider returns it."""
    return {"email": email, "id": 9000 + len(email), "status": status,
            "overall_stats": {"emails_sent": sent, "replies": replies,
                              "opens": 0},
            "lead_campaign_data": list(memberships),
            "created_at": "2026-08-01T00:00:00+00:00"}


def account(*rows):
    """A `check_account` answer, derived the way `check_account` derives it.

    Mirrors the real assembly rather than inventing one, so `people`,
    `anyone_in_sequence` and `campaigns` cannot drift from what production
    hands `account_policy`. `leads` is an int COUNT and `people` is the LIST -
    the distinction the broken reader got backwards.
    """
    people = [collision.touches_of(r) for r in rows]
    sent = sum(p["emails_sent"] for p in people)
    return {
        "domain": "example.test",
        "workspace": "productive",
        "leads": len(people),
        "people": people,
        "our_staging_excluded": [],
        "emails_sent_total": sent,
        "anyone_in_sequence": any(p["in_sequence"] for p in people),
        "unknown_statuses": sorted({s for p in people
                                    for s in p["unknown_statuses"]}),
        "any_bounce": any(collision._norm(p["lead_status"]) == "bounced"
                          for p in people),
        "verdict": (collision.IN_SEQUENCE
                    if any(p["in_sequence"] for p in people)
                    else collision.TOUCHED if sent else collision.CLEAR),
        "checked_at": "2026-10-02T00:00:00+00:00",
    }


def policy(acct, authority=AUTHORITY, readable=True):
    return collision.account_policy(acct, os_campaigns=authority,
                                    ledger_readable=readable)


class TheFixtureCarriesTheCollisionItClaims(unittest.TestCase):
    """THE POSITIVE CONTROL ON THE FIXTURES THEMSELVES.

    Every test below rests on `anyone_in_sequence` actually being True and the
    membership actually carrying its campaign id. If `account()` silently built
    a row with neither, the loosening tests would pass for the wrong reason -
    an account with no live membership ALLOWs trivially.
    """

    def test_a_non_os_sequence_is_really_live_and_really_named(self):
        acct = account(lead("a@example.test", [membership(THEIRS,
                                                         collision.IN_SEQUENCE)]))
        self.assertTrue(acct["anyone_in_sequence"])
        live, unnamed = collision.mid_sequence_campaigns(acct)
        self.assertEqual({"352"}, live)
        self.assertEqual(0, unnamed)

    def test_an_os_sequence_is_really_live_and_really_named(self):
        acct = account(lead("a@example.test", [membership(OURS,
                                                         collision.IN_SEQUENCE)]))
        self.assertTrue(acct["anyone_in_sequence"])
        self.assertEqual(({"487"}, 0), collision.mid_sequence_campaigns(acct))


class ANonOsSequenceDoesNotBlock(unittest.TestCase):
    """THE TEST THE OPERATOR NAMED. It FAILS if a non-OS sequence blocks."""

    def test_a_colleague_mid_sequence_on_an_internal_campaign_does_not_stop_us(self):
        verdict, why = policy(account(
            lead("a@example.test", [membership(THEIRS, collision.IN_SEQUENCE,
                                               sent=5)], sent=5)))
        self.assertNotEqual(
            collision.STOP, verdict,
            "campaign 352 is operator-declared internal. Under the rule of "
            "2026-10-02 a sequence of theirs is not our collision, and "
            "treating it as a block is the defect this test exists to catch")
        self.assertEqual(collision.ALLOW, verdict, why)

    def test_the_history_is_still_reported_rather_than_dropped(self):
        """It does not block, and it is not silently forgotten either: the
        account's own sends still reach the operator's sentence, so nobody can
        call this account cold."""
        verdict, why = policy(account(
            lead("a@example.test", [membership(THEIRS, collision.IN_SEQUENCE,
                                               sent=5)], sent=5)))
        self.assertEqual(collision.ALLOW, verdict)
        self.assertIn("5 email(s) were sent to this account", why)

    def test_an_unknown_campaign_nobody_has_declared_does_not_block_either(self):
        """999999 is in neither the authority nor the internal list. It is
        positively attributed and positively not ours, which is the whole
        condition - absence from the authority is the answer, not a gap."""
        verdict, _ = policy(account(
            lead("a@example.test", [membership(999999, collision.IN_SEQUENCE)])))
        self.assertEqual(collision.ALLOW, verdict)


class AnOsSequenceStillStops(unittest.TestCase):
    """Without this, the pair above only proves the gate can be loosened."""

    def test_a_colleague_mid_sequence_on_our_own_campaign_stops_it(self):
        verdict, why = policy(account(
            lead("a@example.test", [membership(OURS, collision.IN_SEQUENCE)])))
        self.assertEqual(collision.STOP, verdict, why)
        self.assertIn("mid-sequence", why)
        self.assertIn("487", why)
        self.assertIn("ours", why)

    def test_one_of_ours_among_several_of_theirs_still_stops_it(self):
        """The arm asks whether ANY live membership is ours, so a single
        sequence of ours is not outvoted by three of somebody else's."""
        verdict, why = policy(account(
            lead("a@example.test", [membership(THEIRS, collision.IN_SEQUENCE)]),
            lead("b@example.test", [membership(327, collision.IN_SEQUENCE)]),
            lead("c@example.test", [membership(OURS, collision.IN_SEQUENCE)])))
        self.assertEqual(collision.STOP, verdict, why)
        self.assertIn("487", why)

    def test_the_id_type_does_not_decide_it(self):
        """`"487" in {487}` is false. If the comparison ever goes back to raw
        types, our own live campaign reads as somebody else's and this gate
        un-blocks silently."""
        for spelling in (487, "487", " 487 "):
            verdict, why = policy(account(
                lead("a@example.test",
                     [membership(spelling, collision.IN_SEQUENCE)])))
            self.assertEqual(collision.STOP, verdict,
                             f"campaign_id {spelling!r} is campaign 487")


class AnUnidentifiableSequenceFailsClosed(unittest.TestCase):
    """UNKNOWN must not become "not ours". This is the fail-closed arm.

    An account claiming `anyone_in_sequence` while carrying nothing to check it
    against is the shape every hand-built fixture in the suite has, and it is
    also what a future reader bug would produce. If that collapsed to ALLOW,
    every account whose shape this function misreads would become sendable -
    which is the same class of defect as the reader bug itself, one layer up.
    """

    def test_a_claimed_collision_with_no_people_still_stops(self):
        verdict, why = policy({"verdict": collision.IN_SEQUENCE,
                               "anyone_in_sequence": True, "people": [],
                               "emails_sent_total": 2})
        self.assertEqual(collision.STOP, verdict, why)
        self.assertIn("does not name a campaign", why)

    def test_a_live_membership_with_no_campaign_id_still_stops(self):
        acct = account(lead("a@example.test",
                            [membership(None, collision.IN_SEQUENCE)]))
        self.assertEqual((set(), 1), collision.mid_sequence_campaigns(acct))
        verdict, why = policy(acct)
        self.assertEqual(collision.STOP, verdict, why)
        self.assertIn("does not name a campaign", why)

    def test_a_blank_campaign_id_is_not_a_campaign_called_empty(self):
        acct = account(lead("a@example.test",
                            [membership("   ", collision.IN_SEQUENCE)]))
        self.assertEqual((set(), 1), collision.mid_sequence_campaigns(acct))
        self.assertEqual(collision.STOP, policy(acct)[0])

    def test_one_unnamed_membership_stops_it_even_beside_a_named_foreign_one(self):
        """The unnamed row is not outvoted by a row that IS attributable. One
        sequence nobody can identify is one sequence that might be ours."""
        acct = account(
            lead("a@example.test", [membership(THEIRS, collision.IN_SEQUENCE)]),
            lead("b@example.test", [membership(None, collision.IN_SEQUENCE)]))
        verdict, why = policy(acct)
        self.assertEqual(collision.STOP, verdict, why)


class AnUnreadableAuthorityFailsClosed(unittest.TestCase):
    """Not knowing whose campaign it is is not knowing it is not ours.

    `os_campaign_ids` returns `(ids, readable)` precisely because an empty set
    means both "we own nothing" and "the file could not be read". Here the two
    must diverge: empty-but-READ lets a foreign sequence through, UNREADABLE
    does not.
    """

    def test_an_unreadable_ledger_stops_a_sequence_it_cannot_attribute(self):
        verdict, why = policy(
            account(lead("a@example.test",
                         [membership(THEIRS, collision.IN_SEQUENCE)])),
            authority=frozenset(), readable=False)
        self.assertEqual(collision.STOP, verdict, why)
        self.assertIn("could not be read", why)

    def test_an_empty_but_read_ledger_is_not_the_same_answer(self):
        """The control that makes the test above mean something: with the same
        empty set and `readable=True`, the sequence does NOT block."""
        verdict, _ = policy(
            account(lead("a@example.test",
                         [membership(THEIRS, collision.IN_SEQUENCE)])),
            authority=frozenset(), readable=True)
        self.assertEqual(collision.ALLOW, verdict)

    def test_an_unreadable_ledger_does_not_override_a_reply(self):
        """STOP either way, but the reason must stay the true one - an answered
        account is answered whether or not the ledger could be read."""
        verdict, why = policy(
            account(lead("a@example.test",
                         [membership(THEIRS, "replied")], replies=1)),
            authority=frozenset(), readable=False)
        self.assertEqual(collision.STOP, verdict)
        self.assertIn("answered", why)


class EverythingElseInThePolicyIsUnchanged(unittest.TestCase):
    """The other arms are not touched by this, and each is checked on a
    campaign that is NOT ours - so none of them is quietly leaning on the
    mid-sequence STOP that used to fire first."""

    def test_a_reply_stops_it_whoever_sent_it(self):
        verdict, why = policy(account(
            lead("a@example.test", [membership(THEIRS, "replied")], replies=1)))
        self.assertEqual(collision.STOP, verdict)
        self.assertIn("answered", why)

    def test_an_interested_mark_stops_it_whoever_sent_it(self):
        verdict, why = policy(account(
            lead("a@example.test", [membership(THEIRS, "sequence_finished",
                                               interested=True)])))
        self.assertEqual(collision.STOP, verdict)
        self.assertIn("answered", why)

    def test_a_bounce_holds(self):
        verdict, why = policy(account(
            lead("a@example.test", [membership(THEIRS, "sequence_finished")],
                 status="bounced")))
        self.assertEqual(collision.HOLD, verdict)
        self.assertIn("bounced", why)

    def test_a_campaign_that_ended_early_holds(self):
        verdict, why = policy(account(
            lead("a@example.test", [membership(THEIRS, collision.STOPPED)])))
        self.assertEqual(collision.HOLD, verdict)
        self.assertIn("ended early", why)

    def test_an_unread_status_holds(self):
        verdict, why = policy(account(
            lead("a@example.test", [membership(THEIRS, "mystery_state")])))
        self.assertEqual(collision.HOLD, verdict)
        self.assertIn("no verified meaning", why)

    def test_finished_with_no_reply_allows_and_reports_the_history(self):
        verdict, why = policy(account(
            lead("a@example.test", [membership(THEIRS, "sequence_finished",
                                               sent=9)], sent=9)))
        self.assertEqual(collision.ALLOW, verdict)
        self.assertIn("9 email(s)", why)

    def test_an_unreadable_account_still_holds(self):
        verdict, why = policy({"verdict": collision.UNKNOWN})
        self.assertEqual(collision.HOLD, verdict)
        self.assertIn("could not be read", why)


class TheAuthorityIsAskedWhenItIsNotInjected(unittest.TestCase):
    """`os_campaigns=None` must reach the real `os_campaign_ids`, not a stub.

    Injection is what every other test here uses, so without this one the
    production path - the one with no keyword arguments - would be untested and
    could be wired to nothing at all.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))

    def write_ledger(self, bison_ids):
        with open(os.path.join(self.tmp, "campaigns.jsonl"), "w",
                  encoding="utf-8") as handle:
            for cid in bison_ids:
                handle.write(json.dumps({"campaign_id": f"fixture-{cid}",
                                         "bison_campaign_id": cid}) + "\n")

    def test_a_ledger_bound_campaign_stops_it_with_no_injection(self):
        self.write_ledger([OURS])
        ids, readable = collision.os_campaign_ids()
        self.assertEqual((frozenset({487}), True), (ids, readable))
        verdict, why = collision.account_policy(account(
            lead("a@example.test", [membership(OURS, collision.IN_SEQUENCE)])))
        self.assertEqual(collision.STOP, verdict, why)
        self.assertIn("487", why)

    def test_a_campaign_absent_from_the_ledger_does_not_block_with_no_injection(self):
        self.write_ledger([OURS])
        verdict, _ = collision.account_policy(account(
            lead("a@example.test", [membership(THEIRS,
                                               collision.IN_SEQUENCE)])))
        self.assertEqual(collision.ALLOW, verdict)


class TheReaderReadsTheShapeTheProviderSends(unittest.TestCase):
    """THE READER BUG, AS A TEST.

    `people` is the LIST and `leads` is an int COUNT. Each person's memberships
    live under `campaigns`, a LIST of dicts carrying `campaign_id`. A reader
    that asks the PERSON for a flat `campaign_id` finds nothing on every row and
    reports an empty set - which reads as "nobody is mid-sequence" and un-blocks
    the gate, so nothing fails to announce it.
    """

    def setUp(self):
        self.acct = account(
            lead("a@example.test", [membership(OURS, collision.IN_SEQUENCE),
                                    membership(THEIRS, "sequence_finished")]),
            lead("b@example.test", [membership(THEIRS, collision.IN_SEQUENCE)]))

    def test_leads_is_a_count_and_people_is_the_list(self):
        self.assertIsInstance(self.acct["leads"], int)
        self.assertEqual(2, self.acct["leads"])
        self.assertIsInstance(self.acct["people"], list)
        self.assertEqual(2, len(self.acct["people"]))

    def test_each_person_carries_a_list_of_campaign_dicts(self):
        person = self.acct["people"][0]
        self.assertIsInstance(person["campaigns"], list)
        self.assertEqual(2, len(person["campaigns"]))
        for row in person["campaigns"]:
            self.assertIsInstance(row, dict)
            for field in ("campaign_id", "status", "emails_sent", "replies",
                          "opens", "interested"):
                self.assertIn(field, row)

    def test_there_is_no_flat_campaign_id_on_the_person(self):
        """THE NEGATIVE CONTROL, AND THE BUG ITSELF. The key the broken reader
        looked for is not there, on any person."""
        for person in self.acct["people"]:
            self.assertNotIn("campaign_id", person)

    def test_the_broken_reader_sees_nothing_and_the_fixed_one_sees_both(self):
        broken = {p.get("campaign_id") for p in self.acct["people"]
                  if p.get("campaign_id")}
        self.assertEqual(set(), broken,
                         "the person-level read finds nothing - and an empty "
                         "set is exactly what 'nobody is mid-sequence' looks "
                         "like, which is why this was silent")
        live, unnamed = collision.mid_sequence_campaigns(self.acct)
        self.assertEqual({"487", "352"}, live)
        self.assertEqual(0, unnamed)

    def test_only_live_memberships_are_collected(self):
        """`sequence_finished` on 352 is in the same person's list as the live
        487. A reader that returned every campaign would block on history."""
        live, _ = collision.mid_sequence_campaigns(self.acct)
        finished = account(lead("c@example.test",
                                [membership(OURS, "sequence_finished")]))
        self.assertIn("352", live)       # live on person b, not the finished one
        self.assertEqual((set(), 0),
                         collision.mid_sequence_campaigns(finished))


if __name__ == "__main__":
    unittest.main()
