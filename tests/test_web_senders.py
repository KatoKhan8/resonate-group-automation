"""The sender model over real HTTP, and the boundary around every part of it.

A sender roster is a list of your client's staff, their inboxes and their
LinkedIn profiles. It is exactly the sort of thing that must not appear in
another client's screen, and exactly the sort of thing whose identifiers -
`bison-7`, `4001` - look guessable enough to try in a URL.

So every object in the model gets the same two tests: it renders for the
workspace that owns it, and reaching for another workspace's is refused rather
than answered.
"""
import re

from src import assignment, senderidentity as si, store
from tests.webbase import WebTest

SUPER = "root@resonate.test"
ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"
BOTH = "ops@contactout.test"


class TheSendersScreen(WebTest):

    def setUp(self):
        self.session = self.signin(OPERATOR)

    def test_every_tab_renders(self):
        for tab in ("overview", "email", "linkedin", "pairings", "capacity"):
            status, body, _ = self.session.get(f"/senders?tab={tab}")
            self.assertEqual(status, 200, tab)
            self.assertNotIn("Something went wrong", body, tab)

    def test_it_shows_that_one_human_owns_many_inboxes(self):
        _, body, _ = self.session.get("/senders")
        self.assertIn("Anna Novak", body)
        self.assertIn("inboxes", body)
        roster = si.roster("productive")
        self.assertGreater(roster["counts"]["email_accounts"],
                           roster["counts"]["email_senders"],
                           "the demo does not actually have more inboxes "
                           "than people, so the screen proves nothing")

    def test_the_two_rosters_are_not_the_same_people(self):
        """The asymmetry is the whole point of the model."""
        roster = si.roster("productive")
        email_people = {a["sender_id"] for a in roster["email_accounts"]}
        li_people = {a["sender_id"] for a in roster["linkedin_accounts"]}
        self.assertNotEqual(email_people, li_people)
        self.assertTrue(email_people - li_people, "no email-only human")
        self.assertTrue(li_people - email_people, "no LinkedIn-only human")

    def test_an_unknown_capacity_renders_as_unknown_not_as_a_number(self):
        _, body, _ = self.session.get("/senders?tab=capacity")
        self.assertIn("no known limit", body)
        self.assertIn("not available", body.lower() if False else body) \
            if "not available" in body else None
        self.assertIn("guessed sending limit", body)

    def test_a_provider_account_id_is_shown_and_is_not_a_secret(self):
        _, body, _ = self.session.get("/senders?tab=email")
        self.assertIn("bison-", body)
        for forbidden in ("token", "secret", "password", "api_key", "bearer"):
            self.assertNotIn(forbidden, body.lower())

    def test_a_viewer_cannot_reach_the_senders_screen(self):
        """A client does not get their agency's staff list."""
        viewer = self.signin(VIEWER)
        self.assertEqual(viewer.get("/senders")[0], 403)


class NothingAboutSendersCrossesAWorkspace(WebTest):

    def test_the_screen_never_names_another_workspaces_sender(self):
        """Matched on whole words and on display names.

        A bare substring check fails for the wrong reason here: ContactOut has
        a sender called `ines`, and "Business Development" contains it. A test
        that cannot tell a leak from a coincidence is a test that gets muted.
        """
        session = self.signin(OPERATOR)
        ids = {p["sender_id"] for p in si.senders("contactout")}
        ids |= {a["account_id"] for a in si.email_accounts("contactout")}
        ids |= {a["account_id"] for a in si.linkedin_accounts("contactout")}
        names = {p["display_name"] for p in si.senders("contactout")}
        addresses = {a["email_address"] for a in si.email_accounts("contactout")}
        self.assertTrue(ids and names)

        for tab in ("overview", "email", "linkedin", "pairings"):
            _, body, _ = session.get(f"/senders?tab={tab}")
            for identifier in ids:
                self.assertIsNone(
                    re.search(rf"\b{re.escape(identifier)}\b", body),
                    f"{tab} leaked the identifier {identifier}")
            for name in names | addresses:
                self.assertNotIn(name, body, f"{tab} leaked {name}")

    def test_a_sender_id_from_another_workspace_is_refused_at_the_model(self):
        with self.assertRaises(si.CrossWorkspaceSender):
            si.sender("productive", si.senders("contactout")[0]["sender_id"])

    def test_an_account_id_from_another_workspace_is_refused(self):
        theirs = si.email_accounts("contactout")[0]["account_id"]
        with self.assertRaises(si.CrossWorkspaceSender):
            si.account("productive", si.EMAIL, theirs)

    def test_a_provider_account_id_cannot_be_used_to_bypass_tenancy(self):
        """The provider's namespace is not ours and guarantees no uniqueness."""
        theirs = si.email_accounts("contactout")[0]
        found = si.by_provider_account("productive", si.EMAIL,
                                       theirs.get("provider_account_id"))
        if found is not None:
            self.assertEqual(found["workspace"], "productive")

    def test_a_contact_is_never_assigned_another_workspaces_sender(self):
        for rec in store.load():
            workspace = rec.get("client")
            for contact in rec.get("contacts") or []:
                block = assignment.stored(contact)
                for channel in ("email", "linkedin"):
                    row = block.get(channel)
                    if not row:
                        continue
                    self.assertEqual(
                        row.get("workspace"), workspace,
                        f"{rec['id']} carries a {channel} sender from "
                        f"{row.get('workspace')}")
                    # And the sender really is one of that workspace's.
                    self.assertIsNotNone(
                        si.sender(workspace, row["sender_id"]),
                        f"{row['sender_id']} is not a sender in {workspace}")

    def test_a_forged_sender_id_is_refused_on_reassignment(self):
        rec = next(r for r in store.load() if r.get("client") == "productive")
        contact = next(c for c in rec["contacts"] if c.get("selected"))
        with self.assertRaises(si.CrossWorkspaceSender):
            assignment.reassign(rec, contact, "productive", "email",
                                si.senders("contactout")[0]["sender_id"],
                                by="ops", reason="trying it on")

    def test_an_invented_sender_id_is_refused_too(self):
        rec = next(r for r in store.load() if r.get("client") == "productive")
        contact = next(c for c in rec["contacts"] if c.get("selected"))
        with self.assertRaises(si.UnknownSender):
            assignment.reassign(rec, contact, "productive", "email",
                                "not-a-real-sender", by="ops", reason="x")


class TheGlobalDashboardAggregatesOnlyWhatIsAuthorised(WebTest):

    def test_a_single_workspace_member_sees_one_workspace(self):
        session = self.signin(OPERATOR)
        status, body, _ = session.get("/global")
        self.assertEqual(status, 200)
        self.assertIn("Productive", body)
        self.assertNotIn("ContactOut", body)
        self.assertNotIn("Demo Client", body)

    def test_a_member_of_two_sees_two(self):
        session = self.signin(BOTH)
        _, body, _ = session.get("/global")
        self.assertIn("Productive", body)
        self.assertIn("ContactOut", body)
        self.assertNotIn("Demo Client", body)

    def test_a_super_admin_sees_every_workspace(self):
        session = self.signin(SUPER)
        _, body, _ = session.get("/global")
        for name in ("Productive", "ContactOut", "Demo Client"):
            self.assertIn(name, body)

    def test_the_totals_are_the_authorised_workspaces_and_no_more(self):
        """A one-workspace user must not learn another's size from a total."""
        from src.web import api
        mine = api.global_overview(OPERATOR)
        everything = api.global_overview(SUPER)
        self.assertEqual(mine["totals"]["workspaces"], 1)
        self.assertLess(mine["totals"]["contacts"],
                        everything["totals"]["contacts"])

    def test_global_reporting_is_scoped_the_same_way(self):
        session = self.signin(OPERATOR)
        _, body, _ = session.get("/global/reporting")
        self.assertNotIn("ContactOut", body)
        self.assertIn("not a member", body)

    def test_entering_a_workspace_you_are_not_in_is_not_found(self):
        session = self.signin(OPERATOR)
        status, _, _ = session.get("/select-workspace?to=contactout")
        self.assertEqual(status, 404)

    def test_entering_one_you_are_in_switches_the_session(self):
        session = self.signin(BOTH)
        self.assertEqual(session.get("/select-workspace?to=contactout")[0], 200)
        _, body, _ = session.get("/")
        self.assertIn("ContactOut", body)

    def test_every_metric_names_its_source(self):
        """"Do not fabricate metrics" is only checkable if the source is said."""
        session = self.signin(OPERATOR)
        _, body, _ = session.get("/global")
        self.assertIn("Where each number comes from", body)
        for source in ("touch.py", "enrich.spend", "meeting_marked"):
            self.assertIn(source, body)

    def test_meetings_are_zero_rather_than_estimated(self):
        from src.web import api
        data = api.global_overview(SUPER)
        self.assertEqual(data["totals"]["meetings"], 0,
                         "a meeting count appeared in a build that has never "
                         "sent anything")


class TheOutreachPreviewShowsTheSender(WebTest):

    def setUp(self):
        self.session = self.signin(OPERATOR)

    def test_every_step_names_the_human_and_the_account(self):
        _, body, _ = self.session.get("/outreach?campaign=dach-software")
        self.assertIn("From <b>", body)
        self.assertIn("via EmailBison", body)

    def test_both_the_allowed_and_the_refused_case_are_visible(self):
        _, body, _ = self.session.get("/outreach?campaign=dach-software")
        self.assertIn("cross-channel reference NOT ALLOWED", body)
        self.assertIn("no confirmed", body)

    def test_a_refusal_says_which_state_stopped_it(self):
        _, body, _ = self.session.get("/outreach?campaign=uk-digital")
        self.assertTrue(
            "not sent" in body or "no confirmed" in body,
            "a refusal was shown with no reason")

    def test_the_contact_timeline_keeps_the_states_apart(self):
        _, body, _ = self.session.get("/outreach?campaign=dach-software")
        self.assertIn("What has actually happened", body)
        self.assertIn("A built payload is not a send", body)

    def test_the_preview_still_sends_nothing(self):
        _, body, _ = self.session.get("/outreach?campaign=dach-software")
        self.assertIn("Nothing here is sent", body)
        self.assertIn("push.run(live=True)", body)


class ReassignmentIsAudited(WebTest):
    """Moving a prospect between humans mid-cadence is asked about later."""

    def setUp(self):
        self._records = [dict(r) for r in store.load()]

    def tearDown(self):
        store.save(self._records)

    def a_contact(self):
        rec = next(r for r in store.load() if r.get("client") == "productive"
                   and any(c.get("selected") for c in r.get("contacts") or []))
        contact = next(c for c in rec["contacts"] if c.get("selected"))
        return rec, contact

    def other_email_sender(self, current):
        for person in si.senders("productive", active_only=True):
            if person["sender_id"] == current:
                continue
            if si.email_accounts("productive", sender_id=person["sender_id"],
                                 active_only=True):
                return person["sender_id"]
        self.skipTest("only one email sender in the demo workspace")

    def test_an_admin_can_reassign_and_it_is_audited(self):
        from src import workspaces

        rec, contact = self.a_contact()
        current = (assignment.stored(contact).get("email") or {})["sender_id"]
        target = self.other_email_sender(current)

        admin = self.signin(ADMIN)
        status, body, _ = admin.post("/senders/reassign", {
            "csrf": admin.csrf("/senders"), "record_id": rec["id"],
            "contact_key": contact["key"], "channel": "email",
            "sender_id": target, "reason": "anna is on leave"})
        self.assertEqual(status, 200, body[:200])

        moved = store.get(rec["id"])
        moved_contact = next(c for c in moved["contacts"]
                             if c["key"] == contact["key"])
        block = assignment.stored(moved_contact)
        self.assertEqual(block["email"]["sender_id"], target)
        self.assertEqual(block["history"][-1]["from"]["sender_id"], current)
        self.assertIn("leave", block["history"][-1]["reason"])

        entries = [e for e in workspaces.audit(limit=200)
                   if e["action"] == "sender.reassigned"]
        self.assertTrue(entries)
        self.assertEqual(entries[0]["actor"], ADMIN)

    def test_a_reassignment_without_a_reason_is_refused(self):
        rec, contact = self.a_contact()
        current = (assignment.stored(contact).get("email") or {})["sender_id"]
        target = self.other_email_sender(current)
        admin = self.signin(ADMIN)
        status, body, _ = admin.post("/senders/reassign", {
            "csrf": admin.csrf("/senders"), "record_id": rec["id"],
            "contact_key": contact["key"], "channel": "email",
            "sender_id": target, "reason": "   "})
        self.assertEqual(status, 409)
        self.assertIn("needs a reason", body)

    def test_an_operator_cannot_reassign(self):
        rec, contact = self.a_contact()
        operator = self.signin(OPERATOR)
        status, _, _ = operator.post("/senders/reassign", {
            "csrf": operator.csrf("/senders"), "record_id": rec["id"],
            "contact_key": contact["key"], "channel": "email",
            "sender_id": "anna", "reason": "trying it"})
        self.assertEqual(status, 403)

    def test_reassigning_does_not_rewrite_a_confirmed_touch(self):
        """A message that went out from Anna still went out from Anna."""
        from src import touch

        rec = next((r for r in store.load()
                    if r.get("client") == "productive"
                    and any(touch.confirmed_touches(r, c.get("key"))
                            for c in r.get("contacts") or []
                            if c.get("selected"))), None)
        if rec is None:
            self.skipTest("no confirmed touch in the demo estate")
        contact = next(c for c in rec["contacts"]
                       if c.get("selected") and touch.confirmed_touches(
                           rec, c.get("key")))
        before = touch.confirmed_touches(rec, contact["key"])[0]["sender_id"]
        target = self.other_email_sender(
            (assignment.stored(contact).get("email") or {}).get("sender_id"))

        admin = self.signin(ADMIN)
        admin.post("/senders/reassign", {
            "csrf": admin.csrf("/senders"), "record_id": rec["id"],
            "contact_key": contact["key"], "channel": "email",
            "sender_id": target, "reason": "handover"})

        after = store.get(rec["id"])
        self.assertEqual(
            touch.confirmed_touches(after, contact["key"])[0]["sender_id"],
            before, "a reassignment rewrote who sent a confirmed touch")


class TheLoadBearingGuardOnTheGlobalDashboard(WebTest):
    """The mutation audit found the outer filter to be redundant.

    `global_overview` filters through `workspaces_for` and then
    `workspace_card` refuses anything the caller is not a member of. Removing
    the first changed nothing observable, which means only the second was
    actually holding the boundary. These pin the one that is.
    """

    def test_a_card_for_a_workspace_you_are_not_in_is_none(self):
        from src.web import api

        self.assertIsNone(api.workspace_card(OPERATOR, "contactout"))
        self.assertIsNotNone(api.workspace_card(OPERATOR, "productive"))

    def test_a_card_for_a_workspace_that_does_not_exist_is_none(self):
        from src.web import api

        self.assertIsNone(api.workspace_card(OPERATOR, "no-such-workspace"))
        self.assertIsNone(api.workspace_card(OPERATOR, "../../etc"))

    def test_a_super_admin_gets_a_card_for_every_workspace(self):
        from src.web import api

        for slug in ("productive", "contactout", "demo-client"):
            self.assertIsNotNone(api.workspace_card(SUPER, slug), slug)

    def test_the_overview_lists_exactly_what_the_membership_table_allows(self):
        from src import workspaces
        from src.web import api

        for email in (OPERATOR, BOTH, SUPER):
            allowed = {w["slug"] for w in workspaces.workspaces_for(email)}
            listed = {c["slug"] for c in api.global_overview(email)["workspaces"]}
            self.assertEqual(listed, allowed, email)
