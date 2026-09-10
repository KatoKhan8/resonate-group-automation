"""Nothing checked whether one of our own seats was already talking to them.

`collision` asked EmailBison only. A live campaign is HeyReach-fed and the client
runs 33 LinkedIn seats holding 25,595 conversations, so a connection request
could have gone to somebody a seat was mid-conversation with and no check would
have seen it. PRODUCT-GAPS recorded the gap; the read route was already on the
allowlist.

WHAT WAS MEASURED BEFORE ANY OF THIS WAS WRITTEN. `POST /inbox/GetConversationsV2`
takes a `filters` object, and every field of a real conversation was probed as a
`searchString` to find out what it actually matches:

    firstName -> 2    companyName -> 0    profileUrl   -> 0
    lastName  -> 1    linkedin_id -> 0    message text -> 0

So it matches the correspondent's NAME and nothing else. Two things follow, and
both are asserted below: a person-level question is sound, and a company-level
one cannot be asked at all - a search for a company answers 0 for every input,
which is indistinguishable from an answer.

An unrecognised filter key is discarded in silence and the unfiltered 25,595
come back, so a typo in a filter name would read as "no prior contact" for
everybody.
"""
import unittest
from unittest import mock

from src import collision


def conversation(slug, first="Ada", last="Lovelace", company="Acme",
                 messages=1, sender="ME", seat=116968):
    return {
        "id": "conv-" + slug,
        "totalMessages": messages,
        "lastMessageAt": "2026-09-09T00:00:00Z",
        "lastMessageSender": sender,
        "correspondentProfile": {
            "profileUrl": "https://www.linkedin.com/in/" + slug,
            "firstName": first, "lastName": last, "companyName": company},
        "linkedInAccount": {"id": seat, "firstName": "Mina",
                            "lastName": "Ruzicic"},
    }


WORKSPACE = "productive"
OUR_SEAT = 116968


def inbox(rows, total=None, seats=(OUR_SEAT,)):
    """Stub the one read route AND this client's roster, together.

    Together on purpose. Stubbing only the inbox let these tests read the real
    `senders.jsonl`, which happens to contain seat 116968 - so they passed for
    a reason that had nothing to do with what they were asserting, and would
    have gone green against an empty roster on somebody else's machine.
    """
    import contextlib
    from src import senderidentity

    rows_out = [{"kind": senderidentity.LINKEDIN_ACCOUNT,
                 "workspace": WORKSPACE, "provider_account_id": str(x),
                 "active": True, "health": "ok"} for x in seats]

    class Stubs(contextlib.ExitStack):
        """`as stub` still hands back the inbox mock, so the tests that assert
        WHAT WAS SENT keep working."""

        def __enter__(self):
            super().__enter__()
            self.conversations = self.enter_context(mock.patch.object(
                collision.heyreach, "conversations",
                return_value=(rows,
                              total if total is not None else len(rows))))
            self.enter_context(mock.patch.object(
                senderidentity, "linkedin_accounts", return_value=rows_out))
            return self.conversations

    return Stubs()





class TheSlugIsTheIdentity(unittest.TestCase):
    """The same profile is written five ways, two of them already in state."""

    def test_every_form_of_one_url_reduces_to_one_slug(self):
        for url in ("https://www.linkedin.com/in/ada-lovelace",
                    "https://www.linkedin.com/in/ada-lovelace/",
                    "http://linkedin.com/in/ada-lovelace",
                    "uk.linkedin.com/in/ada-lovelace/",
                    "https://www.linkedin.com/in/ada-lovelace?trk=abc",
                    "ADA-LOVELACE", "ada-lovelace"):
            with self.subTest(url=url):
                self.assertEqual(collision.profile_slug(url), "ada-lovelace")

    def test_nothing_is_not_a_slug(self):
        for value in (None, "", "   ", "/", "https://www.linkedin.com/in/"):
            with self.subTest(value=value):
                self.assertEqual(collision.profile_slug(value), "")

    def test_a_profileless_url_is_refused_rather_than_cleared(self):
        with self.assertRaises(collision.CollisionUnknown):
            collision.check_linkedin_profile("", expect_workspace=WORKSPACE)


class APriorConversationIsFound(unittest.TestCase):
    def test_a_matching_slug_with_messages_is_touched(self):
        with inbox([conversation("ada-lovelace")]):
            verdict, detail = collision.check_linkedin_profile(
                "https://www.linkedin.com/in/ada-lovelace", "Ada Lovelace", expect_workspace=WORKSPACE)
        self.assertEqual(verdict, collision.TOUCHED)
        self.assertEqual(detail["our_seat"], 116968)
        self.assertEqual(detail["slug"], "ada-lovelace")

    def test_a_reply_from_them_outranks_a_touch(self):
        """A person who answered must never receive a cold opener."""
        with inbox([conversation("ada-lovelace", sender="CORRESPONDENT")]):
            verdict, detail = collision.check_linkedin_profile(
                "linkedin.com/in/ada-lovelace", "Ada", expect_workspace=WORKSPACE)
        self.assertEqual(verdict, collision.IN_SEQUENCE)
        self.assertTrue(detail["they_replied"])

    def test_a_conversation_with_no_messages_is_still_not_clear(self):
        with inbox([conversation("ada-lovelace", messages=0)]):
            verdict, _ = collision.check_linkedin_profile(
                "linkedin.com/in/ada-lovelace", "Ada", expect_workspace=WORKSPACE)
        self.assertEqual(verdict, collision.TOUCHED)

    def test_the_url_form_does_not_change_the_answer(self):
        stored = conversation("ada-lovelace")
        stored["correspondentProfile"]["profileUrl"] = (
            "uk.linkedin.com/in/ada-lovelace/?trk=x")
        with inbox([stored]):
            verdict, _ = collision.check_linkedin_profile(
                "https://www.linkedin.com/in/ada-lovelace", "Ada", expect_workspace=WORKSPACE)
        self.assertEqual(verdict, collision.TOUCHED)


class SomebodyElseWithTheSameFirstNameIsNotThem(unittest.TestCase):
    """The query is broad on purpose; the slug supplies the precision."""

    def test_twelve_other_danas_do_not_make_a_collision(self):
        others = [conversation("dana-%d" % i, first="Dana", last="X%d" % i)
                  for i in range(12)]
        with inbox(others):
            verdict, detail = collision.check_linkedin_profile(
                "https://www.linkedin.com/in/danamarsh", "Dana Marsh", expect_workspace=WORKSPACE)
        self.assertEqual(verdict, collision.CLEAR)
        self.assertEqual(detail["conversations_for_that_name"], 12)

    def test_the_search_uses_the_first_name_not_the_full_name(self):
        """`searchString` is literal on punctuation - the apostrophe form
        answers 4 and the stripped form answers 0 - so a full-name term is a
        fragile negative."""
        with inbox([]) as stub:
            collision.check_linkedin_profile(
                "linkedin.com/in/dalemorgan", "Dale Morgan", expect_workspace=WORKSPACE)
        sent = stub.call_args.kwargs["filters"]["searchString"]
        self.assertEqual(sent, "Dale")

    def test_a_clear_answer_records_what_it_scanned(self):
        """A verdict that does not say what it looked at is unreadable later."""
        with inbox([conversation("someone-else", first="Dana")]):
            _, detail = collision.check_linkedin_profile(
                "linkedin.com/in/danamarsh", "Dana Marsh", expect_workspace=WORKSPACE)
        self.assertEqual(detail["searched_as"], "Dana")
        self.assertEqual(detail["conversations_for_that_name"], 1)


class AnUnusableAnswerIsRefused(unittest.TestCase):
    def test_a_name_matching_too_many_conversations_raises(self):
        with inbox([conversation("x")], total=collision.BROAD_NAME_MATCH + 1):
            with self.assertRaises(collision.CollisionUnknown):
                collision.check_linkedin_profile("linkedin.com/in/x", "John", expect_workspace=WORKSPACE)

    def test_a_non_list_response_is_not_read_as_no_contact(self):
        """Through the roster stub, so the refusal is for the stated reason.

        Patching only the inbox let this read the real `senders.jsonl`; on a
        machine with an empty roster it would still have raised, for a
        completely different reason, and passed.
        """
        with inbox([]) as stub:
            stub.return_value = (None, 0)
            with self.assertRaises(collision.CollisionUnknown):
                collision.check_linkedin_profile("linkedin.com/in/x", "Ada",
                                                 expect_workspace=WORKSPACE)

    def test_an_empty_name_is_refused(self):
        with self.assertRaises(collision.CollisionUnknown):
            collision.conversations_named("")

    def test_a_provider_error_propagates_rather_than_clearing(self):
        with mock.patch.object(collision.heyreach, "conversations",
                               side_effect=RuntimeError("502")):
            with self.assertRaises(RuntimeError):
                collision.check_linkedin_profile("linkedin.com/in/x", "Ada", expect_workspace=WORKSPACE)


class TheCompanyQuestionCannotBeAsked(unittest.TestCase):
    """The measured limit, asserted so nobody infers past it."""

    def test_the_account_check_returns_unknown_not_clear(self):
        verdict, detail = collision.account_is_unanswerable("acme.example")
        self.assertEqual(verdict, collision.UNKNOWN)
        self.assertIn("companyName", detail["why"])
        self.assertIn("not a company-level CLEAR", detail["do_not_conclude"])

    def test_it_is_not_one_of_the_answering_verdicts(self):
        verdict, _ = collision.account_is_unanswerable("acme.example")
        for answering in (collision.CLEAR, collision.TOUCHED,
                          collision.IN_SEQUENCE):
            self.assertNotEqual(verdict, answering)


class OnlyProvenFilterKeysAreSent(unittest.TestCase):
    """An unrecognised key is discarded in silence and the whole inbox
    returns, so a filter typo would read as no prior contact for everybody."""

    def test_the_only_filter_key_sent_is_the_measured_one(self):
        with inbox([]) as stub:
            collision.conversations_named("Ada")
        self.assertEqual(list(stub.call_args.kwargs["filters"]),
                         ["searchString"])


if __name__ == "__main__":
    unittest.main()


class TheInboxIsScopedToThisClientsSeats(unittest.TestCase):
    """The gap this closes, and it is the same one that already happened.

    On 2026-09-09 the EMAIL collision check answered CLEAR against another
    client's empty estate, and `check_address` was hardened to require and
    verify a workspace. This side kept the original unscoped signature - on
    the channel the campaigns actually run on.

    Scoping cannot be done in the query: `POST /inbox/GetConversationsV2`
    accepts no organisation parameter, and `organizationUnitId` appears
    nowhere in the request. So it is done on the ANSWER - a conversation is
    evidence about this client only if it sits on a seat this client owns.
    """

    def test_a_workspace_is_required(self):
        """The default must not be "whatever the key can see"."""
        with inbox([]):
            with self.assertRaises(collision.CollisionUnknown):
                collision.check_linkedin_profile(
                    "linkedin.com/in/ada-lovelace", "Ada")

    def test_another_tenants_conversation_does_not_create_a_collision(self):
        """A seat we do not own is not evidence about our prospect."""
        with inbox([conversation("ada-lovelace", seat=999999)],
                   seats=(OUR_SEAT,)):
            verdict, detail = collision.check_linkedin_profile(
                "linkedin.com/in/ada-lovelace", "Ada",
                expect_workspace=WORKSPACE)
        self.assertEqual(verdict, collision.CLEAR)
        self.assertEqual(detail["other_tenants_conversations_ignored"], 1)

    def test_our_own_seat_still_creates_one(self):
        with inbox([conversation("ada-lovelace", seat=OUR_SEAT)]):
            verdict, _ = collision.check_linkedin_profile(
                "linkedin.com/in/ada-lovelace", "Ada",
                expect_workspace=WORKSPACE)
        self.assertEqual(verdict, collision.TOUCHED)

    def test_an_empty_roster_refuses_rather_than_answering_clear(self):
        """Fail closed. An unscoped CLEAR is not a statement about anybody.

        This is the exact shape of the original incident: a check that could
        not see the estate reported that nobody had been contacted.
        """
        with inbox([conversation("ada-lovelace", seat=999999)], seats=()):
            with self.assertRaises(collision.CollisionUnknown):
                collision.check_linkedin_profile(
                    "linkedin.com/in/ada-lovelace", "Ada",
                    expect_workspace=WORKSPACE)

    def test_a_clear_answer_names_the_estate_it_is_about(self):
        with inbox([]):
            _, detail = collision.check_linkedin_profile(
                "linkedin.com/in/ada-lovelace", "Ada",
                expect_workspace=WORKSPACE)
        self.assertEqual(detail["workspace"], WORKSPACE)
        self.assertEqual(detail["seats_searched"], 1)

    def test_foreign_conversations_are_not_counted_as_coverage(self):
        """They must not inflate "we looked at 40 conversations" either."""
        rows = [conversation("someone-else", seat=999999) for _ in range(40)]
        with inbox(rows, seats=(OUR_SEAT,)):
            _, detail = collision.check_linkedin_profile(
                "linkedin.com/in/ada-lovelace", "Ada",
                expect_workspace=WORKSPACE)
        self.assertEqual(detail["conversations_for_that_name"], 0)
        self.assertEqual(detail["other_tenants_conversations_ignored"], 40)
