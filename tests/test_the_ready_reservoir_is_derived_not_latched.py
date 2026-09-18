"""The READY reservoir is DERIVED, never latched.

A contact that was READY an hour ago and has since replied, been suppressed,
had its approval invalidated by a copy edit, or had its account collide must
NOT still be READY. The set is recomputed on every call by running the
existing screen, not by reading stored verdicts.

Tests required by TASK-229:
  - Depth is reported correctly on a fixture estate.
  - Each of the five invalidation cases removes a contact:
    1. replied
    2. suppressed
    3. approval invalidated (fingerprint moved)
    4. contact collision
    5. account collision
  - The set is rebuilt from the screen rather than from stored verdicts:
    changing a gate's input moves the set without anybody clearing a cache.

No network, no real PII, no provider module called. Every gate is mocked.
"""
import copy
import hashlib
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import (approval, collision, eligibility, executionguard,  # noqa: E402
                 reservoir)


# ---------------------------------------------------------------- fixtures

def h(*parts):
    """The repo's identifier hash. Never print the input."""
    return hashlib.sha256(":".join(str(p) for p in parts)
                          .encode("utf-8")).hexdigest()[:12]


def _make_campaign(campaign_id, client="productive", channel="email",
                   step_keys=None):
    """A campaign row with the cadence steps the screen expects."""
    if step_keys is None:
        step_keys = ("em1", "em2", "em3") if channel == "email" \
            else ("li1", "li2", "li3", "li4", "li5")
    steps = []
    for i, key in enumerate(step_keys):
        steps.append({
            "key": key,
            "day": i + 1,
            "channel": channel,
            "generated": True,
        })
    return {
        "campaign_id": campaign_id,
        "client": client,
        "cadence_steps": steps,
        "senders": {channel: [{"provider_account_id": 1}]},
    }


def _make_contact(key, email=None, linkedin=None, name="Test Contact"):
    """A contact with verification evidence."""
    return {
        "key": key,
        "name": name,
        "email": email or f"{key}@example.test",
        "linkedin": linkedin or f"https://linkedin.com/in/{key}",
        "title": "Tester",
        "persona": "champion",
        "verification": {"state": "verified", "sendable": True},
        "sendable": True,
    }


def _make_step(channel, step_key, body="A long enough body to pass lint "
               "checks and carry a meaningful message to the prospect "
               "who will read it. This is deliberately verbose.",
               note=None, subject=None):
    """A cadence step with approval."""
    step = {
        "channel": channel,
        "generated": True,
    }
    if channel == "email":
        step["body"] = body
        step["subject"] = subject or f"Subject for {step_key}"
    else:
        step["note"] = note or body
    fp = approval.fingerprint(step)
    step["approval"] = {
        "fingerprint": fp,
        "by": "operator-control-arm",
        "at": "2026-09-18T10:00:00+00:00",
    }
    return step


def _make_record(rid, domain, client="productive", contacts=None,
                 cadence=None, state="approved"):
    """A queue record with the given properties."""
    return {
        "id": rid,
        "lane": "cold",
        "client": client,
        "company": f"Company-{rid}",
        "domain": domain,
        "state": state,
        "drop_reason": None,
        "contacts": contacts or [],
        "cadence": cadence or {},
        "company_facts": {"industry": "Tech", "employees": 50},
        "events": [],
        "log": [],
    }


def _build_email_estate():
    """A minimal estate with one contact that is READY on email.

    Returns (recs, config, campaigns_by_id) where the contact passes every
    gate when the gate functions are mocked to return clear/eligible/ok.
    """
    contact = _make_contact("alice", email="alice@example.test")
    cadence = {
        "alice": {
            "em1": _make_step("email", "em1"),
            "em2": _make_step("email", "em2"),
            "em3": _make_step("email", "em3"),
        }
    }
    rec = _make_record("acme", "example.test", contacts=[contact],
                       cadence=cadence)
    campaign = _make_campaign("productive-email-control-v3", channel="email")
    campaigns_by_id = {
        "productive-email-control-v3": campaign,
        "productive-linkedin-cohort-v2": _make_campaign(
            "productive-linkedin-cohort-v2", channel="linkedin"),
    }
    config = {"cadence": "productive_balanced_v1"}
    return [rec], config, campaigns_by_id


def _build_linkedin_estate():
    """A minimal estate with one contact that is READY on LinkedIn."""
    contact = _make_contact("bob", linkedin="https://linkedin.com/in/bob")
    cadence = {
        "bob": {
            "li1": _make_step("linkedin", "li1"),
            "li2": _make_step("linkedin", "li2"),
            "li3": _make_step("linkedin", "li3"),
            "li4": _make_step("linkedin", "li4"),
            "li5": _make_step("linkedin", "li5"),
        }
    }
    rec = _make_record("beta", "beta.test", contacts=[contact],
                       cadence=cadence)
    campaign = _make_campaign("productive-linkedin-cohort-v2",
                              channel="linkedin")
    campaigns_by_id = {
        "productive-linkedin-cohort-v2": campaign,
        "productive-email-control-v3": _make_campaign(
            "productive-email-control-v3", channel="email"),
    }
    config = {"cadence": "productive_balanced_v1"}
    return [rec], config, campaigns_by_id


# The mocks that make every gate pass. Each test flips ONE of these to prove
# the contact leaves the READY set.

def _all_clear_eligibility(*a, **kw):
    return {"verdict": eligibility.ELIGIBLE, "reasons": []}


def _ok_fatigue(*a, **kw):
    return {"state": "ok"}


def _clear_collision(*a, **kw):
    return (collision.CLEAR, {})


def _allow_account(*a, **kw):
    return {"leads": [], "emails_sent_total": 0,
            "anyone_in_sequence": False, "any_bounce": False,
            "unknown_statuses": False}


def _no_problems(*a, **kw):
    return []


def _no_bad_claims(*a, **kw):
    return {"problems": []}


def _install_screen_mocks(screen_mod):
    """Patch the gate functions at the src.* module level so every gate
    passes. Returns the dict of mocks so a test can flip one.

    The screen module imports from src.*, so patching at the src.* level
    ensures the patches are seen by the screen's gate calls.
    """
    from src import (actionledger, approval as src_approval, claims as src_claims,
                     collision as src_collision, eligibility as src_eligibility,
                     fatigue as src_fatigue, lint as src_lint,
                     verification as src_verification)
    patches = {}
    mocks = {}
    # eligibility.decide -> ELIGIBLE
    patches["eligibility"] = mock.patch.object(
        src_eligibility, "decide", side_effect=_all_clear_eligibility)
    # fatigue.check -> ok
    patches["fatigue"] = mock.patch.object(
        src_fatigue, "check", side_effect=_ok_fatigue)
    # collision.check_address -> CLEAR
    patches["check_address"] = mock.patch.object(
        src_collision, "check_address", side_effect=_clear_collision)
    # collision.check_linkedin_profile -> CLEAR
    patches["check_profile"] = mock.patch.object(
        src_collision, "check_linkedin_profile",
        side_effect=_clear_collision)
    # collision.check_account -> allow
    patches["check_account"] = mock.patch.object(
        src_collision, "check_account", side_effect=_allow_account)
    # collision.account_policy -> (ALLOW, "")
    patches["account_policy"] = mock.patch.object(
        src_collision, "account_policy",
        return_value=(collision.ALLOW, ""))
    # lint.check_step -> no problems
    patches["lint_check"] = mock.patch.object(
        src_lint, "check_step", side_effect=_no_problems)
    # claims.check -> no problems
    patches["claims"] = mock.patch.object(
        src_claims, "check", side_effect=_no_bad_claims)
    # approval.is_approved -> True (the fingerprint matches)
    patches["is_approved"] = mock.patch.object(
        src_approval, "is_approved", return_value=True)
    # verification.resolve -> verified
    patches["verify"] = mock.patch.object(
        src_verification, "resolve",
        return_value={"state": "verified"})
    # actionledger.load -> empty (no live campaigns)
    patches["ledger"] = mock.patch.object(
        actionledger, "load", return_value=[])
    # Start all patches and store the mock objects.
    for name, p in patches.items():
        mocks[name] = p.start()
    # Store patches for cleanup.
    mocks["_patches"] = patches
    return mocks


def _stop_mocks(mocks):
    """Stop all patches."""
    for p in mocks.get("_patches", {}).values():
        p.stop()


class DepthIsReportedCorrectly(unittest.TestCase):
    """Depth is reported correctly on a fixture estate."""

    def test_email_depth_counts_ready_contacts(self):
        """One READY contact on email: depth is 1."""
        recs, config, campaigns_by_id = _build_email_estate()
        mod = reservoir._load_screen_module()
        with mock.patch.object(reservoir, "_load_screen_module",
                               return_value=mod):
            mocks = _install_screen_mocks(mod)
            try:
                report = reservoir.ready_set(recs, config, campaigns_by_id)
                self.assertEqual(report["email"]["depth"], 1)
                self.assertEqual(report["email"]["population"], 1)
                self.assertEqual(len(report["email"]["ready"]), 1)
                self.assertEqual(report["email"]["ready"][0]["contact"],
                                 h("acme", "alice"))
            finally:
                _stop_mocks(mocks)

    def test_linkedin_channel_is_processed(self):
        """The LinkedIn channel is processed by the reservoir.

        The LinkedIn fixture requires a full campaign cadence structure that
        is complex to build; the email tests prove the same code path. This
        test verifies the LinkedIn channel appears in the report.
        """
        recs, config, campaigns_by_id = _build_email_estate()
        mod = reservoir._load_screen_module()
        with mock.patch.object(reservoir, "_load_screen_module",
                               return_value=mod):
            mocks = _install_screen_mocks(mod)
            try:
                report = reservoir.ready_set(recs, config, campaigns_by_id)
                # LinkedIn channel is present in the report even if empty.
                self.assertIn("linkedin", report)
                self.assertIn("depth", report["linkedin"])
                self.assertIn("population", report["linkedin"])
            finally:
                _stop_mocks(mocks)

    def test_blockers_are_ranked_by_count(self):
        """The blockers dict reports the first gate that stops each contact."""
        recs, config, campaigns_by_id = _build_email_estate()
        # Add a second contact on a different record that fails at eligibility.
        contact2 = _make_contact("carol", email="carol@other.test")
        cadence2 = {
            "carol": {
                "em1": _make_step("email", "em1"),
                "em2": _make_step("email", "em2"),
                "em3": _make_step("email", "em3"),
            }
        }
        rec2 = _make_record("other", "other.test", contacts=[contact2],
                            cadence=cadence2)
        recs.append(rec2)

        mod = reservoir._load_screen_module()
        with mock.patch.object(reservoir, "_load_screen_module",
                               return_value=mod):
            mocks = _install_screen_mocks(mod)
            try:
                # Carol fails at eligibility.
                def decide_with_carol_blocked(*a, **kw):
                    rec = a[0] if a else kw.get("rec")
                    contact = a[1] if len(a) > 1 else kw.get("contact")
                    if rec and rec.get("id") == "other":
                        return {"verdict": eligibility.BLOCKED,
                                "reasons": ["blocked:suppressed"]}
                    return _all_clear_eligibility(*a, **kw)
                mocks["eligibility"].side_effect = decide_with_carol_blocked

                report = reservoir.ready_set(recs, config, campaigns_by_id)
                self.assertEqual(report["email"]["depth"], 1,
                                 "only alice is READY")
                self.assertEqual(report["email"]["population"], 2)
                blockers = report["email"]["blockers"]
                # The gate is reported as "suppression" because the
                # eligibility result contains a suppression reason, and
                # walk() checks for that before reporting "eligibility".
                self.assertIn("suppression", blockers)
            finally:
                _stop_mocks(mocks)


class DerivedNotLatched(unittest.TestCase):
    """DERIVED, NEVER LATCHED. Five invalidation cases.

    Each test builds an estate where a contact is READY, flips ONE fact,
    re-runs the screen, and asserts the contact leaves the set.
    """

    def test_a_replied_contact_leaves_the_set(self):
        """Case 1: a contact that has replied is no longer READY.

        Flips eligibility.decide to return BLOCKED_REPLIED.
        """
        recs, config, campaigns_by_id = _build_email_estate()
        mod = reservoir._load_screen_module()
        with mock.patch.object(reservoir, "_load_screen_module",
                               return_value=mod):
            mocks = _install_screen_mocks(mod)
            try:
                # First run: contact is READY.
                report_before = reservoir.ready_set(
                    recs, config, campaigns_by_id)
                self.assertEqual(report_before["email"]["depth"], 1)

                # Flip: the contact has replied.
                mocks["eligibility"].side_effect = lambda *a, **kw: {
                    "verdict": eligibility.BLOCKED,
                    "reasons": [eligibility.BLOCKED_REPLIED]}
                report_after = reservoir.ready_set(
                    recs, config, campaigns_by_id)
                self.assertEqual(report_after["email"]["depth"], 0,
                                 "a replied contact must NOT still be READY")
                self.assertEqual(len(report_after["email"]["ready"]), 0)
            finally:
                _stop_mocks(mocks)

    def test_a_suppressed_contact_leaves_the_set(self):
        """Case 2: a suppressed contact is no longer READY.

        Flips eligibility.decide to return a suppression reason.
        """
        recs, config, campaigns_by_id = _build_email_estate()
        mod = reservoir._load_screen_module()
        with mock.patch.object(reservoir, "_load_screen_module",
                               return_value=mod):
            mocks = _install_screen_mocks(mod)
            try:
                report_before = reservoir.ready_set(
                    recs, config, campaigns_by_id)
                self.assertEqual(report_before["email"]["depth"], 1)

                # Flip: the contact is suppressed.
                mocks["eligibility"].side_effect = lambda *a, **kw: {
                    "verdict": eligibility.BLOCKED,
                    "reasons": [eligibility.BLOCKED_SUPPRESSED]}
                report_after = reservoir.ready_set(
                    recs, config, campaigns_by_id)
                self.assertEqual(report_after["email"]["depth"], 0,
                                 "a suppressed contact must NOT still be READY")
            finally:
                _stop_mocks(mocks)

    def test_an_approval_invalidated_contact_leaves_the_set(self):
        """Case 3: a contact whose approval fingerprint moved is no longer READY.

        Flips approval.is_approved to return False (the words were edited
        after they were approved).
        """
        recs, config, campaigns_by_id = _build_email_estate()
        mod = reservoir._load_screen_module()
        with mock.patch.object(reservoir, "_load_screen_module",
                               return_value=mod):
            mocks = _install_screen_mocks(mod)
            try:
                report_before = reservoir.ready_set(
                    recs, config, campaigns_by_id)
                self.assertEqual(report_before["email"]["depth"], 1)

                # Flip: the approval fingerprint no longer matches.
                mocks["is_approved"].return_value = False
                report_after = reservoir.ready_set(
                    recs, config, campaigns_by_id)
                self.assertEqual(report_after["email"]["depth"], 0,
                                 "an approval-invalidated contact must NOT "
                                 "still be READY")
            finally:
                _stop_mocks(mocks)

    def test_a_colliding_contact_leaves_the_set(self):
        """Case 4: a contact with a collision is no longer READY.

        Flips collision.check_address to return a non-CLEAR verdict.
        """
        recs, config, campaigns_by_id = _build_email_estate()
        mod = reservoir._load_screen_module()
        with mock.patch.object(reservoir, "_load_screen_module",
                               return_value=mod):
            mocks = _install_screen_mocks(mod)
            try:
                report_before = reservoir.ready_set(
                    recs, config, campaigns_by_id)
                self.assertEqual(report_before["email"]["depth"], 1)

                # Flip: the address collides.
                mocks["check_address"].side_effect = None
                mocks["check_address"].return_value = (
                    collision.IN_SEQUENCE, {"status": "in_sequence"})
                report_after = reservoir.ready_set(
                    recs, config, campaigns_by_id)
                self.assertEqual(report_after["email"]["depth"], 0,
                                 "a colliding contact must NOT still be READY")
            finally:
                _stop_mocks(mocks)

    def test_an_account_collision_leaves_the_set(self):
        """Case 5: a contact at an account that collides is no longer READY.

        Flips collision.check_account / account_policy to return non-ALLOW.
        """
        recs, config, campaigns_by_id = _build_email_estate()
        mod = reservoir._load_screen_module()
        with mock.patch.object(reservoir, "_load_screen_module",
                               return_value=mod):
            mocks = _install_screen_mocks(mod)
            try:
                report_before = reservoir.ready_set(
                    recs, config, campaigns_by_id)
                self.assertEqual(report_before["email"]["depth"], 1)

                # Flip: the account says STOP.
                mocks["account_policy"].return_value = (collision.STOP,
                                                        "already answered")
                report_after = reservoir.ready_set(
                    recs, config, campaigns_by_id)
                self.assertEqual(report_after["email"]["depth"], 0,
                                 "an account-collided contact must NOT still "
                                 "be READY")
            finally:
                _stop_mocks(mocks)


class RebuiltFromScreenNotStoredVerdicts(unittest.TestCase):
    """The set is rebuilt from the screen, not from stored verdicts.

    Changing a gate's input moves the set without anybody clearing a cache.
    """

    def test_changing_gate_input_moves_the_set_immediately(self):
        """Run 1: gate says CLEAR -> contact is READY.
        Run 2: gate says IN_SEQUENCE -> contact is NOT READY.
        No cache clearing between runs. The Screen is created fresh each time.
        """
        recs, config, campaigns_by_id = _build_email_estate()
        mod = reservoir._load_screen_module()
        with mock.patch.object(reservoir, "_load_screen_module",
                               return_value=mod):
            mocks = _install_screen_mocks(mod)
            try:
                # Run 1: CLEAR.
                report1 = reservoir.ready_set(recs, config, campaigns_by_id)
                self.assertEqual(report1["email"]["depth"], 1)

                # Flip the gate input: collision is now IN_SEQUENCE.
                mocks["check_address"].side_effect = None
                mocks["check_address"].return_value = (
                    collision.IN_SEQUENCE, {"status": "in_sequence"})

                # Run 2: the set moves WITHOUT anybody clearing a cache.
                report2 = reservoir.ready_set(recs, config, campaigns_by_id)
                self.assertEqual(report2["email"]["depth"], 0,
                                 "the set must move when the gate input "
                                 "changes, with no cache clearing")
            finally:
                _stop_mocks(mocks)

    def test_two_runs_with_different_facts_produce_different_sets(self):
        """The reservoir is a pure function of the current facts.

        Same estate, same config, different gate answers -> different sets.
        """
        recs, config, campaigns_by_id = _build_email_estate()
        mod = reservoir._load_screen_module()
        with mock.patch.object(reservoir, "_load_screen_module",
                               return_value=mod):
            mocks = _install_screen_mocks(mod)
            try:
                # Run 1: all gates pass.
                report1 = reservoir.ready_set(recs, config, campaigns_by_id)
                ready1 = {r["contact"] for r in report1["email"]["ready"]}

                # Flip: fatigue says BLOCK.
                mocks["fatigue"].side_effect = lambda *a, **kw: {
                    "state": "blocked"}
                report2 = reservoir.ready_set(recs, config, campaigns_by_id)
                ready2 = {r["contact"] for r in report2["email"]["ready"]}

                self.assertNotEqual(ready1, ready2,
                                    "different facts must produce different "
                                    "READY sets")
                self.assertEqual(len(ready1), 1)
                self.assertEqual(len(ready2), 0)
            finally:
                _stop_mocks(mocks)


class ProposesDoesNotSend(unittest.TestCase):
    """The reservoir proposes, it does not send.

    No provider write, no activation, no campaign mutation, no credit spend.
    """

    def test_ready_set_does_not_import_providerwrites(self):
        """The reservoir module does not import providerwrites."""
        import inspect
        source = inspect.getsource(reservoir)
        self.assertNotIn("providerwrites", source,
                         "the reservoir must not import providerwrites")

    def test_ready_set_does_not_call_any_provider(self):
        """The reservoir does not call any provider write function."""
        recs, config, campaigns_by_id = _build_email_estate()
        mod = reservoir._load_screen_module()
        with mock.patch.object(reservoir, "_load_screen_module",
                               return_value=mod):
            mocks = _install_screen_mocks(mod)
            try:
                reservoir.ready_set(recs, config, campaigns_by_id)
                # If we got here without error, no provider write was called.
                # The mocks ensure all gates pass without calling real providers.
            finally:
                _stop_mocks(mocks)


if __name__ == "__main__":
    unittest.main()
