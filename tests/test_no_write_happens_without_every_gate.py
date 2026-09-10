"""A guard nobody is obliged to call is a guard that gets skipped.

It happened twice in one session, to the author of the guards, within the hour.
`bison.require_workspace` existed and was optional, so three prior-contact reads
omitted it and answered CLEAR against another client's empty estate. And nothing
compared a provider's configured copy to the approved copy, so a vendor
placeholder note sat in a fully-verified canary campaign.

So `executionguard.authorize()` is not a checklist a writer is trusted to run.
It is the only source of the `Authorization` a writer requires. Every test below
proves the same property from a different angle: WITH A GATE FAILING, NO
PROVIDER CALL HAPPENS AT ALL - not a refused call, not a rolled-back call, none.

The spy is the whole method. `Provider` records every call it receives and is
never wired to a real transport, so `spy.calls == []` is a stronger claim than
any assertion about return values: it says the code never got as far as trying.
"""
import datetime
import os
import unittest
from unittest import mock

from src import (actionledger, approval, cadence, campaigns, clients,
                 collision, configdiff, eligibility, executionguard,
                 killswitch, store)

from tests.base import QueueTest

NOTE = ("hi Dana, i work with Design Services teams on utilisation. "
        "curious how Brightpath handles it at your size. happy to connect.")
WS = 10
# DERIVED FROM THE CLOCK, NOT PINNED TO A DATE.
#
# These were hard-coded to 2026-09-09. `actionledger.reserve` stamps
# `store.now()`, and `count_on` compares calendar days - so every cap assertion
# passed on the day it was written and failed the next morning. A test that
# depends on today's date is a test that reports a defect it has not found.
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
FRESH = (NOW - datetime.timedelta(minutes=1)).isoformat()
STALE = (NOW - datetime.timedelta(minutes=30)).isoformat()


class Provider:
    """A stand-in for any provider write. Records; never sends."""

    def __init__(self):
        self.calls = []

    def write(self, authorization, **kw):
        if not isinstance(authorization, executionguard.Authorization):
            raise AssertionError(
                "a write layer must refuse anything that is not an "
                "Authorization; a dict claiming the gates passed is not proof")
        authorization.spend()
        self.calls.append({"key": authorization.key, **kw})
        return {"ok": True}


class GuardTest(QueueTest):
    """One approved LinkedIn canary, entirely synthetic."""

    def setUp(self):
        super().setUp()
        self.spy = Provider()
        self.config = clients.load("productive")
        rec = store.new_record("rec-1", "domains", "productive",
                               "Brightpath", "brightpath.test")
        rec["state"] = "verified"
        rec["company_facts"] = {"industry": "Design Services",
                                "research_outcome": "HTTP_SUCCESS"}
        rec["contacts"] = [{
            "key": "dana-marsh", "name": "Dana Marsh",
            "title": "Head of Production", "email": "dana@brightpath.test",
            "linkedin": "danamarsh", "persona": "champion",
            "angle": "operations",
            "verification": {"evidence": [
                {"provider": "contactout", "status": "valid",
                 "email": "dana@brightpath.test", "catch_all": False,
                 "disposable": False, "at": "2026-09-09T00:00:00+00:00"},
                {"provider": "reoon", "status": "valid",
                 "email": "dana@brightpath.test", "catch_all": False,
                 "disposable": False, "safe_to_send": True,
                 "at": "2026-09-09T00:00:00+00:00"}]},
            "mx": {"status": "known_allowed", "email_eligible": True},
        }]
        with store.transaction() as rows:
            rows.append(rec)
        self.rec = store.get("rec-1")
        self.contact = self.rec["contacts"][0]

        self.step = cadence.expand_step(
            self.rec, self.contact, executionguard._spec_for("day3"),
            self.config)
        # Approve it the way a human would, through the canonical path.
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "rec-1":
                    row.setdefault("cadence", {}).setdefault(
                        "dana-marsh", {})["day3"] = dict(
                            self.step,
                            approval={"by": "operator", "at": store.now(),
                                      "fingerprint": approval.fingerprint(
                                          self.step)})
        self.rec = store.get("rec-1")
        self.contact = self.rec["contacts"][0]

        self.campaign = campaigns.new_campaign(
            "canary", "productive", "CLIENT - CANARY", created_by="operator")
        self.campaign.update({
            "heyreach_campaign_id": 594061, "heyreach_list_id": 926076,
            "org_unit": 118832, "record_ids": ["rec-1"],
            "senders": {"email": [], "linkedin": [{"id": 116968,
                                                   "daily_limit": 1}]},
            "daily_volume": {"email": 0, "linkedin": 1},
            "provider_delays": [["HOUR", 0]],
            "provider_status_expected": "PAUSED",
        })
        # The seat, inventoried in THIS test's isolated sender state.
        # `senderidentity.path()` derives from the queue directory, so
        # `QueueTest` scopes it automatically. Inventoried rather than mocked:
        # the sender gate checks the provider seat is in the client's canonical
        # roster and is active and healthy, and a mocked roster proves none of
        # that.
        from src import senderidentity
        with senderidentity.transaction() as rows:
            rows.append(senderidentity.new_linkedin_account(
                "productive", "li-116968", None,
                "https://www.linkedin.com/in/mina-ruzicic-b4422438a",
                provider="heyreach", provider_account_id="116968",
                active=True, daily_limit=40, health="ok"))
        self.approve_campaign()

    def approve_campaign(self):
        """Record a campaign-level approval, shaped as the orchestrator does.

        Step approval covers the words; campaign approval covers the sender,
        the provider binding, the limits and the lead set. Both are required,
        and every gate downstream of it is unreachable without it - which is
        how the fixture found out it was missing.
        """
        current = campaigns.fingerprint(self.campaign, store.load(),
                                        self.config)
        self.campaign["approval"] = {"action": "approve", "by": "operator",
                                     "at": store.now(),
                                     "fingerprint": current}
        self.campaign["fingerprint"] = current
        self.campaign["status"] = campaigns.APPROVED

    def readback(self, verdict=configdiff.PASS, verified_at=FRESH,
                 failures=(), campaign_id="canary", channel="linkedin",
                 provider_campaign_id=594061):
        """A sealed read-back, bound to what it compared.

        A dict will not do: the gate requires `configdiff.Readback` precisely
        because a dict asserting that a provider was verified is not proof that
        it was, and one dict used to authorise any number of actions for any
        campaign.
        """
        return configdiff.Readback(
            diff={"verdict": verdict, "failures": list(failures)},
            approved={}, provider={}, campaign_id=campaign_id,
            channel=channel, provider_campaign_id=provider_campaign_id,
            verified_at=verified_at)

    def authorize(self, **over):
        kw = dict(operation="linkedin_connection_request", channel="linkedin",
                  campaign=self.campaign, rec=self.rec, contact=self.contact,
                  step_key="day3", workspace=WS, config=self.config,
                  now=NOW, readback=self.readback())
        kw.update(over)
        return executionguard.authorize(**kw)

    def attempt(self, **over):
        """Authorize then write. Returns the spy so callers assert on calls."""
        auth = self.authorize(**over)
        self.spy.write(auth, note=NOTE)
        return auth

    # Every gate below needs collision and killswitch neutralised or the test
    # would pass for the wrong reason. Each test re-enables the one it targets.
    def allow_collision(self):
        return mock.patch.object(collision, "check_linkedin_profile",
                                 return_value=(collision.CLEAR, {}))

    def allow_killswitch(self):
        return mock.patch.object(killswitch, "require", return_value=True)

    def allow_sender(self):
        """A no-op: the seat is genuinely inventoried in setUp.

        This used to stub `senderidentity.require_sender`, which was the wrong
        function - the gate looks up a PROVIDER seat, not a human sender id -
        and stubbing it hid that. Kept as a context manager so the call sites
        read the same, and so a future seat-level test can override it.
        """
        import contextlib
        return contextlib.nullcontext()

    def refused_at(self, gate, **over):
        with self.allow_collision(), self.allow_killswitch(), self.allow_sender():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt(**over)
        self.assertEqual(caught.exception.gate, gate,
                         f"expected gate {gate!r}, got "
                         f"{caught.exception.gate!r}: {caught.exception.why}")
        self.assertEqual(self.spy.calls, [], "a provider call was made anyway")
        return caught.exception



class TheHappyPathIsAuthorized(GuardTest):
    def test_a_fully_gated_action_authorizes_and_writes_once(self):
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            auth = self.attempt()
        self.assertEqual(len(self.spy.calls), 1)
        self.assertEqual(auth.key, "rec-1:dana-marsh:day3:linkedin")
        self.assertIn("killswitch", auth.gates)
        self.assertIn("reserved", auth.gates)

    def test_the_ledger_gate_is_recorded_in_the_gates_tuple(self):
        """`gates` is what an audit reads to prove which checks ran."""
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            auth = self.attempt()
        for gate in ("tenancy", "approval", "campaign_approval", "readback",
                     "collision", "pilot_cap", "ledger", "killswitch",
                     "reserved"):
            self.assertIn(gate, auth.gates, gate)

    def test_the_idempotency_key_is_push_id_not_a_second_definition(self):
        """Two definitions of one identity drift, and then the ledger and
        `push.already_pushed` key different things with every test green."""
        from src import push
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            auth = self.attempt()
        self.assertEqual(auth.key,
                         push.push_id(self.rec, "dana-marsh", "day3",
                                      "linkedin"))

    def test_the_ledger_recorded_the_attempt_before_the_write(self):
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            self.attempt()
        self.assertEqual(actionledger.state_of("rec-1:dana-marsh:day3:linkedin"),
                         actionledger.ATTEMPTED)

    def test_one_authorization_cannot_be_spent_twice(self):
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            auth = self.authorize()
            self.spy.write(auth, note=NOTE)
            with self.assertRaises(executionguard.NotAuthorized):
                self.spy.write(auth, note=NOTE)
        self.assertEqual(len(self.spy.calls), 1)


class EachGateStopsTheProviderCallEntirely(GuardTest):
    """The property that matters: `spy.calls == []`, not a handled error."""

    def test_killswitch_off_prevents_the_call(self):
        """And the refusal must be the killswitch's OWN verdict.

        Asserting only on `gate == "killswitch"` is what let this test pass
        while the gate was broken: the campaign ROW was being passed as an id
        string, `campaign_state` raised AttributeError on `.get`, and a type
        error satisfied the assertion. So the message is checked too - the real
        `SendingRefused` names the layer that refused and how many did, and a
        Python type error cannot fake that.
        """
        with self.allow_collision(), self.allow_sender():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt()
        self.assertEqual(caught.exception.gate, "killswitch")
        self.assertNotIn("AttributeError", caught.exception.why)
        self.assertNotIn("object has no attribute", caught.exception.why)
        self.assertIn("layer", caught.exception.why.lower())
        self.assertEqual(self.spy.calls, [])

    def test_the_campaign_layer_is_actually_consulted(self):
        """The gate reached `campaign_state` at all, which it never did while
        the id string was being passed."""
        state = killswitch.state(workspace="productive", campaign=self.campaign)
        layers = [row.get("layer") for row in state.get("layers") or []]
        self.assertIn("campaign", layers,
                      "the campaign layer never evaluated")

    def test_a_frozen_campaign_is_refused_by_the_killswitch(self):
        """The property the broken gate could not have enforced."""
        with mock.patch.object(campaigns, "is_frozen", return_value=True):
            state = killswitch.state(workspace="productive",
                                     campaign=self.campaign)
        self.assertFalse(state["sending"])

    def test_a_cap_of_zero_prevents_the_call(self):
        # `pilotcaps.configured()` reads `daily_volume`, not a `pilot` key.
        config = dict(self.config, daily_volume={"linkedin": 0, "email": 0})
        self.refused_at("pilot_cap", config=config)

    def test_tenant_mismatch_prevents_the_call(self):
        self.campaign["org_unit"] = ""
        self.refused_at("tenancy")

    def test_a_stale_approval_prevents_the_call(self):
        """Change the words after approval; the fingerprint moves."""
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "rec-1":
                    row["cadence"]["dana-marsh"]["day3"]["approval"][
                        "fingerprint"] = "0000000000000000"
        self.rec = store.get("rec-1")
        self.contact = self.rec["contacts"][0]
        self.refused_at("approval")

    def test_no_approval_at_all_prevents_the_call(self):
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "rec-1":
                    row["cadence"]["dana-marsh"]["day3"].pop("approval")
        self.rec = store.get("rec-1")
        self.contact = self.rec["contacts"][0]
        self.refused_at("approval")

    def test_a_stale_readback_prevents_the_call(self):
        self.refused_at("readback", readback=self.readback(verified_at=STALE))

    def test_a_failing_readback_prevents_the_call(self):
        self.refused_at("readback",
                        readback=self.readback(verdict=configdiff.FAIL,
                                               failures=["note: mismatch"]))

    def test_no_readback_at_all_prevents_the_call(self):
        self.refused_at("readback", readback=None)

    def test_a_readback_that_is_not_a_dict_prevents_the_call(self):
        self.refused_at("readback", readback="PASS")

    def test_collision_appearing_after_staging_prevents_the_call(self):
        """The check is re-read at authorization time, not trusted from before."""
        with self.allow_killswitch(), self.allow_sender(), mock.patch.object(
                collision, "check_linkedin_profile",
                return_value=(collision.TOUCHED, {"note": "already talking"})):
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt()
        self.assertEqual(caught.exception.gate, "collision")
        self.assertEqual(self.spy.calls, [])

    def test_a_reply_making_them_in_sequence_prevents_the_call(self):
        with self.allow_killswitch(), self.allow_sender(), mock.patch.object(
                collision, "check_linkedin_profile",
                return_value=(collision.IN_SEQUENCE, {"note": "they replied"})):
            with self.assertRaises(executionguard.NotAuthorized):
                self.attempt()
        self.assertEqual(self.spy.calls, [])

    def test_an_unresolvable_collision_prevents_the_call(self):
        """UNKNOWN is never CLEAR."""
        with self.allow_killswitch(), self.allow_sender(), mock.patch.object(
                collision, "check_linkedin_profile",
                side_effect=collision.CollisionUnknown("too broad")):
            with self.assertRaises(collision.CollisionUnknown):
                self.attempt()
        self.assertEqual(self.spy.calls, [])

    def test_adding_a_sender_after_approval_prevents_the_call(self):
        """Phase 6: swapping the sender must invalidate the approval, and it
        does so BEFORE the sender-count gate is even reached."""
        self.campaign["senders"]["linkedin"].append({"id": 129531})
        self.refused_at("campaign_approval")

    def test_two_senders_are_refused_even_when_both_were_approved(self):
        """The sender gate itself, isolated by approving the change."""
        self.campaign["senders"]["linkedin"].append({"id": 129531})
        self.approve_campaign()
        self.refused_at("sender")

    def test_no_sender_on_the_campaign_prevents_the_call(self):
        self.campaign["senders"]["linkedin"] = []
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            with self.assertRaises(executionguard.NotAuthorized):
                self.attempt()
        self.assertEqual(self.spy.calls, [])

    def test_an_unknown_step_prevents_the_call(self):
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            with self.assertRaises(executionguard.NotAuthorized):
                self.attempt(step_key="day99")
        self.assertEqual(self.spy.calls, [])

    def test_a_bad_channel_prevents_the_call(self):
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt(channel="carrier_pigeon")
        self.assertEqual(caught.exception.gate, "channel")
        self.assertEqual(self.spy.calls, [])


class SuppressionIsReadAsBehaviourNotAsText(GuardTest):
    """The check was `"suppress" not in json.dumps(decided).lower()`, which
    refuses a CLEAR verdict reading "suppression: none" and passes a real
    suppression spelled differently."""

    def decided(self, *reasons):
        return {"verdict": "eligible" if not reasons else "blocked",
                "reasons": list(reasons), "reason": reasons[0] if reasons else None}

    def test_each_declared_suppression_reason_refuses(self):
        for reason in executionguard.SUPPRESSION_REASONS:
            with self.subTest(reason=reason):
                with self.allow_collision(), self.allow_killswitch(), \
                     self.allow_sender(), \
                     mock.patch.object(eligibility, "decide",
                                       return_value=self.decided(reason)):
                    with self.assertRaises(executionguard.NotAuthorized) as c:
                        self.attempt()
                self.assertIn(c.exception.gate, ("eligibility", "suppression"))
                self.assertEqual(self.spy.calls, [])

    def test_the_word_suppression_in_a_clear_reason_does_not_refuse(self):
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender(), \
             mock.patch.object(eligibility, "decide", return_value={
                 "verdict": "eligible", "reasons": [],
                 "note": "suppression: none; collision: clear"}):
            self.attempt()
        self.assertEqual(len(self.spy.calls), 1)

    def test_the_reasons_come_from_eligibilitys_own_constants(self):
        """Named rather than spelled, so the two cannot drift."""
        for reason in executionguard.SUPPRESSION_REASONS:
            self.assertTrue(str(reason).startswith("blocked:"), reason)


class TheCapCountsDurableRowsNotAPlanDict(GuardTest):
    """`pilotcaps.check(plan)` compares a caller's dict. Two callers each
    declaring one both passed, and together sent two. The ledger closes it."""

    def test_a_second_action_the_same_day_is_refused_by_the_cap(self):
        config = dict(self.config, daily_volume={"linkedin": 1, "email": 0})
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            self.attempt(config=config)
            self.assertEqual(len(self.spy.calls), 1)
            actionledger.settle("rec-1:dana-marsh:day3:linkedin",
                                actionledger.SENT)
            # A different person, so the ledger key differs and only the cap
            # can stop it. Their step must carry ITS OWN approval: copying the
            # first contact's cadence entry copies the first contact's
            # fingerprint, and the approval gate refuses that - correctly, as
            # the first version of this test discovered.
            with store.transaction() as rows:
                for row in rows:
                    if row["id"] == "rec-1":
                        second = dict(row["contacts"][0], key="sam-lee",
                                      name="Sam Lee", linkedin="samlee",
                                      email="sam@brightpath.test")
                        row["contacts"].append(second)
            rec = store.get("rec-1")
            second_step = cadence.expand_step(
                rec, rec["contacts"][1],
                executionguard._spec_for("day3"), config)
            with store.transaction() as rows:
                for row in rows:
                    if row["id"] == "rec-1":
                        row["cadence"]["sam-lee"] = {"day3": dict(
                            second_step,
                            approval={"by": "operator", "at": store.now(),
                                      "fingerprint": approval.fingerprint(
                                          second_step)})}
            rec = store.get("rec-1")
            # Adding a contact changes the campaign's lead set, so the campaign
            # approval has to be renewed or `campaign_approval` refuses first
            # and the cap is never reached.
            self.approve_campaign()
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt(config=config, rec=rec,
                             contact=rec["contacts"][1])
        self.assertEqual(caught.exception.gate, "pilot_cap")
        self.assertEqual(len(self.spy.calls), 1)

    def test_one_tenants_actions_do_not_consume_anothers_ceiling(self):
        """`count_on` had no workspace parameter, so every tenant counted
        together - in a system where tenancy outranks nearly everything.

        The tenant is the CLIENT SLUG. It was briefly EmailBison's numeric
        estate id, which is the wrong namespace twice over: two clients in one
        estate would share a ceiling, and one client worked from two estates
        would have its ceiling split with both halves passing.
        """
        actionledger.reserve(
            "other:contact:day3:linkedin", channel="linkedin",
            workspace="another-client", campaign_id="someone-else",
            sender_id=999, rec_id="other", contact_key="contact",
            step_key="day3", operation="op", fingerprint="fp")
        day = NOW.isoformat()
        self.assertEqual(actionledger.count_on(day, channel="linkedin"), 1)
        self.assertEqual(
            actionledger.count_on(day, channel="linkedin",
                                  workspace="productive"), 0)
        self.assertEqual(
            actionledger.count_on(day, channel="linkedin",
                                  workspace="another-client"), 1)

    def test_the_ledger_row_names_the_client_and_records_the_estate(self):
        """Both facts are needed: the tenant for counting, the provider estate
        as evidence of where the action was aimed."""
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            auth = self.attempt()
        row = actionledger.rows_for(auth.key)[-1]
        self.assertEqual(row["workspace"], "productive")
        self.assertEqual(row["provider_workspace"], WS)
        self.assertEqual(auth.workspace, "productive")

    def test_the_ledger_count_is_what_the_cap_reads(self):
        self.assertEqual(actionledger.count_on(NOW.isoformat(),
                                              channel="linkedin"), 0)
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            self.attempt()
        self.assertEqual(actionledger.count_on(NOW.isoformat(),
                                              channel="linkedin"), 1)


class AnUnsettledAttemptBlocksEveryRetry(GuardTest):
    """Never retry a prospect-facing write because the client saw no response."""

    def test_a_second_authorization_for_the_same_key_is_refused(self):
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            self.attempt()
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt()
        self.assertEqual(caught.exception.gate, "ledger")
        self.assertEqual(len(self.spy.calls), 1)

    def test_an_already_sent_key_is_refused_as_a_duplicate(self):
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            self.attempt()
            actionledger.settle("rec-1:dana-marsh:day3:linkedin",
                                actionledger.SENT)
            with self.assertRaises(executionguard.NotAuthorized):
                self.attempt()
        self.assertEqual(len(self.spy.calls), 1)

    def test_an_unresolved_key_is_blocked_forever_not_retried(self):
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            self.attempt()
            actionledger.settle("rec-1:dana-marsh:day3:linkedin",
                                actionledger.UNRESOLVED,
                                why="provider truth could not settle it")
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt()
        self.assertEqual(caught.exception.gate, "ledger")
        self.assertEqual(len(self.spy.calls), 1)

    def test_a_failed_attempt_may_be_retried(self):
        """FAILED means the provider refused before acting. That is safe."""
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            self.attempt()
            actionledger.settle("rec-1:dana-marsh:day3:linkedin",
                                actionledger.FAILED, why="provider 400")
            self.attempt()
        self.assertEqual(len(self.spy.calls), 2)


class ChangingAnythingMaterialInvalidatesApproval(GuardTest):
    """Phase 6. `approval.fingerprint(step)` covers the WORDS and nothing else.

    Sender, provider campaign, list, tenant, limits and the lead set all change
    what reaches a prospect and none of them touch it. `campaigns.material()`
    covers exactly those, so the campaign-level approval is what catches them.
    """

    def changing(self, **fields):
        for name, value in fields.items():
            self.campaign[name] = value
        self.refused_at("campaign_approval")

    def test_changing_the_provider_campaign_blocks(self):
        self.changing(heyreach_campaign_id=594060)

    def test_changing_the_provider_list_blocks(self):
        """Re-pointing at a big production list must not keep an approval."""
        self.changing(heyreach_list_id=605355)

    def test_changing_the_tenant_blocks(self):
        self.changing(org_unit=999999)

    def test_changing_the_limits_blocks(self):
        self.changing(daily_volume={"email": 0, "linkedin": 50})

    def test_changing_the_provider_delay_blocks(self):
        self.changing(provider_delays=[["DAY", 3]])

    def test_changing_the_expected_status_blocks(self):
        self.changing(provider_status_expected="IN_PROGRESS")

    def test_changing_the_record_set_blocks(self):
        self.changing(record_ids=["rec-1", "rec-2"])

    def test_changing_the_angle_blocks(self):
        """The angle selects the words, so this moves both fingerprints."""
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "rec-1":
                    row["contacts"][0]["angle"] = "delivery"
        self.rec = store.get("rec-1")
        self.contact = self.rec["contacts"][0]
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt()
        self.assertIn(caught.exception.gate, ("approval", "campaign_approval"))
        self.assertEqual(self.spy.calls, [])

    def test_changing_the_lead_identity_blocks(self):
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "rec-1":
                    row["contacts"][0]["linkedin"] = "someone-else"
        self.rec = store.get("rec-1")
        self.contact = self.rec["contacts"][0]
        self.refused_at("campaign_approval")

    def test_a_campaign_never_approved_at_all_blocks(self):
        self.campaign["approval"] = None
        self.refused_at("campaign_approval")

    def test_a_rejected_campaign_blocks(self):
        self.campaign["approval"] = dict(self.campaign["approval"],
                                        action="reject")
        self.refused_at("campaign_approval")

    def test_a_volatile_counter_does_not_invalidate_approval(self):
        """The other half: a field that cannot change what a prospect receives
        must NOT move the fingerprint, or every read would revoke consent."""
        before = campaigns.fingerprint(self.campaign, store.load(), self.config)
        self.campaign["log"] = [{"at": store.now(), "note": "read"}]
        self.campaign["events"] = [{"type": "looked_at"}]
        self.campaign["started_at"] = store.now()
        after = campaigns.fingerprint(self.campaign, store.load(), self.config)
        self.assertEqual(before, after)


class TheDryRunReservesNothing(GuardTest):
    def test_dry_run_passes_the_gates_without_reserving(self):
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            auth = executionguard.dry_run(
                operation="linkedin_connection_request", channel="linkedin",
                campaign=self.campaign, rec=self.rec, contact=self.contact,
                step_key="day3", workspace=WS, config=self.config, now=NOW,
                readback=self.readback())
        self.assertNotIn("reserved", auth.gates)
        self.assertEqual(actionledger.load(), [])


class TheWriteLayerRefusesAnythingButAnAuthorization(GuardTest):
    def test_a_dict_is_not_an_authorization(self):
        with self.assertRaises(AssertionError):
            self.spy.write({"key": "rec-1:dana-marsh:day3:linkedin",
                            "gates": ("all", "of", "them")}, note=NOTE)
        self.assertEqual(self.spy.calls, [])

    def test_none_is_not_an_authorization(self):
        with self.assertRaises(AssertionError):
            self.spy.write(None, note=NOTE)
        self.assertEqual(self.spy.calls, [])


if __name__ == "__main__":
    unittest.main()


class TheSenderGateChecksTheProviderSeat(GuardTest):
    """The gate's subject is the PROVIDER seat, not an internal human id.

    THE DEFECT THIS PINS. The first version called
    `senderidentity.require_sender(client, sender_id)`. That function resolves a
    HUMAN sender id, and the id a campaign carries is a `provider_account_id`.
    Worse, every inventoried LinkedIn seat has `sender_id: None` on purpose -
    PRODUCT-GAPS 33d, neither provider exposes who owns an inbox - so the lookup
    could never succeed for any seat, and the gate refused the correctly
    configured canary with a message claiming its ownership was unestablished.

    That is the shape of failure this repository keeps producing: a check that
    computes the wrong thing and refuses, which reads as safety and is actually
    a guard that has stopped guarding, because it now says no to everything and
    so distinguishes nothing.
    """

    def seat(self, **over):
        from src import senderidentity
        row = dict(kind=senderidentity.LINKEDIN_ACCOUNT, workspace="productive",
                   account_id="li-116968", sender_id=None, provider="heyreach",
                   provider_account_id="116968",
                   profile_url="https://www.linkedin.com/in/mina-ruzicic",
                   active=True, daily_limit=40, health="ok")
        row.update(over)
        with senderidentity.transaction() as rows:
            rows[:] = [r for r in rows
                       if r.get("kind") != senderidentity.LINKEDIN_ACCOUNT]
            rows.append(row)

    def test_a_seat_with_no_human_owner_still_passes(self):
        # The canary's exact shape. `sender_id: None` is canonical, not missing
        # data, so it must not be read as an unattributable sender.
        self.seat(sender_id=None)
        with self.allow_collision(), self.allow_killswitch():
            self.assertIn("sender", self.attempt().gates)

    def test_a_seat_nobody_inventoried_is_refused(self):
        self.seat(provider_account_id="999999")
        self.assertIn("roster", self.refused_at("sender").why)

    def test_a_deactivated_seat_is_refused(self):
        self.seat(active=False)
        self.assertIn("not active", self.refused_at("sender").why)

    def test_an_unhealthy_seat_is_refused(self):
        self.seat(health="disconnected")
        self.assertIn("disconnected", self.refused_at("sender").why)

    def test_another_client_seat_does_not_satisfy_this_client(self):
        # The tenancy half. A seat with the right provider id in the WRONG
        # workspace must not vouch for this client's send, or one tenant's
        # roster licenses another's outreach.
        self.seat(workspace="mediaboard")
        self.assertIn("roster", self.refused_at("sender").why)
