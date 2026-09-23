r"""A client buys accounts worked, not emails sent.

OPERATOR, 2026-09-23: "Client report and weekly report count accounts first
(accounts in flight, engaged, replied, meetings), then emails."

Every number this system has put in front of this client has been an email
number. Leading with "502 sent" and burying "eight companies have written
back" tells them how busy we were, not what they got. **The order is the
feature**, so it is asserted rather than left to whoever writes the prose.

## AND THE HONEST DEGRADATION IS THE OTHER HALF

Built on the operator's write-back decision of the same day: the ledger is
the source, the provider is a periodic workspace-level witness, never a
per-account call. Until production ships the write-back the ledger does not
carry this estate's sends, and the report says so.

**`unanswerable` is its own number and is never folded into `untouched`.**
While the write-back is missing, that distinction IS the report:

    "we cannot currently tell you how many accounts are untouched"   true
    "1,530 accounts are untouched"                                   false

A client reading the second would conclude we have not started.
"""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import events                                          # noqa: E402
from src import replies as replyclass                           # noqa: E402
from src import slackagenttools as tools                        # noqa: E402
from src import slackscope                                      # noqa: E402

from tests.test_what_is_happening_with_this_account import (     # noqa: E402
    contact, record, reply_event, touch)


class Reporting(unittest.TestCase):

    def setUp(self):
        self._pack = tools.knowledge.pack
        tools.knowledge.pack = lambda *a, **k: {
            "workspaces": {"alpha": {"provider_campaign_ids": []}}}
        self.addCleanup(setattr, tools.knowledge, "pack", self._pack)
        tools._LEDGER_WITNESS.clear()
        self.addCleanup(tools._LEDGER_WITNESS.clear)

    def report(self, rows, ledger_ok=True, meetings=(), scope=None):
        scope = scope or slackscope.Scope(slackscope.INTERNAL, source="test")
        with mock.patch.object(tools, "_records", lambda slug: list(rows)), \
                mock.patch.object(tools, "_default_workspace",
                                  lambda: "alpha"), \
                mock.patch.object(tools, "_ledger_carries_sends",
                                  lambda slug, now=None: ledger_ok), \
                mock.patch.object(tools, "sends_today",
                                  lambda scope, argument=None: {
                                      "campaigns_read": 2,
                                      "campaigns": []}), \
                mock.patch("src.slackmeetings.by_domain",
                           lambda workspace=None, **k: list(meetings)):
            return tools.weekly_report(scope, None)


# ================================ 1. THE ORDER IS THE FEATURE

class AccountsComeFirst(Reporting):

    def test_accounts_are_present_and_named_in_order(self):
        out = self.report([record()])
        self.assertEqual(out["accounts_order"],
                         ["in_flight", "engaged", "replied", "meetings"])

    def test_the_accounts_block_precedes_the_emails_block(self):
        """Key order in the payload, because the model is handed this
        readback and writes prose from it top down."""
        out = self.report([record()])
        keys = list(out)
        self.assertLess(keys.index("accounts"), keys.index("emails"))

    def test_emails_are_still_there(self):
        out = self.report([record()])
        self.assertIn("emails", out)

    def test_the_note_says_why(self):
        out = self.report([record()])
        self.assertIn("not emails sent", out["note"])


# ================================ 2. IN FLIGHT MEANS WORKED, NOT FINISHED

class WhatCountsAsInFlight(Reporting):

    def rows(self):
        return [
            record(domain="a.test"),                                # untouched
            record(domain="b.test", events_=[touch()]),             # sequenced
            record(domain="c.test", events_=[
                touch(kind=events.LINKEDIN_CONNECTED,
                      channel="linkedin")]),                        # engaged
            record(domain="d.test", events_=[touch(), reply_event()]),
            record(domain="e.test",
                   contacts=[contact(suppressed=True)],
                   events_=[touch()]),                              # dnc
        ]

    def test_untouched_is_not_in_flight(self):
        """Nothing has happened to it. Counting it as worked is how a
        pipeline number becomes a list of companies we own."""
        out = self.report(self.rows())
        self.assertEqual(out["accounts"]["untouched"], 1)
        self.assertEqual(out["accounts"]["in_flight"], 3)

    def test_do_not_contact_is_not_in_flight(self):
        out = self.report(self.rows())
        self.assertEqual(out["accounts"]["do_not_contact"], 1)

    def test_a_meeting_counts_in_flight_and_as_a_meeting(self):
        out = self.report([record(domain="d.test",
                                  events_=[touch(), reply_event()])],
                          meetings=[{"domain": "d.test"}])
        self.assertEqual(out["accounts"]["meetings"], 1)
        self.assertEqual(out["accounts"]["in_flight"], 1)

    def test_each_account_is_counted_once(self):
        out = self.report(self.rows())
        block = out["accounts"]
        total = (block["in_flight"] + block["untouched"]
                 + block["do_not_contact"] + block["unanswerable"])
        self.assertEqual(total, 5)


# ================================ 3. THE HONEST DEGRADATION

class UnanswerableIsNotUntouched(Reporting):

    def test_a_blind_ledger_reports_unanswerable_not_untouched(self):
        out = self.report([record(domain="a.test"),
                           record(domain="b.test")], ledger_ok=False)
        self.assertEqual(out["accounts"]["unanswerable"], 2)
        self.assertEqual(out["accounts"]["untouched"], 0)

    def test_and_it_says_so_in_words(self):
        """The number alone would be read as a footnote."""
        out = self.report([record()], ledger_ok=False)
        self.assertIn("must not be read as one", out["accounts_warning"])

    def test_accounts_with_evidence_still_count_while_blind(self):
        out = self.report([record(domain="a.test"),
                           record(domain="b.test", events_=[touch()])],
                          ledger_ok=False)
        self.assertEqual(out["accounts"]["in_flight"], 1)
        self.assertEqual(out["accounts"]["unanswerable"], 1)

    def test_a_healthy_ledger_carries_no_warning(self):
        out = self.report([record()], ledger_ok=True)
        self.assertNotIn("accounts_warning", out)
        self.assertEqual(out["accounts"]["untouched"], 1)

    def test_the_verdict_is_on_the_report(self):
        out = self.report([record()], ledger_ok=False)
        self.assertFalse(out["ledger_carries_sends"])


# ================================ 4. A HUMAN REPLY IS NOT ANY REPLY

class RepliesAreCountedTheWayTheOperatorDefinedThem(Reporting):

    def test_an_out_of_office_is_not_a_human_reply(self):
        out = self.report([record(events_=[
            touch(), reply_event(classification="out_of_office")])])
        self.assertEqual(out["replies"]["human"], 0)
        self.assertEqual(out["replies"]["by_class"]["out_of_office"], 1)

    def test_an_assistant_redirect_is_not_a_human_reply(self):
        out = self.report([record(events_=[
            touch(), reply_event(classification="assistant_redirect")])])
        self.assertEqual(out["replies"]["human"], 0)

    def test_a_real_reply_is(self):
        out = self.report([record(events_=[
            touch(), reply_event(classification="not_relevant")])])
        self.assertEqual(out["replies"]["human"], 1)

    def test_an_unclassified_reply_is_not_counted_as_human(self):
        """Nobody has looked at it. Calling it human is a guess in the
        flattering direction, and this figure reaches a client."""
        out = self.report([record(events_=[
            touch(), reply_event(classification=None)])])
        self.assertEqual(out["replies"]["human"], 0)
        self.assertEqual(out["replies"]["by_class"]["unclassified"], 1)

    def test_positive_is_counted_apart_from_human(self):
        out = self.report([record(events_=[
            touch(), reply_event(classification="positive")])])
        self.assertEqual(out["replies"]["positive"], 1)
        self.assertEqual(out["replies"]["human"], 1)

    def test_the_definition_is_the_shared_one(self):
        """Not a second list of automated classes maintained here. One
        definition, or the report and the classifier drift."""
        for name in replyclass.AUTOMATED_CATEGORIES:
            out = self.report([record(events_=[
                touch(), reply_event(classification=name)])])
            with self.subTest(classification=name):
                self.assertEqual(out["replies"]["human"], 0)

    def test_a_stored_positive_carries_the_staleness_caveat(self):
        """MEASURED 2026-09-23, and it is why item 4 cannot read this field.

        The ledger's only `positive` for the live estate is the executive
        assistant reply from campaign 491 - "Jennifer's inbox can get a
        little extra at times, so her amazing Executive Assistant Rose is
        helping keep things running smoothly" - stored `positive` by
        classifier `rules-3` at 18:35 on 2026-09-22. The CURRENT classifier
        calls it `assistant_redirect`, and the provider's own
        `automated_reply` flag on that row is true.

        The operator's re-run reached the same answer, 0 positive of 14, and
        its verdicts were never written back.

        AND THE GUARD THAT WOULD CATCH IT DOES NOT EXIST: `replies.VERSION`
        is still "rules-3", the same string the stale event carries, so a
        stored verdict cannot be told from a fresh one by inspection.
        """
        out = self.report([record(events_=[
            touch(), reply_event(classification="positive")])])
        self.assertEqual(out["replies"]["positive"], 1)
        self.assertIn("re-classifies as `assistant_redirect`",
                      out["replies"]["positive_caveat"])

    def test_the_version_still_cannot_tell_them_apart(self):
        """Asserts the defect, so the day `replies.VERSION` is bumped this
        fails and somebody revisits the caveat instead of leaving it to
        outlive the problem."""
        self.assertEqual(replyclass.VERSION, "rules-3")

    def test_no_positives_means_no_caveat(self):
        out = self.report([record(events_=[
            touch(), reply_event(classification="not_relevant")])])
        self.assertNotIn("positive_caveat", out["replies"])

    def test_one_reply_with_receipt_and_verdict_is_one(self):
        """The doubling bug, at report scale, where it would be biggest."""
        out = self.report([record(events_=[
            touch(),
            {"type": events.REPLY_RECEIVED, "contact": "ada",
             "at": "2026-09-22T10:00:00Z", "channel": "email"},
            {"type": events.REPLY_CLASSIFIED, "contact": "ada",
             "at": "2026-09-22T10:00:05Z", "channel": "email",
             "classification": "not_relevant"}])])
        self.assertEqual(out["replies"]["by_class"], {"not_relevant": 1})
        self.assertEqual(out["replies"]["human"], 1)


# ================================ 5. SCOPE

class ItIsClientScopedLikeEverythingElse(Reporting):

    def test_a_client_gets_its_own_workspace(self):
        scope = slackscope.Scope(slackscope.CLIENT, workspace="alpha",
                                 source="test")
        out = self.report([record()], scope=scope)
        self.assertEqual(out["workspace"], "alpha")

    def test_it_is_registered_for_both_scopes(self):
        self.assertIn("weekly_report", tools.REGISTRY)
        _fn, _desc, scopes, _arg = tools.REGISTRY["weekly_report"]
        self.assertIn(slackscope.CLIENT, scopes)
        self.assertIn(slackscope.INTERNAL, scopes)


if __name__ == "__main__":
    unittest.main()
