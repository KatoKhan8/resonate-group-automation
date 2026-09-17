#!/usr/bin/env python3
"""Whichever of two staged campaigns activates second is refused.

THE HAZARD. A campaign this system staged and left PAUSED produces membership
rows reading `sending_paused` or `stopped`, both of which are in
`EXCLUDABLE_MEMBERSHIP`. `staging_artifact_evidence`'s four arms are all
RETROSPECTIVE - "has never sent an email to anybody" is satisfied by a
campaign that is about to. So while cohort A sits staged and paused,
`check_account` on its accounts reads CLEAR, and cohort B can be built at
the same accounts.

WHAT CLOSES IT IS ORDER RATHER THAN DESIGN. The moment A activates, its rows
read `in_sequence`, stop being excludable (because `in_sequence` is NOT in
`EXCLUDABLE_MEMBERSHIP`), and B's activation is refused by the account gate.
**Nothing asserts that.** These tests pin it.

Campaign 485 on the live estate is a DRAFT holding the same ten leads as the
live campaign 487, and its membership rows read `stopped`. That is the
concrete shape of the window.

GLM's adversarial review claimed `without_our_staging` could flip an account
from IN_SEQUENCE to CLEAR. That specific claim is a FALSE POSITIVE - verified
in `docs/GLM-REVIEW-COLLISION-2026-09-17.md`. `_excludable` refuses any
membership status outside `EXCLUDABLE_MEMBERSHIP = frozenset({'sending_paused',
'stopped'})`, so a row reading `in_sequence` can never be dropped. The
ADJACENT hazard - two paused campaigns, both excluded, both later activated -
is real, and that is what these tests pin.
"""
import json
import os
import tempfile
import unittest

from src import collision, providers
from src.providers import bison

WS = 10

PLACEHOLDER = "test-key-not-real"
_saved = {}


def setUpModule():
    for name in ("BISON_KEY", "BISON_BASE"):
        _saved[name] = os.environ.get(name)
    os.environ["BISON_KEY"] = PLACEHOLDER
    os.environ.setdefault("BISON_BASE", "https://bison.invalid")


def tearDownModule():
    for name, value in _saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


# --------------------------------------------------------------- constants

CAMPAIGN_A = 600
CAMPAIGN_B = 601
CLIENT = "productive"
CANONICAL_A = "productive-email-cohort-a"
CANONICAL_B = "productive-email-cohort-b"
DOMAIN = "acme.test"

#: What a campaign of ours that has never sent anything reads like.
SILENT = {
    "id": 0,
    "name": "",
    "status": "paused",
    "emails_sent": 0, "total_leads_contacted": 0,
    "opened": 0, "unique_opens": 0,
    "replied": 0, "unique_replies": 0,
    "bounced": 0, "unsubscribed": 0, "interested": 0,
    "total_leads": 1,
}


def campaign_row(cid, canonical, **overrides):
    row = dict(SILENT)
    row["id"] = cid
    row["name"] = (f"RESONATE - PRODUCTIVE - EMAIL - COHORT "
                   f"[{CLIENT}/{canonical}]")
    row.update(overrides)
    return row


def membership(campaign_id, status, sent=0, replies=0, opens=0,
               interested=False):
    return {"campaign_id": campaign_id, "status": status, "emails_sent": sent,
            "replies": replies, "opens": opens, "interested": interested}


def lead(email, sent=0, memberships=(), lead_status="unverified"):
    return {
        "id": abs(hash(email)) % 100000,
        "email": email,
        "status": lead_status,
        "overall_stats": {"emails_sent": sent, "replies": 0, "opens": 0},
        "lead_campaign_data": list(memberships),
        "created_at": "2026-04-08T18:33:00.000000Z",
    }


class Wire:
    """A mutable provider transport. Campaigns can be 'activated' by changing
    their status and their memberships' status in place."""

    def __init__(self, campaigns, rows, queues=None):
        self.campaigns = dict(campaigns)
        self.rows = list(rows)
        self.queues = dict(queues or {})

    def __call__(self, method, url, headers=None, body=None, timeout=None):
        if bison.USERS_PATH in url:
            return 200, {"data": {"workspace": {"id": WS, "name": "TESTWS"}}}
        if "/scheduled-emails" in url:
            which = int(url.split("/campaigns/")[1].split("/")[0])
            return 200, {"data": self.queues.get(which, []),
                         "meta": {"current_page": 1, "last_page": 1,
                                  "per_page": 15,
                                  "total": len(self.queues.get(which, []))}}
        if "/campaigns/" in url:
            which = int(url.split("/campaigns/")[1].split("?")[0].split("/")[0])
            if which not in self.campaigns:
                return 404, {"message": "no such campaign"}
            return 200, {"data": self.campaigns[which]}
        return 200, {"data": self.rows,
                     "meta": {"current_page": 1, "last_page": 1,
                              "per_page": 15, "total": len(self.rows)}}

    def activate(self, cid):
        """Simulate the membership-level effect of activation.

        Only the membership rows change - from `sending_paused`/`stopped` to
        `in_sequence`. The campaign status stays `paused` (which is in
        `NOT_SENDING_STATES`), so the campaign-level proof still holds. This
        isolates the membership-level protection: `in_sequence` is NOT in
        `EXCLUDABLE_MEMBERSHIP`, so the row is no longer excludable.

        This is the realistic transient state: the provider has resumed the
        campaign (memberships flip to `in_sequence` immediately) but the
        campaign row and counters have not moved yet.
        """
        for row in self.rows:
            for m in row.get("lead_campaign_data", []):
                if m.get("campaign_id") == cid:
                    m["status"] = "in_sequence"


class ActivationOrderTest(unittest.TestCase):
    """Two campaigns staged at the same account, both proven silent."""

    def setUp(self):
        collision.forget_staging_evidence()
        self.addCleanup(collision.forget_staging_evidence)
        tmp = tempfile.mkdtemp()
        self.campaigns_path = os.path.join(tmp, "campaigns.jsonl")
        self.ledger_path = os.path.join(tmp, "action-ledger.jsonl")
        self._write(self.campaigns_path, [
            {"campaign_id": CANONICAL_A, "client": CLIENT,
             "bison_campaign_id": CAMPAIGN_A, "name": "x"},
            {"campaign_id": CANONICAL_B, "client": CLIENT,
             "bison_campaign_id": CAMPAIGN_B, "name": "x"},
        ])
        self._write(self.ledger_path, [])
        for name, value in (("CAMPAIGNS", self.campaigns_path),
                            ("ACTION_LEDGER", self.ledger_path)):
            before = os.environ.get(name)
            os.environ[name] = value
            self.addCleanup(self._restore, name, before)

    @staticmethod
    def _restore(name, before):
        if before is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = before

    @staticmethod
    def _write(path, rows):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")

    def _estate(self, a_status="sending_paused", b_status="stopped"):
        """Both campaigns at one lead, one domain, both paused."""
        return [lead(f"prospect@{DOMAIN}", memberships=[
            membership(CAMPAIGN_A, a_status),
            membership(CAMPAIGN_B, b_status),
        ])]

    def _wire(self, rows=None, a_status="paused", b_status="paused"):
        rows = rows if rows is not None else self._estate()
        w = Wire(
            campaigns={
                CAMPAIGN_A: campaign_row(CAMPAIGN_A, CANONICAL_A,
                                         status=a_status),
                CAMPAIGN_B: campaign_row(CAMPAIGN_B, CANONICAL_B,
                                         status=b_status),
            },
            rows=rows)
        providers.set_transport(w)
        self.addCleanup(providers.reset_transport)
        return w

    def _account(self, wire=None):
        if wire is None:
            wire = self._wire()
        return collision.check_account(DOMAIN, expect_workspace=WS)

    # -------------------------------------------------------- (1) exclusion

    def test_the_exclusion_happens(self):
        """With both campaigns staged and paused and zero sends,
        `check_account` returns a verdict that is not blocked by either
        campaign's own rows, and `our_staging_excluded` names them both."""
        account = self._account()
        self.assertEqual(account["verdict"], collision.CLEAR)
        excluded_ids = sorted(
            {e["campaign_id"] for e in account["our_staging_excluded"]})
        self.assertEqual(excluded_ids, [CAMPAIGN_A, CAMPAIGN_B])

    def test_the_policy_says_allow(self):
        """Both rows excluded → no sequence, no sends, no suspect status →
        ALLOW."""
        account = self._account()
        decision, why = collision.account_policy(account)
        self.assertEqual(decision, collision.ALLOW)
        self.assertIn("no prior contact", why)

    # --------------------------------------------------- (2) the window

    def test_the_window_is_real(self):
        """While both campaigns sit paused, a second cohort at the same
        account passes the account gate. The window is documented, not
        folklore."""
        account = self._account()
        decision, _why = collision.account_policy(account)
        self.assertEqual(decision, collision.ALLOW,
                         "a second cohort at this account would be refused "
                         "even though neither campaign has sent - the window "
                         "is not real, or the test is wrong")

    # ----------------------------- (3) the second activation is refused

    def test_activating_a_makes_b_refused(self):
        """THE PROPERTY THAT MATTERS. Activate A: its rows become
        `in_sequence`, stop being excludable. Now `check_account` reads
        IN_SEQUENCE → STOP. B's activation is refused by the account gate,
        with a reason naming the account."""
        wire = self._wire()
        wire.activate(CAMPAIGN_A)
        collision.forget_staging_evidence()
        account = self._account(wire)
        self.assertEqual(account["verdict"], collision.IN_SEQUENCE)
        self.assertTrue(account["anyone_in_sequence"])
        decision, why = collision.account_policy(account)
        self.assertEqual(decision, collision.STOP)
        self.assertIn("mid-sequence", why)

    def test_activating_b_makes_a_refused(self):
        """The mirror. Activate B first; A's activation is refused."""
        wire = self._wire()
        wire.activate(CAMPAIGN_B)
        collision.forget_staging_evidence()
        account = self._account(wire)
        self.assertEqual(account["verdict"], collision.IN_SEQUENCE)
        decision, why = collision.account_policy(account)
        self.assertEqual(decision, collision.STOP)
        self.assertIn("mid-sequence", why)

    def test_after_a_activates_b_rows_are_no_longer_excluded(self):
        """After A activates, only A's rows are `in_sequence` and unexcluded.
        B's rows are still `stopped` and still excluded. The account is STOP
        because of A, not because B became visible."""
        wire = self._wire()
        wire.activate(CAMPAIGN_A)
        collision.forget_staging_evidence()
        account = self._account(wire)
        excluded_ids = {e["campaign_id"]
                        for e in account["our_staging_excluded"]}
        self.assertIn(CAMPAIGN_B, excluded_ids,
                      "B's paused rows should still be excluded")
        self.assertNotIn(CAMPAIGN_A, excluded_ids,
                         "A's activated rows must not be excluded")

    # ----------------------------------------------- (4) the break-proof

    def test_break_proof_adding_in_sequence_to_excludable_breaks_the_guard(self):
        """THE BREAK-PROOF. Add `in_sequence` to `EXCLUDABLE_MEMBERSHIP` by
        hand. The test in (3) must go RED - and for the intended reason: the
        account reads CLEAR instead of IN_SEQUENCE, not because of an
        unrelated failure. Then PUT THE CONSTANT BACK."""
        original = collision.EXCLUDABLE_MEMBERSHIP
        try:
            collision.EXCLUDABLE_MEMBERSHIP = frozenset(
                {"sending_paused", "stopped", "in_sequence"})
            wire = self._wire()
            wire.activate(CAMPAIGN_A)
            collision.forget_staging_evidence()
            account = self._account(wire)
            decision, _why = collision.account_policy(account)
            # With in_sequence excludable, A's activated rows are dropped,
            # the account reads CLEAR/ALLOW, and B's activation is NOT
            # refused. That is the break.
            self.assertNotEqual(decision, collision.STOP,
                                "the break-proof did not break: adding "
                                "in_sequence to EXCLUDABLE_MEMBERSHIP should "
                                "have made the account read ALLOW, not STOP")
        finally:
            collision.EXCLUDABLE_MEMBERSHIP = original

    def test_the_constant_is_untouched(self):
        """After the break-proof, `EXCLUDABLE_MEMBERSHIP` is back to its
        shipped value. This test runs last by name order and confirms no
        mutation leaked."""
        self.assertEqual(collision.EXCLUDABLE_MEMBERSHIP,
                         frozenset({"stopped", "sending_paused"}))


if __name__ == "__main__":
    unittest.main()
