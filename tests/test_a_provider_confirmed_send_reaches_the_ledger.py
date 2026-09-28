#!/usr/bin/env python3
"""EmailBison's own sends have to reach this system's ledger.

MEASURED 2026-09-28, on the production store and the real provider.

    EmailBison, `scheduled-emails` over the 20 campaigns
    `campaigns.jsonl` claims, fully paginated           912 rows `sent`
    confirmed touches in the whole record event log       1

`leadobserve.confirm_email_touches` was already correct and had ZERO
production callers - reachable only from `python -m src.leadobserve`. So this
is not a missing computation, it is the repository's named recurring defect:
a thing computed correctly that nothing downstream reads, sitting on the most
safety-relevant fact the provider publishes. Four symptoms, one cause:

    `already_sent` is empty for a person who was really emailed, so a
      step-four draft may write "as I mentioned" with nothing behind it - and
      may equally repeat step one word for word
    `digest.lines` says "Confirmed sends: none recorded"
    `slackagenttools._ledger_carries_sends` answers False
    the weekly report calls 1,504 accounts unplaceable, which measures the
      blind spot rather than the estate

And a second, quieter defect underneath it. `scheduled_rows` was the FOURTH
reader of the campaign queue and took the 40-page default while the other
three walk `bison.CAMPAIGN_QUEUE_PAGE_CAP`.
`tests/test_the_queue_cap_is_one_number.py` exists to prevent exactly that
drift and could not see this reader, because nothing called it. Campaign 491
holds 665 queue rows - 45 pages - so the ONE function whose job is to record
sends could not read the campaign with the most of them: 410 provider-
confirmed sends, invisible, and invisible without an error anybody would see.

WHAT THESE TESTS REFUSE TO DO. They never assert that a function exists, that
a source file contains a word, or that a shape is a dict. Every one of them
changes provider truth and asserts what the production consumers then answer -
and each positive has a negative control beside it, because a reconciler that
recorded a touch for every queue row would pass a test that only ever showed
it a `sent` row.
"""
import unittest
from unittest import mock

from src import (account, digest, events, generate, leadobserve, push,
                 replywatch, store, touch)
from src.providers import bison
from tests.base import QueueTest

CAMPAIGN = 493
CLIENT = "productive"
REC = "northwind-test"
CONTACT = "priya-raghunathan"
ADDRESS = "priya@northwind.test"
SENT_AT = "2026-09-23T18:23:03.000000Z"

#: Campaign 493's real sequence, read from the provider on 2026-09-28: three
#: steps, orders 1/2/3, no variants, steps two and three same-thread replies.
#: Every other sending campaign in this estate has the same shape.
SEQUENCE = [
    {"id": 4757, "order": 1, "variant": None, "variant_from_step": None,
     "thread_reply": False, "active": True},
    {"id": 4758, "order": 2, "variant": None, "variant_from_step": None,
     "thread_reply": True, "active": True},
    {"id": 4759, "order": 3, "variant": None, "variant_from_step": None,
     "thread_reply": True, "active": True},
]


def queue_row(status="sent", sent_at=SENT_AT, row_id=88001, step_id=4757,
              variables=None, email=ADDRESS):
    """One row in the shape `bison.scheduled_emails` really returns.

    Field for field off a live read of campaign 493 on 2026-09-28: the lead
    is a nested object carrying `custom_variables` in the provider's
    `[{name, value}]` wire shape, and `status` is the provider's own word.
    """
    if variables is None:
        variables = {"record_id": REC, "contact_key": CONTACT,
                     "client": CLIENT}
    return {
        "id": row_id,
        "campaign_id": CAMPAIGN,
        "sequence_step_id": step_id,
        "thread_reply": False,
        "status": status,
        "sent_at": sent_at,
        "scheduled_date": "2026-09-23T18:00:00.000000Z",
        "raw_message_id": f"<{row_id}@wwwtheproductiveai.com>",
        "email_subject": "quick question about Northwind",
        "email_body": "<p>Hello Priya,</p><p>One question.</p>",
        "sender_email": {"id": 2763, "email": "i.mamic@test.invalid"},
        "campaign": {"id": CAMPAIGN, "status": "active",
                     "open_tracking": False},
        "lead": {"id": 771001, "email": email,
                 "custom_variables": [{"name": k, "value": v}
                                      for k, v in sorted(variables.items())]},
        "opens": 0, "unique_opens": 0, "clicks": 0, "replies": 0,
        "unique_replies": 0, "interested": False,
    }


class LedgerTest(QueueTest):

    def setUp(self):
        super().setUp()
        store.save([self.record()])

    def record(self):
        return dict(
            store.new_record(REC, "cold", CLIENT, "Northwind Studio",
                             "northwind.test"),
            contacts=[{"key": CONTACT, "name": "Priya Raghunathan",
                       "title": "Operations Director", "email": ADDRESS}],
            cadence={CONTACT: {"em1": {"channel": "email", "day": 1,
                                       "status": "prepared",
                                       "subject": "quick question about "
                                                  "Northwind",
                                       "body": "Hello Priya, one question."}}})

    def provider(self, *rows, campaigns=None, steps=None):
        """Patch the provider reads, and refuse a cap this reader must not use.

        The fake ASSERTS ON THE CAP IT IS HANDED rather than ignoring it. A
        reader that silently took the 40-page default is the defect under
        test, and a fake that accepted any cap would pass either way.

        `sequence_steps` is patched too, and it must be: unpatched, the step
        resolver would reach the real EmailBison from a unit test.
        """
        rows = list(rows)

        def fake(cid, cap=None):
            if cap != bison.CAMPAIGN_QUEUE_PAGE_CAP:
                raise AssertionError(
                    f"scheduled_emails called with cap={cap!r}; the campaign "
                    f"queue has one cap and it is "
                    f"{bison.CAMPAIGN_QUEUE_PAGE_CAP}")
            return [r for r in rows if int(r["campaign_id"]) == int(cid)]

        patches = [mock.patch.object(bison, "scheduled_emails", fake),
                   mock.patch.object(bison, "sequence_steps",
                                     lambda cid: list(SEQUENCE if steps is None
                                                      else steps))]
        if campaigns is not None:
            patches.append(mock.patch.object(
                leadobserve, "claimed_email_campaigns",
                lambda *a, **k: list(campaigns)))
        return _All(patches)

    def rec(self):
        return store.get(REC)

    def confirmed(self):
        return account.touches(self.rec(), CONTACT, confirmed_only=True)

    def already_sent(self):
        """What the DRAFT PROMPT would be handed. The production consumer."""
        rec = self.rec()
        contact = rec["contacts"][0]
        sequence = [{"key": "em1", "day": 1, "channel": "email"},
                    {"key": "em3", "day": 8, "channel": "email"}]
        return generate.history_block(rec, contact, sequence, "em3", "email")


class _All:
    """Several patches as one context manager, so a test reads in one line."""

    def __init__(self, patches):
        self.patches = patches

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()
        return False


class AProviderSendBecomesAConfirmedTouch(LedgerTest):

    def test_the_ledger_is_empty_before_anything_runs(self):
        """The baseline this fixes, asserted rather than assumed."""
        self.assertEqual(self.confirmed(), [])
        self.assertEqual(self.already_sent(), [])

    def test_a_sent_row_writes_exactly_one_confirmed_touch(self):
        with self.provider(queue_row()):
            out = leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(len(out["recorded"]), 1)
        self.assertEqual(len(self.confirmed()), 1)

    def test_the_touch_is_dated_by_the_provider_not_by_now(self):
        """A reconciliation run on Monday must not claim Wednesday's send
        happened on Monday. `created_at` on our side is never the authority."""
        with self.provider(queue_row()):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        found = [e for e in self.rec()["events"]
                 if e["type"] == events.PUSH_MARKED]
        self.assertEqual(found[0]["at"], SENT_AT)

    def test_already_sent_stops_being_empty(self):
        """CRITERION 1. The block the draft prompt is handed, by name."""
        with self.provider(queue_row()):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        block = self.already_sent()
        self.assertEqual(len(block), 1)
        self.assertEqual(block[0]["channel"], "email")

    def test_the_event_carries_the_provider_evidence(self):
        """A touch nobody can trace back to a provider row is not a readback."""
        with self.provider(queue_row()):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        found = [e for e in self.rec()["events"]
                 if e["type"] == events.PUSH_MARKED][0]
        self.assertEqual(found["provider"], leadobserve.EMAILBISON)
        self.assertEqual(found["scheduled_email_id"], 88001)
        self.assertEqual(str(found["campaign_id"]), str(CAMPAIGN))
        self.assertIn(str(CAMPAIGN), found["provider_event_id"])


class TheNegativeControls(LedgerTest):
    """A reconciler that wrote a touch for every row would pass every test
    above. These are the rows it must refuse."""

    def test_a_scheduled_row_writes_nothing(self):
        """Nothing has happened to anybody. This is the `push_prepared`
        error one layer out: a queued message is not a message."""
        with self.provider(queue_row(status="scheduled", sent_at=None)):
            out = leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(out["recorded"], [])
        self.assertEqual(len(out["waiting"]), 1)
        self.assertEqual(self.confirmed(), [])
        self.assertEqual(self.already_sent(), [])

    def test_a_sending_paused_row_writes_nothing(self):
        """The provider's own word on 1,556 rows in this estate today, and it
        is NOT in `EMAIL_STATES`. An unknown status must wait, never confirm."""
        with self.provider(queue_row(status="sending_paused", sent_at=None)):
            out = leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(out["recorded"], [])
        self.assertEqual(len(out["waiting"]), 1)
        self.assertEqual(self.confirmed(), [])

    def test_a_bounced_row_records_the_bounce_and_not_a_touch(self):
        """A send was attempted and failed. Nobody was reached, and
        `touch.CONFIRMING_EVENTS` excludes the bounce by name."""
        with self.provider(queue_row(status="bounced")):
            out = leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(len(out["recorded"]), 1)
        kinds = [e["type"] for e in self.rec()["events"]
                 if e["type"] in (events.PUSH_MARKED, events.EMAIL_BOUNCED)]
        self.assertEqual(kinds, [events.EMAIL_BOUNCED])
        self.assertEqual(self.confirmed(), [])
        self.assertEqual(self.already_sent(), [])

    def test_a_lead_this_system_cannot_place_is_unmatched_never_invented(self):
        """66 of the estate's real sends are in this state today, on
        503/504/505. Reported for a person, never attached to a near miss."""
        with self.provider(queue_row(variables={}, email="nobody@else.test")):
            out = leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(out["recorded"], [])
        self.assertEqual(len(out["unmatched"]), 1)
        self.assertEqual(self.confirmed(), [])

    def test_another_tenants_lead_is_refused_on_the_client_field(self):
        """Tenancy outranks the join. A `client` that disagrees with the
        record means the lead in front of us is not the lead we think it is."""
        with self.provider(queue_row(variables={"record_id": REC,
                                                "contact_key": CONTACT,
                                                "client": "someone-else"})):
            out = leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(out["recorded"], [])
        self.assertEqual(len(out["unmatched"]), 1)
        self.assertEqual(self.confirmed(), [])

    def test_dry_is_the_default_and_writes_nothing(self):
        with self.provider(queue_row()):
            out = leadobserve.confirm_email_touches(CAMPAIGN)
        self.assertFalse(out["live"])
        self.assertEqual(len(out["recorded"]), 1, "a dry run must still say "
                                                  "what it would do")
        self.assertEqual(self.confirmed(), [], "a dry run wrote to the ledger")


class ExactlyOnce(LedgerTest):

    def test_a_loop_running_every_five_minutes_records_one_touch(self):
        for _ in range(4):
            with self.provider(queue_row()):
                leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(len(self.confirmed()), 1)
        self.assertEqual(len(self.already_sent()), 1)

    def test_the_repeat_is_reported_as_already_known(self):
        with self.provider(queue_row()):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        with self.provider(queue_row()):
            out = leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(out["recorded"], [])
        self.assertEqual(len(out["already"]), 1)


class TheDigestStopsSayingNoneRecorded(LedgerTest):
    """CRITERION 3, through the real digest, not through a counter."""

    def _lines(self):
        return digest.lines(digest.build(CLIENT, until="2026-09-23T23:00:00Z"))

    def test_before_ingestion_it_says_none_recorded(self):
        self.assertIn("Confirmed sends: none recorded", self._lines())

    def test_after_ingestion_it_names_the_send(self):
        with self.provider(queue_row()):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        lines = self._lines()
        self.assertNotIn("Confirmed sends: none recorded", lines)
        self.assertIn("Confirmed sends: 1 to 1 people", lines)

    def test_a_scheduled_row_does_not_move_the_digest(self):
        """The negative control on the criterion itself."""
        with self.provider(queue_row(status="scheduled", sent_at=None)):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertIn("Confirmed sends: none recorded", self._lines())


class TheStepComesFromTheProvidersOwnRung(LedgerTest):
    """Without this, ingestion records the touch and `already_sent` stays
    empty anyway - the event is dropped by `sent_so_far` for naming no step.

    Measured 2026-09-28: of every event on 1,582 production records, exactly
    ONE carries `scheduled_email_id`, so the exact reconciliation answers
    None for effectively every real send.
    """

    def record(self):
        """Three declared email steps, as 1,272 of the real records have."""
        rec = super().record()
        rec["cadence"][CONTACT].update({
            "em2": {"channel": "email", "day": 4, "status": "planned"},
            "em3": {"channel": "email", "day": 8, "status": "planned"}})
        return rec

    def _step_recorded(self):
        return [e["step"] for e in self.rec()["events"]
                if e["type"] == events.PUSH_MARKED]

    def test_rung_one_lands_on_the_first_declared_email_step(self):
        with self.provider(queue_row(step_id=4757)):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(self._step_recorded(), ["em1"])

    def test_rung_two_lands_on_the_second_and_not_the_first(self):
        """5 of 489's 10 real sends and 88 of 491's 410 are rung two. Reading
        them as rung one would report two messages as one."""
        with self.provider(queue_row(step_id=4758)):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(self._step_recorded(), ["em2"])

    def test_two_rungs_to_one_person_are_two_touches_on_two_steps(self):
        with self.provider(queue_row(step_id=4757, row_id=1),
                           queue_row(step_id=4758, row_id=2)):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(sorted(self._step_recorded()), ["em1", "em2"])
        self.assertEqual(len(self.confirmed()), 2)

    def test_a_variant_takes_the_rung_it_varies_from(self):
        """A variant is the same rung in different words, not a further one."""
        steps = SEQUENCE + [{"id": 4999, "order": None, "variant": True,
                             "variant_from_step": 4758,
                             "thread_reply": True, "active": True}]
        with self.provider(queue_row(step_id=4999), steps=steps):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(self._step_recorded(), ["em2"])

    def test_an_exact_prior_event_still_wins_over_the_rung(self):
        """An identifier must never be overruled by a positional match."""
        rec = self.record()
        rec["events"] = [{"type": events.PUSH_PREPARED, "contact": CONTACT,
                          "step": "em3", "scheduled_email_id": 88001,
                          "at": SENT_AT}]
        store.save([rec])
        with self.provider(queue_row(step_id=4757)):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(self._step_recorded(), ["em3"])


class TheRungRefusesRatherThanGuesses(LedgerTest):
    """Each of these would otherwise attribute a real message to the wrong
    rung, which puts "as I mentioned" in front of somebody over words they
    never received."""

    def _ordinals(self, steps):
        return leadobserve.email_step_ordinals(CAMPAIGN, steps=steps)

    def test_a_sequence_with_an_unreadable_order_is_refused_whole(self):
        broken = [dict(SEQUENCE[0], order=None)] + SEQUENCE[1:]
        self.assertEqual(self._ordinals(broken), {})

    def test_two_steps_sharing_a_rung_refuse_the_whole_sequence(self):
        clash = [SEQUENCE[0], dict(SEQUENCE[1], order=1), SEQUENCE[2]]
        self.assertEqual(self._ordinals(clash), {})

    def test_a_variant_of_nothing_gets_no_rung(self):
        orphan = SEQUENCE + [{"id": 5000, "order": None, "variant": True,
                              "variant_from_step": None}]
        self.assertNotIn(5000, self._ordinals(orphan))

    def test_a_clean_sequence_is_not_refused(self):
        """Otherwise every refusal above would pass on a resolver that
        always returns nothing."""
        self.assertEqual(self._ordinals(SEQUENCE), {4757: 1, 4758: 2,
                                                    4759: 3})

    def test_a_rung_past_the_declaration_is_not_clamped_to_the_last_step(self):
        """The record declares em1 only. Rung three is NOT em1: clamping
        would report three confirmed touches as one."""
        with self.provider(queue_row(step_id=4759)):
            out = leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        # `events.record` drops a None field rather than storing a null, so
        # the absence of the key IS the absent step.
        steps = [e.get("step") for e in self.rec()["events"]
                 if e["type"] == events.PUSH_MARKED]
        self.assertEqual(steps, [None])
        self.assertEqual(out["stepless"], 1)

    def test_an_unorderable_sequence_still_records_the_touch(self):
        """The person WAS emailed. Refusing the rung must not refuse the
        fact - `_ledger_carries_sends` and the digest still have to see it."""
        broken = [dict(s, order=None) for s in SEQUENCE]
        with self.provider(queue_row(), steps=broken):
            out = leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        self.assertEqual(len(self.confirmed()), 1)
        self.assertFalse(out["sequence_ordered"])
        self.assertEqual(out["stepless"], 1)
        self.assertEqual(self.already_sent(), [],
                         "a touch with no rung must not be shown to the "
                         "draft prompt as though its day were known")


class AnUnreadableQueueIsUnknownAndNeverZero(LedgerTest):
    """Campaign 491's exact 2026-09-28 shape: 45 pages against a 40-page cap.

    The refusal is correct and is not what is fixed. What is fixed is a
    reconciliation that reported the whole estate while one campaign's 410
    sends were unread."""

    def _refusing(self, *rows):
        good = list(rows)

        def fake(cid, cap=None):
            if int(cid) == 491:
                raise bison.PartialInventory(
                    "emailbison scheduled_emails: 45 pages to walk and this "
                    "read stops at 40")
            return [r for r in good if int(r["campaign_id"]) == int(cid)]

        return _All([
            mock.patch.object(bison, "scheduled_emails", fake),
            mock.patch.object(bison, "sequence_steps",
                              lambda cid: list(SEQUENCE)),
            mock.patch.object(leadobserve, "claimed_email_campaigns",
                              lambda *a, **k: [491, CAMPAIGN])])

    def test_the_refusal_does_not_stop_the_other_campaigns(self):
        with self._refusing(queue_row()):
            out = leadobserve.confirm_all_email_touches(live=True)
        self.assertEqual(out["recorded"], 1)
        self.assertEqual(len(self.confirmed()), 1)

    def test_the_blind_campaign_is_named_and_the_run_is_incomplete(self):
        with self._refusing(queue_row()):
            out = leadobserve.confirm_all_email_touches(live=True)
        self.assertFalse(out["complete"])
        self.assertEqual([r["campaign_id"] for r in out["blind"]], ["491"])
        self.assertIn("PartialInventory", out["blind"][0]["why"])

    def test_a_readable_estate_reports_complete(self):
        """Otherwise `complete` would be a field that is always False and
        therefore says nothing."""
        with self.provider(queue_row(), campaigns=[CAMPAIGN]):
            out = leadobserve.confirm_all_email_touches(live=True)
        self.assertTrue(out["complete"])
        self.assertEqual(out["blind"], [])

    def test_unknown_is_never_reported_as_a_state_that_was_read(self):
        with self._refusing(queue_row()):
            out = leadobserve.confirm_all_email_touches(live=True)
        self.assertEqual(out["per_campaign"]["491"]["state"], "UNKNOWN")
        self.assertNotIn("recorded", out["per_campaign"]["491"])


class TheCapIsTheOneNumber(LedgerTest):
    """The fourth reader joins the three `test_the_queue_cap_is_one_number`
    already pins. Asserted on the ARGUMENT, not on the source text."""

    def test_scheduled_rows_walks_the_campaign_queue_cap(self):
        seen = {}

        def fake(cid, cap=None):
            seen["cap"] = cap
            return []

        with mock.patch.object(bison, "scheduled_emails", fake):
            leadobserve.scheduled_rows(CAMPAIGN)
        self.assertEqual(seen["cap"], bison.CAMPAIGN_QUEUE_PAGE_CAP)

    def test_it_is_not_the_forty_page_default(self):
        """The regression that hid 491. Equalising the two constants would
        silently restore it, so the difference is asserted here too."""
        self.assertNotEqual(bison.CAMPAIGN_QUEUE_PAGE_CAP, bison.PAGE_CAP)


class TheReconcilerHasAProductionCaller(LedgerTest):
    """CONSUMER BEFORE PRODUCER. `confirm_email_touches` was correct and had
    zero production callers for its whole life, which is why the ledger was
    empty. A unit test of the reconciler cannot notice that; only a test that
    enters through the loop can."""

    def _poll(self, *rows, reply_pages=()):
        good = list(rows)

        def fake_queue(cid, cap=None):
            return [r for r in good if int(r["campaign_id"]) == int(cid)]

        return _All([
            mock.patch.object(bison, "scheduled_emails", fake_queue),
            mock.patch.object(bison, "sequence_steps",
                              lambda cid: list(SEQUENCE)),
            mock.patch.object(leadobserve, "claimed_email_campaigns",
                              lambda *a, **k: [CAMPAIGN]),
            mock.patch.object(replywatch, "configured",
                              lambda *a, **k: True),
            mock.patch.object(replywatch.poller, "run",
                              lambda *a, **k: {"outcomes": [], "cursor": None,
                                               "pages": 0, "events": 0,
                                               "applied": 0, "duplicates": 0,
                                               "unmatched": 0}),
            mock.patch.object(replywatch, "expected_workspace",
                              lambda *a, **k: None)])

    def test_the_reply_watcher_records_the_send(self):
        """The whole chain: the loop that already runs on a timer -> the
        reconciler -> the record event log -> `already_sent`."""
        with self._poll(queue_row()):
            replywatch.poll_once("emailbison", live=True)
        self.assertEqual(len(self.confirmed()), 1)
        self.assertEqual(len(self.already_sent()), 1)

    def test_the_status_row_reports_what_the_reconciliation_saw(self):
        with self._poll(queue_row()):
            row = replywatch.poll_once("emailbison", live=True)
        self.assertEqual(row["sends_reconciled"], 1)
        self.assertTrue(row["sends_complete"])
        self.assertEqual(row["sends_blind"], [])

    def test_a_reconciliation_failure_never_stops_reply_ingestion(self):
        """A missed reply is somebody being written to after they answered.
        That outranks the ledger, so the reconciler must not be able to
        break the poll - and must not report clean either."""
        def explode(*a, **k):
            raise RuntimeError("provider unreachable")

        with mock.patch.object(leadobserve, "confirm_all_email_touches",
                               explode):
            with self._poll(queue_row()):
                row = replywatch.poll_once("emailbison", live=True)
        self.assertTrue(row["healthy"])
        self.assertIsNone(row["sends_complete"])
        self.assertNotEqual(row["sends_complete"], True)

    def test_heyreach_does_not_run_the_email_reconciler(self):
        """A per-provider step must not fire for the other provider."""
        called = []
        with mock.patch.object(leadobserve, "confirm_all_email_touches",
                               lambda **k: called.append(k) or {}):
            replywatch._reconcile_sends("heyreach", live=True)
        self.assertEqual(called, [])


class TheConfirmingVocabularyIsNotWidened(LedgerTest):
    """The one thing that would make all of this dangerous rather than
    useful: reading something weaker than a send as a send."""

    def test_push_prepared_is_still_not_a_confirming_event(self):
        self.assertNotIn(events.PUSH_PREPARED, touch.CONFIRMING_EVENTS)

    def test_sent_maps_to_push_marked_and_not_to_delivered(self):
        """EmailBison's `sent` says it handed the message to SMTP. Recording
        it as `email_delivered` would claim a mailbox accepted it."""
        self.assertEqual(leadobserve.EVENT_FOR[leadobserve.SENT],
                         events.PUSH_MARKED)
        self.assertEqual(touch.CONFIRMING_EVENTS[events.PUSH_MARKED],
                         touch.SENT)


if __name__ == "__main__":
    unittest.main()
