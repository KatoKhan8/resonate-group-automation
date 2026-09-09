"""MX policy categories, and the contract the rest of the system reads.

`tests/test_mx.py` covers vendor recognition, the cache and the push invariant.
This file covers what was added on top: a policy expressed over categories
rather than vendor names, and the stable field names a preview or a UI reads.

The rule these exist to protect is that "which vendor is this" and "how hard
does it filter" stay separate questions. Collapsing them is how Microsoft 365
ends up blocked for being Microsoft.
"""
import unittest

from src import channels, mx
from tests.base import ProviderTest

GOOGLE = ["aspmx.l.google.com"]
MICROSOFT = ["x-com.mail.protection.outlook.com"]
PROOFPOINT = ["mx1-us1.ppe-hosted.com"]
MIMECAST = ["eu-smtp-inbound-1.mimecast.com"]
BARRACUDA = ["x.ess.barracudanetworks.com"]
CISCO = ["mx.iphmx.com"]
MAILCHANNELS = ["mx.mailchannels.net"]


class TestTheCategories(unittest.TestCase):
    def test_there_are_exactly_four(self):
        self.assertEqual(mx.CATEGORIES,
                         (mx.NORMAL, mx.PROTECTED, mx.HIGH_PROTECTION,
                          mx.UNKNOWN_CATEGORY))

    def test_every_known_provider_has_one(self):
        for key in mx.ALL_KNOWN:
            self.assertIn(mx.category_of(key), mx.CATEGORIES, key)

    def test_the_three_blocked_by_default_are_the_high_protection_three(self):
        self.assertEqual(mx.providers_in(mx.HIGH_PROTECTION),
                         ("barracuda", "mimecast", "proofpoint"))

    def test_every_mailbox_host_is_normal(self):
        """The category is about filtering, not about who runs the mailbox."""
        for key in mx.MAILBOX_HOSTS:
            self.assertEqual(mx.category_of(key), mx.NORMAL, key)

    def test_an_unrecognised_provider_is_unknown_not_normal(self):
        self.assertEqual(mx.category_of("something-new"), mx.UNKNOWN_CATEGORY)
        self.assertEqual(mx.category_of(None), mx.UNKNOWN_CATEGORY)

    def test_the_blocked_list_is_derived_from_the_categories(self):
        """So adding a vendor cannot silently change anybody's policy."""
        self.assertEqual(tuple(mx.DEFAULTS["blocked_providers"]),
                         mx.providers_in(mx.HIGH_PROTECTION))

    def test_mailchannels_is_recognised_and_not_treated_as_a_gateway(self):
        decision = mx.decide(MAILCHANNELS, mx.settings({}), domain="x.test")
        self.assertEqual(decision["mx_provider"], "mailchannels")
        self.assertEqual(decision["mx_classification"], mx.NORMAL)
        self.assertTrue(decision["email_eligible"])


class TestThePolicyIsConfigurable(unittest.TestCase):
    def policy(self, **categories):
        return mx.settings({"email_security": {"mx_filter":
                                               {"category_policy": categories}}})

    def test_the_default_blocks_high_protection_and_nothing_else(self):
        policy = mx.settings({})
        self.assertEqual(policy["category_policy"][mx.HIGH_PROTECTION], "block")
        for category in (mx.NORMAL, mx.PROTECTED, mx.UNKNOWN_CATEGORY):
            self.assertEqual(policy["category_policy"][category], "allow")

    def test_a_client_may_block_a_whole_category(self):
        policy = self.policy(protected="block")
        decision = mx.decide(CISCO, policy, domain="x.test")
        self.assertFalse(decision["email_eligible"])
        self.assertEqual(decision["email_excluded_reason"],
                         "mx_protection:cisco")

    def test_a_client_may_unblock_high_protection(self):
        policy = self.policy(high_protection="allow")
        # The vendor list still names them, so the explicit list still wins.
        policy["blocked_providers"] = ()
        self.assertTrue(mx.decide(PROOFPOINT, policy,
                                  domain="x.test")["email_eligible"])

    def test_a_mailbox_host_cannot_be_blocked_even_by_category(self):
        """Blocking `normal` would delete the addressable market.

        Google, Microsoft, Zoho and Fastmail are where most prospects keep
        their mail. A category policy that reached them would be a footgun
        with no legitimate use, so the guard is that the category rule applies
        to gateways only - the same rule that stops a vendor name blocking
        them.
        """
        policy = self.policy(normal="block")
        for hosts in (GOOGLE, MICROSOFT):
            self.assertTrue(mx.decide(hosts, policy,
                                      domain="x.test")["email_eligible"], hosts)

    def test_a_normal_category_gateway_can_still_be_blocked(self):
        """MailChannels is a relay rather than a mailbox host, so it is
        reachable by policy even though it is categorised normal."""
        policy = self.policy(normal="block")
        decision = mx.decide(MAILCHANNELS, policy, domain="x.test")
        self.assertFalse(decision["email_eligible"])
        self.assertEqual(decision["email_excluded_reason"],
                         "mx_protection:mailchannels")

    def test_an_unknown_category_name_is_ignored(self):
        policy = self.policy(**{"extremely_protected": "block"})
        self.assertEqual(policy["category_policy"], mx.DEFAULT_CATEGORY_POLICY)

    def test_an_unknown_verdict_falls_back_to_the_default(self):
        policy = self.policy(high_protection="maybe")
        self.assertEqual(policy["category_policy"][mx.HIGH_PROTECTION], "block")

    def test_a_non_dictionary_policy_is_ignored_rather_than_obeyed(self):
        policy = mx.settings({"email_security":
                              {"mx_filter": {"category_policy": "block"}}})
        self.assertEqual(policy["category_policy"], mx.DEFAULT_CATEGORY_POLICY)

    def test_microsoft_and_google_survive_a_strict_gateway_policy(self):
        policy = self.policy(protected="block", high_protection="block")
        for hosts in (GOOGLE, MICROSOFT):
            self.assertTrue(mx.decide(hosts, policy,
                                      domain="x.test")["email_eligible"], hosts)


class TestTheStoredContract(unittest.TestCase):
    """The field names a preview, a report or a future UI reads."""

    FIELDS = ("mx_records", "mx_provider", "mx_classification",
              "mx_checked_at", "email_eligible", "email_excluded_reason")

    def test_every_decision_carries_every_field(self):
        for hosts in (GOOGLE, PROOFPOINT, CISCO, []):
            decision = mx.decide(hosts, mx.settings({}), domain="x.test")
            for field in self.FIELDS:
                self.assertIn(field, decision, f"{hosts}: {field}")

    def test_the_two_vocabularies_never_disagree(self):
        for hosts in (GOOGLE, PROOFPOINT, MIMECAST, BARRACUDA, CISCO, []):
            decision = mx.decide(hosts, mx.settings({}), domain="x.test")
            self.assertEqual(decision["email_eligible"],
                             decision["email_cadence_allowed"], hosts)
            self.assertEqual(decision["mx_provider"],
                             decision["security_provider"], hosts)
            self.assertEqual(decision["mx_checked_at"],
                             decision["checked_at"], hosts)

    def test_a_blocked_contact_gets_the_documented_reason_string(self):
        for hosts, vendor in ((PROOFPOINT, "proofpoint"), (MIMECAST, "mimecast"),
                              (BARRACUDA, "barracuda")):
            decision = mx.decide(hosts, mx.settings({}), domain="x.test")
            self.assertEqual(decision["email_excluded_reason"],
                             f"mx_protection:{vendor}")

    def test_an_allowed_contact_has_no_exclusion_reason(self):
        decision = mx.decide(GOOGLE, mx.settings({}), domain="x.test")
        self.assertIsNone(decision["email_excluded_reason"])

    def test_a_failure_reason_names_the_failure_not_a_vendor(self):
        self.assertEqual(mx.decide([], mx.settings({}),
                                   domain="x.test")["email_excluded_reason"],
                         "mx_no_mx")
        self.assertEqual(mx.decide([], mx.settings({}), status=mx.DNS_FAILURE,
                                   domain="x.test")["email_excluded_reason"],
                         "mx_dns_failure")

    def test_the_reason_is_greppable_and_stable(self):
        reason = mx.decide(PROOFPOINT, mx.settings({}),
                           domain="x.test")["email_excluded_reason"]
        prefix, vendor = reason.split(":", 1)
        self.assertEqual(prefix, mx.PROTECTION_REASON)
        self.assertIn(vendor, mx.GATEWAYS)

    def test_a_human_can_be_told_what_the_reason_means(self):
        reason = mx.decide(MIMECAST, mx.settings({}),
                           domain="x.test")["email_excluded_reason"]
        self.assertIn("Mimecast", channels.explain(reason))


class TestResolverFailures(ProviderTest):
    """Malformed answers and timeouts, which real DNS produces regularly."""

    def resolve_with(self, resolver):
        return mx.for_domain("x.test", {}, cache={}, resolver=resolver,
                             save=False)

    def test_a_timeout_holds_the_channel(self):
        def timeout(domain, **kw):
            raise TimeoutError("no answer in 3s")
        decision = self.resolve_with(timeout)
        self.assertEqual(decision["status"], mx.DNS_FAILURE)
        self.assertFalse(decision["email_eligible"])

    def test_a_malformed_response_is_a_failure_not_a_guess(self):
        def malformed(domain, **kw):
            raise mx.MXError("truncated answer")
        decision = self.resolve_with(malformed)
        self.assertEqual(decision["status"], mx.DNS_FAILURE)
        self.assertIsNone(decision["mx_provider"])

    def test_junk_hostnames_classify_as_unknown_rather_than_crashing(self):
        decision = self.resolve_with(lambda d, **kw: ["", "...", "@@@", None])
        self.assertIn(decision["status"], (mx.UNKNOWN_PROVIDER, mx.NO_MX))
        self.assertIsNone(decision["mx_provider"])

    def test_an_empty_answer_is_no_mx(self):
        decision = self.resolve_with(lambda d, **kw: [])
        self.assertEqual(decision["status"], mx.NO_MX)
        self.assertFalse(decision["email_eligible"])

    def test_a_failure_is_not_cached(self):
        cache = {}
        def timeout(domain, **kw):
            raise TimeoutError()
        mx.for_domain("x.test", {}, cache=cache, resolver=timeout, save=False)
        self.assertEqual(cache, {}, "a bad second must not hold email a week")

    def test_a_success_is_cached_with_its_classification_recoverable(self):
        cache = {}
        mx.for_domain("x.test", {}, cache=cache,
                      resolver=lambda d, **kw: PROOFPOINT, save=False)
        self.assertIn("x.test", cache)
        again = mx.for_domain("x.test", {}, cache=cache,
                              resolver=lambda d, **kw: GOOGLE, save=False)
        self.assertTrue(again["cached"])
        self.assertEqual(again["mx_classification"], mx.HIGH_PROTECTION,
                         "the cache must not lose the classification")

    def test_the_resolver_is_never_called_when_filtering_is_off(self):
        called = []
        mx.for_domain("x.test",
                      {"email_security": {"mx_filter": {"enabled": False}}},
                      cache={}, resolver=lambda d, **kw: called.append(d),
                      save=False)
        self.assertEqual(called, [])

    def test_no_network_was_touched(self):
        self.assertEqual(self.cassette.calls, [])


if __name__ == "__main__":
    unittest.main()
