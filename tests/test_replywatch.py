"""Reply protection has to run without being asked, and say when it isn't.

`poller` was correct and unscheduled, which meant the guarantee in
`ACCOUNT-OUTREACH.md` - a confirmed reply stops that lead on both channels -
held only as often as somebody typed the command. These cover the scheduler
that closes that gap, and the properties that make an automatic poll safe
rather than merely convenient:

  it is off unless asked for, and refuses rather than looping when it cannot
  reach a provider; one provider failing neither stops the other nor moves
  its own checkpoint; two pollers cannot run at once; and running twice has
  no second effect on canonical truth.

Classification, suppression and account policy are not re-tested here - they
have their own suites. What is tested is that driving them from a timer
changes none of it.
"""
import os
import unittest

from tests import base
from tests.campaignbase import CampaignTest
from src import poller, replywatch, store
from src.providers import bison


def reply_row(ident, stamp, sender, text="Happy to chat.",
              kind="Tracked Reply", folder="Inbox", record="acme",
              contact="acme-champ", client="demo"):
    variables = {"record_id": record, "contact_key": contact}
    if client is not None:
        variables["client"] = client
    return {"id": ident, "uuid": f"uuid-{ident}", "type": kind,
            "folder": folder, "from_email_address": sender,
            "created_at": stamp, "date_received": stamp[:10],
            "text_body": text, "automated_reply": False,
            "custom_variables": variables}


def move_to_workspace(slug, record_id="acme"):
    recs = store.load()
    for rec in recs:
        if rec["id"] == record_id:
            rec["client"] = slug
    store.save(recs)


class Gating(unittest.TestCase):
    """A background thread that reaches a provider must be asked for."""

    def test_it_is_off_unless_the_environment_asks(self):
        self.assertFalse(replywatch.settings({})["enabled"])
        watcher, why = replywatch.start({})
        self.assertIsNone(watcher)
        self.assertIn("off", why)

    def test_the_interval_has_a_floor(self):
        """A tighter loop is a provider complaint, not a faster stop."""
        got = replywatch.settings({"REPLY_POLL_SECONDS": "5"})
        self.assertEqual(got["interval"], replywatch.MIN_INTERVAL)

    def test_a_nonsense_interval_falls_back_rather_than_crashing(self):
        got = replywatch.settings({"REPLY_POLL_SECONDS": "soon"})
        self.assertEqual(got["interval"], replywatch.DEFAULT_INTERVAL)

    def test_an_unknown_provider_is_refused_not_ignored(self):
        """Silently dropping it would report healthy while polling nothing."""
        with self.assertRaises(replywatch.NotConfigured):
            replywatch.settings({"REPLY_POLL_PROVIDERS": "emailbison,gmail"})

    def test_it_refuses_to_start_without_credentials(self):
        watcher, why = replywatch.start({"REPLY_POLL_ENABLED": "1"})
        self.assertIsNone(watcher)
        self.assertIn("credentials", why)

    def test_starting_is_not_the_same_as_sending(self):
        """The whole path is read-only; nothing here may reach `push`."""
        self.assertNotIn("push", replywatch.__dict__)


class WatchTest(CampaignTest):
    """Scheduler behaviour against an isolated store and a fake provider."""

    def setUp(self):
        super().setUp()
        self._real_fetch = bison.fetch_replies
        self._env = {k: os.environ.get(k) for k in ("BISON_KEY", "HEYREACH_KEY")}
        os.environ["BISON_KEY"] = "test-key-not-real"
        os.environ.pop("HEYREACH_KEY", None)
        self.recs = self.seed_records()

    def tearDown(self):
        bison.fetch_replies = self._real_fetch
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        super().tearDown()

    def serve(self, rows):
        """Point the real poller at fixed rows, one page, newest first."""
        def fetch(cursor=None, per_page=None):
            return (rows, None)
        bison.fetch_replies = fetch
        return fetch

    def explode(self, exc):
        def fetch(cursor=None, per_page=None):
            raise exc
        bison.fetch_replies = fetch
        return fetch

    def record(self, rid="acme"):
        return next(r for r in store.load() if r["id"] == rid)


class FailureIsVisible(WatchTest):

    def test_an_unreachable_provider_is_recorded_not_swallowed(self):
        self.explode(bison.ProviderError("connection refused"))
        entry = replywatch.poll_once("emailbison")
        self.assertFalse(entry["healthy"])
        self.assertIn("gave up", entry["last_error"])
        self.assertEqual(entry["consecutive_failures"], 1)

    def test_a_failure_does_not_move_the_checkpoint(self):
        """A checkpoint advanced past rows nobody read is a lost reply."""
        self.serve([reply_row(1, "2026-09-01T10:00:00Z", "champ@acme.test")])
        replywatch.poll_once("emailbison")
        mark = poller.cursor_for("emailbison")
        self.explode(bison.ProviderError("gone"))
        replywatch.poll_once("emailbison")
        self.assertEqual(poller.cursor_for("emailbison"), mark)

    def test_consecutive_failures_accumulate_then_clear(self):
        self.explode(bison.ProviderError("nope"))
        replywatch.poll_once("emailbison")
        entry = replywatch.poll_once("emailbison")
        self.assertEqual(entry["consecutive_failures"], 2)
        self.serve([])
        entry = replywatch.poll_once("emailbison")
        self.assertEqual(entry["consecutive_failures"], 0)
        self.assertTrue(entry["healthy"])

    def test_one_provider_failing_does_not_stop_the_other(self):
        self.serve([reply_row(7, "2026-09-01T10:00:00Z", "champ@acme.test")])
        got = replywatch.sweep(providers=("heyreach", "emailbison"))
        self.assertFalse(got["heyreach"]["healthy"], "no credentials")
        self.assertTrue(got["emailbison"]["healthy"])

    def test_an_unconfigured_provider_never_reports_healthy(self):
        entry = replywatch.poll_once("heyreach")
        self.assertFalse(entry["healthy"])
        self.assertIn("not configured", entry["last_error"])

    def test_nothing_polled_is_not_healthy(self):
        """Unknown is not healthy. Absence of a poll is absence of proof."""
        self.assertFalse(replywatch.healthy({}))
        self.assertFalse(replywatch.healthy({"emailbison": {"healthy": True}}),
                         "healthy needs a successful poll behind it")

    def test_two_pollers_cannot_run_at_once(self):
        """The second is skipped, not queued: the work is already happening."""
        calls = []

        def fetch(cursor=None, per_page=None):
            calls.append(cursor)
            return ([], None)
        bison.fetch_replies = fetch
        with store.lock(for_path=replywatch.lock_file("emailbison")):
            entry = replywatch.poll_once("emailbison")
        self.assertEqual(entry.get("skipped_reason"), "already polling")
        self.assertEqual(calls, [], "it did not poll behind the lock")


class CanonicalTruthSurvivesATimer(WatchTest):

    def test_a_reply_pauses_only_its_own_account(self):
        self.serve([reply_row(11, "2026-09-01T10:00:00Z", "champ@acme.test")])
        replywatch.poll_once("emailbison")
        self.assertTrue(self.record("acme").get("paused"))
        self.assertFalse(self.record("borealis").get("paused"),
                         "one lead's reply is not another lead's problem")

    def test_the_same_reply_on_the_next_sweep_has_no_second_effect(self):
        row = reply_row(12, "2026-09-01T10:00:00Z", "champ@acme.test")
        self.serve([row])
        first = replywatch.poll_once("emailbison")
        self.assertEqual(first["new_replies_ingested"], 1)

        # The mark stops it being re-read at all; force the re-read anyway,
        # because idempotence must not depend on the checkpoint being right.
        # Scoped: the mark this run reads belongs to the workspace the
        # fixture says the key is bound to, not to a slot shared with
        # whatever estate it was pointed at last.
        poller.save_checkpoint("emailbison", None, scope=base.FIXTURE_SCOPE)
        self.serve([row])
        second = replywatch.poll_once("emailbison")
        self.assertEqual(second["new_replies_ingested"], 0)
        self.assertEqual(second["duplicates_ignored"], 1)

    def test_a_second_sweep_ingests_nothing_new(self):
        self.serve([reply_row(13, "2026-09-01T10:00:00Z", "champ@acme.test")])
        replywatch.poll_once("emailbison")
        again = replywatch.poll_once("emailbison")
        self.assertEqual(again["new_replies_ingested"], 0)

    def test_our_own_sent_mail_is_not_a_reply(self):
        self.serve([reply_row(14, "2026-09-01T10:00:00Z", "sender@demo.test",
                              kind="Outgoing Email", folder="Sent")])
        entry = replywatch.poll_once("emailbison")
        self.assertEqual(entry["events_inspected"], 0,
                         "outgoing mail must never enter as an event")
        self.assertFalse(self.record("acme").get("paused"))

    def test_a_bounce_is_not_a_human_reply(self):
        self.serve([reply_row(15, "2026-09-01T10:00:00Z", "champ@acme.test",
                              kind="Bounced", folder="Bounced",
                              text="550 no such user")])
        replywatch.poll_once("emailbison")
        rec = self.record("acme")
        replied = [e for e in (rec.get("events") or [])
                   if "reply" in str(e.get("type") or "")]
        self.assertEqual(replied, [], "a bounce is not somebody answering")

    def test_an_unknown_identity_cannot_stop_anybody(self):
        row = reply_row(16, "2026-09-01T10:00:00Z", "stranger@nowhere.test",
                        record="nobody", contact="nobody-champ")
        self.serve([row])
        entry = replywatch.poll_once("emailbison")
        self.assertEqual(entry["ambiguous_identities"], 1)
        self.assertEqual(entry["new_replies_ingested"], 0)
        self.assertFalse(self.record("acme").get("paused"))
        self.assertFalse(self.record("borealis").get("paused"))

    def test_a_reply_naming_the_wrong_record_cannot_stop_it(self):
        """Naming a record does not grant the right to write to it."""
        row = reply_row(17, "2026-09-01T10:00:00Z", "champ@acme.test",
                        record="borealis", contact="acme-champ")
        self.serve([row])
        replywatch.poll_once("emailbison")
        self.assertFalse(self.record("borealis").get("paused"))

    def test_the_workspace_comes_from_the_record_not_the_poll(self):
        """Asserting the fixture's own slug would pass against a hardcoded
        one, so this moves the record to a different workspace first. The
        poll is per provider; only the record knows whose reply this is."""
        move_to_workspace("elsewhere")
        self.serve([reply_row(18, "2026-09-01T10:00:00Z", "champ@acme.test",
                              client="elsewhere")])
        entry = replywatch.poll_once("emailbison")
        self.assertEqual(entry["workspaces"], {"elsewhere": 1})

    def test_a_record_with_no_workspace_is_not_guessed_into_one(self):
        move_to_workspace(None)
        self.serve([reply_row(20, "2026-09-01T10:00:00Z", "champ@acme.test",
                              client=None)])
        entry = replywatch.poll_once("emailbison")
        self.assertEqual(entry["workspaces"], {"unassigned": 1})

    def test_a_payload_cannot_claim_a_record_in_another_workspace(self):
        """Tenancy, enforced against the provider rather than the browser.

        The row names a real record and a real contact but claims a
        different workspace. Matching on identity alone would let whoever
        controls a provider payload pause any account in the estate.
        """
        move_to_workspace("elsewhere")
        self.serve([reply_row(21, "2026-09-01T10:00:00Z", "champ@acme.test",
                              client="demo")])
        entry = replywatch.poll_once("emailbison")
        self.assertEqual(entry["new_replies_ingested"], 0)
        self.assertEqual(entry["ambiguous_identities"], 1)
        self.assertFalse(self.record("acme").get("paused"))

    def test_an_unmatched_event_is_attributed_to_no_workspace(self):
        self.serve([reply_row(19, "2026-09-01T10:00:00Z", "who@nowhere.test",
                              record="nobody", contact="nobody-champ")])
        entry = replywatch.poll_once("emailbison")
        self.assertEqual(entry["workspaces"], {})


class TheLoop(unittest.TestCase):

    def test_a_sweep_that_raises_does_not_kill_the_watcher(self):
        """A watcher that dies quietly is worse than one that never ran."""
        calls = []

        def sweeper(providers=None, max_pages=None):
            calls.append(1)
            raise RuntimeError("everything is on fire")

        watcher = replywatch.Watcher(interval=60, sweeper=sweeper)
        watcher._stop.set()          # one pass, then exit
        watcher._loop()
        self.assertEqual(len(calls), 0, "a stopped watcher does not poll")

        watcher = replywatch.Watcher(interval=60, sweeper=sweeper)
        thread_safe = []

        def once(providers=None, max_pages=None):
            thread_safe.append(1)
            watcher._stop.set()
            raise RuntimeError("still on fire")
        watcher._sweep = once
        watcher._loop()
        self.assertEqual(len(thread_safe), 1)
        self.assertEqual(watcher.sweeps, 1, "it completed the pass")

    def test_stop_is_idempotent(self):
        watcher = replywatch.Watcher(interval=60, sweeper=lambda **k: {})
        watcher.stop()
        watcher.stop()


if __name__ == "__main__":
    unittest.main()
