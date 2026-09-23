"""A drop needs an ownership readback it can prove is current.

## The defect this pins

`inbound.OWNED_SEATS` was the literal `{174892}` and `OWNED_CAMPAIGNS` four
ids, both read back from the provider on 2026-09-20. By 2026-09-23 the account
held 33 further live campaigns (613724-613761) on 33 distinct seats, every one
of them ours and none of them in either set. `_positively_not_ours` would
therefore have answered **True** for a reply to one of our own campaigns and
the unmatched-reply notification would have been dropped silently.

It had not yet fired only because those campaigns had sent 75 connection
requests and received no reply at all. The window was open; nothing had walked
through it.

## What is asserted

The rule is the register's own: a cached value on a safety path carries the
date and source it came from, and REFUSES rather than answers when it cannot
prove it is current. Refusing costs a notification nobody needed. Answering
wrongly costs a reply nobody saw. Those are not symmetric, and the tests below
say so in both directions.
"""
import datetime
import json
import os
import tempfile
import unittest

from src import inbound


def readback(generated_at, campaign=613724, seat=116968):
    return {
        "generated_at": generated_at,
        "heyreach": {"resonate_campaigns": [
            {"heyreach_campaign_id": campaign, "senders": [{"id": seat}]}]},
    }


def write(payload):
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(payload, handle)
    handle.close()
    return handle.name


def hours_ago(n):
    at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=n)
    return at.isoformat().replace("+00:00", "Z")


class ReadbackTest(unittest.TestCase):

    def path(self, payload):
        p = write(payload)
        self.addCleanup(lambda: os.path.exists(p) and os.unlink(p))
        return p


class AFreshReadbackLicensesADrop(ReadbackTest):

    def test_it_reads_seats_and_campaigns_from_the_file(self):
        owned, why = inbound._owned(path=self.path(readback(hours_ago(1))))
        self.assertIsNone(why)
        seats, campaigns = owned
        self.assertIn(116968, seats)
        self.assertIn(613724, campaigns)

    def test_the_literals_are_a_floor_not_a_ceiling(self):
        """A readback that lost a campaign cannot make us disown it."""
        owned, _ = inbound._owned(path=self.path(readback(hours_ago(1))))
        seats, campaigns = owned
        self.assertTrue(inbound.OWNED_SEATS.issubset(seats))
        self.assertTrue(inbound.OWNED_CAMPAIGNS.issubset(campaigns))


class AStaleReadbackRefuses(ReadbackTest):

    def test_past_the_age_limit_it_returns_none(self):
        age = inbound.OWNERSHIP_MAX_AGE_HOURS + 1
        owned, why = inbound._owned(path=self.path(readback(hours_ago(age))))
        self.assertIsNone(owned)
        self.assertIn("old", why)

    def test_the_reason_names_the_command_that_refreshes_it(self):
        """'Could not prove ownership' must never print like 'not ours'."""
        age = inbound.OWNERSHIP_MAX_AGE_HOURS + 40
        _owned, why = inbound._owned(path=self.path(readback(hours_ago(age))))
        self.assertIn("provider_truth.py", why)

    def test_a_missing_file_refuses(self):
        owned, why = inbound._owned(path="/nonexistent/readback.json")
        self.assertIsNone(owned)
        self.assertIn("unreadable", why)

    def test_an_undated_readback_refuses(self):
        payload = readback(hours_ago(1))
        payload.pop("generated_at")
        owned, why = inbound._owned(path=self.path(payload))
        self.assertIsNone(owned)
        self.assertIn("generated_at", why)

    def test_an_unparseable_date_refuses(self):
        owned, why = inbound._owned(path=self.path(readback("last Tuesday")))
        self.assertIsNone(owned)
        self.assertIn("unparseable", why)


class TheRefusalReachesTheDecision(unittest.TestCase):
    """The part that matters: a refusal must not drop anything."""

    def use(self, result):
        prev = inbound._owned
        inbound._owned = lambda *a, **k: result
        self.addCleanup(setattr, inbound, "_owned", prev)

    def test_a_stale_readback_drops_nothing(self):
        self.use((None, "readback is 63h old"))
        for event in ({"linkedin_account_id": 999999},
                      {"external_campaign_id": 999999},
                      {"linkedin_account_id": 116968,
                       "external_campaign_id": 613724}):
            self.assertFalse(inbound._positively_not_ours(event),
                             f"dropped {event} on an unprovable allowlist")

    def test_the_stale_b1_case_specifically(self):
        """The 2026-09-23 case, as it stood: our campaign, an unlisted seat."""
        self.use((({174892}, {605732, 605487, 604869, 599020}), None))
        ours_but_unlisted = {"linkedin_account_id": 116968,
                             "external_campaign_id": 613724}
        # With the stale literals treated as current, our own reply is dropped.
        self.assertTrue(inbound._positively_not_ours(ours_but_unlisted))
        # With the readback unprovable, it is kept. That is the fix.
        self.use((None, "stale"))
        self.assertFalse(inbound._positively_not_ours(ours_but_unlisted))

    def test_a_fresh_readback_still_drops_a_foreign_seat(self):
        """The refusal must not have disabled attribution altogether."""
        self.use((({174892}, {605732}), None))
        self.assertTrue(
            inbound._positively_not_ours({"linkedin_account_id": 999999}))


if __name__ == "__main__":
    unittest.main()
