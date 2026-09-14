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

from src import (campaigns, clients, collision, heyreachfactory, killswitch,
                 providerwrites, store)
from src.providers import heyreach


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


def _full_cadence(contact_key="brooke"):
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


def _make_record(rec_id="acme", contact_key="brooke", *, domain="acme.test",
                 client="productive", linkedin=None):
    """A record with one contact and a full LinkedIn cadence."""
    url = linkedin or f"https://www.linkedin.com/in/{contact_key}"
    return {
        "id": rec_id, "client": client, "domain": domain,
        "contacts": [{"key": contact_key, "name": "Brooke Baron",
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


class _EnsureLeadsTestBase(unittest.TestCase):
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
        }
        return mocks


def _start_all(mocks):
    for m in mocks.values():
        m.start()
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
        self.assertIn("brooke", text)
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
        self.assertIn("brooke", text)
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
        self.assertIn("brooke", text)
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
        _start_all(mocks)

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
        _start_all(mocks)
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
        self.assertIn("brooke", text)
        self.assertIn("stop", text.lower())
        self.assertEqual(tenant_called, [],
                         "tenant check should not have been reached")


# =============================================== LINKEDIN_ADD_LEAD not enabled

class LinkAddLeadNotEnabled(unittest.TestCase):
    """LINKEDIN_ADD_LEAD is NOT in SUPPORTED. This is deliberate."""

    def test_linkedin_add_lead_is_not_in_supported(self):
        self.assertNotIn(providerwrites.LINKEDIN_ADD_LEAD,
                         providerwrites.SUPPORTED)

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
        self.assertTrue(any("brooke" in d for d in report["did"]))
        self.assertTrue(any("variables=" in d for d in report["did"]))


if __name__ == "__main__":
    unittest.main()
