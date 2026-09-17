#!/usr/bin/env python3
"""A ceiling that was declared, documented, printed, and enforced by nobody.

`pilotcaps.CEILING["new_accounts_per_day"] = 5` has been in the tree since the
file was written. It has a label, it has a reason - *"opening every account at
once means every reply arrives at once, and a pilot exists to be watched"* - and
`python -m src.pilotcaps` prints it next to the ceilings that work. On
2026-09-17 a grep for it across `src/` returned one file: the one that declares
it. No caller ever put it in a plan, and unlike `touches_per_account_per_week`
it had no `CONSTRAINS` entry handing it to `fatigue` either.

That is this repository's "existence is not function" defect in its purest
form. Nothing was wrong with the number. Nothing was wrong with the reason. The
value was simply computed, displayed, and read by nothing downstream.

WHY IT WAS ABOUT TO MATTER. The next production batch is 17 contacts across
roughly 17 distinct accounts. Under a 5/day ceiling that is a breach by more
than three times, and before this file nothing in the system would have refused
it - the trace would have said `pilot_cap PASS`.

TWO HALVES, AND THE SECOND IS THE ONE THAT GENERALISES:

  1. The cap is enforced at `executionguard` gate 5, counted from the DURABLE
     action ledger, per tenant and per calendar day.
  2. `pilotcaps.require` can no longer answer True over a silence. The
     mechanism that let this ceiling sleep was not a missing enforcer; it was
     that omitting a key from a plan looked exactly like passing it.
"""
import datetime
import unittest

from src import actionledger, executionguard, pilotcaps, store

from tests.base import QueueTest
from tests.test_no_write_happens_without_every_gate import GuardTest, NOW

TODAY = NOW.isoformat()
YESTERDAY = (NOW - datetime.timedelta(days=1)).isoformat()


def ledger_row(rec_id, contact="somebody", workspace="productive",
               at=TODAY, state=actionledger.SENT, channel="email"):
    """One settled ledger row, shaped as `reserve` writes it."""
    return {"key": f"{rec_id}:{contact}:em1:{channel}", "state": state,
            "at": at, "operation": "op", "channel": channel,
            "workspace": workspace, "campaign_id": "c1", "sender_id": 7,
            "rec_id": rec_id, "contact_key": contact, "step_key": "em1",
            "fingerprint": "fp", "by": "system"}


class AnAccountIsACompanyNotARow(unittest.TestCase):
    """`accounts_opened_on` answers with a SET of accounts, so the ceiling
    counts companies disturbed rather than messages sent."""

    def test_five_contacts_at_one_company_is_one_account_opened(self):
        rows = [ledger_row("rec-1", f"person-{i}") for i in range(5)]
        self.assertEqual(
            actionledger.accounts_opened_on(TODAY, workspace="productive",
                                            rows=rows),
            {"rec-1"})

    def test_five_companies_are_five(self):
        rows = [ledger_row(f"rec-{i}") for i in range(5)]
        self.assertEqual(
            len(actionledger.accounts_opened_on(TODAY, workspace="productive",
                                                rows=rows)), 5)

    def test_an_account_opened_on_linkedin_is_open_for_email_too(self):
        """NOT PER CHANNEL, unlike every other count in this ledger. The
        company has one inbox and the operator has one morning, so a per-
        channel answer would let one account be opened twice in a day."""
        rows = [ledger_row("rec-1", channel="linkedin")]
        self.assertEqual(
            actionledger.accounts_opened_on(TODAY, workspace="productive",
                                            rows=rows), {"rec-1"})

    def test_a_failed_attempt_opened_nothing(self):
        """`failed` means the provider refused BEFORE acting. Nobody heard
        from us, so no account was opened and the ceiling is not spent."""
        rows = [ledger_row("rec-1", state=actionledger.FAILED)]
        self.assertEqual(
            actionledger.accounts_opened_on(TODAY, workspace="productive",
                                            rows=rows), set())

    def test_an_unresolved_attempt_did_open_it(self):
        """The direction that under-counts exposure is the wrong one, and it
        is the same default `count_on` and `contacts_reached` already use."""
        rows = [ledger_row("rec-1", state=actionledger.UNRESOLVED)]
        self.assertEqual(
            actionledger.accounts_opened_on(TODAY, workspace="productive",
                                            rows=rows), {"rec-1"})


class OneTenantAndOneDay(unittest.TestCase):
    """`count_on` shipped without a workspace parameter and one client's
    actions consumed another's ceiling. A second count must not repeat it."""

    def test_another_tenants_accounts_are_not_counted(self):
        rows = [ledger_row(f"rec-{i}", workspace="another-client")
                for i in range(5)]
        self.assertEqual(
            actionledger.accounts_opened_on(TODAY, workspace="productive",
                                            rows=rows), set())
        self.assertEqual(
            len(actionledger.accounts_opened_on(TODAY,
                                                workspace="another-client",
                                                rows=rows)), 5)

    def test_yesterdays_accounts_do_not_consume_todays_ceiling(self):
        """A calendar day, which is what the ceiling says. Five companies
        opened yesterday leave all five of today's openings available."""
        rows = [ledger_row(f"rec-{i}", at=YESTERDAY) for i in range(5)]
        self.assertEqual(
            actionledger.accounts_opened_on(TODAY, workspace="productive",
                                            rows=rows), set())
        self.assertEqual(
            len(actionledger.accounts_opened_on(YESTERDAY,
                                                workspace="productive",
                                                rows=rows)), 5)

    def test_an_account_open_yesterday_is_new_again_today(self):
        """And that is correct rather than a leak: the reason is about replies
        arriving together on one morning, not about ever having been touched.
        `touches_per_account_per_week` is the cumulative one."""
        rows = [ledger_row("rec-1", at=YESTERDAY)]
        self.assertNotIn("rec-1",
                         actionledger.accounts_opened_on(
                             TODAY, workspace="productive", rows=rows))


class TheReservationHoldsTheCeilingUnderTheLock(QueueTest):
    """Gate 5 is an early refusal; the binding check is inside `reserve`'s own
    transaction, because counting outside the lock and appending inside it is
    how two workers both pass at the ceiling."""

    def seed(self, n, workspace="productive"):
        for i in range(n):
            actionledger.reserve(
                f"seed-{i}:p:em1:email", channel="email", workspace=workspace,
                campaign_id="c1", sender_id=7, rec_id=f"seed-{i}",
                contact_key="p", step_key="em1", operation="op",
                fingerprint="fp")

    def attempt_new_account(self, rec_id="fresh", workspace="productive"):
        return actionledger.reserve(
            f"{rec_id}:p:em1:email", channel="email", workspace=workspace,
            campaign_id="c1", sender_id=7, rec_id=rec_id, contact_key="p",
            step_key="em1", operation="op", fingerprint="fp",
            cap_new_accounts=5)

    def test_the_fifth_new_account_is_allowed(self):
        self.seed(4)
        self.assertTrue(self.attempt_new_account())

    def test_the_sixth_new_account_is_refused(self):
        self.seed(5)
        with self.assertRaises(actionledger.CapReached) as caught:
            self.attempt_new_account()
        self.assertIn("5 account(s) already opened today", str(caught.exception))

    def test_a_second_contact_at_an_open_account_is_allowed_at_the_ceiling(self):
        """Otherwise a five-contact account spends a ceiling meant for five
        companies, and a limit written to stagger the pilot becomes a limit on
        working an account properly."""
        self.seed(5)
        row = actionledger.reserve(
            "seed-0:second-person:em1:email", channel="email",
            workspace="productive", campaign_id="c1", sender_id=7,
            rec_id="seed-0", contact_key="second-person", step_key="em1",
            operation="op", fingerprint="fp", cap_new_accounts=5)
        self.assertEqual(row["state"], actionledger.ATTEMPTED)

    def test_another_tenant_at_the_ceiling_does_not_refuse_this_one(self):
        self.seed(5, workspace="another-client")
        self.assertTrue(self.attempt_new_account(workspace="productive"))


class TheGateRefusesTheSixthAccount(GuardTest):
    """The whole point: `authorize` refuses, at `pilot_cap`, with no provider
    call - not `reserve` refusing after six gates said yes."""

    def setUp(self):
        super().setUp()
        # Generous channel ceilings so these tests fail for their own reason
        # rather than on `linkedin_per_day`. The subject here is accounts.
        self.config = dict(self.config,
                           daily_volume={"linkedin": 10, "email": 10})

    def open_accounts(self, n):
        """Open `n` OTHER accounts today, on the email channel.

        Email deliberately. `accounts_opened_on` ignores the channel - which
        is the property under test - while `count_on(channel="linkedin")` and
        the stoppability gate's `contacts_reached(channel="linkedin")` do not,
        so seeding on the other channel isolates the account ceiling from the
        per-channel ones instead of tripping them first.
        """
        for i in range(n):
            actionledger.reserve(
                f"other-{i}:p:em1:email", channel="email",
                workspace="productive", campaign_id="c1", sender_id=900,
                rec_id=f"other-{i}", contact_key="p", step_key="em1",
                operation="op", fingerprint="fp")

    def test_the_fifth_account_of_the_day_authorizes(self):
        """Or the ceiling is a ban rather than a limit."""
        self.open_accounts(4)
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            auth = self.attempt(config=self.config)
        self.assertIn("pilot_cap", auth.gates)
        self.assertEqual(len(self.spy.calls), 1)

    def test_the_sixth_account_of_the_day_is_refused(self):
        self.open_accounts(5)
        refusal = self.refused_at("pilot_cap", config=self.config)
        self.assertIn("Companies opened for the first time in a day",
                      refusal.why)
        self.assertIn("6", refusal.why)

    def test_the_refusal_carries_the_reason_the_ceiling_gives(self):
        """A refusal an operator cannot argue with is a refusal they route
        around. The number is not the argument; the reason is."""
        self.open_accounts(5)
        refusal = self.refused_at("pilot_cap", config=self.config)
        self.assertIn("a pilot exists to be watched", refusal.why)

    def test_a_contact_at_an_already_open_account_authorizes_at_the_ceiling(self):
        """Five accounts are open and one of them is this record's. This
        action opens nothing, so it is not a sixth opening."""
        self.open_accounts(4)
        actionledger.reserve(
            "rec-1:earlier-colleague:em1:email", channel="email",
            workspace="productive", campaign_id="c1", sender_id=900,
            rec_id="rec-1", contact_key="earlier-colleague", step_key="em1",
            operation="op", fingerprint="fp")
        self.assertEqual(
            len(actionledger.accounts_opened_on(TODAY,
                                                workspace="productive")), 5)
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            auth = self.attempt(config=self.config)
        self.assertIn("pilot_cap", auth.gates)
        self.assertEqual(len(self.spy.calls), 1)

    def test_another_tenants_accounts_do_not_consume_this_ones_ceiling(self):
        for i in range(5):
            actionledger.reserve(
                f"theirs-{i}:p:em1:email", channel="email",
                workspace="another-client", campaign_id="c1", sender_id=900,
                rec_id=f"theirs-{i}", contact_key="p", step_key="em1",
                operation="op", fingerprint="fp")
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            auth = self.attempt(config=self.config)
        self.assertIn("pilot_cap", auth.gates)

    def test_yesterdays_openings_do_not_refuse_today(self):
        """The ledger is stamped by `store.now()`, so yesterday's rows are
        written directly. The calendar day is the whole scope of the cap."""
        with store.file_transaction(actionledger.path()) as rows:
            rows.extend(ledger_row(f"old-{i}", at=YESTERDAY)
                        for i in range(9))
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            auth = self.attempt(config=self.config)
        self.assertIn("pilot_cap", auth.gates)

    def test_the_ledger_is_the_authority_not_the_callers_plan(self):
        """No parameter of `authorize` declares how many accounts are open,
        and adding one would be the defect `actionledger` exists to close."""
        self.open_accounts(5)
        self.refused_at("pilot_cap", config=self.config)
        self.assertEqual(self.spy.calls, [])


class ACapNobodyChecksCannotLookLikeACapThatPassed(unittest.TestCase):
    """The general defect, not this one ceiling.

    `require({"email_per_day": 1})` used to return True having examined one
    ceiling out of seven. Every unexamined one came back in `check`'s
    `unchecked` list, which nothing read. So the failure was not that somebody
    wrote a bad check - it was that writing no check was indistinguishable
    from writing a passing one.
    """

    ALL_BUT_EMAIL = set(pilotcaps.KEYS) - {"email_per_day"}

    def test_a_silent_plan_no_longer_passes(self):
        with self.assertRaises(pilotcaps.UnacknowledgedCap):
            pilotcaps.require({"email_per_day": 1})

    def test_the_refusal_names_every_ceiling_that_went_unasked(self):
        with self.assertRaises(pilotcaps.UnacknowledgedCap) as caught:
            pilotcaps.require({"email_per_day": 1})
        for key in self.ALL_BUT_EMAIL:
            self.assertIn(key, str(caught.exception))

    def test_acknowledging_them_passes(self):
        self.assertTrue(pilotcaps.require({"email_per_day": 1},
                                          not_checking=self.ALL_BUT_EMAIL))

    def test_a_reason_may_travel_with_the_acknowledgement(self):
        """A dict is the readable form: the key, and who does enforce it."""
        self.assertTrue(pilotcaps.require(
            {"email_per_day": 1},
            not_checking={k: "checked elsewhere" for k in self.ALL_BUT_EMAIL}))

    def test_missing_one_key_from_the_acknowledgement_still_refuses(self):
        """The exact property that makes this survive the NEXT ceiling: an
        acknowledgement is a list, not a flag, so adding a key to `CEILING`
        breaks every call site until somebody decides who enforces it."""
        partial = self.ALL_BUT_EMAIL - {"new_accounts_per_day"}
        with self.assertRaises(pilotcaps.UnacknowledgedCap) as caught:
            pilotcaps.require({"email_per_day": 1}, not_checking=partial)
        self.assertIn("new_accounts_per_day", str(caught.exception))

    def test_claiming_not_to_check_something_the_plan_checks_refuses(self):
        """One of the two statements is false and a reader cannot tell which."""
        with self.assertRaises(pilotcaps.UnacknowledgedCap) as caught:
            pilotcaps.require({"email_per_day": 1},
                              not_checking=set(pilotcaps.KEYS))
        self.assertIn("email_per_day", str(caught.exception))

    def test_a_key_that_is_not_a_ceiling_refuses(self):
        with self.assertRaises(pilotcaps.UnacknowledgedCap):
            pilotcaps.require({"email_per_day": 1},
                              not_checking=self.ALL_BUT_EMAIL | {"invented"})

    def test_a_plan_covering_every_ceiling_needs_no_acknowledgement(self):
        self.assertTrue(pilotcaps.require({k: 1 for k in pilotcaps.KEYS}))

    def test_a_breach_is_still_a_breach_and_still_says_so(self):
        """Coverage is a fact about the call site; a breach is a fact about
        the world. The breach keeps its own type and its own message, or
        every existing caller's refusal becomes harder to read."""
        with self.assertRaises(pilotcaps.PilotCapExceeded) as caught:
            pilotcaps.require({"email_per_day": 10_000})
        self.assertIn("10000", str(caught.exception).replace(",", ""))


class EveryCeilingHasAnEnforcer(unittest.TestCase):
    """The regression guard for the whole class of defect.

    A ceiling added to `pilotcaps.CEILING` is now accounted for in exactly one
    of two places: gate 5 checks it, or `executionguard.CAPS_ENFORCED_ELSEWHERE`
    names what does. Neither is a place a new ceiling reaches by accident, and
    this test fails the moment one does not.
    """

    CHECKED_AT_GATE_5 = {"email_per_day", "linkedin_per_day",
                         "per_sender_per_day", "new_accounts_per_day"}

    def test_no_ceiling_is_unaccounted_for(self):
        accounted = (self.CHECKED_AT_GATE_5
                     | set(executionguard.CAPS_ENFORCED_ELSEWHERE))
        self.assertEqual(set(pilotcaps.KEYS) - accounted, set())

    def test_nothing_is_claimed_twice(self):
        self.assertEqual(
            self.CHECKED_AT_GATE_5
            & set(executionguard.CAPS_ENFORCED_ELSEWHERE), set())

    def test_the_ceiling_this_was_about_is_five(self):
        self.assertEqual(pilotcaps.CEILING["new_accounts_per_day"], 5)

    def test_the_next_batch_would_be_refused(self):
        """17 contacts across 17 accounts, which is what the cap is for."""
        with self.assertRaises(pilotcaps.PilotCapExceeded) as caught:
            pilotcaps.require({"new_accounts_per_day": 17},
                              not_checking=set(pilotcaps.KEYS)
                              - {"new_accounts_per_day"})
        self.assertIn("17", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
