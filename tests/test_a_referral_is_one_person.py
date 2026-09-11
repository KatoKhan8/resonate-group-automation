#!/usr/bin/env python3
"""Two identifiers in a reply are not evidence that they belong to one person.

REPRODUCED END TO END on 2026-09-11. `evidence()` gathers emails, profiles and
names as three INDEPENDENT lists - it says so in its own docstring, "No
interpretation" - and `promotable()` then took `emails[0]` and `profiles[0]`
with nothing tying them together:

    reply     "speak to Dana Reed, dana.reed@acme.test ... you could also try
               Tomas Brabec: linkedin.com/in/tomas-brabec"
    promoted  status=ready  email=dana.reed@acme.test
                            linkedin=.../in/tomas-brabec

One contact, Dana's mailbox, Tomas's profile. The LinkedIn step sends a
connection request to `contact["linkedin"]` with a note greeting
`contact["name"]`, so Tomas would have received an invitation addressed to
Dana, about a conversation he had never had. Two real humans, one contacted
under somebody else's name.

Three things made it reachable rather than theoretical:

  - A reply SIGNATURE is enough. Two identifiers in a body is the ordinary
    shape of a referral, not an exotic one.
  - The approval screen rendered `email or linkedin`, so when an address was
    present the profile was never shown. The operator could not see the half
    that was wrong at the moment of deciding.
  - The caller took `named.split(",")[0]` - the same guess again, in the field
    that becomes the greeting.

The fix refuses rather than resolves. A path that cannot know which identifier
belongs to whom must not choose one.
"""
import unittest

from tests.webbase import WebTest

from src import events, referral, replies
from src.web import api, pages


def a_record(*contacts):
    return {"id": "acme", "domain": "acme.test", "company": "Acme",
            "contacts": list(contacts)}


def promote(body, rec=None):
    rec = rec or a_record()
    return referral.promotable(rec, referral.evidence(body))


class AReplyNamingTwoPeopleIsRefused(unittest.TestCase):

    def test_the_exact_reproduction(self):
        got = promote("please speak to Dana Reed, dana.reed@acme.test, she "
                      "owns this now. you could also try Tomas Brabec: "
                      "https://linkedin.com/in/tomas-brabec")
        self.assertEqual(got["status"], referral.AMBIGUOUS)
        self.assertIsNone(got["email"])
        self.assertIsNone(got["linkedin"])

    def test_a_signature_profile_is_enough_to_make_it_ambiguous(self):
        """The ordinary case, and the one that makes this reachable."""
        got = promote("talk to dana.reed@acme.test -- Marek Havel, CFO, "
                      "https://linkedin.com/in/marek-havel")
        self.assertEqual(got["status"], referral.AMBIGUOUS)

    def test_two_addresses_are_ambiguous_too(self):
        got = promote("try dana.reed@acme.test or tomas.brabec@acme.test")
        self.assertEqual(got["status"], referral.AMBIGUOUS)

    def test_the_refusal_keeps_the_candidates_for_a_person_to_read(self):
        """Refusing must not throw away what the reply said. A human deciding
        from the text is the intended path now, so the text has to reach them.
        """
        got = promote("speak to Dana Reed, dana.reed@acme.test, or Tomas "
                      "Brabec: https://linkedin.com/in/tomas-brabec")
        self.assertIn("dana.reed@acme.test", got["candidates"]["emails"])
        self.assertTrue(got["candidates"]["profiles"])

    def test_the_reason_says_what_is_wrong(self):
        got = promote("try dana.reed@acme.test or tomas.brabec@acme.test")
        self.assertIn("more than one person", got["why"])


class OneIdentifierStillPromotes(unittest.TestCase):
    """A guard that refuses every referral is not a guard, it is an outage."""

    def test_one_address_and_one_name(self):
        got = promote("not me - please speak to Dana Reed, "
                      "dana.reed@acme.test, she owns this now")
        self.assertEqual(got["status"], referral.READY)
        self.assertEqual(got["email"], "dana.reed@acme.test")
        self.assertEqual(got["name"], "Dana Reed")

    def test_one_profile_and_one_name(self):
        got = promote("please talk to Dana Reed: "
                      "https://linkedin.com/in/dana-reed")
        self.assertEqual(got["status"], referral.READY)
        self.assertIn("dana-reed", got["linkedin"])

    def test_a_name_with_no_identifier_is_still_not_a_candidate(self):
        got = promote("you should speak to Dana about this")
        self.assertEqual(got["status"], referral.NOT_A_CANDIDATE)


class TheNameIsNeverGuessed(unittest.TestCase):

    def test_one_identifier_but_two_names_carries_no_name(self):
        """Which of the two does the address belong to? Unknown, so nothing.

        The greeting is what a prospect reads first, and a wrong one is the
        cheapest possible way to be obviously wrong at a real person. Note the
        record still PROMOTES - there is only one identifier, so there is only
        one person to add. It is added without a name, which the caller shows
        as an empty greeting field rather than a guessed one.

        A cue per name, because `NAME` only captures what follows one: an
        earlier version of this test wrote "ask Dana Reed or Tomas Brabec",
        which yields a single name and proved nothing.
        """
        got = promote("please ask Dana Reed, or try Tomas Brabec - "
                      "dana.reed@acme.test")
        self.assertEqual(len(referral.evidence(
            "please ask Dana Reed, or try Tomas Brabec")["names"]), 2,
            "the fixture no longer mentions two people")
        self.assertEqual(got["status"], referral.READY)
        self.assertIsNone(got["name"])

    def test_the_persisted_event_shape_carries_the_names_too(self):
        """`promotable` is handed two shapes and must count both.

        The stored event has `named` - one comma-joined string - where the
        live evidence dict has `names`, a list. Reading only the list found
        nothing on the path that actually adds a contact, so the count that
        refuses a guessed name never fired there.
        """
        self.assertEqual(
            referral.names_in({"named": "Dana Reed"}), ["Dana Reed"])
        self.assertEqual(referral.names_in({"named": "Dana Reed, Tomas Brabec"}),
                         ["Dana Reed", "Tomas Brabec"])
        self.assertEqual(referral.names_in({"named": None}), [])
        self.assertEqual(referral.names_in({}), [])

    def test_joining_and_splitting_the_names_round_trips(self):
        """What the whole `named` reading rests on: `NAME` captures one or two
        capitalised words, so it cannot produce a name containing a comma. If
        that ever changes, the split stops being exact and this fails first."""
        found = referral.evidence(
            "please email Dana Reed, or ask Tomas Brabec, or try O'Neill-Smith")
        self.assertTrue(found["names"])
        self.assertEqual(
            referral.names_in({"named": ", ".join(found["names"])}),
            found["names"])

    def test_every_answer_carries_the_name_field(self):
        """So a caller never has to re-derive it from the comma-joined list,
        which is where the second half of this bug lived."""
        for body in ("speak to Dana Reed, dana.reed@acme.test",
                     "try a@acme.test or b@acme.test",
                     "you should speak to Dana"):
            self.assertIn("name", promote(body), body)


class InTheEstate(WebTest):
    """The estate `WebTest` builds, reached through `Repo` as the screen does.

    A mention's event id is a hash of provider, type, record, contact, channel
    and time - not of the body - so each class applies its reply at its own
    instant. Two bodies at one instant would be one event.
    """

    BODY = ""
    AT = "2026-09-01T09:00:00+00:00"

    def setUp(self):
        super().setUp()
        from src import repo as repo_module

        self.repo = repo_module.Repo.for_user("ops@productive.test",
                                              "productive")
        self.rec = next(r for r in self.repo.records() if r.get("contacts"))
        self.who = self.rec["contacts"][0]["key"]
        replies.apply(self.rec, self.who, self.BODY, at=self.AT,
                      channel="email")
        self.repo.save_records([self.rec])

    def rows(self):
        return api.referred_people(self.repo, self.repo.record(self.rec["id"]),
                                   self.who)

    def mention_id(self):
        """This class's mention, matched on its own instant.

        The estate outlives a class, so mentions accumulate on the record and
        `rows()[0]` is whichever reply was applied first - a different body,
        belonging to a different test.
        """
        return next(r["event_id"] for r in self.rows() if r["at"] == self.AT)


class TheOperatorsButtonRefusesIt(InTheEstate):
    """End to end, because `promotable` returning AMBIGUOUS is only half of it.

    The button is what writes a contact. A guard the button never consults is
    a correct answer to a question nobody asked - the recurring defect in this
    repository, and worth one test rather than an assumption.
    """

    BODY = ("I have left - please speak to Dana Reed, dana.reed@acme.test, "
            "or try Tomas Brabec: https://www.linkedin.com/in/tomas-brabec")
    AT = "2026-09-01T10:17:00+00:00"

    def test_adding_it_is_refused(self):
        with self.assertRaises(api.ActionRefused) as caught:
            api.add_referred_contact(self.repo, self.rec["id"], self.who,
                                     self.mention_id(), by="ops@test")
        self.assertIn("more than one person", str(caught.exception))

    def test_no_contact_is_written(self):
        before = len(self.repo.record(self.rec["id"])["contacts"])
        with self.assertRaises(api.ActionRefused):
            api.add_referred_contact(self.repo, self.rec["id"], self.who,
                                     self.mention_id(), by="ops@test")
        self.assertEqual(len(self.repo.record(self.rec["id"])["contacts"]),
                         before)

    def test_the_row_offers_no_add_button(self):
        self.assertTrue(self.rows())
        self.assertFalse(any(r["promotable"] for r in self.rows()))

    def test_the_screen_shows_both_identifiers_it_refused(self):
        """A refusal the operator cannot act on is a dead end. The reply body
        is not rendered on this page, so the row has to carry what it said."""
        html = pages._referred_panel(
            {"referred": self.rows(), "record_id": self.rec["id"],
             "contact_key": self.who}, "csrf-token")
        self.assertIn("dana.reed@acme.test", html)
        self.assertIn("tomas-brabec", html)
        self.assertNotIn("Add to this account", html)


class ASingleReferralStillReachesTheAccount(InTheEstate):
    """The control. A guard that also stops the ordinary referral has traded
    one wrong person for no people at all.

    One test, one add: the estate outlives the class, so a second add of the
    same address is correctly refused as already here and would say nothing
    about this fix.
    """

    BODY = ("Not me - please email Dana Reed instead: "
            "solo.referral@newperson.test")
    AT = "2026-09-01T11:42:00+00:00"

    def test_it_is_offered_added_and_named(self):
        html = pages._referred_panel(
            {"referred": self.rows(), "record_id": self.rec["id"],
             "contact_key": self.who}, "csrf-token")
        self.assertIn("Add to this account", html)
        self.assertIn("solo.referral@newperson.test", html)

        added = api.add_referred_contact(self.repo, self.rec["id"], self.who,
                                         self.mention_id(), by="ops@test")
        self.assertEqual(added["email"], "solo.referral@newperson.test")
        # The name `promotable` vouched for, not the first of a list.
        self.assertEqual(added.get("name"), "Dana Reed")


class AnUnnameableReferralIsAddedWithoutAGreeting(InTheEstate):
    """One address, two people named: the address is addable and the name is
    not. The caller used to take the first of the comma-joined `named` list -
    the same guess as the identifier bug, in the field a prospect reads first.
    """

    BODY = ("please email Dana Reed, or ask Tomas Brabec - "
            "twonames@newperson.test")
    AT = "2026-09-01T12:08:00+00:00"

    def test_it_is_added_with_no_guessed_name(self):
        added = api.add_referred_contact(self.repo, self.rec["id"], self.who,
                                         self.mention_id(), by="ops@test")
        self.assertEqual(added["email"], "twonames@newperson.test")
        self.assertFalse(added.get("name"),
                         "the greeting name was guessed from the first of two")


if __name__ == "__main__":
    unittest.main()
