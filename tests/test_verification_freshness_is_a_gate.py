"""TASK-979. A verification has a shelf life, and a catch-all holds.

Two operator decisions, 2026-10-03:

  `max_verification_age_days` is 30. Unknown, absent, or older than 30 days
  is HOLD. Absent includes an UNDATED answer: `legacy_evidence` stamps
  `at: None` rather than inventing today's date, so an entry nothing can
  date is one nobody can vouch for.

  `catch_all_is_sendable` is false. Reoon's `is_safe_to_send` on a catch-all
  domain is a vendor's opinion about a server that answers yes to
  everything. The clearance is still recorded and still visible; it just
  does not send until the operator rules.

WHAT THIS FILE IS REALLY FOR. `age_of` has reported these ages since it was
written, and its own docstring says nothing consumed them because nobody had
chosen a number. So the measurement existed, the gate did not, and the
recurring defect in this repository is exactly that - a thing computed
correctly that nothing downstream reads. Every test here therefore asserts
through a CONSUMER (`is_sendable`, `lint.sendable`, `eligibility.decide`)
rather than against `_staleness`, because a freshness rule that only
`_staleness` can see is the same defect with a newer date on it.

EVERY CASE CARRIES ITS CONTROL. A change that simply held every address
would satisfy half of these and fail the other half: each hold is paired
with the same evidence, made current, going through. A gate that holds every
contact is as useless as one that holds none.

THE CLOCK IS INJECTED, NEVER THE CALENDAR'S. `decide` takes `now`, so
"29 days old" is a fact about the test rather than about the day it runs.
This file is the one place that must not be date-dependent, since
date-dependent fixtures are what the rule it tests breaks.
"""
import datetime
import unittest

from src import eligibility as E, lint, mx, store, verification as v
from tests.campaignbase import CampaignTest, contact as make_contact
from tests.test_eligibility import GOOGLE, GateTest

ADDRESS = "someone@example.test"
NOW = datetime.datetime(2026, 10, 3, 12, 0, tzinfo=datetime.timezone.utc)

# One confirmation, so the freshness rule is the only thing under test and a
# shortfall in the COUNT cannot be mistaken for a shortfall in the DATE.
SINGLE = dict(v.DEFAULT_POLICY, required_confirmations=1)
PAIR = dict(v.DEFAULT_POLICY, required_confirmations=2)


def aged(provider, days, status=None, **fields):
    """One confirmation, stamped a given number of days before `NOW`."""
    at = (NOW - datetime.timedelta(days=days)).isoformat()
    return v.result(provider, status or v.S_VALID, ADDRESS, at=at, **fields)


class TheWindowIsThirtyDays(unittest.TestCase):
    def test_a_confirmation_inside_the_window_sends(self):
        """THE CONTROL for every hold below."""
        decision = v.decide([aged("contactout", 29)], SINGLE, now=NOW)
        self.assertTrue(decision["sendable"])
        self.assertFalse(decision["stale"])

    def test_a_confirmation_past_the_window_holds(self):
        decision = v.decide([aged("contactout", 31)], SINGLE, now=NOW)
        self.assertFalse(decision["sendable"])
        self.assertTrue(decision["stale"])
        self.assertEqual(decision["state"], v.HELD)

    def test_the_boundary_belongs_to_the_fresh_side(self):
        """Exactly 30 days is "within 30 days". Named so the next person does
        not have to re-derive which way the comparison runs."""
        self.assertTrue(v.decide([aged("contactout", 30)], SINGLE,
                                 now=NOW)["sendable"])

    def test_an_undated_confirmation_holds(self):
        """A legacy `verdict` field, which carries no date by design."""
        old = {"key": "k", "email": ADDRESS, "verdict": "valid"}
        decision = v.resolve(old, SINGLE, now=NOW)
        self.assertEqual(decision["confirmation_count"], 1)
        self.assertFalse(decision["sendable"])
        self.assertTrue(decision["stale"])
        self.assertIn("undated", decision["reason"])

    def test_the_reason_says_which_hold_this_is(self):
        """"Nobody verified it" and "it was verified too long ago" need
        different fixes - a provider that can answer, versus one re-check of
        an address a provider already cleared."""
        decision = v.decide([aged("contactout", 400)], SINGLE, now=NOW)
        self.assertIn("within 30 days", decision["reason"])
        self.assertIn("contactout 400 days ago", decision["reason"])


class ItCountsFreshConfirmationsRatherThanScanningForTheOldest(unittest.TestCase):
    """The distinction that makes this a freshness rule and not a punishment
    for holding evidence.

    `apply` is append-only - it says so, because a caller restating a shorter
    list was deleting paid provider answers - so a re-verified address keeps
    the rows from every earlier pass. A rule that refused on the OLDEST entry
    would hold a contact two vendors confirmed this morning purely because a
    third vendor's answer from last year is still on the record, while an
    identical contact with a shorter history sent. The answer may not depend
    on surplus evidence.
    """

    def test_two_fresh_confirmations_send_despite_an_expired_third(self):
        contact = {"key": "k", "email": ADDRESS, "verification": {"evidence": [
            aged("contactout", 400), aged("deliverable", 1), aged("reoon", 1)]}}
        self.assertEqual(len(v.all_evidence(contact)), 3)
        decision = v.resolve(contact, PAIR, now=NOW)
        self.assertTrue(decision["sendable"], decision["reason"])

    def test_one_fresh_of_two_required_still_holds(self):
        """And the count is of FRESH ones, so an expired confirmation does
        not make up the required pair."""
        decision = v.decide([aged("contactout", 1), aged("reoon", 90)],
                            PAIR, now=NOW)
        self.assertFalse(decision["sendable"])
        self.assertIn("only 1 of 2", decision["reason"])

    def test_an_expired_error_row_does_not_hold_a_fresh_pair(self):
        """An `error` is evidence of nothing, in this direction too: it was
        never holding the gate open, so expiring it must not close one."""
        decision = v.decide([aged("contactout", 1), aged("deliverable", 1),
                             aged("reoon", 500, status=v.S_ERROR)],
                            PAIR, now=NOW)
        self.assertTrue(decision["sendable"], decision["reason"])


class AbsentIsNotOff(unittest.TestCase):
    def test_a_policy_that_never_heard_of_the_rule_still_applies_it(self):
        """The quietest way to lose a guard is for a hand-built policy dict -
        a test, an older caller, a future UI - to disable it by omission."""
        legacy_shaped = {"primary": "contactout", "required_confirmations": 1,
                         "accept_all_clears_on": ["reoon"],
                         "disagreement": "hold"}
        self.assertNotIn("max_verification_age_days", legacy_shaped)
        self.assertFalse(v.decide([aged("contactout", 99)], legacy_shaped,
                                  now=NOW)["sendable"])

    def test_an_explicit_none_turns_it_off(self):
        """Deliberate and configured, which is the only way it may happen."""
        off = dict(SINGLE, max_verification_age_days=None)
        self.assertTrue(v.decide([aged("contactout", 99)], off,
                                 now=NOW)["sendable"])

    def test_the_default_policy_carries_thirty(self):
        self.assertEqual(v.DEFAULT_POLICY["max_verification_age_days"], 30)
        self.assertIs(v.DEFAULT_POLICY["catch_all_is_sendable"], False)

    def test_a_client_file_can_be_read_for_both(self):
        """`policy_for` is the single constructor, so a client may set these
        the same way it sets every other verification knob."""
        policy = v.policy_for({"verification": {
            "max_verification_age_days": 7, "catch_all_is_sendable": True}})
        self.assertEqual(policy["max_verification_age_days"], 7)
        self.assertIs(policy["catch_all_is_sendable"], True)


class TheOperatorsCatchAllHold(unittest.TestCase):
    def cleared(self):
        return [aged("contactout", 1, status=v.S_ACCEPT_ALL, catch_all=True),
                aged("reoon", 1, safe_to_send=True, catch_all=True)]

    def test_a_catch_all_the_clearer_cleared_does_not_send(self):
        decision = v.decide(self.cleared(), SINGLE, now=NOW)
        self.assertFalse(decision["sendable"])
        self.assertEqual(decision["state"], v.ACCEPT_ALL_UNCLEARED)

    def test_the_clearance_is_still_visible(self):
        """"Reoon approved it and the operator has not ruled on catch-alls"
        and "nothing cleared it" are different facts, and the first becomes
        sendable the moment they rule. Discarding the clearance would make
        the decision unrecoverable."""
        decision = v.decide(self.cleared(), SINGLE, now=NOW)
        self.assertIn("cleared by reoon", decision["reason"])
        self.assertIn("does not send to a catch-all", decision["reason"])

    def test_the_hold_is_the_policy_and_not_a_lost_clearance(self):
        """THE CONTROL. The same evidence, with the operator's decision
        reversed, sends - so this is a policy switch rather than the
        catch-all path having quietly broken."""
        policy = dict(SINGLE, catch_all_is_sendable=True)
        decision = v.decide(self.cleared(), policy, now=NOW)
        self.assertTrue(decision["sendable"])
        self.assertEqual(decision["state"], v.VERIFIED)

    def test_an_uncleared_catch_all_is_still_reported_as_uncleared(self):
        """The two catch-all outcomes must stay distinguishable: one needs a
        decision from the operator, the other needs a verifier."""
        evidence = [aged("contactout", 1, status=v.S_ACCEPT_ALL,
                         catch_all=True)]
        decision = v.decide(evidence, SINGLE, now=NOW)
        self.assertIn("nothing that clears it", decision["reason"])


class TheGateIsReadByTheSendPath(GateTest):
    """The part that makes this a pipeline step rather than a report.

    `eligibility.decide` is the central gate and it already delegates to
    `lint.sendable` and `verification.resolve`, so the rule arrives at every
    consumer without eligibility having to learn it. What eligibility DOES
    need is to say which hold this is.
    """

    def expire(self, rec, days=400):
        person = rec["contacts"][0]
        for entry in (person.get("verification") or {}).get("evidence") or []:
            entry["at"] = (datetime.datetime.now(datetime.timezone.utc)
                           - datetime.timedelta(days=days)).isoformat()
        return person

    def test_a_clean_step_is_eligible(self):
        """THE CONTROL, and the one that matters most in this class: the
        fixture's own fresh verification still reaches ELIGIBLE, so nothing
        below is a gate that refuses everything."""
        rec, recs = self.ready()
        decision = self.decide(rec, recs)
        self.assertEqual(decision["verdict"], E.ELIGIBLE, decision["reasons"])

    def test_an_expired_verification_holds_the_step(self):
        rec, recs = self.ready()
        self.expire(rec)
        store.save(recs if recs else [rec])
        decision = self.decide(rec, recs)
        self.assertEqual(decision["verdict"], E.HELD, decision["reasons"])

    def test_it_is_reported_as_stale_and_not_as_unknown(self):
        """A reviewer told "verification unknown" goes looking for a better
        address; this address has two provider confirmations and needs one
        re-check. The reason code is the whole value of the distinction."""
        rec, recs = self.ready()
        self.expire(rec)
        decision = self.decide(rec, recs)
        self.assertIn(E.HELD_VERIFICATION_STALE, decision["reasons"])
        self.assertNotIn(E.HELD_VERIFICATION_UNKNOWN, decision["reasons"])

    def test_lint_refuses_the_same_address(self):
        """`lint.sendable` and the send gate must not disagree about what
        verified means - this repository has had that defect twice, and it is
        worse than either being wrong alone."""
        rec, recs = self.ready()
        person = self.expire(rec)
        policy = lint.policy_for_record(rec)
        self.assertFalse(lint.sendable(person, policy))

    def test_a_contact_with_no_evidence_is_still_unknown_not_stale(self):
        """The codes must not collapse into each other in either direction."""
        rec, recs = self.ready()
        rec["contacts"][0].pop("verification", None)
        rec["contacts"][0].pop("verdict", None)
        rec["contacts"][0].pop("reoon", None)
        decision = self.decide(rec, recs)
        self.assertIn(E.HELD_VERIFICATION_UNKNOWN, decision["reasons"])
        self.assertNotIn(E.HELD_VERIFICATION_STALE, decision["reasons"])


class TheStoredBlockReportsIt(unittest.TestCase):
    def test_apply_writes_the_flag(self):
        contact = {"key": "k", "email": ADDRESS}
        evidence = [aged("contactout", 400)]
        v.apply(contact, v.decide(evidence, SINGLE, now=NOW), evidence,
                policy=SINGLE)
        self.assertIs(contact["verification"]["stale"], True)
        self.assertIs(contact["sendable"], False)

    def test_the_stored_flag_is_not_what_the_gate_reads(self):
        """The evidence is the durable fact and the block is a cached opinion
        about it. A block written as fresh must not carry that into next
        month, so the flag is recomputed and a tampered one changes nothing.
        """
        contact = {"key": "k", "email": ADDRESS,
                   "verification": {"evidence": [aged("contactout", 400)],
                                    "state": v.VERIFIED, "sendable": True,
                                    "stale": False}}
        self.assertFalse(v.is_sendable(contact, SINGLE, now=NOW))


if __name__ == "__main__":
    unittest.main()
