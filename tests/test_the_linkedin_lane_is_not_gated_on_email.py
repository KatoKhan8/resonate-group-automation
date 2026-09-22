#!/usr/bin/env python3
"""A person reachable on LinkedIn must be drafted for, address or no address.

MEASURED ON THE REAL PRODUCTIVE COHORT, 2026-09-12. Of the contacts on
qualified companies, ALL 24 carried a usable LinkedIn profile and 7 were
email-sendable. The rest were catch-all domains reoon would not clear
(`accept_all_uncleared`) or MX gateways the client's own policy closes
(`mx_security_provider_blocked:proofpoint`) - both correct refusals about
EMAIL, and neither of them a fact about LinkedIn.

`generate.plan` opened with:

    sendable = [c for c in rec["contacts"] if lint.sendable(c)]
    if not sendable:
        return ops          # nothing is drafted for an unverified address

That sentence is exactly right for an email draft and wrong for the rest of
the function, because the connection-note branch twenty lines below needs a
LinkedIn profile and no address at all. So a company whose every contact had
an uncleared catch-all got no copy of any kind, on either channel, and
`campaign_ready` stood at 1 of 24 while the channel that could reach 24 of
them was never drafted for.

CLAUDE.md's rule - "No email is generated for an unverified address" - is
untouched. Only the LinkedIn work moved out from behind it, and the tests
below assert both halves, because a fix that unblocked LinkedIn by weakening
the email rule would be worse than the defect.
"""
import unittest

from src import channels, generate, lint, store


def a_contact(key, email, linkedin, verified, angle=None):
    contact = {"key": key, "name": key.replace("-", " ").title(),
               "title": "Head of Operations", "email": email,
               "linkedin": linkedin, "selected": True, "persona": "champion"}
    if angle:
        contact["angle"] = angle
    if verified:
        # Real evidence rows, because `verification.is_sendable` recomputes
        # from the evidence and never reads the stored state - a fixture that
        # set `sendable: True` would be asserting against a cache the product
        # deliberately ignores.
        from src import verification
        contact["verdict"] = "valid"
        contact["sendable"] = True
        contact["verification"] = {
            "state": "verified", "sendable": True, "confirmation_count": 2,
            "evidence": [verification.result("deliverable", verification.S_VALID,
                                             email),
                         verification.result("reoon", verification.S_VALID,
                                             email)]}
    else:
        # The real shape of the blocked half: a catch-all nobody could clear.
        contact["verdict"] = "accept_all"
        contact["sendable"] = False
        contact["verification"] = {"state": "accept_all_uncleared",
                                   "sendable": False, "evidence": [],
                                   "reason": "reoon says the catch-all is not "
                                             "safe to send"}
    return contact


def a_record(contacts, rid="acct-one"):
    rec = store.new_record(rid, "domains", "productive", "Acme", "acme.test")
    rec["state"] = "verified"
    rec["contacts"] = contacts
    rec["hook"] = "resourcing visibility"
    return rec


CLIENT = {"name": "Productive",
          "linkedin_connection_note": {"mode": "llm"}}


class TheEmailRuleIsUntouched(unittest.TestCase):
    """Asserted first and on purpose. Everything below is only acceptable if
    this still holds."""

    def test_no_email_is_drafted_for_an_unverified_address(self):
        rec = a_record([a_contact("dana", "dana@acme.test",
                                  "https://www.linkedin.com/in/dana-marsh",
                                  verified=False, angle="operations")])
        steps = {op["step"] for op in generate.plan(rec, CLIENT)}
        self.assertNotIn("draft", steps,
                         "an email was drafted for an address nobody cleared")

    def test_an_email_is_drafted_for_a_verified_one(self):
        rec = a_record([a_contact("dana", "dana@acme.test",
                                  "https://www.linkedin.com/in/dana-marsh",
                                  verified=True, angle="operations")])
        steps = [op["step"] for op in generate.plan(rec, CLIENT)]
        self.assertIn("draft", steps)


class TheLinkedInLaneOpensWithoutAnAddress(unittest.TestCase):

    def setUp(self):
        self.unverified = a_contact("dana", "dana@acme.test",
                                    "https://www.linkedin.com/in/dana-marsh",
                                    verified=False)
        self.rec = a_record([self.unverified])

    def test_the_contact_is_linkedin_eligible_to_begin_with(self):
        """Without this the rest proves nothing."""
        self.assertFalse(lint.sendable(self.unverified))
        ok, why = channels.linkedin_verdict(self.rec, self.unverified, CLIENT)
        self.assertTrue(ok, why)

    def test_a_connection_note_is_planned(self):
        steps = {op["step"] for op in generate.plan(self.rec, CLIENT)}
        self.assertIn("linkedin_note", steps,
                      "a person with a usable profile and no clearable "
                      "address got no copy written for them at all")

    def test_the_angle_that_the_note_needs_is_planned_too(self):
        """`eligibility` refuses a domains contact with no angle
        (`blocked:lint:domains_contact_no_angle`), which is what 12 of the 24
        real contacts were blocked on. Planning the note and not the angle
        would move the block rather than clear it."""
        steps = {op["step"] for op in generate.plan(self.rec, CLIENT)}
        self.assertIn("persona_angle", steps)

    def test_still_no_email_for_them(self):
        ops = generate.plan(self.rec, CLIENT)
        self.assertEqual([o for o in ops if o["step"] == "draft"], [])


class WhoIsNotOpened(unittest.TestCase):
    """`channels.linkedin_verdict` is asked rather than re-implemented, so its
    refusals have to survive the change."""

    def plan_for(self, **over):
        contact = a_contact("dana", "dana@acme.test",
                            "https://www.linkedin.com/in/dana-marsh",
                            verified=False)
        contact.update(over)
        rec = a_record([contact])
        if over.pop("_unsubscribe_record", None):
            rec["contacts"][0]["unsubscribed"] = True
        return {op["step"] for op in generate.plan(rec, CLIENT)}

    def test_no_profile_is_not_opened(self):
        self.assertEqual(self.plan_for(linkedin=""), set())

    def test_an_unusable_profile_is_not_opened(self):
        """A company page or a search URL. Sending a connection request to one
        is not a smaller mistake than sending it to nobody."""
        self.assertEqual(
            self.plan_for(linkedin="https://www.linkedin.com/company/acme"),
            set())

    def test_an_unsubscribed_person_is_not_opened(self):
        self.assertEqual(self.plan_for(unsubscribed=True), set())

    def test_a_duplicate_is_not_opened(self):
        self.assertEqual(self.plan_for(duplicate_of="somebody-else"), set())


if __name__ == "__main__":
    unittest.main()
