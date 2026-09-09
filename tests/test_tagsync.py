"""What the providers should be told, and the fact that nothing tells them.

Three properties, and they are the reason this is an outbox and not a call:

**Canonical state is upstream.** A tag is a copy of a conclusion. Nothing
here can change what Resonate believes, and a provider failure delays a
label in somebody else's UI rather than losing a suppression.

**Desired state, not instructions.** A row says what should be true, keyed by
(workspace, record, contact, provider). Re-ingesting the same reply
recomputes the same row, so there is no second operation to deduplicate.

**Nothing sends.** No tag endpoint on either provider has been validated.
`send()` refuses out loud rather than silently doing nothing.
"""
import unittest

from src import accountpolicy as ap, events, store, tagsync
from tests.campaignbase import CampaignTest

WS = "productive"
JOHN, SARAH, MIKE = "john", "sarah", "mike"


class TagTest(CampaignTest):

    def record(self, rid="tag-acme"):
        rec = store.new_record(rid, "domains", WS, "Acme Ltd", "acme.test")
        rec["contacts"] = [
            # Email only: EmailBison can name them, HeyReach cannot.
            {"key": JOHN, "name": "John Smith", "email": "john@acme.test",
             "selected": True},
            # Both channels.
            {"key": SARAH, "name": "Sarah Jones", "email": "sarah@acme.test",
             "linkedin": "https://www.linkedin.com/in/sarah-jones/",
             "selected": True},
            # Neither. Nothing can be tagged for them anywhere.
            {"key": MIKE, "name": "Michael Green", "selected": True},
        ]
        store.save([rec])
        return rec

    def reply(self, rec, key=JOHN, outcome=ap.POSITIVE,
              at="2026-08-05T09:00:00+00:00"):
        events.record(rec, events.REPLY_RECEIVED, contact_key=key,
                      channel="email", at=at,
                      provider_event_id=f"r-{rec['id']}-{key}")
        events.record(rec, events.REPLY_CLASSIFIED, contact_key=key,
                      channel="email", at=at, classification=outcome,
                      provider_event_id=f"r-{rec['id']}-{key}:c")
        if outcome == ap.POSITIVE:
            events.record(rec, events.POSITIVE_REPLY_DETECTED, contact_key=key,
                          channel="email", at=at,
                          provider_event_id=f"r-{rec['id']}-{key}:p")
        return ap.apply_reply(rec, key, outcome, at=at, channel="email",
                              workspace=WS)

    def rows(self, provider=None):
        """Only this test's record. The shared fixture seeds others."""
        out = [r for r in tagsync.load().values()
               if r["record_id"] == "tag-acme"]
        return [r for r in out if provider is None or r["provider"] == provider]


class EveryOutcomeHasTags(TagTest):

    def test_every_canonical_outcome_maps_to_tags_and_a_stage(self):
        for outcome in ap.OUTCOMES:
            self.assertIn(outcome, tagsync.OUTCOME_TAGS, outcome)
            self.assertIn(outcome, tagsync.STAGE_OF, outcome)
            for tag in tagsync.OUTCOME_TAGS[outcome]:
                self.assertIn(tag, tagsync.TAGS, tag)
            self.assertIn(tagsync.STAGE_OF[outcome], tagsync.TAGS, outcome)

    def test_every_tag_is_namespaced(self):
        """A bare `positive` would collide with the client's own sequences."""
        for tag in tagsync.TAGS:
            self.assertTrue(tag.startswith(tagsync.PREFIX), tag)

    def test_the_stage_is_one_of_the_tags_the_outcome_asserts(self):
        for outcome in ap.OUTCOMES:
            self.assertIn(tagsync.STAGE_OF[outcome],
                          tagsync.OUTCOME_TAGS[outcome], outcome)

    def test_a_removal_request_always_carries_the_dnc_tag(self):
        for outcome in (ap.UNSUBSCRIBE, ap.ACCOUNT_DNC):
            self.assertIn(tagsync.DNC, tagsync.OUTCOME_TAGS[outcome], outcome)

    def test_the_desired_state_uses_the_outcome_that_was_applied(self):
        """Re-deriving from the log would read the unclassified receipt."""
        rec = self.record()
        events.record(rec, events.REPLY_RECEIVED, contact_key=JOHN,
                      channel="email", provider_event_id="raw")
        want = tagsync.desired(rec, JOHN, outcome=ap.UNSUBSCRIBE)
        self.assertEqual(want["stage"], tagsync.DNC)
        self.assertNotEqual(want["stage"], tagsync.REVIEW)


class IdentityIsProvedOrNothingIsTagged(TagTest):

    def test_emailbison_names_a_lead_by_mailbox(self):
        rec = self.record()
        where = tagsync.target(rec["contacts"][0], tagsync.EMAILBISON)
        self.assertEqual(where, {"by": "email", "value": "john@acme.test"})

    def test_heyreach_names_a_lead_by_canonical_profile(self):
        rec = self.record()
        where = tagsync.target(rec["contacts"][1], tagsync.HEYREACH)
        self.assertEqual(where["by"], "linkedin_url")
        self.assertEqual(where["value"],
                         "https://www.linkedin.com/in/sarah-jones")

    def test_a_provider_lead_id_wins_over_a_derived_identifier(self):
        contact = {"email": "x@y.test", "bison_lead_id": 4210}
        where = tagsync.target(contact, tagsync.EMAILBISON)
        self.assertEqual(where, {"by": "provider_lead_id", "value": "4210"})

    def test_a_name_and_a_company_can_never_name_a_lead(self):
        """No fuzzy provider tagging, anywhere, ever."""
        contact = {"name": "John Smith", "company": "Acme Ltd"}
        for provider in tagsync.PROVIDERS:
            self.assertIsNone(tagsync.target(contact, provider), provider)

    def test_a_contact_we_cannot_name_is_blocked_not_pending(self):
        rec = self.record()
        self.reply(rec, MIKE, ap.NEGATIVE)
        for row in self.rows():
            if row["contact_key"] == MIKE:
                self.assertEqual(row["status"], tagsync.BLOCKED)
                self.assertIn("no authoritative", row["why"])

    def test_blocked_rows_are_never_retried(self):
        rec = self.record()
        self.reply(rec, MIKE, ap.NEGATIVE)
        owed = [r for r in tagsync.pending() if r["contact_key"] == MIKE]
        self.assertEqual(owed, [])


class TheOutboxIsIdempotent(TagTest):

    def test_one_reply_queues_one_row_per_provider(self):
        rec = self.record()
        self.reply(rec, SARAH, ap.POSITIVE)
        rows = [r for r in self.rows() if r["contact_key"] == SARAH]
        self.assertEqual(sorted(r["provider"] for r in rows),
                         [tagsync.EMAILBISON, tagsync.HEYREACH])

    def test_the_same_reply_applied_twice_queues_nothing_new(self):
        rec = self.record()
        self.reply(rec, SARAH, ap.POSITIVE)
        before = len(tagsync.load())
        written = tagsync.enqueue(rec, SARAH, WS, outcome=ap.POSITIVE)
        self.assertEqual(written, [])
        self.assertEqual(len(tagsync.load()), before)

    def test_a_changed_outcome_does_queue_a_new_desired_state(self):
        """`not now` in March, `remove me` in June. The stage moves."""
        rec = self.record()
        tagsync.enqueue(rec, SARAH, WS, outcome=ap.NOT_NOW)
        first = tagsync.load()[f"{WS}|tag-acme|{SARAH}|{tagsync.EMAILBISON}"]
        self.assertEqual(first["stage"], tagsync.FOLLOW_UP)

        tagsync.enqueue(rec, SARAH, WS, outcome=ap.UNSUBSCRIBE)
        second = tagsync.load()[f"{WS}|tag-acme|{SARAH}|{tagsync.EMAILBISON}"]
        self.assertEqual(second["stage"], tagsync.DNC)
        self.assertIn(tagsync.DNC, second["tags"])

    def test_the_key_is_workspace_record_contact_provider(self):
        row = {"workspace": WS, "record_id": "acme", "contact_key": JOHN,
               "provider": tagsync.EMAILBISON}
        self.assertEqual(tagsync.key_of(row),
                         f"{WS}|acme|{JOHN}|{tagsync.EMAILBISON}")

    def test_a_replayed_provider_event_moves_the_outbox_once(self):
        rec = self.record()
        event = {"type": events.REPLY_RECEIVED, "record_id": rec["id"],
                 "contact_key": SARAH, "channel": "email",
                 "provider_event_id": "same"}
        events.apply([rec], event)
        first = len(tagsync.load())
        events.apply([rec], dict(event))
        self.assertEqual(len(tagsync.load()), first)


class FailureIsRecordedNotLost(TagTest):

    def queued(self, rec):
        self.reply(rec, SARAH, ap.POSITIVE)
        return [r for r in tagsync.pending()
                if r["provider"] == tagsync.EMAILBISON][0]

    def test_a_failed_attempt_keeps_the_row_owed(self):
        rec = self.record()
        row = self.queued(rec)
        tagsync.record_attempt(row, ok=False, error="502 from provider")
        owed = [r for r in tagsync.pending() if r["contact_key"] == SARAH]
        self.assertTrue(owed)
        self.assertEqual(owed[0]["status"], tagsync.FAILED)
        self.assertEqual(owed[0]["attempts"], 1)
        self.assertIn("502", owed[0]["last_error"])

    def test_a_successful_attempt_clears_it(self):
        rec = self.record()
        row = self.queued(rec)
        tagsync.record_attempt(row, ok=True)
        owed = [r for r in tagsync.pending()
                if r["contact_key"] == SARAH
                and r["provider"] == tagsync.EMAILBISON]
        self.assertEqual(owed, [])

    def test_a_provider_failure_does_not_touch_canonical_state(self):
        """The property the whole outbox exists for."""
        rec = self.record()
        row = self.queued(rec)
        tagsync.record_attempt(row, ok=False, error="boom")
        self.assertEqual(ap.account_state(rec)[0], ap.HOLD)
        self.assertEqual(
            ap.contact_state(rec["contacts"][1])[0], ap.HOLD)

    def test_one_provider_failing_does_not_affect_the_other(self):
        rec = self.record()
        self.reply(rec, SARAH, ap.POSITIVE)
        bison = [r for r in tagsync.pending()
                 if r["provider"] == tagsync.EMAILBISON][0]
        tagsync.record_attempt(bison, ok=False, error="boom")
        heyreach = [r for r in tagsync.pending()
                    if r["provider"] == tagsync.HEYREACH]
        self.assertTrue(heyreach)
        self.assertEqual(heyreach[0]["status"], tagsync.PENDING)


class ReplyIngestionDoesNotDependOnTagging(TagTest):

    def test_an_outbox_failure_cannot_unwind_the_reply(self):
        import src.tagsync as module

        original = module.enqueue

        def boom(*a, **kw):
            raise RuntimeError("disk full")

        module.enqueue = boom
        try:
            rec = self.record()
            moved = self.reply(rec, SARAH, ap.ACCOUNT_DNC)
        finally:
            module.enqueue = original

        self.assertIsNone(moved["tags"], "a tag failure was reported as done")
        self.assertEqual(ap.account_state(rec)[0], ap.SUPPRESS,
                         "an outbox failure unwound a suppression")

    def test_the_tag_step_runs_after_every_state_transition(self):
        rec = self.record()
        moved = self.reply(rec, SARAH, ap.ACCOUNT_DNC)
        self.assertIn("account_suppressed", moved["changed"])
        self.assertEqual(sorted(moved["tags"]),
                         [tagsync.EMAILBISON, tagsync.HEYREACH])


class NothingSends(TagTest):

    def test_send_refuses(self):
        with self.assertRaises(tagsync.TagSyncRefused):
            tagsync.send({"provider": tagsync.EMAILBISON}, live=True)

    def test_every_adapter_marks_itself_unvalidated(self):
        rec = self.record()
        self.reply(rec, SARAH, ap.POSITIVE)
        for request in tagsync.preview(tagsync.pending()):
            if "skipped" in request:
                continue
            self.assertIs(request["validated"], False, request["provider"])

    def test_the_preview_says_what_would_be_sent_and_sends_nothing(self):
        rec = self.record()
        self.reply(rec, SARAH, ap.POSITIVE)
        requests = tagsync.preview(tagsync.pending())
        self.assertTrue(requests)
        for request in requests:
            if "skipped" in request:
                continue
            self.assertIn(tagsync.POSITIVE, request["body"]["tags"])
            self.assertIn("identify", request)

    def test_a_blocked_row_previews_as_skipped_with_its_reason(self):
        rec = self.record()
        self.reply(rec, JOHN, ap.POSITIVE)          # email only
        rows = [r for r in tagsync.load().values()
                if r["contact_key"] == JOHN
                and r["provider"] == tagsync.HEYREACH]
        preview = tagsync.preview(rows)
        self.assertIn("skipped", preview[0])


class TenancyTravelsWithEveryRow(TagTest):

    def test_every_row_names_its_workspace(self):
        rec = self.record()
        self.reply(rec, SARAH, ap.POSITIVE)
        for row in self.rows():
            self.assertEqual(row["workspace"], WS)

    def test_two_workspaces_do_not_share_a_key(self):
        left = {"workspace": "a", "record_id": "r", "contact_key": "c",
                "provider": tagsync.EMAILBISON}
        right = dict(left, workspace="b")
        self.assertNotEqual(tagsync.key_of(left), tagsync.key_of(right))


if __name__ == "__main__":
    unittest.main()
