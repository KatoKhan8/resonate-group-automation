"""A contact who told us to stop does not render as engaged.

`reply.on_negative` defaults to `(CONTINUE, CONTACT)`, which `_TRANSITION`
turns into `(STOP, CONTINUE, False)`: the replier's own sequence ends and the
account carries on. So `accountpolicy._stop_contact` writes
`contact["stopped"]`, the account is *not* paused, and a REPLY_RECEIVED event
sits on the record.

`account._contact_state` read `suppressed`, then `account_paused`, then
`their_replies` - and never `stopped`. The reply made it truthy, so somebody
who had just said "not interested" came back as ENGAGED, which
`pages.STATE_KIND` renders in the "pass" colour, on the account view an
operator uses to choose who to work next.

Nothing was ever sent to them: `eligibility.py:291` reads the same flag and
refuses the step. This was the display disagreeing with the engine - a value
written correctly and read by nobody, which is the defect this repository
keeps producing.

The last two tests are the ones that keep the fix honest. A guard that
returned STOPPED too eagerly would swallow ordinary engagement, and one that
changed who `fatigue.account_check` counts would quietly relax a volume cap
while claiming to fix a colour.
"""
import unittest

from src import account, accountpolicy, fatigue
from tests.test_account_outreach import AccountTest, JOHN, SARAH, WS


class AStoppedContactIsNotEngaged(AccountTest):

    def stopped(self):
        """The real path: a confirmed touch, a reply, a negative outcome."""
        rec = self.touch(self.record(), JOHN, "anna", "email", 1)
        rec = self.reply(rec, JOHN)
        moved = accountpolicy.apply_reply(rec, JOHN,
                                          outcome=accountpolicy.NEGATIVE)
        self.assertIn("replier_stopped", moved["changed"])
        return rec

    # ----------------------------------------------------------- the defect

    def test_the_state_is_stopped_rather_than_engaged(self):
        state = account.graph(self.stopped(), WS)["by_contact"][JOHN]["state"]
        # Asserted before the constant is used, so the pre-fix failure names
        # the behaviour rather than a missing attribute.
        self.assertNotEqual(state, account.ENGAGED)
        self.assertEqual(state, account.STOPPED)

    def test_the_flag_the_engine_reads_is_the_flag_the_view_reads(self):
        """The two disagreed, which is the whole defect."""
        rec = self.stopped()
        contact = {c["key"]: c for c in account.contacts_of(rec)}[JOHN]
        self.assertTrue(contact.get("stopped"))
        self.assertEqual(account.graph(rec, WS)["by_contact"][JOHN]["state"],
                         account.STOPPED)

    def test_the_account_is_not_paused_which_is_why_it_showed_engaged(self):
        """If the account paused, PAUSED would have masked the bug."""
        rec = self.stopped()
        self.assertNotEqual(account.graph(rec, WS)["by_contact"][SARAH]
                            ["state"], account.PAUSED)

    # ------------------------------------------- and it did not overreach

    def test_an_ordinary_replier_is_still_engaged(self):
        """Otherwise the guard swallows engagement and proves nothing."""
        rec = self.reply(self.touch(self.record(), JOHN, "anna", "email", 1),
                         JOHN)
        self.assertEqual(account.graph(rec, WS)["by_contact"][JOHN]["state"],
                         account.ENGAGED)

    def test_suppression_still_outranks_stopping(self):
        rec = self.stopped()
        for contact in account.contacts_of(rec):
            if contact["key"] == JOHN:
                contact["suppressed"] = True
        self.assertEqual(account.graph(rec, WS)["by_contact"][JOHN]["state"],
                         account.SUPPRESSED)

    def test_fatigue_counts_exactly_who_it_counted_before(self):
        """A display fix does not get to relax a volume cap.

        JOHN has a confirmed touch and was counted as active before this
        change - as ENGAGED, because of the reply. Whether somebody who has
        stopped should count towards `account.max_active_contacts` is a
        volume-policy question, and a change to a colour is not where it
        gets answered.
        """
        self.assertEqual(
            fatigue.account_check(self.stopped())["counts"]["active"], 1)

    def test_that_count_matches_the_one_a_plain_reply_produces(self):
        """The control: same touch and reply, no negative outcome applied."""
        rec = self.reply(self.touch(self.record(), JOHN, "anna", "email", 1),
                         JOHN)
        self.assertEqual(
            fatigue.account_check(rec)["counts"]["active"], 1)


if __name__ == "__main__":
    unittest.main()
