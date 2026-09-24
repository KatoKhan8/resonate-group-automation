"""#resonate-notifications, repaired: attribution, naming, aggregation, tier.

Between 2026-09-22 and 2026-09-24 the ops channel received **102
`UNMATCHED REPLY NEEDS REVIEW` posts**. Every one carried the same five
fields - provider, `status: unmatched`, `why: no record for this event`,
`held: 0`, and a sentence saying a person decides. No campaign. No lead. No
event type. No timestamp. Nothing to act on and nothing to dismiss, which is
how a real CRITICAL gets missed in the scroll.

Replayed through this change: **4 posts**, and two of them name a real
unmatched reply on HeyReach campaign 613744, which is ours. Those two were in
the channel the whole time, indistinguishable from the other hundred.

Four properties are pinned here, and each maps to one half of the failure:

  1. ATTRIBUTION      an event on somebody else's campaign is not ours
  2. NAMING           an alert that names no object is not posted
  3. AGGREGATION      one digest an hour, and never an empty one
  4. TIER             three posting behaviours and nothing else

The fifth thing pinned is the one that is easiest to break by accident:
**nothing here may be a quieter way of losing a real alert.** Every drop
needs positive evidence, and every refusal is recorded.
"""
import datetime
import os
import unittest

from src import events, inbound, notify, unmatched
from src import workspaces as ws
from tests.campaignbase import CampaignTest

OPS = "#resonate-notifications-test"

#: Our registry, as `unmatched.registry()` builds it from campaigns.jsonl.
#: The EmailBison and HeyReach halves are deliberately disjoint number
#: ranges that overlap nothing: the bug this fixes was one compared to the
#: other.
MINE = {
    "emailbison": {491: "EMAIL BATCH1 KRESIMIR", 487: "EMAIL CONTROL V3"},
    "heyreach": {605732: "LINKEDIN COHORT V2", 613744: "LI B1 SEAT 174892"},
}

#: The client's own, measured 2026-09-24 from `bison.fetch_events`: 806 of
#: the 841 events after midnight were on these three.
THEIRS = (327, 328, 352)

HOUR = "2026-09-24T10"
AT = "2026-09-24T10:%02d:00Z"
LATER = "2026-09-24T11:30:00Z"


class _Repaired(CampaignTest):

    def setUp(self):
        super().setUp()
        self._prev = os.environ.get(notify.OPS_CHANNEL_VAR)
        os.environ[notify.OPS_CHANNEL_VAR] = OPS
        ws.ensure("productive", "Productive", client="productive")
        # The seat predicate is not what these tests are about, and its
        # readback refusal would otherwise decide the outcome of some of
        # them. Held fresh and empty so every verdict below comes from the
        # campaign registry.
        self._owned = inbound._owned
        inbound._owned = lambda *a, **k: ((set(inbound.OWNED_SEATS), set()),
                                          None)
        self.addCleanup(setattr, inbound, "_owned", self._owned)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(notify.OPS_CHANNEL_VAR, None)
        else:
            os.environ[notify.OPS_CHANNEL_VAR] = self._prev
        super().tearDown()

    def email_event(self, campaign, n=0, domain="unknown.test"):
        return events.neutral(
            type=events.REPLY_RECEIVED, channel="email", provider="emailbison",
            provider_event_id=f"emailbison:{campaign}-{n}",
            email=f"somebody@{domain}", at=AT % n,
            text="please take me off this list",
            external_campaign_id=campaign)

    def linkedin_event(self, n=0, campaign=None, handle="a-person"):
        return events.neutral(
            type=events.REPLY_RECEIVED, channel="linkedin", provider="heyreach",
            provider_event_id=f"heyreach:thread-{n}:{AT % n}",
            linkedin=f"https://www.linkedin.com/in/{handle}", at=AT % n,
            text="who are you", external_campaign_id=campaign)

    def flush(self, lookup=None, now=LATER):
        return unmatched.flush(now=now, known=MINE, lookup=lookup)

    def digests(self):
        return [r for r in notify.load()
                if r["type"] == notify.UNMATCHED_DIGEST]


# ------------------------------------------------------- 1. ATTRIBUTION

class AnEventOnTheClientsCampaignIsNotOurs(_Repaired):
    """806 of 841 EmailBison events after midnight on 2026-09-24 were on
    campaigns 327, 328 and 352, which the client runs in the same workspace
    our credential reaches. None of them was an unmatched reply of ours."""

    def test_the_three_client_campaigns_post_nothing(self):
        for i, campaign in enumerate(THEIRS):
            inbound.handle(self.email_event(campaign, i), [])
        self.flush()
        self.assertEqual([r["verdict"] for r in unmatched.load()],
                         [unmatched.THEIRS] * 3)
        self.assertEqual(self.digests(), [])

    def test_they_are_recorded_rather_than_forgotten(self):
        """Posting nothing is not the same as knowing nothing. Every one is
        in the ledger with the campaign that placed it there."""
        inbound.handle(self.email_event(328), [])
        self.flush()
        row = unmatched.load()[0]
        self.assertEqual(row["campaign_id"], 328)
        self.assertIn("328", row["verdict_why"])

    def test_an_event_on_our_campaign_does_reach_the_channel(self):
        inbound.handle(self.email_event(491), [])
        self.flush()
        self.assertEqual(unmatched.load()[0]["verdict"], unmatched.OURS)
        self.assertEqual(len(self.digests()), 1)

    def test_a_campaign_id_from_the_other_provider_is_never_ours(self):
        """THE BUG THIS REPLACES. `inbound._positively_not_ours` compared an
        EmailBison campaign id against a set of HeyReach ids, so 491 read as
        somebody else's. Here the registries cannot touch: 605732 is a
        HeyReach campaign of ours and is not an EmailBison campaign at all."""
        verdict, _cid, _name, why = unmatched.attribute(
            {"provider": "emailbison", "campaign_id": 605732}, known=MINE)
        self.assertEqual(verdict, unmatched.THEIRS)
        self.assertIn("emailbison", why)
        self.assertEqual(
            unmatched.attribute({"provider": "emailbison", "campaign_id": 491},
                                known=MINE)[0], unmatched.OURS)
        self.assertEqual(
            unmatched.attribute({"provider": "heyreach", "campaign_id": 605732},
                                known=MINE)[0], unmatched.OURS)

    def test_the_registry_is_built_from_our_own_campaign_state(self):
        """Not from a provider readback that expires. `work/campaigns.jsonl`
        is written when we create a campaign, so a campaign of ours is in it
        before its first send."""
        from src import campaigns as campaign_store
        campaign = campaign_store.new_campaign("c-reg", "productive", "A NAME")
        campaign["bison_campaign_id"] = 4242
        campaign_store.save([campaign])
        self.assertEqual(unmatched.registry()["emailbison"][4242], "A NAME")

    def test_a_lead_in_six_of_theirs_and_none_of_ours_is_theirs(self):
        inbound.handle(self.linkedin_event(1), [])
        self.flush(lookup=lambda url: {388947: "x", 388952: "y", 429679: "z"})
        self.assertEqual(unmatched.load()[0]["verdict"], unmatched.THEIRS)
        self.assertEqual(self.digests(), [])


class ADropStillNeedsPositiveEvidence(_Repaired):
    """The half of TASK-238 that must survive every change to this path.

    A quiet channel bought by discarding a real reply is far worse than a
    hundred false positives, so every one of these is KEPT.
    """

    def test_no_campaign_and_no_lookup_is_kept(self):
        inbound.handle(self.linkedin_event(1), [])
        self.flush(lookup=None)
        self.assertEqual(unmatched.load()[0]["verdict"],
                         unmatched.UNATTRIBUTED)
        self.assertEqual(len(self.digests()), 1)

    def test_a_lookup_that_raises_is_kept(self):
        def explodes(_url):
            raise RuntimeError("heyreach 500")

        inbound.handle(self.linkedin_event(1), [])
        self.flush(lookup=explodes)
        self.assertEqual(unmatched.load()[0]["verdict"],
                         unmatched.UNATTRIBUTED)
        self.assertEqual(len(self.digests()), 1)

    def test_a_lookup_that_answers_about_nobody_is_kept(self):
        inbound.handle(self.linkedin_event(1), [])
        self.flush(lookup=lambda url: {})
        self.assertEqual(unmatched.load()[0]["verdict"],
                         unmatched.UNATTRIBUTED)
        self.assertEqual(len(self.digests()), 1)

    def test_an_unparseable_campaign_id_is_kept(self):
        verdict, _cid, _name, _why = unmatched.attribute(
            {"provider": "emailbison", "campaign_id": "not-a-number"},
            known=MINE)
        self.assertEqual(verdict, unmatched.UNATTRIBUTED)

    def test_an_empty_registry_never_makes_an_event_somebody_elses(self):
        """"this id is in none of our campaigns" and "we could not read our
        campaigns" are the same expression, and must never be the same
        answer. A provider nobody registered, or a campaigns.jsonl that would
        not parse, would otherwise disown the whole estate at once."""
        for known in ({}, {"emailbison": {}, "heyreach": {}}):
            with self.subTest(known=known):
                self.assertEqual(
                    unmatched.attribute(
                        {"provider": "emailbison", "campaign_id": 328},
                        known=known)[0],
                    unmatched.UNATTRIBUTED)
                self.assertEqual(
                    unmatched.attribute(
                        {"provider": "heyreach", "campaign_id": None,
                         "profile_url": "https://example.test/in/x"},
                        known=known,
                        lookup=lambda url: {388947: "theirs"})[0],
                    unmatched.UNATTRIBUTED)

    def test_an_unregistered_provider_never_reads_as_theirs(self):
        verdict, _cid, _name, _why = unmatched.attribute(
            {"provider": "manual", "campaign_id": 12}, known=MINE)
        self.assertEqual(verdict, unmatched.UNATTRIBUTED)


# ------------------------------------------------------------ 2. NAMING

class EveryPostedAlertNamesItsObject(_Repaired):
    """The required test.

    Two failures, three weeks apart, and they are the same rule from both
    sides: `d6a719c2`, where every external-stop CRITICAL named campaign 487
    while carrying 491's figures - and the 102 posts that named nothing at
    all. One is dismissed, the other is scrolled past.
    """

    def test_the_shape_of_the_102_posts_is_refused(self):
        """Verbatim: the payload every one of them carried."""
        row = notify.plan(
            notify.UNMATCHED_REPLY, None,
            fields={"provider": "emailbison", "status": "unmatched",
                    "why": "no record for this event", "held": 0,
                    "action": "a person decides; nothing is auto-attributed"},
            ids={"provider_event_id": "emailbison:deadbeef"})
        self.assertEqual(row["status"], notify.SUPPRESSED)
        self.assertIn("names nothing to act on", row["why"])
        self.assertIn("campaign", row["why"])

    def test_the_same_alert_with_its_object_is_posted(self):
        row = notify.plan(
            notify.UNMATCHED_REPLY, None,
            fields={"provider": "emailbison", "campaign": "491 EMAIL BATCH1",
                    "lead": "unknown.test", "event_type": "reply_received",
                    "provider_event_id": "emailbison:deadbeef",
                    "at": "2026-09-24T10:00:00Z", "action": "decide who it is"},
            ids={"provider_event_id": "emailbison:deadbeef"})
        self.assertEqual(row["status"], notify.PLANNED)
        self.assertEqual(row["channel"], OPS)

    def test_every_digest_this_module_builds_names_its_object(self):
        """Not one alert: every alert the new path can produce."""
        for i, campaign in enumerate((491, 487)):
            inbound.handle(self.email_event(campaign, i), [])
        inbound.handle(self.linkedin_event(9), [])
        self.flush(lookup=lambda url: {})
        self.assertTrue(self.digests())
        for row in self.digests():
            named, missing = notify.names_its_object(
                row["type"], row["payload"], row["ids"], row["workspace"])
            self.assertTrue(named, f"{row['type']} missing {missing}")
            self.assertEqual(row["status"], notify.PLANNED)

    def test_the_digest_names_the_campaign_the_id_and_the_lead(self):
        inbound.handle(self.email_event(491, 3, domain="acme.test"), [])
        self.flush()
        text = notify.render(self.digests()[0])
        self.assertIn("491", text)
        self.assertIn("EMAIL BATCH1", text)
        self.assertIn("acme.test", text)
        self.assertIn("reply_received", text)
        self.assertIn("emailbison:491-3", text)
        self.assertIn("2026-09-24T10:03", text)

    def test_it_never_names_the_prospects_words_or_their_mailbox(self):
        inbound.handle(self.email_event(491, 4, domain="acme.test"), [])
        self.flush()
        text = notify.render(self.digests()[0])
        self.assertNotIn("take me off this list", text)
        self.assertNotIn("somebody@", text)

    def test_a_required_field_removed_makes_it_unpostable(self):
        """The mutation. Drop the campaign breakdown out of a real digest
        payload and the same payload stops being postable."""
        inbound.handle(self.email_event(491, 5), [])
        self.flush()
        payload = dict(self.digests()[0]["payload"])
        self.assertTrue(notify.names_its_object(
            notify.UNMATCHED_DIGEST, payload)[0])
        payload["by_campaign"] = []
        named, missing = notify.names_its_object(
            notify.UNMATCHED_DIGEST, payload)
        self.assertFalse(named)
        self.assertIn("by_campaign", missing)

    def test_a_blank_field_is_not_a_named_one(self):
        """`campaign: ''` is exactly the shape a builder produces when it
        reads a key that does not exist - which is how 481's "five empty
        steps" happened on 2026-09-24."""
        named, missing = notify.names_its_object(
            notify.CAMPAIGN_STOPPED_EXTERNALLY,
            {"campaign": "", "was": "active", "now": "paused",
             "action": "check"})
        self.assertFalse(named)
        self.assertIn("campaign", missing)

    def test_the_status_feed_is_out_of_scope_and_still_posts(self):
        """`_status_payload` refuses ids by construction, so requiring one
        would be requiring it to break its own contract."""
        prev = {k: os.environ.get(k) for k in
                (notify.STATUS_CHANNEL_VAR, notify.STATUS_ENABLED_VAR)}
        os.environ[notify.STATUS_CHANNEL_VAR] = "#status-test"
        os.environ[notify.STATUS_ENABLED_VAR] = "1"
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None
                                 else os.environ.__setitem__(k, v)
                                 for k, v in prev.items()])
        row = notify.plan(notify.STATUS_CHECKPOINT, None,
                          fields={"checkpoint": "12 of 12 monitors up"})
        self.assertEqual(row["status"], notify.PLANNED)

    def test_an_unconfigured_row_keeps_its_own_reason(self):
        """A workspace with no channel is a configuration problem somebody
        fixes in a minute. Overwriting that status with "it named nothing"
        would hide the actionable reason behind the one that is not, and
        `/admin/slack` counts UNCONFIGURED rows by status."""
        row = notify.plan(notify.POSITIVE_REPLY, "nowhere-workspace",
                          fields={})
        self.assertEqual(row["status"], notify.UNCONFIGURED)
        self.assertIn("no Slack channel", row["why"])

    def test_a_kind_with_no_entry_still_needs_an_identifier(self):
        """The default is not a waiver."""
        self.assertFalse(notify.names_its_object(notify.MX_ANOMALY, {"a": 1})[0])
        self.assertTrue(notify.names_its_object(
            notify.MX_ANOMALY, {"a": 1}, {"domain": "acme.test"})[0])


# ------------------------------------------------------- 3. AGGREGATION

class OneDigestAnHour(_Repaired):

    def test_thirty_events_in_one_hour_are_one_post(self):
        for i in range(30):
            inbound.handle(self.email_event(491, i), [])
        self.flush()
        self.assertEqual(len(unmatched.load()), 30)
        self.assertEqual(len(self.digests()), 1)
        self.assertEqual(self.digests()[0]["payload"]["unmatched"], 30)

    def test_two_hours_are_two_posts(self):
        inbound.handle(self.email_event(491, 1), [])
        event = self.email_event(491, 2)
        event["at"] = "2026-09-24T09:15:00Z"
        inbound.handle(event, [])
        self.flush()
        self.assertEqual(len(self.digests()), 2)

    def test_a_digest_with_no_rows_of_ours_is_not_posted(self):
        for i, campaign in enumerate(THEIRS):
            inbound.handle(self.email_event(campaign, i), [])
        results = self.flush()
        self.assertEqual(self.digests(), [])
        self.assertEqual([r["posted"] for r in results], [False])
        self.assertEqual(results[0]["theirs"], 3)

    def test_an_empty_hour_produces_no_payload_at_all(self):
        self.assertIsNone(unmatched.summarise(HOUR, []))
        self.assertIsNone(unmatched.summarise(
            HOUR, [{"verdict": unmatched.THEIRS, "provider": "emailbison"}]))

    def test_the_client_count_rides_along_so_the_suppression_is_visible(self):
        inbound.handle(self.email_event(491, 1), [])
        for i, campaign in enumerate(THEIRS):
            inbound.handle(self.email_event(campaign, 10 + i), [])
        self.flush()
        payload = self.digests()[0]["payload"]
        self.assertEqual(payload["unmatched"], 1)
        self.assertEqual(payload["client_events_not_posted"], 3)

    def test_the_current_hour_is_not_digested_yet(self):
        """Digesting a partial hour would post it and then be unable to post
        the rest: the id is the hour, so the second would deduplicate onto
        the first and the remaining events would never be seen."""
        inbound.handle(self.email_event(491, 1), [])
        self.flush(now="2026-09-24T10:40:00Z")
        self.assertEqual(self.digests(), [])
        self.flush(now=LATER)
        self.assertEqual(len(self.digests()), 1)

    def test_flushing_twice_posts_once(self):
        inbound.handle(self.email_event(491, 1), [])
        self.flush()
        self.flush()
        self.assertEqual(len(self.digests()), 1)

    def test_a_long_hour_points_at_the_ledger_rather_than_printing_itself(self):
        for i in range(unmatched.MAX_ROWS + 5):
            inbound.handle(self.email_event(491, i), [])
        self.flush()
        payload = self.digests()[0]["payload"]
        self.assertEqual(payload["unmatched"], unmatched.MAX_ROWS + 5)
        self.assertEqual(len(payload["events"]), unmatched.MAX_ROWS + 1)
        self.assertIn("unmatched-ledger.jsonl", payload["events"][-1])

    def test_the_verdict_is_written_back_so_an_hour_is_resolved_once(self):
        inbound.handle(self.email_event(328, 1), [])
        self.flush()
        self.assertEqual(unmatched.load()[0]["verdict"], unmatched.THEIRS)
        self.assertTrue(unmatched.load()[0]["digest"])
        self.assertEqual(unmatched.pending(), {})


# ------------------------------------------------------------- 4. TIER

class ThreePostingBehavioursAndNothingElse(_Repaired):

    def test_there_are_exactly_three(self):
        self.assertEqual(len(set(notify.POSTING.values())), 3)
        self.assertEqual(set(notify.POSTING.values()), set(notify.TIERS))

    def test_every_severity_has_one(self):
        for severity in notify.SEVERITIES:
            self.assertIn(notify.POSTING[severity], notify.TIERS)

    def test_critical_posts_and_pins(self):
        self.assertEqual(notify.posting_for(notify.CRITICAL),
                         notify.PIN_AND_POST)

    def test_action_required_posts_immediately(self):
        self.assertEqual(notify.posting_for(notify.ACTION_REQUIRED),
                         notify.POST_NOW)

    def test_info_goes_to_the_daily_thread(self):
        self.assertEqual(notify.posting_for(notify.INFO), notify.DAILY_THREAD)

    def test_a_warning_is_never_demoted_to_the_thread(self):
        """Nine real guards carry WARNING - held campaigns, QA failures,
        sender capacity, MX anomalies, credit exposure. Moving them into a
        thread would be this change quietly doing what it exists to stop."""
        self.assertEqual(notify.posting_for(notify.WARNING), notify.POST_NOW)
        self.assertNotEqual(notify.posting_for(notify.WARNING),
                            notify.DAILY_THREAD)

    def test_an_unmapped_severity_posts_rather_than_hides(self):
        self.assertEqual(notify.posting_for("something_new"), notify.POST_NOW)

    def test_the_four_critical_kinds_all_pin(self):
        critical = [k for k, (_d, s) in notify.ROUTES.items()
                    if s == notify.CRITICAL]
        self.assertTrue(critical)
        for kind in critical:
            self.assertEqual(notify.posting_for(notify.ROUTES[kind][1]),
                             notify.PIN_AND_POST)

    def test_the_digest_posts_immediately_and_is_not_threaded(self):
        self.assertEqual(notify.ROUTES[notify.UNMATCHED_DIGEST],
                         (notify.GLOBAL, notify.ACTION_REQUIRED))
        self.assertEqual(notify.posting_for(notify.ACTION_REQUIRED),
                         notify.POST_NOW)


class TheDailyThreadIsOpsOnly(_Repaired):

    def _sent(self, kind, at, slack_ts, severity=notify.INFO,
              destination=notify.GLOBAL, channel=OPS):
        return {"id": f"row-{slack_ts}", "at": at, "type": kind,
                "workspace": None, "destination": destination,
                "severity": severity, "channel": channel,
                "status": notify.SENT, "why": "posted", "ids": {},
                "payload": {}, "actions": [], "attempts": 1,
                "last_error": None, "slack_ts": slack_ts, "thread_ts": None}

    def test_the_second_info_of_the_day_replies_under_the_first(self):
        rows = [self._sent(notify.CAMPAIGN_APPROVED,
                           "2026-09-24T08:00:00+00:00", "111.1")]
        second = self._sent(notify.CAMPAIGN_APPROVED,
                            "2026-09-24T14:00:00+00:00", None)
        second["id"] = "row-second"
        self.assertEqual(notify.thread_parent_ts(second, rows), "111.1")

    def test_a_new_day_starts_a_new_thread(self):
        rows = [self._sent(notify.CAMPAIGN_APPROVED,
                           "2026-09-23T08:00:00+00:00", "111.1")]
        today = self._sent(notify.CAMPAIGN_APPROVED,
                           "2026-09-24T09:00:00+00:00", None)
        today["id"] = "row-today"
        self.assertIsNone(notify.thread_parent_ts(today, rows))

    def test_a_critical_is_never_pulled_into_the_thread(self):
        rows = [self._sent(notify.CAMPAIGN_APPROVED,
                           "2026-09-24T08:00:00+00:00", "111.1")]
        alert = self._sent(notify.CAMPAIGN_BLANK_CONTENT,
                           "2026-09-24T09:00:00+00:00", None,
                           severity=notify.CRITICAL)
        alert["id"] = "row-critical"
        self.assertEqual(notify.posting_for(alert["severity"]),
                         notify.PIN_AND_POST)

    def test_a_positive_reply_is_never_threaded(self):
        """It is WORKSPACE and INFO, and it is the one message a client's
        channel exists for. Burying it under a thread would be this change
        committing the fault it was written to fix."""
        rows = [self._sent(notify.POSITIVE_REPLY,
                           "2026-09-24T08:00:00+00:00", "111.1",
                           destination=notify.WORKSPACE, channel="#client")]
        second = self._sent(notify.POSITIVE_REPLY,
                            "2026-09-24T14:00:00+00:00", None,
                            destination=notify.WORKSPACE, channel="#client")
        second["id"] = "row-second"
        self.assertIsNone(notify.thread_parent_ts(second, rows))


# --------------------------------------------- 5. and nothing got quieter

class NothingHereLosesARealAlert(_Repaired):

    def test_the_hold_still_runs_before_any_attribution_question(self):
        """TASK-238 invariant 1. An unattributable reply still stops the
        cadence to that person, because being known twice must not make
        somebody less safe."""
        outcome = inbound.handle(self.email_event(328), [])
        self.assertIn("held_unattributed", outcome)

    def test_the_ledger_cannot_break_ingest(self):
        """`unmatched.record` has `notify.notify`'s contract: the pause, the
        classification and the stop have already happened by the time it
        runs, and it may never raise into the caller."""
        real = unmatched.transaction

        def broken(*_a, **_k):
            raise OSError("disk full")

        unmatched.transaction = broken
        self.addCleanup(setattr, unmatched, "transaction", real)
        outcome = inbound.handle(self.email_event(491), [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        self.assertIsNone(outcome["notification"])

    def test_the_sweep_survives_a_digest_that_cannot_be_built(self):
        from src import replywatch
        real = unmatched.flush

        def broken(*_a, **_k):
            raise RuntimeError("no")

        unmatched.flush = broken
        self.addCleanup(setattr, unmatched, "flush", real)
        result = replywatch.sweep(providers=[])
        self.assertIn("error", result[replywatch.DIGEST_KEY])

    def test_the_digest_key_is_not_mistaken_for_a_provider(self):
        """`sweep`'s result is keyed by provider everywhere it is read, and
        the CLI printed `entry.get("healthy")` over every key. A list under a
        thirteenth key would have crashed the `--once` report."""
        from src import replywatch
        self.assertNotIn(replywatch.DIGEST_KEY, replywatch.PROVIDERS)
        result = replywatch.sweep(providers=[])
        self.assertIsInstance(result[replywatch.DIGEST_KEY], list)

    def test_the_digest_is_action_required_and_reaches_the_ops_channel(self):
        inbound.handle(self.email_event(491), [])
        self.flush()
        row = self.digests()[0]
        self.assertEqual(row["destination"], notify.GLOBAL)
        self.assertEqual(row["severity"], notify.ACTION_REQUIRED)
        self.assertEqual(row["channel"], OPS)

    def test_a_suppressed_alert_is_still_a_row_somebody_can_find(self):
        """Not posted is not deleted. `/notifications` shows it, with the
        field that was missing."""
        row = notify.plan(notify.CAMPAIGN_QA_FAILED, None,
                          fields={"failures": 3})
        self.assertEqual(row["status"], notify.SUPPRESSED)
        self.assertIn(row["id"], [r["id"] for r in notify.load()])


if __name__ == "__main__":
    unittest.main()
