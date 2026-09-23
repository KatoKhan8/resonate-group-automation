"""A stored `positive` nobody can prove is current is never counted as one.

OPERATOR, 2026-09-23: Phase D item 4 - positive replies into the client
channel - waits on the VERSION bump and the ledger write-back. **Until then,
a test that a `rules-3` verdict is never counted.**

## WHY NOT JUST ASSERT THE VERSION STRING

`tests/test_the_report_counts_accounts_before_emails.py` already asserts
`replies.VERSION == "rules-3"` so that a bump fails loudly. That guard
catches the BUMP. It does not catch the DRIFT, which is the actual fault:
the rules moved twice on 2026-09-23 - `0b78fd68` at 13:18 rewrote the
`\\bpass\\b` pattern and moved "we already use" and "not a priority" out of
NEGATIVE; `83a30652` at 14:46 added QUESTION and SEND_INFO across 210 lines
- and `VERSION` read `"rules-3"` through all of it. Nothing went red.

So this file asserts on the DATA instead. The row below is the shape of the
real one, read out of the live estate on 2026-09-23:

    {"type": "reply_classified", "contact": "jennifer-bagley",
     "at": "2026-09-22T18:35:03Z", "classification": "positive",
     "classifier": "rules-3", "confidence": "0.75",
     "reason": "matched 2 positive phrase(s)"}

It is an executive assistant saying "Jennifer's inbox can get a little extra
at times, so her amazing Executive Assistant Rose is helping keep things
running smoothly". The current classifier calls it `assistant_redirect`; the
provider's own `automated_reply` flag on that row is true. It is stored
`positive`, and a feature that reads the stored field announces it to a
client as somebody being interested.

## THE TRAP THIS FILE IS MOSTLY ABOUT

The obvious guard is `row["classifier"] == replies.VERSION`. **That guard
passes this row.** Both strings are `"rules-3"`. A field that is present,
readable and cannot distinguish anything is worse than an absent one,
because the guard written against it looks correct.

`TheGuardThatWouldNotWork` below pins that: it constructs the naive
comparison, shows it admitting the stale row, and asserts that the real code
does not do it.
"""
import unittest

from src import replies as replyclass, replyverdict


#: The live row, minus the contact's name.
STALE = {"contact_key": "jennifer-bagley", "channel": "email",
         "at": "2026-09-22T18:35:03.000000Z", "type": "reply_classified",
         "classification": "positive", "positive": False,
         "classifier": "rules-3",
         "provider_event_id":
             "emailbison:a2cf1001-12a3-4473-ae31-b5954c2392c1:classified"}


class FakeRules:
    """A `replies` module that CAN identify its rule set."""

    def __init__(self, digest):
        self.RULE_HASH = digest
        self.VERSION = "rules-9"


class TheStaleVerdictIsNotCounted(unittest.TestCase):

    def test_the_real_stale_row_is_not_confirmed(self):
        self.assertFalse(replyverdict.is_confirmed(STALE))

    def test_and_it_is_not_confirmed_because_nothing_can_be(self):
        """Today the answer is no for every row, and the reason is not
        something about this row - it is that the rules have no identity."""
        self.assertIsNone(replyverdict.current_rule_identity())
        self.assertFalse(replyverdict.rules_are_identifiable())

    def test_the_split_puts_it_on_the_unconfirmed_side(self):
        confirmed, unconfirmed = replyverdict.split_positives([STALE])
        self.assertEqual(confirmed, 0)
        self.assertEqual(unconfirmed, 1)

    def test_a_row_naming_no_classifier_is_not_confirmed_either(self):
        row = dict(STALE)
        row.pop("classifier")
        self.assertFalse(replyverdict.is_confirmed(
            row, FakeRules("sha256:abc")))

    def test_the_positive_detected_twin_is_not_double_counted(self):
        """One reply is several events. `positive_reply_detected` is the
        same reply seen again, and counting both doubles it - the bug
        94725a3d fixed at report scale."""
        twin = {"contact_key": "jennifer-bagley", "channel": "email",
                "at": "2026-09-22T18:35:03.000000Z",
                "type": "positive_reply_detected", "positive": True,
                "classification": None}
        confirmed, unconfirmed = replyverdict.split_positives([STALE, twin])
        self.assertEqual((confirmed, unconfirmed), (0, 1))


class TheGuardThatWouldNotWork(unittest.TestCase):
    """The whole reason this module exists rather than a one-line check."""

    def test_the_naive_comparison_admits_the_stale_row(self):
        """`classifier == VERSION` passes the executive assistant straight
        through, because the rules moved and the string did not. This is
        asserted rather than described so that the day somebody 'simplifies'
        replyverdict into that comparison, the next test goes red."""
        self.assertEqual(STALE["classifier"], replyclass.VERSION)

    def test_but_the_real_code_refuses_it(self):
        self.assertFalse(replyverdict.is_confirmed(STALE))

    def test_version_is_never_used_as_the_rule_identity(self):
        """A fallback to VERSION would turn the guard into a rubber stamp.
        A module that exposes ONLY VERSION must yield no identity."""

        class OnlyVersion:
            VERSION = "rules-3"

        self.assertIsNone(replyverdict.current_rule_identity(OnlyVersion()))
        self.assertFalse(replyverdict.is_confirmed(STALE, OnlyVersion()))


class TheDayTheHashLands(unittest.TestCase):
    """Decision 2, tested before it arrives, so it needs no code change."""

    def test_a_matching_digest_confirms_the_verdict(self):
        rules = FakeRules("sha256:deadbeef")
        fresh = dict(STALE, classifier="sha256:deadbeef")
        self.assertTrue(replyverdict.is_confirmed(fresh, rules))

    def test_a_verdict_from_the_previous_rule_set_still_is_not(self):
        rules = FakeRules("sha256:deadbeef")
        self.assertFalse(replyverdict.is_confirmed(STALE, rules))

    def test_the_split_then_separates_them(self):
        rules = FakeRules("sha256:deadbeef")
        fresh = dict(STALE, classifier="sha256:deadbeef")
        confirmed, unconfirmed = replyverdict.split_positives(
            [STALE, fresh], replies_module=rules)
        self.assertEqual((confirmed, unconfirmed), (1, 1))

    def test_any_of_the_accepted_attribute_names_works(self):
        """Named by list so production can land whichever it prefers
        without this module or this test needing an edit."""
        for attr in replyverdict.RULE_IDENTITY_ATTRS:
            with self.subTest(attr=attr):
                module = type("R", (), {attr: "sha256:feed", "VERSION": "x"})()
                self.assertEqual(
                    replyverdict.current_rule_identity(module), "sha256:feed")


class TheProjectionCarriesIt(unittest.TestCase):
    """`account.replies` dropped `classifier` on the way out, which is why
    2026-09-23 concluded there was no local way to ask this question."""

    def test_the_classifier_reaches_the_caller(self):
        from src import account, events

        rec = {"id": "r1", "domain": "acme.test", "events": [
            {"type": events.REPLY_CLASSIFIED, "contact": "ada",
             "at": "2026-09-22T10:00:00Z", "channel": "email",
             "classification": "positive", "classifier": "rules-3",
             "provider_event_id": "emailbison:xyz:classified"}]}
        row = account.replies(rec)[0]
        self.assertEqual(row["classifier"], "rules-3")
        self.assertEqual(row["provider_event_id"],
                         "emailbison:xyz:classified")

    def test_an_event_without_one_projects_none_rather_than_raising(self):
        from src import account, events

        rec = {"id": "r1", "domain": "acme.test", "events": [
            {"type": events.REPLY_RECEIVED, "contact": "ada",
             "at": "2026-09-22T10:00:00Z", "channel": "email"}]}
        self.assertIsNone(account.replies(rec)[0]["classifier"])


if __name__ == "__main__":
    unittest.main()
