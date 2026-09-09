"""Senders, accounts, pairings and the boundary each of them sits inside.

Two things are being held here.

**A sender is not an account.** The whole reason this model exists is that
"Anna" and "anna07@" are different objects, and that Anna-on-email and
Petar-on-LinkedIn are different people. Conflating any two of those is how a
message ends up claiming a colleague who does not exist.

**Everything is workspace-scoped, including the provider's own ids.** A
HeyReach account id is somebody else's namespace with no cross-tenant
uniqueness guarantee, so resolving one has to be scoped or it becomes a way to
walk from a provider id into another client's roster.
"""
import unittest

from src import assignment, senderidentity as si, store
from tests.campaignbase import CampaignTest

MINE = "productive"
THEIRS = "contactout"


def two_workspaces():
    return [
        si.new_sender(MINE, "anna", "Anna Novak", team="growth"),
        si.new_sender(MINE, "petar", "Petar Horvat", team="growth"),
        si.new_email_account(MINE, "anna07", "anna", "anna07@productive.test",
                             provider_account_id="shared-id"),
        si.new_linkedin_account(MINE, "petar-li", "petar",
                                "https://www.linkedin.com/in/petar"),

        si.new_sender(THEIRS, "mara", "Mara Kovac"),
        si.new_email_account(THEIRS, "mara01", "mara", "mara01@contactout.test",
                             # Deliberately the same provider id as Anna's.
                             provider_account_id="shared-id"),
        si.new_linkedin_account(THEIRS, "mara-li", "mara",
                                "https://www.linkedin.com/in/mara"),
    ]


class TheModelSeparatesPeopleFromAccounts(CampaignTest):

    def setUp(self):
        super().setUp()
        si.install(two_workspaces())

    def test_one_human_can_own_many_inboxes(self):
        si.install(two_workspaces() + [
            si.new_email_account(MINE, f"anna{n:02d}", "anna",
                                 f"anna{n:02d}@productive.test")
            for n in range(8, 28)])
        mine = si.email_accounts(MINE, sender_id="anna")
        self.assertEqual(len(mine), 21)
        self.assertEqual({a["sender_id"] for a in mine}, {"anna"})

    def test_the_email_human_and_the_linkedin_human_are_not_the_same(self):
        roster = si.roster(MINE)
        email_people = {a["sender_id"] for a in roster["email_accounts"]}
        li_people = {a["sender_id"] for a in roster["linkedin_accounts"]}
        self.assertEqual(email_people, {"anna"})
        self.assertEqual(li_people, {"petar"})
        self.assertNotEqual(email_people, li_people)

    def test_an_account_with_no_owner_is_surfaced_not_hidden(self):
        si.add(si.new_email_account(MINE, "orphan01", "nobody",
                                    "orphan@productive.test"))
        roster = si.roster(MINE)
        self.assertEqual([a["account_id"] for a in roster["orphan_accounts"]],
                         ["orphan01"])

    def test_a_health_state_defaults_to_unknown_not_to_healthy(self):
        account = si.new_email_account(MINE, "x1", "anna", "x@productive.test")
        self.assertEqual(account["health"], si.HEALTH_UNKNOWN)

    def test_an_unknown_capacity_stays_unknown(self):
        """A guessed sending limit looks like a control and is not one."""
        si.install([
            si.new_sender(MINE, "anna", "Anna"),
            si.new_email_account(MINE, "a1", "anna", "a1@productive.test",
                                 daily_limit=40),
            si.new_email_account(MINE, "a2", "anna", "a2@productive.test"),
        ])
        cap = si.capacity(MINE)["email"]
        self.assertEqual(cap["known_daily_capacity"], 40)
        self.assertEqual(cap["accounts_with_no_known_limit"], 1)
        self.assertFalse(cap["complete"],
                         "a partial sum was presented as the capacity")

    def test_a_bad_id_is_refused(self):
        for bad in ("../etc", "Anna", "", "a" * 100, "an na"):
            with self.assertRaises(si.SenderError):
                si.new_sender(MINE, bad, "x")


class NothingCrossesAWorkspace(CampaignTest):

    def setUp(self):
        super().setUp()
        si.install(two_workspaces())

    def test_a_sender_from_another_workspace_is_refused_not_returned(self):
        with self.assertRaises(si.CrossWorkspaceSender):
            si.sender(MINE, "mara")

    def test_an_email_account_from_another_workspace_is_refused(self):
        with self.assertRaises(si.CrossWorkspaceSender):
            si.account(MINE, si.EMAIL, "mara01")

    def test_a_linkedin_account_from_another_workspace_is_refused(self):
        with self.assertRaises(si.CrossWorkspaceSender):
            si.account(MINE, si.LINKEDIN, "mara-li")

    def test_a_sender_that_exists_nowhere_is_simply_absent(self):
        """Absent and forbidden are different answers to different questions."""
        self.assertIsNone(si.sender(MINE, "nobody-at-all"))

    def test_a_shared_provider_id_does_not_cross(self):
        """A provider id is somebody else's namespace, with no uniqueness."""
        mine = si.by_provider_account(MINE, si.EMAIL, "shared-id")
        theirs = si.by_provider_account(THEIRS, si.EMAIL, "shared-id")
        self.assertEqual(mine["account_id"], "anna07")
        self.assertEqual(theirs["account_id"], "mara01")
        self.assertNotEqual(mine["workspace"], theirs["workspace"])

    def test_a_roster_lists_only_one_workspace(self):
        roster = si.roster(MINE)
        for row in roster["senders"] + roster["email_accounts"]:
            self.assertEqual(row["workspace"], MINE)
        self.assertNotIn("mara", [s["sender_id"] for s in roster["senders"]])

    def test_a_pairing_cannot_name_another_workspaces_sender(self):
        """Stored is not the same as honoured: the allocator resolves the
        LinkedIn human out of this workspace's pool and finds nobody."""
        si.add(si.new_pairing(MINE, "anna", "mara"))
        contact = {"key": "k"}
        rec = {"id": "r", "contacts": [contact]}
        assignment.ensure(rec, contact, MINE)
        block = contact["sender_assignment"]
        self.assertEqual(block["linkedin"]["sender_id"], "petar",
                         "a foreign sender was honoured through a pairing")

    def test_capacity_counts_only_this_workspace(self):
        self.assertEqual(si.capacity(MINE)["email"]["accounts"], 1)
        self.assertEqual(si.capacity(THEIRS)["email"]["accounts"], 1)


class TheRelationshipGate(CampaignTest):

    def setUp(self):
        super().setUp()
        si.install(two_workspaces())

    def allowed(self, config):
        return si.relationship(MINE, "anna", "petar", config=config)

    def test_colleague_language_is_off_until_a_workspace_turns_it_on(self):
        link = self.allowed({})
        self.assertFalse(link["colleague_language_allowed"])
        self.assertIn("has not enabled", link["why"])

    def test_a_workspace_can_turn_it_on(self):
        link = self.allowed({"sender_policy": {"colleague_language": True}})
        self.assertTrue(link["colleague_language_allowed"])

    def test_the_same_person_needs_no_permission(self):
        link = si.relationship(MINE, "anna", "anna", config={})
        self.assertEqual(link["kind"], si.SAME_PERSON)

    def test_a_sender_from_another_workspace_is_never_a_colleague(self):
        """`sender()` raises for a foreign id, so this must not leak through."""
        with self.assertRaises(si.CrossWorkspaceSender):
            si.relationship(MINE, "anna", "mara",
                            config={"sender_policy":
                                    {"colleague_language": True}})

    def test_an_inactive_sender_is_not_described_as_a_colleague(self):
        si.set_active(MINE, si.SENDER, "petar", False)
        link = self.allowed({"sender_policy": {"colleague_language": True}})
        self.assertFalse(link["colleague_language_allowed"])


class StickyAssignment(CampaignTest):

    def setUp(self):
        super().setUp()
        si.install(two_workspaces())

    def contact(self, key="k"):
        contact = {"key": key, "selected": True}
        rec = {"id": "r", "contacts": [contact]}
        return rec, contact

    def test_the_first_allocation_is_deterministic(self):
        first, second = self.contact(), self.contact()
        assignment.ensure(first[0], first[1], MINE)
        assignment.ensure(second[0], second[1], MINE)
        self.assertEqual(first[1]["sender_assignment"]["email"]["account_id"],
                         second[1]["sender_assignment"]["email"]["account_id"])

    def test_adding_an_inbox_does_not_move_an_assigned_contact(self):
        """The bug this model exists to remove: a hash whose modulus moved."""
        rec, contact = self.contact()
        assignment.ensure(rec, contact, MINE)
        before = dict(contact["sender_assignment"]["email"])

        for n in range(2, 20):
            si.add(si.new_email_account(MINE, f"anna{n:02d}", "anna",
                                        f"anna{n:02d}@productive.test"))
        assignment.ensure(rec, contact, MINE)
        after = contact["sender_assignment"]["email"]
        self.assertEqual(after["sender_id"], before["sender_id"])
        self.assertEqual(after["account_id"], before["account_id"])

    def test_a_changed_roster_is_reported_rather_than_acted_on(self):
        rec, contact = self.contact()
        assignment.ensure(rec, contact, MINE)
        self.assertFalse(assignment.is_stale(contact, MINE))
        si.add(si.new_email_account(MINE, "anna99", "anna",
                                    "anna99@productive.test"))
        self.assertTrue(assignment.is_stale(contact, MINE))
        # And still has not moved anybody.
        self.assertEqual(contact["sender_assignment"]["email"]["account_id"],
                         "anna07")

    def test_a_pairing_is_honoured_and_then_sticks(self):
        si.install(two_workspaces() + [
            si.new_sender(MINE, "tom", "Tom Ricci"),
            si.new_linkedin_account(MINE, "tom-li", "tom",
                                    "https://www.linkedin.com/in/tom"),
            si.new_pairing(MINE, "anna", "tom")])
        rec, contact = self.contact()
        assignment.ensure(rec, contact, MINE)
        self.assertEqual(contact["sender_assignment"]["linkedin"]["sender_id"],
                         "tom")
        self.assertEqual(contact["sender_assignment"]["linkedin"]["via"],
                         "pairing")

    def test_reassignment_needs_a_reason(self):
        rec, contact = self.contact()
        assignment.ensure(rec, contact, MINE)
        si.add(si.new_sender(MINE, "mark", "Mark Weber"))
        si.add(si.new_email_account(MINE, "mark01", "mark",
                                    "mark01@productive.test"))
        with self.assertRaises(ValueError):
            assignment.reassign(rec, contact, MINE, "email", "mark",
                                by="ops", reason="   ")

    def test_reassignment_records_both_sides_and_the_actor(self):
        rec, contact = self.contact()
        assignment.ensure(rec, contact, MINE)
        si.add(si.new_sender(MINE, "mark", "Mark Weber"))
        si.add(si.new_email_account(MINE, "mark01", "mark",
                                    "mark01@productive.test"))
        entry = assignment.reassign(rec, contact, MINE, "email", "mark",
                                    by="ops@productive.test",
                                    reason="anna is on leave")
        self.assertEqual(entry["from"]["sender_id"], "anna")
        self.assertEqual(entry["to"]["sender_id"], "mark")
        self.assertEqual(entry["by"], "ops@productive.test")
        self.assertIn("leave", entry["reason"])
        self.assertEqual(
            contact["sender_assignment"]["history"], [entry])

    def test_reassignment_to_a_foreign_sender_is_refused(self):
        rec, contact = self.contact()
        assignment.ensure(rec, contact, MINE)
        with self.assertRaises(si.CrossWorkspaceSender):
            assignment.reassign(rec, contact, MINE, "email", "mara",
                                by="ops", reason="trying it on")

    def test_reassignment_to_somebody_who_cannot_carry_it_is_refused(self):
        rec, contact = self.contact()
        assignment.ensure(rec, contact, MINE)
        # Petar owns a LinkedIn profile and no inbox.
        with self.assertRaises(assignment.NoEligibleSender):
            assignment.reassign(rec, contact, MINE, "email", "petar",
                                by="ops", reason="no inbox")

    def test_a_channel_with_no_pool_is_recorded_not_raised(self):
        si.install([si.new_sender(MINE, "anna", "Anna"),
                    si.new_email_account(MINE, "a1", "anna",
                                         "a1@productive.test")])
        rec, contact = self.contact()
        assignment.ensure(rec, contact, MINE)
        block = contact["sender_assignment"]
        self.assertTrue(block["email"])
        self.assertIsNone(block.get("linkedin"))
        self.assertIn("linkedin", block["unavailable"])

    def test_the_pair_key_groups_the_two_humans(self):
        rec, contact = self.contact()
        assignment.ensure(rec, contact, MINE)
        self.assertEqual(assignment.pair_of(contact), "anna+petar")


if __name__ == "__main__":
    unittest.main()
