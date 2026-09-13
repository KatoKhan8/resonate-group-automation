"""A reply was written into a client's record with no trace of where it came from.

An EmailBison credential's workspace is chosen in the vendor's UI, not by us. It
has moved mid-session: over three days one key answered for four different
estates while nothing changed on this side. The poller reads replies, and
`inbound.ingest` applies them to `work/queue.jsonl` - so a reply polled while the
credential was bound to the wrong workspace paused this client's account,
classified the reply, fired a positive-reply alert and was counted in
client-facing reporting.

The event log is append-only, so that claim could not be retracted. Worse, it
could not even be IDENTIFIED afterwards: nothing on the stored event said which
estate produced it. `events.record` stored `provider` and never a workspace.

So the estate travels onto the event. This is provenance, not enforcement - the
refusal belongs at the poll, where `expect` now defaults to the deployment's pin.
What this buys is the ability to answer, a day later, which estate said this.

The distinction the last class asserts matters: `reply_received` is the
PROVIDER'S claim and carries the estate. `company_paused` and
`reply_classified` are OUR decisions about that claim, and stamping an estate on
them would attribute our own reasoning to a provider.
"""
import os
import sys
import tempfile
import unittest

from src import adapters, events, inbound, store


def payload(email="pat@acme.test", event_id="u1"):
    return {"data": [{"id": "reply-1", "uuid": event_id, "type": "reply",
                      "folder": "inbox", "from_email_address": email,
                      "date_received": "2026-09-09T10:00:00Z",
                      "text_body": "sure, tell me more"}]}


class ReplyTest(unittest.TestCase):
    def setUp(self):
        # `use_directory` sets QUEUE and clears every STATE_OVERRIDE for the
        # whole process, so a test that does not put them back hands its temp
        # directory to whatever runs next. That is not cosmetic: it silently
        # disarmed `TestTheBarrierCoversEveryWriter`, whose `spendledger` case
        # resolves its path from `store.queue_path()` and so was writing to
        # this leaked temp directory instead of being refused. The barrier
        # test passed alone and failed only in a full run, which is exactly
        # the shape of a guard that has stopped guarding.
        self._env = {k: os.environ.get(k)
                     for k in ("QUEUE", "OUT") + store.STATE_OVERRIDES}
        self.addCleanup(self._restore_environment)
        store.use_directory(os.path.join(tempfile.mkdtemp(prefix="rga-ws-"),
                                         "work"))
        rec = store.new_record("r1", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [{"key": "pat", "name": "Pat Lee",
                            "email": "pat@acme.test"}]
        with store.transaction() as rows:
            rows.append(rec)


    def _restore_environment(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def stored(self, kind="reply_received", rid="r1"):
        return [e for e in (store.get(rid).get("events") or [])
                if e.get("type") == kind]


class TheEstateTravelsOntoTheEvent(ReplyTest):
    def test_the_reply_event_names_the_workspace_it_was_read_from(self):
        inbound.ingest(payload(), "emailbison", provider_workspace=10)
        found = self.stored()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["provider_workspace"], 10)

    def test_a_reply_read_from_another_estate_is_identifiable_afterwards(self):
        """The whole point. The claim still lands - refusing is the poller's
        job - but it can now be found and discarded by hand."""
        inbound.ingest(payload(), "emailbison", provider_workspace=29)
        self.assertEqual(self.stored()[0]["provider_workspace"], 29)

    def test_the_estate_is_stamped_by_the_caller_not_by_the_adapter(self):
        """The estate is a property of the CREDENTIAL that did the reading, and
        an adapter is a pure translation that was never told which key fetched
        its input."""
        neutral = adapters.from_emailbison(payload())
        self.assertEqual(len(neutral), 1)
        self.assertIsNone(neutral[0].get("provider_workspace"))

    def test_an_unstamped_ingest_invents_nothing(self):
        """A default would assert an ownership this code cannot prove, which is
        `bison.require_workspace`'s own rule."""
        inbound.ingest(payload(), "emailbison")
        self.assertIsNone(self.stored()[0].get("provider_workspace"))

    def test_a_supplied_estate_does_not_overwrite_one_already_on_the_event(self):
        """`setdefault`, so a source that genuinely knows its own estate keeps
        it rather than being relabelled by the caller."""
        rows = adapters.from_emailbison(payload())
        rows[0]["provider_workspace"] = 3
        outcomes = [inbound.handle(e, store.load()) for e in rows]
        self.assertEqual((outcomes[0]["applied"] or {}).get("status"), "applied")


class OnlyTheProvidersClaimCarriesAnEstate(ReplyTest):
    """Our own decisions must not be attributed to a provider."""

    def setUp(self):
        super().setUp()
        inbound.ingest(payload(), "emailbison", provider_workspace=10)

    def test_the_providers_claim_carries_it(self):
        self.assertEqual(self.stored("reply_received")[0]["provider_workspace"],
                         10)

    def test_our_decisions_do_not(self):
        for kind in ("company_paused", "contact_held", "review_required"):
            with self.subTest(kind=kind):
                for entry in self.stored(kind):
                    self.assertIsNone(entry.get("provider_workspace"),
                                      f"{kind} claims a provider estate")

    def test_the_pause_still_happens(self):
        """Provenance must not have changed the safety behaviour."""
        self.assertTrue(store.get("r1").get("paused"))


class ItSurvivesTheThingsThatUsedToLoseIt(ReplyTest):
    def test_it_survives_a_reload_from_disk(self):
        inbound.ingest(payload(), "emailbison", provider_workspace=10)
        again = [e for e in (store.get("r1").get("events") or [])
                 if e.get("type") == "reply_received"]
        self.assertEqual(again[0]["provider_workspace"], 10)

    def test_a_duplicate_delivery_does_not_relabel_the_original(self):
        """Idempotent on the provider's own id, so the second delivery changes
        nothing - including the estate recorded on the first."""
        inbound.ingest(payload(), "emailbison", provider_workspace=10)
        inbound.ingest(payload(), "emailbison", provider_workspace=29)
        found = self.stored()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["provider_workspace"], 10)


if __name__ == "__main__":
    unittest.main()
