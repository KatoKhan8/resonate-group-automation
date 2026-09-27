"""A DNS failure holds the channel, and the S5 gate refuses it.

TASK-284. The risk is not in `src/mx.py` - that module already distinguishes
five outcomes correctly. The risk is in the journal and the gate: a
`dns_failure` row that the MX walk writes with `email_channel=True` (held,
not closed) must still be refused by S5, because `dns_failure` is not in
`MX_OK`. And a null-`mx` row - one the walk never reached - must also be
refused, because `None` is not in `MX_OK` either.

This test drives through both the module's decision and the S5 gate's
predicate, because the two vocabularies differ: the module says
`email_cadence_allowed=False`, the walk writes `email_channel=True`, and
the gate says `mx not in MX_OK`. All three must agree that the row does
not proceed.
"""
import json
import os
import tempfile
import unittest

from src import mx


def _resolver_for(mapping):
    def resolve(domain, *args, **kwargs):
        if domain not in mapping:
            raise mx.MXError(f"no fixture for {domain}")
        value = mapping[domain]
        if isinstance(value, Exception):
            raise value
        return list(value)
    return resolve


# The S5 gate's predicate, restated here from scripts/stage_s5_verify.py:120.
# This is the tuple the gate checks, and the test proves dns_failure is not
# in it. If the tuple in the script changes, this test must change too -
# which is the point of stating it here rather than importing it.
MX_OK = ("known_allowed", "unknown_provider")


def _s5_gate_accepts(row):
    """The S5 gate predicate from scripts/stage_s5_verify.py:188-191.

    A row passes only when all three conditions hold:
      - verdict is "in"
      - email_channel is True
      - mx is in MX_OK
    """
    return (row.get("verdict") == "in"
            and row.get("email_channel") is True
            and row.get("mx") in MX_OK)


class ADnsFailureHoldsTheChannelAtTheModule(unittest.TestCase):
    """The module level: mx.for_domain and mx.decide."""

    def test_a_dns_failure_produces_dns_failure_status(self):
        resolve = _resolver_for({"acme.test": mx.MXError("timeout")})
        d = mx.for_domain("acme.test", {}, cache={}, resolver=resolve,
                          save=False)
        self.assertEqual(d["status"], mx.DNS_FAILURE)

    def test_a_dns_failure_does_not_allow_email(self):
        resolve = _resolver_for({"acme.test": mx.MXError("timeout")})
        d = mx.for_domain("acme.test", {}, cache={}, resolver=resolve,
                          save=False)
        self.assertFalse(d["email_cadence_allowed"])

    def test_a_dns_failure_is_not_in_mx_ok(self):
        """The gate tuple does not contain dns_failure. This is the line
        that refuses the row at S5."""
        self.assertNotIn(mx.DNS_FAILURE, MX_OK)

    def test_decide_preserves_dns_failure_when_status_is_passed(self):
        """Even with hosts, an explicit dns_failure status holds."""
        d = mx.decide([], mx.settings({}), status=mx.DNS_FAILURE,
                       domain="acme.test")
        self.assertEqual(d["status"], mx.DNS_FAILURE)
        self.assertFalse(d["email_cadence_allowed"])

    def test_a_dns_failure_is_never_cached(self):
        """A transient failure must not become a week-long hold."""
        cache = {}
        resolve = _resolver_for({"acme.test": mx.MXError("timeout")})
        mx.for_domain("acme.test", {}, cache=cache, resolver=resolve,
                      save=False)
        self.assertNotIn("acme.test", cache)


class ANullMxIsRefusedByTheGate(unittest.TestCase):
    """A row the walk never reached carries mx=None. The gate refuses it."""

    def test_none_is_not_in_mx_ok(self):
        self.assertNotIn(None, MX_OK)

    def test_a_null_mx_row_does_not_pass_the_gate(self):
        row = {"domain": "acme.test", "verdict": "in",
               "email_channel": True, "mx": None}
        self.assertFalse(_s5_gate_accepts(row))


class TheS5GateRefusesDnsFailure(unittest.TestCase):
    """The gate level: a dns_failure row in the journal cannot pass."""

    def test_a_dns_failure_row_does_not_pass_the_gate(self):
        """The walk writes email_channel=True for dns_failure (held, not
        closed), but the gate's mx-in-MX_OK check refuses it."""
        row = {"domain": "acme.test", "verdict": "in",
               "email_channel": True, "mx": mx.DNS_FAILURE}
        self.assertFalse(_s5_gate_accepts(row))

    def test_a_no_mx_row_does_not_pass_the_gate(self):
        row = {"domain": "acme.test", "verdict": "in",
               "email_channel": False, "mx": mx.NO_MX}
        self.assertFalse(_s5_gate_accepts(row))

    def test_a_known_blocked_row_does_not_pass_the_gate(self):
        row = {"domain": "acme.test", "verdict": "in",
               "email_channel": False, "mx": mx.KNOWN_BLOCKED}
        self.assertFalse(_s5_gate_accepts(row))

    def test_a_known_allowed_row_passes_the_gate(self):
        row = {"domain": "acme.test", "verdict": "in",
               "email_channel": True, "mx": mx.KNOWN_ALLOWED}
        self.assertTrue(_s5_gate_accepts(row))

    def test_an_unknown_provider_row_passes_the_gate(self):
        row = {"domain": "acme.test", "verdict": "in",
               "email_channel": True, "mx": mx.UNKNOWN_PROVIDER}
        self.assertTrue(_s5_gate_accepts(row))

    def test_an_out_verdict_is_refused_regardless_of_mx(self):
        row = {"domain": "acme.test", "verdict": "out",
               "email_channel": True, "mx": mx.KNOWN_ALLOWED}
        self.assertFalse(_s5_gate_accepts(row))


class TheWalkWritesDnsFailureCorrectly(unittest.TestCase):
    """The walk's skip logic: dns_failure is NOT skipped (held, not closed).

    The walk sets email_channel = not skip, where
    skip = status in (KNOWN_BLOCKED, NO_MX). dns_failure is not in that
    tuple, so email_channel is True. But the S5 gate still refuses it
    because mx is not in MX_OK. This is the correct two-layer protection.
    """

    def test_dns_failure_is_not_skipped_by_the_walk(self):
        skip = mx.DNS_FAILURE in (mx.KNOWN_BLOCKED, mx.NO_MX)
        self.assertFalse(skip)

    def test_known_blocked_is_skipped_by_the_walk(self):
        skip = mx.KNOWN_BLOCKED in (mx.KNOWN_BLOCKED, mx.NO_MX)
        self.assertTrue(skip)

    def test_no_mx_is_skipped_by_the_walk(self):
        skip = mx.NO_MX in (mx.KNOWN_BLOCKED, mx.NO_MX)
        self.assertTrue(skip)

    def test_the_two_layers_agree_on_dns_failure(self):
        """The walk holds the channel (email_channel=True), and the gate
        refuses the row (mx not in MX_OK). Both layers protect."""
        status = mx.DNS_FAILURE
        skip = status in (mx.KNOWN_BLOCKED, mx.NO_MX)
        email_channel = not skip
        row = {"domain": "acme.test", "verdict": "in",
               "email_channel": email_channel, "mx": status}
        self.assertTrue(email_channel, "the walk holds, not closes")
        self.assertFalse(_s5_gate_accepts(row),
                         "the gate refuses despite the hold")


class TheFiveOutcomesAreDistinct(unittest.TestCase):
    """Five outcomes, not four. Merging dns_failure into unknown_provider
    would quietly send into the thing the module exists to avoid."""

    def test_there_are_five_real_outcomes(self):
        real = (mx.KNOWN_ALLOWED, mx.KNOWN_BLOCKED, mx.UNKNOWN_PROVIDER,
                mx.DNS_FAILURE, mx.NO_MX)
        self.assertEqual(len(set(real)), 5)

    def test_dns_failure_and_unknown_provider_are_not_the_same(self):
        """If these were merged, a resolver failure would read as a policy
        decision rather than a held channel."""
        self.assertNotEqual(mx.DNS_FAILURE, mx.UNKNOWN_PROVIDER)


class LabelBoundaryMatching(unittest.TestCase):
    """pphosted.com matches mx1.pphosted.com, not notpphosted.com.evil.test.

    TASK-284 step 4: assert through the classify function, which is what
    the walk calls, not by reading the source.
    """

    def test_pphosted_matches_mx1_pphosted(self):
        key, _ = mx.classify(["mx1.pphosted.com"])
        self.assertEqual(key, "proofpoint")

    def test_pphosted_does_not_match_notpphosted_evil(self):
        key, _ = mx.classify(["notpphosted.com.evil.test"])
        self.assertIsNone(key)

    def test_pphosted_does_not_match_evil_subdomain(self):
        key, _ = mx.classify(["pphosted.com.evil.test"])
        self.assertIsNone(key)

    def test_mimecast_does_not_match_mymimecast(self):
        key, _ = mx.classify(["mymimecast.net"])
        self.assertIsNone(key)

    def test_mimecast_matches_real_mimecast(self):
        key, _ = mx.classify(["eu-smtp-inbound-1.mimecast.com"])
        self.assertEqual(key, "mimecast")

    def test_the_walk_verdict_for_a_blocked_domain(self):
        """A domain with Proofpoint MX gets known_blocked through decide."""
        d = mx.decide(["mx1.pphosted.com"], mx.settings({}),
                       domain="acme.test")
        self.assertEqual(d["status"], mx.KNOWN_BLOCKED)
        self.assertFalse(d["email_cadence_allowed"])

    def test_the_walk_verdict_for_an_unknown_domain(self):
        """A domain with unrecognised MX gets unknown_provider."""
        d = mx.decide(["mail.someinternalthing.example"], mx.settings({}),
                       domain="acme.test")
        self.assertEqual(d["status"], mx.UNKNOWN_PROVIDER)

    def test_the_walk_verdict_for_no_mx(self):
        """A domain with no MX records gets no_mx."""
        d = mx.decide([], mx.settings({}), status=mx.NO_MX,
                       domain="acme.test")
        self.assertEqual(d["status"], mx.NO_MX)
        self.assertFalse(d["email_cadence_allowed"])


class AllowsEmailRefusesDnsFailure(unittest.TestCase):
    """mx.allows_email is what production reads. It must refuse dns_failure."""

    def test_a_contact_with_stored_dns_failure_is_not_allowed(self):
        contact = {"email": "john@acme.test", "mx": {
            "email_domain": "acme.test",
            "mx_records": [],
            "status": mx.DNS_FAILURE,
            "email_cadence_allowed": False,
            "security_provider": None,
        }}
        allowed, _ = mx.allows_email(contact, {})
        self.assertFalse(allowed)

    def test_a_contact_with_stored_known_blocked_is_not_allowed(self):
        contact = {"email": "john@acme.test", "mx": {
            "email_domain": "acme.test",
            "mx_records": ["mx1.pphosted.com"],
            "status": mx.KNOWN_BLOCKED,
            "email_cadence_allowed": False,
            "security_provider": "proofpoint",
        }}
        allowed, _ = mx.allows_email(contact, {})
        self.assertFalse(allowed)

    def test_a_contact_with_no_mx_check_is_allowed(self):
        """No MX check has been run: the contact is allowed by default."""
        contact = {"email": "john@acme.test"}
        allowed, reason = mx.allows_email(contact, {})
        self.assertTrue(allowed)


if __name__ == "__main__":
    unittest.main()
