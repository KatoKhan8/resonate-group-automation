"""Our store and EmailBison must agree about who has replied. Both ways.

MEASURED 2026-09-24, and this file is the regression for it. Five leads
carried `reply_received` AND `reply_classified` in the store - three of them
also `contact_stopped` or `company_paused` - and were still `in_sequence` at
the provider in campaigns 491 and 492, both ACTIVE. They were stopped by hand.
23 of the 28 flagged records were correctly stopped, so the reply ingestion
path (PROBLEM-REGISTER ISSUE-001) works and this is the link below it: nothing
compared the two pictures afterwards.

THE WRITE SCOPE IS THE PART WORTH PINNING. A watcher is a reader and holds no
write scope, which is why the first blank-content halt alerted and halted
nothing - the guard was right and the control was ceremony. The fix there was
`allow_writes(only=PAUSE_ROUTES)`, and
`test_a_blank_email_can_never_be_sent_again` asserts that the same scope does
NOT reach `leads/attach-leads`. This is the equivalent one route further down:
the reconciliation may stop ONE PERSON and may not enrol, resume, pause a
campaign or attach leads, and stopping is the only verb in this system that
can only ever mean somebody receives less.

Every fixture status here is a word read off the live estate on 2026-09-24:
`in_sequence`, `sending_paused`, `stopped`, `replied`, `bounced`. The
membership shapes are the ones `bison._status_in` produces.
"""

import importlib.util
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (campaigns, events, notify, providers as _providers,   # noqa: E402
                 replyreconcile, store)
from src.providers import bison                                        # noqa: E402
from tests.campaignbase import CampaignTest                            # noqa: E402

PROVIDER_CAMPAIGN = 491
ACME_LEAD = 900001
BOREALIS_LEAD = 900002

#: A lead in this campaign that our store has never staged. 491 holds leads
#: this factory never created, and 73 of the 76 blank emails went to exactly
#: that population - a check that only looks at our own rows reports a
#: campaign clean while it is not.
FOREIGN_LEAD = 900099


def _watch_loop():
    """`scripts/bison_watch_loop.py`, imported by path. Not a package."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "scripts", "bison_watch_loop.py")
    spec = importlib.util.spec_from_file_location("blw_reconcile", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReconcileTest(CampaignTest):
    """Two records, one contact each, both staged into EmailBison 491."""

    def setUp(self):
        super().setUp()
        self.recs = self.seed_records()
        for rec, lead_id in zip(self.recs, (ACME_LEAD, BOREALIS_LEAD)):
            rec["contacts"][0]["bison_lead_id"] = lead_id
        store.save(self.recs)

        row = campaigns.new_campaign("demo-email-v1", "demo", "Demo email")
        row["record_ids"] = [r["id"] for r in self.recs]
        row["bison_campaign_id"] = PROVIDER_CAMPAIGN
        campaigns.save([row])
        self.row = row

        self._real = {name: getattr(bison, name)
                      for name in ("membership", "stop_lead")}
        self.addCleanup(self._restore_bison)
        self.stopped = []

    def _restore_bison(self):
        for name, fn in self._real.items():
            setattr(bison, name, fn)

    # -------------------------------------------------------------- helpers

    def reply_from(self, rec):
        """Record a reply on this record's one contact, as `inbound` would."""
        events.record(rec, events.REPLY_RECEIVED,
                      contact_key=rec["contacts"][0]["key"], channel="email",
                      provider="emailbison",
                      provider_event_id=f"fixture:{rec['id']}")
        store.save(self.recs)

    def arm_provider(self, statuses):
        """`bison.membership` answers from `statuses`; a stop moves the lead.

        The named-leads form is what `leadstop.stop_contact` asks - one read
        per person, exact whatever page they are on - so it is the form the
        fake has to honour.
        """
        live = dict(statuses)

        def _membership(campaign_id, lead_ids=None):
            self.assertEqual(str(campaign_id), str(PROVIDER_CAMPAIGN))
            if lead_ids is None:
                return dict(live)
            return {int(i): live[int(i)] for i in lead_ids if int(i) in live}

        def _stop(campaign_id, lead_ids, **_kw):
            # THE SCOPE, READ FROM INSIDE THE ONE CALL IT EXISTS FOR.
            self.seen = {}
            for name, route in (
                    ("stop", f"/campaigns/{campaign_id}/leads/"
                             "stop-future-emails"),
                    ("attach", f"/campaigns/{campaign_id}/leads/attach-leads"),
                    ("pause", f"/campaigns/{campaign_id}/pause"),
                    ("resume", f"/campaigns/{campaign_id}/resume"),
                    ("create", "/campaigns"),
                    ("sequence", f"/campaigns/{campaign_id}/sequence-steps")):
                allowed, why = _providers.writes_allowed(
                    "https://send.example.test/api" + route)
                self.seen[name] = allowed
                self.seen[name + "_why"] = why
            for lead_id in lead_ids:
                live[int(lead_id)] = "stopped"
                self.stopped.append(int(lead_id))
            return {"stopped": True}

        bison.membership = _membership
        bison.stop_lead = _stop
        return live

    def check(self, statuses, live=False):
        self.arm_provider(statuses)
        return replyreconcile.check(
            PROVIDER_CAMPAIGN, membership=dict(statuses),
            recs=store.load(), rows=campaigns.load(), live=live)

    def notifications(self, kind):
        return [n for n in notify.load() if n.get("type") == kind]


class AReplierTheProviderStillHasInSequence(ReconcileTest):
    """FORWARD: our store says stop and the provider disagrees."""

    def test_the_disagreement_is_found(self):
        self.reply_from(self.recs[0])
        report = self.check({ACME_LEAD: "in_sequence",
                             BOREALIS_LEAD: "in_sequence"})
        found = report["forward"]["disagreements"]
        self.assertEqual([f["lead_id"] for f in found], [ACME_LEAD])
        self.assertEqual(found[0]["reason"], replyreconcile.REPLIED)
        self.assertEqual(found[0]["provider_status"], "in_sequence")
        self.assertEqual(report["forward"]["checked"], 1)

    def test_the_dry_run_stops_nobody(self):
        self.reply_from(self.recs[0])
        report = self.check({ACME_LEAD: "in_sequence"})
        self.assertTrue(report["forward"]["disagreements"])
        self.assertEqual(report["forward"]["stopped"], 0)
        self.assertEqual(self.stopped, [])

    def test_the_live_run_stops_exactly_that_one(self):
        self.reply_from(self.recs[0])
        report = self.check({ACME_LEAD: "in_sequence",
                             BOREALIS_LEAD: "in_sequence"}, live=True)
        self.assertEqual(self.stopped, [ACME_LEAD])
        self.assertEqual(report["forward"]["stopped"], 1)
        self.assertEqual(report["forward"]["failed"], [])
        self.assertTrue(report["forward"]["disagreements"][0]["stopped"])

    def test_the_stop_is_recorded_where_the_history_is(self):
        """`PROVIDER_STOP_CONFIRMED`, through `leadstop`'s own writer."""
        self.reply_from(self.recs[0])
        self.check({ACME_LEAD: "in_sequence"}, live=True)
        rec = next(r for r in store.load() if r["id"] == self.recs[0]["id"])
        kinds = [e["type"] for e in rec.get("events") or []]
        self.assertIn(events.PROVIDER_STOP_CONFIRMED, kinds)

    def test_a_lead_the_provider_already_stopped_is_not_a_disagreement(self):
        self.reply_from(self.recs[0])
        report = self.check({ACME_LEAD: "stopped"})
        self.assertEqual(report["forward"]["disagreements"], [])
        self.assertEqual(report["forward"]["already"], 1)

    def test_sending_paused_is_still_sendable(self):
        """A paused campaign's membership reverses the moment somebody
        resumes, so it is NOT a settled state - `bison.RESUMABLE_STATES`
        says so, and this is the reconciliation reading it."""
        self.reply_from(self.recs[0])
        report = self.check({ACME_LEAD: "sending_paused"})
        self.assertEqual(
            [f["lead_id"] for f in report["forward"]["disagreements"]],
            [ACME_LEAD])

    def test_a_status_nobody_has_seen_counts_as_sendable(self):
        """`queued_for_sending` appeared in this estate on 2026-09-24. An
        unrecognised status is not evidence of safety."""
        self.reply_from(self.recs[0])
        report = self.check({ACME_LEAD: "queued_for_sending"})
        self.assertTrue(report["forward"]["disagreements"])

    def test_a_lead_the_provider_does_not_hold_is_not_a_disagreement(self):
        """Absent from this campaign is not "sendable in this campaign"."""
        self.reply_from(self.recs[0])
        report = self.check({BOREALIS_LEAD: "in_sequence"})
        self.assertEqual(report["forward"]["disagreements"], [])

    def test_a_bounce_is_a_forward_reason_too(self):
        """`eligibility.must_not_contact` never returns a bounce - it is a
        fact about an ADDRESS - so `store_stop_reason` adds it. Without that
        a bounced address the provider still has in sequence would be sent
        the next step."""
        events.record(self.recs[0], events.EMAIL_BOUNCED,
                      contact_key=self.recs[0]["contacts"][0]["key"],
                      channel="email", provider="emailbison",
                      provider_event_id="fixture:bounce")
        store.save(self.recs)
        report = self.check({ACME_LEAD: "in_sequence"})
        found = report["forward"]["disagreements"]
        self.assertEqual([f["reason"] for f in found],
                         [replyreconcile.BOUNCED])

    def test_a_contact_with_no_reason_is_never_touched(self):
        report = self.check({ACME_LEAD: "in_sequence",
                             BOREALIS_LEAD: "in_sequence"}, live=True)
        self.assertEqual(report["forward"]["checked"], 0)
        self.assertEqual(self.stopped, [])


class TheScopeIsNarrowInTimeAndInPower(ReconcileTest):
    """The equivalent of the blank-content halt's scope test, one verb down.

    `_halt_on_blank_content` opens `allow_writes(only=PAUSE_ROUTES)` and its
    test asserts that scope does not reach `leads/attach-leads`. This asserts
    the same shape for `STOP_ROUTES`, and asserts it against every verb that
    could mean somebody receives MORE.
    """

    def setUp(self):
        super().setUp()
        self.reply_from(self.recs[0])
        self.seen = {}

    def test_the_stop_route_is_authorised(self):
        self.check({ACME_LEAD: "in_sequence"}, live=True)
        self.assertTrue(self.seen.get("stop"),
                        f"the stop was not authorised: {self.seen.get('stop_why')}")

    def test_the_scope_does_not_reach_attach_leads(self):
        self.check({ACME_LEAD: "in_sequence"}, live=True)
        self.assertFalse(self.seen.get("attach"),
                         "the stop's scope reached attach-leads: enrolling is "
                         "the one thing a reconciliation may never do")

    def test_the_scope_reaches_no_verb_that_can_send_more(self):
        """Resume, pause, create and sequence-write are all outside it.

        A resume starts sending, a create is the first step on the path that
        ends in one, and a sequence write changes the words that go out. A
        pause is out too - not because it is dangerous, but because this
        function's job is to stop ONE PERSON, and a scope that also pauses a
        campaign is a scope one refactor from halting an estate.
        """
        self.check({ACME_LEAD: "in_sequence"}, live=True)
        for verb in ("resume", "pause", "create", "sequence"):
            self.assertFalse(self.seen.get(verb),
                             f"the stop's scope reached {verb}")

    def test_the_scope_is_closed_before_and_after(self):
        """Narrow in TIME as well: nothing is authorised outside the call."""
        allowed_before, _ = _providers.writes_allowed(
            "https://send.example.test/api/campaigns/491/leads/"
            "stop-future-emails")
        self.assertFalse(allowed_before)
        self.check({ACME_LEAD: "in_sequence"}, live=True)
        allowed_after, _ = _providers.writes_allowed(
            "https://send.example.test/api/campaigns/491/leads/"
            "stop-future-emails")
        self.assertFalse(allowed_after,
                         "the reconciliation left a write scope open")

    def test_the_scope_names_a_route_fragment_not_a_whole_url(self):
        """A host change must not silently widen or void it."""
        for entry in replyreconcile.STOP_ROUTES:
            self.assertNotIn("://", entry)
            self.assertTrue(entry)
        scope = _providers.allow_writes("t", only=replyreconcile.STOP_ROUTES)
        self.assertTrue(scope.permits(
            "https://anything.test/api/campaigns/1/leads/stop-future-emails"))
        self.assertFalse(scope.permits(
            "https://anything.test/api/campaigns/1/leads/attach-leads"))


class TheProviderKnowsSomethingTheStoreDoesNot(ReconcileTest):
    """REVERSE: a reply or a bounce the store never ingested."""

    def test_a_provider_reply_with_no_store_event_is_written_back(self):
        report = self.check({ACME_LEAD: "replied"}, live=True)
        self.assertEqual(report["reverse"]["replied"], 1)
        self.assertEqual(report["reverse"]["written"], 1)
        rec = next(r for r in store.load() if r["id"] == self.recs[0]["id"])
        replies = [e for e in rec["events"] if events.is_reply(e)]
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].get("source"),
                         "provider_membership_reconcile")

    def test_the_written_reply_carries_no_words(self):
        """A membership status proves a reply happened and nothing else.

        It may not become something a classifier or a client channel could
        read as a positive reply with content behind it.
        """
        self.check({ACME_LEAD: "replied"}, live=True)
        rec = next(r for r in store.load() if r["id"] == self.recs[0]["id"])
        entry = next(e for e in rec["events"] if events.is_reply(e))
        for field in ("body", "text", "excerpt", "subject", "from", "email"):
            self.assertNotIn(field, entry)

    def test_a_bounce_is_written_back_as_a_bounce(self):
        self.check({BOREALIS_LEAD: "bounced"}, live=True)
        rec = next(r for r in store.load() if r["id"] == self.recs[1]["id"])
        self.assertIn(events.EMAIL_BOUNCED,
                      [e["type"] for e in rec["events"]])

    def test_a_second_cycle_writes_it_once(self):
        """Idempotent on `provider_event_id`, which is what makes a poll
        every five minutes for a week one row."""
        self.check({ACME_LEAD: "replied"}, live=True)
        second = self.check({ACME_LEAD: "replied"}, live=True)
        self.assertEqual(second["reverse"]["missing"], [])
        self.assertEqual(second["reverse"]["written"], 0)
        rec = next(r for r in store.load() if r["id"] == self.recs[0]["id"])
        self.assertEqual(len([e for e in rec["events"]
                              if events.is_reply(e)]), 1)

    def test_a_reply_the_store_already_holds_is_not_written_again(self):
        self.reply_from(self.recs[0])
        report = self.check({ACME_LEAD: "replied"}, live=True)
        self.assertEqual(report["reverse"]["replied"], 1)
        self.assertEqual(report["reverse"]["missing"], [])

    def test_the_dry_run_writes_nothing(self):
        report = self.check({ACME_LEAD: "replied"})
        self.assertEqual(len(report["reverse"]["missing"]), 1)
        self.assertEqual(report["reverse"]["written"], 0)
        rec = next(r for r in store.load() if r["id"] == self.recs[0]["id"])
        # `.get`, because a dry run leaves the record untouched - it does not
        # even acquire an empty `events` list. That is the assertion.
        self.assertEqual([e for e in rec.get("events") or []
                          if events.is_reply(e)], [])

    def test_a_lead_we_never_staged_is_counted_not_invented(self):
        report = self.check({FOREIGN_LEAD: "replied"}, live=True)
        self.assertEqual(report["reverse"]["replied"], 1)
        self.assertEqual(report["reverse"]["unmatched"], 1)
        self.assertEqual(report["reverse"]["written"], 0)

    def test_an_in_sequence_lead_writes_nothing(self):
        report = self.check({ACME_LEAD: "in_sequence"}, live=True)
        self.assertEqual(report["reverse"]["missing"], [])


class AnUnreadableMembershipIsNotACleanOne(ReconcileTest):
    """A false clean on the safety path is the failure this whole watcher
    exists to catch at the provider. It must not be reintroduced here."""

    def test_a_refused_membership_read_reconciles_nothing(self):
        def _boom(*_a, **_k):
            raise bison.ProviderError("provider 500")

        bison.membership = _boom
        report = replyreconcile.check(PROVIDER_CAMPAIGN, recs=store.load(),
                                      rows=campaigns.load(), live=True)
        self.assertIn("could not be read", report.get("refused") or "")
        self.assertEqual(report["forward"]["checked"], 0)
        self.assertEqual(self.stopped, [])

    def test_a_campaign_with_no_local_row_refuses(self):
        report = replyreconcile.check(999999, membership={},
                                      recs=store.load(), rows=campaigns.load())
        self.assertIn("no local campaign row", report.get("refused") or "")


class WhatIsSaidAboutIt(ReconcileTest):
    """The CRITICAL and the daily INFO line."""

    def setUp(self):
        super().setUp()
        self._channel = os.environ.get("SLACK_OPS_CHANNEL")
        os.environ["SLACK_OPS_CHANNEL"] = "C-TEST-OPS"
        self.addCleanup(self._restore_channel)

    def _restore_channel(self):
        if self._channel is None:
            os.environ.pop("SLACK_OPS_CHANNEL", None)
        else:
            os.environ["SLACK_OPS_CHANNEL"] = self._channel

    def test_a_replier_found_sendable_is_critical(self):
        self.reply_from(self.recs[0])
        report = self.check({ACME_LEAD: "in_sequence"})
        replyreconcile.announce(report)
        raised = self.notifications(notify.REPLY_PROTECTION_FAILED)
        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0]["severity"], notify.CRITICAL)
        self.assertEqual(raised[0]["payload"]["stopped_by_reconciliation"],
                         "NO")

    def test_a_stopped_replier_still_raises_the_critical(self):
        """The alert is on DISCOVERY and carries whether the stop landed.

        The blank-content halt settled this: a repair that succeeds must not
        swallow the finding, because the finding is that a replier was
        sendable at all.
        """
        self.reply_from(self.recs[0])
        report = self.check({ACME_LEAD: "in_sequence"}, live=True)
        replyreconcile.announce(report)
        raised = self.notifications(notify.REPLY_PROTECTION_FAILED)
        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0]["payload"]["stopped_by_reconciliation"],
                         "yes")

    def test_a_bounce_disagreement_is_not_a_reply_critical(self):
        events.record(self.recs[0], events.EMAIL_BOUNCED,
                      contact_key=self.recs[0]["contacts"][0]["key"],
                      channel="email", provider="emailbison",
                      provider_event_id="fixture:bounce2")
        store.save(self.recs)
        report = self.check({ACME_LEAD: "in_sequence"})
        replyreconcile.announce(report)
        self.assertEqual(self.notifications(notify.REPLY_PROTECTION_FAILED), [])

    def test_the_counts_go_to_the_status_feed_at_info(self):
        report = self.check({ACME_LEAD: "replied"})
        replyreconcile.announce(report)
        posted = self.notifications(notify.STATUS_CHECKPOINT)
        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0]["destination"], notify.STATUS)
        self.assertEqual(posted[0]["severity"], notify.INFO)
        self.assertEqual(posted[0]["payload"]["provider_replied"], 1)
        self.assertEqual(posted[0]["payload"]["events_missing_from_store"], 1)

    def test_an_unchanged_cycle_does_not_post_a_second_line(self):
        """Silence means unchanged. Nine campaigns at 300s would otherwise be
        2,592 identical lines a day, and a feed nobody reads is a feed the
        CRITICAL is lost in."""
        for _ in range(3):
            replyreconcile.announce(self.check({ACME_LEAD: "in_sequence"}))
        self.assertEqual(len(self.notifications(notify.STATUS_CHECKPOINT)), 1)

    def test_a_changed_picture_posts_a_new_line(self):
        replyreconcile.announce(self.check({ACME_LEAD: "in_sequence"}))
        self.reply_from(self.recs[0])
        replyreconcile.announce(self.check({ACME_LEAD: "in_sequence"}))
        self.assertEqual(len(self.notifications(notify.STATUS_CHECKPOINT)), 2)

    def test_nothing_posted_names_a_person(self):
        """`notify._status_payload` REFUSES rather than stripping, so a field
        added carelessly fails here rather than reaching the channel with the
        widest audience in the product."""
        self.reply_from(self.recs[0])
        replyreconcile.announce(self.check({ACME_LEAD: "in_sequence"},
                                           live=True))
        for row in notify.load():
            self.assertNotEqual(row["status"], notify.FAILED)
            for value in row["payload"].values():
                self.assertNotIn("@", str(value))
                for rec in self.recs:
                    self.assertNotIn(rec["contacts"][0]["key"], str(value))

    def test_the_line_carries_ids_and_counts_only(self):
        self.reply_from(self.recs[0])
        line = replyreconcile.line(self.check({ACME_LEAD: "in_sequence"}))
        self.assertIn(str(PROVIDER_CAMPAIGN), line)
        for rec in self.recs:
            self.assertNotIn(rec["contacts"][0]["key"], line)


class TheWatcherCarriesTheCheck(ReconcileTest):
    """It is wired into the loop, on the roster the loop already paid for."""

    def test_the_loop_exposes_it(self):
        module = _watch_loop()
        self.assertTrue(callable(module._reconcile_replies))

    def test_it_runs_on_the_membership_snapshot_already_read(self):
        module = _watch_loop()
        self.reply_from(self.recs[0])
        self.arm_provider({ACME_LEAD: "in_sequence"})
        lines = []
        report = module._reconcile_replies(
            PROVIDER_CAMPAIGN,
            {"membership_rows": {ACME_LEAD: "in_sequence"}}, lines.append)
        self.assertEqual(self.stopped, [ACME_LEAD])
        self.assertEqual(report["forward"]["stopped"], 1)
        self.assertTrue(any("RECONCILE-FORWARD" in l for l in lines))

    def test_an_unreadable_membership_does_not_reconcile(self):
        module = _watch_loop()
        self.reply_from(self.recs[0])
        self.arm_provider({ACME_LEAD: "in_sequence"})
        self.assertIsNone(module._reconcile_replies(
            PROVIDER_CAMPAIGN, {"membership_rows": None}, lambda _l: None))
        self.assertEqual(self.stopped, [])

    def test_the_counts_survive_a_split_walk(self):
        """`_membership_states` counts the rows `_membership_rows` read.

        They were one function; splitting them is what lets the walk be paid
        for once. A count taken from a different read is a second reader.
        """
        module = _watch_loop()
        self.assertIsNone(module._membership_states(None))
        self.assertEqual(
            module._membership_states({1: "in_sequence", 2: "in_sequence",
                                       3: "stopped"}),
            {"in_sequence": 2, "stopped": 1})

    def test_the_snapshot_carries_the_roster_and_counts_it_once(self):
        """One walk answers both questions, and they cannot disagree."""
        module = _watch_loop()
        rows = {ACME_LEAD: "in_sequence", BOREALIS_LEAD: "stopped"}
        real = (bison.campaign, bison.scheduled_emails, bison.sending_schedule)
        bison.campaign = lambda _cid: {"status": "active", "total_leads": 2}
        bison.scheduled_emails = lambda *_a, **_k: []
        bison.sending_schedule = lambda *_a, **_k: {"emails_being_sent": 0}
        self.arm_provider(rows)
        try:
            state = module.snapshot(PROVIDER_CAMPAIGN)
        finally:
            (bison.campaign, bison.scheduled_emails,
             bison.sending_schedule) = real
        self.assertEqual(state["membership_rows"], rows)
        self.assertEqual(state["membership"], {"in_sequence": 1, "stopped": 1})


if __name__ == "__main__":
    unittest.main()
