"""A checkpoint earned in one EmailBison workspace cannot silence another.

`/api/replies` answers for exactly one workspace and never says which. The
credential's binding is chosen in the vendor's UI, not here, and it has
returned four different estates in three days with nothing in this repository
changing: 51 inboxes, then 225 (153 tagged Productive), then 32 Greenfield, then
32 Bluewave.

The checkpoint was keyed by provider name alone. So a poll taken while the key
happened to be bound to Bluewave stored Bluewave's newest reply timestamp
in the slot marked `emailbison`, and when the binding moved back to Productive
every Productive reply older than that mark was filtered out by
`poll_emailbison`'s own high-water comparison as something already seen. It was
never ingested, no cadence was stopped by it, and the run reported success with
`events: 0` - on the one path whose job is to stop writing to somebody who has
already answered.

`GET /api/users` is what makes this fixable: it is the only route that states
the bound workspace. Found read-only on 2026-09-08; `/me`, `/user`, `/account`,
`/whoami` and `/workspaces/current` are all 404.
"""
import json
import os
import unittest

from src import poller, providers, replywatch
from src.providers import bison
from tests.base import ProviderTest

PRODUCTIVE = {"id": 10, "name": "PRODUCTIVE"}
BLUEWAVE = {"id": 29, "name": "Bluewave"}

# Older than Bluewave's newest below, which is the whole point.
REPLY = {"id": 1, "uuid": "u1", "type": "reply", "folder": "inbox",
         "created_at": "2026-09-08T09:00:00Z",
         "date_received": "2026-09-08T09:00:00Z",
         "from_email_address": "someone@productive.test"}
BLUEWAVE_REPLY = dict(REPLY, id=2, uuid="u2",
                        created_at="2026-09-08T13:56:20Z",
                        date_received="2026-09-08T13:56:20Z",
                        # A reserved domain, not the real one this estate sends from:
                        # `test_fixture_hygiene` refuses a live domain in
                        # a committed fixture, and it is right to.
                        from_email_address="someone@other-estate.test")


def feed(*rows):
    """One page, then the end of the feed."""
    pages = [(list(rows), None)]

    def fetch(cursor=None, per_page=None):
        return pages.pop(0) if pages else ([], None)
    return fetch


class AMarkIsBoundToItsWorkspace(ProviderTest):

    def run_poll(self, who, rows, **kw):
        return poller.run("emailbison", live=True, identify=lambda: who,
                          fetch=feed(*rows), sleep=lambda *_: None,
                          recs=[], **kw)

    # ------------------------------------------------------------ the defect

    def test_a_mark_from_one_workspace_does_not_suppress_another(self):
        """The bug, end to end: poll Bluewave, swing to Productive, and the
        older Productive reply must still arrive."""
        self.run_poll(BLUEWAVE, [BLUEWAVE_REPLY])
        result = self.run_poll(PRODUCTIVE, [REPLY])
        self.assertEqual(result["events"], 1,
                         "the Productive reply was filtered out by a mark "
                         "earned in Bluewave's estate")

    def test_the_two_estates_keep_separate_marks(self):
        self.run_poll(BLUEWAVE, [BLUEWAVE_REPLY])
        self.run_poll(PRODUCTIVE, [REPLY])
        saved = poller.load_checkpoints()
        self.assertIn("emailbison:ws29", saved)
        self.assertIn("emailbison:ws10", saved)
        self.assertEqual(saved["emailbison:ws29"]["cursor"],
                         "2026-09-08T13:56:20Z")
        self.assertEqual(saved["emailbison:ws10"]["cursor"],
                         "2026-09-08T09:00:00Z")

    def test_a_mark_still_suppresses_within_one_workspace(self):
        """Otherwise the fix is just a disabled checkpoint."""
        self.run_poll(PRODUCTIVE, [REPLY])
        again = self.run_poll(PRODUCTIVE, [REPLY])
        self.assertEqual(again["events"], 0)

    def test_the_pollers_own_lookup_is_not_reached(self):
        """`poll_emailbison` falls back to an unscoped `cursor_for` when
        handed None, which would read the shared slot straight back."""
        poller.save_checkpoint("emailbison", "2999-01-01T00:00:00Z")
        result = self.run_poll(PRODUCTIVE, [REPLY])
        self.assertEqual(result["events"], 1,
                         "the unscoped slot was consulted after all")

    # ------------------------------------------------- and it refuses loudly

    def test_an_unexpected_workspace_is_refused(self):
        with self.assertRaises(poller.WrongWorkspace):
            self.run_poll(BLUEWAVE, [BLUEWAVE_REPLY], expect=10)

    def test_the_refusal_names_both_workspaces(self):
        with self.assertRaises(poller.WrongWorkspace) as caught:
            self.run_poll(BLUEWAVE, [BLUEWAVE_REPLY], expect=10)
        said = str(caught.exception)
        self.assertIn("29", said)
        self.assertIn("Bluewave", said)
        self.assertIn("10", said)

    def test_a_refusal_touches_no_checkpoint(self):
        """A refusal that advanced the mark would cause the exact loss it
        exists to prevent."""
        before = poller.load_checkpoints()
        with self.assertRaises(poller.WrongWorkspace):
            self.run_poll(BLUEWAVE, [BLUEWAVE_REPLY], expect=10)
        self.assertEqual(poller.load_checkpoints(), before)

    def test_a_refusal_ingests_nothing(self):
        with self.assertRaises(poller.WrongWorkspace):
            self.run_poll(BLUEWAVE, [BLUEWAVE_REPLY], expect=10)
        self.assertEqual(poller.load_checkpoints(), {})

    def test_the_expected_workspace_polls_normally(self):
        result = self.run_poll(PRODUCTIVE, [REPLY], expect=10)
        self.assertEqual(result["events"], 1)
        self.assertEqual(result["workspace"], PRODUCTIVE)

    def test_expect_compares_across_string_and_int(self):
        """Config arrives as text; the API answers with a number."""
        self.assertEqual(
            self.run_poll(PRODUCTIVE, [REPLY], expect="10")["events"], 1)

    # --------------------------------------------------------- the identity

    def test_an_identity_without_an_id_is_refused(self):
        """Not read as "unscoped, carry on" - that is the original bug."""
        with self.assertRaises(poller.PollError):
            poller.run("emailbison", live=True, identify=lambda: {},
                       fetch=feed(REPLY), sleep=lambda *_: None, recs=[])

    def test_a_raising_identity_stops_the_poll(self):
        def boom():
            raise providers.ProviderError("no /users")
        with self.assertRaises(providers.ProviderError):
            poller.run("emailbison", live=True, identify=boom,
                       fetch=feed(REPLY), sleep=lambda *_: None, recs=[])
        self.assertEqual(poller.load_checkpoints(), {})

    def test_a_pin_nobody_can_check_is_refused(self):
        """A provider with no identity route cannot honour a pin, and
        silence would be the same defect one level up: an unanswerable
        question read as a pass."""
        with self.assertRaises(poller.WrongWorkspace):
            poller.run("heyreach", live=True, expect=10,
                       fetch=feed(), sleep=lambda *_: None, recs=[])

    def test_that_refusal_says_the_provider_cannot_answer(self):
        with self.assertRaises(poller.WrongWorkspace) as caught:
            poller.run("heyreach", live=True, expect=10,
                       fetch=feed(), sleep=lambda *_: None, recs=[])
        self.assertIn("cannot say", str(caught.exception))

    def test_an_unpinned_provider_without_identity_still_polls(self):
        """Otherwise the refusal above breaks HeyReach entirely."""
        # HeyReach pages by offset/limit, not by cursor.
        result = poller.run("heyreach", live=True,
                            fetch=lambda offset=None, limit=None: ([], None),
                            sleep=lambda *_: None, recs=[])
        self.assertTrue(result["live"])

    def test_heyreach_is_unscoped_and_unchanged(self):
        """One estate, no selector. Scoping it would be invention."""
        self.assertIsNone(poller.identity_of("heyreach")[0])
        self.assertEqual(poller.checkpoint_key("heyreach"), "heyreach")

    def test_a_dry_run_states_no_cursor_rather_than_a_borrowed_one(self):
        poller.save_checkpoint("emailbison", "2026-01-01T00:00:00Z")
        result = poller.run("emailbison", live=False)
        self.assertIsNone(result["cursor"])
        self.assertIsNone(result["workspace"])


class TheProviderReadsItsOwnBinding(ProviderTest):
    """`bison.bound_workspace` parsing, against the shape the live route
    returned on 2026-09-08."""

    LIVE = {"data": {"id": 2, "name": "Z. B.",
                     "email": "someone@example.test",
                     "workspace": {"id": 29, "name": "Bluewave"}}}

    def bound(self, status, body):
        os.environ["BISON_KEY"] = "not-a-real-key"
        providers.set_transport(
            lambda *a, **kw: (status, json.dumps(body)))
        return bison.bound_workspace()

    def test_the_live_shape_is_read(self):
        self.assertEqual(self.bound(200, self.LIVE),
                         {"id": 29, "name": "Bluewave"})

    def test_a_missing_workspace_raises(self):
        with self.assertRaises(providers.ProviderError):
            self.bound(200, {"data": {"id": 2}})

    def test_a_non_numeric_id_raises(self):
        with self.assertRaises(providers.ProviderError):
            self.bound(200, {"data": {"workspace": {"id": "main"}}})

    def test_a_boolean_id_raises(self):
        """`True` is an `int`, and would key a checkpoint as `ws1`."""
        with self.assertRaises(providers.ProviderError):
            self.bound(200, {"data": {"workspace": {"id": True}}})

    def test_a_numeric_string_id_is_accepted(self):
        self.assertEqual(
            self.bound(200, {"data": {"workspace": {"id": "10",
                                                    "name": "PRODUCTIVE"}}}),
            {"id": 10, "name": "PRODUCTIVE"})

    def test_a_non_200_raises(self):
        with self.assertRaises(providers.ProviderError):
            self.bound(403, {"message": "This action is unauthorized."})


class TheWatcherPassesThePinDown(ProviderTest):
    """A guard nothing calls is the defect this repository keeps producing,
    so this asserts the wiring, not just the function."""

    def poll(self, env, run=None):
        calls = []

        def fake_run(provider, **kw):
            calls.append(kw)
            return {"provider": provider, "live": True, "cursor": None,
                    "workspace": None, "pages": 0, "events": 0,
                    "outcomes": []}

        original = poller.run
        poller.run = run or fake_run
        self.addCleanup(setattr, poller, "run", original)
        os.environ["BISON_KEY"] = "not-a-real-key"
        replywatch.poll_once("emailbison", env=env)
        return calls

    def test_the_pin_reaches_the_poller(self):
        calls = self.poll({"BISON_KEY": "x", "BISON_WORKSPACE_ID": "10"})
        self.assertEqual([c.get("expect") for c in calls], ["10"])

    def test_an_unpinned_deployment_passes_none(self):
        calls = self.poll({"BISON_KEY": "x"})
        self.assertEqual([c.get("expect") for c in calls], [None])

    def test_a_wrong_workspace_is_reported_unhealthy_not_crashed(self):
        def boom(provider, **kw):
            raise poller.WrongWorkspace("bound to 29 (Bluewave)")
        self.poll({"BISON_KEY": "x", "BISON_WORKSPACE_ID": "10"}, run=boom)
        status = replywatch.load_status().get("emailbison") or {}
        self.assertFalse(status.get("healthy"))
        self.assertIn("Bluewave", status.get("last_error", ""))


if __name__ == "__main__":
    unittest.main()
