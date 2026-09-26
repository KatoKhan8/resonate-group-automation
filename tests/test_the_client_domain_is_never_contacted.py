"""The client's own domain is never contacted.

TASK-354, operator decision 2026-09-26. `config/clients/productive.yaml`
`domain` was `productive.test` (a reserved TLD) and is now the client's
real domain. The self-exclusion check refuses any contact whose email
matches the configured domain.

Two things must be true:

1. An address at the client's configured domain is refused as a prospect.
2. The OLD value no longer protects anything.

The check is on the CONTACT'S EMAIL DOMAIN, not the record's domain.
"""
import unittest

from src import clients, eligibility


class TheClientDomainIsRefused(unittest.TestCase):
    """A contact whose email matches the client's configured domain is blocked."""

    def test_matching_email_is_blocked(self):
        config = {"domain": "client.test"}
        rec = {"id": "test-rec", "client": "test", "domain": "acme.test",
               "state": "verified"}
        contact = {"key": "jane", "email": "jane@client.test",
                   "name": "Jane Doe"}
        reasons = eligibility.must_not_contact(rec, contact, config=config)
        self.assertIn(eligibility.BLOCKED_CLIENT_DOMAIN,
                      [r for r in reasons if r is not None])

    def test_matching_email_case_insensitive(self):
        config = {"domain": "client.test"}
        rec = {"id": "test-rec", "client": "test", "domain": "acme.test",
               "state": "verified"}
        contact = {"key": "jane", "email": "jane@CLIENT.TEST",
                   "name": "Jane Doe"}
        reasons = eligibility.must_not_contact(rec, contact, config=config)
        self.assertIn(eligibility.BLOCKED_CLIENT_DOMAIN,
                      [r for r in reasons if r is not None])


class TheOldDomainNoLongerProtects(unittest.TestCase):
    """When the config domain changes, the old value no longer protects."""

    def test_old_domain_is_not_blocked(self):
        config = {"domain": "newclient.test"}
        rec = {"id": "test-rec", "client": "test", "domain": "acme.test",
               "state": "verified"}
        contact = {"key": "bob", "email": "bob@oldclient.test",
                   "name": "Bob Test"}
        reasons = eligibility.must_not_contact(rec, contact, config=config)
        self.assertNotIn(eligibility.BLOCKED_CLIENT_DOMAIN,
                         [r for r in reasons if r is not None])


class NonClientDomainsAreUnaffected(unittest.TestCase):
    """A contact at a normal prospect domain is not refused."""

    def test_prospect_domain_passes(self):
        config = {"domain": "client.test"}
        rec = {"id": "test-rec", "client": "test",
               "domain": "acme-agency.test", "state": "verified"}
        contact = {"key": "alice", "email": "alice@acme-agency.test",
                   "name": "Alice Prospect"}
        reasons = eligibility.must_not_contact(rec, contact, config=config)
        self.assertNotIn(eligibility.BLOCKED_CLIENT_DOMAIN,
                         [r for r in reasons if r is not None])


class NoDomainConfiguredDoesNotRefuse(unittest.TestCase):
    """A client config with no domain field does not refuse anyone."""

    def test_missing_domain_is_safe(self):
        config = {}
        rec = {"id": "test-rec", "client": "test", "domain": "acme.test",
               "state": "verified"}
        contact = {"key": "alice", "email": "alice@anything.test",
                   "name": "Alice"}
        reasons = eligibility.must_not_contact(rec, contact, config=config)
        self.assertNotIn(eligibility.BLOCKED_CLIENT_DOMAIN,
                         [r for r in reasons if r is not None])


class TheRealConfigLoads(unittest.TestCase):
    """The real productive.yaml loads and has the updated domain."""

    def test_productive_config_domain_is_set(self):
        config = clients.load("productive")
        # The domain must not be the old placeholder
        self.assertNotEqual(config.get("domain"), "productive.test")
        # The domain must be set
        self.assertTrue(config.get("domain"),
                        "domain must be set in productive.yaml")


class TheHumanReadableReason(unittest.TestCase):
    """The new blocked code has a human-readable sentence."""

    def test_it_is_in_human(self):
        self.assertIn(eligibility.BLOCKED_CLIENT_DOMAIN, eligibility.HUMAN)


if __name__ == "__main__":
    unittest.main()
