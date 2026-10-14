#!/usr/bin/env python3
"""The suppression check is load-bearing, and this file proves it by removing it.

TASK-SUPPRESSION-2026-10-14. `src/suppression.py` is new - it has never
existed on any ref - so there is no prior behaviour here to regress. The
question this file answers is the only one that matters about a new guard:
**does anything actually depend on it.**

## Why asserting a refusal is not enough

Four controls in this repository have already been found unable to fail, and
the mechanism is the same every time: the test asserts that nothing reached
the provider, and nothing reached the provider for a reason the test is not
measuring. `test_a_stop_beats_an_authorization` says so in its own docstring -
its first version passed with the `revalidate` call deleted, because the
fixture never reserved the ledger key and `perform` was refusing at the
reservation check the whole time.

So every refusal asserted below is paired with two things:

  1. **A positive control.** The same fixture, with nothing objecting, reaches
     the transport. If it does not, the refusal proves nothing.
  2. **Proof of consultation.** `suppression.consultations()` records every
     verdict the module has answered. A test can therefore tell "it refused"
     from "it was never asked", which is the distinction the four dead
     controls could not make.

## The mutation, performed here rather than described

`test_the_mutation_goes_red` neutralises the suppression check exactly as
deleting it from `executionguard.revalidate` would, and asserts that the
suppressed contact then reaches the transport. That assertion failing is what
would tell a future reader this file has stopped measuring anything.
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import (accountpolicy, actionledger, agencydnc, approval, campaigns, clients,
                 eligibility, events, executionguard, killswitch,
                 providerwrites, store, suppression, verification)
from src.providers import heyreach
from tests.base import QueueTest

# The fixture is lifted from `test_a_stop_beats_an_authorization`, which
# established what a facing write needs before the door is the only thing
# left that can refuse: a bound campaign row, a reserved ledger key, and a
# destination the provider says cannot send.
DRAFT_DESTINATION = 599020
CANON = "productive-linkedin-production-v1"
DRAFT_ROW = {"id": DRAFT_DESTINATION, "status": "PAUSED", "name": "test",
             "organizationUnitId": "174892"}
CANON_ROW = {"campaign_id": CANON, "client": "productive",
             "heyreach_campaign_id": str(DRAFT_DESTINATION),
             "provider_status_expected": "PAUSED",
             "provider_note": "{connection_note}",
             "provider_actions": ["CHECK_IS_CONNECTION", "MESSAGE"]}
OPERATION = providerwrites.LINKEDIN_ADD_LEAD
STEP = {"channel": "linkedin", "note": "a note somebody approved"}
FINGERPRINT = approval.fingerprint(STEP)
KEY = "acme:acme-1:day3:linkedin"


def a_contact(email="dana@acme.test"):
    return {"key": "acme-1", "name": "Dana Reed", "email": email,
            "linkedin": "https://www.linkedin.com/in/dana-reed",
            "selected": True, "primary": True, "verdict": "valid",
            "sendable": True, "persona": "champion", "angle": "operations",
            "verification": {"evidence": [
                verification.result("contactout", "valid", email),
                verification.result("reoon", "valid", email)]}}


def an_authorization():
    return executionguard.Authorization(
        key=KEY, operation=OPERATION, channel="linkedin",
        workspace="productive", campaign_id="productive-canary",
        sender_id="116968", rec_id="acme", contact_key="acme-1",
        step_key="day3", fingerprint=FINGERPRINT, gates=("tenancy",),
        at=store.now())


class SuppressionBase(QueueTest):

    def setUp(self):
        super().setUp()
        suppression.reset_consultations()
        self.addCleanup(suppression.reset_consultations)
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["state"] = "verified"
        rec["contacts"] = [a_contact()]
        rec["cadence"] = {"acme-1": {"day3": {
            "channel": "linkedin", "note": "hi Dana, worth a word?"}}}
        store.save([rec])

    def unsubscribe_through_the_real_path(self):
        """A removal request honoured the canonical way, not a hand-set flag."""
        recs = store.load()
        accountpolicy.apply_reply(
            recs[0], "acme-1", outcome=accountpolicy.UNSUBSCRIBE,
            at=store.now(), reason="asked to be removed",
            channel="email", config=clients.load("productive"))
        store.save(recs)

    def record_a_classified_reply_only(self):
        """The latent divergence between the two definitions of "replied".

        `eligibility._replied` walks the event log with `events.is_reply`,
        which is `reply_received`, `email_reply` and `linkedin_reply`.
        `account.replies` - which `suppression` reads - also counts
        `reply_classified` and `positive_reply_detected`.

        So a contact carrying ONLY a classified or positive reply is eligible
        to `eligibility` and blocked by `suppression`. MEASURED AS LATENT, not
        live: 0 of 1381 contacts in the 2026-10-03 production queue are in
        this state, because the two events are written as a pair. It is
        guarded here because the pair is written by one function and a verb
        that records one without the other is a send to somebody who answered.
        """
        recs = store.load()
        events.record(recs[0], events.POSITIVE_REPLY_DETECTED,
                      contact_key="acme-1", at=store.now())
        store.save(recs)


class TheDoorConsultsSuppression(SuppressionBase):
    """`executionguard.revalidate` is the door's re-read. It must ask.

    These assert against the REAL `revalidate`. The fixture is not a fully
    approved estate, so `eligibility.decide` answers `skipped:no_such_step`
    and refuses after suppression has spoken. That is used rather than worked
    around: a refusal naming the `revalidate` gate is positive proof that
    suppression was asked and ALLOWED, and a refusal naming the `suppression`
    gate is proof it was asked and refused. The two are distinguishable, which
    is the whole requirement.
    """

    def test_the_door_consults_suppression(self):
        """THE RED-ON-REMOVAL TEST.

        No other gate can satisfy this assertion. `consultations()` is
        appended to by `suppression.decide` and by nothing else, so deleting
        the consult from `revalidate` empties it and this fails - whatever
        else refuses or passes, and without needing an eligible estate.
        """
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            executionguard.revalidate(an_authorization())
        self.assertEqual(
            caught.exception.gate, "revalidate",
            "suppression refused this clean contact, so the assertion below "
            "would pass for the wrong reason")
        self.assertIn(
            ("acme", "acme-1", suppression.ALLOW),
            suppression.consultations(),
            "revalidate did not consult suppression about this contact")

    def test_a_suppressed_contact_is_refused_at_the_suppression_gate(self):
        self.unsubscribe_through_the_real_path()
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            executionguard.revalidate(an_authorization())
        self.assertEqual(caught.exception.gate, "suppression")
        self.assertIn("Nothing was written", str(caught.exception))
        self.assertIn(("acme", "acme-1", suppression.BLOCK),
                      suppression.consultations())

    def test_suppression_refuses_where_must_not_contact_passes(self):
        """The consult is load-bearing, not merely present.

        `eligibility.must_not_contact` is the person-level question
        `suppression` wraps, and the honest comparison is against it rather
        than against `decide`, which answers about a step.

        A contact carrying only `positive_reply_detected`: every slot of
        `must_not_contact` is None, and suppression blocks. If this ever
        fails because `must_not_contact` learned to see it too, that is an
        improvement - but the definitions will then agree and this test
        should be deleted deliberately rather than left passing for a new
        reason.
        """
        self.record_a_classified_reply_only()
        recs = store.load()
        rec, contact = recs[0], recs[0]["contacts"][0]

        self.assertEqual(
            [r for r in eligibility.must_not_contact(rec, contact) if r], [],
            "must_not_contact now blocks this too, so the divergence this "
            "test guards has closed; delete it on purpose")

        verdict = suppression.decide(rec, contact,
                                     scope=suppression.SCOPE_SEND)
        self.assertEqual(verdict.action, suppression.BLOCK)
        self.assertIn(suppression.BLOCK_REPLIED, verdict.reasons)

        with self.assertRaises(executionguard.NotAuthorized) as caught:
            executionguard.revalidate(an_authorization())
        self.assertEqual(caught.exception.gate, "suppression",
                         "something other than suppression refused, so this "
                         "test is measuring the wrong gate")


class NoPathReachesTheTransport(SuppressionBase):
    """A suppressed address must not reach a provider by any route found.

    Routes enumerated by reading `providerwrites.OPERATIONS`: every
    prospect-facing operation goes through `_perform`, which calls
    `revalidate` for `facing` writes. `EMAIL_RESUME` is the one verb that
    restarts sending while NOT being `facing`, and it carries its own
    `CONDITIONAL` for exactly that reason; it is exercised below.
    """

    def setUp(self):
        super().setUp()
        self.assertNotEqual(
            store.campaigns_path(),
            os.path.join(store.ROOT, "work", "campaigns.jsonl"),
            "this test would write the real campaign ledger")
        campaigns.save([dict(CANON_ROW)])
        self.assertEqual(
            providerwrites.classify_campaign("linkedin", DRAFT_DESTINATION),
            providerwrites.RESONATE_OS,
            "the bound row does not classify as ours, so these writes would "
            "be refused on ownership and this class would stop measuring "
            "whether suppression is consulted at all")
        self.calls = []
        actionledger.reserve(
            KEY, channel="linkedin", workspace="productive",
            provider_workspace=10, campaign_id="productive-canary",
            sender_id="116968", rec_id="acme", contact_key="acme-1",
            step_key="day3", operation=OPERATION, fingerprint=FINGERPRINT,
            by="test", cap_per_day=10, cap_per_sender=10)

    def attempt(self):
        """A real `perform`, with ELIGIBILITY HELD OPEN so it cannot mask.

        `eligibility.decide` is stubbed to `eligible` for one reason: this
        fixture is not a fully approved estate, so the real one answers
        `skipped:no_such_step` and refuses every write here - which would make
        "the transport was not reached" true no matter what suppression did.
        That is precisely how the four dead controls in this repository
        passed. Holding it open leaves suppression as the only gate in
        `revalidate` that can still refuse, and the mutation test below
        proves that is what happens.
        """
        # `eligibility.Decision`, not a bare dict: `killswitch.step_state`
        # reads `.eligible` off it, and a dict that merely looks right fails
        # with an AttributeError two layers down instead of standing in for
        # the real verdict.
        eligible = eligibility.Decision(
            {"verdict": eligibility.ELIGIBLE, "reasons": [], "reason": None})
        # THE KILLSWITCH IS HELD OPEN, AND THIS IS THE MOST IMPORTANT
        # STUB IN THE FILE.
        #
        # `killswitch.require` refuses globally and unconditionally today -
        # "live sending is refused in code: push.run(live=True) raises and
        # tagsync.send refuses unconditionally. This is not a flag". So in
        # this build NOTHING reaches a provider, and an unstubbed test here
        # would assert that a suppressed address cannot reach the transport
        # while the killswitch did all the work. That is the fifth dead
        # control, and it is what this stub exists to prevent.
        #
        # Held open deliberately so the question under test is the one being
        # answered: when live sending IS eventually permitted, does
        # suppression stop this write. Every refusal asserted below is
        # therefore attributable to suppression and to nothing else.
        with mock.patch.object(providerwrites, "SUPPORTED", (OPERATION,)), \
             mock.patch.object(providerwrites,
                               "CAMPAIGN_LEVEL_STAGING_IS_PROVEN", True), \
             mock.patch.object(eligibility, "decide", return_value=eligible), \
             mock.patch.object(killswitch, "require", return_value=None), \
             mock.patch.object(heyreach, "campaign_read",
                               return_value=dict(DRAFT_ROW)), \
             mock.patch.object(campaigns, "require",
                               return_value=dict(CANON_ROW)):
            return providerwrites.perform(
                OPERATION, provider_campaign_id=DRAFT_DESTINATION,
                campaign=CANON, authorization=an_authorization(),
                payload={"profile": "dana-reed", "note": STEP["note"]},
                step=STEP,
                transport=lambda p: self.calls.append("transport") or {"ok": 1},
                readback=lambda: {"ok": 1}, expected={"ok": 1})

    def test_the_positive_control_the_transport_is_reachable(self):
        """Every other gate passes with this fixture. Without this, a later
        assertion that the transport was not reached means nothing."""
        self.attempt()
        self.assertEqual(self.calls, ["transport"])
        self.assertIn(("acme", "acme-1", suppression.ALLOW),
                      suppression.consultations(),
                      "the transport was reached without suppression being "
                      "asked at all")

    def test_a_suppressed_address_does_not_reach_the_transport(self):
        self.unsubscribe_through_the_real_path()
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            self.attempt()
        self.assertEqual(caught.exception.gate, "suppression")
        self.assertEqual(self.calls, [],
                         "the provider was written to for a suppressed address")

    def test_and_the_ledger_does_not_claim_a_send(self):
        self.unsubscribe_through_the_real_path()
        with self.assertRaises(executionguard.NotAuthorized):
            self.attempt()
        self.assertNotEqual(actionledger.state_of(KEY), actionledger.SENT)

    def test_the_mutation_goes_red(self):
        """THE MUTATION, PERFORMED.

        `suppression.decide` is replaced by one that always ALLOWs, which is
        what deleting the consult from `revalidate` amounts to. The same
        suppressed address then reaches the transport.

        Three assertions, and all three are needed:

          * the stub WAS called - otherwise the mutation never took effect
            and the rest of this test is about nothing,
          * the transport WAS reached under the mutation - otherwise some
            other gate is doing the refusing and this file has never been
            measuring suppression,
          * the transport was NOT reached without the mutation.

        The second is the one that would catch this file going hollow.
        """
        self.unsubscribe_through_the_real_path()
        stub_calls = []

        def always_allow(rec, contact, **kw):
            stub_calls.append(((rec or {}).get("id"),
                               (contact or {}).get("key")))
            return suppression.Verdict(suppression.ALLOW, (), {},
                                       rec_id=(rec or {}).get("id"),
                                       contact_key=(contact or {}).get("key"),
                                       at=store.now())

        # 1. Unmutated: suppression refuses and the provider is untouched.
        with self.assertRaises(executionguard.NotAuthorized) as caught:
            self.attempt()
        self.assertEqual(caught.exception.gate, "suppression")
        self.assertEqual(self.calls, [])

        # 2. Mutated: the guard is neutralised and the write goes through.
        self.calls = []
        with mock.patch.object(suppression, "decide", always_allow):
            self.attempt()

        self.assertTrue(
            stub_calls,
            "the suppression stub was never called, so the mutation did not "
            "take effect and nothing below is evidence of anything")
        self.assertEqual(
            self.calls, ["transport"],
            "with suppression neutralised the write STILL did not reach the "
            "transport, so something else was refusing and this file has "
            "never been measuring suppression")

    def test_the_resume_verb_is_covered_too(self):
        """`EMAIL_RESUME` restarts a paused sequence and is NOT `facing`, so
        it never reaches `revalidate`. It carries its own `CONDITIONAL`, which
        is the one other route to a prospect found by reading
        `providerwrites.OPERATIONS`, and it must refuse a suppressed contact.
        """
        self.unsubscribe_through_the_real_path()
        condition = providerwrites.CONDITIONAL[providerwrites.EMAIL_RESUME]
        campaigns.save([dict(CANON_ROW, campaign_id="resume-canon",
                             record_ids=["acme"],
                             bison_campaign_id="481")])
        with self.assertRaises(providerwrites.WriteRefused) as caught:
            condition("481", campaign_id="resume-canon")
        said = str(caught.exception)
        self.assertIn("suppressed", said)
        self.assertIn("transport was not reached", said)


class PositiveControlsBothDirections(QueueTest):
    """An earlier incident got this wrong in both directions, so both are fixed.

    These assert `accountpolicy`'s shipped behaviour, not a classifier written
    for this lane: the rule lives in `effects()` and `_TRANSITION`, and a test
    of a private copy of the rule would pass while the shipped one drifted.
    """

    def test_an_unclassified_warm_reply_is_not_a_permanent_opt_out(self):
        """DIRECTION ONE. A warm reply carrying a generic unsubscribe footer
        arrives unclassified. It must HOLD for review, never SUPPRESS.

        This is not hypothetical from the corpus side: every rendered body
        carries `optout.OPT_OUT_LINE`, which literally says "reply STOP", so
        a top-posted warm reply quoting the original contains the word STOP
        in its quoted tail. A rule reading the whole body would opt the
        person out for agreeing to a meeting.
        """
        effect = accountpolicy.effects(accountpolicy.UNKNOWN)
        self.assertEqual(effect["replier"], accountpolicy.HOLD)
        self.assertNotEqual(effect["replier"], accountpolicy.SUPPRESS)
        self.assertTrue(effect["review"],
                        "an unclassified reply must be put in front of a "
                        "person, not decided automatically")
        self.assertNotIn(accountpolicy.UNKNOWN, accountpolicy.REMOVAL_REQUESTS)

    def test_the_text_of_a_reply_never_drives_suppression(self):
        """The same rule, asserted where it could actually be broken.

        `classify_outcome` reads the recorded classification off the event and
        never re-reads the message, and `suppression` consults
        `eligibility.must_not_contact`, which reads the contact's flags. So a
        record whose reply event carries our own opt-out wording as text, and
        no classification, is UNKNOWN - not an opt-out.
        """
        rec = store.new_record("warm", "domains", "productive", "Warm",
                               "warm.test")
        rec["contacts"] = [dict(a_contact("sam@warm.test"), key="warm-1")]
        events.record(rec, events.REPLY_RECEIVED, contact_key="warm-1",
                      at=store.now())
        self.assertEqual(accountpolicy.classify_outcome(rec, "warm-1"),
                         accountpolicy.UNKNOWN)
        effect = accountpolicy.effects(
            accountpolicy.classify_outcome(rec, "warm-1"))
        self.assertNotEqual(effect["replier"], accountpolicy.SUPPRESS)

    def test_a_clear_opt_out_is_not_read_as_buying_intent(self):
        """DIRECTION TWO. An explicit removal request must suppress, and must
        never resolve to POSITIVE or activate anything."""
        for outcome in accountpolicy.REMOVAL_REQUESTS:
            effect = accountpolicy.effects(outcome)
            self.assertEqual(effect["replier"], accountpolicy.SUPPRESS,
                             f"{outcome} did not suppress the replier")
            self.assertFalse(effect["activate_referred"],
                             f"{outcome} activated a referred contact")
            self.assertNotEqual(effect["decision"]["outcome"],
                                accountpolicy.POSITIVE)

    def test_no_amount_of_disinterest_adds_up_to_an_opt_out(self):
        """The converse, which keeps the two directions from collapsing: a
        "not interested" must stop the sequence and must NOT suppress, so an
        operator reopening a stale contact does not reopen a removal request.
        """
        for outcome in (accountpolicy.NOT_NOW, accountpolicy.NOT_ICP,
                        accountpolicy.NEGATIVE):
            effect = accountpolicy.effects(outcome)
            self.assertNotEqual(
                effect["replier"], accountpolicy.SUPPRESS,
                f"{outcome} suppressed somebody who never asked to be removed")


class TheThresholdsAreConfigNotConstants(unittest.TestCase):
    """The client has confirmed none of them except the 90-day cooling."""

    def test_every_threshold_can_be_overridden(self):
        for key, value in (("hold_after_last_touch_days", 7),
                           ("hold_above_total_sends", 3),
                           ("cooling_days", 180),
                           ("hold_on_active_sequence", False)):
            got = suppression.thresholds({"suppression": {key: value}})
            self.assertEqual(got[key], value, f"{key} is not configurable")

    def test_the_defaults_are_the_provisional_numbers_the_operator_set(self):
        got = suppression.thresholds()
        self.assertEqual(got["hold_after_last_touch_days"], 30)
        self.assertEqual(got["hold_above_total_sends"], 10)
        self.assertEqual(got["cooling_days"], 90)

    def test_cooling_lifts_a_volume_hold_and_never_a_removal_request(self):
        """90 days is confirmed correct: after it, a lead may be contacted
        again. That applies to the volume and recency HOLDS and to nothing
        else - a removal request is not a thing that cools off."""
        rec = {"id": "r", "contacts": [], "events": []}
        hot = suppression.decide(
            rec, {"key": "k"}, now="2026-10-14T00:00:00+00:00",
            provider_touches={"last_touch_at": "2026-10-01T00:00:00+00:00",
                              "total_sends": 50, "active_sequence": False})
        self.assertEqual(hot.action, suppression.HOLD)

        cooled = suppression.decide(
            rec, {"key": "k"}, now="2026-10-14T00:00:00+00:00",
            provider_touches={"last_touch_at": "2026-01-01T00:00:00+00:00",
                              "total_sends": 50, "active_sequence": False})
        self.assertEqual(cooled.action, suppression.ALLOW,
                         "a lead 286 days cold is still held, so the "
                         "confirmed 90-day rule is not in force")

        opted_out = suppression.decide(
            rec, {"key": "k", "unsubscribed": True},
            now="2026-10-14T00:00:00+00:00",
            provider_touches={"last_touch_at": "2026-01-01T00:00:00+00:00",
                              "total_sends": 1, "active_sequence": False})
        self.assertEqual(opted_out.action, suppression.BLOCK,
                         "a removal request expired after 90 days")

    def test_unknown_touch_history_holds_rather_than_passes(self):
        """The base commit is titled "UNKNOWN is never a pass". Suppression
        cannot see what the providers sent unless it is told, and a person we
        know nothing about is not a person who is safe to contact."""
        verdict = suppression.decide({"id": "r", "contacts": [], "events": []},
                                     {"key": "k"})
        self.assertEqual(verdict.action, suppression.HOLD)
        self.assertIn(suppression.HOLD_TOUCH_HISTORY_UNKNOWN, verdict.reasons)


class TheDncLedgerDoesNotDropARowItReportedWriting(unittest.TestCase):
    """A do-not-contact ledger that loses rows is the same failure as none.

    REPRODUCED 2026-10-14, before the fix. `add` appends
    `json.dumps(...) + "\\n"`. A torn write - row lands, newline does not -
    gets the NEXT append glued onto its end, so one physical line holds two
    objects. `load` did `json.loads(line)` inside
    `except ValueError: continue`, commented "a corrupt line suppresses
    nobody", and both rows vanished: the torn one AND the good one glued to
    it, for which `add` had already returned a fingerprint and therefore
    reported success. Measured: `add` claimed 3 rows, `load` saw 1,
    `lookup` answered None for somebody who had asked to be removed.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="dnc-integrity-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = os.path.join(self.dir, "agency-dnc.jsonl")

    def row(self, who, at):
        return json.dumps(
            {"fingerprint": agencydnc.fingerprint("email", who),
             "reason": "requested", "at": at}, sort_keys=True)

    def test_a_torn_append_does_not_swallow_the_next_row(self):
        """The whole defect, end to end, as the reproduction ran it."""
        alice = agencydnc.add("email", "alice@example.test", at="2026-10-01",
                              file_path=self.path)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(self.row("bob@example.test", "2026-10-02"))  # no \n
        carol = agencydnc.add("email", "carol@example.test", at="2026-10-03",
                              file_path=self.path)

        index = agencydnc.load(file_path=self.path)
        self.assertIn(carol, index,
                      "add() returned carol's fingerprint and she is not on "
                      "the list: a torn write ate a successful one")
        self.assertIn(alice, index)
        self.assertIn(agencydnc.fingerprint("email", "bob@example.test"),
                      index, "the torn row itself was not recovered either")
        self.assertIsNotNone(
            agencydnc.lookup({"email": "carol@example.test"}, index=index))

    def test_a_file_already_glued_by_an_older_crash_still_recovers_both(self):
        """The heal-on-write cannot help a file torn before the fix existed,
        so the read path has to recover it. Two objects, one line, no
        trailing newline problem to heal - exactly what was found on disk."""
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(self.row("dave@example.test", "2026-10-04")
                         + self.row("erin@example.test", "2026-10-05") + "\n")
        index = agencydnc.load(file_path=self.path)
        self.assertEqual(len(index), 2, "a glued pair lost a row")
        for who in ("dave@example.test", "erin@example.test"):
            self.assertIn(agencydnc.fingerprint("email", who), index)

    def test_genuinely_unreadable_bytes_are_reported_not_hidden(self):
        """Recovery is not the same as pretending the file is clean."""
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(self.row("fred@example.test", "2026-10-06") + "\n")
            handle.write("{not json at all\n")
        self.assertEqual(agencydnc.damaged_lines(file_path=self.path), [2])
        # The good row is still honoured - a damaged byte must not take the
        # whole roster down on the send path.
        index = agencydnc.load(file_path=self.path)
        self.assertIn(agencydnc.fingerprint("email", "fred@example.test"),
                      index)
        with self.assertRaises(ValueError):
            agencydnc.load(file_path=self.path, strict=True)

    def test_a_healthy_file_reports_no_damage(self):
        """The positive control. Without it, `damaged_lines` returning []
        would prove nothing - an empty list is also what a reader that
        inspects nothing returns."""
        agencydnc.add("email", "gail@example.test", at="2026-10-07",
                      file_path=self.path)
        agencydnc.add("email", "hank@example.test", at="2026-10-08",
                      file_path=self.path)
        self.assertEqual(agencydnc.damaged_lines(file_path=self.path), [])
        self.assertEqual(len(agencydnc.load(file_path=self.path)), 2)


if __name__ == "__main__":
    unittest.main()
