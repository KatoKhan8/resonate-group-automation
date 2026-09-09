"""A positive reply, from arrival to the channel it announces in.

`test_notify.py` tests the router in isolation. This runs the real path: a
provider event arrives, the company is paused, the reply is classified, and
only then is anything routed - to that workspace's own channel, carrying the
outreach history that actually happened.

The property worth the most here is the last one. The "Previous outreach"
block in a positive-reply alert comes from `touch.confirmed_touches`, the same
gate that decides whether a *message* may claim a touch occurred. So a planned
step cannot appear in it, which means the team is never told their multichannel
sequence converted when only one channel ever ran.
"""
import os
import unittest

from src import (accountpolicy as ap, assignment, events, notify, replies,
                 senderidentity as si,
                 store, workspaces as ws)
from tests.campaignbase import CampaignTest

MINE = "productive"
THEIRS = "contactout"


def roster(workspace=MINE):
    return [
        si.new_sender(workspace, "anna", "Anna Novak", team="growth"),
        si.new_sender(workspace, "petar", "Petar Horvat", team="growth"),
        si.new_email_account(workspace, "anna07", "anna",
                             f"anna07@{workspace}.test"),
        si.new_linkedin_account(workspace, "petar-li", "petar",
                                "https://www.linkedin.com/in/petar"),
    ]


MINIMAL_CONFIG = """\
name: {name}
domain: {slug}.test
booking_link: https://{slug}.test/book
sender:
  mode: client_rep
market:
  must: services business
  size_min_employees: 10
  geos: [United Kingdom]
personas:
  champion:
    titles: [COO, Operations Manager]
    cap_per_domain: 2
    angles:
      ops: utilisation and capacity
cadence: productive_default
tone:
  email: plain
  linkedin: plain
"""


class TwoTenants(CampaignTest):
    """Two real client configs, so "the other workspace" is really another.

    `CampaignTest` reads the repository's own `config/clients/`, which holds
    one client. Pointing `CLIENTS_DIR` at a temp directory with two configs is
    what makes a cross-tenant routing test test anything - relabelling one
    client twice would prove only that a string was copied.
    """

    def setUp(self):
        super().setUp()
        import os as _os
        import tempfile

        self._clients = tempfile.mkdtemp(prefix="rga-clients-")
        self._prev_clients = _os.environ.get("CLIENTS_DIR")
        _os.environ["CLIENTS_DIR"] = self._clients
        for slug, name in ((MINE, "Productive"), (THEIRS, "ContactOut"),
                           ("demo-client", "Demo Client")):
            with open(_os.path.join(self._clients, f"{slug}.yaml"), "w",
                      encoding="utf-8") as f:
                f.write(MINIMAL_CONFIG.format(slug=slug, name=name))

    def tearDown(self):
        import os as _os
        import shutil

        if self._prev_clients is None:
            _os.environ.pop("CLIENTS_DIR", None)
        else:
            _os.environ["CLIENTS_DIR"] = self._prev_clients
        shutil.rmtree(self._clients, ignore_errors=True)
        super().tearDown()


class TheWholeChain(TwoTenants):

    def setUp(self):
        super().setUp()
        ws.ensure(MINE, "Productive", client=MINE)
        ws.ensure(THEIRS, "ContactOut", client=THEIRS)
        ws.set_policy(MINE, {"slack.workspace_channel": "#client-productive"},
                      actor="test")
        ws.set_policy(THEIRS,
                      {"slack.workspace_channel": "#client-contactout"},
                      actor="test")
        si.install(roster(MINE) + roster(THEIRS))

    def record(self, client=MINE, rid="acme", with_touches=True):
        rec = store.new_record(rid, "domains", client, "Example Agency",
                               f"{rid}.test")
        rec["contacts"] = [{"key": "k", "name": "Sarah Smith", "title": "COO",
                            "email": "sarah@acme.test", "selected": True,
                            "primary": True,
                            "linkedin": "https://www.linkedin.com/in/sarah"}]
        rec["cadence"] = {}
        contact = rec["contacts"][0]
        assignment.ensure(rec, contact, client)
        if with_touches:
            # A real multichannel sequence: Anna on day 1, Petar on day 3.
            events.record(rec, events.PUSH_MARKED, contact_key="k",
                          channel="email", step="day1", day=1,
                          sender_id="anna", account_id="anna07")
            events.record(rec, events.PUSH_MARKED, contact_key="k",
                          channel="linkedin", step="day3", day=3,
                          sender_id="petar", account_id="petar-li")
        store.save([rec])
        return rec

    def reply(self, rec, text="Sounds interesting. Happy to take a look next "
                             "week.", channel="email", event_id="bison-1"):
        """The pause first, exactly as `events.apply` would have done it."""
        rec["paused"] = {"since": store.now(), "reason": "reply_received"}
        result = replies.apply(rec, "k", text, channel=channel,
                               provider="emailbison",
                               provider_event_id=event_id)
        # `replies.apply` mutates the record; the caller persists. Saving here
        # is what the real ingest path does, and without it every assertion
        # against the store would read the record from before the reply.
        rows = [r for r in store.load() if r["id"] != rec["id"]] + [rec]
        store.save(rows)
        return result

    # ------------------------------------------------------------ routing

    def test_a_positive_reply_announces_in_its_own_workspace_channel(self):
        rec = self.record()
        result = self.reply(rec)
        row = result["notification"]
        self.assertIsNotNone(row)
        self.assertEqual(row["type"], notify.POSITIVE_REPLY)
        self.assertEqual(row["workspace"], MINE)
        self.assertEqual(row["channel"], "#client-productive")
        self.assertEqual(row["status"], notify.PLANNED)

    def test_it_never_announces_in_the_other_workspaces_channel(self):
        rec = self.record()
        row = self.reply(rec)["notification"]
        self.assertNotEqual(row["channel"], "#client-contactout")

    def test_the_other_workspaces_reply_goes_to_the_other_channel(self):
        rec = self.record(client=THEIRS, rid="other")
        row = self.reply(rec, event_id="bison-2")["notification"]
        self.assertEqual(row["channel"], "#client-contactout")

    def test_a_workspace_with_no_channel_records_it_and_sends_nowhere(self):
        ws.ensure("demo-client", "Demo Client", client="demo-client")
        si.install(si.load() + roster("demo-client"))
        rec = self.record(client="demo-client", rid="demo")
        row = self.reply(rec, event_id="bison-3")["notification"]
        self.assertEqual(row["status"], notify.UNCONFIGURED)
        self.assertIsNone(row["channel"])

    # ------------------------------------------------- the real timeline

    def test_the_previous_outreach_is_the_one_that_happened(self):
        rec = self.record()
        row = self.reply(rec)["notification"]
        touches = row["payload"]["previous_touches"]
        self.assertEqual(len(touches), 2)
        self.assertIn("Day 1", touches[0])
        self.assertIn("Anna Novak", touches[0])
        self.assertIn("Day 3", touches[1])
        self.assertIn("Petar Horvat", touches[1])

    def test_a_planned_step_never_appears_as_outreach(self):
        """The team must not be told a sequence ran when it did not."""
        rec = self.record(with_touches=False)
        events.record(rec, events.PUSH_PREPARED, contact_key="k",
                      channel="email", step="day1", day=1,
                      push_id="acme:k:day1:email")
        store.save([rec])
        row = self.reply(rec, event_id="bison-4")["notification"]
        self.assertNotIn("previous_touches", row["payload"])

    def test_both_humans_are_named_and_they_are_different_people(self):
        rec = self.record()
        payload = self.reply(rec)["notification"]["payload"]
        self.assertEqual(payload["email_sender"], "Anna Novak")
        self.assertEqual(payload["linkedin_sender"], "Petar Horvat")

    def test_the_originating_channel_is_stated(self):
        rec = self.record()
        row = self.reply(rec, channel="linkedin", event_id="hr-1")
        self.assertEqual(row["notification"]["payload"]["channel"], "linkedin")

    def test_a_linkedin_reply_still_shows_the_earlier_email(self):
        """The point of E: the conversion came from a sequence, not a channel."""
        rec = self.record()
        payload = self.reply(rec, channel="linkedin",
                             event_id="hr-2")["notification"]["payload"]
        self.assertEqual(payload["channel"], "linkedin")
        self.assertTrue(any("email" in t for t in payload["previous_touches"]))

    def test_a_long_reply_is_excerpted_rather_than_pasted_whole(self):
        """A Slack channel is a poor place to keep somebody's correspondence."""
        rec = self.record()
        long_reply = ("Sounds interesting, happy to take a look next week. "
                      + "Some additional context about our situation. " * 20)
        row = self.reply(rec, text=long_reply, event_id="bison-5")
        excerpt = row["notification"]["payload"]["reply_excerpt"]
        # Bounded twice, and the tighter bound wins: `replies.classify`
        # already excerpts to 200 before this layer sees it, so notify's own
        # limit is a backstop for callers that do not go through the
        # classifier. Asserting the property rather than either constant.
        self.assertLess(len(excerpt), len(long_reply))
        self.assertLessEqual(len(excerpt), notify.EXCERPT_LIMIT)
        self.assertNotIn(chr(10), excerpt)

    def test_notifys_own_excerpt_bound_is_a_real_backstop(self):
        """For a caller that hands text straight in, without the classifier."""
        rec = self.record()
        row = notify.positive_reply(
            rec, "k", MINE, excerpt="y " * 500,
            provider_event_id="direct-1")
        self.assertLessEqual(len(row["payload"]["reply_excerpt"]),
                             notify.EXCERPT_LIMIT + 3)
        self.assertTrue(row["payload"]["reply_excerpt"].endswith("..."))

    def test_the_pause_is_stated_in_the_message(self):
        rec = self.record()
        payload = self.reply(rec)["notification"]["payload"]
        self.assertIn("paused", payload["paused"])

    # ------------------------------------------------------- the ordering

    def test_the_pause_survives_a_notification_that_cannot_route(self):
        ws.set_policy(MINE, {"slack.workspace_channel": ""}, actor="test")
        rec = self.record()
        result = self.reply(rec)
        self.assertTrue(result["paused"])
        self.assertTrue(store.get("acme")["paused"])

    def test_the_classification_is_recorded_before_anything_is_routed(self):
        rec = self.record()
        self.reply(rec)
        kinds = [e["type"] for e in store.get("acme")["events"]]
        self.assertIn(events.REPLY_CLASSIFIED, kinds)
        self.assertIn(events.POSITIVE_REPLY_DETECTED, kinds)

    # -------------------------------------------------------- idempotency

    def test_the_same_provider_event_twice_is_one_notification(self):
        rec = self.record()
        self.reply(rec, event_id="bison-same")
        rec = store.get("acme")
        self.reply(rec, event_id="bison-same")
        positive = [r for r in notify.load()
                    if r["type"] == notify.POSITIVE_REPLY]
        self.assertEqual(len(positive), 1)

    def test_a_heyreach_replay_is_also_one_notification(self):
        rec = self.record()
        for _ in range(4):
            self.reply(rec, channel="linkedin", event_id="hr-same")
            rec = store.get("acme")
        positive = [r for r in notify.load()
                    if r["type"] == notify.POSITIVE_REPLY]
        self.assertEqual(len(positive), 1)



class TheAlertSaysWhatTheSystemAlreadyDid(TheWholeChain):
    """A positive reply alert that reports only the reply makes the reader
    open Resonate to find the one thing they need immediately: whether the
    rest of the account is still being written to.

    `apply_reply` already returns that. The notification was built without
    it.
    """

    def test_it_carries_the_account_state_the_policy_produced(self):
        rec = self.record()
        result = self.reply(rec)
        fields = result["notification"]["payload"]
        self.assertTrue(fields.get("account_state"))

    def test_the_state_is_the_one_that_was_applied_not_a_second_opinion(self):
        """Passed through rather than recomputed: a derivation here could
        disagree with what actually happened to the record."""
        rec = self.record()
        result = self.reply(rec)
        applied = result["effect"]["account"]
        shown = result["notification"]["payload"]["account_state"]
        self.assertEqual(shown, ap.ACTION_LABEL[applied])

    def test_a_next_action_is_a_thing_somebody_does(self):
        rec = self.record()
        fields = self.reply(rec)["notification"]["payload"]
        action = fields.get("next_action")
        if action:
            self.assertNotIn(action.lower(), ("hold", "stop", "continue"))

    def test_the_new_fields_reach_the_client_channel(self):
        """The allowlist drops anything not named in it, which is the
        behaviour it exists for - so these had to be added deliberately."""
        for field in ("contact_state", "account_state", "next_action"):
            self.assertIn(field, notify.WORKSPACE_SAFE_FIELDS)

    def test_they_carry_nothing_about_senders_or_other_tenants(self):
        rec = self.record()
        fields = self.reply(rec)["notification"]["payload"]
        blob = " ".join(str(fields.get(f) or "") for f in
                        ("contact_state", "account_state", "next_action"))
        for leak in ("anna", "petar", "contactout", "bison", "heyreach"):
            self.assertNotIn(leak, blob.lower())

    def test_an_absent_effect_leaves_the_fields_absent(self):
        """Absent rather than guessed: a reader must not mistake "we did
        not record this" for "nothing happened"."""
        rec = self.record()
        row = notify.positive_reply(rec, "k", MINE, effect=None)
        fields = row["payload"]
        self.assertIsNone(fields.get("account_state"))
        self.assertIsNone(fields.get("next_action"))


class NeutralAndNegativeStayOutOfSlack(TwoTenants):

    def setUp(self):
        super().setUp()
        ws.ensure(MINE, "Productive", client=MINE)
        ws.set_policy(MINE, {"slack.workspace_channel": "#client-productive"},
                      actor="test")
        si.install(roster(MINE))

    def rec(self):
        rec = store.new_record("acme", "domains", MINE, "Acme", "acme.test")
        rec["contacts"] = [{"key": "k", "name": "S", "selected": True,
                            "email": "s@acme.test", "primary": True}]
        store.save([rec])
        return rec

    def test_a_negative_reply_produces_no_slack_notification(self):
        rec = self.rec()
        rec["paused"] = {"since": store.now(), "reason": "reply_received"}
        result = replies.apply(rec, "k", "Not interested, please remove me "
                                         "from your list.", channel="email")
        self.assertIsNone(result["notification"])
        self.assertEqual(notify.load(), [])

    def test_a_negative_reply_still_pauses(self):
        rec = self.rec()
        rec["paused"] = {"since": store.now(), "reason": "reply_received"}
        result = replies.apply(rec, "k", "No thanks.", channel="email")
        self.assertTrue(result["paused"])


class TheAbsentFallbacks(TwoTenants):
    """The two ways a notification could end up in a room nobody chose.

    Both need a fixture where falling back would actually have somewhere to
    go. A test that leaves the operations channel unset cannot tell "we did
    not fall back" from "there was nothing to fall back to", and it passes
    either way - which is how a missing guard survives a green suite.
    """

    def setUp(self):
        super().setUp()
        self._prev = os.environ.get(notify.OPS_CHANNEL_VAR)
        os.environ[notify.OPS_CHANNEL_VAR] = "#resonate-outbound-ops"
        ws.ensure(MINE, "Productive", client=MINE)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(notify.OPS_CHANNEL_VAR, None)
        else:
            os.environ[notify.OPS_CHANNEL_VAR] = self._prev
        super().tearDown()

    def test_an_unmapped_workspace_does_not_borrow_the_operations_channel(self):
        self.assertIsNotNone(notify.ops_channel(),
                             "with no operations channel this test cannot "
                             "tell a refused fallback from an absent one")
        self.assertIsNone(notify.workspace_channel(MINE))

    def test_the_notification_it_produces_has_no_channel(self):
        row = notify.plan(notify.POSITIVE_REPLY, MINE,
                          fields={"company": "Acme"},
                          ids={"record_id": "r1"})
        self.assertIsNone(row["channel"])
        self.assertNotEqual(row["channel"], notify.ops_channel())
        self.assertEqual(row["status"], notify.UNCONFIGURED)

    def shadow(self):
        """A second workspace claiming a client that is already taken.

        Written into the table directly, because `ws.ensure` refuses to
        create one - two workspaces sharing a client share every record and
        campaign in it. This is what a hand-edited table looks like, and
        `notify` refusing to guess a channel is what should happen when it
        is found rather than created.
        """
        rows = ws.load()
        rows.append(ws.new_workspace("productive-emea", "Productive EMEA",
                                     client=MINE))
        ws.save(rows)

    def test_the_product_will_not_create_that_estate(self):
        with self.assertRaises(ws.ClientTaken):
            ws.ensure("productive-emea", "Productive EMEA", client=MINE)

    def test_a_client_claimed_by_two_workspaces_resolves_to_neither(self):
        """Picking either would put one client's reply in the other's room."""
        self.shadow()
        ws.set_policy(MINE, {"slack.workspace_channel": "#first"},
                      actor="test")
        ws.set_policy("productive-emea",
                      {"slack.workspace_channel": "#second"}, actor="test")
        self.assertIsNone(notify.workspace_for_client(MINE))

    def test_one_workspace_claiming_it_still_resolves(self):
        """The refusal has to be about ambiguity, not about failing to look."""
        ws.set_policy(MINE, {"slack.workspace_channel": "#first"},
                      actor="test")
        self.assertEqual(notify.workspace_for_client(MINE), MINE)

    def test_an_ambiguous_reply_is_announced_nowhere(self):
        self.shadow()
        ws.set_policy(MINE, {"slack.workspace_channel": "#first"},
                      actor="test")
        rec = store.new_record("acme", "domains", MINE, "Acme", "acme.test")
        rec["contacts"] = [{"key": "k", "name": "S", "email": "s@acme.test",
                            "selected": True}]
        rec["cadence"] = {}
        store.save([rec])
        rec["paused"] = {"since": store.now(), "reason": "reply_received"}
        result = replies.apply(rec, "k", "Sounds interesting, happy to talk.",
                               channel="email", provider="emailbison",
                               provider_event_id="bison-ambiguous")
        self.assertIsNone(result["notification"])
        self.assertTrue(rec["paused"], "the pause is not conditional on "
                                       "anybody being told")


class TheGlobalOperationsFeed(TwoTenants):

    def setUp(self):
        super().setUp()
        self._prev = os.environ.get(notify.OPS_CHANNEL_VAR)
        os.environ[notify.OPS_CHANNEL_VAR] = "#resonate-outbound-ops"
        ws.ensure(MINE, "Productive", client=MINE)
        ws.set_policy(MINE, {"slack.workspace_channel": "#client-productive"},
                      actor="test")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(notify.OPS_CHANNEL_VAR, None)
        else:
            os.environ[notify.OPS_CHANNEL_VAR] = self._prev
        super().tearDown()

    def test_an_approval_request_carries_the_context_to_decide(self):
        campaign = {"campaign_id": "uk-digital", "name": "UK Digital",
                    "segment_key": "PRODUCTIVE-UK", "personas": ["champion"],
                    "geos": ["United Kingdom"], "fingerprint": "abc123"}
        row = notify.campaign_approval_required(
            campaign, {"companies": 24, "contacts": 24, "email_eligible": 17,
                       "linkedin_eligible": 20, "held": 4, "qa": "pass",
                       "double_verified": 18, "mx_summary": "3 blocked",
                       "sender_strategy": "Anna + Petar",
                       "estimated_credits": 150},
            MINE, review_url="/campaigns/uk-digital")
        self.assertEqual(row["destination"], notify.GLOBAL)
        self.assertEqual(row["channel"], "#resonate-outbound-ops")
        self.assertEqual(row["severity"], notify.ACTION_REQUIRED)
        for field in ("companies", "contacts", "held", "qa", "fingerprint",
                      "sender_strategy", "estimated_credits", "review_url"):
            self.assertIn(field, row["payload"], field)

    def test_the_approval_offers_the_four_actions(self):
        row = notify.campaign_approval_required(
            {"campaign_id": "c", "fingerprint": "f"}, {}, MINE)
        self.assertEqual([a["action_id"] for a in row["actions"]],
                         ["approve_campaign", "reject_campaign",
                          "hold_campaign", "open_review"])

    def test_operational_events_never_reach_the_client_channel(self):
        for event_type in (notify.PROVIDER_HEALTH_ISSUE, notify.FAILED_JOB,
                           notify.UNMATCHED_REPLY, notify.CAMPAIGN_QA_FAILED,
                           notify.SENDER_CAPACITY_WARNING):
            row = notify.operational(event_type, MINE, detail="x")
            self.assertEqual(row["channel"], "#resonate-outbound-ops",
                             event_type)

    def test_a_workspace_bound_kind_is_refused_by_the_operational_helper(self):
        with self.assertRaises(notify.NotifyError):
            notify.operational(notify.POSITIVE_REPLY, MINE)


if __name__ == "__main__":
    unittest.main()
