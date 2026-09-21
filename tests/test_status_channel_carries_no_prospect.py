#!/usr/bin/env python3
"""The team status feed: a third destination, and it carries no person.

OPERATOR DECISION, 2026-09-21: #resonate-os is a GLOBAL route named "status",
separate from the ops channel, and "nothing in this channel contains prospect
names, emails or client-internal data beyond counts."

The tests that matter are the refusals. This channel has the widest human
audience in the product, so the guarantee cannot be "the caller will be
careful" - it has to be that a careless caller gets an exception.
"""
import os
import tempfile
import unittest

from src import notify, store


class StatusCase(unittest.TestCase):

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self._env = {k: os.environ.get(k) for k in
                     ("NOTIFICATIONS", notify.STATUS_CHANNEL_VAR,
                      notify.STATUS_ENABLED_VAR, notify.OPS_CHANNEL_VAR)}
        os.environ["NOTIFICATIONS"] = os.path.join(self._dir.name,
                                                   "notifications.jsonl")
        os.environ[notify.STATUS_CHANNEL_VAR] = "C0STATUS"
        os.environ[notify.OPS_CHANNEL_VAR] = "C0OPS"
        os.environ.pop(notify.STATUS_ENABLED_VAR, None)
        self.addCleanup(self._restore)

    def _restore(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._dir.cleanup()


class TheStatusFeedIsItsOwnDestination(StatusCase):

    def test_status_is_not_the_ops_channel(self):
        decision = notify.destination_for(notify.STATUS_NOW_RUNNING)
        self.assertEqual(decision["destination"], notify.STATUS)
        self.assertEqual(decision["channel"], "C0STATUS")
        self.assertEqual(decision["status"], notify.PLANNED)

    def test_ops_events_still_go_to_ops(self):
        decision = notify.destination_for(notify.PROVIDER_HEALTH_ISSUE)
        self.assertEqual(decision["destination"], notify.GLOBAL)
        self.assertEqual(decision["channel"], "C0OPS")

    def test_the_digest_moved_to_status(self):
        self.assertEqual(notify.route(notify.OPERATIONS_DIGEST)[0],
                         notify.STATUS)

    def test_a_hard_stop_has_its_own_status_type_so_ops_keeps_its_own(self):
        """The one deliberate double route. Two types, two ids, so neither
        can suppress or de-duplicate the other."""
        self.assertEqual(notify.route(notify.STATUS_HARD_STOP),
                         (notify.STATUS, notify.CRITICAL))
        self.assertNotEqual(
            notify.notification_id(notify.STATUS_HARD_STOP, ids="x"),
            notify.notification_id(notify.PROVIDER_HEALTH_ISSUE, ids="x"))

    def test_an_unconfigured_status_channel_is_a_status_not_a_crash(self):
        os.environ.pop(notify.STATUS_CHANNEL_VAR)
        decision = notify.destination_for(notify.STATUS_CHECKPOINT)
        self.assertEqual(decision["status"], notify.UNCONFIGURED)
        self.assertIn(notify.STATUS_CHANNEL_VAR, decision["why"])

    def test_the_feed_is_on_by_default_and_can_be_switched_off(self):
        self.assertTrue(notify.status_enabled())
        os.environ[notify.STATUS_ENABLED_VAR] = "off"
        self.assertFalse(notify.status_enabled())
        self.assertEqual(
            notify.destination_for(notify.STATUS_CHECKPOINT)["status"],
            notify.SUPPRESSED)


class NoProspectReachesTheTeamChannel(StatusCase):

    def test_a_field_named_like_a_person_is_refused(self):
        for field in ("contact_name", "prospect", "reply_excerpt",
                      "linkedin_url", "subject"):
            with self.assertRaises(notify.NotifyError, msg=field):
                notify._status_payload({field: "anything"})

    def test_an_address_field_is_refused_but_a_channel_count_is_not(self):
        """`email` as a field name is a mailbox; `enrolled_email` is a count
        of leads on the email side, and the operator wants both channels
        counted separately in every report. Substring-matching `email`
        blocked the first dual-channel batch report from being posted."""
        for field in ("email", "address", "mailbox"):
            with self.assertRaises(notify.NotifyError, msg=field):
                notify._status_payload({field: "anything"})
        payload = notify._status_payload(
            {"enrolled_email": 80, "enrolled_linkedin": 0,
             "email_scheduled_rows": 0})
        self.assertEqual(payload["enrolled_email"], 80)

    def test_an_address_hidden_inside_an_innocent_field_is_refused(self):
        with self.assertRaises(notify.NotifyError):
            notify._status_payload(
                {"note": "first send landed for a.person@example.com"})

    def test_counts_and_words_about_the_machine_pass(self):
        payload = notify._status_payload(
            {"enrolled": 360, "sent_today": 2, "campaigns": 8,
             "note": "batch 1 pushed, veto window elapsed"})
        self.assertEqual(payload["enrolled"], 360)
        self.assertEqual(payload["sent_today"], 2)

    def test_a_credential_shaped_field_is_refused_here_too(self):
        with self.assertRaises(Exception):
            notify._status_payload({"slack_token": "xoxb-nope"})

    def test_plan_uses_the_status_builder_for_status_events(self):
        with self.assertRaises(Exception):
            notify.plan(notify.STATUS_CHECKPOINT,
                        fields={"contact_name": "somebody"})
        row = notify.plan(notify.STATUS_CHECKPOINT, fields={"ready": 868},
                          ids={"checkpoint": "t1"})
        self.assertEqual(row["destination"], notify.STATUS)
        self.assertEqual(row["payload"], {"ready": 868})

    def test_the_workspace_allowlist_is_untouched_by_this(self):
        """The workspace feed keeps its own rules: this added a destination,
        it did not relax an existing one."""
        payload = notify._workspace_payload(
            {"contact_name": "Somebody", "internal_sender_pool": "no"})
        self.assertEqual(payload, {"contact_name": "Somebody"})


class StatusRowsAreDeliverableWithoutAWorkspace(StatusCase):

    def test_a_status_row_is_planned_with_no_workspace_and_a_channel(self):
        row = notify.plan(notify.STATUS_NOW_RUNNING,
                          fields={"monitors": 8}, ids={"hour": "2026-09-21T19"})
        self.assertIsNone(row["workspace"])
        self.assertEqual(row["status"], notify.PLANNED)
        self.assertEqual(row["channel"], "C0STATUS")

    def test_the_same_hour_plans_once(self):
        first = notify.plan(notify.STATUS_NOW_RUNNING, fields={"monitors": 8},
                            ids={"hour": "2026-09-21T19"})
        second = notify.plan(notify.STATUS_NOW_RUNNING, fields={"monitors": 9},
                             ids={"hour": "2026-09-21T19"})
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(notify.load()), 1)


if __name__ == "__main__":
    unittest.main()
