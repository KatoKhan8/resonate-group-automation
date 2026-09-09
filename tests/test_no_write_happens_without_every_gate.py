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
                 collision, configdiff, executionguard, killswitch, store)

from tests.base import QueueTest

NOTE = ("hi Dana, i work with Design Services teams on utilisation. "
        "curious how Brightpath handles it at your size. happy to connect.")
WS = 10
NOW = datetime.datetime(2026, 9, 9, 12, 0, 0, tzinfo=datetime.timezone.utc)
FRESH = "2026-09-09T11:59:00+00:00"
STALE = "2026-09-09T11:30:00+00:00"


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

    def readback(self, verdict=configdiff.PASS, verified_at=FRESH,
                 failures=()):
        return {"diff": {"verdict": verdict, "failures": list(failures)},
                "verified_at": verified_at}

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


class TheHappyPathIsAuthorized(GuardTest):
    def test_a_fully_gated_action_authorizes_and_writes_once(self):
        with self.allow_collision(), self.allow_killswitch():
            auth = self.attempt()
        self.assertEqual(len(self.spy.calls), 1)
        self.assertEqual(auth.key, "rec-1:dana-marsh:day3:linkedin")
        self.assertIn("killswitch", auth.gates)
        self.assertIn("reserved", auth.gates)

    def test_the_ledger_recorded_the_attempt_before_the_write(self):
        with self.allow_collision(), self.allow_killswitch():
            self.attempt()
        self.assertEqual(actionledger.state_of("rec-1:dana-marsh:day3:linkedin"),
                         actionledger.ATTEMPTED)

    def test_one_authorization_cannot_be_spent_twice(self):
        with self.allow_collision(), self.allow_killswitch():
            auth = self.authorize()
            self.spy.write(auth, note=NOTE)
            with self.assertRaises(executionguard.NotAuthorized):
                self.spy.write(auth, note=NOTE)
        self.assertEqual(len(self.spy.calls), 1)


class EachGateStopsTheProviderCallEntirely(GuardTest):
    """The property that matters: `spy.calls == []`, not a handled error."""

    def refused_at(self, gate, **over):
        with self.allow_collision(), self.allow_killswitch():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt(**over)
        self.assertEqual(caught.exception.gate, gate,
                         f"expected gate {gate!r}, got "
                         f"{caught.exception.gate!r}: {caught.exception.why}")
        self.assertEqual(self.spy.calls, [], "a provider call was made anyway")
        return caught.exception

    def test_killswitch_off_prevents_the_call(self):
        with self.allow_collision():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt()
        self.assertEqual(caught.exception.gate, "killswitch")
        self.assertEqual(self.spy.calls, [])

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
        with self.allow_killswitch(), mock.patch.object(
                collision, "check_linkedin_profile",
                return_value=(collision.TOUCHED, {"note": "already talking"})):
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt()
        self.assertEqual(caught.exception.gate, "collision")
        self.assertEqual(self.spy.calls, [])

    def test_a_reply_making_them_in_sequence_prevents_the_call(self):
        with self.allow_killswitch(), mock.patch.object(
                collision, "check_linkedin_profile",
                return_value=(collision.IN_SEQUENCE, {"note": "they replied"})):
            with self.assertRaises(executionguard.NotAuthorized):
                self.attempt()
        self.assertEqual(self.spy.calls, [])

    def test_an_unresolvable_collision_prevents_the_call(self):
        """UNKNOWN is never CLEAR."""
        with self.allow_killswitch(), mock.patch.object(
                collision, "check_linkedin_profile",
                side_effect=collision.CollisionUnknown("too broad")):
            with self.assertRaises(collision.CollisionUnknown):
                self.attempt()
        self.assertEqual(self.spy.calls, [])

    def test_two_senders_on_the_campaign_prevents_the_call(self):
        self.campaign["senders"]["linkedin"].append({"id": 129531})
        with self.allow_collision(), self.allow_killswitch():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt()
        self.assertEqual(caught.exception.gate, "sender")
        self.assertEqual(self.spy.calls, [])

    def test_no_sender_on_the_campaign_prevents_the_call(self):
        self.campaign["senders"]["linkedin"] = []
        with self.allow_collision(), self.allow_killswitch():
            with self.assertRaises(executionguard.NotAuthorized):
                self.attempt()
        self.assertEqual(self.spy.calls, [])

    def test_an_unknown_step_prevents_the_call(self):
        with self.allow_collision(), self.allow_killswitch():
            with self.assertRaises(executionguard.NotAuthorized):
                self.attempt(step_key="day99")
        self.assertEqual(self.spy.calls, [])

    def test_a_bad_channel_prevents_the_call(self):
        with self.allow_collision(), self.allow_killswitch():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt(channel="carrier_pigeon")
        self.assertEqual(caught.exception.gate, "channel")
        self.assertEqual(self.spy.calls, [])


class TheCapCountsDurableRowsNotAPlanDict(GuardTest):
    """`pilotcaps.check(plan)` compares a caller's dict. Two callers each
    declaring one both passed, and together sent two. The ledger closes it."""

    def test_a_second_action_the_same_day_is_refused_by_the_cap(self):
        config = dict(self.config, daily_volume={"linkedin": 1, "email": 0})
        with self.allow_collision(), self.allow_killswitch():
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
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt(config=config, rec=rec,
                             contact=rec["contacts"][1])
        self.assertEqual(caught.exception.gate, "pilot_cap")
        self.assertEqual(len(self.spy.calls), 1)

    def test_the_ledger_count_is_what_the_cap_reads(self):
        self.assertEqual(actionledger.count_on(NOW.isoformat(),
                                              channel="linkedin"), 0)
        with self.allow_collision(), self.allow_killswitch():
            self.attempt()
        self.assertEqual(actionledger.count_on(NOW.isoformat(),
                                              channel="linkedin"), 1)


class AnUnsettledAttemptBlocksEveryRetry(GuardTest):
    """Never retry a prospect-facing write because the client saw no response."""

    def test_a_second_authorization_for_the_same_key_is_refused(self):
        with self.allow_collision(), self.allow_killswitch():
            self.attempt()
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.attempt()
        self.assertEqual(caught.exception.gate, "ledger")
        self.assertEqual(len(self.spy.calls), 1)

    def test_an_already_sent_key_is_refused_as_a_duplicate(self):
        with self.allow_collision(), self.allow_killswitch():
            self.attempt()
            actionledger.settle("rec-1:dana-marsh:day3:linkedin",
                                actionledger.SENT)
            with self.assertRaises(executionguard.NotAuthorized):
                self.attempt()
        self.assertEqual(len(self.spy.calls), 1)

    def test_an_unresolved_key_is_blocked_forever_not_retried(self):
        with self.allow_collision(), self.allow_killswitch():
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
        with self.allow_collision(), self.allow_killswitch():
            self.attempt()
            actionledger.settle("rec-1:dana-marsh:day3:linkedin",
                                actionledger.FAILED, why="provider 400")
            self.attempt()
        self.assertEqual(len(self.spy.calls), 2)


class TheDryRunReservesNothing(GuardTest):
    def test_dry_run_passes_the_gates_without_reserving(self):
        with self.allow_collision(), self.allow_killswitch():
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
