"""The client's own domain is never contacted.

TASK-354, operator decision 2026-09-26. `config/clients/productive.yaml`
`domain` was `productive.test` (a reserved TLD) and is now `productive.io`.

Two things must be true:

1. An address `@productive.io` is refused as a prospect.
2. The OLD value `@productive.test` no longer protects anything.

The check is on the CONTACT'S EMAIL DOMAIN, not the record's domain. A
record for `acme.com` whose contact has `jane@productive.io` is still
refused, because the email reaches the client's own people.
"""
import unittest

from src import clients, eligibility


class TheClientDomainIsRefused(unittest.TestCase):
    """Acceptance: @productive.io is refused as a prospect."""

    def test_productive_io_email_is_blocked(self):
        config = {"domain": "productive.io"}
        rec = {"id": "test-rec", "client": "productive", "domain": "acme.com",
               "state": "verified"}
        contact = {"key": "jane", "email": "jane@productive.io",
                   "name": "Jane Doe"}
        reasons = eligibility.must_not_contact(rec, contact, config=config)
        self.assertIn(eligibility.BLOCKED_CLIENT_DOMAIN,
                      [r for r in reasons if r is not None])

    def test_productive_io_case_insensitive(self):
        config = {"domain": "productive.io"}
        rec = {"id": "test-rec", "client": "productive", "domain": "acme.com",
               "state": "verified"}
        contact = {"key": "jane", "email": "jane@PRODUCTIVE.IO",
                   "name": "Jane Doe"}
        reasons = eligibility.must_not_contact(rec, contact, config=config)
        self.assertIn(eligibility.BLOCKED_CLIENT_DOMAIN,
                      [r for r in reasons if r is not None])


class TheOldDomainNoLongerProtects(unittest.TestCase):
    """The OLD value @productive.test is now unprotected.

    Nothing in the estate should carry one. If it does, it is reported,
    not silently rewritten.
    """

    def test_productive_test_is_not_blocked(self):
        config = {"domain": "productive.io"}
        rec = {"id": "test-rec", "client": "productive", "domain": "acme.com",
               "state": "verified"}
        contact = {"key": "bob", "email": "bob@productive.test",
                   "name": "Bob Test"}
        reasons = eligibility.must_not_contact(rec, contact, config=config)
        self.assertNotIn(eligibility.BLOCKED_CLIENT_DOMAIN,
                         [r for r in reasons if r is not None])


class NonClientDomainsAreUnaffected(unittest.TestCase):
    """A contact at a normal prospect domain is not refused."""

    def test_prospect_domain_passes(self):
        config = {"domain": "productive.io"}
        rec = {"id": "test-rec", "client": "productive",
               "domain": "acme-agency.com", "state": "verified"}
        contact = {"key": "alice", "email": "alice@acme-agency.com",
                   "name": "Alice Prospect"}
        reasons = eligibility.must_not_contact(rec, contact, config=config)
        self.assertNotIn(eligibility.BLOCKED_CLIENT_DOMAIN,
                         [r for r in reasons if r is not None])


class NoDomainConfiguredDoesNotRefuse(unittest.TestCase):
    """A client config with no domain field does not refuse anyone."""

    def test_missing_domain_is_safe(self):
        config = {}
        rec = {"id": "test-rec", "client": "test", "domain": "acme.com",
               "state": "verified"}
        contact = {"key": "alice", "email": "alice@anything.test",
                   "name": "Alice"}
        reasons = eligibility.must_not_contact(rec, contact, config=config)
        self.assertNotIn(eligibility.BLOCKED_CLIENT_DOMAIN,
                         [r for r in reasons if r is not None])


class TheRealConfigLoads(unittest.TestCase):
    """The real productive.yaml loads and has the right domain."""

    def test_productive_config_domain_is_productive_io(self):
        config = clients.load("productive")
        self.assertEqual(config.get("domain"), "productive.io")


class TheHumanReadableReason(unittest.TestCase):
    """The new blocked code has a human-readable sentence."""

    def test_it_is_in_human(self):
        self.assertIn(eligibility.BLOCKED_CLIENT_DOMAIN, eligibility.HUMAN)


if __name__ == "__main__":
    unittest.main()
