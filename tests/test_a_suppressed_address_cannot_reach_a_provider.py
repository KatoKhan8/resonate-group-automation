#!/usr/bin/env python3
"""The suppression check is load-bearing, and this file proves it by removing it.

TASK-SUPPRESSION-2026-10-14. `src/suppression.py` is new - it has never
existed on any ref - so there is no prior behaviour here to regress. The
question this file answers is the only one that matters about a new guard:
**does anything actually depend on it.**

It covers both halves of the suppression problem, B1 and B2 of CANARY-01:

  * a suppressed address cannot reach a provider (`TheDoorConsultsSuppression`,
    `NoPathReachesTheTransport`), and
  * a removal request produces a row that is actually WRITTEN
    (`ARemovalRequestIsWrittenAndSurvivesARestart`), read back in a separate
    interpreter, plus a ledger that does not drop it afterwards
    (`TheDncLedgerDoesNotDropARowItReportedWriting`).

## Why asserting a refusal is not enough

SIX controls in this repository have now been found unable to fail, and the
mechanism is the same every time: the test asserts that nothing reached the
provider, and nothing reached the provider for a reason the test is not
measuring. `test_a_stop_beats_an_authorization` says so in its own docstring -
its first version passed with the `revalidate` call deleted, because the
fixture never reserved the ledger key and `perform` was refusing at the
reservation check the whole time.

So every refusal asserted below is paired with two things:

  1. **A positive control.** The same fixture, with nothing objecting, reaches
     the transport - or, for the write tests, a known row IS visible to the
     reader process. If that does not hold, the refusal proves nothing.
  2. **Proof that the thing was reached.** `suppression.consultations()`
     records every verdict the module has answered, so a test can tell "it
     refused" from "it was never asked" - the distinction the six dead
     controls could not make. The mutation tests additionally assert their
     stub was CALLED, because a mutation that never took effect is
     indistinguishable from a guard that held.

## Three mutations, performed here rather than described

* `NoPathReachesTheTransport.test_the_mutation_goes_red` neutralises
  `suppression.decide` and asserts the suppressed contact then reaches the
  transport.
* `ARemovalRequestIsWrittenAndSurvivesARestart.test_the_mutation_goes_red`
  reverts `inbound.mutated_records` to the old `status == "applied"` condition
  and asserts the written hold disappears.
* The DNC tests were checked by reverting `agencydnc.load` to its old
  skip-the-line behaviour.

Each was also performed against the SOURCE, with `__pycache__` wiped and the
file restored byte-identical afterwards; the md5 pairs are recorded in
`docs/SUPPRESSION-MEASUREMENT-2026-10-14.md`. Those assertions failing is what
would tell a future reader this file has stopped measuring anything.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from src import (accountpolicy, actionledger, agencydnc, approval,
                 bisonfactory, cadence, campaigns, clients, eligibility,
                 events, executionguard, inbound, killswitch, providerwrites,
                 store, suppression, verification, workspaces)
from src.providers import heyreach
from tests.base import QueueTest
# The staging fixture comes from the module that established this path runs
# end to end, rather than a second hand-written copy of it - a duplicated
# record builder has already cost this repository five tests.
from tests.test_staging_a_campaign_twice_builds_one import (
    CONFIG, FakeBison, CID, record)
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty

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


#: The repository root, for a child process that has to import `src`.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(store.__file__)))

#: Read the queue in a FRESH INTERPRETER and report the suppression state it
#: can see. Deliberately a separate process rather than another `store.load()`
#: in this one: the defect being guarded is a mutation that lived only in the
#: parent's memory, and an in-process reload can be satisfied by a cache, a
#: module global, or the very list object that was mutated.
READER = """
import json, sys
sys.path.insert(0, sys.argv[1])
from src import store
out = []
for rec in store.load():
    for contact in rec.get("contacts") or []:
        out.append({
            "rec": rec.get("id"),
            "contact": contact.get("key"),
            "unsubscribed": bool(contact.get("unsubscribed")),
            "suppressed": bool(contact.get("suppressed")),
            "paused": bool(contact.get("paused")),
            "events": [e.get("type") for e in rec.get("events") or []],
        })
print(json.dumps(out))
"""


class ARemovalRequestIsWrittenAndSurvivesARestart(QueueTest):
    """B2 of CANARY-01: the write is demonstrated, not assumed.

    `src/inbound.py` saved only when some outcome's status was `applied`, so a
    batch in which nothing could be attributed computed its safety holds,
    reported them, and discarded them when `recs` went out of scope. Polling
    was never the problem; nothing persisted.

    Every assertion here reads the queue back in a **separate interpreter**,
    because the bug was precisely a change that existed in one process's
    memory and nowhere else.
    """

    def setUp(self):
        super().setUp()
        self.script = os.path.join(self.tmp, "reader.py")
        with open(self.script, "w", encoding="utf-8") as handle:
            handle.write(READER)

    def read_in_a_fresh_process(self):
        done = subprocess.run(
            [sys.executable, self.script, REPO_ROOT],
            capture_output=True, env=os.environ.copy())
        # Decoded explicitly rather than with `text=True`: this machine
        # decodes a child's pipe as cp1250 under `text=True`, which turns a
        # readable payload into None and a test into a mystery.
        out = done.stdout.decode("utf-8", "replace")
        err = done.stderr.decode("utf-8", "replace")
        self.assertEqual(done.returncode, 0,
                         f"the reader process failed: {err[-600:]}")
        return json.loads(out)

    def a_record(self, rid, email):
        rec = store.new_record(rid, "domains", "productive", rid.title(),
                               f"{rid}.test")
        rec["state"] = "approved"
        rec["contacts"] = [{"key": "person", "name": "Person",
                            "email": email, "primary": True,
                            "sendable": True}]
        return rec

    def a_removal_request(self, email, record_id=None, contact_key=None):
        """An EmailBison inbound reply in the provider's own shape."""
        row = {"id": "r-1", "uuid": "u-1", "folder": "inbox",
               "from_email_address": email,
               "subject": "re: quick question",
               "text_body": "Please remove me from your list.",
               "date_received": "2026-10-14T10:00:00+00:00",
               "campaign_id": 352}
        if record_id:
            row["lead"] = {"record_id": record_id, "contact_key": contact_key,
                           "client": "productive", "email": email}
        return {"data": [row]}

    # ---------------------------------------------------- the positive control

    def test_the_reader_process_can_see_a_known_row(self):
        """Without this, every assertion below could be read from an empty
        list and still pass. It proves the child process resolves the same
        queue this test is writing."""
        store.save([self.a_record("acme", "dana@acme.test")])
        seen = self.read_in_a_fresh_process()
        self.assertEqual([(r["rec"], r["contact"]) for r in seen],
                         [("acme", "person")])
        self.assertFalse(seen[0]["unsubscribed"])
        self.assertFalse(seen[0]["paused"])

    # ------------------------------------------- the attributable removal

    def test_an_attributed_removal_request_writes_a_suppression_row(self):
        """The path that already worked, asserted so the fix cannot regress
        it: the reply names its record, so `apply_reply` suppresses the
        contact and the status is `applied`."""
        store.save([self.a_record("acme", "dana@acme.test")])
        inbound.ingest(
            self.a_removal_request("dana@acme.test", "acme", "person"),
            "emailbison")

        seen = self.read_in_a_fresh_process()
        self.assertTrue(
            seen[0]["unsubscribed"],
            "a removal request naming its own record left no written row")
        self.assertIn(events.CONTACT_SUPPRESSED, seen[0]["events"])

    # ----------------------------------------- the unattributable removal

    def test_an_unattributable_removal_request_still_writes_a_held_row(self):
        """THE DEFECT. The same person on two records, so `match_record`
        rightly refuses to guess which one the reply answers - and the hold
        applied to both must still reach the disk."""
        store.save([self.a_record("acme", "dana@acme.test"),
                    self.a_record("beta", "dana@acme.test")])
        outcomes = inbound.ingest(
            self.a_removal_request("dana@acme.test"), "emailbison")

        self.assertEqual(outcomes[0]["applied"]["status"], "unmatched",
                         "this reply was attributed after all, so this test "
                         "is no longer exercising the unmatched path")
        self.assertEqual(len(outcomes[0]["held_unattributed"]), 2)

        seen = self.read_in_a_fresh_process()
        self.assertEqual(len(seen), 2)
        for row in seen:
            self.assertTrue(
                row["paused"],
                f"{row['rec']}: the hold was computed, reported in the "
                f"outcome, and never written - a person who asked to be "
                f"removed is sendable again on the next run")
            self.assertIn(events.CONTACT_HELD, row["events"])

    def test_a_hold_is_a_hold_and_not_a_silent_permanent_opt_out(self):
        """Positive control in the other direction, and the reason this is a
        HOLD at all: the reply has not been classified, so writing it down as
        an unsubscribe would throw away "sure, Thursday works" along with the
        removal requests. It must be reversible by the person who reads it."""
        store.save([self.a_record("acme", "dana@acme.test"),
                    self.a_record("beta", "dana@acme.test")])
        inbound.ingest(self.a_removal_request("dana@acme.test"), "emailbison")

        for row in self.read_in_a_fresh_process():
            self.assertTrue(row["paused"])
            self.assertFalse(
                row["unsubscribed"],
                "an unread reply became a permanent opt-out with no review")
            self.assertNotIn(events.CONTACT_SUPPRESSED, row["events"])

    # ------------------------------------------------------- the mutation

    def test_the_mutation_goes_red(self):
        """Reverting the save condition to `status == "applied"` alone loses
        the row again, in a fresh process.

        `inbound.mutated_records` is replaced rather than edited, and the
        replacement is asserted to have been CALLED - a mutation that never
        took effect is indistinguishable from a guard that held.
        """
        store.save([self.a_record("acme", "dana@acme.test"),
                    self.a_record("beta", "dana@acme.test")])
        stub_calls = []

        def only_applied(outcome):
            stub_calls.append((outcome.get("applied") or {}).get("status"))
            return (outcome.get("applied") or {}).get("status") == "applied"

        with mock.patch.object(inbound, "mutated_records", only_applied):
            inbound.ingest(self.a_removal_request("dana@acme.test"),
                           "emailbison")

        self.assertTrue(stub_calls,
                        "the stub was never called, so the mutation did not "
                        "take effect and nothing below is evidence")
        self.assertEqual(stub_calls, ["unmatched"])

        seen = self.read_in_a_fresh_process()
        self.assertTrue(
            all(not row["paused"] for row in seen),
            "the hold survived the mutation, so something other than "
            "`mutated_records` is persisting it and this test has never been "
            "measuring the save condition")

        # And unmutated, on the same fixture, it is written. Both halves are
        # needed: the first shows the condition is load-bearing, the second
        # that the fix works on the very state the mutation lost.
        inbound.ingest(self.a_removal_request("dana@acme.test"), "emailbison")
        self.assertTrue(
            all(row["paused"] for row in self.read_in_a_fresh_process()))


class NobodySuppressedIsEnrolledAtTheProvider(QueueTest):
    """The staging path writes leads WITHOUT passing the send door.

    `_ensure_leads` calls `bison.create_lead` and `bison.attach_leads`
    directly - its own comment says it "does not go through
    `providerwrites.perform`" - and `executionguard.revalidate`, where the
    suppression consult lives, has exactly one caller: `_perform`. So none of
    the assertions in the classes above covers this path, and measured on
    2026-10-14 it asked nothing about whether these people had asked not to
    be contacted.

    That is the difference between "a suppressed address cannot reach the
    transport" and "a suppressed address cannot be ENROLLED". Being enrolled
    is not being sent to - but EmailBison's own scheduler sends from the
    campaign, and CLAUDE.md already records that the killswitch "refuses to
    START an action and cannot END a campaign already running". A suppressed
    person attached to a live campaign is reached by the provider, with no
    gate of ours in the path.

    The fixture is `test_lead_writes_respect_the_killswitch`'s, which is the
    one that established this path runs end to end: with the killswitch held
    open, two leads are created.
    """

    def setUp(self):
        super().setUp()
        self.bison = FakeBison()
        self.bison.DAYS = FakeBison.DAYS
        real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", real)
        patch_collision_empty(self)

        store.save([record("rec-1", "one@example.com", "Ada"),
                    record("rec-2", "two@example.com", "Grace")])
        row = campaigns.new_campaign(CID, "productive", "Factory test")
        row["cadence_steps"] = [dict(s) for s in cadence.steps_for(
            None, config=CONFIG)]
        row["record_ids"] = ["rec-1", "rec-2"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])

        workspace = workspaces.new_workspace("productive", "Productive",
                                             client="productive")
        workspace["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([workspace])

    def suppress(self, record_id):
        """A removal request honoured the canonical way on one record."""
        recs = store.load()
        target = next(r for r in recs if r["id"] == record_id)
        accountpolicy.apply_reply(
            target, target["contacts"][0]["key"],
            outcome=accountpolicy.UNSUBSCRIBE, at=store.now(),
            reason="asked to be removed", channel="email",
            config=clients.load("productive"))
        store.save(recs)

    def test_the_positive_control_two_clean_leads_are_created(self):
        """Without this, every refusal below is unattributable - and this
        fixture is the one that proves the path reaches lead creation at
        all."""
        bisonfactory.stage(CID, config=CONFIG, live=True)
        self.assertEqual(self.bison.created_leads, 2)

    def test_one_suppressed_contact_stops_the_whole_lead_write(self):
        """And it stops the RUN, not just that lead. A cohort quietly short
        by one is a cohort nobody notices is wrong - the same stance this
        function already takes for a lead missing its copy."""
        self.suppress("rec-1")
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory.stage(CID, config=CONFIG, live=True)
        said = str(caught.exception)
        self.assertIn("must not be contacted", said)
        self.assertIn("rec-1", said)
        self.assertEqual(
            self.bison.created_leads, 0,
            "a suppressed person was enrolled at the provider")

    def test_a_lead_naming_nobody_in_the_queue_is_refused(self):
        """UNKNOWN is not a pass. Suppression cannot be read for a record
        that is not there, and a question that cannot be asked does not get
        answered yes."""
        clean = [{"record_id": "rec-1", "contact_key": "ghost"}]
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._refuse_suppressed_leads(clean)
        self.assertIn("suppression cannot be read", str(caught.exception))

    def test_the_guard_is_load_bearing(self):
        """THE MUTATION. Neutralise the guard and the suppressed person is
        enrolled, which is the state this closes.

        The stub is asserted to have been CALLED first: without that, a
        mutation that never took effect reads exactly like a guard that
        held.
        """
        self.suppress("rec-1")
        stub_calls = []

        def allow_everybody(wanted):
            stub_calls.append(len(wanted))
            return len(wanted)

        with mock.patch.object(bisonfactory, "_refuse_suppressed_leads",
                               allow_everybody):
            bisonfactory.stage(CID, config=CONFIG, live=True)

        self.assertTrue(stub_calls,
                        "the guard was never called from _ensure_leads, so "
                        "it is not on this path at all")
        self.assertEqual(
            self.bison.created_leads, 2,
            "with the guard neutralised no lead was created either, so "
            "something else was refusing and this class has never been "
            "measuring the suppression guard")


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


class TheProvidersOwnBlacklistIsASecondList(unittest.TestCase):
    """CANARY-01, 2026-10-14: "EmailBison keeps its own blacklist ... which
    nothing in this system has ever reconciled against ours."

    THE LIST ITSELF CANNOT BE READ, and that is measured, not assumed.
    `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md:612-613` records
    `/blocklist/emails` and `/blocklist/domains` as 404;
    `scripts/reengagement_provider_confirmed.py` records the same of
    `/unsubscribes`, `/suppressions` and `/do-not-contact`. So a list-to-list
    reconciliation is not available at any price, and what IS available is the
    provider's per-lead verdict on people we already hold.

    These tests take a status string rather than fetching one. No provider
    call is made here or anywhere in this lane.
    """

    REC = {"id": "r1", "contacts": [], "events": []}

    def clean(self):
        return {"key": "k", "email": "person@example.test"}

    def suppressed(self):
        return {"key": "k", "email": "person@example.test",
                "unsubscribed": True}

    def test_both_lists_stopping_them_agrees(self):
        finding, detail = suppression.reconcile(
            self.REC, self.suppressed(), provider_status="unsubscribed")
        self.assertEqual(finding, suppression.AGREE)
        self.assertEqual(detail["ours"], suppression.BLOCK)

    def test_blocked_there_and_not_here_is_reported(self):
        """We would keep trying, and read the provider's silence as "no
        reply" - which is how a stopped person becomes a cold lead again."""
        finding, _ = suppression.reconcile(
            self.REC, self.clean(), provider_status="complained")
        self.assertEqual(finding, suppression.BLOCKED_THERE_ONLY)

    def test_suppressed_here_and_active_there_is_the_dangerous_one(self):
        """The provider keeps sending to somebody who asked US to stop, and
        no gate of ours is in that path."""
        finding, detail = suppression.reconcile(
            self.REC, self.suppressed(), provider_status="in_sequence")
        self.assertEqual(finding, suppression.SUPPRESSED_HERE_ONLY)
        self.assertIn(suppression.BLOCK_SUPPRESSED, detail["our_reasons"])

    def test_absence_from_the_snapshot_is_never_agreement(self):
        """The decisive one. Their blacklist is unreadable, so "not in what
        we fetched" cannot mean "not on their list". A reconciliation that
        scored absence as AGREE would report a clean estate while watching
        nothing - the shape of the six controls already found unable to
        fail."""
        for contact in (self.clean(), self.suppressed()):
            finding, detail = suppression.reconcile(
                self.REC, contact, provider_status=None)
            self.assertEqual(finding, suppression.UNKNOWN_THERE)
            self.assertIsNone(detail["theirs"])

    def test_a_status_we_do_not_recognise_does_not_clear_a_suppression(self):
        """Stopped here, and the provider reports a word neither vocabulary
        holds. Not provably safe, so not AGREE."""
        finding, _ = suppression.reconcile(
            self.REC, self.suppressed(), provider_status="some_new_word")
        self.assertEqual(finding, suppression.SUPPRESSED_HERE_ONLY)

    def test_the_provider_vocabulary_is_not_a_second_copy(self):
        """`PROVIDER_STOPPED` must hold the words
        `reengagement_provider_confirmed.py` established against the live
        instance. Two vocabularies for one provider's words is how the two
        come to disagree, and that script is the one that measured them."""
        for word in ("unsubscribed", "opted_out", "complained", "blocked",
                     "suppressed", "bounced", "hard_bounced"):
            self.assertIn(word, suppression.PROVIDER_STOPPED)
        self.assertNotIn("in_sequence", suppression.PROVIDER_STOPPED,
                         "an active sequence read as a stop")

    def test_reconcile_all_groups_an_estate_and_normalises_the_key(self):
        rec = {"id": "r1", "events": [],
               "contacts": [{"key": "a", "email": "Person@Example.TEST"},
                            {"key": "b", "email": "other@example.test",
                             "unsubscribed": True}]}
        out = suppression.reconcile_all(
            [rec], {"person@example.test": "unsubscribed",
                    "other@example.test": "in_sequence"})
        self.assertEqual([r["contact_key"] for r in
                          out[suppression.BLOCKED_THERE_ONLY]], ["a"],
                         "the mixed-case address did not match, so the key "
                         "is not being normalised")
        self.assertEqual([r["contact_key"] for r in
                          out[suppression.SUPPRESSED_HERE_ONLY]], ["b"])
        self.assertEqual(out[suppression.UNKNOWN_THERE], [])

    def test_a_contact_the_snapshot_omits_lands_in_unknown(self):
        rec = {"id": "r1", "events": [],
               "contacts": [{"key": "a", "email": "ghost@example.test"}]}
        out = suppression.reconcile_all([rec], {})
        self.assertEqual(len(out[suppression.UNKNOWN_THERE]), 1)
        self.assertEqual(out[suppression.AGREE], [])


if __name__ == "__main__":
    unittest.main()
