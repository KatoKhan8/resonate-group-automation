"""Which account a contact sends from, and why it never changes on a rerun.

A contact that moves between inboxes between runs looks to a mailbox provider
like two strangers writing about the same thing. The determinism tests below
are the ones that keep that from happening.
"""
import unittest

from src import campaigns, senders
from tests.campaignbase import CampaignTest

CAMPAIGN = {
    "campaign_id": "camp-1",
    "senders": {
        "email": [{"id": "bison-1", "daily_limit": 3},
                  {"id": "bison-2", "daily_limit": 3}],
        "linkedin": [{"id": "hr-1", "daily_limit": 2}],
    },
    "daily_volume": {"email": 5, "linkedin": 2},
}


def item(contact_key, channel="email"):
    return {"contact_key": contact_key, "channel": channel,
            "push_id": f"rec:{contact_key}:day1:{channel}"}


class TestReadingTheConfig(unittest.TestCase):
    def test_a_bare_string_is_accepted_as_an_account(self):
        campaign = {"senders": {"email": ["bison-9"]}}
        self.assertEqual(senders.accounts(campaign, "email")[0]["id"], "bison-9")

    def test_an_account_is_enabled_unless_it_says_otherwise(self):
        campaign = {"senders": {"email": [{"id": "a"}, {"id": "b", "enabled": False}]}}
        self.assertEqual([a["id"] for a in senders.enabled(campaign, "email")], ["a"])

    def test_a_missing_limit_falls_back_to_the_default(self):
        campaign = {"senders": {"email": [{"id": "a"}]}}
        self.assertEqual(senders.accounts(campaign, "email")[0]["daily_limit"],
                         senders.DEFAULT_DAILY_LIMIT)

    def test_a_row_with_no_id_is_ignored_rather_than_guessed_at(self):
        campaign = {"senders": {"email": [{"daily_limit": 10}, {"id": "a"}]}}
        self.assertEqual(len(senders.accounts(campaign, "email")), 1)

    def test_capacity_is_the_sum_of_the_enabled_limits(self):
        self.assertEqual(senders.capacity(CAMPAIGN, "email"), 6)


class TestDeterminism(unittest.TestCase):
    def test_the_same_contact_always_gets_the_same_account(self):
        first = senders.assign(CAMPAIGN, "email", "acme-champ")["id"]
        for _ in range(20):
            self.assertEqual(senders.assign(CAMPAIGN, "email", "acme-champ")["id"],
                             first)

    def test_the_choice_does_not_depend_on_pythons_hash_seed(self):
        """sha1 of the key, not hash(), which is salted per process."""
        import inspect
        self.assertIn("sha1", inspect.getsource(senders._slot))

    def test_a_rerun_over_the_same_work_assigns_identically(self):
        work = [item(f"c{i}") for i in range(6)]
        first = senders.assign_all(CAMPAIGN, work)["assigned"]
        second = senders.assign_all(CAMPAIGN, list(reversed(work)))["assigned"]
        self.assertEqual({r["push_id"]: r["account"] for r in first},
                         {r["push_id"]: r["account"] for r in second})

    def test_different_contacts_spread_across_the_accounts(self):
        used = {senders.assign(CAMPAIGN, "email", f"contact-{i}")["id"]
                for i in range(20)}
        self.assertEqual(used, {"bison-1", "bison-2"})


class TestTheLimits(unittest.TestCase):
    def test_an_account_at_its_limit_is_passed_over(self):
        account = senders.assign(CAMPAIGN, "email", "acme-champ",
                                 used={"bison-1": 3, "bison-2": 0})
        self.assertEqual(account["id"], "bison-2")

    def test_every_account_full_refuses_rather_than_overshooting(self):
        with self.assertRaises(senders.NoSenderAvailable):
            senders.assign(CAMPAIGN, "email", "x", used={"bison-1": 3,
                                                         "bison-2": 3})

    def test_the_daily_cap_is_respected_across_a_whole_run(self):
        work = [item(f"c{i}") for i in range(10)]
        result = senders.assign_all(CAMPAIGN, work)
        self.assertEqual(len(result["assigned"]), 6)      # capacity is 6
        self.assertEqual(len(result["refused"]), 4)
        for account, count in result["used"].items():
            self.assertLessEqual(count, 3, account)

    def test_a_refusal_says_which_step_and_why(self):
        work = [item(f"c{i}") for i in range(10)]
        refused = senders.assign_all(CAMPAIGN, work)["refused"][0]
        self.assertIn("push_id", refused)
        self.assertIn("daily limit", refused["why"])


class TestDisabledAndMissing(unittest.TestCase):
    def test_a_disabled_account_is_never_used(self):
        campaign = {"senders": {"email": [{"id": "off", "enabled": False},
                                          {"id": "on"}]}}
        for i in range(20):
            self.assertEqual(senders.assign(campaign, "email", f"c{i}")["id"],
                             "on")

    def test_a_channel_with_no_account_refuses(self):
        with self.assertRaises(senders.NoSenderAvailable):
            senders.assign({"senders": {}}, "email", "x")

    def test_a_channel_with_only_disabled_accounts_refuses(self):
        campaign = {"senders": {"email": [{"id": "off", "enabled": False}]}}
        with self.assertRaises(senders.NoSenderAvailable):
            senders.assign(campaign, "email", "x")

    def test_one_channel_being_unavailable_does_not_block_the_other(self):
        campaign = {"senders": {"email": [], "linkedin": [{"id": "hr-1"}]}}
        result = senders.assign_all(campaign, [item("a", "email"),
                                               item("b", "linkedin")])
        self.assertEqual([r["channel"] for r in result["assigned"]], ["linkedin"])
        self.assertEqual([r["channel"] for r in result["refused"]], ["email"])


class TestTheMappingCheck(unittest.TestCase):
    def test_a_good_mapping_passes(self):
        ok, detail = senders.check_mapping(CAMPAIGN)
        self.assertTrue(ok)
        self.assertIn("capacity", detail)

    def test_no_accounts_at_all_fails(self):
        ok, detail = senders.check_mapping({"senders": {}})
        self.assertFalse(ok)
        self.assertIn("no sender accounts", detail)

    def test_every_account_disabled_fails(self):
        campaign = {"senders": {"email": [{"id": "a", "enabled": False}]}}
        ok, detail = senders.check_mapping(campaign)
        self.assertFalse(ok)
        self.assertIn("disabled", detail)

    def test_a_volume_beyond_the_capacity_fails(self):
        campaign = {"senders": {"email": [{"id": "a", "daily_limit": 5}]},
                    "daily_volume": {"email": 500}}
        ok, detail = senders.check_mapping(campaign)
        self.assertFalse(ok)
        self.assertIn("exceeds", detail)


class TestSendersInACampaign(CampaignTest):
    def test_a_campaign_dry_run_reports_the_accounts_it_would_use(self):
        campaign, recs, _ = self.approved_campaign()
        plan = campaigns.dry_run("camp-1", day=21, recs=recs,
                                 config=self.config, campaign=campaign)
        self.assertTrue(plan["senders"])
        for channel, used in plan["senders"].items():
            self.assertTrue(used, channel)

    def test_the_launch_checklist_fails_when_no_sender_is_configured(self):
        campaign, recs = self.ready_campaign()
        campaign["senders"] = {}
        result = campaigns.validate("camp-1", recs, self.config,
                                    campaign=campaign)
        self.assertIn("sender mapping", result["blockers"])


if __name__ == "__main__":
    unittest.main()
