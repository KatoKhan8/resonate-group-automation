"""The wrong-angle guard holds on the channel that actually sends.

`personas.default_angle` returns None when no configured angle fits a person -
a finance lead in a persona defining only founder wording - so that they are
held rather than written to with the wrong words. Its docstring says exactly
that, and `lint.check` enforced it with `domains_contact_no_angle`.

`lint.check_linkedin` did not. And `cadence.angle_words` falls back to the
first angle in the map when a contact carries none:

    phrase = angles.get(angle) if angle else None
    if not phrase:
        phrase = next(iter(angles.values()), "how the work is tracked")

So the held contact was silently given somebody else's copy, chosen by
dictionary insertion order, on LinkedIn - while the email version of the same
message was correctly blocked. Measured on the pilot: a Director of Digital
Project Managers with `angle: None` rendered a clean, lint-passing connection
note arguing "margin per project", which is finance framing. The email steps
were held. The LinkedIn steps were queued.

The guard that stops it existed and covered the blocked channel, not the
sending one. That is the failure this file pins.
"""
import unittest

from src import cadence, clients, lint


def record(angle):
    contact = {"key": "c1", "name": "Pat Doe",
               "title": "Director of Digital Project Managers",
               "email": "pat@acme.test", "linkedin": "pat-doe",
               "persona": "champion"}
    if angle:
        contact["angle"] = angle
    return {"id": "r1", "client": "productive", "lane": "domains",
            "domain": "acme.test", "company": "Acme", "hook": "h",
            "contacts": [contact]}


NOTE = {"channel": "linkedin", "step": "day3",
        "note": "hi Pat, i work with agencies on how the work is tracked. "
                "curious how Acme handles it at your size. happy to connect."}


class TheAngleGuardHoldsOnLinkedIn(unittest.TestCase):

    def setUp(self):
        self.config = clients.load("productive")

    def test_a_contact_with_no_angle_is_caught_on_linkedin(self):
        fails = lint.check_linkedin(record(None), "c1", NOTE)
        self.assertIn("domains_contact_no_angle", fails)

    def test_the_email_path_still_catches_it_too(self):
        """Both channels, or the guard is only half a guard."""
        step = {"channel": "email", "subject": "a fine subject",
                "body": "A real body with enough words to clear the length "
                        "rule, written plainly and without any of the banned "
                        "filler this linter refuses to let through."}
        self.assertIn("domains_contact_no_angle",
                      lint.check(record(None), "c1", step))

    def test_a_contact_with_an_angle_passes(self):
        """Otherwise the guard refuses everybody and proves nothing."""
        self.assertNotIn("domains_contact_no_angle",
                         lint.check_linkedin(record("finance"), "c1", NOTE))

    def test_the_silent_fallback_that_made_it_matter(self):
        """`angle_words` picks the first angle when a contact has none.

        Pinned rather than changed: several callers depend on it returning
        something. What must not happen is that copy reaching a person, and
        the lint guard above is what stops it.
        """
        contact = {"key": "c1", "title": "Director of Digital Project Managers",
                   "persona": "champion"}
        angle, phrase = cadence.angle_words(contact, self.config)
        self.assertIsNone(contact.get("angle"))
        self.assertTrue(phrase, "a contact with no angle still renders copy")


class TheBreakupClaimsNoHistory(unittest.TestCase):
    """It said "rather than keep adding to your inbox" - a claim about our own
    prior sending, on records whose event log is empty. An earlier fix removed
    one history claim from this template, left this one, and described the
    template as claiming nothing. It also said "before I close the file",
    implying a process the prospect never entered."""

    def test_the_body_claims_nothing_about_prior_outreach(self):
        body = cadence.TEMPLATES["breakup"]["body"].lower()
        for claim in ("adding to your inbox", "i have written", "heard back",
                      "close the file", "following up", "as i mentioned",
                      "my last", "circling back"):
            self.assertNotIn(claim, body)


if __name__ == "__main__":
    unittest.main()
