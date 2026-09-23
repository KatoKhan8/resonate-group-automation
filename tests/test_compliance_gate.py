#!/usr/bin/env python3
"""The compliance gate: an unsubscribe affordance or a named provider setting.

COMPLIANCE.md records that the estate has no List-Unsubscribe header and no
provider field through which to set one. The gate inside executionguard's
gate 4 refuses any email cadence step that carries neither an unsubscribe
link in the body nor a named provider-level setting.

WHY THIS IS INSIDE GATE 4 AND NOT eligibility.decide.

killswitch.py:277-293 explains why wiring a send-only refusal into
eligibility.decide is a dead end: dry previews would then refuse everything.
The gate is skipped for staging=True, because staging reaches nobody and a
preview that refuses every step is the whole product refusing itself.

WHAT EACH TEST PROVES:

  1. A cadence with no unsubscribe affordance is refused.
  2. The refusal names the "compliance" gate and carries the passed-gate
     trace, so a test can assert the intended gate fired.
  3. A cadence relying on a provider-level setting must name it or be refused.
  4. A dry preview (staging=True) is NOT refused by this gate.
  5. DECLINE_QUIET_DAYS has no enforcing caller, so the day somebody wires it
     up this test goes red and COMPLIANCE.md gets corrected.
"""
import contextlib
import datetime
import inspect
import os
import tempfile
import unittest
from unittest import mock

from src import (approval, cadence, campaigns, clients, collision, configdiff,
                 executionguard, killswitch, replyengine, store)
from tests.base import QueueTest, pin_client_config

NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
FRESH = (NOW - datetime.timedelta(minutes=1)).isoformat()
WS = 10


class ComplianceGateTest(QueueTest):
    """An email cadence with no unsubscribe affordance is refused.

    The setup is a minimal email path: tenancy, approval, readback, then
    gate 4 where the compliance gate sits. Collision and killswitch are
    neutralised so the test reaches the compliance gate and no further.
    """

    def setUp(self):
        super().setUp()
        self.config = pin_client_config(self)
        rec = store.new_record("rec-compliance", "domains", "productive",
                               "Acme Co", "acme.test")
        rec["state"] = "verified"
        rec["company_facts"] = {"industry": "Design",
                                "research_outcome": "HTTP_SUCCESS"}
        rec["contacts"] = [{
            "key": "dana-compliance", "name": "Dana Reed",
            "title": "Head of Ops", "email": "dana@acme.test",
            "linkedin": "https://linkedin.com/in/dana-reed",
            "persona": "champion", "angle": "operations",
            "selected": True, "verdict": "valid", "sendable": True,
            "verification": {"evidence": [
                {"provider": "contactout", "status": "valid",
                 "email": "dana@acme.test", "catch_all": False,
                 "disposable": False, "at": "2026-09-09T00:00:00+00:00"},
                {"provider": "reoon", "status": "valid",
                 "email": "dana@acme.test", "catch_all": False,
                 "safe_to_send": True,
                 "at": "2026-09-09T00:00:00+00:00"}]},
            "mx": {"status": "known_allowed", "email_eligible": True},
        }]
        # Store a day1 step (email, generated) with no unsubscribe link.
        # day1 is generated=True in the cadence, so expand_step uses the
        # stored body directly without template rendering.
        # Body must be >= 40 words to pass lint, and needs a subject line.
        body_no_unsub = ("I work with design teams on resourcing and "
                         "capacity planning across the portfolio. I have "
                         "been doing this for over a decade now and have "
                         "seen many different approaches work well. Happy "
                         "to share how peers at similar-sized firms handle "
                         "it at your scale and what tends to work best in "
                         "practice for teams your size.")
        step_data = {"channel": "email",
                     "subject": "resourcing at Acme Co",
                     "body": body_no_unsub,
                     "generated": True}
        fp = approval.fingerprint(step_data)
        with store.transaction() as rows:
            rows.append(rec)
            for row in rows:
                if row["id"] == "rec-compliance":
                    row.setdefault("cadence", {}).setdefault(
                        "dana-compliance", {})["day1"] = dict(
                            step_data,
                            approval={"by": "operator", "at": store.now(),
                                      "fingerprint": fp})
        self.rec = store.get("rec-compliance")
        self.contact = self.rec["contacts"][0]

        self.campaign = campaigns.new_campaign(
            "compliance-test", "productive", "CLIENT - COMPLIANCE",
            created_by="operator")
        self.campaign.update({
            "bison_campaign_id": 487,
            "record_ids": ["rec-compliance"],
            "senders": {"email": [{"id": 116968, "daily_limit": 1}],
                        "linkedin": []},
            "daily_volume": {"email": 1, "linkedin": 0},
            "org_unit": 118832,
        })
        # Sender inventory for the email seat.
        from src import senderidentity
        with senderidentity.transaction() as rows:
            rows.append(senderidentity.new_sender(
                "productive", "mina", "Mina Ruzicic"))
            rows.append(senderidentity.new_linkedin_account(
                "productive", "li-116968", "mina",
                "https://www.linkedin.com/in/mina-ruzicic-b4422438a",
                provider="emailbison", provider_account_id="116968",
                active=True, daily_limit=40, health="ok"))
        # Campaign approval.
        current = campaigns.fingerprint(self.campaign, store.load(),
                                        self.config)
        self.campaign["approval"] = {"action": "approve", "by": "operator",
                                     "at": store.now(),
                                     "fingerprint": current}
        self.campaign["fingerprint"] = current
        self.campaign["status"] = campaigns.APPROVED

    def _readback(self, channel="email", provider_campaign_id=487):
        return configdiff.Readback(
            diff={"verdict": configdiff.PASS, "failures": []},
            approved={}, provider={}, campaign_id="compliance-test",
            channel=channel, provider_campaign_id=provider_campaign_id,
            verified_at=FRESH)

    @contextlib.contextmanager
    def _pass_gates_before_compliance(self):
        """Stub everything between gate 1 and the compliance gate.

        Tenancy needs bison.require_workspace to succeed. Collision needs
        both check_address and check_account to answer CLEAR. MX needs to
        allow email. Lint needs to pass. The killswitch is after the
        compliance gate, so it does not need stubbing for a refusal AT
        compliance.
        """
        from src.providers import bison
        from src import lint, mx
        with mock.patch.object(bison, "require_workspace",
                               lambda expected: expected), \
             mock.patch.object(collision, "check_address",
                               return_value=(collision.CLEAR, {})), \
             mock.patch.object(collision, "check_account",
                               return_value={"verdict": collision.CLEAR,
                                             "people": [],
                                             "emails_sent_total": 0}), \
             mock.patch.object(mx, "allows_email",
                               return_value=(True, "test stub")), \
             mock.patch.object(lint, "check_step", return_value=[]), \
             mock.patch.object(lint, "check", return_value=[]):
            yield

    def _authorize_email(self, **over):
        kw = dict(operation="email_send", channel="email",
                  campaign=self.campaign, rec=self.rec,
                  contact=self.contact, step_key="day1",
                  workspace=WS, config=self.config,
                  now=NOW, readback=self._readback())
        kw.update(over)
        return executionguard.authorize(**kw)

    # ------------------------------------------------ 1. the basic refusal

    def test_a_cadence_with_no_unsubscribe_affordance_is_refused(self):
        """No link in the body, no provider setting named: refused."""
        with self._pass_gates_before_compliance():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self._authorize_email()
        self.assertEqual(caught.exception.gate, "compliance")

    # ------------------------------------------------ 2. gate name and trace

    def test_the_refusal_names_the_compliance_gate(self):
        """The gate field says 'compliance', not 'eligibility' or 'copy'."""
        with self._pass_gates_before_compliance():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self._authorize_email()
        self.assertEqual(caught.exception.gate, "compliance")
        self.assertIn("compliance", str(caught.exception))

    def test_the_refusal_carries_the_passed_gate_trace(self):
        """The passed-gate trace includes everything before compliance.

        A bare 'refused at compliance' cannot be triaged: it does not say
        whether tenancy, approval and readback were satisfied. The trace is
        the difference between 'the compliance gate fired' and 'something
        fired and we do not know what reached it'.

        The compliance gate runs inside gate 4 (the JIT block), after
        eligibility and suppression checks but before the gates.extend that
        records them. So the trace shows what passed before gate 4 started:
        tenancy, approval, campaign_approval, readback.
        """
        with self._pass_gates_before_compliance():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self._authorize_email()
        passed = caught.exception.passed
        self.assertIn("tenancy", passed)
        self.assertIn("approval", passed)
        self.assertIn("campaign_approval", passed)
        self.assertIn("readback", passed)

    def test_the_refusal_message_names_what_is_missing(self):
        """The operator must be able to read the refusal and know what to fix.

        A gate that passes because it checked the wrong thing is the failure
        mode this repository has hit most often. The refusal says WHICH
        affordance is absent.
        """
        with self._pass_gates_before_compliance():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self._authorize_email()
        msg = str(caught.exception)
        self.assertIn("unsubscribe", msg.lower())

    # ------------------------------------------------ 3. provider setting

    def test_a_named_provider_setting_satisfies_the_gate(self):
        """A campaign that names a provider-level setting passes.

        The setting must be NAMED - an unnamed reliance is not evidence.
        """
        self.campaign["compliance"] = {
            "unsubscribe_via": "emailbison_managed_opt_out"}
        with self._pass_gates_before_compliance():
            # The gate passes; the authorization may still fail later at
            # collision or killswitch, but it does NOT fail at compliance.
            try:
                self._authorize_email()
            except executionguard.NotAuthorized as e:
                self.assertNotEqual(e.gate, "compliance",
                                    "a named provider setting should "
                                    "satisfy the compliance gate")

    def test_an_empty_provider_setting_is_not_named(self):
        """A compliance dict with an empty string is the same as none."""
        self.campaign["compliance"] = {"unsubscribe_via": ""}
        with self._pass_gates_before_compliance():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self._authorize_email()
        self.assertEqual(caught.exception.gate, "compliance")

    def test_a_config_level_setting_also_satisfies(self):
        """The client config can carry the default when the campaign does not.

        The gate checks campaign first, then config. A config-level default
        is the right place for a setting that applies to every campaign.
        """
        self.config["compliance"] = {
            "unsubscribe_via": "provider_handles_opt_out"}
        with self._pass_gates_before_compliance():
            try:
                self._authorize_email()
            except executionguard.NotAuthorized as e:
                self.assertNotEqual(e.gate, "compliance")

    # ------------------------------------------------ 4. staging bypass

    def test_a_dry_preview_is_not_refused_by_this_gate(self):
        """staging=True skips the compliance gate.

        A preview that refuses every step is the whole product refusing
        itself - the dead end killswitch.py:277-293 names for wiring a
        send-only refusal into eligibility.decide.
        """
        with self._pass_gates_before_compliance():
            try:
                self._authorize_email(staging=True)
            except executionguard.NotAuthorized as e:
                self.assertNotEqual(
                    e.gate, "compliance",
                    "staging must not be refused by the compliance gate")

    def test_linkedin_is_not_refused_by_this_gate(self):
        """The gate only applies to email. LinkedIn has no email body.

        A gate that refuses every LinkedIn step because it checked for an
        email unsubscribe link is checking the wrong thing.
        """
        # Set up a LinkedIn step instead.
        li_step = {"channel": "linkedin", "note": "hello, worth a word?"}
        li_fp = approval.fingerprint(li_step)
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "rec-compliance":
                    row.setdefault("cadence", {}).setdefault(
                        "dana-compliance", {})["day3"] = dict(
                            li_step,
                            approval={"by": "operator", "at": store.now(),
                                      "fingerprint": li_fp})
        self.rec = store.get("rec-compliance")
        self.contact = self.rec["contacts"][0]
        self.campaign["heyreach_campaign_id"] = 594061
        self.campaign["heyreach_list_id"] = 926076
        self.campaign["org_unit"] = 118832
        self.campaign["senders"] = {
            "email": [],
            "linkedin": [{"id": 116968, "daily_limit": 1}]}
        current = campaigns.fingerprint(self.campaign, store.load(),
                                        self.config)
        self.campaign["approval"] = {"action": "approve", "by": "operator",
                                     "at": store.now(),
                                     "fingerprint": current}
        self.campaign["fingerprint"] = current
        readback = configdiff.Readback(
            diff={"verdict": configdiff.PASS, "failures": []},
            approved={}, provider={}, campaign_id="compliance-test",
            channel="linkedin", provider_campaign_id=594061,
            verified_at=FRESH)
        with mock.patch.object(collision, "check_linkedin_profile",
                               return_value=(collision.CLEAR, {})), \
             mock.patch.object(collision, "check_account",
                               return_value={"verdict": collision.CLEAR,
                                             "people": [],
                                             "emails_sent_total": 0}):
            try:
                executionguard.authorize(
                    operation="linkedin_connection_request",
                    channel="linkedin", campaign=self.campaign,
                    rec=self.rec, contact=self.contact, step_key="day3",
                    workspace=WS, config=self.config, now=NOW,
                    readback=readback)
            except executionguard.NotAuthorized as e:
                self.assertNotEqual(
                    e.gate, "compliance",
                    "LinkedIn must not be refused by the email compliance "
                    "gate")


# ------------------------------------------------ 5. DECLINE_QUIET_DAYS
class DeclineQuietDaysHasNoEnforcingCaller(unittest.TestCase):
    """replyengine.DECLINE_QUIET_DAYS = 180 is declared and dead.

    COMPLIANCE.md §2.2 records that neither POST_DECLINE_QUESTIONS nor
    DECLINE_QUIET_DAYS is referenced anywhere else in src/, tests/ or docs/.
    This test asserts that property directly: it reads the constant and
    checks that no function in src/ references it. The day somebody wires it
    up, this test goes red and COMPLIANCE.md gets corrected.
    """

    def test_decline_quiet_days_is_defined(self):
        """The constant exists and says 180."""
        self.assertEqual(replyengine.DECLINE_QUIET_DAYS, 180)

    def test_post_decline_questions_is_defined(self):
        self.assertEqual(replyengine.POST_DECLINE_QUESTIONS, 1)

    def test_no_enforcing_caller_exists_in_src(self):
        """Neither constant is referenced outside replyengine.py itself.

        This is the test that goes red when somebody wires the 180-day
        silence up. At that point COMPLIANCE.md §2.2 must move from
        'operator obligation' to 'system enforced'.
        """
        import src
        src_dir = os.path.dirname(inspect.getfile(src))
        for root, _dirs, files in os.walk(src_dir):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(root, fname)
                if os.path.basename(path) == "replyengine.py":
                    continue
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertNotIn(
                    "DECLINE_QUIET_DAYS", content,
                    f"{path} references DECLINE_QUIET_DAYS - the 180-day "
                    f"silence now has an enforcing caller. Update "
                    f"COMPLIANCE.md §2.2 to move it from 'operator "
                    f"obligation' to 'system enforced'")
                self.assertNotIn(
                    "POST_DECLINE_QUESTIONS", content,
                    f"{path} references POST_DECLINE_QUESTIONS - the "
                    f"decline-question cap now has an enforcing caller. "
                    f"Update COMPLIANCE.md §2.2")


# ------------------------------------------------ helper function tests
class UnsubscribeAffordanceDetection(unittest.TestCase):
    """The regex that decides whether a body carries an unsubscribe link."""

    def test_a_plain_body_has_no_affordance(self):
        body = "I work with design teams on resourcing."
        self.assertFalse(executionguard._has_unsubscribe_affordance(body))

    def test_an_empty_body_has_no_affordance(self):
        self.assertFalse(executionguard._has_unsubscribe_affordance(""))
        self.assertFalse(executionguard._has_unsubscribe_affordance(None))

    def test_an_https_unsubscribe_link_is_detected(self):
        body = ("Great to connect. "
                "Unsubscribe: https://example.com/unsubscribe/abc123")
        self.assertTrue(executionguard._has_unsubscribe_affordance(body))

    def test_an_opt_out_link_is_detected(self):
        body = ("Click here to opt-out: "
                "https://example.com/preferences/opt-out?id=42")
        self.assertTrue(executionguard._has_unsubscribe_affordance(body))

    def test_a_manage_preferences_link_is_detected(self):
        body = ("Update your preferences: "
                "https://example.com/manage-preferences")
        self.assertTrue(executionguard._has_unsubscribe_affordance(body))

    def test_a_mustache_merge_field_is_detected(self):
        body = "Hello. {{unsubscribe}} to stop receiving emails."
        self.assertTrue(executionguard._has_unsubscribe_affordance(body))

    def test_a_dollar_merge_field_is_detected(self):
        body = "Hello. ${unsubscribe} to stop receiving emails."
        self.assertTrue(executionguard._has_unsubscribe_affordance(body))

    def test_a_bare_word_unsubscribe_is_not_enough(self):
        """The reply classifier catches 'unsubscribe' on the inbound side.

        This gate asks whether the OUTBOUND message gave the recipient a way
        to stop without writing a reply. A bare word is not a mechanism.
        """
        body = "If you do not want to hear from us, unsubscribe."
        self.assertFalse(executionguard._has_unsubscribe_affordance(body))


class NamedUnsubscribeSetting(unittest.TestCase):
    """A campaign or config that names a provider-level setting."""

    def test_no_compliance_key_returns_none(self):
        self.assertIsNone(
            executionguard._named_unsubscribe_setting({}, {}))

    def test_an_empty_compliance_dict_returns_none(self):
        self.assertIsNone(
            executionguard._named_unsubscribe_setting(
                {"compliance": {}}, {}))

    def test_a_named_setting_is_returned(self):
        campaign = {"compliance": {"unsubscribe_via": "bison_managed"}}
        result = executionguard._named_unsubscribe_setting(campaign, {})
        self.assertEqual(result, "bison_managed")

    def test_an_empty_string_is_not_named(self):
        campaign = {"compliance": {"unsubscribe_via": ""}}
        self.assertIsNone(
            executionguard._named_unsubscribe_setting(campaign, {}))

    def test_config_level_is_checked_when_campaign_has_none(self):
        config = {"compliance": {"unsubscribe_via": "provider_default"}}
        result = executionguard._named_unsubscribe_setting({}, config)
        self.assertEqual(result, "provider_default")

    def test_campaign_takes_priority_over_config(self):
        campaign = {"compliance": {"unsubscribe_via": "campaign_specific"}}
        config = {"compliance": {"unsubscribe_via": "config_default"}}
        result = executionguard._named_unsubscribe_setting(campaign, config)
        self.assertEqual(result, "campaign_specific")

    def test_none_config_does_not_crash(self):
        self.assertIsNone(
            executionguard._named_unsubscribe_setting({}, None))


if __name__ == "__main__":
    unittest.main()
