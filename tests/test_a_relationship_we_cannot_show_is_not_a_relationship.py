#!/usr/bin/env python3
"""A first touch may not claim a second one.

The defect, measured on 2026-09-13 while selecting a live canary. The
generator produced this for a prospect nobody had ever written to:

    "I want to make sure our last conversation landed clearly, so I am
     following up directly. We missed the deadline for the brand audit
     deliverable last week. That was on us."

There was no conversation, no deliverable and no deadline. It passed lint and
it passed claims, and it was one approval away from a real CEO.

WHY IT PASSED. Every rule in `claims` asks what a sentence says about the
PROSPECT, so a sentence about US was treated as harmless - `GENERIC_SUBJECTS`
returns early for anything opening "we", "our" or "I". An assertion of shared
history is about us AND them, and it went straight through that exit. The
question branch had the same hole: "did you get my last email?" asserts a
previous email and contains a question mark.

This is worse than an unsupported figure. A wrong headcount is an error the
recipient may not notice; an invented relationship is a lie, and they are the
one person guaranteed to know it.
"""
import unittest

from src import claims, events, store
from tests.base import QueueTest


def record(with_touch=False, contact_key="ck-1", touch_contact=None):
    rec = {
        "id": "rec-1", "client": "productive", "domain": "acme.test",
        "company": "Acme Studio", "state": "ready",
        "company_facts": {"name": "Acme Studio", "employees": 40,
                          "industry": "Design Services",
                          "offices": ["Dublin, IE"]},
        "research": [], "events": [], "log": [],
        "contacts": [{"key": contact_key, "email": "dana@acme.test",
                      "first_name": "Dana", "last_name": "Reed",
                      "sendable": True}],
    }
    if with_touch:
        rec["events"].append({
            "type": events.EMAIL_DELIVERED,
            "contact": touch_contact or contact_key,
            "channel": "email", "at": "2026-09-01T09:00:00Z"})
    return rec


def contact_of(rec):
    return rec["contacts"][0]


# Straight from the operator's list, plus the two the generator actually
# wrote. None of these may ship to somebody nobody has written to.
UNSUPPORTED = (
    "We spoke before about your resourcing.",
    "Following up on our previous conversation about utilisation.",
    "When we last connected you were mid-rebrand.",
    "As discussed, here is the outline.",
    "As we agreed, I am sending the scope over.",
    "Circling back on this.",
    "Just looping back about the audit.",
    "You mentioned that resourcing was the bottleneck.",
    "You told me your team was at capacity.",
    "You asked for pricing last month.",
    "We have worked together on delivery before.",
    "I have been following your work for a while.",
    "I've been tracking your studio for months.",
    "Did you get my last email?",
    "Sorry for the delay on our end.",
    "We missed the deadline for the brand audit deliverable last week.",
    "I want to make sure our last conversation landed clearly.",
    "Per our call, the revised timeline is Friday.",
    "As promised, the deck is attached.",
    "Checking back after we spoke.",
    # Named by date rather than by "last", which the first version of the
    # rule required. The generator wrote this one too, and it passed.
    "The 2026-09-10 email thread highlights a gap in domain validation.",
    "We own the oversight of the initial outreach timeline.",
    "Our call last Tuesday covered the scope.",
)

# Ordinary first-touch copy. A guard that refuses these is a guard somebody
# switches off, which is the failure mode the HEDGES comment already records.
NEUTRAL = (
    "I work with design studios on resourcing.",
    "Would you be open to a short call this week?",
    "Acme Studio is a design services company in Dublin.",
    "If resourcing is not a priority right now, that is a fair answer.",
    "We help agencies connect project delivery to finance.",
    "I am reaching out because you lead production at Acme Studio.",
    "Most studios we work with bill on utilisation.",
    "We discussed our roadmap internally and thought of you.",
    # Our own experience, described honestly. The relative clause puts the
    # verb beside "we" without saying anything about the recipient, and a
    # first version of the rule refused all four.
    "Most operations leads we speak to are running scheduling in one place.",
    "Most operations leads we spoke to were running scheduling in one place.",
    "The agencies we worked with last year had the same problem.",
    "Clients we met had the same problem.",
    "Our team has worked on delivery tooling for eight years.",
    # "the email" is not a shared artefact until something says it is.
    "I will keep the email short.",
    "The email below explains it.",
    "Would a short call this week work?",
)


class AnInventedHistoryIsRefused(QueueTest):

    def test_every_unsupported_relationship_claim_is_refused(self):
        rec = record()
        store.save([rec])
        for sentence in UNSUPPORTED:
            with self.subTest(sentence=sentence):
                problems = claims.check(sentence, rec, contact_of(rec))
                self.assertTrue(
                    problems,
                    f"shipped without evidence of contact: {sentence!r}")
                self.assertIn("contacted this person before",
                              problems[0]["why"])

    def test_the_two_the_generator_actually_wrote(self):
        """Named separately: these are the ones that got to a live canary."""
        rec = record()
        body = ("I want to make sure our last conversation landed clearly, "
                "so I am following up directly. We missed the deadline for "
                "the brand audit deliverable last week. That was on us.")
        problems = claims.check(body, rec, contact_of(rec))
        self.assertGreaterEqual(len(problems), 2, problems)

    def test_ordinary_first_touch_copy_still_ships(self):
        rec = record()
        for sentence in NEUTRAL:
            with self.subTest(sentence=sentence):
                self.assertEqual(
                    claims.check(sentence, rec, contact_of(rec)), [],
                    f"refused honest first-touch copy: {sentence!r}")


class EvidenceOfContactLicensesIt(QueueTest):
    """The gate allows the language when the record can show the history."""

    def test_a_confirmed_touch_licenses_the_follow_up(self):
        rec = record(with_touch=True)
        for sentence in ("Following up on our previous conversation.",
                         "As discussed, here is the outline.",
                         "Circling back on this."):
            with self.subTest(sentence=sentence):
                self.assertEqual(claims.check(sentence, rec, contact_of(rec)),
                                 [], sentence)

    def test_a_reply_licenses_it_too(self):
        rec = record()
        rec["events"].append({"type": events.REPLY_RECEIVED, "contact": "ck-1",
                              "channel": "email", "at": "2026-09-02T10:00:00Z"})
        self.assertEqual(
            claims.check("You mentioned resourcing was the bottleneck.",
                         rec, contact_of(rec)), [])

    def test_a_colleagues_history_does_not_license_it(self):
        """The account has been contacted. This person has not.

        `collision` treats a colleague mid-sequence as a fact about the
        company, and it is - but "we spoke last week" is a fact about a
        PERSON, and saying it to somebody else at the same company is still
        false.
        """
        rec = record(with_touch=True, touch_contact="somebody-else")
        problems = claims.check("When we last connected you were mid-rebrand.",
                                rec, contact_of(rec))
        self.assertTrue(problems, "a colleague's touch licensed this person")

    def test_a_planned_step_is_not_contact(self):
        """Drafted and never sent is not a conversation."""
        rec = record()
        rec["events"].append({"type": "push_prepared", "contact": "ck-1",
                              "at": "2026-09-02T10:00:00Z"})
        self.assertTrue(
            claims.check("As discussed, here is the outline.",
                         rec, contact_of(rec)),
            "a prepared-but-unsent step licensed a shared history")


class TheDetectorItself(unittest.TestCase):
    """Guard the guard: a matcher that matches nothing passes everything."""

    def test_it_finds_the_phrase_and_says_which(self):
        found = claims.implies_prior_contact("As discussed, here is the plan.")
        self.assertTrue(found)
        self.assertIn("discussed", found.lower())

    def test_it_does_not_fire_on_neutral_copy(self):
        for sentence in NEUTRAL:
            with self.subTest(sentence=sentence):
                self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_inflections_are_covered_without_a_list_per_tense(self):
        for sentence in ("We spoke last week.", "We have spoken before.",
                         "When we talked you mentioned scope.",
                         "Since we connected, things have moved."):
            with self.subTest(sentence=sentence):
                self.assertIsNotNone(claims.implies_prior_contact(sentence))

    def test_it_is_a_claim_before_any_exemption_applies(self):
        """The two exits that let this through: first person, and questions."""
        self.assertTrue(claims.is_claim("We missed the deadline last week."))
        self.assertTrue(claims.is_claim("Did you get my last email?"))
        self.assertTrue(claims.is_claim("As discussed, here is the plan."))


if __name__ == "__main__":
    unittest.main()
