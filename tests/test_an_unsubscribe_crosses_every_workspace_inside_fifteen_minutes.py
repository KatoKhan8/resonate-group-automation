#!/usr/bin/env python3
"""The reply is the unsubscribe, so it has to reach further than one record.

OPERATOR DECISION, 2026-09-24: **there will be no unsubscribe link in any
campaign. The opt-out mechanism is the REPLY.** Three of the four things that
follow from that are measured here; the fourth - that the classifier reads a
removal request in every language this estate sends to - is
`test_an_unsubscribe_is_read_in_every_language_we_send_to.py`.

## What was true before this file

`reply.on_unsubscribe` suppressed the contact ON THE RECORD THAT RECEIVED THE
REPLY. `agencydnc` - the one mechanism in this system that holds a
do-not-contact across a tenancy boundary - had **no production caller at
all**: every `agencydnc.add` in the repository was in a test. So an opt-out
was a fact about one row in one workspace's queue, and the next workspace to
import the same person read them as contactable.

And the case where that matters most was the case that did least. One person
worked by two of our workspaces is two records; `events.match_record` refuses
to say which one a reply answers; `inbound.handle` took the `unmatched` branch
and applied a HOLD - which an operator clears as soon as they have read it.
"Unsubscribe me", from the person hardest to attribute, bought a pause.

## The three terms of the 15 minutes, and which are measured

    1  provider visibility   reply sent -> row readable in the inbox feed
    2  detection             reply_watch_loop --interval 300
    3  ingest + suppress     inbound.handle -> classify -> suppress ->
                             agency list -> provider stop

Term 1 is UNMEASURED and cannot be measured without a human sending a real
message from a real mailbox; it is the same gap
`test_a_linkedin_reply_stops_email_inside_fifteen_minutes.py` names, and the
headroom left for it is asserted below rather than assumed away. Term 2 is a
constant this repository sets, and the test reads it from the loop rather than
restating it. Term 3 is code plus one provider write, and both halves are
timed - the local half here, the provider write by the measurement cited in
`STOP_WRITE_MEASURED_SECONDS`.

**What "takes effect" means here is deliberately the LOCAL gate, not the
provider.** The provider stop is what stops the queued email; the suppression
is what stops every FUTURE campaign in every workspace, and it is the one that
is permanent. Both are inside the same 15 minutes and only one of them can be
proved offline, so the file says which is which.
"""
import argparse
import inspect
import time
import unittest

from src import (accountpolicy, agencydnc, eligibility, events,
                 executionguard, inbound, replies, store)
from tests.base import QueueTest

#: `scripts/reply_watch_loop.py --interval`, and `REPLY_POLL_SECONDS`'s
#: documented default. Asserted against both below rather than trusted: a
#: latency computed from a constant nothing reads is a guess with a number in
#: it.
POLL_INTERVAL_SECONDS = 300

#: MEASURED 2026-09-23 against the live provider - three `bison.stop_lead`
#: calls against leads already terminal in campaign 492, median 1658 ms, max
#: 1694 ms. Carried over from
#: `test_a_linkedin_reply_stops_email_inside_fifteen_minutes.py` rather than
#: re-derived, because it is the same call on the same path and two copies of
#: one measurement drift.
STOP_WRITE_MEASURED_SECONDS = 1.694

#: What the LOCAL half of term 3 may cost before something is wrong. It is
#: classification, a few dict writes, one JSONL append and one queue save; if
#: it ever approaches even a minute, something is retrying.
LOCAL_BUDGET_SECONDS = 30.0

#: The operator's gate.
GATE_SECONDS = 15 * 60

#: A REAL REPLY. `work/reply-drafts.jsonl`, EmailBison event 1609395,
#: delivered 2026-09-22 - a prospect answering a live sequence with three
#: words. It carries no name and no address, which is why it can be quoted in
#: a tracked file; the corpus it came from is `work/` and stays there.
A_REAL_BARE_STOP = "no. stop."

ADDRESS = "dana@acme.test"
PROFILE = "https://www.linkedin.com/in/dana-marsh"


def a_record(rid, client, domain, key="dana-marsh"):
    rec = store.new_record(rid, "domains", client, f"Co {rid}", domain)
    rec["state"] = "verified"
    rec["contacts"] = [{
        "key": key, "name": "Dana Marsh", "title": "Head of Operations",
        "email": ADDRESS, "linkedin": PROFILE, "selected": True,
        "verdict": "valid", "sendable": True, "persona": "champion",
    }]
    return rec


def a_reply(text=A_REAL_BARE_STOP, at="2026-09-24T10:00:00+00:00", **over):
    event = {"type": events.REPLY_RECEIVED, "provider": "emailbison",
             "email": ADDRESS, "at": at, "channel": "email",
             "provider_event_id": "evt-unsub-1", "text": text}
    event.update(over)
    return event


class TheOptOutCrossesWorkspaces(QueueTest):
    """One workspace receives it; every workspace is bound by it."""

    def setUp(self):
        super().setUp()
        store.append([a_record("acme-productive", "productive", "acme.test")])

    def deliver(self, text=A_REAL_BARE_STOP):
        recs = store.load()
        out = inbound.handle(a_reply(text=text), recs)
        with store.transaction() as rows:
            rows[:] = recs
        return out

    def test_the_real_reply_is_read_as_an_unsubscribe(self):
        """Everything below is worthless if this one word is misread."""
        out = self.deliver()
        self.assertEqual(out["applied"]["status"], "applied")
        self.assertEqual(out["classification"]["classification"],
                         replies.UNSUBSCRIBE)

    def test_the_contact_is_suppressed_and_not_merely_stopped(self):
        """SUPPRESS is the only effect an operator cannot quietly reopen."""
        self.deliver()
        contact = store.load()[0]["contacts"][0]
        self.assertTrue(contact.get("unsubscribed"))
        effect, _why = accountpolicy.contact_state(contact)
        self.assertEqual(effect, accountpolicy.SUPPRESS)

    def test_both_identifier_kinds_reach_the_agency_list(self):
        """"The address AND the account" - `keys_for` has exactly two kinds.

        The email is what they replied from. The LinkedIn profile is the OTHER
        way we reach the same person, and an opt-out honoured on one channel
        and not the other is not an opt-out.
        """
        self.deliver()
        index = agencydnc.load()
        self.assertIn(agencydnc.fingerprint("email", ADDRESS), index)
        self.assertIn(agencydnc.fingerprint(
            "linkedin", "https://www.linkedin.com/in/dana-marsh"), index)

    def test_the_reason_is_a_request_and_not_an_internal_decision(self):
        """A closed vocabulary, and this is the value that means "they asked"."""
        self.deliver()
        entry = agencydnc.load()[agencydnc.fingerprint("email", ADDRESS)]
        self.assertEqual(entry["reason"], agencydnc.REQUESTED)

    def test_a_workspace_that_imports_them_TOMORROW_is_bound(self):
        """THE POINT OF THE WHOLE CHANGE.

        A record that did not exist when the reply arrived, in a different
        client's workspace, holding the same person. Nothing was written to
        this record and nothing could have been - it is created afterwards.
        The only thing standing between this person and another campaign is
        the agency-wide list.
        """
        self.deliver()
        later = a_record("acme-secondclient", "secondclient", "acme.test")
        reasons = eligibility.must_not_contact(later, later["contacts"][0])
        self.assertIn(eligibility.BLOCKED_AGENCY_DNC, reasons)

    def test_that_refusal_is_one_the_execution_guard_honours(self):
        """A reason no gate reads is a field, not a suppression."""
        self.assertIn(eligibility.BLOCKED_AGENCY_DNC,
                      executionguard.SUPPRESSION_REASONS)

    def test_a_refusal_is_NOT_an_unsubscribe(self):
        """The control, and it is not a formality.

        Over-suppression is a real error with a real cost: "not interested" is
        an answer about this quarter and belongs to the workspace that heard
        it. If it reached the agency list, one client's cold prospect would be
        permanently unreachable by every other client we have.
        """
        self.deliver("not interested, thanks")
        self.assertEqual(agencydnc.load(), {})

    def test_an_out_of_office_is_NOT_an_unsubscribe(self):
        self.deliver("I am out of the office until 3 October.")
        self.assertEqual(agencydnc.load(), {})

    def test_the_agency_write_is_idempotent(self):
        """A replayed webhook must not grow the file without bound."""
        self.deliver()
        first = len(agencydnc.load())
        recs = store.load()
        inbound.handle(a_reply(provider_event_id="evt-unsub-2"), recs)
        with store.transaction() as rows:
            rows[:] = recs
        self.assertEqual(len(agencydnc.load()), first)


class BeingKnownTwiceMustNotSurviveAnOptOut(QueueTest):
    """The cross-workspace case is also the case attribution refuses."""

    def setUp(self):
        super().setUp()
        store.append([a_record("acme-productive", "productive", "acme.test"),
                      a_record("acme-secondclient", "secondclient", "acme-group.test")])

    def deliver(self, text=A_REAL_BARE_STOP):
        recs = store.load()
        out = inbound.handle(a_reply(text=text), recs)
        with store.transaction() as rows:
            rows[:] = recs
        return out

    def test_attribution_is_still_refused(self):
        """Unchanged, and it must stay unchanged. Which record the reply
        answers is a question for a person; what it SAYS is not."""
        self.assertEqual(self.deliver()["applied"]["status"], "unmatched")

    def test_every_record_holding_them_is_suppressed_not_held(self):
        out = self.deliver()
        self.assertEqual(len(out["suppressed_unattributed"]), 2)
        self.assertEqual(out["held_unattributed"], [])
        for rec in store.load():
            contact = rec["contacts"][0]
            self.assertTrue(
                contact.get("unsubscribed"),
                f"{rec['id']} only held somebody who asked to be removed")

    def test_an_unclassifiable_reply_still_only_holds(self):
        """The guard `hold_for_unattributed_reply` was written to keep.

        An unread reply is not an unsubscribe. Only the two stop classes are
        acted on here; everything else takes the reversible hold it always
        took.
        """
        out = self.deliver("Thanks - can you resend the deck?")
        self.assertEqual(out["suppressed_unattributed"], [])
        self.assertEqual(len(out["held_unattributed"]), 2)
        for rec in store.load():
            self.assertFalse(rec["contacts"][0].get("unsubscribed"))

    def test_nothing_was_attributed_to_either_record(self):
        """A suppression is a state change, never a claim of receipt."""
        self.deliver()
        for rec in store.load():
            self.assertEqual(
                [e for e in rec.get("events") or [] if events.is_reply(e)], [])


class AnUnattributableOptOutSurvivesTheProcess(QueueTest):
    """`ingest` saved only when something MATCHED, and this never matches."""

    def setUp(self):
        super().setUp()
        store.append([a_record("acme-productive", "productive", "acme.test"),
                      a_record("acme-secondclient", "secondclient", "acme-group.test")])

    def test_ingest_persists_a_suppression_it_could_not_attribute(self):
        """Through `ingest`, which owns the save - NOT through `handle`.

        `handle` mutates records in memory. Every existing test of the
        unattributed path writes them back itself, which is why the missing
        save never showed up as a failure. This calls the function production
        calls and then re-reads the file.
        """
        inbound.ingest({"data": [{
            "id": 9901, "uuid": "unsub-9", "type": "reply", "folder": "inbox",
            "from_email_address": ADDRESS,
            "date_received": "2026-09-24T10:00:00+00:00",
            "text_body": A_REAL_BARE_STOP,
            "automated_reply": False}]}, "emailbison")
        for rec in store.load():
            self.assertTrue(
                rec["contacts"][0].get("unsubscribed"),
                f"{rec['id']} lost the suppression when the process moved on")


class TheClockIsMeasuredNotArgued(QueueTest):

    def setUp(self):
        super().setUp()
        store.append([a_record("acme-productive", "productive", "acme.test")])

    def test_the_local_half_is_fast_enough_to_be_irrelevant(self):
        recs = store.load()
        started = time.monotonic()
        inbound.handle(a_reply(), recs)
        elapsed = time.monotonic() - started
        self.assertLess(
            elapsed, LOCAL_BUDGET_SECONDS,
            f"classify + suppress + agency write took {elapsed:.2f}s against "
            f"a {LOCAL_BUDGET_SECONDS}s budget")

    def test_the_poll_interval_is_what_the_running_loop_uses(self):
        import scripts.reply_watch_loop as loop

        self.assertIn("--interval", inspect.getsource(loop.main))
        parser = argparse.ArgumentParser()
        parser.add_argument("--interval", type=float, default=300.0)
        self.assertEqual(parser.parse_args([]).interval,
                         float(POLL_INTERVAL_SECONDS))

    def test_the_documented_default_agrees_with_the_loop(self):
        """Two constants that must not drift, checked against each other.

        `REPLY_POLL_SECONDS` is what the in-process watcher uses and
        `--interval` is what the standalone loop uses. A deployment running
        one and a latency computed from the other is how a 15-minute promise
        quietly becomes a 30-minute one.
        """
        from src import config

        described = dict((name, why) for name, _kind, _area, why
                         in config.VARIABLES)["REPLY_POLL_SECONDS"]
        self.assertIn(str(POLL_INTERVAL_SECONDS), described)

    def worst_case(self):
        return (POLL_INTERVAL_SECONDS + STOP_WRITE_MEASURED_SECONDS
                + LOCAL_BUDGET_SECONDS)

    def test_the_measured_worst_case_clears_the_gate(self):
        self.assertLess(self.worst_case(), GATE_SECONDS)

    def test_the_gate_has_headroom_for_provider_visibility(self):
        """Term 1 is unmeasured. Say how much room is left for it."""
        headroom = GATE_SECONDS - self.worst_case()
        self.assertGreater(
            headroom, 8 * 60,
            "less than 8 minutes left for provider visibility - the "
            "unmeasured term now dominates the gate")


if __name__ == "__main__":
    unittest.main()
