#!/usr/bin/env python3
"""The account is the unit of outreach, and the send gate could not see it.

MEASURED ON 2026-09-12, against the live pilot account, before this was
closed. `collision.check_account` on that domain answered:

    verdict            touched
    leads              1
    emails_sent_total  9
    campaigns          328 stopped (4 sent), 352 sequence_finished (5 sent)
    replies            0
    since              2026-04-23

Nine cold emails, to a colleague on the SAME record as the pilot contact,
across two campaigns, over five months. Canonical state held 42 events and
ZERO confirmed touches. `agencydnc` held zero entries. And suppression,
collision and fatigue all answered that the account was cold.

The cause is structural rather than an oversight. `executionguard` gate 4 ran

    if channel == "linkedin": check_linkedin_profile(...)
    else:                     check_address(...)

- person level, one channel, one OR the other - and `check_account`, the only
function that answers "has anybody at this company heard from us", had no
caller on any send path in the repository.

A BLANKET REFUSAL ON `touched` WOULD BE THE WRONG FIX and is the reason this
took a policy rather than a boolean. Most of a worked estate has been touched;
refusing all of it stops the product instead of protecting anyone. So
`collision.account_policy` keeps the distinctions the provider already draws:
somebody mid-sequence or somebody who answered is a STOP, a bounce or an
unreadable estate is a HOLD, and a finished campaign with no reply is history
that ALLOWS - while still being reported, so nobody can call that account
cold again.

The gate reads the email estate whatever channel is sending, because that is
where this client's history lives. Which required the thing that did not
exist: a canonical per-client provider binding, now `providers.emailbison.
workspace` in the client's own configuration, read by
`clients.provider_workspace` and refused when absent.
"""
import unittest

from src import clients, collision
from tests.base import QueueTest


def account(verdict=collision.CLEAR, sent=0, in_sequence=False,
            bounce=False, replies=0, interested=False, statuses=("stopped",)):
    """An answer shaped exactly as `collision.check_account` returns one."""
    return {
        "domain": "kestrelwharf.test", "workspace": "10",
        "leads": 1 if (sent or in_sequence) else 0,
        "emails_sent_total": sent,
        "anyone_in_sequence": in_sequence,
        "any_bounce": bounce,
        "verdict": verdict,
        "people": ([{"email": "someone@kestrelwharf.test", "lead_id": 1,
                     "lead_status": "bounced" if bounce else "unverified",
                     "emails_sent": sent, "replies": replies, "opens": 0,
                     "in_sequence": in_sequence,
                     "campaigns": [{"campaign_id": 1, "status": s,
                                    "emails_sent": sent, "replies": replies,
                                    "interested": interested}
                                   for s in statuses]}]
                   if (sent or in_sequence) else []),
    }


class ThePolicyKeepsTheDistinctions(unittest.TestCase):
    """Pure, so every case is stated rather than inferred from a fixture."""

    def decide(self, **kw):
        return collision.account_policy(account(**kw))[0]

    def test_an_untouched_account_is_allowed(self):
        self.assertEqual(self.decide(), collision.ALLOW)

    def test_a_finished_campaign_with_no_reply_is_history(self):
        """THE LIVE CASE. Nine emails, two finished campaigns, no reply."""
        self.assertEqual(
            self.decide(verdict=collision.TOUCHED, sent=9,
                        statuses=("stopped", "sequence_finished")),
            collision.ALLOW)

    def test_somebody_mid_sequence_stops_it(self):
        self.assertEqual(
            self.decide(verdict=collision.IN_SEQUENCE, sent=2,
                        in_sequence=True, statuses=("in_sequence",)),
            collision.STOP)

    def test_somebody_who_replied_stops_it(self):
        self.assertEqual(
            self.decide(verdict=collision.TOUCHED, sent=4, replies=1),
            collision.STOP)

    def test_somebody_marked_interested_stops_it(self):
        """A reply we never parsed is still an answer."""
        self.assertEqual(
            self.decide(verdict=collision.TOUCHED, sent=4, interested=True),
            collision.STOP)

    def test_a_bounce_holds_for_a_person_to_look(self):
        self.assertEqual(
            self.decide(verdict=collision.TOUCHED, sent=2, bounce=True),
            collision.HOLD)

    def test_an_unreadable_estate_holds(self):
        """Missing evidence is not positive evidence."""
        self.assertEqual(self.decide(verdict=collision.UNKNOWN),
                         collision.HOLD)
        self.assertEqual(collision.account_policy(None)[0], collision.HOLD)

    def test_a_stop_outranks_a_bounce(self):
        """Order matters: somebody in sequence is the stronger fact."""
        self.assertEqual(
            self.decide(verdict=collision.IN_SEQUENCE, sent=3,
                        in_sequence=True, bounce=True),
            collision.STOP)

    def test_every_answer_says_why(self):
        """The reason is what an operator reads, so it names the fact."""
        for kw in ({}, {"verdict": collision.TOUCHED, "sent": 9},
                   {"verdict": collision.IN_SEQUENCE, "in_sequence": True},
                   {"verdict": collision.UNKNOWN}):
            with self.subTest(**kw):
                _decision, why = collision.account_policy(account(**kw))
                self.assertTrue(why and len(why) > 20, why)


class TheBindingIsPerClient(QueueTest):
    """A provider estate is a binding beneath a client, not a global default."""

    def test_productive_names_its_email_estate(self):
        self.assertEqual(
            clients.provider_workspace(clients.load("productive"),
                                       "emailbison"),
            "10")

    def test_an_unbound_client_answers_none_not_a_default(self):
        """The defect this replaces: a process-global BISON_WORKSPACE_ID and a
        `--workspace` argument, so any caller could name any estate for any
        client and a second client would inherit the first one's."""
        self.assertIsNone(clients.provider_workspace({}, "emailbison"))
        self.assertIsNone(
            clients.provider_workspace({"providers": {}}, "emailbison"))

    def test_an_unbound_provider_on_a_bound_client_is_still_none(self):
        self.assertIsNone(
            clients.provider_workspace(clients.load("productive"), "nosuch"))


# That the GATE consults the policy is asserted behaviourally, on the real
# `executionguard.authorize`, in
# `test_no_write_happens_without_every_gate.TheAccountIsAskedToo`. The first
# version of that assertion lived here and was worthless twice over: one test
# patched `check_account` and then called it directly, proving nothing about
# the gate, and the other read `inspect.getsource` for the gate's name - which
# is the failure mode a comment can satisfy.


if __name__ == "__main__":
    unittest.main()
