"""A live sequence HOLDs the account, and ownership is not asked.

OPERATOR DECISION, Zvonimir, 2026-10-02: "Kolizija: ako je osoba trenutno
mid-sequence u bilo kojoj aktivnoj kampanji, OS ili ne, verdikt je HOLD do kraja
te sekvence, ne STOP i ne DNC."

TWO QUESTIONS THAT WERE CONFLATED, AND THIS MODULE TESTS ONE OF THEM.

  ATTRIBUTION - whose campaign sent it. Non-OS history does not block and does
      not count as our touch. Tested in `test_an_undeclared_campaign_is_never_ours`,
      where the fail-closed rule lives: an unreadable authority is UNKNOWN,
      never "not ours".
  COLLISION - is somebody mid-sequence to this person right now. THIS module.
      Ownership is not consulted, so a non-OS sequence and an OS sequence must
      reach the SAME verdict, and a test that can tell them apart by owner is
      asserting the superseded rule.

THE FIRST VERSION OF THIS FILE GOT THAT WRONG and is worth recording. It asserted
that a non-OS sequence does NOT block, because `account_policy` had been wired to
gate the collision on the OS authority. The protection a mid-sequence check
provides is against TWO SENDERS REACHING ONE PERSON IN THE SAME WEEK, which does
not care whose campaign the other one is - so gating it on ownership let a
colleague actively being emailed by the client read as ALLOW.

HOLD, NOT STOP, AND NOT ALLOW. A sequence ends: STOP would write the account off
for a condition that clears itself, and ALLOW would send into the collision. HOLD
is "a person should look", re-evaluated when the sequence finishes. It blocks
exactly as hard as STOP did - `executionguard` requires ALLOW, both factories
test `in (STOP, HOLD)`, `nextaction` tests `!= ALLOW`.

EVERY ACCOUNT HERE IS ASSEMBLED THROUGH `collision.touches_of`, NOT BY HAND, so
the `campaigns` list in each person is built by the production function that
builds it in production - the other half of the reader fix.
"""
import unittest

from src import collision

#: In the ledger authority as measured 2026-10-02.
OURS = 487
#: Operator-declared internal, 2026-10-01. ~209,000 emails, never ours.
THEIRS = 352
#: In neither the authority nor the internal list.
STRANGER = 999999


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
    `anyone_in_sequence` and `campaigns` cannot drift from what production hands
    `account_policy`. `leads` is an int COUNT and `people` is the LIST - the
    distinction the broken reader got backwards.
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


class TheFixtureCarriesTheCollisionItClaims(unittest.TestCase):
    """THE POSITIVE CONTROL ON THE FIXTURES THEMSELVES.

    Every test below rests on `anyone_in_sequence` actually being True and the
    membership actually carrying its campaign id. If `account()` silently built
    a row with neither, the verdicts would be right for the wrong reason.
    """

    def test_a_live_membership_is_really_live_and_really_named(self):
        for campaign in (THEIRS, OURS, STRANGER):
            acct = account(lead("a@example.test",
                                [membership(campaign, collision.IN_SEQUENCE)]))
            self.assertTrue(acct["anyone_in_sequence"])
            self.assertEqual(({str(campaign)}, 0),
                             collision.mid_sequence_campaigns(acct))

    def test_a_finished_membership_is_not_live(self):
        """The negative control: the reader does not call history a collision."""
        acct = account(lead("a@example.test",
                            [membership(OURS, "sequence_finished")]))
        self.assertFalse(acct["anyone_in_sequence"])
        self.assertEqual((set(), 0), collision.mid_sequence_campaigns(acct))


class OwnershipDoesNotDecideACollision(unittest.TestCase):
    """THE TEST THE REFINEMENT TURNS ON. All three must agree.

    A non-OS sequence, an OS sequence and a sequence on a campaign nobody has
    ever declared must reach the SAME verdict. If any of these diverges from the
    others, ownership has been put back into the collision question.
    """

    def test_a_non_os_sequence_holds_the_account(self):
        verdict, why = collision.account_policy(account(
            lead("a@example.test", [membership(THEIRS, collision.IN_SEQUENCE,
                                               sent=5)], sent=5)))
        self.assertEqual(
            collision.HOLD, verdict,
            "a colleague being emailed by the client RIGHT NOW is a collision. "
            "ALLOW here is the defect the first version of this file shipped")
        self.assertIn("mid-sequence", why)
        self.assertIn("not finished", why)

    def test_an_os_sequence_holds_the_account_identically(self):
        verdict, why = collision.account_policy(account(
            lead("a@example.test", [membership(OURS, collision.IN_SEQUENCE,
                                               sent=5)], sent=5)))
        self.assertEqual(collision.HOLD, verdict, why)
        self.assertIn("mid-sequence", why)

    def test_a_campaign_nobody_declared_holds_the_account_too(self):
        verdict, _ = collision.account_policy(account(
            lead("a@example.test", [membership(STRANGER,
                                               collision.IN_SEQUENCE)])))
        self.assertEqual(collision.HOLD, verdict)

    def test_the_three_verdicts_are_literally_the_same(self):
        """Asserted as one comparison, so no future edit can change one of the
        three and leave the others looking fine."""
        verdicts = {
            collision.account_policy(account(
                lead("a@example.test", [membership(c, collision.IN_SEQUENCE)]
                     )))[0]
            for c in (THEIRS, OURS, STRANGER)}
        self.assertEqual({collision.HOLD}, verdicts)

    def test_the_reason_never_claims_ownership(self):
        """The verdict agreeing is not enough: a reason that says "which is
        ours" would mean the authority was still being consulted."""
        for campaign in (THEIRS, OURS, STRANGER):
            _, why = collision.account_policy(account(
                lead("a@example.test",
                     [membership(campaign, collision.IN_SEQUENCE)])))
            for word in ("ours", "which is ours", "not ours", "ledger"):
                self.assertNotIn(word, why,
                                 f"the reason must name the collision, not "
                                 f"ownership: {why!r}")


class ItIsNotStopAndNotDnc(unittest.TestCase):
    """A sequence ENDS, so the account is not written off."""

    def test_the_verdict_is_not_stop(self):
        verdict, _ = collision.account_policy(account(
            lead("a@example.test", [membership(THEIRS,
                                               collision.IN_SEQUENCE)])))
        self.assertNotEqual(collision.STOP, verdict,
                            "STOP says the account is answered, and a running "
                            "sequence has answered nothing")

    def test_the_reason_says_to_come_back(self):
        _, why = collision.account_policy(account(
            lead("a@example.test", [membership(THEIRS,
                                               collision.IN_SEQUENCE)])))
        self.assertIn("re-evaluate", why)

    def test_the_reason_names_what_is_running_so_somebody_can_look(self):
        _, why = collision.account_policy(account(
            lead("a@example.test", [membership(THEIRS,
                                               collision.IN_SEQUENCE)])))
        self.assertIn("352", why)


class AReplyIsTerminalAndIsAskedFirst(unittest.TestCase):
    """THE ORDERING THE HOLD CREATED.

    Both arms used to return STOP, so their order changed only the sentence.
    Mid-sequence is a HOLD now, so asking it first would DOWNGRADE an answered
    account to "come back later" - the one regression this change could have
    introduced silently.
    """

    def test_a_reply_beside_a_live_sequence_still_stops(self):
        verdict, why = collision.account_policy(account(
            lead("a@example.test", [membership(THEIRS, collision.IN_SEQUENCE)]),
            lead("b@example.test", [membership(THEIRS, "replied")],
                 replies=1)))
        self.assertEqual(collision.STOP, verdict, why)
        self.assertIn("answered", why)

    def test_interested_beside_a_live_sequence_still_stops(self):
        verdict, why = collision.account_policy(account(
            lead("a@example.test", [membership(OURS, collision.IN_SEQUENCE)]),
            lead("b@example.test", [membership(OURS, "sequence_finished",
                                               interested=True)])))
        self.assertEqual(collision.STOP, verdict, why)
        self.assertIn("answered", why)

    def test_a_reply_on_the_same_person_as_the_live_sequence_stops(self):
        """One person, two memberships: one live, one replied."""
        verdict, why = collision.account_policy(account(
            lead("a@example.test",
                 [membership(THEIRS, collision.IN_SEQUENCE),
                  membership(OURS, "replied")], replies=1)))
        self.assertEqual(collision.STOP, verdict, why)


class ACollisionCannotBeSoftenedByAShapeNobodyCanRead(unittest.TestCase):
    """HOLD for ANY live membership, including one that cannot be named.

    A reader bug must not be able to turn a collision into an ALLOW - which is
    exactly what the person-level `campaign_id` read did before it was fixed.
    """

    def test_a_claimed_collision_with_no_people_still_holds(self):
        verdict, why = collision.account_policy(
            {"verdict": collision.IN_SEQUENCE, "anyone_in_sequence": True,
             "people": [], "emails_sent_total": 2})
        self.assertEqual(collision.HOLD, verdict, why)
        self.assertIn("names no campaign", why)

    def test_a_live_membership_with_no_campaign_id_still_holds(self):
        acct = account(lead("a@example.test",
                            [membership(None, collision.IN_SEQUENCE)]))
        self.assertEqual((set(), 1), collision.mid_sequence_campaigns(acct))
        verdict, why = collision.account_policy(acct)
        self.assertEqual(collision.HOLD, verdict, why)

    def test_a_blank_campaign_id_is_not_a_campaign_called_empty(self):
        acct = account(lead("a@example.test",
                            [membership("   ", collision.IN_SEQUENCE)]))
        self.assertEqual((set(), 1), collision.mid_sequence_campaigns(acct))
        self.assertEqual(collision.HOLD, collision.account_policy(acct)[0])

    def test_an_unnamed_membership_is_counted_in_the_reason(self):
        """`unnamed` is reported rather than dropped: a live membership whose
        campaign cannot be named is a real gap in the provider answer, and a
        silent zero would hide it."""
        acct = account(
            lead("a@example.test", [membership(THEIRS, collision.IN_SEQUENCE)]),
            lead("b@example.test", [membership(None, collision.IN_SEQUENCE)]))
        verdict, why = collision.account_policy(acct)
        self.assertEqual(collision.HOLD, verdict)
        self.assertIn("352", why)
        self.assertIn("1 further live membership(s) name no campaign", why)


class EverythingElseInThePolicyIsUnchanged(unittest.TestCase):
    """Each arm checked on a campaign that is NOT ours, so none of them is
    leaning on an ownership read that no longer happens."""

    def test_a_reply_stops_it_whoever_sent_it(self):
        verdict, why = collision.account_policy(account(
            lead("a@example.test", [membership(THEIRS, "replied")], replies=1)))
        self.assertEqual(collision.STOP, verdict)
        self.assertIn("answered", why)

    def test_a_bounce_holds(self):
        verdict, why = collision.account_policy(account(
            lead("a@example.test", [membership(THEIRS, "sequence_finished")],
                 status="bounced")))
        self.assertEqual(collision.HOLD, verdict)
        self.assertIn("bounced", why)

    def test_a_campaign_that_ended_early_holds(self):
        verdict, why = collision.account_policy(account(
            lead("a@example.test", [membership(THEIRS, collision.STOPPED)])))
        self.assertEqual(collision.HOLD, verdict)
        self.assertIn("ended early", why)

    def test_an_unread_status_holds(self):
        verdict, why = collision.account_policy(account(
            lead("a@example.test", [membership(THEIRS, "mystery_state")])))
        self.assertEqual(collision.HOLD, verdict)
        self.assertIn("no verified meaning", why)

    def test_finished_with_no_reply_allows_and_reports_the_history(self):
        verdict, why = collision.account_policy(account(
            lead("a@example.test", [membership(THEIRS, "sequence_finished",
                                               sent=9)], sent=9)))
        self.assertEqual(collision.ALLOW, verdict)
        self.assertIn("9 email(s)", why)

    def test_nothing_at_all_allows(self):
        self.assertEqual(collision.ALLOW, collision.account_policy(account())[0])

    def test_an_unreadable_account_still_holds(self):
        verdict, why = collision.account_policy({"verdict": collision.UNKNOWN})
        self.assertEqual(collision.HOLD, verdict)
        self.assertIn("could not be read", why)


class TheCollisionArmAsksNoAuthorityAtAll(unittest.TestCase):
    """The structural proof, not just a behavioural one.

    If `account_policy` still reached for the ledger on this path, it would
    break in a store with no campaign file - or worse, quietly depend on one.
    Both halves of the authority are replaced with something that raises, and
    the verdict must be unaffected.
    """

    def test_the_verdict_holds_with_both_authorities_booby_trapped(self):
        def explode():
            raise AssertionError("account_policy must not ask about ownership "
                                 "on the collision path")

        saved = (collision.os_campaign_ids, collision.our_heyreach_campaign_ids)
        collision.os_campaign_ids = explode
        collision.our_heyreach_campaign_ids = explode
        try:
            for campaign in (THEIRS, OURS, STRANGER):
                verdict, _ = collision.account_policy(account(
                    lead("a@example.test",
                         [membership(campaign, collision.IN_SEQUENCE)])))
                self.assertEqual(collision.HOLD, verdict)
        finally:
            collision.os_campaign_ids, collision.our_heyreach_campaign_ids = saved

    def test_the_booby_trap_really_intercepts(self):
        """THE CONTROL ON THE TEST ABOVE, and it has to be a real one.

        If patching those two names did not actually intercept anything, the
        test above would pass while proving nothing at all. So the same patch is
        applied to a caller that DOES consult the authority - `osattribution`,
        which is the attribution path - and it must raise. That is the proof
        that the collision path's silence is a fact about the collision path and
        not about a patch that missed.
        """
        from src import osattribution

        def explode():
            raise AssertionError("intercepted")

        saved = collision.os_campaign_ids
        collision.os_campaign_ids = explode
        try:
            with self.assertRaises(AssertionError):
                osattribution.authority("bison")
        finally:
            collision.os_campaign_ids = saved


class TheReaderReadsTheShapeTheProviderSends(unittest.TestCase):
    """THE READER BUG, AS A TEST.

    `people` is the LIST and `leads` is an int COUNT. Each person's memberships
    live under `campaigns`, a LIST of dicts carrying `campaign_id`. A reader that
    asks the PERSON for a flat `campaign_id` finds nothing on every row and
    reports an empty set - and because an empty set used to un-block the gate,
    nothing failed to say so.
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
                         "the person-level read finds nothing on every row")
        self.assertEqual(({"487", "352"}, 0),
                         collision.mid_sequence_campaigns(self.acct))

    def test_only_live_memberships_are_collected(self):
        """`sequence_finished` on 352 sits in the same person's list as the live
        487. A reader that returned every campaign would report history as a
        collision."""
        finished = account(lead("c@example.test",
                                [membership(OURS, "sequence_finished")]))
        self.assertEqual((set(), 0),
                         collision.mid_sequence_campaigns(finished))

    def test_the_id_type_does_not_decide_anything(self):
        """`"487" in {487}` is false. `campaign_key` is the one place that
        settles it, and the reason names the campaign either way."""
        for spelling in (487, "487", " 487 ", "0487"):
            acct = account(lead("a@example.test",
                                [membership(spelling, collision.IN_SEQUENCE)]))
            live, unnamed = collision.mid_sequence_campaigns(acct)
            self.assertEqual(({"487"}, 0), (live, unnamed),
                             f"campaign_id {spelling!r} is campaign 487")
            self.assertEqual(collision.HOLD,
                             collision.account_policy(acct)[0])


if __name__ == "__main__":
    unittest.main()
