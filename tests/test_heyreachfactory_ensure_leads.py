"""ensure_leads: the caller that puts a real lead into a HeyReach campaign.

TASK-019. Behavioural tests against a fake transport. Each gate is tested
by name, and the transport is verified to never be reached when a gate
fires. The readback is the verdict: a readback that disagrees raises.

Tests required by the task:
  - a contact who fails suppression, DNC, collision or the killswitch is
    refused BY NAME and the transport is never reached;
  - a batch where one lead cannot fill one variable refuses the WHOLE push;
  - a tenant mismatch refuses before the transport;
  - re-running pushes nobody twice;
  - a readback that disagrees with what was asked for RAISES;
  - a transport that answers 200 with a body nobody can classify does not
    become a success.
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import (campaigns, clients, collision, configdiff, executionguard,
                 heyreachfactory, killswitch, providerwrites, store)
from src.providers import bison, heyreach


# ----------------------------------------------- fixture helpers

def _approved_step(key, day, action, *, note=None):
    """One approved LinkedIn cadence step."""
    step = {"key": key, "day": day, "channel": "linkedin",
            "linkedin_action": action, "generated": True,
            "approval": {"fingerprint": f"fp-{key}",
                         "at": "2026-09-14T00:00:00"}}
    if note is not None:
        step["note"] = note
    return step


def _full_cadence(contact_key="pat"):
    """A complete LinkedIn cadence with every required role covered."""
    return {
        contact_key: {
            "li1": _approved_step("li1", 1, "connect",
                                  note="Hi, would love to connect."),
            "li2": _approved_step("li2", 3, "message",
                                  note="Thanks for connecting."),
            "li3": _approved_step("li3", 6, "message",
                                  note="One thing that might help."),
            "li4": _approved_step("li4", 10, "message",
                                  note="The teams closest to your size."),
            "li5": _approved_step("li5", 15, "message",
                                  note="Happy to share a case study."),
        }
    }


def _fallback_config():
    """Client config with fallbacks for every required role."""
    return {
        "name": "productive",
        "linkedin_sequence": {
            "fallbacks": {
                "connection_note": "Hi there, would love to connect.",
                "connected_1": "Thanks for connecting!",
                "connected_2": "Good to be in touch.",
                "connected_3": "Following up on our conversation.",
                "connected_4": "One last thought.",
                "message_2": "Glad we connected.",
                "message_3": "Thought this might help.",
                "message_4": "Worth a look?",
            }
        },
        "heyreach": {"org_unit_id": "12345", "default_account_id": 99},
    }


def _make_record(rec_id="acme", contact_key="pat", *, domain="acme.test",
                 client="productive", linkedin=None):
    """A record with one contact and a full LinkedIn cadence.

    IT CARRIES A COMPANY NAME, and it did not. `cadence.company_name` refuses
    a name that is domain-shaped - "refusing to address a prospect by their
    own hostname" - so these records could never have been pushed in
    production, and eight tests only passed because `authorize` was mocked and
    nothing ever expanded their copy.

    A fixture that cannot survive the path it is testing is a fixture that
    hides the first real defect it meets.
    """
    url = linkedin or f"https://www.linkedin.com/in/{contact_key}"
    return {
        "id": rec_id, "client": client, "domain": domain,
        "company": "Kestrel Wharf Studio",
        "company_facts": {"name": "Kestrel Wharf Studio"},
        "contacts": [{"key": contact_key, "name": "Pat Okafor",
                      "linkedin": url}],
        "cadence": _full_cadence(contact_key),
    }


def _make_campaign(campaign_id="test-li-campaign", client="productive",
                   record_ids=None):
    """A campaign row ready for ensure_leads."""
    return {
        "campaign_id": campaign_id,
        "client": client,
        "name": "LinkedIn test",
        "status": "draft",
        "heyreach_campaign_id": "599020",
        "record_ids": record_ids or ["acme"],
        "cadence_version": "productive_li_heavy_v1",
    }


# The killswitch mock that says "on" for every workspace.
_KS_ON = {"sending": True, "why": "on"}


class _NoPatchOutlivesItsTest(unittest.TestCase):
    """Every `mock.patch` started in this module stops when its test ends.

    Several tests here stop only SOME of the patches they start, and any test
    that fails before its inline `.stop()` leaves the rest installed for the
    remainder of the PROCESS - silently disabling the real function for every
    later test in the run.

    That is not hypothetical. `TheRealAuthorizationGateIsReachable` was
    written to prove that the genuine `executionguard.authorize` refuses a
    contact with no approved copy. Run alone it passes. Run after this
    module's other classes it reported "Exception not raised", because
    `authorize` was still mocked from an earlier test - which is precisely the
    failure the test existed to rule out.

    `mock.patch.stopall()` stops everything started with `.start()`, so it
    does not matter which test forgot which one. `tests/base.py` makes the
    same argument for `addCleanup` over `tearDown`.
    """

    @staticmethod
    def _stop_everything():
        """Tolerant, because several tests stop some of their own patches.

        `stopall` raises on a patcher that is already stopped, and stopping
        one twice is exactly what a test that cleans up after itself will
        cause. The point of this is that NOTHING survives the test, not that
        every stop is the first one.
        """
        try:
            mock.patch.stopall()
        except RuntimeError:
            pass

    def setUp(self):
        super().setUp()
        self.addCleanup(self._stop_everything)


class _EnsureLeadsTestBase(_NoPatchOutlivesItsTest):
    """Temp estate for ensure_leads tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-ensure-leads-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        self.campaign_file = os.path.join(self.tmp, "work", "campaigns.jsonl")
        self.ledger_file = os.path.join(self.tmp, "work",
                                        "action_ledger.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._env = {}
        for k in ("QUEUE", "CAMPAIGNS", "ACTION_LEDGER"):
            self._env[k] = os.environ.get(k)
        os.environ["QUEUE"] = self.queue
        os.environ["CAMPAIGNS"] = self.campaign_file
        os.environ["ACTION_LEDGER"] = self.ledger_file
        # Default killswitch mock: on. Individual tests override.
        self._ks_patch = mock.patch.object(killswitch, "workspace_state",
                                           return_value=_KS_ON)
        self._ks_patch.start()
        # Default gate-6 mock: the campaign is DRAFT, so it is proven unable
        # to send and the gate lets the test reach whatever it is actually
        # testing. Gate 6 (TASK-125) sits immediately before the provider
        # write, so every test that exercises the write path now passes
        # through it; without this they fail on an unreadable campaign status
        # instead of on the thing they assert. A test that wants to exercise
        # the gate itself overrides this - see test_campaign_cannot_send.
        self._draft_patch = mock.patch.object(
            heyreach, "campaign_cannot_send", return_value=True)
        self._draft_patch.start()
        # addCleanup, for the reason this file already gives below: a patch
        # that outlives its test leaks into every test that runs after it.
        # Without this, the whole of test_campaign_cannot_send sees
        # campaign_cannot_send permanently returning True and 12 of its tests
        # fail - in a suite where each module passes alone.
        self.addCleanup(self._draft_patch.stop)
        # THE EMAILBISON WORKSPACE, because the collision gate reads the
        # client's own EMAIL estate even for a LinkedIn campaign - the account
        # is the unit, so somebody mid-sequence by email is a reason not to
        # open a second channel at that company. `bound_workspace()` is a real
        # provider read and there are no credentials here, so it is stubbed
        # for every test in this module rather than in the handful that
        # happened to reach it.
        self._ws_patch = mock.patch.object(
            bison, "bound_workspace", return_value={"id": 10,
                                                    "name": "PRODUCTIVE"})
        self._ws_patch.start()
        self.addCleanup(self._ws_patch.stop)
        # THE LINKEDIN SEAT. `_seat_for` reads the canonical row first and
        # falls back to the provider's `campaignAccountIds`, because a lead
        # pushed without a seat is a lead assigned to nobody - and the seat is
        # who the prospect sees the message come from. Both are reads these
        # tests have no credentials for.
        self._seat_patch = mock.patch.object(
            heyreach, "campaign_read",
            return_value={"id": 599020, "campaignAccountIds": [174892],
                          "organizationUnitId": 118832})
        self._seat_patch.start()
        self.addCleanup(self._seat_patch.stop)
        # addCleanup, NOT tearDown. `unittest` does not call tearDown when a
        # setUp raises, and an inline `.stop()` never runs if the test fails
        # before it - either way the mock stays installed for the rest of the
        # process and silently disables the real function for every later
        # test. That is not hypothetical here: with these patches leaking,
        # `TheRealAuthorizationGateIsReachable` saw a mocked
        # `executionguard.authorize` and reported that the real gate had not
        # refused, when run alone it passes. `tests/base.py` documents the
        # same trap for the same reason.
        self.addCleanup(self._ks_patch.stop)

    def tearDown(self):
        self._ks_patch.stop()
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed(self, recs, campaign):
        store.save(recs)
        campaigns.save([campaign])

    def _config(self):
        return _fallback_config()

    def _patch_external(self, *, membership_found=None):
        """Mock the provider calls. Returns the mocks as a dict."""
        if membership_found is None:
            membership_found = set()
        # Build a fake Readback for configdiff.compare_heyreach.
        fake_readback = configdiff.Readback(
            diff={"verdict": configdiff.PASS, "failures": []},
            approved={}, provider={},
            campaign_id="test-li-campaign", channel="linkedin",
            provider_campaign_id=599020,
            verified_at=store.now())
        # Build a fake Authorization for executionguard.authorize.
        fake_auth = executionguard.Authorization(
            key="fake-auth-key", operation=providerwrites.LINKEDIN_ADD_LEAD,
            channel="linkedin", workspace="productive",
            campaign_id="test-li-campaign", sender_id="0",
            rec_id="acme", contact_key="pat", step_key="day3",
            fingerprint="fp-li1", gates=("tenancy", "approval", "readback",
                                         "eligibility", "suppression", "copy",
                                         "claims", "fatigue", "collision",
                                         "account_collision", "sender", "cap",
                                         "killswitch"),
            at=store.now())
        mocks = {
            "tenant": mock.patch.object(heyreach, "check_tenant",
                                        return_value=True),
            "readback": mock.patch.object(
                heyreach, "readback_membership",
                return_value={"found": membership_found, "missing": set(),
                              "total": len(membership_found),
                              "per_lead": []}),
            "perform": mock.patch.object(providerwrites, "perform"),
            "collision": mock.patch.object(
                collision, "check_account",
                return_value={"domain": "acme.test", "verdict": "clear",
                              "anyone_in_sequence": False,
                              "emails_sent_total": 0, "leads": 0,
                              "people": [], "unknown_statuses": [],
                              "any_bounce": False,
                              "workspace": "productive"}),
            "compare_heyreach": mock.patch.object(
                configdiff, "compare_heyreach", return_value=fake_readback),
            "authorize": mock.patch.object(
                executionguard, "authorize", return_value=fake_auth),
        }
        return mocks


def _auth_patches():
    """The two patches every `ensure_leads(live=True)` test needs.

    `executionguard.authorize` and `configdiff.compare_heyreach` are on the
    live path, so a test that does not patch them reaches the real gate. Two
    tests here omitted both and passed anyway - because an earlier class's
    patches were leaking - and started failing honestly the moment that leak
    was closed. Sharing them makes the omission impossible to repeat.
    """
    fake_readback = configdiff.Readback(
        diff={"verdict": configdiff.PASS, "failures": []},
        approved={}, provider={},
        campaign_id="test-li-campaign", channel="linkedin",
        provider_campaign_id=599020, verified_at=store.now())
    fake_auth = executionguard.Authorization(
        key="fake-auth-key", operation=providerwrites.LINKEDIN_ADD_LEAD,
        channel="linkedin", workspace="productive",
        campaign_id="test-li-campaign", sender_id="0",
        rec_id="acme", contact_key="pat", step_key="li1",
        fingerprint="fp-li1",
        gates=("tenancy", "approval", "readback", "eligibility",
               "suppression", "copy", "claims", "fatigue", "collision",
               "account_collision", "sender", "cap", "killswitch"),
        at=store.now())
    return {
        "compare_heyreach": mock.patch.object(
            configdiff, "compare_heyreach", return_value=fake_readback),
        "authorize": mock.patch.object(
            executionguard, "authorize", return_value=fake_auth),
    }


def _start_all(mocks, case=None):
    """Start every patch, and register its stop with the TEST CASE.

    `case.addCleanup` rather than an inline `_stop_all` at the end of the
    test: a test that fails before reaching the stop leaves the mock
    installed for the rest of the PROCESS, silently disabling the real
    function for every later test. That happened here -
    `TheRealAuthorizationGateIsReachable` saw a mocked
    `executionguard.authorize` and reported that the real gate had not
    refused; run alone it passes. `tests/base.py` documents the same trap.

    `case` is optional only so existing callers keep working; pass it.
    """
    for m in mocks.values():
        m.start()
        if case is not None:
            case.addCleanup(m.stop)
    return mocks


def _stop_all(mocks):
    for m in mocks.values():
        m.stop()


# =============================================== killswitch

class KillswitchRefuses(_EnsureLeadsTestBase):
    """A contact who fails the killswitch is refused BY NAME."""

    def test_killswitch_off_refuses_before_transport(self):
        self._ks_patch.stop()
        rec = _make_record()
        camp = _make_campaign()
        self._seed([rec], camp)

        transport = mock.MagicMock()
        with mock.patch.object(killswitch, "workspace_state",
                               return_value={"sending": False,
                                             "why": "switched off"}), \
             mock.patch.object(heyreach, "add_leads_to_campaign",
                               transport):
            with self.assertRaises(heyreachfactory.FactoryRefused) as ctx:
                heyreachfactory.ensure_leads(
                    "test-li-campaign", config=self._config())
        self.assertIn("productive", str(ctx.exception))
        transport.assert_not_called()


# =============================================== suppression / DNC

class SuppressionRefuses(_EnsureLeadsTestBase):
    """A contact who fails suppression is refused BY NAME."""

    def test_suppressed_contact_refused_by_name(self):
        rec = _make_record()
        rec["contacts"][0]["suppressed"] = True
        camp = _make_campaign()
        self._seed([rec], camp)

        transport = mock.MagicMock()
        mocks = _start_all(self._patch_external())
        try:
            with mock.patch.object(heyreach, "add_leads_to_campaign",
                                   transport):
                with self.assertRaises(heyreachfactory.FactoryRefused) as ctx:
                    heyreachfactory.ensure_leads(
                        "test-li-campaign", config=self._config(), live=True)
        finally:
            _stop_all(mocks)
        text = str(ctx.exception)
        self.assertIn("pat", text)
        self.assertIn("blocked", text)
        transport.assert_not_called()

    def test_dnc_contact_refused_by_name(self):
        rec = _make_record()
        rec["contacts"][0]["unsubscribed"] = True
        camp = _make_campaign()
        self._seed([rec], camp)

        transport = mock.MagicMock()
        mocks = _start_all(self._patch_external())
        try:
            with mock.patch.object(heyreach, "add_leads_to_campaign",
                                   transport):
                with self.assertRaises(heyreachfactory.FactoryRefused) as ctx:
                    heyreachfactory.ensure_leads(
                        "test-li-campaign", config=self._config(), live=True)
        finally:
            _stop_all(mocks)
        text = str(ctx.exception)
        self.assertIn("pat", text)
        transport.assert_not_called()


# =============================================== collision

class CollisionRefuses(_EnsureLeadsTestBase):
    """A contact whose account collides is refused BY NAME."""

    def test_account_stop_refused_by_name(self):
        rec = _make_record()
        camp = _make_campaign()
        self._seed([rec], camp)

        fake_account = {"domain": "acme.test", "verdict": "in_sequence",
                        "anyone_in_sequence": True, "emails_sent_total": 3,
                        "leads": 1, "people": [], "unknown_statuses": [],
                        "any_bounce": False, "workspace": "productive"}
        transport = mock.MagicMock()
        mocks = _start_all(self._patch_external())
        mocks["collision"].stop()
        try:
            with mock.patch.object(collision, "check_account",
                                   return_value=fake_account), \
                 mock.patch.object(heyreach, "add_leads_to_campaign",
                                   transport):
                with self.assertRaises(heyreachfactory.FactoryRefused) \
                        as ctx:
                    heyreachfactory.ensure_leads(
                        "test-li-campaign", config=self._config(), live=True)
        finally:
            mocks["tenant"].stop()
            mocks["readback"].stop()
            mocks["perform"].stop()
        text = str(ctx.exception)
        self.assertIn("pat", text)
        self.assertIn("stop", text.lower())
        transport.assert_not_called()


# =============================================== tenant mismatch

class TenantMismatchRefuses(_EnsureLeadsTestBase):
    """A tenant mismatch refuses before the transport."""

    def test_tenant_mismatch_refuses_before_transport(self):
        rec = _make_record()
        camp = _make_campaign()
        self._seed([rec], camp)

        transport = mock.MagicMock()
        mocks = _start_all(self._patch_external())
        mocks["tenant"].stop()
        try:
            with mock.patch.object(
                    heyreach, "check_tenant",
                    side_effect=heyreach.ProviderError(
                        "heyreach check_tenant: campaign 599020 belongs to "
                        "org '99999' and this client is configured for "
                        "'12345'")), \
                 mock.patch.object(heyreach, "add_leads_to_campaign",
                                   transport):
                with self.assertRaises(heyreach.ProviderError):
                    heyreachfactory.ensure_leads(
                        "test-li-campaign", config=self._config(), live=True)
        finally:
            mocks["readback"].stop()
            mocks["perform"].stop()
            mocks["collision"].stop()
        transport.assert_not_called()


# =============================================== unsupported sequence

class UnsupportedSequenceRefuses(_EnsureLeadsTestBase):
    """A batch where one lead cannot fill one variable refuses the WHOLE push.

    The _plan function already filters out contacts with missing copy.
    This test proves that refuse_unsupported_sequence is called on the
    rows actually being pushed, catching a variable gap that _plan's
    filter did not catch.
    """

    def test_batch_with_missing_variable_refuses_whole_push(self):
        rec = _make_record()
        camp = _make_campaign()
        self._seed([rec], camp)

        real_plan = heyreachfactory._plan

        def _plan_with_gap(campaign, recs, config, **kw):
            result = real_plan(campaign, recs, config, **kw)
            for c in result["pushable"]:
                c["custom_fields"].pop("connected_4", None)
            return result

        transport = mock.MagicMock()
        mocks = _start_all(self._patch_external())
        try:
            with mock.patch.object(heyreachfactory, "_plan",
                                   side_effect=_plan_with_gap), \
                 mock.patch.object(heyreach, "add_leads_to_campaign",
                                   transport):
                with self.assertRaises(heyreach.SequenceRefused) as ctx:
                    heyreachfactory.ensure_leads(
                        "test-li-campaign", config=self._config(), live=True)
        finally:
            _stop_all(mocks)
        self.assertIn("connected_4", str(ctx.exception))
        transport.assert_not_called()


# =============================================== idempotency

class Idempotent(_EnsureLeadsTestBase):
    """Re-running pushes nobody twice."""

    def test_rerun_pushes_nobody_twice(self):
        rec = _make_record()
        camp = _make_campaign()
        self._seed([rec], camp)

        url = rec["contacts"][0]["linkedin"].lower()
        perform_mock = mock.MagicMock()
        mocks = {
            "tenant": mock.patch.object(heyreach, "check_tenant",
                                        return_value=True),
            "readback": mock.patch.object(
                heyreach, "readback_membership",
                return_value={"found": {url}, "missing": set(),
                              "total": 1, "per_lead": [{}]}),
            "perform": mock.patch.object(providerwrites, "perform",
                                         perform_mock),
            "collision": mock.patch.object(
                collision, "check_account",
                return_value={"domain": "acme.test", "verdict": "clear",
                              "anyone_in_sequence": False,
                              "emails_sent_total": 0, "leads": 0,
                              "people": [], "unknown_statuses": [],
                              "any_bounce": False,
                              "workspace": "productive"}),
        }
        _start_all(mocks)
        try:
            report = heyreachfactory.ensure_leads(
                "test-li-campaign", config=self._config(), live=True)
        finally:
            _stop_all(mocks)

        perform_mock.assert_not_called()
        self.assertTrue(any("already members" in d
                            for d in report["did"]))

    def test_dry_run_does_not_call_transport(self):
        rec = _make_record()
        camp = _make_campaign()
        self._seed([rec], camp)

        transport = mock.MagicMock()
        mocks = _start_all(self._patch_external())
        try:
            with mock.patch.object(heyreach, "add_leads_to_campaign",
                                   transport):
                report = heyreachfactory.ensure_leads(
                    "test-li-campaign", config=self._config(), live=False)
        finally:
            _stop_all(mocks)
        transport.assert_not_called()
        self.assertTrue(any("dry run" in d for d in report["did"]))


# =============================================== readback disagreement

class ReadbackDisagrees(_EnsureLeadsTestBase):
    """A readback that disagrees with what was asked for RAISES."""

    def test_readback_missing_lead_raises(self):
        rec = _make_record()
        camp = _make_campaign()
        self._seed([rec], camp)

        url = rec["contacts"][0]["linkedin"].lower()

        def _readback_fail(pid, urls):
            return {"found": set(), "missing": {url},
                    "total": 0, "per_lead": []}

        mocks = {
            "tenant": mock.patch.object(heyreach, "check_tenant",
                                        return_value=True),
            "readback": mock.patch.object(heyreach, "readback_membership",
                                          side_effect=_readback_fail),
            "collision": mock.patch.object(
                collision, "check_account",
                return_value={"domain": "acme.test", "verdict": "clear",
                              "anyone_in_sequence": False,
                              "emails_sent_total": 0, "leads": 0,
                              "people": [], "unknown_statuses": [],
                              "any_bounce": False,
                              "workspace": "productive"}),
        }
        mocks.update(_auth_patches())
        _start_all(mocks, self)

        def _perform_side_effect(*args, **kwargs):
            rb = kwargs.get("readback")
            if callable(rb):
                observed = rb()
                if observed.get("missing"):
                    raise providerwrites.WriteUnverified(
                        f"readback says missing: {observed['missing']}")
            return {"class": "accepted"}

        try:
            with mock.patch.object(providerwrites, "perform",
                                   side_effect=_perform_side_effect):
                with self.assertRaises(providerwrites.WriteUnverified):
                    heyreachfactory.ensure_leads(
                        "test-li-campaign", config=self._config(), live=True)
        finally:
            _stop_all(mocks)


# =========================================== what perform is actually told

class WhatTheFactoryHandsTheDoor(_EnsureLeadsTestBase):
    """The two arguments the door cannot work without, asserted on the call.

    Every other test in this module mocks `providerwrites.perform` and looks
    at what happened around it. None looked at what it was HANDED, and two
    defects lived in that blind spot:

      - `provider_campaign_id` was added to `perform` so the destination's
        state could be re-read at the moment of the write. Deleting it from
        this factory's call broke nothing in this module - the write would
        have refused in production and no test would have said so first.

      - the transport closure took the WHOLE batch while the loop calls
        `perform` once per contact, so N contacts meant N writes each
        carrying all N leads. Every test here pushes a single contact, where
        N squared and N are the same number.

    Both are asserted here, on the arguments, with two contacts.
    """

    def _push_two(self):
        """Push two contacts live and return the recorded perform calls."""
        recs = [_make_record("acme", "pat"),
                _make_record("beta", "sam", domain="beta.test")]
        camp = _make_campaign(record_ids=["acme", "beta"])
        self._seed(recs, camp)

        perform_mock = mock.MagicMock(return_value={"class": "accepted"})
        mocks = {
            "tenant": mock.patch.object(heyreach, "check_tenant",
                                        return_value=True),
            "readback": mock.patch.object(
                heyreach, "readback_membership",
                return_value={"found": set(), "missing": set(),
                              "total": 0, "per_lead": []}),
            "add": mock.patch.object(heyreach, "add_leads_to_campaign",
                                     return_value={"ok": True}),
            "perform": mock.patch.object(providerwrites, "perform",
                                         perform_mock),
            "collision": mock.patch.object(
                collision, "check_account",
                return_value={"domain": "acme.test", "verdict": "clear",
                              "anyone_in_sequence": False,
                              "emails_sent_total": 0, "leads": 0,
                              "people": [], "unknown_statuses": [],
                              "any_bounce": False,
                              "workspace": "productive"}),
        }
        mocks.update(_auth_patches())
        _start_all(mocks, self)
        try:
            heyreachfactory.ensure_leads(
                "test-li-campaign", config=self._config(), live=True)
        finally:
            _stop_all(mocks)
        return perform_mock

    def test_the_readback_is_obtained_for_a_write_that_adds_people(self):
        """`staging=True`, and without it the add-lead path cannot pass.

        `authorize` refuses unless the diff says PASS, and this path is asking
        permission to ADD leads - so comparing the lead set by equality asks
        the provider to already hold the people being added. The flag is what
        makes the comparison containment instead.

        It was added to `configdiff`, tested there, and NOT WIRED: this
        closure called `compare_heyreach` without it, so the live path still
        compared by equality and still refused. A correct change that nothing
        consumes is a change that did nothing, and this assertion is what
        catches that - it reads the call the factory actually made.
        """
        recs = [_make_record("acme", "pat")]
        camp = _make_campaign(record_ids=["acme"])
        self._seed(recs, camp)

        spy = mock.MagicMock(return_value=_auth_patches()["compare_heyreach"]
                             .new)
        fake = configdiff.Readback(
            diff={"verdict": configdiff.PASS, "failures": []},
            approved={}, provider={}, campaign_id="test-li-campaign",
            channel="linkedin", provider_campaign_id=599020,
            verified_at=store.now())
        spy.return_value = fake
        mocks = {
            "tenant": mock.patch.object(heyreach, "check_tenant",
                                        return_value=True),
            "readback": mock.patch.object(
                heyreach, "readback_membership",
                return_value={"found": set(), "missing": set(),
                              "total": 0, "per_lead": []}),
            "add": mock.patch.object(heyreach, "add_leads_to_campaign",
                                     return_value={"ok": True}),
            "perform": mock.patch.object(providerwrites, "perform",
                                         mock.MagicMock(
                                             return_value={"class": "accepted"})),
            "compare": mock.patch.object(configdiff, "compare_heyreach", spy),
            "authorize": _auth_patches()["authorize"],
            "collision": mock.patch.object(
                collision, "check_account",
                return_value={"domain": "acme.test", "verdict": "clear",
                              "anyone_in_sequence": False,
                              "emails_sent_total": 0, "leads": 0,
                              "people": [], "unknown_statuses": [],
                              "any_bounce": False,
                              "workspace": "productive"}),
        }
        _start_all(mocks, self)
        try:
            heyreachfactory.ensure_leads(
                "test-li-campaign", config=self._config(), live=True)
        finally:
            _stop_all(mocks)

        self.assertTrue(spy.called, "no readback was obtained at all")
        self.assertIs(
            spy.call_args.kwargs.get("staging"), True,
            "the readback compares lead sets by equality, which cannot pass "
            "before the leads exist")

    def test_the_destination_campaign_is_named_on_every_call(self):
        """Without it the door cannot read the campaign's state, and refuses.

        `599020` is the campaign row's `heyreach_campaign_id`, so this also
        pins that the PROVIDER id is passed rather than the local one - the
        two are different strings and only one can be read from HeyReach.
        """
        perform_mock = self._push_two()
        self.assertEqual(perform_mock.call_count, 2)
        for call in perform_mock.call_args_list:
            self.assertEqual(call.kwargs.get("provider_campaign_id"), 599020)

    def test_each_write_carries_exactly_the_contact_it_was_authorised_for(self):
        """One authorization names one record, one contact, one step. The
        write it drives must carry that person and nobody else."""
        perform_mock = self._push_two()
        self.assertEqual(perform_mock.call_count, 2)

        sent = []
        for call in perform_mock.call_args_list:
            transport = call.kwargs["transport"]
            with mock.patch.object(heyreach, "add_leads_to_campaign") as add:
                transport(call.kwargs.get("payload"))
            _campaign_id, rows, _seat = add.call_args[0]
            self.assertEqual(
                len(rows), 1,
                "this write carries more than the one contact its "
                "authorization named")
            sent.append(rows[0]["contact_key"])
        self.assertEqual(sorted(sent), ["pat", "sam"])

    def test_each_readback_asks_only_about_that_contact(self):
        """A readback scoped to the whole batch passes on somebody else's
        lead: after the first write every later one finds what a different
        authorization put there."""
        perform_mock = self._push_two()
        asked = []
        for call in perform_mock.call_args_list:
            readback = call.kwargs["readback"]
            with mock.patch.object(
                    heyreach, "readback_membership",
                    return_value={"found": set(), "missing": set(),
                                  "total": 0, "per_lead": []}) as rb:
                readback()
            _campaign_id, urls = rb.call_args[0]
            self.assertEqual(len(urls), 1)
            asked.append(urls[0])
            self.assertEqual(call.kwargs["expected"],
                             {"found": {urls[0].strip().lower()}})
        self.assertEqual(len(set(asked)), 2)


# =============================================== unclassifiable response

class UnclassifiableResponse(_EnsureLeadsTestBase):
    """A transport that answers 200 with a body nobody can classify does not
    become a success."""

    def test_unclassifiable_body_is_not_success(self):
        rec = _make_record()
        camp = _make_campaign()
        self._seed([rec], camp)

        def _readback_unclear(pid, urls):
            return {"found": set(), "missing": set(urls),
                    "total": 0, "per_lead": []}

        mocks = {
            "tenant": mock.patch.object(heyreach, "check_tenant",
                                        return_value=True),
            "readback": mock.patch.object(heyreach, "readback_membership",
                                          side_effect=_readback_unclear),
            "collision": mock.patch.object(
                collision, "check_account",
                return_value={"domain": "acme.test", "verdict": "clear",
                              "anyone_in_sequence": False,
                              "emails_sent_total": 0, "leads": 0,
                              "people": [], "unknown_statuses": [],
                              "any_bounce": False,
                              "workspace": "productive"}),
        }
        mocks.update(_auth_patches())
        _start_all(mocks, self)
        try:
            with mock.patch.object(
                    providerwrites, "perform",
                    side_effect=providerwrites.WriteUnverified(
                        "readback says missing: the provider answered but "
                        "the membership read found nobody. Not a success")):
                with self.assertRaises(providerwrites.WriteUnverified) \
                        as ctx:
                    heyreachfactory.ensure_leads(
                        "test-li-campaign", config=self._config(), live=True)
        finally:
            _stop_all(mocks)
        self.assertIn("Not a success", str(ctx.exception))


# =============================================== guard breaking

class GuardBreaking(_EnsureLeadsTestBase):
    """Break each guard deliberately and confirm the INTENDED test fails
    for the INTENDED reason - and that a different guard did not fire first."""

    def test_killswitch_fires_before_suppression(self):
        """Both are wrong, but killswitch is first and must be what refuses."""
        self._ks_patch.stop()
        rec = _make_record()
        rec["contacts"][0]["suppressed"] = True
        camp = _make_campaign()
        self._seed([rec], camp)

        with mock.patch.object(killswitch, "workspace_state",
                               return_value={"sending": False,
                                             "why": "off"}):
            with self.assertRaises(heyreachfactory.FactoryRefused) as ctx:
                heyreachfactory.ensure_leads(
                    "test-li-campaign", config=self._config())
        text = str(ctx.exception)
        self.assertIn("killswitch", text.lower())
        self.assertNotIn("blocked", text)

    def test_suppression_fires_before_collision(self):
        """Suppression is gate 2, collision is gate 3."""
        rec = _make_record()
        rec["contacts"][0]["suppressed"] = True
        camp = _make_campaign()
        self._seed([rec], camp)

        fake_account = {"domain": "acme.test", "verdict": "in_sequence",
                        "anyone_in_sequence": True, "emails_sent_total": 3,
                        "leads": 1, "people": [], "unknown_statuses": [],
                        "any_bounce": False, "workspace": "productive"}
        mocks = _start_all(self._patch_external())
        mocks["collision"].stop()
        try:
            with mock.patch.object(collision, "check_account",
                                   return_value=fake_account):
                with self.assertRaises(heyreachfactory.FactoryRefused) \
                        as ctx:
                    heyreachfactory.ensure_leads(
                        "test-li-campaign", config=self._config(), live=True)
        finally:
            _stop_all(mocks)
        text = str(ctx.exception)
        self.assertIn("blocked", text)
        self.assertNotIn("account verdict", text)

    def test_collision_fires_before_tenant(self):
        """Collision is gate 3, tenant is gate 4."""
        rec = _make_record()
        camp = _make_campaign()
        self._seed([rec], camp)

        fake_account = {"domain": "acme.test", "verdict": "in_sequence",
                        "anyone_in_sequence": True, "emails_sent_total": 3,
                        "leads": 1, "people": [], "unknown_statuses": [],
                        "any_bounce": False, "workspace": "productive"}

        tenant_called = []

        def _tenant_should_not_fire(pid, org):
            tenant_called.append(True)
            return True

        mocks = _start_all(self._patch_external())
        mocks["tenant"].stop()
        mocks["collision"].stop()
        try:
            with mock.patch.object(collision, "check_account",
                                   return_value=fake_account), \
                 mock.patch.object(heyreach, "check_tenant",
                                   side_effect=_tenant_should_not_fire):
                with self.assertRaises(heyreachfactory.FactoryRefused) \
                        as ctx:
                    heyreachfactory.ensure_leads(
                        "test-li-campaign", config=self._config(), live=True)
        finally:
            mocks["readback"].stop()
            mocks["perform"].stop()
        text = str(ctx.exception)
        self.assertIn("pat", text)
        self.assertIn("stop", text.lower())
        self.assertEqual(tenant_called, [],
                         "tenant check should not have been reached")


# =============================================== LINKEDIN_ADD_LEAD not enabled

class LinkAddLeadNotEnabled(_NoPatchOutlivesItsTest):
    """NARROWED, TASK-137. It is in SUPPORTED, and that is not the
    permission - the condition on its destination is."""

    def test_linkedin_add_lead_is_enabled_only_conditionally(self):
        self.assertIn(providerwrites.LINKEDIN_ADD_LEAD,
                      providerwrites.SUPPORTED)
        self.assertTrue(
            providerwrites.is_conditional(providerwrites.LINKEDIN_ADD_LEAD))

    def test_the_condition_has_no_way_to_admit_an_activation(self):
        """Nothing in CONDITIONAL could ever turn activation on.

        `add_lead` is conditionally open because a campaign state exists -
        DRAFT - in which the write reaches nobody. No campaign state makes
        activation reach nobody, so it carries no condition at all and there
        is no value anybody can pass to `perform` that admits it.
        """
        for operation in (providerwrites.LINKEDIN_ACTIVATE,
                          providerwrites.EMAIL_ACTIVATE):
            self.assertNotIn(operation, providerwrites.CONDITIONAL)
            self.assertNotIn(operation, providerwrites.SUPPORTED)

    def test_linkedin_add_lead_is_declared(self):
        channel, facing, why = providerwrites.describe(
            providerwrites.LINKEDIN_ADD_LEAD)
        self.assertEqual(channel, "linkedin")
        self.assertTrue(facing)


# =============================================== dry run report

class DryRunReport(_EnsureLeadsTestBase):
    """Dry run prints exactly who would be pushed, from which seat, with
    which variables, and touches nothing."""

    def test_dry_run_lists_contacts_and_variables(self):
        rec = _make_record()
        camp = _make_campaign()
        self._seed([rec], camp)

        mocks = _start_all(self._patch_external())
        try:
            report = heyreachfactory.ensure_leads(
                "test-li-campaign", config=self._config(), live=False)
        finally:
            _stop_all(mocks)

        self.assertFalse(report["live"])
        self.assertTrue(any("dry run" in d for d in report["did"]))
        self.assertTrue(any("pat" in d for d in report["did"]))
        self.assertTrue(any("variables=" in d for d in report["did"]))


# =============================================== authorization gate
#
# THE TEST THE REVIEW DEMANDS.
#
# _mint_authorization used to construct executionguard.Authorization(...)
# directly. providerwrites.perform checks with isinstance, so a hand-built
# object passes while having passed NO gate. executionguard.authorize() is
# the ONLY place in src/ that may construct one, and it runs gates the five
# pre-filters do not, starting with `copy` and `approval`.
#
# This test drives ensure_leads through a contact that passes all five
# pre-filter gates but fails an executionguard gate they do not check.
# If the implementation constructs Authorization directly (bypassing
# authorize()), this test FAILS because the write proceeds. If the
# implementation calls authorize(), the mock fires, NotAuthorized is raised,
# and the write never happens.

class AuthorizationGateRefuses(_EnsureLeadsTestBase):
    """ensure_leads cannot obtain an Authorization for a contact that
    executionguard.authorize would refuse on a gate the five pre-filters
    do not check. The write must never happen."""

    def test_authorize_refuses_on_approval_gate_write_never_happens(self):
        """The contact passes all five pre-filters but fails approval.

        The five pre-filters are: killswitch (on), suppression (clean),
        collision (clear), tenant (match), unsupported sequence (all filled).
        The approval gate is NOT one of the five. If authorize() is called,
        it refuses. If authorize() is NOT called, the write proceeds and
        this test fails.
        """
        rec = _make_record()
        camp = _make_campaign()
        self._seed([rec], camp)

        transport = mock.MagicMock()
        # Mock the five pre-filters to pass, plus configdiff.compare_heyreach.
        mocks = {
            "tenant": mock.patch.object(heyreach, "check_tenant",
                                        return_value=True),
            "readback": mock.patch.object(
                heyreach, "readback_membership",
                return_value={"found": set(), "missing": set(),
                              "total": 0, "per_lead": []}),
            "collision": mock.patch.object(
                collision, "check_account",
                return_value={"domain": "acme.test", "verdict": "clear",
                              "anyone_in_sequence": False,
                              "emails_sent_total": 0, "leads": 0,
                              "people": [], "unknown_statuses": [],
                              "any_bounce": False,
                              "workspace": "productive"}),
            "compare_heyreach": _auth_patches()["compare_heyreach"],
        }
        _start_all(mocks, self)

        # Mock authorize() to refuse on the "approval" gate - a gate the
        # five pre-filters do NOT check. If the implementation calls
        # authorize(), this fires. If it constructs Authorization directly,
        # this mock is never called and the write proceeds.
        def _authorize_refuses(**kwargs):
            raise executionguard.NotAuthorized(
                "approval",
                "these exact words carry no current approval; an edit to "
                "the template, angle or evidence moves the fingerprint and "
                "the approval no longer applies")

        try:
            with mock.patch.object(executionguard, "authorize",
                                   side_effect=_authorize_refuses), \
                 mock.patch.object(heyreach, "add_leads_to_campaign",
                                   transport):
                with self.assertRaises(executionguard.NotAuthorized) as ctx:
                    heyreachfactory.ensure_leads(
                        "test-li-campaign", config=self._config(), live=True)
        finally:
            _stop_all(mocks)

        # The refusal names the approval gate.
        self.assertEqual(ctx.exception.gate, "approval")
        # The transport was NEVER reached.
        transport.assert_not_called()

    def test_authorize_must_be_called_not_constructed(self):
        """Prove that authorize() is actually called, not bypassed.

        If the implementation constructs Authorization directly, this mock
        is never called and the assertion fails. This is the test the review
        demands: it must FAIL without the authorize() call.
        """
        rec = _make_record()
        camp = _make_campaign()
        self._seed([rec], camp)

        fake_readback = configdiff.Readback(
            diff={"verdict": configdiff.PASS, "failures": []},
            approved={}, provider={},
            campaign_id="test-li-campaign", channel="linkedin",
            provider_campaign_id=599020,
            verified_at=store.now())
        fake_auth = executionguard.Authorization(
            key="fake-auth", operation=providerwrites.LINKEDIN_ADD_LEAD,
            channel="linkedin", workspace="productive",
            campaign_id="test-li-campaign", sender_id="0",
            rec_id="acme", contact_key="pat", step_key="day3",
            fingerprint="fp-li1", gates=(), at=store.now())
        authorize_mock = mock.MagicMock(return_value=fake_auth)
        mocks = {
            "tenant": mock.patch.object(heyreach, "check_tenant",
                                        return_value=True),
            "readback": mock.patch.object(
                heyreach, "readback_membership",
                return_value={"found": set(), "missing": set(),
                              "total": 0, "per_lead": []}),
            "perform": mock.patch.object(providerwrites, "perform"),
            "collision": mock.patch.object(
                collision, "check_account",
                return_value={"domain": "acme.test", "verdict": "clear",
                              "anyone_in_sequence": False,
                              "emails_sent_total": 0, "leads": 0,
                              "people": [], "unknown_statuses": [],
                              "any_bounce": False,
                              "workspace": "productive"}),
            "compare_heyreach": mock.patch.object(
                configdiff, "compare_heyreach", return_value=fake_readback),
            "authorize": mock.patch.object(
                executionguard, "authorize", authorize_mock),
        }
        _start_all(mocks)
        try:
            heyreachfactory.ensure_leads(
                "test-li-campaign", config=self._config(), live=True)
        finally:
            _stop_all(mocks)

        # authorize() WAS called. If the implementation constructs
        # Authorization directly, this assertion fails.
        authorize_mock.assert_called()


if __name__ == "__main__":
    unittest.main()


class TheRealAuthorizationGateIsReachable(_NoPatchOutlivesItsTest):
    """Every other test in this file MOCKS `executionguard.authorize` and
    hands `_mint_authorization` a fake Authorization, which is reasonable for
    exercising the orchestration around it and proves nothing about the gate.

    The first version of this task constructed the Authorization itself.
    The second called `authorize` correctly and named `step_key = "day3"` -
    a step of the OLD seven-step cadence that `productive_li_heavy_v1` does
    not contain - so the `copy` gate would have refused every person alive.
    Neither was caught by a test, because no test let the real function run.

    These do.
    """

    def campaign_row(self, cadence_name="productive_li_heavy_v1"):
        return {"campaign_id": "c1", "client": "productive", "name": "t",
                "record_ids": ["acme"], "cadence": cadence_name,
                "heyreach_campaign_id": "599020"}

    def test_the_step_key_is_the_cadences_own_first_linkedin_step(self):
        from src import clients

        config = clients.load("productive")
        self.assertEqual(
            heyreachfactory._first_linkedin_step(self.campaign_row(), config),
            "li1")

    def test_a_cadence_with_no_linkedin_step_refuses(self):
        """Rather than defaulting to one. A default here would be the same
        class of bug as the hard-coded key it replaced.

        The email-only cadence is constructed rather than named: no shipped
        cadence is email-only today, and a test that names one would start
        passing or failing for reasons that have nothing to do with this.
        """
        from src import cadence, clients

        config = clients.load("productive")
        email_only = ({"key": "em1", "day": 1, "channel": "email"},
                      {"key": "em2", "day": 4, "channel": "email"})
        patch = mock.patch.object(cadence, "steps_for", return_value=email_only)
        patch.start()
        self.addCleanup(patch.stop)
        with self.assertRaises(heyreachfactory.FactoryRefused) as caught:
            heyreachfactory._first_linkedin_step(self.campaign_row(), config)
        self.assertIn("no LinkedIn step", str(caught.exception))

    def test_a_contact_executionguard_refuses_yields_no_authorization(self):
        """THE ONE THAT DECIDES IT. No mock: the real gate runs, and a contact
        with no approved copy must not come back with an Authorization."""
        from src import clients, executionguard

        config = clients.load("productive")
        bare = {"id": "acme", "client": "productive", "domain": "acme.test",
                "company": "Acme", "contacts": [{"key": "acme-c1",
                                                 "name": "Ada Tester"}],
                "cadence": {}}
        with self.assertRaises(Exception) as caught:
            heyreachfactory._mint_authorization(
                self.campaign_row(), bare, bare["contacts"][0],
                config=config, readback=None, by="test")
        self.assertNotIsInstance(
            caught.exception, AssertionError,
            "the gate must refuse, not assert")
        # And nothing that looks like an Authorization came back.
        self.assertFalse(isinstance(caught.exception,
                                    executionguard.Authorization))
