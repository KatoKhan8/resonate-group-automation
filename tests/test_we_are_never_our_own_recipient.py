#!/usr/bin/env python3
"""Our own identities are refused as recipients.

Operator decision B3, 2026-09-30.

THE DEFECT, MEASURED against the real gates before the fix:

    someone@productive.io        BLOCKED  (client_own_domain)
    beslic.zvonimir@gmail.com    PASSES   <- the operator
    zvonimir@resonategroup.co    PASSES   <- the operator
    ivan@resonategroup.co        PASSES   <- our own agency
    225 of 225 sending addresses PASSES   <- the estate could email itself

`must_not_contact` refused the CLIENT's own domain and nothing else of ours.
The 225 addresses are every mailbox EmailBison sends our campaigns from, across
86 lookalike domains, and any of them could have been enrolled as a prospect.
A self-send burns a sending mailbox's reputation against itself and puts a real
send somewhere nobody is reading.

TWO GAPS, and the second is the one that matters. `operatorexclusion.blocks`
reads `rec["domain"]` - the ACCOUNT. A record filed under one company can carry
a contact at another, so an excluded domain reached through a stranger's record
was never asked about. Every sweep below files our own addresses under a
STRANGER's record deliberately: if the account check were what saved us, these
tests would pass while the hole stayed open.

The register is one-way hashed, so no address in it can be read back out of the
file. This test asks the GATE, never the file.
"""
import csv
import os
import unittest

from src import clients, eligibility, ingest, operatorexclusion as oe

SENDERS = os.path.join("work", "sender-emails.csv")

STRANGER = "some-agency.com"


def _record(email, domain=STRANGER):
    return {
        "id": "probe", "domain": domain, "client": "productive",
        "lane": "domains", "state": "ready", "company": "Probe Co",
        "contacts": [{
            "key": "probe", "name": "Probe Person", "first_name": "Probe",
            "title": "Chief Financial Officer", "email": email,
            "persona": "economic_buyer", "angle": "finance",
            "sendable": True, "primary": True,
            "verification": {
                "state": "verified", "sendable": True,
                "evidence": [{"provider": p, "status": "valid",
                              "email": email}
                             for p in ("deliverable", "reoon")]}}],
    }


def _refusal(email, domain=STRANGER, suppressed=None, config=None):
    record = _record(email, domain)
    reasons = eligibility.must_not_contact(
        record, record["contacts"][0],
        config=config if config is not None else clients.load("productive"),
        suppressed=suppressed)
    return next((r for r in reasons if r), None)


class TheOperatorIsNeverARecipient(unittest.TestCase):

    def setUp(self):
        oe.forget()
        self.addCleanup(oe.forget)
        self.suppressed = ingest.load_suppress()
        self.config = clients.load("productive")

    def refusal(self, email, domain=STRANGER):
        return _refusal(email, domain, self.suppressed, self.config)

    def test_the_operators_own_address_is_excluded(self):
        self.assertEqual(self.refusal("beslic.zvonimir@gmail.com"),
                         eligibility.BLOCKED_OPERATOR_EXCLUDED)

    def test_the_operator_at_the_agency_domain_is_excluded(self):
        self.assertEqual(self.refusal("zvonimir@resonategroup.co"),
                         eligibility.BLOCKED_OPERATOR_EXCLUDED)

    def test_anyone_at_the_agency_domain_is_excluded(self):
        self.assertEqual(self.refusal("ivan@resonategroup.co"),
                         eligibility.BLOCKED_OPERATOR_EXCLUDED)

    def test_the_clients_own_domain_is_still_refused(self):
        self.assertIsNotNone(self.refusal("someone@productive.io",
                                          domain="productive.io"))

    def test_a_gmail_prospect_is_not_collateral(self):
        """THE CONTROL THAT MAKES THE OPERATOR'S EXCLUSION HONEST. The
        operator's address is at a public mailbox provider, so it is keyed on
        the ADDRESS. If it had been keyed on the domain this would fail and
        every Gmail prospect would be refused."""
        self.assertIsNone(self.refusal("someone.else@gmail.com"))

    def test_a_stranger_passes(self):
        """The control. Without it a rule that refuses everybody passes."""
        self.assertIsNone(self.refusal("stranger@some-agency.com"))


class TheEstateNeverEmailsItself(unittest.TestCase):

    def setUp(self):
        oe.forget()
        self.addCleanup(oe.forget)
        if not os.path.exists(SENDERS):
            self.skipTest(f"{SENDERS} is gitignored and absent in this clone")
        with open(SENDERS, encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        column = next((c for c in rows[0] if "mail" in c.lower()), None)
        self.addresses = sorted({(r.get(column) or "").strip().lower()
                                 for r in rows
                                 if "@" in (r.get(column) or "")})
        self.suppressed = ingest.load_suppress()
        self.config = clients.load("productive")

    def test_every_sending_mailbox_is_refused_as_a_recipient(self):
        self.assertGreater(len(self.addresses), 200,
                           "the sender inventory looks truncated")
        passing = [a for a in self.addresses
                   if _refusal(a, STRANGER, self.suppressed,
                               self.config) is None]
        self.assertEqual(passing, [],
                         f"{len(passing)} of our own sending mailboxes can be "
                         f"enrolled as prospects, e.g. {passing[:3]}")

    def test_they_are_refused_through_a_strangers_record(self):
        """Stated separately because it is the half the account check misses:
        the refusal must not depend on the record being filed at our domain."""
        one = self.addresses[0]
        self.assertEqual(_refusal(one, STRANGER, self.suppressed, self.config),
                         eligibility.BLOCKED_OPERATOR_EXCLUDED)


class TheBypassesGlmFound(unittest.TestCase):
    """GLM attacked 8e47fc4c and named two escapes. Both were real.

    An exact-match key is not a boundary, and `normalise_email` deliberately
    keeps `+tag`. Measured before the fix: `ivan@eu.resonategroup.co` and
    `beslic.zvonimir+test@gmail.com` both passed `must_not_contact`, while
    `ivan@mail.resonategroup.co` did not - `norm_domain` strips `mail.` and
    `www.` and nothing else, so the hole looked closed from some angles.
    """

    def setUp(self):
        oe.forget()
        self.addCleanup(oe.forget)
        self.suppressed = ingest.load_suppress()
        self.config = clients.load("productive")

    def refusal(self, email):
        return _refusal(email, STRANGER, self.suppressed, self.config)

    def test_a_subdomain_of_the_agency_is_excluded(self):
        self.assertEqual(self.refusal("ivan@eu.resonategroup.co"),
                         eligibility.BLOCKED_OPERATOR_EXCLUDED)

    def test_a_deep_subdomain_is_excluded(self):
        self.assertEqual(self.refusal("ivan@a.b.c.resonategroup.co"),
                         eligibility.BLOCKED_OPERATOR_EXCLUDED)

    def test_a_subdomain_of_a_sending_domain_is_excluded(self):
        self.assertEqual(self.refusal("x@eu.withproductive-ai.com"),
                         eligibility.BLOCKED_OPERATOR_EXCLUDED)

    def test_plus_addressing_does_not_dodge_the_operators_exclusion(self):
        self.assertEqual(self.refusal("beslic.zvonimir+test@gmail.com"),
                         eligibility.BLOCKED_OPERATOR_EXCLUDED)

    def test_repeated_plus_tags_do_not_dodge_it_either(self):
        self.assertEqual(self.refusal("beslic.zvonimir+a+b@gmail.com"),
                         eligibility.BLOCKED_OPERATOR_EXCLUDED)

    def test_gmail_dot_folding_does_not_dodge_it(self):
        """GLM answered UNKNOWN on the operator question until this existed.
        Gmail ignores dots, so `b.eslic.zvonimir@` is the same mailbox as the
        bare form and would otherwise have passed every gate - ordinary Gmail
        prospects do. Folded on Gmail and Googlemail ONLY; everywhere else a
        dot is part of the mailbox name."""
        for spelling in ("b.eslic.zvonimir@gmail.com",
                         "besliczvonimir@gmail.com",
                         "b.e.s.l.i.c.zvonimir+x@gmail.com"):
            with self.subTest(spelling):
                self.assertEqual(self.refusal(spelling),
                                 eligibility.BLOCKED_OPERATOR_EXCLUDED)

    def test_a_dotted_gmail_prospect_is_not_collateral(self):
        """The control for the fold. Dots are folded, not ignored - a
        different Gmail mailbox is still a different person."""
        self.assertIsNone(self.refusal("other.name@gmail.com"))

    def test_dots_are_not_folded_off_gmail(self):
        """A dot is significant nearly everywhere, so the fold must be
        domain-scoped rather than global."""
        self.assertEqual(
            oe._address_variants("a.b", "example.test"), [])
        self.assertIn("ab@gmail.com", oe._address_variants("a.b", "gmail.com"))

    def test_a_lookalike_domain_that_is_not_ours_still_passes(self):
        """THE CONTROL THAT KEEPS THE SUFFIX WALK HONEST. `notresonategroup.co`
        ends with our name and is not us. A walk that matched on substring
        rather than on label boundaries would refuse it."""
        self.assertIsNone(self.refusal("cfo@notresonategroup.co"))

    def test_our_name_under_a_different_tld_still_passes(self):
        self.assertIsNone(self.refusal("x@resonategroup.co.uk"))

    def test_the_walk_stops_before_a_single_label(self):
        """It must never be possible for a one-label key to be asked about,
        or excluding anything would risk excluding a whole TLD."""
        self.assertEqual(oe.domain_and_parents("a.b.example.test"),
                         ["a.b.example.test", "b.example.test",
                          "example.test"])
        self.assertEqual(oe.domain_and_parents("example.test"),
                         ["example.test"])


class TheRegisterKeepsItsTwoKeySpacesApart(unittest.TestCase):

    def test_an_address_key_is_not_a_domain_key(self):
        self.assertNotEqual(oe.address_key("a@example.test"),
                            oe.account_key("example.test"))

    def test_an_unusable_address_has_no_key(self):
        self.assertEqual(oe.address_key(""), "")
        self.assertEqual(oe.address_key(None), "")

    def test_excluding_an_address_does_not_exclude_its_domain(self):
        oe.forget()
        self.addCleanup(oe.forget)
        self.assertTrue(oe.blocks_address("beslic.zvonimir@gmail.com"))
        self.assertFalse(oe.blocks({"domain": "gmail.com"}))


if __name__ == "__main__":
    unittest.main()
