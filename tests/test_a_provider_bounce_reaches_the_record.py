#!/usr/bin/env python3
"""A bounce the provider reports is on the record, so the send path refuses.

BORN RED, AND RED AT THE PRODUCER END. `tests/test_a_bounced_address_stops_
being_sendable.py` already proves the whole CONSUMER half: `channels._bounced`
reads `rec["events"]` for `events.EMAIL_BOUNCED`, `eligibility.decide` consults
it at `src/eligibility.py:806-807` before MX and before verification, and since
`acf078b72` that is measured on a path that is actually reached. None of that
is in question here.

What is in question is whether the event ever ARRIVES. Measured 2026-10-15:

  - Five provider-confirmed bounces. Read from the watcher heartbeats at
    2026-10-15T19:09-19:12Z, which are written by the twenty
    `scripts/bison_watch_loop.py` processes that poll EmailBison every 180s:
    campaign 491 -> 1, 492 -> 1, 495 -> 1, 503 -> 2. No provider call was made
    to establish this; the watchers had already paid for the reads.
  - Zero `email_bounced` events on any record. `0070` measured the three
    records behind the 491/492/495 bounces: 12 / 3 / 3 events each, every one
    of them `draft_approved`, and `channels.email_verdict` answering
    `(True, None)` - SENDABLE, no reason - for all three addresses.
  - And the one scheduled path that CAN write the event was live through every
    one of the five. `scripts/reply_watch_loop.py` has been running
    `poller.run("emailbison")` since 2026-09-20T12:23:34Z. Its own sink
    records 26 REPLY ingests and no bounce - including at 15:15, 15:21, 15:26
    and 16:03 on 2026-09-22, minutes either side of 491's bounce at 15:29:12Z
    and 492's at 15:36:47Z, and at 12:24 and 13:25 on 2026-09-25 around 503's
    two at 12:32:20Z and 12:54:34Z.

So the replies feed is not where this estate's bounces appear. Every one of the
five is visible on the scheduled-email queue, which `leadobserve.scheduled_rows`
already reads and turns into `state: "bounced"` - and the only function that
turns that into an event, `leadobserve.confirm_email_touches`, has no
production caller at all.

WHY THIS TEST IS SHAPED AROUND THE PROVIDER AND NOT AROUND A FUNCTION. The
invariant does not care which module records the bounce; it cares that a bounce
the provider is reporting cannot leave the address sendable. So the fixture
puts the provider in exactly the state it was in on 2026-09-22 - the queue row
says `bounced`, the replies feed says nothing - and then runs the paths a
scheduled host actually runs. Whatever wiring is chosen, this goes green
without being rewritten, as long as the producer sits somewhere that runs.

THE CONTROLS ARE THE POINT, because a red test proves nothing until the red is
attributable. `TheProviderFixtureIsReal` shows the queue row is a row the
estate's own reader classifies as a bounce, and `TheHarnessCarriesAnEvent`
shows the same provider, the same record and the same scheduled path carry a
REPLY all the way to a pause. Both are green today. What is missing is one
specific thing and these two say which.
"""
import unittest
from unittest import mock

from src import (channels, eligibility, events, leadobserve, lint,
                 poller, store)
from src.providers import bison
from tests.base import ProviderTest

PRODUCTIVE = {"id": 10, "name": "PRODUCTIVE"}

#: The campaign the fixture's bounce sits in. 492 is one of the four that
#: really bounced; the number only has to be consistent within the test.
CAMPAIGN = 492

ADDRESS = "dana@acme.test"
CONTACT_KEY = "ck-1"
RECORD_ID = "rec-1"


def _queue_row(status="bounced"):
    """One `GET /api/campaigns/{id}/scheduled-emails` row, as the provider
    returns it.

    Shaped from the fields `leadobserve.scheduled_rows` actually reads
    (`src/leadobserve.py:416-477`), including the nesting that matters: the
    lead sits under `lead` and our own identifiers sit under the lead's
    `custom_variables`, which is where `GET /api/replies` was measured to put
    them on 2026-09-25 and where `bison.variables_of` looks.
    """
    return {
        "id": 900001,
        "status": status,
        "sequence_step_id": 5001,
        "scheduled_date": "2026-09-22T15:00:00.000000Z",
        "sent_at": "2026-09-22T15:36:47.000000Z",
        "raw_message_id": "<msg-900001@acme.test>",
        "email_subject": "a subject",
        "email_body": "<p>a body</p>",
        "opens": 0, "unique_opens": 0, "clicks": 0,
        "replies": 0, "unique_replies": 0, "interested": 0,
        "lead": {
            "id": 204472,
            "email": ADDRESS,
            "first_name": "Dana",
            "custom_variables": [
                {"name": "record_id", "value": RECORD_ID},
                {"name": "contact_key", "value": CONTACT_KEY},
                {"name": "client", "value": "productive"},
            ],
        },
        "sender_email": {"id": 3687, "email": "sender@resonate.test"},
        "campaign": {"id": CAMPAIGN, "status": "paused",
                     "open_tracking": False},
    }


def _reply_row():
    """One `/api/replies` row for the same person. The control's input."""
    return {
        "id": 1609999, "uuid": "u-1609999",
        "lead_id": 204472, "campaign_id": CAMPAIGN,
        "type": "reply", "folder": "inbox", "automated_reply": False,
        "from_email_address": ADDRESS,
        "created_at": "2026-09-22T15:36:47.000000Z",
        "date_received": "2026-09-22T15:36:47.000000Z",
        "html_body": "<p>no thanks</p>",
        "lead": {"id": 204472, "email": ADDRESS, "first_name": "Dana",
                 "custom_variables": [
                     {"name": "record_id", "value": RECORD_ID},
                     {"name": "contact_key", "value": CONTACT_KEY},
                     {"name": "client", "value": "productive"}]},
    }


def _feed(*rows):
    """A `/api/replies` fetch returning one page and then the end of the feed.

    Called with no rows it is the feed as it really behaved through all five
    bounces: a 200 with nothing in it.
    """
    pages = [(list(rows), None)] if rows else []

    def fetch(cursor=None, per_page=None):
        return pages.pop(0) if pages else ([], None)
    return fetch


def _contact():
    """A contact that is otherwise sendable under THIS record's client.

    `productive` requires `deliverable` as primary; the evidence shape is
    copied from `test_a_bounced_address_stops_being_sendable._productive_
    contact` so the two files cannot drift into disagreeing about what a
    sendable contact is.
    """
    return {"key": CONTACT_KEY, "email": ADDRESS, "name": "Dana Reed",
            "sendable": True, "verdict": "valid",
            "verification": {"evidence": [
                {"provider": "deliverable", "status": "valid",
                 "email": ADDRESS},
                {"provider": "reoon", "status": "valid", "email": ADDRESS}]}}


class BounceTest(ProviderTest):
    """One record, and a provider that can be put into either state."""

    def setUp(self):
        super().setUp()
        # THE CACHE IS WHY THIS FILE PASSED ALONE AND FAILED IN THE SUITE.
        #
        # MEASURED 2026-10-15 on 9bd8648f5: run alone this module has five
        # failing names; inside the full run it has six, and the sixth is
        # `test_without_a_bounce_the_refusal_is_the_other_one` - the GREEN
        # control - failing `held:verification_unknown != blocked:lint_
        # failed`. `lint.policy_for_record` caches the verification policy
        # per client in a MODULE-LEVEL dict cleared only by this call, and
        # this module runs after fifty-eight others, several of which rewrite
        # a client config. A cached default policy puts ContactOut back as
        # primary, so Productive's deliverable/reoon evidence reads as
        # unknown and `decide` holds before it ever reaches lint.
        #
        # Proven rather than inferred: seeding `_POLICY_CACHE["productive"]`
        # with None reproduces all three failures and the exact message
        # (`work/suppression-measure/0110/poison.py`).
        lint.forget_policies()
        rec = store.new_record(RECORD_ID, "domains", "productive", "Acme",
                               "acme.test")
        rec["state"] = "ready"
        rec["contacts"] = [_contact()]
        with store.transaction() as rows:
            rows.append(rec)

    # ------------------------------------------------- the provider's state

    def provider_reports_a_bounce(self, status="bounced"):
        """The state EmailBison was in on 2026-09-22: the queue row says the
        send bounced, and the replies feed says nothing at all."""
        return mock.patch.object(bison, "scheduled_emails",
                                 lambda campaign_id, cap=None: [
                                     _queue_row(status)])

    def provider_reports_nothing(self):
        return mock.patch.object(bison, "scheduled_emails",
                                 lambda campaign_id, cap=None: [
                                     _queue_row("sent")])

    # ------------------------------------------- what a scheduled host runs

    def run_the_scheduled_producers(self, replies=()):
        """Every production path a scheduled host runs against EmailBison.

        TODAY THERE IS EXACTLY ONE, and that is the finding rather than a
        shortcut. `scripts/reply_watch_loop.py --interval 300` was measured
        running as PID 29528 on 2026-10-15 and it calls `poller.run`; the
        twenty `scripts/bison_watch_loop.py` processes beside it read the
        scheduled-email queue every 180s and write no canonical state from it.

        A wiring change adds its host here, and the name it adds is the
        honest record of what now runs. A producer added somewhere nothing
        runs still leaves this list - and this test - exactly as it is.
        """
        ran = []
        ran.append(("poller.run:emailbison", poller.run(
            "emailbison", live=True, identify=lambda: PRODUCTIVE,
            fetch=_feed(*replies), sleep=lambda *_: None)))
        # THE SECOND SCHEDULED HOST: the watcher. Twenty
        # `scripts/bison_watch_loop.py` processes poll EmailBison every 180s
        # and were measured live on 2026-10-15 at 19:57Z, one per campaign.
        # ONE CYCLE OF THE REAL `main()` IS RUN, not any function a wiring
        # might add: this file promises to stay agnostic about which module
        # records the bounce, and a test that called a new producer by name
        # would be asserting the design instead of the invariant. A producer
        # wired anywhere `main()` reaches turns the bounce tests green; one
        # wired where nothing runs leaves them exactly as red as they are.
        ran.append(("bison_watch_loop.main:one-cycle",
                    self.one_watcher_cycle()))
        return ran

    class _OneCycle(BaseException):
        """Ends `main()`'s infinite loop at its first sleep.

        `BaseException` deliberately: `main` catches `Exception` around the
        poll, and a stop signal that the code under test can swallow would
        make a hung loop look like a finished cycle.
        """

    #: What `bison.campaign` answers during the cycle. The counters match the
    #: fixture's single bounced row; `snapshot` reads nothing else off it.
    CAMPAIGN_ROW = {"status": "paused", "emails_sent": 1, "replied": 0,
                    "bounced": 1, "unsubscribed": 0, "total_leads": 1,
                    "updated_at": "2026-09-22T15:36:47.000000Z"}

    def one_watcher_cycle(self):
        """One poll of one campaign, as the scheduled watcher runs it.

        Every provider read `snapshot` makes is mocked - `campaign`,
        `membership`, `sending_schedule`, and `scheduled_emails` by the
        caller's context manager - so nothing here reaches a network, which
        `ProviderTest` would refuse anyway.
        """
        import importlib
        import scripts.bison_watch_loop as wl
        importlib.reload(wl)

        def stop(*_a, **_k):
            raise self._OneCycle

        with mock.patch.object(wl, "load_env", lambda *a, **k: None), \
                mock.patch.object(wl.time, "sleep", stop), \
                mock.patch.object(wl.bison, "campaign",
                                  lambda cid: dict(self.CAMPAIGN_ROW)), \
                mock.patch.object(wl.bison, "membership",
                                  lambda *a, **k: {}), \
                mock.patch.object(wl.bison, "sending_schedule",
                                  lambda *a, **k: {"emails_being_sent": 0}):
            try:
                wl.main(["--campaign", str(CAMPAIGN), "--interval", "0"])
            except self._OneCycle:
                pass
        return "one cycle"

    # ------------------------------------------------------------- readback

    def bounces_on_the_record(self):
        rec = store.get(RECORD_ID)
        return [e for e in (rec.get("events") or [])
                if e.get("type") == events.EMAIL_BOUNCED]

    def kinds_on_the_record(self):
        rec = store.get(RECORD_ID)
        return sorted({e.get("type") for e in (rec.get("events") or [])})


class TheProviderFixtureIsReal(BounceTest):
    """GREEN TODAY. The queue row is a row this estate already reads as a
    bounce - not a straw man built to fail."""

    def test_the_reader_classifies_the_row_as_a_bounce(self):
        with self.provider_reports_a_bounce():
            rows = leadobserve.scheduled_rows(CAMPAIGN)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["state"], leadobserve.BOUNCED)

    def test_the_row_names_our_record_and_our_contact(self):
        """Without this the bounce is unattributable and the test would be
        measuring a matching failure instead of a missing producer."""
        with self.provider_reports_a_bounce():
            row = leadobserve.scheduled_rows(CAMPAIGN)[0]
        self.assertEqual(row["record_id"], RECORD_ID)
        self.assertEqual(row["contact_key"], CONTACT_KEY)
        self.assertEqual(row["email"], ADDRESS)

    def test_the_canonical_event_for_that_state_exists(self):
        self.assertEqual(leadobserve.EVENT_FOR[leadobserve.BOUNCED],
                         events.EMAIL_BOUNCED)
        self.assertIn(events.EMAIL_BOUNCED, events.KNOWN)


class TheHarnessCarriesAnEvent(BounceTest):
    """GREEN TODAY. The same provider, the same record and the same scheduled
    path carry a REPLY all the way to a pause.

    This is what makes the red below attributable. If this ever goes red the
    failure is the harness - the store, the identity, the matching or the
    ingest - and the bounce tests below say nothing until it is green again.
    """

    def test_a_reply_reaches_the_record(self):
        with self.provider_reports_nothing():
            self.run_the_scheduled_producers(replies=[_reply_row()])
        self.assertIn(events.REPLY_RECEIVED, self.kinds_on_the_record())

    def test_a_reply_pauses_the_record(self):
        with self.provider_reports_nothing():
            self.run_the_scheduled_producers(replies=[_reply_row()])
        self.assertTrue(store.get(RECORD_ID).get("paused"))


class ABounceTheProviderReportsReachesTheRecord(BounceTest):
    """RED TODAY. Nothing on a schedule carries it."""

    def test_the_event_is_recorded(self):
        with self.provider_reports_a_bounce():
            ran = self.run_the_scheduled_producers()
        self.assertTrue(
            self.bounces_on_the_record(),
            "the provider reports this address as bounced on the "
            "scheduled-email queue and no production path on a schedule "
            f"recorded it. Paths run: {[name for name, _ in ran]}. Events on "
            f"the record: {self.kinds_on_the_record()}")

    def test_the_event_names_the_contact_who_bounced(self):
        """A bounce is a fact about ONE ADDRESS. An event that names no
        contact would close the wrong people or nobody."""
        with self.provider_reports_a_bounce():
            self.run_the_scheduled_producers()
        found = self.bounces_on_the_record()
        self.assertTrue(found, "no bounce was recorded at all")
        self.assertEqual(found[0].get("contact"), CONTACT_KEY)

    def test_nothing_is_recorded_when_the_provider_reports_no_bounce(self):
        """GUARD THE GUARD, and it guards the expensive direction. A producer
        that writes a bounce for every row it walks would close this estate's
        whole book, and it would pass the two tests above."""
        with self.provider_reports_nothing():
            self.run_the_scheduled_producers()
        self.assertEqual(self.bounces_on_the_record(), [])


class TheSendPathRefusesIt(BounceTest):
    """RED TODAY, and this is the invariant the other classes serve.

    The content handed to `decide` fails lint on `body_too_short` - 200
    characters is one word and lint counts words. That is deliberate, and it
    is borrowed from the test 0080 repaired: the bounce gate sits BEFORE lint
    inside `_email_checks`, so with a bounce the reason must be
    `blocked:address_bounced` and without one it must be `blocked:lint_failed`.
    The second is a positive control rather than an `assertNotEqual`, which
    every refusal in the system satisfies.
    """

    CONTENT = {"channel": "email", "subject": "s", "body": "b" * 200}

    def decide(self):
        rec = store.get(RECORD_ID)
        return eligibility.decide(rec, rec["contacts"][0], "day1",
                                  channel="email", step=dict(self.CONTENT))

    def test_the_address_is_not_sendable_after_the_provider_reports_a_bounce(self):
        with self.provider_reports_a_bounce():
            self.run_the_scheduled_producers()
        rec = store.get(RECORD_ID)
        ok, why = channels.email_verdict(rec, rec["contacts"][0])
        self.assertFalse(
            ok, "the provider reports this address as bounced and "
                "channels.email_verdict still calls it sendable, because no "
                "producer put the event on the record")
        self.assertEqual(why, channels.BOUNCED)

    def test_the_send_path_blocks_it(self):
        with self.provider_reports_a_bounce():
            self.run_the_scheduled_producers()
        verdict = self.decide()
        self.assertEqual(
            verdict.get("reason"), eligibility.BLOCKED_BOUNCED,
            "the provider reports this address as bounced and the send path "
            f"refused for {verdict.get('reason')!r} instead - which means the "
            "bounce never arrived, not that the gate is broken")

    def test_without_a_bounce_the_refusal_is_the_other_one(self):
        """GREEN TODAY. Proves `decide` reaches `_email_checks` with this
        fixture, so a red above is the producer and not an earlier return."""
        with self.provider_reports_nothing():
            self.run_the_scheduled_producers()
        self.assertEqual(self.decide().get("reason"),
                         eligibility.BLOCKED_LINT)


class EveryWordTheProviderMightUseIsStillABounce(BounceTest):
    """RED TODAY, and it is the under-suppression half.

    This estate already declares four provider words for a bounce, in two
    places that were written against the live instance:
    `src/suppression.py:409-410` (`PROVIDER_STOPPED`) and
    `scripts/reengagement_provider_confirmed.py:109` (`BOUNCE_STATES`). The
    reader on the queue surface knows exactly one of them:
    `leadobserve.EMAIL_STATES` is `(scheduled, sent, bounced, stopped)` and
    `_email_state` folds everything else to `email_state_unknown`, which
    `confirm_email_touches` reports as `waiting` - "nothing has happened to
    anybody".

    Only `bounced` has been OBSERVED on this estate: the 2026-10-15 snapshot's
    whole status vocabulary is bounced, in_sequence, replied, scheduled,
    sending_paused, sent, sequence_finished, stopped. So the other three are
    not a measured provider behaviour - they are words this repository has
    already decided mean a bounce, and the day the provider uses one of them
    the queue reader answers "nothing happened" and the address stays
    sendable. A vocabulary change must surface as a row a person reads.
    """

    WORDS = ("bounced", "bounce", "hard_bounced", "soft_bounced")

    def test_each_declared_bounce_word_maps_to_the_bounce_event(self):
        for word in self.WORDS:
            with self.subTest(word=word):
                state = leadobserve._email_state(word)
                self.assertEqual(
                    leadobserve.EVENT_FOR.get(state), events.EMAIL_BOUNCED,
                    f"the provider saying {word!r} reads as {state!r}, which "
                    f"carries no canonical event, so the queue reader would "
                    f"report it as waiting and the address would stay "
                    f"sendable")

    def test_the_observed_word_is_the_one_that_works(self):
        """GREEN TODAY. The control: `bounced` is handled, so the failures
        above are about the words beside it and not about the mapping."""
        self.assertEqual(
            leadobserve.EVENT_FOR.get(leadobserve._email_state("bounced")),
            events.EMAIL_BOUNCED)


class OnlyTheBounceIsRecorded(BounceTest):
    """GREEN TODAY, AND IT IS THE EXPENSIVE DIRECTION.

    `leadobserve.EVENT_FOR` maps `sent -> PUSH_MARKED` as well as
    `bounced -> EMAIL_BOUNCED`, and `PUSH_MARKED` is in
    `touch.CONFIRMING_EVENTS`, which `fatigue.contact_check` counts against
    `max_touches_total` and `max_touches_per_week`. The twenty watched
    EmailBison campaigns carried 918 sends on 2026-10-15 against ONE
    confirmed touch in 1,582 records, so a producer that recorded every
    state it walked would write 918 touches on its first cycle and silently
    change who may be contacted.

    MEASURED 2026-10-15: without this test that mutation is invisible.
    Removing the bounce-only filter from `record_bounces` left the whole
    module at its unmutated name-set, because every other case here asks
    only about EMAIL_BOUNCED.
    """

    def test_a_sent_row_does_not_become_a_confirmed_touch(self):
        with self.provider_reports_nothing():
            self.run_the_scheduled_producers()
        rec = store.get(RECORD_ID)
        kinds = [e.get("type") for e in (rec.get("events") or [])]
        self.assertNotIn(
            events.PUSH_MARKED, kinds,
            "the provider reports this row as `sent` and a producer recorded "
            "a confirmed touch for it. That is the touch backfill, not the "
            "bounce gate, and it moves `fatigue.contact_check` for every "
            "record it reaches")


class TheSameBounceIsNotRecordedTwice(BounceTest):
    """RED TODAY, and red for the ordinary reason: nothing records it once.

    It is here because of how the producer would run. A bounced queue row
    stays `bounced`, the watcher re-reads that queue every 180 seconds, and
    twenty of them were measured running on 2026-10-15. A producer without
    idempotency would therefore append one event per bounce per three
    minutes - 480 a day, per bounce - and `events.record`'s
    `provider_event_id` is what prevents it. This asserts the behaviour, not
    the mechanism.
    """

    def test_two_cycles_record_one_bounce(self):
        with self.provider_reports_a_bounce():
            self.run_the_scheduled_producers()
            self.run_the_scheduled_producers()
        self.assertEqual(
            len(self.bounces_on_the_record()), 1,
            "two polls of the same unchanged bounced row produced "
            f"{len(self.bounces_on_the_record())} event(s) on the record")


if __name__ == "__main__":
    unittest.main()
