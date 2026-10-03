#!/usr/bin/env python3
"""The rule was implemented and did not bite. Now the guard asks it.

`collision.classify` and `eligibility.recontact` landed with sixty-three tests
and `executionguard.authorize` never called either, so gate 4 invoked
`eligibility.decide` with NO dossier. That is visible inertness rather than a
silent pass - every verdict carried `recontact.asked: False` and said in writing
that the classification had not run - but a rule that says so and still lets the
send through is a rule nobody is protected by. The repository has shipped that
shape before: a Slack matcher that was structurally unable to match anything,
past eighteen green tests.

So gate 4 now makes a FOURTH provider read - `collision.recontact_check` -
beside the three it already made, and passes its dossier into
`eligibility.decide(recontact_dossier=...)`.

WHAT EVERY TEST HERE ASSERTS IS THE EFFECT, AND THE EFFECT IS A WRITE THAT DOES
NOT HAPPEN. `Provider` records calls and is never wired to a transport, so
`spy.calls == []` says the code never got as far as trying - which is a stronger
claim than any assertion about a return value, and the one this file is for. A
test that only checked `eligibility.decide`'s answer would prove the rule
computes correctly while the guard sent the email anyway; that is precisely the
gap being closed.

THE DOSSIERS ARE REAL. Each is built by `collision.recontact_dossier` from
documented provider row shapes through the real parsers, by the same fixtures
`tests/test_a_lead_is_classified_before_it_is_contacted.py` uses - so the class
each one carries is COMPUTED by the rule and asserted here before the guard sees
it, never declared by this file. Nothing under test is stubbed: only the network
is removed, and only for the three reads this gate already made.
"""
import contextlib
import unittest
from unittest import mock

from src import collision, eligibility, executionguard

from tests.test_no_write_happens_without_every_gate import GuardTest
from tests.test_a_lead_is_classified_before_it_is_contacted import (
    MANUAL, OS_CAMPAIGNS, OURS, OURS_LEGACY, cold_baseline, email_side,
    linkedin_side, membership, sent_row)


def dossier_of(email=None, link=None, suppression=(), reply_class=None):
    return collision.recontact_dossier(
        email=email if email is not None else cold_baseline(),
        linkedin_=link if link is not None else linkedin_side(rows=()),
        suppression=suppression, reply_class=reply_class)


def never_touched():
    """A genuine first contact: the provider holds no lead row at all."""
    return collision.email_history(lead_row=None,
                                   lookup=collision.LOOKUP_ABSENT,
                                   bindings={}, os_campaigns=OS_CAMPAIGNS,
                                   ledger_readable=True)


class ClassifiedGuardTest(GuardTest):
    """Drive `authorize` with one real dossier and watch what the guard does.

    Built on `GuardTest` deliberately: it is the harness the existing suite
    already asserts authorises a clean step, so the dossier is the only variable
    in every comparison below. A harness of my own would make a refusal that
    came from some unrelated gate look like this one working.
    """

    @contextlib.contextmanager
    def classified(self, dossier, expect):
        """Gate 4's three old reads stubbed; the fourth returns `dossier`.

        `expect` is asserted against the REAL rule before the guard is called,
        so this helper cannot smuggle in a verdict of its own choosing: if the
        fixture stops classifying the way the test name says, the test fails
        here rather than passing for the wrong reason.
        """
        decision, klass, why = collision.classify(dossier)
        self.assertEqual(expect, klass,
                         "the fixture must really classify this way under the "
                         "real rule, or this test proves nothing about it")
        with mock.patch.object(collision, "check_linkedin_profile",
                               return_value=(collision.CLEAR, {})), \
             mock.patch.object(collision, "check_account",
                               return_value={"verdict": collision.CLEAR,
                                             "people": [],
                                             "emails_sent_total": 0}), \
             mock.patch.object(
                 collision, "recontact_check",
                 return_value=(decision, klass, why, dossier)), \
             self.allow_killswitch(), self.allow_sender():
            yield

    def refused(self, dossier, expect):
        """Authorize must raise, the gate must be `recontact`, nothing written."""
        with self.classified(dossier, expect):
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt()
        self.assertEqual("recontact", caught.exception.gate,
                         f"a {expect} lead must be refused by the "
                         f"classification gate, not incidentally by another")
        self.assertEqual([], self.spy.calls,
                         "THE EFFECT: no provider write may have happened")
        return caught.exception


class TheGuardRefusesWhatTheRuleRefuses(ClassifiedGuardTest):

    def test_a_blocked_lead_is_refused_by_the_guard(self):
        """Step 1. A DNC recorded against manual work still stops the send."""
        refusal = self.refused(dossier_of(suppression=("agency_dnc",)),
                               collision.CLASS_BLOCKED)
        self.assertIn("agency_dnc", refusal.why,
                      "the refusal must name what stands against this person, "
                      "so an operator is not sent hunting for it")
        self.assertIn("collision", list(refusal.passed),
                      "the three older collision reads must have passed, "
                      "proving this refusal is the new gate's and not theirs")

    def test_an_on_hold_lead_is_refused_by_the_guard(self):
        """Step 2. Somebody's campaign is running; ours or theirs."""
        self.refused(
            dossier_of(email_side([membership(MANUAL, collision.IN_SEQUENCE,
                                              emails_sent=1)],
                                  sent_rows=[sent_row(MANUAL, 400)])),
            collision.CLASS_ON_HOLD)

    def test_a_paused_legacy_campaign_of_ours_is_refused_by_the_guard(self):
        """The 1,555 rows behind a pause, through the real send path."""
        self.refused(
            dossier_of(email_side([membership(OURS_LEGACY,
                                              collision.SENDING_PAUSED,
                                              emails_sent=2)],
                                  sent_rows=[sent_row(OURS_LEGACY, 200),
                                             sent_row(OURS_LEGACY, 190)])),
            collision.CLASS_ON_HOLD)

    def test_a_revival_lead_is_refused_until_the_operator_approves(self):
        """Step 5. Resonate OS wrote to them, so nothing automated may go."""
        self.refused(
            dossier_of(email_side([membership(OURS, "sequence_finished",
                                              emails_sent=1)],
                                  sent_rows=[sent_row(OURS, 40)])),
            collision.CLASS_REVIVAL)

    def test_a_cold_lead_inside_the_gap_is_refused_by_the_guard(self):
        """Step 4. Cold, but a manual campaign touched them three days ago."""
        self.refused(dossier_of(cold_baseline(days=3)),
                     collision.CLASS_COLD_WAITING)

    def test_an_unknown_lead_is_refused_by_the_guard(self):
        """Step 3c. Nobody can say what reached them, so nothing may."""
        self.refused(
            dossier_of(email_side([membership(MANUAL, "sequence_finished",
                                              emails_sent=1)],
                                  sent_rows=[sent_row(MANUAL, 200)],
                                  lookup=collision.LOOKUP_FAILED)),
            collision.CLASS_UNKNOWN)

    def test_every_non_sendable_class_is_refused_and_none_is_missed(self):
        """A class added to the rule with no path to a refusal here.

        Enumerated from `collision.CLASSES` rather than listed by hand, so a
        sixth outcome cannot be introduced and quietly authorise a send.
        """
        cases = {
            collision.CLASS_BLOCKED: dossier_of(suppression=("agency_dnc",)),
            collision.CLASS_ON_HOLD: dossier_of(email_side(
                [membership(MANUAL, collision.IN_SEQUENCE, emails_sent=1)],
                sent_rows=[sent_row(MANUAL, 400)])),
            collision.CLASS_UNKNOWN: dossier_of(email_side(
                [membership(MANUAL, "sequence_finished", emails_sent=1)],
                sent_rows=[sent_row(MANUAL, 200)],
                lookup=collision.LOOKUP_FAILED)),
            collision.CLASS_REVIVAL: dossier_of(email_side(
                [membership(OURS, "sequence_finished", emails_sent=1)],
                sent_rows=[sent_row(OURS, 40)])),
            collision.CLASS_COLD_WAITING: dossier_of(cold_baseline(days=3)),
        }
        expected = set(collision.CLASSES) - collision.SENDABLE_CLASSES
        self.assertEqual(expected, set(cases),
                         "every non-sendable outcome needs a case here, or one "
                         "of them has no proven path to a refusal")
        for klass, dossier in cases.items():
            with self.subTest(klass=klass):
                self.setUp()
                self.refused(dossier, klass)


class TheGuardStillAuthorisesAColdLead(ClassifiedGuardTest):
    """A gate that refuses everybody is an outage, not a guard."""

    def test_a_cold_lead_with_manual_history_is_authorised_and_written(self):
        """Step 3b: manual history does not make a lead ours, so it may go."""
        with self.classified(dossier_of(cold_baseline(days=200)),
                             collision.CLASS_COLD):
            auth = self.attempt()
        self.assertIsInstance(auth, executionguard.Authorization)
        self.assertEqual(1, len(self.spy.calls),
                         "THE EFFECT: the write really did happen")
        self.assertIn("recontact", auth.as_dict().get("gates") or [])

    def test_a_genuine_first_contact_is_authorised(self):
        """The canary's own case: no lead row anywhere, nothing from anybody."""
        with self.classified(dossier_of(never_touched()),
                             collision.CLASS_COLD):
            self.attempt()
        self.assertEqual(1, len(self.spy.calls))

    def test_the_gate_appears_in_the_trace_of_a_later_refusal(self):
        """`recontact` must be a PASSED gate, not merely an absent one.

        Without this, a build that deleted the gate entirely would pass every
        refusal test above by never reaching them, and this class by writing.
        """
        with self.classified(dossier_of(cold_baseline(days=200)),
                             collision.CLASS_COLD):
            auth = self.attempt()
        self.assertIn("recontact", auth.as_dict()["gates"])
        self.assertIn("collision", auth.as_dict()["gates"])


class ADossierThatCouldNotBeBuiltRefuses(ClassifiedGuardTest):
    """"We could not classify" and "they are cold" must never collapse."""

    def raising(self, exc):
        return mock.patch.object(collision, "recontact_check", side_effect=exc)

    def test_a_read_that_raises_refuses_rather_than_escaping(self):
        """A provider failure must become a REFUSAL, not an exception.

        `CollisionUnknown` escaping `authorize` would be a crash at the call
        site rather than a decision, and a caller that caught broadly would
        read it as "something went wrong, try again" rather than "do not send".
        """
        for exc in (collision.CollisionUnknown("the ledger could not be read"),
                    RuntimeError("the transport died"),
                    TimeoutError("heyreach timed out")):
            with self.subTest(exc=type(exc).__name__):
                self.setUp()
                with mock.patch.object(collision, "check_linkedin_profile",
                                       return_value=(collision.CLEAR, {})), \
                     mock.patch.object(collision, "check_account",
                                       return_value={
                                           "verdict": collision.CLEAR,
                                           "people": [],
                                           "emails_sent_total": 0}), \
                     self.raising(exc), \
                     self.allow_killswitch(), self.allow_sender():
                    with self.assertRaises(executionguard.NotAuthorized) as c:
                        self.attempt()
                self.assertEqual("recontact", c.exception.gate)
                self.assertEqual([], self.spy.calls,
                                 "THE EFFECT: nothing was written")
                # THE REFUSAL MUST BE THE READ'S OWN, NOT THE ONE BEHIND IT.
                # Two independent guards stop this: the `except` arm here, and
                # the `asked` check on the verdict further down. That is
                # defence in depth and it is deliberate - but it also means
                # deleting the first one leaves the test passing on the
                # second, so the refusal is pinned to the FAILURE IT NAMES.
                # Without this assertion a mutation removing the `except`
                # arm's refusal broke nothing, measured.
                self.assertIn(type(exc).__name__, c.exception.why,
                              "the refusal must name what failed, or an "
                              "operator cannot tell an unreadable ledger from "
                              "a gate that simply did not run")
                self.assertIn("could not be made", c.exception.why)

    def test_a_verdict_that_did_not_run_the_classification_is_refused(self):
        """THE VISIBLE-INERTNESS PROPERTY, ASSERTED AT THE GUARD.

        `eligibility.decide` with no dossier returns an ELIGIBLE verdict that
        says `recontact.asked: False`. That is the state the rule shipped in,
        and the guard must now refuse it: a verdict that cannot say what this
        person has already received is not a verdict that may send to them.
        Stubbing `decide` here is deliberate and is the only way to reach that
        state once the gate supplies a dossier - it reconstructs the exact
        answer the un-wired build produced.
        """
        inert = eligibility.recontact(None)
        self.assertIs(False, inert["asked"],
                      "the inert answer must still be reachable and still say "
                      "so, or this test is asserting nothing")
        with self.classified(dossier_of(cold_baseline(days=200)),
                             collision.CLASS_COLD), \
             mock.patch.object(eligibility, "decide", return_value={
                 "verdict": "eligible", "reasons": [], "reason": None,
                 "recontact": inert}):
            with self.assertRaises(executionguard.NotAuthorized) as c:
                self.attempt()
        self.assertEqual("recontact", c.exception.gate)
        self.assertIn("did not run", c.exception.why)
        self.assertEqual([], self.spy.calls)

    def test_a_verdict_with_no_recontact_key_at_all_is_refused(self):
        """An older `decide` returning the pre-rule shape must not pass."""
        with self.classified(dossier_of(cold_baseline(days=200)),
                             collision.CLASS_COLD), \
             mock.patch.object(eligibility, "decide", return_value={
                 "verdict": "eligible", "reasons": [], "reason": None}):
            with self.assertRaises(executionguard.NotAuthorized) as c:
                self.attempt()
        self.assertEqual("recontact", c.exception.gate)
        self.assertEqual([], self.spy.calls)
