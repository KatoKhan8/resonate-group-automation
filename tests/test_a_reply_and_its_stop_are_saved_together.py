"""A stop written mid-ingest used to discard the reply that caused it.

PROBLEM-REGISTER ISSUE-001, reproduced here before being fixed.

`inbound.ingest` reads `base = store.digest()`, builds its records, then calls
`store.save(recs, expect_digest=base)` - which REFUSES with `QueueChanged` if
the queue changed in between. `leadstop._record` was reached from inside that
window and opened its own `store.transaction()`. `store.digest()` is a CONTENT
HASH over the queue file, so that nested commit changed the digest and the
outer save refused.

What was lost is narrower than first reported and it is the wrong half:

  the PROVIDER_STOP_CONFIRMED event SURVIVED - `_record`'s own transaction
  committed it

  ingest's own work was DISCARDED - the REPLY_RECEIVED event, its
  classification, and the account pause

So the system ended a poll interval knowing it had stopped somebody and not
knowing they had replied. `eligibility._replied` and `_paused` both answer
from the record, so they answered clean about a person who had just written
back.

## Why it could not be fixed by deleting the transaction

GLM raised this in review and it is the whole design constraint: **two of the
three callers have no save of their own.** `leadstop.sweep` and the
`leadstop` CLI reach `_record` outside any ingest window, and there that
commit is the only write that happens. Removing it would have silently
dropped every stop those two paths record.

So the caller declares who owns the save. These tests pin both halves: ingest
owns it and passes `persist=False`, and the sweep does not and keeps its
independent commit.

## Why this had never fired in production

`_record` is reached only AFTER a real provider stop has SUCCEEDED
(`report["stopped"] = True` is set immediately above the call). It needs a
reply, matched to a record, that triggers a provider stop, that succeeds.
Zero replies had arrived on any live campaign. Critical by construction,
latent in fact - it would have fired on the first reply that stopped someone,
which is the most valuable event this system can receive.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import events, inbound, leadstop, store  # noqa: E402


def payload(email="pat@acme.test", event_id="u1"):
    return {"data": [{"id": "reply-1", "uuid": event_id, "type": "reply",
                      "folder": "inbox", "from_email_address": email,
                      "date_received": "2026-09-09T10:00:00Z",
                      "text_body": "please remove us from your list"}]}


class ReplyAndStopTest(unittest.TestCase):

    def setUp(self):
        self._env = {k: os.environ.get(k)
                     for k in ("QUEUE", "OUT") + store.STATE_OVERRIDES}
        self.addCleanup(self._restore)
        store.use_directory(os.path.join(tempfile.mkdtemp(prefix="rga-i1-"),
                                         "work"))
        rec = store.new_record("r1", "domains", "productive", "Acme",
                               "acme.test")
        # `bison_lead_id` is what makes `_stop_at_provider` try at all.
        rec["contacts"] = [{"key": "pat", "name": "Pat Lee",
                            "email": "pat@acme.test",
                            "bison_lead_id": 42}]
        with store.transaction() as rows:
            rows.append(rec)

    def _restore(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def events_of(self, kind, rid="r1"):
        return [e for e in (store.get(rid).get("events") or [])
                if e.get("type") == kind]

    def stopping_ingest(self, persist):
        """Ingest one reply while a stop is recorded, at a chosen persistence.

        The provider transport is never reached: `stop_contact` is replaced
        by a stand-in that records the stop exactly as the real one does and
        nothing else, so the test is about WHO SAVES and not about HeyReach
        or EmailBison.
        """
        report = {"record": "r1", "contact": "pat", "lead_id": 42,
                  "campaign": "c1", "provider_campaign": "487",
                  "why": events.REPLY_RECEIVED, "live": True,
                  "already": False, "stopped": True,
                  "status_after": "stopped"}

        def fake_stop(rec, contact, why, **kw):
            leadstop._record(rec, contact, report, persist=persist)
            return dict(report)

        with mock.patch.object(leadstop, "stop_contact", fake_stop):
            return inbound.ingest(payload(), "emailbison")


class TheReplySurvivesTheStopItCaused(ReplyAndStopTest):

    def test_both_the_reply_and_the_stop_are_persisted(self):
        """The acceptance criterion from the register."""
        self.stopping_ingest(persist=False)
        self.assertEqual(
            1, len(self.events_of("reply_received")),
            "the reply that caused the stop was discarded")
        self.assertEqual(
            1, len(self.events_of(events.PROVIDER_STOP_CONFIRMED)),
            "the stop was not recorded")

    def test_ingest_does_not_raise(self):
        """It refused loudly rather than silently - no try/except around
        `store.save` - so the caller saw QueueChanged and the poll failed."""
        try:
            self.stopping_ingest(persist=False)
        except store.QueueChanged as exc:      # pragma: no cover - the defect
            self.fail(f"ingest still refuses its own save: {exc}")

    def test_the_old_behaviour_is_what_it_looked_like(self):
        """The defect, reproduced. Kept so the fix cannot be quietly undone:
        with the nested commit back, ingest's own save refuses and the reply
        is gone while the stop remains."""
        with self.assertRaises(store.QueueChanged):
            self.stopping_ingest(persist=True)
        self.assertEqual([], self.events_of("reply_received"),
                         "the reply should have been lost under the defect")
        self.assertEqual(
            1, len(self.events_of(events.PROVIDER_STOP_CONFIRMED)),
            "the stop should have survived under the defect - that asymmetry "
            "is the finding")


class TheCallersThatOwnNoSaveKeepTheirCommit(ReplyAndStopTest):
    """GLM's objection, pinned. `sweep` and the CLI must keep persisting."""

    def test_persist_defaults_to_true(self):
        import inspect
        for fn in (leadstop.stop_contact, leadstop.stop_linkedin_contact,
                   leadstop._record, leadstop._record_linkedin):
            with self.subTest(function=fn.__name__):
                self.assertIs(
                    True, inspect.signature(fn).parameters["persist"].default,
                    "a caller that owns no save must keep the commit by "
                    "default")

    def test_a_default_record_writes_to_the_file_on_its_own(self):
        report = {"record": "r1", "contact": "pat", "lead_id": 42,
                  "campaign": "c1", "provider_campaign": "487",
                  "why": "dnc", "status_after": "stopped"}
        rec = store.get("r1")
        leadstop._record(rec, {"key": "pat"}, report)
        self.assertEqual(
            1, len(self.events_of(events.PROVIDER_STOP_CONFIRMED)),
            "sweep and the CLI rely on this commit; nothing else saves for "
            "them")

    def test_persist_false_does_not_write_the_file_by_itself(self):
        """The other half: it mutates the record it was handed and leaves
        the file alone, so the caller's single save is what lands it."""
        report = {"record": "r1", "contact": "pat", "lead_id": 42,
                  "campaign": "c1", "provider_campaign": "487",
                  "why": "dnc", "status_after": "stopped"}
        rec = store.get("r1")
        leadstop._record(rec, {"key": "pat"}, report, persist=False)
        self.assertEqual([], self.events_of(events.PROVIDER_STOP_CONFIRMED),
                         "persist=False must not write the queue itself")
        self.assertEqual(
            1, len([e for e in (rec.get("events") or [])
                    if e.get("type") == events.PROVIDER_STOP_CONFIRMED]),
            "the event belongs on the in-memory record the caller holds")


class TheTwoChannelsRecordTheSameWay(ReplyAndStopTest):
    """One writer for both, so the email and LinkedIn paths cannot drift in
    what they record or in how they key idempotency."""

    def test_both_recorders_key_idempotency_on_the_provider_event_id(self):
        report = {"record": "r1", "contact": "pat", "lead_id": 42,
                  "campaign": "c1", "provider_campaign": "487",
                  "why": "dnc", "status_after": "stopped"}
        rec = store.get("r1")
        leadstop._record(rec, {"key": "pat"}, report, persist=False)
        leadstop._record_linkedin(rec, {"key": "pat"}, report, persist=False)
        ids = [e.get("provider_event_id") for e in (rec.get("events") or [])
               if e.get("type") == events.PROVIDER_STOP_CONFIRMED]
        self.assertIn("emailbison:stop:487:42", ids)
        self.assertIn("heyreach:stop:487:42", ids)

    def test_recording_the_same_stop_twice_is_a_no_op(self):
        report = {"record": "r1", "contact": "pat", "lead_id": 42,
                  "campaign": "c1", "provider_campaign": "487",
                  "why": "dnc", "status_after": "stopped"}
        rec = store.get("r1")
        leadstop._record(rec, {"key": "pat"}, report, persist=False)
        leadstop._record(rec, {"key": "pat"}, report, persist=False)
        stops = [e for e in (rec.get("events") or [])
                 if e.get("type") == events.PROVIDER_STOP_CONFIRMED]
        self.assertEqual(1, len(stops),
                         "a re-run or a sweep crossing a reply must not "
                         "append a second identical stop")


if __name__ == "__main__":
    unittest.main()
